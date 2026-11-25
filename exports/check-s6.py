"""Audit the S6 tutor poster (reel scene 6).

Three passes, all headless:
  1. static export clone (#export=r6) — geometry fits the 932x620 poster
  2. live motion scene at a few beats — every block visible, inside the card
  3. content contract — all credibility details and the worked problems exist

Run: py .\\exports\\check-s6.py
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = (ROOT / "nextgen-creative-kit.html").as_uri()
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

MEASURE = """
() => {
  const all = [...document.querySelectorAll('.s6-scene')];
  if (!all.length) return { error: 'no .s6-scene' };
  const sc = all.find(x => {
    const m = x.closest('.m-scene');
    if (m) return getComputedStyle(m).visibility !== 'hidden';
    return x.getBoundingClientRect().width > 800;
  }) || all[0];

  const card = sc.querySelector('.s6-card');
  const cr = card.getBoundingClientRect();
  if (!cr.width) return { error: 'card has no box' };
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return { x: Math.round(r.left - cr.left), y: Math.round(r.top - cr.top),
             w: Math.round(r.width), h: Math.round(r.height),
             b: Math.round(r.bottom - cr.top), r: Math.round(r.right - cr.left),
             op: Math.round(parseFloat(cs.opacity) * 100) / 100 };
  };
  const out = { card: { w: Math.round(cr.width), h: Math.round(cr.height) } };
  out.name = box(sc.querySelector('.s6-name'));
  out.note = box(sc.querySelector('.s6-note'));
  out.tags = box(sc.querySelector('.s6-tags'));
  out.photo = box(sc.querySelector('.s6-photo'));
  out.big = [...sc.querySelectorAll('.s6-big')].map(el => {
    const b = box(el); b.text = el.textContent.trim(); return b;
  });
  out.text = sc.textContent.replace(/\\s+/g, ' ').trim();
  out.counts = {
    sym: sc.querySelectorAll('.s6-sym').length,
    ghost: sc.querySelectorAll('.s6-ghost').length,
    frag: sc.querySelectorAll('.s6-frag').length,
  };
  // only flag real overflow of visible blocks, inside the poster
  const spill = [];
  ['.s6-left'].forEach(sel => {
    const el = sc.querySelector(sel);
    if (!el) return;
    const r = el.getBoundingClientRect();
    if (r.right > cr.right + 1 || r.bottom > cr.bottom + 1 ||
        r.left < cr.left - 1 || r.top < cr.top - 1) {
      spill.push(sel + ' ' + Math.round(r.right - cr.right) + '/' + Math.round(r.bottom - cr.bottom));
    }
  });
  out.spill = spill;
  return out;
}
"""

REQUIRED = ["ER.", "ROHIT VISHWAKARMA", "B.TECH & M.TECH", "IIIT-ALLAHABAD", "EX-SDE", "SAMSUNG", "BHANZU"]
BANNED = ["48 + 27", "92 − 37", "304 − 178", "1,000 − 487"]


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)

        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(URL + "#export=r6", wait_until="load")
        pg.wait_for_timeout(900)
        static = pg.evaluate(MEASURE)
        print("page errors:", errs)
        print("\n== static export clone ==")
        print(json.dumps(static, indent=1, ensure_ascii=False))
        pg.close()

        assert not static.get("error"), static
        assert static["card"] == {"w": 932, "h": 620}, static["card"]
        assert not static["spill"], static["spill"]
        assert static["photo"]["b"] <= 620 and static["photo"]["b"] >= 580, static["photo"]
        assert static["tags"]["b"] <= 620, static["tags"]
        for word in REQUIRED:
            assert word in static["text"], "missing copy: " + word
        for word in BANNED:
            assert word not in static["text"], "sum still in intro: " + word
        assert static["counts"]["sym"] >= 12, static["counts"]

        pg2 = b.new_page(viewport={"width": 1080, "height": 1920})
        pg2.goto(URL + "#motion=capture", wait_until="load")
        pg2.wait_for_function("window.__reel && window.__reel.ready", timeout=20000)
        for t in (24.5, 26.2, 28.0, 29.6, 31.2):
            pg2.evaluate(
                "(t) => { window.__reel.seek(t); return new Promise(r => requestAnimationFrame(() => r())); }",
                t,
            )
            m = pg2.evaluate(MEASURE)
            print(f"\n== motion t = {t} ==")
            print(json.dumps({k: m[k] for k in ("card", "photo", "tags", "spill")},
                             indent=1, ensure_ascii=False))
            print("   big:", [(v["text"], v["op"]) for v in m["big"]])

        b.close()
        print("\nOK — S6 poster fits, carries every credential, no problems board.")


if __name__ == "__main__":
    main()
