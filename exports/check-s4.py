"""Audit deck slide 04 (the tutor).

Confirms the credibility plates fit inside the dark card and that
IIIT ALLAHABAD / BHANZU are set large and bold, not buried in small type.

Run: py .\\exports\\check-s4.py
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = (ROOT / "nextgen-creative-kit.html").as_uri()
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

MEASURE = """
() => {
  const slide = [...document.querySelectorAll('.slide.s4')]
    .find(x => getComputedStyle(x).position === 'fixed') ||
    document.querySelector('.slide.s4');
  const card = slide.querySelector('.s4-card');
  const cr = card.getBoundingClientRect();
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { y: Math.round(r.top - cr.top), b: Math.round(r.bottom - cr.top),
             x: Math.round(r.left - cr.left), r: Math.round(r.right - cr.left) };
  };
  const info = slide.querySelector('.s4-info');
  const out = { card: { w: Math.round(cr.width), h: Math.round(cr.height) } };
  out.info = Object.assign(box(info), { scroll: info.scrollHeight, client: info.clientHeight });
  out.name = box(slide.querySelector('.s4-name'));
  out.creds = [...slide.querySelectorAll('.s4-cred')].map(box);
  out.values = [...slide.querySelectorAll('.s4-v')].map(el => {
    const cs = getComputedStyle(el);
    return Object.assign(box(el), { text: el.textContent.trim(),
                                    size: Math.round(parseFloat(cs.fontSize)),
                                    weight: cs.fontWeight, colour: cs.color });
  });
  out.body = box(slide.querySelector('.s4-body'));
  out.note = box(slide.querySelector('.s4-note'));
  out.photo = box(slide.querySelector('.s4-photo'));
  out.missing = !slide.querySelector('.s4-role') && !slide.querySelector('.s4-now');
  return out;
}
"""


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        pg = b.new_page(viewport={"width": 1080, "height": 1080})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(URL + "#export=s4", wait_until="load")
        pg.wait_for_timeout(900)
        m = pg.evaluate(MEASURE)
        b.close()

    print("page errors:", errs)
    print(json.dumps(m, indent=1, ensure_ascii=False))

    assert not errs, errs
    assert m["card"] == {"w": 924, "h": 612}, m["card"]
    assert m["missing"], "old small s4-role / s4-now lines should be gone"
    assert len(m["values"]) == 3, m["values"]
    for v in m["values"]:
        assert v["size"] >= 30, ("credential word too small", v)
        assert int(v["weight"]) >= 700, ("credential word not bold", v)
        assert v["b"] <= m["card"]["h"] - 40, ("credential spills the card", v)
    assert [v["text"] for v in m["values"]] == ["IIIT ALLAHABAD", "SAMSUNG", "BHANZU"], m["values"]
    assert m["note"]["b"] <= m["card"]["h"], m["note"]
    print("\nOK — deck 04 carries all three credentials as large bold plates.")


if __name__ == "__main__":
    main()
