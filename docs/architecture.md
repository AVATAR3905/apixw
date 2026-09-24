# Architecture

```mermaid
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

