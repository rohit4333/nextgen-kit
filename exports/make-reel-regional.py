# Build the three full 8-scene regional reels.
#
#   neutral  -> exports/mp4/reel-23s.mp4
#   sg-gcc   -> exports/mp4/reel-23s-sg-gcc.mp4
#   au       -> exports/mp4/reel-23s-au.mp4
#
# Same filenames as the earlier 5-scene cuts so existing links keep working;
# the runtime is now the full 41.2s master cut. reel-60s.mp4 is never touched.
#
# Run: py .\exports\make-reel-regional.py
#      py .\exports\make-reel-regional.py --audio-only
#      py .\exports\make-reel-regional.py --video-only

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import reel_audio_engine as e          # noqa: E402
import reel_audio_engine_regional as r  # noqa: E402

AUDIO = ROOT / "exports" / "audio"
MP4 = ROOT / "exports" / "mp4"
VARIANTS = ["neutral", "sg-gcc", "au"]


def mix_path(v):
    return AUDIO / f"reel-full-{v}-mix.wav"


def silent_path(v):
    return MP4 / f"reel-full-{v}-silent.mp4"


def final_path(v):
    return MP4 / ("reel-23s.mp4" if v == "neutral" else f"reel-23s-{v}.mp4")


def build_audio():
    AUDIO.mkdir(parents=True, exist_ok=True)
    for v in VARIANTS:
        mix = r.build_mix(v)[0]
        wavfile.write(str(mix_path(v)), r.SR, (np.clip(mix, -1, 1) * 32767).astype(np.int16))
        peak = 20 * np.log10(np.abs(mix).max())
        print(f"[ok] {mix_path(v).name}  {len(mix) / r.SR:.2f}s  "
              f"{e.lufs(mix):.1f} LUFS  {peak:.2f} dBFS  "
              f"clipped {int((np.abs(mix) >= 0.999).sum())}")


def build_video(v):
    subprocess.run(
        [sys.executable, str(HERE / "make-reel-video-regional.py"), "--hook", v],
        check=True,
        cwd=str(ROOT),
    )


def mux(v):
    subprocess.run(
        [get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(silent_path(v)), "-i", str(mix_path(v)),
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-ar", "48000", "-ac", "2", "-shortest", "-movflags", "+faststart",
         str(final_path(v))],
        check=True,
    )
    print(f"[ok] {final_path(v).name}  {final_path(v).stat().st_size / 1048576:.1f} MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio-only", action="store_true")
    ap.add_argument("--video-only", action="store_true")
    args = ap.parse_args()
    if not args.audio_only:
        for v in VARIANTS:
            print(f"\n-- video {v} --")
            build_video(v)
    if not args.video_only:
        print("\nbuilding regional audio mixes...")
        build_audio()
    if not args.video_only:
        print("\nmuxing...")
        for v in VARIANTS:
            mux(v)
    print("\nDone. Master reel-60s.mp4 untouched.")


if __name__ == "__main__":
    main()
