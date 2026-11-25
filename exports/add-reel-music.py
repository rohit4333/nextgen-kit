# Legacy 60s score — superseded by reel_audio_engine.py for the current 56s cut.
# Run:  py .\exports\add-reel-music.py
#       py .\exports\add-reel-music.py --in exports/mp4/reel-60s.mp4 --out exports/mp4/reel-60s-music.mp4
#
# Uses numpy + scipy + ffmpeg (imageio-ffmpeg). No external music files.
# Timeline (matches T in nextgen-creative-kit.html):
#   S1  0-6   Hook          tense pulse, dark drone
#   S2  6-13  Child's fear  sparse, somber
#   S3 13-20  Parent guilt  weighty, low tension
#   S4 20-29  The turn      hopeful lift/swell (emotional pivot)
#   S5 29-39  Message       warm, gentle, conversational
#   S6 39-48  Tutor intro   confident, premium, warm
#   S7 48-54  Result        bright, resolving
#   S8 54-60  End card      confident resolve, soft fade

import argparse
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
T = [0, 6, 13, 20, 29, 39, 48, 54, 60]
TOTAL = 60.0


def env(length, a=0.08, d=0.12, s=0.7, r=0.25, sr=SR):
    n = max(1, int(length * sr))
    aa, dd, rr = int(a * sr), int(d * sr), int(r * sr)
    sustain_n = max(0, n - aa - dd - rr)
    e = np.concatenate([
        np.linspace(0, 1, max(1, aa), endpoint=False),
        np.linspace(1, s, max(1, dd), endpoint=False),
        np.full(max(1, sustain_n), s),
        np.linspace(s, 0, max(1, rr)),
    ])
    return e[:n]


def fade(seg, fin=0.05, fout=0.08, sr=SR):
    seg = seg.copy()
    fi = min(len(seg), int(fin * sr))
    fo = min(len(seg), int(fout * sr))
    if fi > 0:
        seg[:fi] *= np.linspace(0, 1, fi)
    if fo > 0:
        seg[-fo:] *= np.linspace(1, 0, fo)
    return seg


def tone(freq, dur, amp=0.2, shape="sine", vibrato=0.0, sr=SR):
    n = max(1, int(dur * sr))
    t = np.arange(n) / sr
    if vibrato:
        freq_t = freq * (1 + 0.003 * np.sin(2 * np.pi * vibrato * t))
        phase = 2 * np.pi * np.cumsum(freq_t) / sr
    else:
        phase = 2 * np.pi * freq * t
    if shape == "sine":
        x = np.sin(phase)
    elif shape == "soft":
        x = np.sin(phase) + 0.35 * np.sin(2 * phase) + 0.12 * np.sin(3 * phase)
    elif shape == "warm":
        x = np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.18 * np.sin(3 * phase) + 0.08 * np.sin(4 * phase)
    else:
        x = np.sin(phase)
    return amp * x


def pad(chord, start, dur, amp=0.12, attack=0.8, release=1.2):
    n = int(TOTAL * SR)
    out = np.zeros(n)
    s0 = int(start * SR)
    length = int(dur * SR)
    if s0 >= n:
        return out
    length = min(length, n - s0)
    t = np.arange(length) / SR
    sig = np.zeros(length)
    for i, f in enumerate(chord):
        det = 1 + (i - len(chord) / 2) * 0.0015
        sig += tone(f * det, dur, 1.0, "warm")[:length]
        sig += 0.15 * tone(f * 2 * det, dur, 1.0, "sine")[:length]
    sig /= max(1, len(chord))
    e = np.ones(length)
    a = min(length, int(attack * SR))
    r = min(length, int(release * SR))
    if a > 0:
        e[:a] = np.linspace(0, 1, a) ** 1.6
    if r > 0:
        e[-r:] *= np.linspace(1, 0, r) ** 1.8
    out[s0:s0 + length] += amp * sig * e
    return out


def pulse(freq, times, dur=0.12, amp=0.18):
    n = int(TOTAL * SR)
    out = np.zeros(n)
    for tm in times:
        i0 = int(tm * SR)
        l = min(int(dur * SR), n - i0)
        if i0 < 0 or i0 >= n or l <= 0:
            continue
        sig = tone(freq, dur, 1.0, "soft")[:l] + 0.45 * tone(freq / 2, dur, 1.0, "sine")[:l]
        e = np.exp(-np.linspace(0, 5.5, l))
        e[: min(80, l)] *= np.linspace(0, 1, min(80, l))
        out[i0:i0 + l] += amp * sig * e
    return out


def pluck(freq, tm, dur=1.8, amp=0.1):
    n = int(TOTAL * SR)
    out = np.zeros(n)
    i0 = int(tm * SR)
    l = min(int(dur * SR), n - i0)
    if i0 < 0 or i0 >= n or l <= 0:
        return out
    t = np.arange(l) / SR
    sig = (np.sin(2 * np.pi * freq * t)
           + 0.45 * np.sin(2 * np.pi * freq * 2.01 * t)
           + 0.18 * np.sin(2 * np.pi * freq * 3.99 * t))
    e = np.exp(-t * (2.2 + freq / 900.0))
    atk = min(120, l)
    e[:atk] *= np.linspace(0, 1, atk)
    out[i0:i0 + l] += amp * sig * e
    return out


def noise_bed(start, dur, amp=0.03, hp=300, lp=5000):
    n = int(TOTAL * SR)
    out = np.zeros(n)
    s0 = int(start * SR)
    l = min(int(dur * SR), n - s0)
    if s0 >= n or l <= 0:
        return out
    rng = np.random.default_rng(42 + int(start * 10))
    x = rng.standard_normal(l)
    if lp < SR / 2:
        sos = butter(4, lp, btype="low", fs=SR, output="sos")
        x = sosfilt(sos, x)
    if hp > 20:
        sos = butter(2, hp, btype="high", fs=SR, output="sos")
        x = sosfilt(sos, x)
    x /= (np.max(np.abs(x)) + 1e-6)
    e = np.ones(l)
    a = min(l, int(0.8 * SR))
    r = min(l, int(1.0 * SR))
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    out[s0:s0 + l] += amp * x * e
    return out


def whoosh(at, dur=0.7, amp=0.06, up=True):
    n = int(TOTAL * SR)
    out = np.zeros(n)
    i0 = int(max(0, at - dur / 2) * SR)
    l = min(int(dur * SR), n - i0)
    if l <= 0:
        return out
    rng = np.random.default_rng(7 + int(at * 100))
    x = rng.standard_normal(l)
    t = np.linspace(0, 1, l)
    # sweeping bandpass via time-varying filtered chunks
    chunks = 24
    cs = l // chunks
    y = np.zeros(l)
    for i in range(chunks):
        a = i * cs
        b = l if i == chunks - 1 else (i + 1) * cs
        p = i / max(1, chunks - 1)
        center = (300 + 3400 * p) if up else (3700 - 3400 * p)
        bw = center * 0.8
        lo = max(40, center - bw / 2)
        hi = min(SR / 2 - 200, center + bw / 2)
        if hi <= lo + 50:
            y[a:b] = x[a:b]
            continue
        sos = butter(2, [lo, hi], btype="band", fs=SR, output="sos")
        y[a:b] = sosfilt(sos, x[a:b])
    e = np.sin(np.pi * t) ** 1.7
    y /= (np.max(np.abs(y)) + 1e-6)
    out[i0:i0 + l] += amp * y * e
    return out


def sub_hit(at, freq=45, dur=1.0, amp=0.12):
    n = int(TOTAL * SR)
    out = np.zeros(n)
    i0 = int(at * SR)
    l = min(int(dur * SR), n - i0)
    if i0 >= n or l <= 0:
        return out
    t = np.arange(l) / SR
    sig = np.sin(2 * np.pi * freq * t * (1 - 0.08 * t / max(1e-3, dur)))
    e = np.exp(-t * 3.2)
    out[i0:i0 + l] += amp * sig * e
    return out


def swell(start, dur, chord, amp=0.16):
    n = int(TOTAL * SR)
    out = np.zeros(n)
    s0 = int(start * SR)
    l = min(int(dur * SR), n - s0)
    if l <= 0:
        return out
    t = np.arange(l) / SR
    sig = np.zeros(l)
    for f in chord:
        sig += np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2 * t)
    sig /= max(1, len(chord))
    e = (np.sin(np.pi * t / (l / SR)) ** 1.4)
    out[s0:s0 + l] += amp * sig * e
    return out


def normalize(x, peak=0.92):
    m = np.max(np.abs(x))
    return x * (peak / m) if m > 1e-8 else x


def build_score():
    n = int(TOTAL * SR)
    L = np.zeros(n)
    R = np.zeros(n)

    def add_mono(sig, pan=0.0, g=1.0):
        nonlocal L, R
        sig = sig * g
        L += sig * (1 - max(0, pan)) * 0.85
        R += sig * (1 + min(0, pan)) * 0.85

    # --- S1 Hook (0-6): tense, dark, pulse ---
    add_mono(pad([55, 110, 165], 0.0, 6.5, amp=0.10, attack=0.05, release=0.8), pan=-0.1)
    add_mono(pulse(55, [0.0, 0.75, 1.5, 2.25, 3.0, 3.6, 4.2, 4.8, 5.4], dur=0.18, amp=0.16), pan=0.0)
    add_mono(noise_bed(0.0, 6.2, amp=0.025, hp=1200, lp=7000), pan=0.2)
    add_mono(swell(4.5, 1.8, [220, 277, 330], amp=0.04))

    # --- S2 Child's fear (6-13): somber, sparse ---
    add_mono(pad([65.4, 130.8, 196], 5.6, 8.2, amp=0.09, attack=1.2, release=1.4), pan=0.05)
    for i, tm in enumerate([6.6, 8.2, 10.0, 11.5]):
        add_mono(pluck([261.6, 220, 246.9, 196][i % 4], tm, dur=2.2, amp=0.045), pan=-0.15 + 0.1 * i)
    add_mono(noise_bed(6.0, 7.4, amp=0.018, hp=600, lp=3500), pan=-0.1)

    # --- S3 Parent guilt (13-20): weighty tension ---
    add_mono(pad([58.3, 116.5, 174.6], 12.6, 8.0, amp=0.10, attack=0.9, release=1.1), pan=-0.05)
    add_mono(pulse(58.3, [13.2, 14.4, 15.6, 16.8, 18.0, 19.0], dur=0.16, amp=0.10), pan=0.1)
    add_mono(pluck(233.1, 14.0, amp=0.035), pan=0.2)
    add_mono(pluck(220.0, 16.5, amp=0.03), pan=-0.2)
    add_mono(noise_bed(13.0, 7.2, amp=0.02, hp=200, lp=2500), pan=0.0)

    # --- S4 The turn (20-29): hopeful lift, emotional pivot ---
    add_mono(whoosh(20.0, dur=0.8, amp=0.05, up=True))
    add_mono(pad([73.4, 146.8, 220, 293.7], 19.6, 10.2, amp=0.13, attack=1.4, release=1.8), pan=0.0)
    add_mono(swell(20.2, 4.5, [293.7, 370, 440], amp=0.07))
    for i, tm in enumerate([21.0, 22.8, 24.6, 26.4, 27.8]):
        add_mono(pluck([293.7, 329.6, 370.0, 440.0, 493.9][i], tm, dur=2.4, amp=0.055), pan=-0.2 + 0.1 * i)
    add_mono(noise_bed(20.0, 9.5, amp=0.015, hp=1500, lp=8000), pan=0.15)

    # --- S5 Message (29-39): warm, gentle ---
    add_mono(pad([87.3, 130.8, 174.6, 220], 28.6, 11.0, amp=0.11, attack=1.0, release=1.5), pan=-0.05)
    for i, tm in enumerate([29.8, 31.6, 33.5, 35.4, 37.2]):
        add_mono(pluck([349.2, 392.0, 440.0, 392.0, 349.2][i], tm, dur=2.0, amp=0.04), pan=0.1 * ((-1) ** i))
    add_mono(noise_bed(29.0, 10.5, amp=0.012, hp=800, lp=5000), pan=0.0)

    # --- S6 Tutor intro (39-48): confident, premium, warm ---
    add_mono(whoosh(39.0, dur=0.6, amp=0.045, up=True))
    add_mono(pad([65.4, 98.0, 130.8, 196.0], 38.6, 10.2, amp=0.13, attack=0.7, release=1.6), pan=0.0)
    add_mono(pad([261.6, 329.6, 392.0], 39.4, 9.0, amp=0.05, attack=1.2, release=1.8), pan=0.12)
    for i, tm in enumerate([40.0, 41.8, 43.6, 45.4, 46.8]):
        add_mono(pluck([261.6, 329.6, 392.0, 329.6, 392.0][i], tm, dur=2.2, amp=0.05), pan=-0.15 + 0.08 * i)
    add_mono(sub_hit(39.0, freq=43, dur=1.2, amp=0.08))
    add_mono(noise_bed(39.0, 9.5, amp=0.014, hp=1200, lp=7000), pan=-0.1)

    # --- S7 Result (48-54): bright, resolving ---
    add_mono(whoosh(48.0, dur=0.55, amp=0.04, up=True))
    add_mono(pad([73.4, 110.0, 146.8, 220.0], 47.6, 7.2, amp=0.12, attack=0.6, release=1.4), pan=0.0)
    add_mono(swell(48.2, 3.0, [293.7, 370.0, 440.0], amp=0.06))
    for i, tm in enumerate([48.6, 50.0, 51.4, 52.6]):
        add_mono(pluck([293.7, 370.0, 440.0, 523.3][i], tm, dur=2.0, amp=0.055), pan=-0.1 + 0.07 * i)

    # --- S8 End card (54-60): confident resolve, soft fade ---
    add_mono(pad([65.4, 98.0, 130.8, 196.0, 261.6], 53.6, 7.0, amp=0.13, attack=0.5, release=3.5), pan=0.0)
    add_mono(sub_hit(54.0, freq=41, dur=1.4, amp=0.09))
    for i, tm in enumerate([54.6, 56.2, 57.8]):
        add_mono(pluck([261.6, 329.6, 392.0][i], tm, dur=2.8, amp=0.045), pan=0.0)
    add_mono(noise_bed(54.0, 6.2, amp=0.01, hp=1500, lp=6000), pan=0.1)

    # gentle global transitions at cuts
    for cut in T[1:-1]:
        add_mono(whoosh(cut, dur=0.45, amp=0.022, up=True))

    # master fade out
    out = np.stack([L, R], axis=1)
    tail = int(2.5 * SR)
    if tail > 0:
        out[-tail:] *= np.linspace(1, 0, tail)[:, None] ** 1.5
    head = int(0.15 * SR)
    out[:head] *= np.linspace(0, 1, head)[:, None]

    # subtle stereo widening via tiny decorrelation
    delay = int(0.012 * SR)
    out[delay:, 1] = out[delay:, 1] * 0.92 + out[:-delay, 1] * 0.08

    out = normalize(out, peak=0.88)
    return out


def mux(video_in: Path, audio_wav: Path, video_out: Path):
    cmd = [
        get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "warning",
        "-i", str(video_in), "-i", str(audio_wav),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        "-shortest",
        str(video_out),
    ]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(ROOT / "exports/mp4/reel-60s.mp4"))
    ap.add_argument("--out", dest="out", default=str(ROOT / "exports/mp4/reel-60s-music.mp4"))
    ap.add_argument("--wav", dest="wav", default="", help="also keep the generated WAV here")
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)
    if not inp.exists():
        raise SystemExit(f"input video not found: {inp}")
    out.parent.mkdir(parents=True, exist_ok=True)

    print("composing cinematic score (60s, 48kHz stereo)...")
    audio = build_score()

    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(args.wav) if args.wav else Path(td) / "score.wav"
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        pcm = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        wavfile.write(str(wav_path), SR, pcm)
        print(f"muxing audio -> {out.name} ...")
        mux(inp, wav_path, out)

    mb = out.stat().st_size / (1024 * 1024)
    print(f"[ok] {out.name}  {mb:,.1f} MB")
    probe = subprocess.run(
        [get_ffmpeg_exe(), "-hide_banner", "-i", str(out)],
        capture_output=True, text=True, errors="replace",
    )
    for line in probe.stderr.splitlines():
        s = line.strip()
        if s.startswith("Duration:") or s.startswith("Stream #"):
            print("     " + s)


if __name__ == "__main__":
    main()
