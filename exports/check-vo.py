"""Check every narration clip fits inside its reel scene.

The reel timeline is T = [0, 4.8, 10.2, 15.1, 19, 23.9, 32.1, 35.8, 41.2] and
each VO is placed 0.25s into its scene by reel_audio_engine.py. A clip that runs past its
scene (or into the next VO) gets clipped or talked over, so verify it here.

Run: py .\\exports\\check-vo.py
"""

import wave
from pathlib import Path

import numpy as np

VO = Path(__file__).resolve().parent.parent / "exports" / "vo"

T = [0, 4.8, 10.2, 15.1, 19, 23.9, 32.1, 35.8, 41.2]
VO_START = [0.25, 5.05, 10.45, 15.35, 19.25, 24.15, 32.35, 36.05]
THRESH = 0.008


def speech_span(path):
    w = wave.open(str(path))
    sr, ch = w.getframerate(), w.getnchannels()
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    w.close()
    if ch > 1:
        a = a.reshape(-1, ch).mean(1)
    idx = np.where(np.abs(a) > THRESH)[0]
    if not len(idx):
        return sr, 0.0, 0.0
    return sr, idx[0] / sr, idx[-1] / sr


def main():
    rows = []
    for n in range(1, 9):
        p = VO / f"vo-s{n}.wav"
        sr, t0, t1 = speech_span(p)
        start = VO_START[n - 1]
        speech = t1 - t0
        ends = start + speech
        scene_end = T[n]
        next_vo = VO_START[n] if n < 8 else T[-1]
        rows.append((n, speech, start, ends, scene_end, next_vo))

    print(f"{'clip':5} {'speech':>7} {'placed':>13} {'scene ends':>11} {'next VO':>8}  fit")
    ok = True
    for n, speech, start, ends, scene_end, next_vo in rows:
        limit = min(scene_end, next_vo)
        fit = "ok" if ends <= limit else "OVER by %.2fs" % (ends - limit)
        ok = ok and ends <= limit
        print(f"s{n:<4} {speech:6.2f}s {start:6.2f}–{ends:6.2f} {scene_end:10.1f} {next_vo:8.2f}  {fit}")

    assert ok, "a narration clip runs past its scene"
    print("\nOK — every clip sits inside its scene.")


if __name__ == "__main__":
    main()
