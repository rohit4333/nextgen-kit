"""Check every full 8-scene regional narration clip fits inside its scene.

Master timeline T = [0, 4.8, 10.2, 15.1, 19, 23.9, 32.1, 35.8, 41.2].
Only S1 (hook) and S6 (corrected tutor line) vary from the master VO.

Run: py .\\exports\\check-vo-regional.py
"""

import wave
from pathlib import Path

import numpy as np

VO = Path(__file__).resolve().parent.parent / "exports" / "vo"
T = [0, 4.8, 10.2, 15.1, 19, 23.9, 32.1, 35.8, 41.2]
START = [t + 0.25 for t in T[:-1]]
THRESH = 0.008

HOOK = {
    "neutral": "vo-s1.wav",
    "sg-gcc": "short-hook-sg-gcc.wav",
    "au": "short-hook-au.wav",
}
SHARED = ["vo-s2.wav", "vo-s3.wav", "vo-s4.wav", "vo-s5.wav",
          "full-tutor.wav", "vo-s7.wav", "vo-s8.wav"]


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
    for variant, hook in HOOK.items():
        clips = [hook] + SHARED
        print(f"\n{variant}")
        print(f"  {'clip':24} {'speech':>7} {'placed':>14} {'scene':>7} {'fit':>10}")
        for i, fname in enumerate(clips):
            t0, t1 = speech_span(VO / fname)
            speech = t1 - t0
            start = START[i]
            ends = start + speech
            limit = T[i + 1]
            fit = "ok" if ends <= limit - 0.05 else "OVER by %.2fs" % (ends - limit + 0.05)
            ok = ok and ends <= limit - 0.05
            print(f"  {fname:24} {speech:6.2f}s {start:6.2f}-{ends:6.2f} {limit:7.1f} {fit:>10}")
    assert ok, "a narration clip runs past its scene"
    print("\nOK — every full-reel clip sits inside its scene.")


if __name__ == "__main__":
    main()
