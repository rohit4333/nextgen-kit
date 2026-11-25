# Build a Riyadh-localised copy of the 6-slide carousel.
# Only slides 03, 04 and 06 change; visuals on 01, 02 and 05 stay identical.
#
# Run: py .\exports\make-riyadh-deck.py
# Out: nextgen-creative-kit-riyadh.html

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / "nextgen-creative-kit.html").read_text(encoding="utf-8")


def rep(old, new, label):
    global src
    assert src.count(old) == 1, f"{label}: found {src.count(old)}"
    src = src.replace(old, new)


# Local layout additions. Compact the two affected slides so the footers stay
# inside the 1080² frame after the extra lines are added.
rep("  /* ---------- MOBILE LEGIBILITY ---------- */",
    """  /* ---------- Riyadh localisation ---------- */
  .riyadh-tag{display:inline-flex;align-items:center;align-self:flex-start;gap:10px;
    margin-top:14px;padding:9px 15px;border-radius:2px;background:rgba(18,150,140,.10);
    border:1.2px solid rgba(18,150,140,.55);font-family:var(--mono);font-size:15px;
    letter-spacing:1.5px;color:#0F766E}
  .s6-phone-note{font-family:var(--mono);font-size:16px;letter-spacing:1.4px;font-weight:600;
    color:rgba(246,241,231,.62);margin-top:10px}
  .s6-cta .s6-phone-note{color:rgba(24,10,4,.9);margin-top:4px;font-size:19px;font-weight:700}
  .s6-price{display:inline-flex;align-items:center;align-self:flex-start;gap:12px;
    margin-top:18px;padding:12px 18px;border-radius:2px;background:var(--teal);
    color:#04211F;font-family:var(--mono);font-size:19px;font-weight:700;
    letter-spacing:2px;box-shadow:6px 6px 0 rgba(18,150,140,.20)}
  .s6-note-ksa{font-family:var(--mono);font-size:16px;letter-spacing:1.5px;font-weight:600;
    color:rgba(246,241,231,.58);margin-top:12px;line-height:1.6}
  .s6 .h1{font-size:104px}
  .s6 .body{font-size:28px;margin-top:20px}
  .s6-cta{margin-top:30px;padding:26px 40px 24px}
  .s6-cta .num{font-size:50px}
  .s6 .risk{margin-top:18px}
  .s6-micro{margin-top:12px}
  .s4-note a{color:inherit;text-decoration:none;border-bottom:1px solid rgba(246,241,231,.35)}
  .s4-note a:hover{color:#FF8055;border-bottom-color:#FF8055}
  /* ---------- MOBILE LEGIBILITY ---------- */""", "css")

# Slide 03 — keep the fix slide clean; Riyadh specifics live on S6.

# Slide 04 — photo and credentials untouched; LinkedIn link is already in the source.

# Slide 05 — Riyadh ticket badge reflects KSA time.
rep("""            <div class="meta">LIVE · 1-ON-1 · ONLINE</div>""",
    """            <div class="meta">LIVE · 1-ON-1 · <span class="ksa">KSA TIME</span></div>""",
    "slide 05 ticket badge")
# Slide 06 — India-number note, price box, KSA-time note.
rep("""          <div class="s6-cta">
            <div class="lbl">WHATSAPP TO BOOK</div>
            <div class="num">+91 91941 34507</div>
          </div>
          <div class="risk"><span>NO CONTRACT · CLEAR FEE</span></div>""",
    """          <div class="s6-cta">
            <div class="lbl">WHATSAPP TO BOOK</div>
            <div class="num">+91 91941 34507</div>
            <div class="s6-phone-note">+91 number · sessions run on KSA time</div>
          </div>
          <div class="s6-price">DEMO FREE · THEN 90 SAR / SESSION</div>
          <div class="risk"><span>NO CONTRACT · CLEAR FEE</span></div>""",
    "slide 06 price + notes")

out = ROOT / "nextgen-creative-kit-riyadh.html"
out.write_text(src, encoding="utf-8")
print(f"wrote {out}  {len(src):,} chars")
