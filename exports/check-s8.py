from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(r"C:\Users\rohit\OneDrive\Documents\Default Project")
url=(ROOT/"nextgen-creative-kit.html").as_uri()+"#motion=capture"
with sync_playwright() as p:
    b=p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",headless=True)
    pg=b.new_page(viewport={"width":1080,"height":1920}); errs=[]
    pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.goto(url,wait_until="load"); pg.wait_for_function("window.__reel && window.__reel.ready")
    pg.evaluate("(t)=>{window.__reel.seek(t); return new Promise(r=>requestAnimationFrame(()=>r()));}",39)
    print("errors",errs)
    print(pg.evaluate("""() => {
      const sc=[...document.querySelectorAll('.m-scene')].find(s=>getComputedStyle(s).visibility!=='hidden');
      const f=sc.querySelector('.frame'), copy=f.querySelector('.m-copy'), line=f.querySelector('.line');
      const contact=f.querySelector('.s8-contact'), btn=contact.querySelector('span');
      const abs=el=>{const r=el.getBoundingClientRect();return [Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom)];};
      const box=el=>({top:el.offsetTop,h:el.offsetHeight});
      return {copy:box(copy),line:box(line),contact:box(contact),contactScroll:contact.scrollHeight,
              lineBottom:line.offsetTop+line.offsetHeight+copy.offsetTop,
              contactBottom:contact.offsetTop+contact.offsetHeight+copy.offsetTop,
              btn:abs(btn), lineText:line.textContent};
    }"""))
    b.close()
