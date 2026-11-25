from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(r"C:\Users\rohit\OneDrive\Documents\Default Project")
url = (ROOT / "nextgen-creative-kit.html").as_uri() + "#motion=capture"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    pg = b.new_page(viewport={"width":1080,"height":1920})
    pg.goto(url, wait_until="load")
    pg.wait_for_function("window.__reel && window.__reel.ready", timeout=20000)
    for t in [2.4, 28.0, 39.0]:
        pg.evaluate("(t)=>{window.__reel.seek(t); return new Promise(r=>requestAnimationFrame(()=>r()));}", t)
        print(t, pg.evaluate("""() => {
          const scenes=[...document.querySelectorAll('.motion-stage .m-scene')];
          const sc=scenes.find(s=>getComputedStyle(s).visibility!=='hidden');
          const f=sc.querySelector('.frame'), copy=f.querySelector('.m-copy'), vis=f.querySelector('.m-visual'), k=f.querySelector('.m-kicker');
          const line=f.querySelector('.line'), meta=f.querySelector('.m-meta');
          const cs=getComputedStyle(copy);
          const box=el=>({top:el.offsetTop,h:el.offsetHeight});
          return {frame:{h:f.offsetHeight,pad:getComputedStyle(f).padding},
                  kicker:box(k), visual:box(vis), copy:box(copy), line:box(line),
                  copyPadBottom:cs.paddingBottom, copyMarginTop:cs.marginTop,
                  lineBottom: line.offsetTop+line.offsetHeight+copy.offsetTop,
                  metaBottom: meta.offsetTop+meta.offsetHeight+copy.offsetTop,
                  copyBottom: copy.offsetTop+copy.offsetHeight,
                  lineText: line.textContent.slice(0,40)};
        }"""))
    b.close()
