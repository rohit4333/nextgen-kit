# Render the 41.2-second reel motion cut to MP4, frame-accurately.
# Legacy reel-60s filenames are kept so the audio mux pipeline stays unchanged.
# Run:  py .\exports\make-reel-video.py
#       py .\exports\make-reel-video.py --test      (20-frame smoke test)
#
# Needs: playwright (drives the installed Chrome), imageio-ffmpeg (bundled H.264 encoder), Pillow.
#   py -m pip install playwright imageio-ffmpeg Pillow

import argparse
import io
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
from imageio_ffmpeg import get_ffmpeg_exe
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "nextgen-creative-kit.html"
OUT = ROOT / "exports" / "mp4"
LOG = ROOT / "exports" / "ffmpeg-reel.log"

W, H = 1080, 1920
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_browser() -> str:
    for p in BROWSERS:
        if Path(p).exists():
            return p
    raise SystemExit("Chrome or Edge not found.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=41.2)
    ap.add_argument("--crf", type=int, default=19)
    ap.add_argument("--jpeg-quality", type=int, default=95)
    ap.add_argument("--out", default="reel-60s-silent.mp4")
    ap.add_argument("--test", action="store_true", help="render 20 frames only")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / args.out
    total = int(round(args.seconds * args.fps))
    if args.test:
        total = min(total, 20)

    cmd = [
        get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "warning",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(args.fps), "-i", "-",
        "-an",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2",
        "-movflags", "+faststart",
        str(dest),
    ]

    print(f"browser : {find_browser()}")
    print(f"output  : {dest}")
    print(f"frames  : {total}  ({total / args.fps:.2f}s @ {args.fps}fps)\n")

    log = open(LOG, "wb")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log, stderr=log)

    started = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=find_browser(),
                headless=True,
                args=[
                    "--allow-file-access-from-files",
                    "--hide-scrollbars",
                    "--force-color-profile=srgb",
                ],
            )
            page = browser.new_page(
                viewport={"width": W, "height": H},
                device_scale_factor=1,
            )
            page.goto(KIT.as_uri() + "#motion=capture", wait_until="load")
            page.wait_for_function("window.__reel && window.__reel.ready")
            page.evaluate("() => document.fonts.ready.then(() => true)")

            clip = {"x": 0, "y": 0, "width": W, "height": H}
            for i in range(total):
                t = i / args.fps
                page.evaluate(
                    "(t) => { window.__reel.seek(t);"
                    " return new Promise(r => requestAnimationFrame(() => r())); }",
                    t,
                )
                shot = page.screenshot(
                    clip=clip, type="jpeg", quality=args.jpeg_quality
                )
                img = Image.open(io.BytesIO(shot)).convert("RGB")
                proc.stdin.write(img.tobytes())

                if i % 30 == 0 or i == total - 1:
                    done = i + 1
                    elapsed = time.time() - started
                    rate = done / elapsed if elapsed else 0
                    eta = (total - done) / rate if rate else 0
                    print(f"  {done:4d}/{total}  {done / total * 100:5.1f}%  "
                          f"{rate:4.1f} fps  eta {eta:5.0f}s", flush=True)

            browser.close()
    finally:
        if proc.stdin:
            proc.stdin.close()
        rc = proc.wait()
        log.close()

    if rc != 0:
        raise SystemExit(f"ffmpeg failed with code {rc}. See {LOG}")

    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"\n[ok] {dest.name}  {size_mb:,.1f} MB  in {time.time() - started:.0f}s")

    # probe the finished file so duration/fps are verified, not assumed
    probe = subprocess.run(
        [get_ffmpeg_exe(), "-hide_banner", "-i", str(dest)],
        capture_output=True, text=True, errors="replace",
    )
    for line in probe.stderr.splitlines():
        s = line.strip()
        if s.startswith("Duration:") or s.startswith("Stream #0:0"):
            print("     " + s)


if __name__ == "__main__":
    main()
