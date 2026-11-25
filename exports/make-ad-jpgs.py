# Convert exported carousel PNGs into upload-ready Meta Ads JPGs.
# Quality 92 + 4:4:4 subsampling keeps the thin mono text crisp while staying
# far smaller than the PNG master. Meta re-compresses on upload anyway.
#
# Run: py .\exports\make-ad-jpgs.py --src exports/png-45 --out exports/jpg-45
#      py .\exports\make-ad-jpgs.py --src exports/png-riyadh-45 --out exports/jpg-riyadh-45

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality", type=int, default=92)
    args = ap.parse_args()

    src = ROOT / args.src
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    total = 0
    for png in sorted(src.glob("*.png")):
        im = Image.open(png).convert("RGB")
        dest = out / (png.stem + ".jpg")
        im.save(dest, "JPEG", quality=args.quality, subsampling=0,
                optimize=True, progressive=True)
        total += dest.stat().st_size
        print(f"[ok] {dest.name:<38} {im.width}x{im.height}  "
              f"{dest.stat().st_size / 1024:6,.0f} KB")
    print(f"\n{len(list(src.glob('*.png')))} JPGs  {total / 1024:,.0f} KB total  -> {out}")


if __name__ == "__main__":
    main()
