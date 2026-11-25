# Build 4:5 portrait (1080 x 1350) copies of both carousels.
# The extra 270px of height is spent twice: layout spacing (CSS) and a larger
# type scale (TEXT_45). Both blocks are appended AFTER the shared mobile
# legibility layer so they win the cascade — the square rules must never
# cancel the 4:5 spacing or type.
#
# Run: py .\exports\make-carousel-45.py
# Out: nextgen-creative-kit-45.html
#      nextgen-creative-kit-riyadh-45.html

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CSS = """
  /* ---------- 4:5 portrait layout · 1080x1350 ---------- */
  .sq{width:1080px;height:1350px;padding:104px 88px}
  .kicker{margin-bottom:26px}
  .foot{padding-top:26px}

  /* S1 — bottom-anchored copy follows the taller canvas */
  .s1{padding:104px 88px}
  .s1 .accent{left:88px;bottom:372px}
  .s1 .body{left:88px;bottom:236px;max-width:760px}
  .s1-art{right:52px;bottom:424px;width:380px;height:301px}

  /* S2 */
  .s2 ol{margin-top:46px}
  .s2 li{padding:20px 0}
  .chart{height:206px;margin-top:32px}
  .s2 .body{margin-top:28px}

  /* S3 — restore full-size diagram in the taller frame */
  .s3 .h1{font-size:82px}
  .s3-diagram{margin-top:30px}
  .s3-panel{padding:16px 18px;gap:12px}
  .dots{grid-template-columns:repeat(6,32px);gap:14px}
  .dots i{width:32px;height:32px}
  .orbit{min-height:216px}
  .orbit svg{width:240px;height:216px}
  .s3 .body{margin-top:18px}
  .s3 .chips{margin-top:16px}

  /* S4 — let the photo card grow into the extra height */
  .s4-card{height:842px;margin-top:42px}
  .s4-info{padding:40px 40px 20px 52px}
  .s4-body{margin-top:16px}
  .s4-note{max-width:560px}

  /* S5 */
  .s5 .h1{font-size:82px}
  .s5 .body{margin-top:20px}
  .s5 ol{margin-top:24px;gap:16px}
  .ticket{margin-top:24px;padding:18px 22px}
  .s5-after{margin-top:24px}

  /* S6 — restore hero scale; rebalance the artwork */
  .s6 .h1{font-size:116px}
  .s6 .body{margin-top:20px}
  .s6-cta{margin-top:28px}
  .s6 .risk{margin-top:10px}
  .s6-micro{margin-top:16px}
  .s6 .ghost{top:380px}
"""

# Placed last: 46-48px body type renders as ~17 CSS px on a 393px phone.
TEXT_45 = """
  /* ---------- 4:5 portrait text scale · 1080x1350 ---------- */
  .kicker{font-size:36px;letter-spacing:3px}
  .foot{font-size:28px;letter-spacing:1.5px}
  .body{font-size:48px;line-height:1.34}

  .s1 .body{font-size:46px;line-height:1.38}

  .s2 li{font-size:46px;padding:20px 0;line-height:1.3}
  .s2 li::before{font-size:28px;min-width:72px;padding-top:8px}
  .s2 .body{font-size:46px}

  .s3 .body{font-size:46px}
  .s3-h{font-size:26px;letter-spacing:1px;font-weight:600}
  .s3-f{font-size:26px;letter-spacing:1px;font-weight:700}
  .s3-scope{font-size:26px;letter-spacing:1px;margin-top:26px}
  .s3-scope > span:first-child{font-size:26px;letter-spacing:1.4px}
  .s3-weekend{font-size:18px;letter-spacing:1.4px;padding:6px 11px}
  .chip{font-size:24px;padding:7px 12px}
  .riyadh-tag{font-size:22px;letter-spacing:.8px;padding:8px 12px}

  .s4-k{font-size:26px}
  .s4-c{font-size:25px;letter-spacing:1.3px}
  .s4-v{font-size:42px}
  .s4-name{font-size:52px}
  .s4-body{font-size:36px;line-height:1.34;max-width:400px}
  .s4-proof{font-size:22px;letter-spacing:1.2px;margin-top:8px}
  .s4-note{font-size:23px;letter-spacing:1px;line-height:1.6;padding-top:4px}
  .s4-stamp{font-size:24px}

  .s5 .h1{font-size:76px}
  .s5 li{font-size:40px;line-height:1.28}
  .s5 li span{font-size:26px}
  .s5 .body{font-size:44px}
  .ticket .big small{font-size:26px}
  .ticket .meta{font-size:26px;letter-spacing:1px}
  .seal{font-size:22px}
  .s5-pill{font-size:24px;letter-spacing:.7px;padding:18px 26px}
  .s5-proof{font-size:21px;letter-spacing:.9px}

  .s6 .body{font-size:48px;line-height:1.32}
  .s6-cta .lbl{font-size:26px;letter-spacing:1.8px}
  /* keep the specificity fix from the shared layer */
  .s6 .risk span{font-size:28px;letter-spacing:1.1px;padding:10px 13px}
  .s6-micro span{font-size:26px;letter-spacing:1.2px;font-weight:600;color:rgba(246,241,231,.75)}
  .s6-phone-note{font-size:28px;letter-spacing:.9px;font-weight:600}
  .s6-cta .s6-phone-note{font-size:32px;color:rgba(24,10,4,.9);font-weight:700}
  .s6-price{font-size:32px;letter-spacing:1px}
  .s6-note-ksa{font-size:28px;letter-spacing:.9px;font-weight:600}
"""


def build(source_name: str, out_name: str) -> None:
    src = (ROOT / source_name).read_text(encoding="utf-8")
    marker = "  /* ---------- MOBILE LEGIBILITY ---------- */"
    assert marker in src, f"no legibility marker in {source_name}"

    # Both 4:5 blocks must come after the shared legibility layer.
    end = src.rfind("</style>")
    assert end != -1, f"no closing style in {source_name}"
    out = src[:end] + CSS + TEXT_45 + src[end:]

    target = ROOT / out_name
    target.write_text(out, encoding="utf-8")
    print(f"wrote {target.name}  {len(out):,} chars")


if __name__ == "__main__":
    build("nextgen-creative-kit.html", "nextgen-creative-kit-45.html")
    build("nextgen-creative-kit-riyadh.html", "nextgen-creative-kit-riyadh-45.html")
