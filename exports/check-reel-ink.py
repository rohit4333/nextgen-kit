from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(r"C:\Users\rohit\OneDrive\Documents\Default Project")
url = (ROOT / "nextgen-creative-kit.html").as_uri() + "#motion=capture"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    pg = b.new_page(viewport={"width":1080,"height":1920})
    pg.goto(url, wait_until="load"); pg.wait_for_function("window.__reel && window.__reel.ready")
    for t in [2.4,7.5,12.6,17.0,21.5,28.0,34.0,39.0]:
        pg.evaluate("(t)=>{window.__reel.seek(t); return new Promise(r=>requestAnimationFrame(()=>r()));}", t)
        print(t, pg.evaluate("""() => {
          const sc=[...document.querySelectorAll('.m-scene')].find(s=>getComputedStyle(s).visibility!=='hidden');
          const f=sc.querySelector('.frame'), out=[];
          f.querySelectorAll('.m-copy .m-ln-i').forEach(el=>{
            const rg=document.createRange(); rg.selectNodeContents(el);
            for (const r of rg.getClientRects()) out.push([Math.round(r.right),Math.round(r.bottom)]);
          });
          return out;
        }"""))
    b.close()
