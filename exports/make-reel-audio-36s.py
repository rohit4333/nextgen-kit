# Music bed + SFX for the 35.8s Meta Ads cut.
#
# Bed sits at ~-18 dBFS RMS. At 12.0s it drops to silence for 0.5s, then S4
# comes back +1.5 dB. The final reel is loudness-matched to -14 LUFS once the
# human VO is mixed in (pass --vo once the recording arrives).
#
# Run: py .\exports\make-reel-audio-36s.py --audio-only
#      py .\exports\make-reel-audio-36s.py            # build bed + mux all four
#      py .\exports\make-reel-audio-36s.py --mux-only  # mux existing files only

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
import reel_audio_engine as e  # noqa: E402

AUDIO = ROOT / "exports" / "audio"
MP4 = ROOT / "exports" / "mp4"
MARKETS = ["gcc", "sg", "au", "sa"]

# Exact 35.8s cut. The score is composed on the 56s grid and retimed to this.
T36 = [0.0, 3.0, 7.0, 12.0, 16.5, 20.5, 25.5, 29.0, 35.8]
e.T = T36
e.TOTAL = T36[-1]
SR = e.SR

BED_LEVEL_DBFS = -18.0
DROPOUT = (12.0, 12.5)
S4_GAIN_DB = 1.5

# Six VO phrases. Used only when --vo is supplied.
VO_PHRASES = [
    ("Your child isn't failing math. Just disappearing in it.", 0.0, 3.0),
    ("In a class of thirty, the quiet child doesn't ask. The doubt builds. Quietly.", 3.0, 7.0),
    ("Then one test makes it visible.", 7.0, 12.0),
    ("But it can be rebuilt.", 12.0, 16.5),
    ("One student. One tutor. Three times a week.", 20.5, 25.5),
    ("Try a free 35-minute demo on your child's real homework. WhatsApp to book.", 29.0, 35.8),
]


def bed_audio():
    """Score, transition breath, accents, dropout and S4 lift — as a stereo stem."""
    n = int(e.TOTAL * SR)
    bed, perc, sfx = e.build_score_old()
    bed, perc, sfx = e.retime_score(bed), e.retime_score(perc), e.retime_score(sfx)

    for at in T36[1:-1]:
        sfx += e.transition(at)

    music = bed + perc * 0.65 + sfx * 2.5
    music = e.hpf(music, 32)
    music *= 1.82
    music = music - 0.10 * e.bpf(music, 180, 430)
    music = music + 0.055 * e.bpf(music, 7500, 14000)
    music = music + e.convolve_reverb(music, e.make_ir(), wet=0.12)
    music = e.bus_compress(music, -21.0, 2.0, 3.5, 45)

    # Muffled -> open arc, with the turn landing on the 12.0s silence.
    tt = np.arange(n) / SR
    w = (0.10 * e.smoothstep(T36[1], T36[2], tt)
         + 0.20 * e.smoothstep(T36[2], T36[3], tt)
         + 0.10 * e.smoothstep(T36[3], 12.9, tt)
         + 0.60 * e.smoothstep(12.9, 13.7, tt)).astype(np.float32)
    muffled = e.lpf(music, 1600, 4)
    music = muffled * (1 - w[:, None]) + music * w[:, None]
    mid = music.mean(axis=1)
    side = (music[:, 0] - music[:, 1]) * 0.5
    sw = 0.35 + 0.65 * w
    music = np.stack([mid + sw * side, mid - sw * side], axis=1)

    # Accents tied to the exact 35.8s visuals.
    accents = np.zeros((n, 2), dtype=np.float32)
    accents += e.impact(0.0, 0.055)             # hook
    accents += e.riser(12.0, 1.3, 0.045)        # rise into the silence
    accents += e.whoosh(12.0, 0.62, 0.034, up=False)  # dissolve
    accents += e.click_sfx(13.5, 0.075, 1760.0) # "OH."
    accents += e.click_sfx(14.5, 0.070, 1850.0) # "x = 4"
    for at in (16.5, 17.4, 18.3):               # three chat bubbles
        accents += e.tick(at, 0.020)
    accents += e.chime(26.0, 0.030)             # green tick
    accents += e.click_sfx(29.0, 0.090, 2200.0) # CTA
    music += accents

    # 0.5s hard silence at 12.0, then S4 returns slightly louder.
    i0, i1 = int(DROPOUT[0] * SR), int(DROPOUT[1] * SR)
    music[i0:i1] = 0.0
    music[i1:int(T36[4] * SR)] *= 10 ** (S4_GAIN_DB / 20.0)

    head, tail = int(0.15 * SR), int(1.2 * SR)
    music[:head] *= np.linspace(0, 1, head)[:, None]
    music[-tail:] *= (np.linspace(1, 0, tail) ** 1.7)[:, None]

    music *= 10 ** ((BED_LEVEL_DBFS - e.db(music)) / 20.0)
    return music.astype(np.float32)


def build_mix(vo_path=None):
    music = bed_audio()
    if vo_path is None:
        return music

    # Place each pre-cut phrase on its scene start. The human recording is
    # expected as six clips; see --vo-slices for a single continuous take.
    voice = np.zeros_like(music)
    clips = [Path(x) for x in vo_path.split(",")]
    if len(clips) != len(VO_PHRASES):
        raise SystemExit(f"--vo needs {len(VO_PHRASES)} WAV clips, got {len(clips)}")
    for (text, start, end), clip in zip(VO_PHRASES, clips):
        seg = e.process_vo(e.trim_vo(e.read_wav(clip)))
        room = int((end - start) * SR)
        if len(seg) > room:
            raise SystemExit(f"VO too long for {start:.1f}-{end:.1f}s: {clip}")
        voice += e.place(seg, start, length_s=e.TOTAL)

    duck = e.duck_gain(voice, depth_db=7.5)
    low = e.lpf(music, 170, 4)
    high = music - low
    bed_out = low * e.duck_gain(voice, depth_db=13.0) + high * duck
    mix = bed_out + voice * 1.18
    mix = np.tanh(mix * 1.05) / np.tanh(1.05)
    return e.master(mix, target_lufs=-14.0, ceiling_db=-2.0)


def write_wav(path, seg):
    wavfile.write(str(path), SR, (np.clip(seg, -1, 1) * 32767).astype(np.int16))


def mix_path(vo=False):
    return AUDIO / ("REEL_36s-full-mix.wav" if vo else "REEL_36s-bed.wav")


def silent_path(m):
    return MP4 / f"REEL_{m.upper()}_36s-silent.mp4"


def final_path(m):
    return MP4 / f"REEL_{m.upper()}_36s.mp4"


def mux_all(vo=False):
    src = mix_path(vo)
    for m in MARKETS:
        if not silent_path(m).exists():
            raise SystemExit(f"missing {silent_path(m)}")
        subprocess.run(
            [get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(silent_path(m)), "-i", str(src),
             "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-ar", "48000", "-ac", "2", "-shortest", "-movflags", "+faststart",
             str(final_path(m))],
            check=True,
        )
        print(f"[ok] {final_path(m).name}  {final_path(m).stat().st_size / 1048576:.1f} MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio-only", action="store_true")
    ap.add_argument("--mux-only", action="store_true")
    ap.add_argument("--vo", help="six comma-separated human VO WAV clips")
    args = ap.parse_args()

    AUDIO.mkdir(parents=True, exist_ok=True)
    if not args.mux_only:
        mix = build_mix(args.vo)
        write_wav(mix_path(bool(args.vo)), mix)
        peak = 20 * np.log10(np.abs(mix).max())
        print(f"[ok] {mix_path(bool(args.vo)).name}  {len(mix) / SR:.2f}s  "
              f"{e.db(mix):.1f} dBFS RMS  {e.lufs(mix):.1f} LUFS  "
              f"peak {peak:.2f} dBFS")
    if not args.audio_only:
        mux_all(bool(args.vo))
    print("Done. reel-60s.mp4 and legacy reel-60s* files untouched.")


if __name__ == "__main__":
    main()
