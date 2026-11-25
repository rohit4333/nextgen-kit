import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(r"C:\Users\rohit\OneDrive\Documents\Default Project")
url = (ROOT / "nextgen-creative-kit.html").as_uri() + "#motion=capture"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    pg = b.new_page(viewport={"width":1080,"height":1920})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:"+m.text) if m.type=="error" else None)
    pg.goto(url, wait_until="load")
    pg.wait_for_function("window.__reel && window.__reel.ready", timeout=20000)
    pg.evaluate("() => document.fonts.ready.then(() => true)")
    out = {}
    for t in [2.4, 7.5, 12.6, 17.0, 21.5, 28.0, 34.0, 39.0]:
        pg.evaluate("(t)=>{window.__reel.seek(t); return new Promise(r=>requestAnimationFrame(()=>r()));}", t)
        out[t] = pg.evaluate("""() => {
          const stage = document.querySelector('.motion-stage');
          const vis = [...stage.querySelectorAll('.m-scene')].filter(s => getComputedStyle(s).visibility !== 'hidden');
          const scene = vis[0];
          const r = el => { if (!el) return null; const b = el.getBoundingClientRect(); return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]; };
          return {
            scenes: vis.length,
            syms: stage.querySelectorAll('.m-scene .m-sym').length,
            panel: !!stage.querySelector('.m-scene .m-panel'),
            meta: r(stage.querySelector('.m-scene .m-meta')),
            copy: r(stage.querySelector('.m-scene .m-copy')),
            line: r(stage.querySelector('.m-scene .line')),
            board: r(stage.querySelector('.m-scene .tc-board')),
            photo: r(stage.querySelector('.m-scene .tc-photo')),
            visual: r(stage.querySelector('.m-scene .m-visual')),
            svg: r(scene ? scene.querySelector('.scene svg') : null)
          };
        }""")
    print("errors:", errs)
    print(json.dumps(out, indent=1))
    b.close()
