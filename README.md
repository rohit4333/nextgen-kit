# NextGen Creative Kit

Design + video system for a Bhanzu maths-tutor campaign: a scrollable deck, a set of
social exports (carousels, country ads, posters) and the 41.2s reel with a fully
produced soundtrack.

## What's inside

| Path | What it is |
| --- | --- |
| `nextgen-creative-kit.html` | The deck: all slides plus the reel storyboard, motion timeline and SVG symbol layer. Source of truth for every visual. |
| `linkedin-carousel-quiet-confidence.html` | LinkedIn carousel variant. |
| `country-ads.html` | Country-specific ad variants (UAE, KSA, Australia). |
| `signal-noise-poster.svg` | Poster artwork. |
| `assets/` | Portrait cut-outs, textures and photos used by the deck. |
| `exports/` | Everything rendered out of the deck — see below. |

## Exports

- `exports/png/` — deck slides at 2× (1080×1350 / 1080×1920).
- `exports/png-1536/`, `exports/png-4k/` — same slides at 1536 px and 4K.
- `exports/thumbs/` — gallery thumbnails.
- `exports/gif/` — looping teasers.
- `exports/mp4/` — the 41.2s reel (legacy `reel-60s*` filenames):
  - `reel-60s.mp4` — final, video + narration + score + SFX
  - `reel-60s-premium.mp4` — identical mux of `reel-60s.mp4`
  - `reel-60s-music.mp4` — video + score/SFX, no narration
  - `reel-60s-silent.mp4` — visual master, no audio
- `exports/audio/` — 48 kHz / 16-bit stems: `-music`, `-narration`, `-mix`.
- `exports/vo/` — per-scene narration clips (`vo-s1.wav` … `vo-s8.wav`).
- `exports/index.html` — asset gallery for browsing all of the above.

## Rebuilding

```powershell
# narration (edge-tts, en-IN-NeerjaExpressiveNeural, phrase-level prosody)
py .\exports\make-reel-voiceover.py
py .\exports\make-reel-voiceover.py --only 6   # re-record a single scene

# stills: all assets, or just the ones that changed
powershell -ExecutionPolicy Bypass -File .\exports\export-pngs.ps1            # 2x
powershell -ExecutionPolicy Bypass -File .\exports\export-pngs.ps1 -Only s4   # one slide
powershell -ExecutionPolicy Bypass -File .\exports\export-pngs-1536.ps1 -Only s4
powershell -ExecutionPolicy Bypass -File .\exports\export-pngs-4k.ps1 -Only s4
py .\exports\make-thumbs.py --only deck-04-the-tutor

# score + SFX + mix, then mux onto the existing silent video
py .\exports\make-reel-premium-audio.py          # skips work that is already current
py .\exports\make-reel-premium-audio.py --force  # force a full audio rebuild
```

`make-reel-premium-audio.py` only re-renders what changed: it compares the mtimes of
`reel_audio_engine.py` and `exports/vo/*.wav` against the stems, and the stems and the
silent video against the MP4s, so untouched deliverables are never re-exported. The
video itself is never re-rendered by the audio pipeline — the existing visual master is
reused as-is.

The export scripts take `-Only` / `--only` so a copy tweak on one slide re-renders that
slide only (2x, 1536, 4K, thumb) instead of the whole kit.

Requirements: Python 3.11+, `numpy`, `scipy`, `edge-tts`, `imageio-ffmpeg`.

## Audio design

- 120 BPM grid so every cut (6 / 13 / 20 / 29 / 39 / 48 / 54 s) lands on a pulse.
- Section-aware arrangement: tension → empathy (no drums) → weight → lift → warm
  half-time → confident → resolve → trusted close.
- Felt piano, bowed-string pads, sub bass and soft organic percussion; convolution
  reverb on the music only, narration stays dry and close.
- Look-ahead sidechain ducks the bed (and the low band a little deeper) under every
  spoken phrase; the master is gated and limited to ≈ −14.0 LUFS / −2.5 dBFS true peak.
- SFX are deliberately quiet: soft impacts on the act turns, air whooshes on cuts,
  ticks on the credential lines, chimes on the reveal and the closing CTA.
