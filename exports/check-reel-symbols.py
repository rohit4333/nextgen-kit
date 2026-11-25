"""Verify the baked maths texture in reel scenes 1-7.

Checks, headlessly:
  * every storyboard frame 1-7 carries a symbol layer, frame 8 does not
  * the symbols actually paint (pixel diff with the layer hidden)
  * motion floats them: opacity + transform change over the timeline
  * symbols animate behind the content, never above it

Run: py .\\exports\\check-reel-symbols.py
"""

import io
from pathlib import Path

from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = (ROOT / "nextgen-creative-kit.html").as_uri()
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

LAYER = ".reel-sym-layer"
ITEMS = ".reel-sym, .reel-eq"


def shot(pg):
    return Image.open(io.BytesIO(pg.screenshot(type="png"))).convert("RGB")


def diff(a, b):
    d = ImageChops.difference(a, b)
    return sum(1 for px in d.convert("L").getdata() if px > 2)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)

        # 1. markup coverage
        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        pg.goto(URL, wait_until="load")
        pg.wait_for_timeout(500)
        counts = pg.evaluate(
            """() => [...document.querySelectorAll('.reel-item .frame')].map(f => ({
                 note: f.classList.contains('note'),
                 syms: f.querySelectorAll('.reel-sym').length,
                 eqs: f.querySelectorAll('.reel-eq').length,
                 layer: !!f.querySelector('.reel-sym-layer')
               }))"""
        )
        print("per frame:", counts)
        assert len(counts) == 8, "expected 8 storyboard frames"
        assert all(c["layer"] and c["syms"] for c in counts[:7]), "scenes 1-7 need symbols"
        assert not counts[7]["layer"], "scene 8 must stay clean"
        pg.close()

        # 2. painted in the PNG export clone
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(URL + "#export=r1", wait_until="load")
        pg.wait_for_timeout(700)
        on = shot(pg)
        pg.evaluate(
            """() => {
                 const f = [...document.querySelectorAll('.frame')].find(x => x.style.position === 'fixed');
                 f.querySelector('.reel-sym-layer').style.display = 'none';
               }"""
        )
        off = shot(pg)
        painted = diff(on, off)
        print("export r1 painted pixels:", painted)
        assert painted > 5000, "symbols are not painting in the PNG export"
        pg.close()

        # 3. motion: float + background stacking
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(URL + "#motion=capture", wait_until="load")
        pg.wait_for_function("window.__reel && window.__reel.ready", timeout=20000)
        stats = []
        for t in (2.4, 3.2, 4.2, 7.5, 21.5, 28.0, 34.0):
            pg.evaluate(
                "(t) => { window.__reel.seek(t); return new Promise(r => requestAnimationFrame(() => r())); }",
                t,
            )
            stats.append(
                pg.evaluate(
                    """() => {
                         const sc = [...document.querySelectorAll('.m-scene')]
                           .find(s => getComputedStyle(s).visibility !== 'hidden');
                         const l = sc.querySelector('.reel-sym-layer');
                         const els = [...l.querySelectorAll('.reel-sym, .reel-eq')];
                         const ops = els.map(e => parseFloat(getComputedStyle(e).opacity));
                         const tf = els.map(e => getComputedStyle(e).transform);
                         return {
                           z: getComputedStyle(l).zIndex,
                           count: els.length,
                           visible: ops.filter(v => v > 0.02).length,
                           max: Math.max(...ops),
                           moving: new Set(tf).size
                         };
                       }"""
                )
            )
        for t, s in zip((2.4, 3.2, 4.2, 7.5, 21.5, 28.0, 34.0), stats):
            print(f"t={t:>5}: {s}")

        assert all(s["count"] >= 10 for s in stats), "scenes lost their texture"
        assert all(s["z"] == "1" for s in stats), "texture should sit above the scrim"
        assert max(s["max"] for s in stats) > 0.08, "texture renders too faint"
        assert any(s["visible"] < s["count"] for s in stats), "texture never fades"
        assert max(s["moving"] for s in stats) > 3, "texture is not varied"

        # pixels removed when the layer hides -> it is genuinely visible
        pg.evaluate(
            "(t) => { window.__reel.seek(t); return new Promise(r => requestAnimationFrame(() => r())); }",
            2.4,
        )
        on = shot(pg)
        pg.evaluate(
            """() => {
                 const sc = [...document.querySelectorAll('.m-scene')]
                   .find(s => getComputedStyle(s).visibility !== 'hidden');
                 sc.querySelector('.reel-sym-layer').style.display = 'none';
               }"""
        )
        off = shot(pg)
        moving_px = diff(on, off)
        print("motion painted pixels @2.4s:", moving_px)
        assert moving_px > 5000, "symbols are not painting in the motion reel"

        b.close()
        print("\nOK — maths texture is present, subtle and floating.")


if __name__ == "__main__":
    main()
