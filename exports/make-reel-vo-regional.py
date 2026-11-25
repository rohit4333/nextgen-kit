# Narration for the full 8-scene regional reels (41.2s cut).
# S1 hooks are reused: vo-s1.wav (neutral), short-hook-sg-gcc.wav,
# short-hook-au.wav. Only the corrected S6 tutor line is synthesized here.
# Master VO files are never overwritten.
#
# Run: py .\exports\make-reel-vo-regional.py
# Output: exports\vo\full-*.wav  (48 kHz mono)

import asyncio
import importlib.util
import tempfile
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("make_reel_voiceover", HERE / "make-reel-voiceover.py")
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)

OUT = v.OUT
SR = v.SR

# name -> (phrases, (vo_start, scene_end))
# phrase = (text, rate, pitch, gain(dB), pause after (s))
CLIPS = {
    "full-tutor": (
        [
            ("Engineer Rohit Vishwakarma, ex software developer from Samsung.", "+24%", "+0Hz", 0.5, 0.08),
            ("B Tech and M Tech from triple I T Elaahaabaad.", "+20%", "-1Hz", 0.0, 0.07),
            ("Maths expert at bhaan zoo.", "+16%", "-2Hz", -0.5, 0.0),
        ],
        (24.15, 32.1),
    ),
}


def build(phrases, tag):
    """Same pipeline as make-reel-voiceover.speak_line, plus phrase offsets."""
    parts, starts = [], []
    pos = 0.0
    for k, (text, rate, pitch, gain_db, gap) in enumerate(phrases):
        mp3 = Path(tempfile.gettempdir()) / f"full-{tag}-{k}.mp3"
        wav = Path(tempfile.gettempdir()) / f"full-{tag}-{k}.wav"
        asyncio.run(v.synth(text, rate, pitch, mp3))
        v.to_wav(mp3, wav)
        seg = v.trim(v.load(wav))
        seg *= 10 ** ((gain_db - (v.rms_db(seg) + 20.0)) / 20.0)
        starts.append(pos)
        parts.append(seg)
        pos += len(seg) / SR
        if gap > 0:
            parts.append(np.zeros(int(gap * SR), dtype=np.float32))
            pos += gap
    out = np.concatenate(parts)
    peak = np.max(np.abs(out))
    if peak > 0.94:
        out *= 0.94 / peak
    return out, starts


def main():
    for name, (phrases, (start, end)) in CLIPS.items():
        seg, starts = build(phrases, name)
        path = OUT / f"{name}.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(np.clip(seg * 32767, -32768, 32767).astype(np.int16).tobytes())
        dur = len(seg) / SR
        slot = end - start
        fit = "ok" if dur <= slot - 0.05 else "OVER by %.2fs" % (dur - (slot - 0.05))
        offsets = " ".join(f"{start + x:.2f}" for x in starts)
        print(f"[ok] {name}.wav  {dur:5.2f}s  slot {slot:4.2f}s  {fit}  starts: {offsets}")
    print(f"Done -> {OUT}")


if __name__ == "__main__":
    main()
