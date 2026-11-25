# Render the full 8-scene regional motion cut to MP4, frame-accurately.
# Uses nextgen-creative-kit-regional.html; the master renderer and master MP4
# are never touched.
#
# Run: py .\exports\make-reel-video-regional.py --hook neutral
#      py .\exports\make-reel-video-regional.py --hook sg-gcc
#      py .\exports\make-reel-video-regional.py --hook au
#      py .\exports\make-reel-video-regional.py --hook neutral --test   (20 frames)

import argparse
import io
import subprocess
import time
from pathlib import Path

from PIL import Image
from imageio_ffmpeg import get_ffmpeg_exe
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "nextgen-creative-kit-regional.html"
OUT = ROOT / "exports" / "mp4"
LOG = ROOT / "exports" / "ffmpeg-reel-regional.log"

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
    ap.add_argument("--hook", choices=["neutral", "sg-gcc", "au"], default="neutral")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=41.2)
    ap.add_argument("--crf", type=int, default=19)
    ap.add_argument("--jpeg-quality", type=int, default=95)
    ap.add_argument("--out", default=None)
    ap.add_argument("--test", action="store_true", help="render 20 frames only")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    name = args.out or f"reel-full-{args.hook}-silent.mp4"
    dest = OUT / name
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

    url = KIT.as_uri() + "#motion=capture"
    if args.hook != "neutral":
        url += "&hook=" + args.hook
    print(f"browser : {find_browser()}")
    print(f"kit     : {KIT.name}")
    print(f"hook    : {args.hook}")
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
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(url, wait_until="load")
            page.wait_for_function("window.__reel && window.__reel.ready")
            page.evaluate("() => document.fonts.ready.then(() => true)")

            info = page.evaluate("() => ({dur: window.__reel.duration, scenes: window.__reel.scenes.length})")
            print(f"page    : duration {info['dur']}  scenes {info['scenes']}")
            if abs(info["dur"] - args.seconds) > 1e-6 or info["scenes"] != 8:
                raise SystemExit("HTML variant does not match the full 8-scene timeline")
            if errors:
                raise SystemExit("page errors: " + "; ".join(errors))

            clip = {"x": 0, "y": 0, "width": W, "height": H}
            for i in range(total):
                t = i / args.fps
                page.evaluate(
                    "(t) => { window.__reel.seek(t);"
                    " return new Promise(r => requestAnimationFrame(() => r())); }",
                    t,
                )
                shot = page.screenshot(clip=clip, type="jpeg", quality=args.jpeg_quality)
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

    print(f"\n[ok] {dest.name}  {dest.stat().st_size / 1048576:,.1f} MB  in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
