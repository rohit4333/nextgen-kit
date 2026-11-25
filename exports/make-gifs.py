# Build animated GIFs from the exported PNGs.
# Run:  py .\exports\make-gifs.py
# Output: exports\gif\deck-walkthrough.gif (square)
#         exports\gif\reel-story.gif        (9:16)
#
# Requires Pillow:  py -m pip install Pillow

from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "exports" / "png"
OUT = ROOT / "exports" / "gif"
OUT.mkdir(parents=True, exist_ok=True)

SLIDES = [f"deck-0{i}-" for i in range(1, 7)]
DECK = [
    "deck-01-the-fear",
    "deck-02-why-it-happens",
    "deck-03-the-fix",
    "deck-04-the-tutor",
    "deck-05-the-first-session",
    "deck-06-next-step",
]
REEL = [f"reel-0{i}" for i in range(1, 9)]


def build(name, files, width, durations):
    frames = []
    for f in files:
        im = Image.open(SRC / f"{f}.png").convert("RGB")
        height = round(im.height * width / im.width)
        im = im.resize((width, height), Image.LANCZOS)
        frames.append(
            im.quantize(
                colors=256,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
        )

    out = OUT / name
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )

    check = Image.open(out)
    total = sum(durations) / 1000
    print(
        f"[ok] {name:<24} {check.size[0]}x{check.size[1]}  "
        f"{check.n_frames} frames  {total:.1f}s  {out.stat().st_size / 1024:,.0f} KB"
    )


build(
    "deck-walkthrough.gif",
    DECK,
    720,
    [2200] * 5 + [3400],
)

build(
    "reel-story.gif",
    REEL,
    540,
    [2100] + [1700] * 6 + [2900],
)

print(f"\nDone -> {OUT}")
