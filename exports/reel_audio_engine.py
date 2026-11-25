# Cinematic score + SFX + narration mixing engine for the 41.2s reel.
# Legacy reel-60s filenames are kept so the export pipeline stays unchanged.
#
# Design notes
#  - 120 BPM grid (0.5 s beat) so every cut lands on a musical pulse.
#  - Section-aware arrangement: tense lift -> empathy -> build -> high lift ->
#    warm flow -> confidence -> bright resolve -> elevated trusted close.
#  - Felt-piano, bowed-string pads, sub bass and soft organic percussion instead
#    of EDM drums. Reverb send on the music only; narration stays dry and close.
#  - Noise-to-Signal arc: the bed starts muffled/narrow and opens at the insight;
#    a soft pen-click marks each reveal while the VO is never filtered.
#  - Look-ahead sidechain: music dips smoothly under every spoken phrase and
#    recovers without pumping.
#
# Only audio is produced here. Video files are never touched.

from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, lfilter, resample_poly, sosfilt
from scipy.ndimage import minimum_filter1d, uniform_filter1d

ROOT = Path(__file__).resolve().parent.parent
SR = 48000

# The score was composed on the original 56s grid. Each scene is now trimmed to
# the new, tighter cut — the music keeps its tempo and timbre, only the silence
# after each narration line is removed.
OLD_TOTAL = 56.0
OLD_T = [0, 7.5, 13.5, 19, 25.5, 32, 41, 46, 56]

T = [0, 4.8, 10.2, 15.1, 19, 23.9, 32.1, 35.8, 41.2]
TOTAL = T[-1]

# ---------------------------------------------------------------- utilities

def to_stereo(x):
    if x.ndim == 1:
        return np.stack([x, x], axis=1)
    if x.shape[1] == 1:
        return np.repeat(x, 2, axis=1)
    return x[:, :2]


def read_wav(path):
    sr, d = wavfile.read(str(path))
    if d.dtype == np.int16:
        d = d.astype(np.float32) / 32768.0
    elif d.dtype == np.int32:
        d = d.astype(np.float32) / 2147483648.0
    elif d.dtype == np.uint8:
        d = (d.astype(np.float32) - 128) / 128.0
    else:
        d = d.astype(np.float32)
    d = to_stereo(d)
    if sr != SR:
        g = np.gcd(sr, SR)
        d = np.stack([resample_poly(d[:, c], SR // g, sr // g) for c in range(2)], axis=1)
    return d


def lpf(x, hz, order=4):
    sos = butter(order, min(hz, SR / 2 - 200), btype="low", fs=SR, output="sos")
    return np.stack([sosfilt(sos, x[:, c]) for c in range(2)], axis=1)


def hpf(x, hz, order=2):
    sos = butter(order, max(20, min(hz, SR / 2 - 200)), btype="high", fs=SR, output="sos")
    return np.stack([sosfilt(sos, x[:, c]) for c in range(2)], axis=1)


def bpf(x, lo, hi, order=2):
    lo = max(20, lo)
    hi = min(SR / 2 - 200, hi)
    if hi <= lo + 40:
        return x
    sos = butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return np.stack([sosfilt(sos, x[:, c]) for c in range(2)], axis=1)


def norm(x, peak=0.9):
    m = np.max(np.abs(x))
    return x * (peak / m) if m > 1e-8 else x


def db(x):
    return 20 * np.log10(max(float(np.sqrt(np.mean(x ** 2))), 1e-9))


def env_fade(n, fin=0.02, fout=0.05):
    e = np.ones(n)
    fi, fo = min(n, int(fin * SR)), min(n, int(fout * SR))
    if fi:
        e[:fi] = np.linspace(0, 1, fi) ** 1.5
    if fo:
        e[-fo:] *= np.linspace(1, 0, fo) ** 1.8
    return e


def place(seg, start_s, length_s=TOTAL):
    n = int(length_s * SR)
    out = np.zeros((n, 2), dtype=np.float32)
    i0 = int(start_s * SR)
    if i0 >= n:
        return out
    if i0 < 0:
        seg, i0 = seg[-i0:], 0
    l = min(len(seg), n - i0)
    if l > 0:
        out[i0:i0 + l] += seg[:l]
    return out


def trim_vo(seg, thresh=0.006, pre=0.02, post=0.10):
    idx = np.where(np.max(np.abs(seg), axis=1) > thresh)[0]
    if not len(idx):
        return seg
    return seg[max(0, idx[0] - int(pre * SR)): idx[-1] + int(post * SR)]


def build_score_old():
    """Generate the score on its original 56s grid, then restore TOTAL."""
    global TOTAL
    saved = TOTAL
    TOTAL = OLD_TOTAL
    try:
        return build_score()
    finally:
        TOTAL = saved


def retime_score(seg):
    """Lift each scored scene onto the new cut with a smooth overlap at every
    boundary. A little pre-roll lets each scene's pad/percussion tail overlap
    the next scene instead of stopping abruptly on the cut."""
    out = np.zeros((int(TOTAL * SR), 2), dtype=np.float32)
    pre = int(0.28 * SR)
    for i in range(len(T) - 1):
        pre_i = pre if i else 0
        src = int(OLD_T[i] * SR) - pre_i
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
        out[dst:dst + d] += part[:d]
    return out


# ---------------------------------------------------------------- clarity arc

def smoothstep(a, b, x):
    y = np.clip((x - a) / (b - a), 0.0, 1.0)
    return y * y * (3 - 2 * y)


def clarity_w(tt):
    """0 = muffled/narrow, 1 = open/wide; the jump at 17.3-18.2s is the turn."""
    w = np.zeros_like(tt, dtype=np.float32)
    w += 0.10 * smoothstep(T[1], T[2], tt)
    w += 0.20 * smoothstep(T[2], T[3], tt)
    w += 0.10 * smoothstep(T[3], 17.3, tt)
    w += 0.60 * smoothstep(17.3, 18.2, tt)
    return w


def click_sfx(at, amp=0.070, base=1760.0):
    """Short pen-click / insight accent, placed just before each spoken beat."""
    n = int(TOTAL * SR)
    i0 = int(at * SR)
    l = min(int(0.045 * SR), n - i0)
    out = np.zeros((n, 2), dtype=np.float32)
    if l <= 0:
        return out
    t = np.arange(l) / SR
    rng = np.random.default_rng(77 + int(base))
    noise = rng.standard_normal(l).astype(np.float32)
    noise = bpf(np.stack([noise, noise], axis=1), 1600, 4200, 2)[:, 0]
    sig = (noise * np.exp(-t / 0.006)
           + 0.60 * np.sin(2 * np.pi * base * t) * np.exp(-t / 0.012)
           + 0.30 * np.sin(2 * np.pi * base * 1.5 * t) * np.exp(-t / 0.010))
    out[i0:i0 + l, 0] = amp * sig
    out[i0:i0 + l, 1] = amp * sig
    return out


# Each click lands ~0.12s before its narration phrase; pitch rises with the story.
CLICKS = [
    (T[3] + 2.49 - 0.14, 0.070, 1760.0),  # S4 "finally get it" — the turn
    (T[5] + 0.28 - 0.12, 0.060, 1760.0),  # S6 tutor's name
    (T[5] + 1.92 - 0.12, 0.070, 1850.0),  # S6 Samsung
    (T[5] + 3.93 - 0.12, 0.065, 1900.0),  # S6 B.Tech
    (T[5] + 5.16 - 0.12, 0.078, 2000.0),  # S6 IIIT Allahabad
    (T[5] + 6.53 - 0.12, 0.085, 2150.0),  # S6 Bhaanzu
    (T[7] + 0.28 - 0.12, 0.090, 2200.0),  # S8 free demo / CTA
]


def classroom_texture():
    """Faint crowded-room murmur for S1-S3; it gets muffled with the bed."""
    n = int(TOTAL * SR)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(2024)
    noise = rng.standard_normal(n).astype(np.float32)
    noise = bpf(np.stack([noise, noise], axis=1), 300, 1100, 2)[:, 0]
    trem = 0.65 + 0.35 * np.sin(2 * np.pi * 5.3 * tt)
    env = smoothstep(0.0, 1.5, tt) * (1.0 - smoothstep(14.0, 16.5, tt))
    sig = (noise * trem * env * 0.010).astype(np.float32)
    out = np.zeros((n, 2), dtype=np.float32)
    out[:, 0] = sig
    out[:, 1] = np.roll(sig, 311)
    return out


def clarity_process(seg, w, texture):
    """Apply the muffled->open filter, stereo widening and insight clicks."""
    seg = seg + texture
    muffled = lpf(seg, 1600, 4)
    seg = muffled * (1 - w[:, None]) + seg * w[:, None]
    mid = seg.mean(axis=1)
    side = (seg[:, 0] - seg[:, 1]) * 0.5
    sw = 0.35 + 0.65 * w
    seg = np.stack([mid + sw * side, mid - sw * side], axis=1)
    for at, amp, base in CLICKS:
        seg += click_sfx(at, amp, base)
    return seg.astype(np.float32)


# ---------------------------------------------------------------- instruments

def pad(freqs, start, dur, amp=0.10, attack=1.4, release=2.0, bright=2600, seed=0):
    """Bowed-string style pad: harmonic-rich, slow vibrato, wide stereo."""
    n = int(TOTAL * SR)
    i0 = int(start * SR)
    l = min(int(dur * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    t = np.arange(l) / SR
    rng = np.random.default_rng(1000 + seed)
    sig = np.zeros((l, 2), dtype=np.float32)
    for j, f in enumerate(sorted(freqs)):
        vib = 1 + 0.0016 * np.sin(2 * np.pi * (0.13 + 0.02 * j) * t + rng.uniform(0, 6.28))
        det = 1 + (j - len(freqs) / 2) * 0.0016
        for ch, d in ((0, 1.0), (1, 1.0019)):
            w = np.zeros(l)
            for h in range(1, 7):
                w += (1.0 / h ** 1.45) * np.sin(2 * np.pi * f * det * d * vib * h * t + rng.uniform(0, 6.28))
            sig[:, ch] += w.astype(np.float32)
    sig /= max(1, len(freqs))
    sig = lpf(sig, bright, 2)
    e = np.ones(l)
    a, r = min(l, int(attack * SR)), min(l, int(release * SR))
    if a:
        e[:a] = np.linspace(0, 1, a) ** 1.5
    if r:
        e[-r:] *= np.linspace(1, 0, r) ** 1.8
    out = np.zeros((n, 2), dtype=np.float32)
    out[i0:i0 + l] = sig * (amp * e)[:, None]
    return out


def piano(freq, at, amp=0.05, dur=2.4, pan=0.0, seed=0):
    """Felt piano: soft hammer, quick attack, warm decay."""
    n = int(TOTAL * SR)
    i0 = int(at * SR)
    l = min(int(dur * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    t = np.arange(l) / SR
    rng = np.random.default_rng(2000 + seed)
    sig = np.zeros(l)
    for h in range(1, 7):
        d = 1.9 + h * 0.55
        sig += (1.0 / h ** 1.55) * np.sin(2 * np.pi * freq * h * (1 + 0.0007 * h) * t + rng.uniform(0, 6.28)) * np.exp(-t * d)
    atk = max(1, int(0.006 * SR))
    sig[:atk] *= np.linspace(0, 1, atk) ** 1.3
    sig = lpf(np.stack([sig, sig], axis=1), 4200, 2)[:, 0]
    left, right = 1 - max(0.0, pan) * 0.55, 1 + min(0.0, pan) * 0.55
    out = np.zeros((n, 2), dtype=np.float32)
    out[i0:i0 + l, 0] = amp * sig * left
    out[i0:i0 + l, 1] = amp * sig * right
    return out


def sub(freq, start, dur, amp=0.05, attack=0.5, release=1.2):
    n = int(TOTAL * SR)
    i0 = int(start * SR)
    l = min(int(dur * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    t = np.arange(l) / SR
    sig = np.sin(2 * np.pi * freq * t) + 0.18 * np.sin(2 * np.pi * freq * 2 * t)
    e = np.ones(l)
    a, r = min(l, int(attack * SR)), min(l, int(release * SR))
    if a:
        e[:a] = np.linspace(0, 1, a) ** 1.4
    if r:
        e[-r:] *= np.linspace(1, 0, r) ** 1.6
    out = np.zeros((n, 2), dtype=np.float32)
    out[i0:i0 + l] = (amp * sig * e)[:, None]
    return out


def kick(at, amp=0.20, seed=0):
    n = int(TOTAL * SR)
    i0 = int(at * SR)
    l = min(int(0.75 * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    t = np.arange(l) / SR
    f = 46 + 74 * np.exp(-t * 24)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8.0)
    click = np.random.default_rng(3000 + seed).standard_normal(l) * np.exp(-t * 220) * 0.18
    sig = np.tanh((body + click) * 1.6)
    out = np.zeros((n, 2), dtype=np.float32)
    out[i0:i0 + l] = (amp * sig)[:, None]
    return out


def rim(at, amp=0.055, seed=0):
    n = int(TOTAL * SR)
    i0 = int(at * SR)
    l = min(int(0.22 * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    t = np.arange(l) / SR
    rng = np.random.default_rng(4000 + seed)
    body = np.sin(2 * np.pi * 310 * t) * np.exp(-t * 34) * 0.5
    noise = sosfilt(butter(2, 1800, btype="high", fs=SR, output="sos"), rng.standard_normal(l)) * np.exp(-t * 55)
    sig = np.tanh(body + 0.5 * noise)
    out = np.zeros((n, 2), dtype=np.float32)
    out[i0:i0 + l] = (amp * sig)[:, None]
    return out


def shaker(at, amp=0.028, seed=0):
    n = int(TOTAL * SR)
    i0 = int(at * SR)
    l = min(int(0.11 * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    t = np.arange(l) / SR
    rng = np.random.default_rng(5000 + seed)
    noise = bpf(np.stack([rng.standard_normal(l)] * 2, axis=1), 3800, 10500)[:, 0]
    sig = noise * (1 - np.exp(-t * 900)) * np.exp(-t * 42)
    out = np.zeros((n, 2), dtype=np.float32)
    pan = 0.16 * np.sin(seed * 1.7)
    out[i0:i0 + l, 0] = amp * sig * (1 - pan)
    out[i0:i0 + l, 1] = amp * sig * (1 + pan)
    return out


def whoosh(at, dur=0.62, amp=0.034, up=True):
    n = int(TOTAL * SR)
    i0 = int(max(0, at - dur * 0.5) * SR)
    l = min(int(dur * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    rng = np.random.default_rng(6000 + int(at * 41))
    x = rng.standard_normal((l, 2)).astype(np.float32)
    chunks, cs = 24, max(1, l // 24)
    y = np.zeros_like(x)
    for i in range(chunks):
        a, b = i * cs, (l if i == chunks - 1 else (i + 1) * cs)
        p = i / max(1, chunks - 1)
        c = (420 + 3000 * p) if up else (3400 - 2900 * p)
        y[a:b] = bpf(x[a:b], max(60, c - 600), min(SR / 2 - 300, c + 1400))
    t = np.linspace(0, 1, l)
    e = np.sin(np.pi * t) ** 1.7
    out = np.zeros((n, 2), dtype=np.float32)
    out[i0:i0 + l] = lpf(y, 7200, 2) * (amp * e)[:, None]
    return out


def tick(at, amp=0.020, freq=2100):
    n = int(TOTAL * SR)
    i0 = int(at * SR)
    l = min(int(0.09 * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    t = np.arange(l) / SR
    sig = np.sin(2 * np.pi * freq * t) * np.exp(-t * 70) + 0.35 * np.sin(2 * np.pi * freq * 2.6 * t) * np.exp(-t * 95)
    out = np.zeros((n, 2), dtype=np.float32)
    out[i0:i0 + l] = (amp * sig)[:, None]
    return out


def chime(at, amp=0.030, base=784.0):
    n = int(TOTAL * SR)
    i0 = int(at * SR)
    l = min(int(2.6 * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    t = np.arange(l) / SR
    sig = (np.sin(2 * np.pi * base * t) + 0.5 * np.sin(2 * np.pi * base * 1.5 * t)
           + 0.22 * np.sin(2 * np.pi * base * 2 * t)) * np.exp(-t * 2.4)
    atk = max(1, int(0.008 * SR))
    sig[:atk] *= np.linspace(0, 1, atk)
    out = np.zeros((n, 2), dtype=np.float32)
    out[i0:i0 + l, 0] = amp * sig
    out[i0:i0 + l, 1] = amp * np.roll(sig, int(0.011 * SR))
    return out


def transition(at, dur=0.32, amp=0.020):
    """A soft 'clearing breath' on every cut.

    Low-passed noise plus a quiet rising glide, with a squared-sine envelope so
    it starts and ends at zero. It reads as a thought resetting, not a whoosh.
    """
    n = int(TOTAL * SR)
    i0 = int(max(0, at - dur * 0.5) * SR)
    l = min(int(dur * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    t = np.arange(l) / SR
    rng = np.random.default_rng(4321 + int(at * 13))
    noise = rng.standard_normal(l).astype(np.float32)
    noise = lpf(np.stack([noise, noise], axis=1), 1800, 3)[:, 0]
    glide = np.sin(2 * np.pi * np.cumsum(180 + 160 * t / dur) / SR).astype(np.float32)
    env = np.sin(np.pi * t / dur) ** 2
    sig = (0.85 * noise + 0.15 * glide) * env
    out = np.zeros((n, 2), dtype=np.float32)
    out[i0:i0 + l, 0] = amp * sig
    out[i0:i0 + l, 1] = amp * sig
    return out


def impact(at, amp=0.07):
    n = int(TOTAL * SR)
    i0 = int(at * SR)
    l = min(int(1.4 * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    t = np.arange(l) / SR
    hit = np.sin(2 * np.pi * 52 * t * np.exp(-t * 0.5)) * np.exp(-t * 6.0)
    rng = np.random.default_rng(7000 + int(at * 17))
    click = rng.standard_normal(l) * np.exp(-t * 60) * 0.12
    out = np.zeros((n, 2), dtype=np.float32)
    out[i0:i0 + l] = (amp * np.tanh(hit + click))[:, None]
    return out


def riser(end_at, dur=1.3, amp=0.045):
    n = int(TOTAL * SR)
    i0 = int(max(0, end_at - dur) * SR)
    l = min(int(dur * SR), n - i0)
    if l <= 0:
        return np.zeros((n, 2), dtype=np.float32)
    rng = np.random.default_rng(8000 + int(end_at * 13))
    x = rng.standard_normal((l, 2)).astype(np.float32)
    chunks, cs = 26, max(1, l // 26)
    y = np.zeros_like(x)
    for i in range(chunks):
        a, b = i * cs, (l if i == chunks - 1 else (i + 1) * cs)
        p = i / max(1, chunks - 1)
        lo = 300 + 2800 * p
        y[a:b] = bpf(x[a:b], lo, lo + 900)
    t = np.linspace(0, 1, l)
    y *= (amp * (t ** 2.1))[:, None]
    out = np.zeros((n, 2), dtype=np.float32)
    out[i0:i0 + l] = y
    return out


# ---------------------------------------------------------------- reverb / dynamics

def make_ir(dur=1.35, seed=11, damp=5200):
    l = int(dur * SR)
    t = np.arange(l) / SR
    rng = np.random.default_rng(seed)
    ir = rng.standard_normal((l, 2)) * np.exp(-t * 3.1)[:, None]
    for d, g in ((0.021, 0.5), (0.037, 0.35), (0.055, 0.22)):
        i = int(d * SR)
        if i < l:
            ir[i:i + 200] += g * rng.standard_normal((min(200, l - i), 2)) * np.exp(-np.arange(min(200, l - i)) / 60)[:, None]
    ir = lpf(ir.astype(np.float32), damp, 2)
    ir /= np.sqrt(np.sum(ir ** 2, axis=0, keepdims=True)) + 1e-9
    return ir


def convolve_reverb(x, ir, wet=0.12, predelay_ms=18):
    pre = np.zeros((int(predelay_ms * SR / 1000), 2), dtype=np.float32)
    dry = np.concatenate([pre, x], axis=0)
    wet_sig = np.stack([fftconvolve(dry[:, c], ir[:, c])[:len(dry)] for c in range(2)], axis=1)
    wet_sig = hpf(wet_sig.astype(np.float32), 180)
    return wet_sig[:len(x)] * wet


def bus_compress(x, thresh_db=-20.0, ratio=2.2, makeup_db=3.5, win_ms=40):
    env = uniform_filter1d(np.max(np.abs(x), axis=1), size=max(1, int(SR * win_ms / 1000)), mode="nearest")
    th = 10 ** (thresh_db / 20.0)
    over = np.maximum(env / th, 1e-6)
    gain = np.ones_like(env)
    m = over > 1.0
    gain[m] = np.power(over[m], 1.0 / ratio - 1.0)
    return (x * (gain * 10 ** (makeup_db / 20.0))[:, None]).astype(np.float32)


def lufs(x):
    """Integrated loudness per ITU-R BS.1770-4 (K-weighting, 400 ms blocks,
    absolute -70 LUFS gate + relative -10 dB gate)."""
    x = to_stereo(x) if x.ndim == 1 else x
    b1, a1 = ([1.53512485958697, -2.69169618940638, 1.19839281085285],
              [1.0, -1.69065929318241, 0.73248077421585])
    b2, a2 = ([1.0, -2.0, 1.0],
              [1.0, -1.99004745483398, 0.99007225036621])
    y = np.stack([lfilter(b2, a2, lfilter(b1, a1, x[:, c])) for c in range(2)], axis=1)

    blk, hop = int(0.4 * SR), int(0.1 * SR)
    if len(y) < blk:
        z = np.array([np.mean(y ** 2, axis=0).sum()])
    else:
        z = np.array([np.mean(y[i:i + blk] ** 2, axis=0).sum()
                      for i in range(0, len(y) - blk + 1, hop)])
    l = -0.691 + 10 * np.log10(np.maximum(z, 1e-12))
    keep = l > -70.0
    if not np.any(keep):
        return -99.0
    rel = -0.691 + 10 * np.log10(np.mean(z[keep])) - 10.0
    keep &= l > rel
    return float(-0.691 + 10 * np.log10(np.mean(z[keep])))


# ---------------------------------------------------------------- sidechain

def duck_gain(voice, depth_db=9.5):
    """Smooth look-ahead ducking envelope from the narration stem."""
    v = np.max(np.abs(voice), axis=1)
    env = uniform_filter1d(v, size=int(0.05 * SR), mode="nearest")
    env = uniform_filter1d(env, size=int(0.18 * SR), mode="nearest")
    ref = np.percentile(env[env > 1e-4], 90) if np.any(env > 1e-4) else 1.0
    amt = np.clip(env / (ref * 0.75 + 1e-9), 0.0, 1.0) ** 0.85
    amt = uniform_filter1d(amt, size=int(0.26 * SR), mode="nearest")
    return (10 ** (-depth_db * amt / 20.0)).astype(np.float32)[:, None]


def soft_limit(x, ceiling_db=-2.0, look_ms=6.0):
    """Look-ahead peak limiter: transparent, no clipped transients."""
    ceiling = 10 ** (ceiling_db / 20.0)
    env = np.max(np.abs(x), axis=1)
    g = np.minimum(1.0, ceiling / np.maximum(env, 1e-9))
    look = max(1, int(SR * look_ms / 1000))
    g = minimum_filter1d(g, size=2 * look + 1, mode="nearest")   # look ahead
    g = uniform_filter1d(g, size=look + 1, mode="nearest")       # soft attack
    g = np.minimum(g, 1.0)
    return (x * g[:, None]).astype(np.float32)


def master(x, target_lufs=-14.0, ceiling_db=-2.0):
    """Loudness-match to a social-safe target, then hold the peak ceiling."""
    x = x.astype(np.float32)
    for _ in range(4):
        delta = target_lufs - lufs(x)
        if abs(delta) < 0.15:
            break
        x = x * (10 ** (delta / 20.0))
        x = soft_limit(x, ceiling_db)
    return soft_limit(x, ceiling_db)


# ---------------------------------------------------------------- score

A1, B1, D2, E2, F2, G2, A2, Bb2, C3, D3, E3, F3, G3, A3, Bb3, C4, D4, E4, F4, G4, A4, C5, E5, F5, G5, A5 = (
    55.00, 61.74, 73.42, 82.41, 87.31, 98.00, 110.00, 116.54, 130.81, 146.83, 164.81,
    174.61, 196.00, 220.00, 233.08, 261.63, 293.66, 329.63, 349.23, 392.00, 440.00,
    523.25, 659.25, 698.46, 783.99, 880.00)


def build_score():
    n = int(TOTAL * SR)
    bed = np.zeros((n, 2), dtype=np.float32)
    perc = np.zeros((n, 2), dtype=np.float32)
    sfx = np.zeros((n, 2), dtype=np.float32)

    def add_bus(bus, seg, g=1.0):
        bus += seg * g

    # ---- S1 (0-7.5) : attention — longer hold, pulse pushes it forward
    add_bus(bed, pad([D2, A2, D3, F3], 0.0, 8.1, amp=0.12, attack=0.8, release=1.4, bright=2200, seed=1))
    add_bus(bed, pad([A3, C4, E4], 2.5, 5.0, amp=0.028, attack=1.2, release=1.4, bright=3800, seed=2))
    add_bus(bed, sub(D2 / 2, 0.0, 8.0, amp=0.048, attack=0.6, release=1.2))
    for at, f, p, s in [(0.30, A4, -0.18, 3), (2.30, F4, 0.15, 4),
                        (4.30, C5, -0.10, 5), (6.10, E5, 0.14, 6)]:
        add_bus(bed, piano(f, at, amp=0.034, dur=2.6, pan=p, seed=s))
    for k, at in enumerate(np.arange(0.0, 7.5, 1.0)):
        add_bus(perc, kick(at, 0.17 if k else 0.20, seed=k))
    for k in range(15):
        add_bus(perc, shaker(2.5 + k * 0.32, 0.012, seed=k))
    for k, at in enumerate([3.5, 5.5]):
        add_bus(perc, rim(at, 0.030, seed=k + 1))
    add_bus(sfx, impact(0.0, 0.055))

    # ---- S2 (7.5-13.5) : empathy, no big drums, warm and quick
    add_bus(bed, pad([Bb2 / 2, F2, Bb2, D3, A3], 7.25, 6.6, amp=0.11, attack=1.3, release=1.6, bright=2400, seed=5))
    add_bus(bed, pad([D4, F4, A4], 9.0, 4.2, amp=0.022, attack=1.0, release=1.4, bright=3900, seed=6))
    add_bus(bed, sub(Bb2 / 2, 7.5, 6.0, amp=0.040, attack=0.9, release=1.2))
    for at, f, p, s in [(8.0, F4, -0.14, 6), (9.4, D4, 0.10, 7), (10.8, Bb3, -0.06, 8),
                        (12.0, A3, 0.14, 9)]:
        add_bus(bed, piano(f, at, amp=0.040, dur=2.6, pan=p, seed=s))
    add_bus(perc, rim(11.0, 0.026, 2))

    # ---- S3 (13.5-19) : the weight, tight build
    add_bus(bed, pad([F2, C3, F3, A3, E4], 13.25, 6.1, amp=0.12, attack=1.1, release=1.4, bright=2600, seed=11))
    add_bus(bed, sub(F2 / 2, 13.5, 5.6, amp=0.044, attack=0.7, release=1.1))
    for at, f, p, s in [(13.8, C4, -0.12, 12), (15.0, A3, 0.08, 13), (16.2, F4, -0.04, 14),
                        (17.4, E4, 0.12, 15)]:
        add_bus(bed, piano(f, at, amp=0.042, dur=2.4, pan=p, seed=s))
    for k, at in enumerate([13.5, 15.5, 17.5]):
        add_bus(perc, kick(at, 0.14, seed=k + 20))
    for k, at in enumerate([14.5, 16.5, 18.5]):
        add_bus(perc, rim(at, 0.045, seed=k + 30))
    for k in range(11):
        add_bus(perc, shaker(13.5 + k * 0.5, 0.018, seed=k + 40))

    # ---- S4 (19-25.5) : the turn — brighter, rising arpeggio
    add_bus(bed, pad([Bb2, F3, Bb3, D4, A3], 18.75, 7.1, amp=0.13, attack=0.9, release=1.8, bright=3300, seed=21))
    add_bus(bed, pad([D4, F4, A4, C5], 19.2, 6.3, amp=0.040, attack=1.2, release=1.8, bright=4200, seed=22))
    add_bus(bed, sub(Bb2 / 2, 19.0, 6.2, amp=0.052, attack=0.5, release=1.2))
    for at, f, p, s in [(19.4, F4, -0.16, 23), (20.6, A4, 0.12, 24), (21.8, Bb3, -0.08, 25),
                        (23.0, D4, 0.16, 26), (24.2, F4, -0.12, 27), (25.0, A4, 0.10, 28)]:
        add_bus(bed, piano(f, at, amp=0.042, dur=2.4, pan=p, seed=s))
    for k, at in enumerate(np.arange(19.5, 25.5, 0.5)):
        f = [Bb3, D4, F4, A4, C5][k % 5]
        add_bus(bed, piano(f * 2, at, amp=0.014, dur=1.1,
                           pan=0.30 * (-1 if k % 2 else 1), seed=60 + k))
    for k, at in enumerate(np.arange(19.0, 25.5, 1.0)):
        add_bus(perc, kick(at, 0.17, seed=70 + k))
    for k, at in enumerate([19.5, 21.5, 23.5, 25.0]):
        add_bus(perc, rim(at, 0.055, seed=80 + k))
    for k in range(26):
        add_bus(perc, shaker(19.25 + k * 0.25, 0.015, seed=90 + k))

    # ---- S5 (25.5-32) : warm flow, a little more drive
    add_bus(bed, pad([G2, D3, Bb3, F4, A3], 25.25, 7.1, amp=0.12, attack=1.0, release=1.6, bright=2800, seed=31))
    add_bus(bed, pad([C4, E4, G4], 26.5, 5.2, amp=0.025, attack=0.9, release=1.5, bright=4000, seed=32))
    add_bus(bed, sub(G2 / 2, 25.5, 6.2, amp=0.046, attack=0.6, release=1.4))
    for at, f, p, s in [(25.9, D4, -0.12, 32), (27.2, F4, 0.10, 33), (28.5, A4, -0.06, 34),
                        (29.8, Bb3, 0.12, 35), (31.0, D4, -0.10, 36)]:
        add_bus(bed, piano(f, at, amp=0.040, dur=2.5, pan=p, seed=s))
    for k, at in enumerate([25.5, 27.5, 29.5, 31.5]):
        add_bus(perc, kick(at, 0.13, seed=100 + k))
    for k, at in enumerate([26.5, 28.5, 30.5]):
        add_bus(perc, rim(at, 0.042, seed=110 + k))
    for k in range(13):
        add_bus(perc, shaker(25.75 + k * 0.5, 0.016, seed=120 + k))

    # ---- S6 (32-41) : confident, clear — the tutor, lifted top harmony
    add_bus(bed, pad([F2, C3, F3, A3, G4], 31.7, 9.7, amp=0.13, attack=0.8, release=1.9, bright=3100, seed=41))
    add_bus(bed, pad([C4, F4, A4, C5], 32.4, 8.4, amp=0.038, attack=1.1, release=2.0, bright=4400, seed=42))
    add_bus(bed, sub(F2 / 2, 32.0, 8.8, amp=0.052, attack=0.4, release=1.5))
    for at, f, p, s in [(32.6, A3, -0.14, 43), (33.9, C4, 0.12, 44), (35.2, F4, -0.08, 45),
                        (36.5, A4, 0.10, 46), (37.8, C5, -0.12, 47), (39.1, A4, 0.10, 48),
                        (40.2, F4, 0.06, 49)]:
        add_bus(bed, piano(f, at, amp=0.042, dur=2.4, pan=p, seed=s))
    for k, at in enumerate(np.arange(32.5, 40.5, 0.5)):
        f = [F4, A4, C5, F5][k % 4]
        add_bus(bed, piano(f, at, amp=0.013, dur=1.0,
                           pan=0.28 * (-1 if k % 2 else 1), seed=150 + k))
    for k, at in enumerate(np.arange(32.0, 41.0, 1.0)):
        add_bus(perc, kick(at, 0.075, seed=130 + k))
    for k, at in enumerate([32.5, 34.5, 36.5, 38.5, 40.5]):
        add_bus(perc, rim(at, 0.032, seed=140 + k))
    for k in range(18):
        add_bus(perc, shaker(32.25 + k * 0.5, 0.014, seed=160 + k))
    add_bus(sfx, tick(33.3, 0.018, 2100))
    add_bus(sfx, tick(33.9, 0.016, 2500))

    # ---- S7 (41-46) : bright resolve, short and rising
    add_bus(bed, pad([C3, G3, C4, E4, G4, C5], 40.75, 5.7, amp=0.125, attack=0.6, release=1.5, bright=3600, seed=51))
    add_bus(bed, sub(C3 / 2, 41.0, 5.0, amp=0.044, attack=0.4, release=1.2))
    for at, f, p, s in [(41.2, E4, -0.10, 52), (42.2, G4, 0.12, 53),
                        (43.2, C5, -0.06, 54), (44.2, E5, 0.08, 55)]:
        add_bus(bed, piano(f, at, amp=0.036, dur=2.0, pan=p, seed=s))
    for k, at in enumerate(np.arange(41.5, 45.5, 0.5)):
        f = [G4, C5, E5, G5][k % 4]
        add_bus(bed, piano(f, at, amp=0.016, dur=0.9,
                           pan=0.26 * (-1 if k % 2 else 1), seed=170 + k))
    for k, at in enumerate(np.arange(41.0, 46.0, 1.0)):
        add_bus(perc, kick(at, 0.14, seed=180 + k))
    for k, at in enumerate([42.0, 44.0]):
        add_bus(perc, rim(at, 0.044, seed=190 + k))
    for k in range(20):
        add_bus(perc, shaker(41.25 + k * 0.25, 0.018, seed=200 + k))

    # ---- S8 (46-56) : trusted close — longer hold, elevated final chord
    add_bus(bed, pad([F2, C3, F3, A3, C4, F4], 45.6, 10.8, amp=0.13, attack=0.5, release=3.8, bright=3400, seed=61))
    add_bus(bed, pad([A3, C4, F4, A4, C5], 47.0, 8.6, amp=0.042, attack=0.8, release=3.4, bright=4600, seed=62))
    add_bus(bed, pad([C5, F5, A5], 52.0, 4.0, amp=0.018, attack=1.2, release=2.4, bright=6000, seed=63))
    add_bus(bed, sub(F2 / 2, 46.0, 9.8, amp=0.052, attack=0.4, release=2.0))
    for at, f, p, s in [(46.5, A4, -0.10, 62), (47.8, C5, 0.10, 63), (49.1, F4, -0.06, 64),
                        (50.4, A4, 0.10, 65), (51.7, C5, -0.08, 66), (53.0, F4, 0.06, 67),
                        (54.3, A4, -0.06, 68)]:
        add_bus(bed, piano(f, at, amp=0.038, dur=3.0, pan=p, seed=s))
    for k, at in enumerate(np.arange(46.5, 54.5, 0.75)):
        f = [F4, A4, C5, F5][k % 4]
        add_bus(bed, piano(f, at, amp=0.014, dur=1.6,
                           pan=0.24 * (-1 if k % 2 else 1), seed=210 + k))
    for k, at in enumerate([46.0, 48.0, 50.0, 52.0, 54.0]):
        add_bus(perc, kick(at, 0.13, seed=220 + k))
    for k, at in enumerate([47.0, 49.0, 51.0, 53.0]):
        add_bus(perc, rim(at, 0.042, seed=230 + k))
    for k in range(19):
        add_bus(perc, shaker(46.25 + k * 0.5, 0.012, seed=240 + k))
    add_bus(sfx, chime(52.5, 0.018, 1318.5))
    add_bus(sfx, tick(49.2, 0.012, 2600))

    return bed, perc, sfx


# ---------------------------------------------------------------- narration

def process_vo(seg):
    """Close, warm, de-essed narration with gentle glue compression."""
    x = hpf(seg, 80)
    x = lpf(x, 15000)
    warm = bpf(x, 110, 240) * 0.12
    mud = bpf(x, 300, 480) * 0.14
    pres = bpf(x, 2200, 4600) * 0.15
    air = bpf(x, 6800, 11500) * 0.05
    x = x + warm - mud + pres + air
    x = x - 0.10 * bpf(x, 6200, 9200)          # tame sibilance
    # program-dependent compression (slow, musical)
    env = uniform_filter1d(np.max(np.abs(x), axis=1), size=int(0.012 * SR), mode="nearest")
    th = 10 ** (-24 / 20)
    over = np.maximum(env / th, 1e-6)
    gain = np.ones_like(env)
    m = over > 1.0
    gain[m] = np.power(over[m], 1 / 2.6 - 1.0)
    g = uniform_filter1d(gain, size=int(0.09 * SR), mode="nearest")
    x = (x * g[:, None]).astype(np.float32)
    x = np.tanh(x * 1.25) / np.tanh(1.25)
    return norm(x, 0.84).astype(np.float32)


VO_MAP = [(i + 1, T[i] + 0.25) for i in range(8)]


def build_mix():
    n = int(TOTAL * SR)
    bed, perc, sfx = build_score_old()
    bed, perc, sfx = retime_score(bed), retime_score(perc), retime_score(sfx)

    # one soft clearing breath across every cut — no chopped whooshes
    for at in T[1:-1]:
        sfx += transition(at)

    music = bed + perc * 0.65 + sfx * 2.5
    music = hpf(music, 32)
    music *= 1.82                                        # present bed, not wallpaper
    music = music - 0.10 * bpf(music, 180, 430)          # clear low-mid buildup
    music = music + 0.055 * bpf(music, 7500, 14000)      # extra air on the lift
    music = music + convolve_reverb(music, make_ir(), wet=0.12)
    music = bus_compress(music, -21.0, 2.0, 3.5, 45)

    voice = np.zeros((n, 2), dtype=np.float32)
    for idx, start in VO_MAP:
        vp = ROOT / "exports" / "vo" / f"vo-s{idx}.wav"
        if not vp.exists():
            continue
        seg = process_vo(trim_vo(read_wav(vp)))
        voice += place(seg * 1.18, start)

    # narrated bed: ducks smoothly under every spoken phrase, with a little
    # extra low-end dip so kicks/sub never mask speech intelligibility
    duck = duck_gain(voice, depth_db=7.5)
    low = lpf(music, 170, 4)
    high = (music - low).astype(np.float32)
    bed_out = (low * duck_gain(voice, depth_db=13.0) + high * duck).astype(np.float32)

    # Noise -> Signal: only the bed clears and widens; the VO is untouched.
    texture = classroom_texture()
    tt = np.arange(n) / SR
    w = clarity_w(tt)
    bed_out = clarity_process(bed_out, w, texture)

    # music-only deliverable: same clarity arc, no ducking
    music_out = clarity_process(music, w, texture)

    # bed tail fade only — narration stays clean to the last word
    head, tail = int(0.15 * SR), int(1.2 * SR)
    for m in (bed_out, music_out):
        m[:head] *= np.linspace(0, 1, head)[:, None]
        m[-tail:] *= (np.linspace(1, 0, tail) ** 1.7)[:, None]

    mix = bed_out + voice
    vf = int(0.10 * SR)
    mix[-vf:] *= np.linspace(1, 0.985, vf)[:, None]

    # master: glue, transparent limiting, -14 LUFS / -2 dBFS sample peak
    mix = np.tanh(mix * 1.05) / np.tanh(1.05)
    mix = master(mix, target_lufs=-14.0, ceiling_db=-2.0)
    music_out = norm(music_out, 0.89)
    narration = norm(voice, 0.90)
    return mix.astype(np.float32), music_out.astype(np.float32), narration.astype(np.float32)
