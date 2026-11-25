# Audio engine for the full 8-scene regional reels.
#
# Shares the approved Noise-to-Signal master engine and its 41.2s timeline.
# Only two VO files differ per variant: the S1 hook and the corrected S6 line.
# The 41.2s master mix and its files are never modified.

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import reel_audio_engine as e  # noqa: E402

SR = e.SR
T = e.T
TOTAL = e.TOTAL

HOOKS = {
    "neutral": "vo-s1.wav",
    "sg-gcc": "short-hook-sg-gcc.wav",
    "au": "short-hook-au.wav",
}
TUTOR = "full-tutor.wav"


def voice_file(idx, variant):
    if idx == 1:
        return HOOKS[variant]
    if idx == 6:
        return TUTOR
    return f"vo-s{idx}.wav"


def build_mix(variant="neutral"):
    """Master sound design with regional S1 and corrected S6 narration."""
    if variant not in HOOKS:
        raise ValueError(f"unknown variant: {variant}")

    n = int(TOTAL * SR)
    bed, perc, sfx = e.build_score_old()
    bed, perc, sfx = e.retime_score(bed), e.retime_score(perc), e.retime_score(sfx)

    for at in T[1:-1]:
        sfx += e.transition(at)

    music = bed + perc * 0.65 + sfx * 2.5
    music = e.hpf(music, 32)
    music *= 1.82
    music = music - 0.10 * e.bpf(music, 180, 430)
    music = music + 0.055 * e.bpf(music, 7500, 14000)
    music = music + e.convolve_reverb(music, e.make_ir(), wet=0.12)
    music = e.bus_compress(music, -21.0, 2.0, 3.5, 45)

    voice = np.zeros((n, 2), dtype=np.float32)
    for idx, start in e.VO_MAP:
        vp = ROOT / "exports" / "vo" / voice_file(idx, variant)
        if not vp.exists():
            raise SystemExit(f"missing VO clip: {vp}")
        seg = e.process_vo(e.trim_vo(e.read_wav(vp)))
        voice += e.place(seg * 1.18, start)

    duck = e.duck_gain(voice, depth_db=7.5)
    low = e.lpf(music, 170, 4)
    high = (music - low).astype(np.float32)
    bed_out = (low * e.duck_gain(voice, depth_db=13.0) + high * duck).astype(np.float32)

    texture = e.classroom_texture()
    tt = np.arange(n) / SR
    w = e.clarity_w(tt)
    bed_out = e.clarity_process(bed_out, w, texture)
    music_out = e.clarity_process(music, w, texture)

    head, tail = int(0.15 * SR), int(1.2 * SR)
    for m in (bed_out, music_out):
        m[:head] *= np.linspace(0, 1, head)[:, None]
        m[-tail:] *= (np.linspace(1, 0, tail) ** 1.7)[:, None]

    mix = bed_out + voice
    vf = int(0.10 * SR)
    mix[-vf:] *= np.linspace(1, 0.985, vf)[:, None]
    mix = np.tanh(mix * 1.05) / np.tanh(1.05)
    mix = e.master(mix, target_lufs=-14.0, ceiling_db=-2.0)
    music_out = e.norm(music_out, 0.89)
    narration = e.norm(voice, 0.90)
    return mix.astype(np.float32), music_out.astype(np.float32), narration.astype(np.float32)
