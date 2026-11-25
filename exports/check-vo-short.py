"""Check every short-reel narration clip fits inside its scene.

Short timeline T = [0, 3.8, 7.7, 14.7, 18.4, 23.8]. The hook VO is swapped per
region; the other four clips are shared by all three reels.

Run: py .\\exports\\check-vo-short.py
"""

import wave
from pathlib import Path

import numpy as np

VO = Path(__file__).resolve().parent.parent / "exports" / "vo"
T = [0, 3.8, 7.7, 14.7, 18.4, 23.8]
START = [0.15, 4.05, 7.82, 14.95, 18.65]
THRESH = 0.008

REELS = {
    "neutral": ["short-hook-neutral.wav"],
    "sg-gcc": ["short-hook-sg-gcc.wav"],
    "au": ["short-hook-au.wav"],
}
SHARED = ["vo-s4.wav", "short-tutor.wav", "vo-s7.wav", "vo-s8.wav"]


def speech_span(path):
    w = wave.open(str(path), "rb")
    sr, ch = w.getframerate(), w.getnchannels()
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    w.close()
    if ch > 1:
        a = a.reshape(-1, ch).mean(1)
    idx = np.where(np.abs(a) > THRESH)[0]
    if not len(idx):
        return 0.0, 0.0
    return idx[0] / sr, idx[-1] / sr


def main():
    ok = True
    for variant, hooks in REELS.items():
        clips = hooks + SHARED
        print(f"\n{variant}")
        print(f"  {'clip':22} {'speech':>7} {'placed':>14} {'scene':>7} {'fit':>10}")
        for i, fname in enumerate(clips):
            t0, t1 = speech_span(VO / fname)
            speech = t1 - t0
            start = START[i]
            ends = start + speech
            limit = T[i + 1]
            fit = "ok" if ends <= limit - 0.05 else "OVER by %.2fs" % (ends - limit + 0.05)
            ok = ok and ends <= limit - 0.05
            print(f"  {fname:22} {speech:6.2f}s {start:6.2f}-{ends:6.2f} {limit:7.1f} {fit:>10}")
    assert ok, "a narration clip runs past its scene"
    print("\nOK — every short-reel clip sits inside its scene.")


if __name__ == "__main__":
    main()
