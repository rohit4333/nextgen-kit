# Audio engine for the three 23.8s regional short reels.
#
# Same Noise-to-Signal sound design as the 41.2s master, retimed onto five scenes:
#   S1 hook (0-3.8) -> S4 turn (3.8-7.7) -> S6 tutor (7.7-14.7)
#   -> S7 confidence (14.7-18.4) -> S8 CTA (18.4-23.8)
#
# Only the hook VO changes between variants; everything from 3.8s onward is
# bit-identical. The 41.2s master and its engine are never modified.
#
# Reuses every DSP helper from reel_audio_engine.py; only timeline, clarity arc,
# texture envelope and click marks are short-specific.

from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import reel_audio_engine as e  # noqa: E402

SR = e.SR
T = [0, 3.8, 7.7, 14.7, 18.4, 23.8]
TOTAL = T[-1]

# Source frames / score sections kept from the original eight-scene cut.
PICK = [0, 3, 5, 6, 7]

HOOKS = {
    "neutral": "short-hook-neutral.wav",
    "sg-gcc": "short-hook-sg-gcc.wav",
    "au": "short-hook-au.wav",
}

# (clip filename, start within the short timeline)
VO = [
    (None, 0.15),                 # hook — filled from HOOKS per variant
    ("vo-s4.wav", 4.05),          # turn: "finally get it" at ~6.29s
    ("short-tutor.wav", 7.82),    # compressed credentials
    ("vo-s7.wav", 14.95),         # confidence
    ("vo-s8.wav", 18.65),         # CTA
]

# Pen-click motif. The fourth click sits at 13.05s (not the draft's 12.48s)
# because the measured tutor VO reaches "bhaan zoo" at 13.22s after compression.
CLICKS = [
    (6.15, 0.070, 1760.0),   # insight turn
    (7.86, 0.060, 1760.0),   # engineer / Samsung
    (10.48, 0.070, 1850.0),  # IIIT Allahabad
    (13.05, 0.075, 2000.0),  # bhaan zoo
    (18.56, 0.090, 2200.0),  # free demo / CTA
]


def _with_total(total, fn, *args, **kwargs):
    """Run an engine helper with a temporary TOTAL so buffers match this cut."""
    saved = e.TOTAL
    e.TOTAL = total
    try:
        return fn(*args, **kwargs)
    finally:
        e.TOTAL = saved


def retime_score(seg):
    """Lift old score sections PICK[i] onto short scene i with pre-roll overlap."""
    out = np.zeros((int(TOTAL * SR), 2), dtype=np.float32)
    pre = int(0.28 * SR)
    for i in range(len(T) - 1):
        pre_i = pre if i else 0
        src = int(e.OLD_T[PICK[i]] * SR) - pre_i
        n = int((T[i + 1] - T[i]) * SR) + pre_i
        dst = int(T[i] * SR) - pre_i
        part = seg[max(0, src):src + n].copy()
        if pre_i:
            k = min(pre_i, len(part))
            fin = np.linspace(0, 1, k, dtype=np.float32)[:, None] ** 1.5
            fout = np.linspace(1, 0, k, dtype=np.float32)[:, None] ** 1.5
            out[dst:dst + k] *= fout
            part[:k] *= fin
        d = min(len(part), out.shape[0] - dst)
        if d > 0:
            out[dst:dst + d] += part[:d]
    return out


def transition(at):
    return _with_total(TOTAL, e.transition, at)


def click(at, amp, base):
    return _with_total(TOTAL, e.click_sfx, at, amp, base)


def classroom_texture():
    """Crowded-room murmur under the hook only; clears before the turn."""
    n = int(TOTAL * SR)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(2024)
    noise = rng.standard_normal(n).astype(np.float32)
    noise = e.bpf(np.stack([noise, noise], axis=1), 300, 1100, 2)[:, 0]
    trem = 0.65 + 0.35 * np.sin(2 * np.pi * 5.3 * tt)
    env = e.smoothstep(0.0, 1.0, tt) * (1.0 - e.smoothstep(3.0, 4.6, tt))
    sig = (noise * trem * env * 0.010).astype(np.float32)
    out = np.zeros((n, 2), dtype=np.float32)
    out[:, 0] = sig
    out[:, 1] = np.roll(sig, 311)
    return out


def clarity_w(tt):
    """Muffled/narrow hook -> opens at the 6.0-6.8s insight."""
    w = np.zeros_like(tt, dtype=np.float32)
    w += 0.12 * e.smoothstep(0.0, 2.0, tt)
    w += 0.18 * e.smoothstep(2.0, 5.9, tt)
    w += 0.70 * e.smoothstep(6.0, 6.8, tt)
    return w


def clarity_process(seg, w, texture):
    seg = seg + texture
    muffled = e.lpf(seg, 1600, 4)
    seg = muffled * (1 - w[:, None]) + seg * w[:, None]
    mid = seg.mean(axis=1)
    side = (seg[:, 0] - seg[:, 1]) * 0.5
    sw = 0.35 + 0.65 * w
    seg = np.stack([mid + sw * side, mid - sw * side], axis=1)
    for at, amp, base in CLICKS:
        seg += click(at, amp, base)
    return seg.astype(np.float32)


def build_mix(variant="neutral"):
    """Return the mastered stereo mix for one regional hook variant."""
    if variant not in HOOKS:
        raise ValueError(f"unknown variant: {variant}")

    n = int(TOTAL * SR)
    bed, perc, sfx = e.build_score_old()
    bed, perc, sfx = retime_score(bed), retime_score(perc), retime_score(sfx)

    for at in T[1:-1]:
        sfx += transition(at)

    music = bed + perc * 0.65 + sfx * 2.5
    music = e.hpf(music, 32)
    music *= 1.82
    music = music - 0.10 * e.bpf(music, 180, 430)
    music = music + 0.055 * e.bpf(music, 7500, 14000)
    music = music + e.convolve_reverb(music, e.make_ir(), wet=0.12)
    music = e.bus_compress(music, -21.0, 2.0, 3.5, 45)

    voice = np.zeros((n, 2), dtype=np.float32)
    for name, start in VO:
        fname = HOOKS[variant] if name is None else name
        vp = ROOT / "exports" / "vo" / fname
        if not vp.exists():
            raise SystemExit(f"missing VO clip: {vp}")
        seg = e.process_vo(e.trim_vo(e.read_wav(vp)))
        voice += e.place(seg * 1.18, start, length_s=TOTAL)

    duck = e.duck_gain(voice, depth_db=7.5)
    low = e.lpf(music, 170, 4)
    high = (music - low).astype(np.float32)
    bed_out = (low * e.duck_gain(voice, depth_db=13.0) + high * duck).astype(np.float32)

    tt = np.arange(n) / SR
    bed_out = clarity_process(bed_out, clarity_w(tt), classroom_texture())

    head, tail = int(0.15 * SR), int(0.9 * SR)
    bed_out[:head] *= np.linspace(0, 1, head)[:, None]
    bed_out[-tail:] *= (np.linspace(1, 0, tail) ** 1.7)[:, None]

    mix = bed_out + voice
    vf = int(0.10 * SR)
    mix[-vf:] *= np.linspace(1, 0.985, vf)[:, None]
    mix = np.tanh(mix * 1.05) / np.tanh(1.05)
    mix = e.master(mix, target_lufs=-14.0, ceiling_db=-2.0)
    return mix.astype(np.float32)
