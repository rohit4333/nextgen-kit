from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image, ImageStat
import io
ROOT = Path(r"C:\Users\rohit\OneDrive\Documents\Default Project")
url = (ROOT / "nextgen-creative-kit.html").as_uri() + "#motion=capture"
OUT = ROOT/"exports"/"frames-check"; OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
    pg = b.new_page(viewport={"width":1080,"height":1920})
    pg.goto(url, wait_until="load")
    pg.wait_for_function("window.__reel && window.__reel.ready", timeout=20000)
    pg.evaluate("() => document.fonts.ready.then(() => true)")
    # S6 internals
    pg.evaluate("(t)=>{window.__reel.seek(t); return new Promise(r=>requestAnimationFrame(()=>r()));}", 28.0)
    print("S6:", pg.evaluate("""() => {
      const sc=[...document.querySelectorAll('.m-scene')].find(s=>getComputedStyle(s).visibility!=='hidden');
      const board=sc.querySelector('.tc-board'); const strip=sc.querySelector('.tc-strip');
      const card=sc.querySelector('.tc-card');
      const kids=[...board.children].map(el=>({cls:el.className, top:el.offsetTop, h:el.offsetHeight}));
      return {card:[card.offsetWidth,card.offsetHeight], board:[board.offsetWidth,board.offsetHeight,board.scrollHeight],
              strip:[strip.offsetWidth,strip.offsetHeight,strip.scrollWidth],
              kids, fonts:[...sc.querySelectorAll('.tc-add,.tc-sub,.tc-name,.tc-cred')].map(e=>getComputedStyle(e).fontSize)};
    }"""))
    for t in [2.4, 7.5, 12.6, 17.0, 21.5, 28.0, 34.0, 39.0]:
        pg.evaluate("(t)=>{window.__reel.seek(t); return new Promise(r=>requestAnimationFrame(()=>r()));}", t)
        shot=pg.screenshot(clip={"x":0,"y":0,"width":1080,"height":1920}, type="jpeg", quality=92)
        (OUT/f"new-{t}.jpg").write_bytes(shot)
        im=Image.open(io.BytesIO(shot)).convert("RGB")
        st=ImageStat.Stat(im)
        # bottom band where the platform UI sits must stay clean/dark
        band=im.crop((0,1560,1080,1920)); bs=ImageStat.Stat(band)
        print(t, "mean", [round(v) for v in st.mean], "bottom-band mean", [round(v) for v in bs.mean])
    b.close()
print("frames written", OUT)
