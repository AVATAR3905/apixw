#!/usr/bin/env python3
"""Render the Airfare Observatory architecture diagram as a PNG.

Pure PIL so it runs anywhere pillow is installed (no graphviz/mermaid CLI).
Draws the real flow: source simulations -> OCR strips -> calibrated alignment
-> VLM fuse -> schedule backup -> persistence -> analytics, plus the optional
APIX bridge to the AyushyaRanjan/APIx index API.

Writes ``docs/architecture.png`` (and a mermaid twin in ``docs/architecture.md``).
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from PIL import Image, ImageDraw, ImageFont  # noqa: E402


def _font(size: int):
    for cand in ("C:\\Windows\\Fonts\\consola.ttf", "C:\\Windows\\Fonts\\segoeui.ttf"):
        if os.path.exists(cand):
            return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


# (x, y, w, h, label, fill, outline, text_color)
def _box(d, x, y, w, h, title, lines, fill=(24, 24, 34), outline=(120, 120, 140), title_fill=(220, 220, 235)):
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=fill, outline=outline, width=2)
    f_t = _font(15)
    f_s = _font(12)
    d.text((x + 14, y + 8), title, font=f_t, fill=title_fill)
    yy = y + 30
    for line in lines:
        d.text((x + 14, yy), line, font=f_s, fill=(180, 180, 195))
        yy += 16
    return (x + w // 2, y + h)


def _arrow(d, p_from, p_to, label=""):
    x1, y1 = p_from
    x2, y2 = p_to
    import math

    d.line([x1, y1, x2, y2], fill=(150, 190, 255), width=3)
    angle = math.atan2(y2 - y1, x2 - x1)
    hx, hy = 9, 7
    lt = (x2 - hx * math.cos(angle) - hy * math.sin(angle), y2 - hx * math.sin(angle) + hy * math.cos(angle))
    rt = (x2 - hx * math.cos(angle) + hy * math.sin(angle), y2 - hx * math.sin(angle) - hy * math.cos(angle))
    d.polygon([(x2, y2), lt, rt], fill=(150, 190, 255))
    if label:
        f = _font(12)
        d.text(((x1 + x2) / 2 + 6, (y1 + y2) / 2 - 8), label, font=f, fill=(150, 190, 255))


def main():
    W, H = 1180, 900
    img = Image.new("RGB", (W, H), (12, 12, 18))
    d = ImageDraw.Draw(img)

    f_head = _font(20)
    d.text((30, 22), "India Airfare Price Observatory (APIX-2.0) - Extraction & Indexing Architecture",
           font=f_head, fill=(235, 235, 245))

    cx = 240  # main column center

    # Layer 1: sources
    p1 = _box(d, 40, 70, 400, 96, "1  SOURCES",
              ["Playwright results-page render (fixture/sim)", "Published DEL->BOM schedule (64-65 daily)", "Real fare DOM (browser collector)"])

    # Layer 2: extraction
    p2 = _box(d, 40, 210, 400, 172, "2  EXTRACTION (PP-OCRv6)",
              ["element_rects -> cell geometry", "2 tall strips: info | price", "OCR tokens -> row buckets", "_assigned_rows: signed-offset calibration", "65 cards -> per-flight observations"])
    _box(d, 620, 210, 260, 140, "DOM geometry",
         ["per-card cell rects", "card centers", "strip y-offsets"])
    d.line([(620, 260), (440, 260)], fill=(150, 190, 255), width=3)
    _arrow(d, p1, (cx, 210))

    # Layer 3: VLM fuse
    p4 = _box(d, 40, 430, 400, 150, "3  VLM FUSE (headline card)",
              ["local: PaddleOCR-VL-1.6 (0.9B)", "cloud: OpenRouter free vision", "(inclusionai/ling-3.0-flash-vl)", "structured JSON fields -> cheap-", "est record extraction_method=VLM"])
    _box(d, 620, 430, 260, 120, "VLM backends",
         ["paddleocr_vl (local)", "openrouter (free tier)", "EXTRACTION_VLM_BACKEND switch"])
    d.line([(620, 470), (440, 470)], fill=(150, 190, 255), width=3)
    _arrow(d, p2, (cx, 430))

    # Layer 4: backup + normalizer
    p6 = _box(d, 40, 630, 400, 120, "4  BACKUP + NORMALIZE",
              ["_schedule_backup_quotes: fill gaps", "every scheduled flight covered", "RealFareNormalizer: fare breakdown", "(base/tax/UD/convenience)"])
    _arrow(d, p4, (cx, 630))

    # Layer 5: persistence
    _box(d, 40, 790, 400, 90, "5  PERSIST (database/session)",
         ["PostgreSQL (airfare_observatory)", "SQLite fallback", "fare_observations rows with provenance"])
    _arrow(d, p6, (cx, 790))

    # Right column: analytics + API + bridge
    _box(d, 700, 640, 440, 96, "ANALYTICS (statistics/)",
         ["Laspeyres headline index", "carrier / corridor / lead-time matrices", "confidence scoring"])
    _box(d, 700, 760, 440, 96, "APIX BRIDGE + UI (compat layer)",
         ["apix_ui router: /index /routes /backtest", "/fares/cleaned /analytics/heatmap", "/analytics/elasticity + /ingest/dummy", "served by FastAPI /ui static frontend"])
    _arrow(d, (700, 690), (440, 690), "feed")
    _arrow(d, (700, 808), (440, 808), "export")

    # caption
    f_cap = _font(12)
    cap_text = ("SCRAPE_MODE: live | calibrated | hybrid   |   methods: DOM_BROWSER -> OCR -> VLM -> SCHEDULE_BACKUP   |   "
                "159 unit tests, ruff-clean")
    d.text((40, H - 40), cap_text, font=f_cap, fill=(110, 110, 130))

    os.makedirs(os.path.join(PROJECT_ROOT, "docs"), exist_ok=True)
    out = os.path.join(PROJECT_ROOT, "docs", "architecture.png")
    img.save(out)
    print("wrote", out)

    # Mermaid twin
    mermaid = """```mermaid
flowchart TD
  S1[Playwright results-page render] --> E1[element_rects cell geometry]
  S2[Published DEL-BOM schedule] --> E2[crop 2 strips: info | price]
  E1 --> E3{OCR PP-OCRv6 tokens}
  E2 --> E3
  E3 --> E4[ROW alignment _assigned_rows]
  E4 --> F1[per-flight observations]
  F1 --> V1[VLM fuse - cheapest]
  V1 --> B1[Schedule backup fills gaps]
  B1 --> N1[RealFareNormalizer]
  N1 --> P1[(fare_observations PostgreSQL / SQLite)]
  P1 --> A1[Analytics: index & matrices]
  P1 --> BR1[APIX bridge raw_quotes]
  BR1 --> BR2[cleaned_fares + MV route_day_summary]
  BR2 --> API1[FastAPI /api/v1/index]
  API1 --> API2[apix_ui router: /index /routes /backtest]
  API2 --> UI[(FastAPI /ui static frontend)]
  V1 -.local PaddleOCR-VL.-> V
  V1 -.OpenRouter free vision.-> V
```

SCRAPE_MODE: `live` (network) · `calibrated` (deterministic offline) · `hybrid` (calibrated carrier gates + live Google Flights RPC).
See [SCRAPING_OCR_VLM.md](SCRAPING_OCR_VLM.md) for the full collecting/extraction pipeline.
"""
    with open(os.path.join(PROJECT_ROOT, "docs", "architecture.md"), "w", encoding="utf-8") as fh:
        fh.write("# Architecture\n\n" + mermaid + "\n")
    print("wrote", os.path.join(PROJECT_ROOT, "docs", "architecture.md"))


if __name__ == "__main__":
    main()
