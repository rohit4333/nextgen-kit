# Render the 35.8s Meta Ads cut for one market, frame-accurately.
# Market select is burn-in copy only; the video story is identical.
#
# Run: py .\exports\make-reel-video-36s.py --market gcc
#      py .\exports\make-reel-video-36s.py --market sa

import argparse
import io
import subprocess
import time
from pathlib import Path

from PIL import Image
from imageio_ffmpeg import get_ffmpeg_exe
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "nextgen-creative-kit-36s.html"
OUT = ROOT / "exports" / "mp4"
LOG = ROOT / "exports" / "ffmpeg-reel-36s.log"
W, H = 1080, 1920
MARKETS = ["gcc", "sg", "au", "sa"]
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
    ap.add_argument("--market", choices=MARKETS, default="gcc")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=35.8)
    ap.add_argument("--crf", type=int, default=19)
    ap.add_argument("--jpeg-quality", type=int, default=95)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"REEL_{args.market.upper()}_36s-silent.mp4"
    total = int(round(args.seconds * args.fps))
    cmd = [
        get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "warning",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(args.fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2",
        "-movflags", "+faststart", str(dest),
    ]
    url = KIT.as_uri() + "#motion=capture&market=" + args.market
    print(f"market  : {args.market}\noutput  : {dest}\nframes  : {total}\n")
    log = open(LOG, "wb")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log, stderr=log)
    started = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=find_browser(), headless=True,
                args=["--allow-file-access-from-files", "--hide-scrollbars", "--force-color-profile=srgb"],
            )
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(url, wait_until="load")
            page.wait_for_function("window.__reel && window.__reel.ready")
            page.evaluate("() => document.fonts.ready.then(() => true)")
            info = page.evaluate("() => ({d: window.__reel.duration, s: window.__reel.scenes.length})")
            if abs(info["d"] - args.seconds) > 1e-6 or info["s"] != 8:
                raise SystemExit("HTML does not match the 35.8s timeline")
            if errors:
                raise SystemExit("page errors: " + "; ".join(errors))
            clip = {"x": 0, "y": 0, "width": W, "height": H}
            for i in range(total):
                t = i / args.fps
                page.evaluate(
                    "(t) => { window.__reel.seek(t); return new Promise(r => requestAnimationFrame(() => r())); }",
                    t,
                )
                img = Image.open(io.BytesIO(page.screenshot(clip=clip, type="jpeg", quality=args.jpeg_quality))).convert("RGB")
                proc.stdin.write(img.tobytes())
                if i % 30 == 0 or i == total - 1:
                    done = i + 1
                    elapsed = time.time() - started
                    rate = done / elapsed if elapsed else 0
                    print(f"  {done:4d}/{total}  {done / total * 100:5.1f}%  {rate:4.1f} fps", flush=True)
            browser.close()
    finally:
        if proc.stdin:
            proc.stdin.close()
        rc = proc.wait()
        log.close()
    if rc != 0:
        raise SystemExit(f"ffmpeg failed with code {rc}. See {LOG}")
    print(f"[ok] {dest.name}  {dest.stat().st_size / 1048576:.1f} MB  in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
