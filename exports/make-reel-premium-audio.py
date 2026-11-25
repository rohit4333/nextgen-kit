# Build the premium audio for the 41.2s reel and mux it onto the existing silent video.
# Legacy reel-60s filenames are kept so the export pipeline stays unchanged.
#
# All sound design lives in exports/reel_audio_engine.py; this file is only the
# CLI that renders the stems, writes the WAVs and muxes the MP4s. The video is
# never re-rendered or altered — only the audio track is attached.
#
# Run:  py .\exports\make-reel-premium-audio.py
# Output:
#   exports/audio/reel-60s-music.wav        (score + SFX, ducked under VO)
#   exports/audio/reel-60s-narration.wav    (narration only, full 41.2s timeline)
#   exports/audio/reel-60s-mix.wav          (combined mix)
#   exports/mp4/reel-60s-premium.mp4        (video + mix)
#   exports/mp4/reel-60s.mp4                (copy of the above — the master)
#   exports/mp4/reel-60s-music.mp4          (video + music bed, no narration)

import subprocess
import sys
from pathlib import Path

import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import reel_audio_engine as engine  # noqa: E402

AUDIO = ROOT / "exports" / "audio"
MP4 = ROOT / "exports" / "mp4"
SILENT = MP4 / "reel-60s-silent.mp4"
SR = engine.SR


def write_wav(path, data):
    pcm = np.clip(data, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    wavfile.write(str(path), SR, pcm)
    print(f"[ok] {path.name}  {path.stat().st_size / 1024 / 1024:.1f} MB")


def mux(video, audio, out, bitrate="192k"):
    subprocess.run(
        [get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(video), "-i", str(audio),
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", bitrate,
         "-ar", "48000", "-ac", "2",
         "-shortest", "-movflags", "+faststart", str(out)],
        check=True,
    )
    print(f"[ok] {out.name}  {out.stat().st_size / 1024 / 1024:.1f} MB")


def probe(path):
    p = subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True)
    for line in p.stderr.splitlines():
        s = line.strip()
        if s.startswith("Duration") or "Stream #" in s:
            print("     " + s)


def newest(paths):
    times = [p.stat().st_mtime for p in paths if p.exists()]
    return max(times) if times else 0.0


def main():
    force = "--force" in sys.argv
    AUDIO.mkdir(parents=True, exist_ok=True)
    if not SILENT.exists():
        raise SystemExit(f"missing silent master: {SILENT}")

    music_wav = AUDIO / "reel-60s-music.wav"
    narr_wav = AUDIO / "reel-60s-narration.wav"
    mix_wav = AUDIO / "reel-60s-mix.wav"
    premium = MP4 / "reel-60s-premium.mp4"
    master = MP4 / "reel-60s.mp4"
    music_mp4 = MP4 / "reel-60s-music.mp4"

    # Re-render only what actually changed: score/VO edits invalidate the stems,
    # new stems invalidate the MP4s. Nothing else is ever rebuilt.
    sources = [Path(__file__).with_name("reel_audio_engine.py")]
    sources += sorted((ROOT / "exports" / "vo").glob("vo-s*.wav"))
    fresh = mix_wav.exists() and mix_wav.stat().st_mtime >= newest(sources)

    if force or not fresh:
        print("building premium mix (score + SFX + VO)...")
        mix, music, narration = engine.build_mix()
        write_wav(music_wav, music)
        write_wav(narr_wav, narration)
        write_wav(mix_wav, mix)
    else:
        print("[skip] stems are up to date (use --force to rebuild)")

    if (force or not premium.exists()
            or premium.stat().st_mtime < max(mix_wav.stat().st_mtime, SILENT.stat().st_mtime)):
        print("muxing -> reel-60s-premium.mp4")
        mux(SILENT, mix_wav, premium)
        probe(premium)
        master.write_bytes(premium.read_bytes())
        print(f"[ok] updated {master}")
    else:
        print("[skip] reel-60s-premium.mp4 is up to date")

    if (force or not music_mp4.exists()
            or music_mp4.stat().st_mtime < max(music_wav.stat().st_mtime, SILENT.stat().st_mtime)):
        print("muxing -> reel-60s-music.mp4 (no narration)")
        mux(SILENT, music_wav, music_mp4)
    else:
        print("[skip] reel-60s-music.mp4 is up to date")

    # numeric report on whatever is on disk
    sr, data = wavfile.read(str(mix_wav))
    m = data.mean(axis=1) / 32768.0
    print(f"peak {20 * np.log10(np.abs(m).max()):.2f} dBFS   "
          f"clipped {int((np.abs(m) >= 0.999).sum())}   "
          f"lufs {engine.lufs(data.astype(np.float32) / 32768.0):.1f}   "
          f"dur {len(m) / sr:.2f}s")


if __name__ == "__main__":
    main()
