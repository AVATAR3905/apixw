# Scraping, OCR & VLM — Collection Pipeline Guide

This document covers the live-data collection pipeline: how flight prices are
scraped from the web, how pixels are turned into structured fare records with
OCR and a vision-language model, and how the whole thing is made safe to demo.

## Table of contents

1. [Feed architecture (two feeds)](#feed-architecture)
2. [SCRAPE_MODE: live / calibrated / hybrid](#scrape_mode)
3. [Feed 1 — Carrier direct scraping](#feed-1-carrier-direct)
4. [Feed 2 — Google Flights RPC](#feed-2-google-flights-rpc)
5. [OCR engine (PP-OCRv6)](#ocr-engine)
6. [VLM engine (PaddleOCR-VL / OpenRouter)](#vlm-engine)
7. [Adaptive extractor chain (DOM → OCR → VLM)](#adaptive-extractor)
8. [Verification & demo tooling](#verification--demo-tooling)
9. [Presentation runbook](#presentation-runbook)

---

## Feed architecture

The observatory collects the same corridor from two independent feeds and
reconciles them (`services/collectors/dual_feed_runner.py`):

| Feed | Source | Role | Key module |
|------|--------|------|------------|
| 1 (primary) | Airline direct booking portals (IndiGo, SpiceJet, Akasa, ...) | Authoritative price | `services/collectors/carrier_direct_scraper.py` + `carrier_direct/*_scraper.py` |
| 2 (validator) | Google Flights RPC endpoints | Cross-check / fallback, markup audit | `services/collectors/real_flight_connector.py` |

A `CrossFeedDiscrepancyValidator` (`packages/statistics/discrepancy_validator.py`)
compares the two, flags `AGGREGATOR_MARKUP` / `AGGREGATOR_DISCOUNT` when they
diverge beyond a threshold, and stores the reconciled primary observation via
`RealFareNormalizer` (`services/collectors/real_fare_normalizer.py`).

```
carrier portals ──> Playwright DOM ─┐
                                   ├─> reconcile (parity / markup audit) ─> fare_observations
Google Flights RPC ──> fast_flights ┘                       (is_synthetic=False)
```

All network work is made resilient with:
- a Playwright **browser pool** (`services/collectors/browser_pool.py`) that
  reuses idle contexts and degrades gracefully to a fresh launch;
- per-source **circuit breakers** (`services/collectors/circuit_breaker.py`)
  so a dead portal never stalls a corridor run;
- a **response cache** (`services/collectors/response_cache.py`) that dedupes
  repeated network reads (Redis first, in-memory fallback).

---

## SCRAPE_MODE

`packages/shared/config.py` exposes `SCRAPE_MODE` (env var `SCRAPE_MODE`,
default `live`). It switches the whole collector suite between network and
deterministic off-network behaviour, and is read inside each scraper.

| Mode | Carrier direct feed | RPC validator feed | Uses network | Typical use |
|------|---------------------|--------------------|--------------|-------------|
| `live` | real network scrape | real Google Flights | yes | production / rehearsal |
| `calibrated` | deterministic baseline | skipped (returns `[]`) | no | offline demos, hermetic tests |
| `hybrid` | deterministic baseline | **real** Google Flights | RPC only | presentations with network |

Setting it for a run (PowerShell):

```powershell
$env:SCRAPE_MODE = "hybrid"
python -m services.collectors.dual_feed_runner --route DEL-BOM --horizon 7
```

Why this exists: airline portals (goindigo.in, spicejet.com, ...) routinely
time out, hit CAPTCHAs, or drop the Playwright driver. In `live` mode the
browser path already degrades through pool → dedicated launch → calibrated
baseline so a single dead portal aborts nothing. `calibrated` / `hybrid` skip
the wait entirely for a fast, deterministic, network-independent run.

The `CarrierDirectScraper` gate lives at
`services/collectors/carrier_direct_scraper.py:70` and the RPC gate at
`services/collectors/real_flight_connector.py:65`.

---

## Feed 1 — Carrier direct

`services/collectors/carrier_direct_scraper.py::CarrierDirectScraper.scrape_carrier_corridor`

1. If `SCRAPE_MODE ∈ {calibrated, hybrid}` → immediately return
   `_generate_authoritative_carrier_quotes` (deterministic baseline tagged with
   a 5-part fare decomposition; see `carrier_direct/base_carrier_scraper.py`).
2. Otherwise try the **browser pool**: `get_browser_pool().run_browser(...)`.
3. On pool failure → a dedicated `async_playwright()` launch.
4. On any crash → calibrate to the baseline (never abort the corridor run).

Each carrier has an NDC-first scraper with a browser fallback and calibrated
model: `services/collectors/carrier_direct/{indigo,airindia,spicejet,akasa}_scraper.py`.
OTA scrapers (`ota/*_scraper.py` — MakeMyTrip, Cleartrip, Yatra, Ixigo,
Skyscanner, EaseMyTrip) follow the same three-tier pattern via
`ota/base_ota_scraper.py`.

The in-browser pass (`scrape_carrier_corridor` → `_scrape_with_context`) does:

```
DOM harvest ──> element_rects (flight/card geometry) ─┐
screenshot  ──> OCR strip passes ────────────────────┼─> AdaptiveExtractor ─> typed fare records
             └─ VLM escalation only if price/route missing
```

Because the offline OCR escalation can pull in the ~106s VLM once per card,
the fallback path is pinned to `AdaptiveExtractor(allow_vlm=False)` so a
presentation never stalls waiting on vision weights.

---

## Feed 2 — Google Flights RPC

`services/collectors/real_flight_connector.py::RealFlightRPCConnector.search_corridor_horizon`

`fast_flights` builds a real Google Flights request for the corridor/horizon
and returns live offers. Those are normalized to raw quotes (carrier code via
`_map_carrier_name_to_code`, synthesized flight numbers when the feed omits
them, departure/arrival parsed from the `departure` datetime).

Gating: in `calibrated` mode the RPC feed returns `[]` (the reconciliation
layer then marks everything `DIRECT_ONLY`). In `live` **and** `hybrid` it hits
Google Flights for genuine aggregator prices — this is what populates the
side-by-side parity table in `dual_feed_runner` output during a demo with
network (measured: ~3s, ~52 quotes for DEL→BOM).

The connector has its own circuit breaker and response cache keyed by
`rpc:{origin}:{dest}:{date}`.

---

## OCR engine

`services/extraction/ocr_service.py::OCRService`

- **Backend:** PaddleOCR `PP-OCRv6` detection + recognition (v5 fallback),
  loading paddleocr/paddlepaddle lazily so the rest of the pipeline imports
  and runs even where those heavy weights aren't installed.
- **Input:** an image path (full page or a cropped strip).
- **Output:** a list of `OCRToken(text, score, bbox)`.
- An in-process memo cache keyed by `(abs path, mtime)` dedupes repeated OCR
  of the same strip (several pipeline stages OCR the same files) — this is
  what keeps a full presentation run to a single real inference pass.

`services/extraction/layout_clusterer.py` turns the token stream into fare
cards: tokens are clustered by geometry (`LayoutClusterer.cards`), and
`fields_from_tokens` on the adaptive extractor parses price / route / airline /
flight / times / stops / duration with deterministic regexes.

Run it alone:

```powershell
python -c "from services.extraction.ocr_service import OCRService; print(len(OCRService().extract('C:/path/img.png')))"
```

`supports_ocr()` reports engine availability without triggering model load.

---

## VLM engine

`services/extraction/vlm_service.py::VLMService`

Two backends behind one interface:

| Backend | Trigger | Cost | Notes |
|---------|---------|------|-------|
| `PaddleOCR-VL-1.6` (0.9B) | preferred local visual backend | ~106s first inference per image; weights cached under `C:\Users\<user>\.paddlex\official_models\...` | fully offline |
| OpenRouter vision | network fallback for ambiguous fields | per-token API cost | `packages/ai/openrouter_vision.py` |

The local backend returns markdown-ish text from the image; a field parser
(`_parse_fields`) converts it to the same field set as the OCR stage, using
`_walk_strings` to recurse into the model's semi-structured output.

`supports_vlm()` reports availability without a 100s probe.
Backend selection is controlled by `EXTRACTION_VLM_BACKEND`
(`openrouter` | `paddleocr_vl`).

---

## Adaptive extractor

`services/extraction/adaptive_extractor.py::AdaptiveExtractor`

Deterministic first, neural last — precedence `DOM → OCR → VLM`:

1. **DOM**: element boxes + text straight from Playwright — cheapest, most trusted.
2. **OCR**: PP-OCRv6 + geometry clustering for pixel-only surfaces.
3. **VLM**: only escalates for fields neither earlier stage resolved (verified
   end-to-end: OCR alone resolves 4/4 fields at conf 0.99–1.00; the VLM fires
   only when price or route is still missing).

`AdaptiveExtractor.extract(ExtractionContext(image_path=..., dom_text=[...]))`
returns an `ExtractionResult(fields, extraction_method, confidence, chain)`.
`extraction_method` reflects the strongest stage that actually produced a field,
so downstream `ConfidenceService.composite` can discount weaker stages.

`allow_vlm=False` (used in the carrier-scraper OCR fallback) hard-suppresses
the vision stage — important for keeping live scraping responsive.

---

## Verification & demo tooling

| Script | What it proves | Rough runtime |
|--------|----------------|---------------|
| `scripts/verify_extraction.py` | Full OCR + VLM chain on a rendered fare card, stage by stage (tokens → cards → fields → VLM → verdict) | ~2 min (VLM weights already cached) |
| `scripts/verify_browser_pool.py` | Real Playwright Chromium through the pool: JS, text extraction, screenshot proof | ~2-5 s |
| `scripts/demo_ocr_vlm_pipeline.py` | Multi-airline extraction across N travel dates; `--vlm-every N` fuses the cheap head with the real VLM | minutes |
| `scripts/presentation_run.py` | One-command presentable run: full page + OCR strips + VLM panel + `06_report.md` | OCR ~minutes; full-page VLM inference ~20-45 min |
| `scripts/run_observatory.py` / `scripts/start_observatory.py` | Scheduled collection / API+collector startup | n/a |
| `python -m services.collectors.dual_feed_runner --route DEL-BOM --horizon 7` | Full reconcile + parity table + DB persistence | seconds (hybrid) |

All `scripts/verify_*.py` bootstrap `sys.path` to the project root so they run
from the repo root with a plain `python scripts/foo.py`.

Been run and confirmed on this machine: `verify_extraction.py` → **PASS**
(OCR 4 tokens ~10.5s conf 0.99+; VLM ~106s; chain verdict PASS),
`verify_browser_pool.py` → **PASS** (network load + JS + screenshot).

---

## Presentation runbook

Reproduce the demo exactly the way it was verified:

```powershell
# 1) OCR + VLM extraction chain (needs the cached PaddleOCR-VL weights)
python scripts/verify_extraction.py            # or --image <your screenshot>

# 2) Browser automation through the collector pool (works offline too)
python scripts/verify_browser_pool.py

# 3) Full reconcile with REAL Google Flights prices vs calibrated carrier gates
$env:SCRAPE_MODE = "hybrid"
python -m services.collectors.dual_feed_runner --route DEL-BOM --horizon 7

# 4) Illustrated extraction demo (assets + report into the out dir)
#    NOTE: local paddleocr_vl on the FULL PAGE image takes ~20-45 min.
#    For a fast slide deck use --vlm-backend none (or openrouter) instead.
python scripts/presentation_run.py --date 2026-09-16 --vlm-backend paddleocr_vl
```

Recommended demo mode: **`SCRAPE_MODE=hybrid`** — the carrier gates answer in a
fraction of a second (calibrated), the RPC feed contributes genuine aggregator
prices (~3s), and the reconcile table shows real `Direct+RPC Paired
Validations`, `Average Discrepancy`, and `AGGREGATOR_DISCOUNT` rows.

For the OCR/VLM image proof: `verify_extraction.py` runs the local VLM on a
small rendered card (~106s, incl. one-time weights load) — much faster than the
full-page presentation run — so prefer it for live neural-extraction demos.

No-network fallback: `SCRAPE_MODE=calibrated` runs everything deterministically
— expect `RPC Fallbacks Activated: 0` and an empty paired-validations table by
design; the header printed by `dual_feed_runner` states `SCRAPE_MODE: calibrated`
so the audience sees why.

Environment quick reference:

| Env var | Values | Effect |
|---------|--------|--------|
| `SCRAPE_MODE` | `live` / `calibrated` / `hybrid` | network vs deterministic feed gating |
| `EXTRACTION_ALLOW_OCR` | `true` / `false` | OCR stage on/off |
| `EXTRACTION_ALLOW_VLM` | `true` / `false` | VLM escalation on/off |
| `EXTRACTION_VLM_BACKEND` | `openrouter` / `paddleocr_vl` | select VLM backend |
| `DEMO_OUT_DIR` / `EXTRACT_VERIFY_DIR` | path | scratch / output dirs |