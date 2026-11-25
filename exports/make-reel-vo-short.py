# Narration for the 23.8s short reels — four new clips, three reused.
#
# Reused as-is: vo-s4.wav (turn), vo-s7.wav (confidence), vo-s8.wav (CTA).
# New: short-hook-neutral, short-tutor, short-hook-sg-gcc, short-hook-au.
#
# Phrase/rate/pitch handling is identical to make-reel-voiceover.py; this script
# loads that file by path (its hyphens make it non-importable) so the two
# pipelines cannot drift apart. Rates were tuned against measured phrase
# durations so every clip lands inside its approved scene.
#
# Run: py .\exports\make-reel-vo-short.py
#      py .\exports\make-reel-vo-short.py --only short-hook-au
# Output: exports\vo\short-*.wav  (48 kHz mono)

import importlib.util
import sys
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
# Hook VO starts 0.15s in; tutor VO 0.12s in — tighter than the 41s master.
CLIPS = {
    "short-hook-neutral": (
        [
            ("Your child is not slow.", "+24%", "-2Hz", 0.5, 0.10),
            ("They are just invisible in a crowded room.", "+22%", "-1Hz", -0.5, 0.0),
        ],
        (0.15, 3.8),
    ),
    "short-tutor": (
        [
            ("Engineer Rohit, ex software developer from Samsung.", "+32%", "+0Hz", 0.5, 0.04),
            ("B Tech and M Tech from triple I T Elaahaabaad.", "+30%", "-1Hz", 0.0, 0.04),
            ("Maths expert at bhaan zoo.", "+26%", "-2Hz", -0.5, 0.0),
        ],
        (7.82, 14.7),
    ),
    "short-hook-sg-gcc": (
        [
            ("Rigour that sticks.", "+36%", "-1Hz", 0.5, 0.06),
            ("Exam confidence, with a mentor who has been there.", "+34%", "-2Hz", 0.0, 0.0),
        ],
        (0.15, 3.8),
    ),
    "short-hook-au": (
        [
            ("Maths need not feel stressful.", "+34%", "+0Hz", 0.0, 0.08),
            ("One tutor, one child, calm.", "+34%", "+0Hz", -0.5, 0.0),
        ],
        (0.15, 3.8),
    ),
}


def main():
    only = None
    if "--only" in sys.argv:
        only = set(x.strip() for x in sys.argv[sys.argv.index("--only") + 1].split(","))

    for name, (phrases, (start, end)) in CLIPS.items():
        if only and name not in only:
            continue
        seg = v.speak_line(phrases, name)
        path = OUT / f"{name}.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(np.clip(seg * 32767, -32768, 32767).astype(np.int16).tobytes())
        dur = len(seg) / SR
        slot = end - start
        fit = "ok" if dur <= slot - 0.05 else "OVER by %.2fs" % (dur - (slot - 0.05))
        print(f"[ok] {name}.wav  {dur:5.2f}s  slot {slot:4.2f}s  {fit}")
    print(f"Done -> {OUT}")


if __name__ == "__main__":
    main()
