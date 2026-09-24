# Scripts Reference

Every runnable entry point in the observatory, what it does, and how to invoke
it. All paths are relative to the repo root; comma-separated env vars are set
per-invocation (PowerShell: `$env:VAR = "..."`).

---

## Orchestration & servers

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/run_observatory.py` | Unified one-command runner: seed DB, live collect, warm forecast accuracy, start FastAPI (8000) + dashboard (3000) | `python scripts/run_observatory.py [--reset --no-seed --no-collect --full --use-vlm --no-warm --no-servers --api-port --dash-port --prod-dash]` |
| `scripts/start_observatory.py` | Start FastAPI + Next.js dashboard concurrently with health checks | `python scripts/start_observatory.py` |
| `scripts/presentation_run.py` | Illustrated demo: renders a flight-results page, runs the real OCR (strips) + VLM chain, writes 6 presentation assets + report into an out dir | `python scripts/presentation_run.py --date 2026-09-16 --vlm-backend paddleocr_vl --out-dir "C:\Users\cecilia\Downloads\Apix output"` |
| `scripts/show_process.py` | Fresh OCR+VLM run for tomorrow's travel date, generating every PNG + MD stage file. See `docs/SCRAPING_OCR_VLM.md` | `python scripts/show_process.py [--day-offset 1]` |

## Collection & extraction pipelines

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/demo_ocr_vlm_pipeline.py` | Multi-airline OCR+VLM end-to-end extraction demo over the horizon; persists every fare card (not just cheapest) | `python scripts/demo_ocr_vlm_pipeline.py [--days 28 --vlm-every 7 --vlm-none --vlm-backend paddleocr_vl --no-persist [--route --start-offset]]` |
| `python -m services.collectors.dual_feed_runner` | Two-feed reconcile: carrier direct vs Google Flights RPC, prints parity table, persists real observations | env `SCRAPE_MODE=live\|calibrated\|hybrid` then `python -m services.collectors.dual_feed_runner --route DEL-BOM --horizon 7` |
| `scripts/verify_extraction.py` | Watch the full OCR+VLM extraction chain stage by stage on a rendered (or your own) fare card | `python scripts/verify_extraction.py [--image X.png --open]` |
| `scripts/verify_browser_pool.py` | Smoke-test real Playwright Chromium through the collector pool (JS + text + screenshot) | `python scripts/verify_browser_pool.py` |
| `scripts/run_production_rehearsal.py` | End-to-end MoSPI rehearsal walkthrough highlighting statistical/RW defenses | `python scripts/run_production_rehearsal.py` |

## Validation & maintenance

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/validate_flights.py` | Per-flight intrinsic (vs fixture ground truth) + live (vs Google Flights) fare validation | `python scripts/validate_flights.py [--route --date ...]` |
| `scripts/purge_synthetic_and_recalculate.py` | Permanently remove synthetic observations and recompute indices from authentic data only | `python scripts/purge_synthetic_and_recalculate.py` |
| `scripts/make_architecture_diagram.py` | Regenerates `docs/architecture.png` + `docs/architecture.md` (pure PIL, no graphviz) | `python scripts/make_architecture_diagram.py` |
| `scripts/_env_guard.py` | Dependency guard helper used by demo scripts (internal) | n/a |

---

## Key environment variables

| Var | Values | Effect |
|-----|--------|--------|
| `SCRAPE_MODE` | `live` / `calibrated` / `hybrid` | network vs deterministic feed gating (see `docs/SCRAPING_OCR_VLM.md`) |
| `EXTRACTION_ALLOW_OCR` | `true` / `false` | enable/disable the PP-OCRv6 stage |
| `EXTRACTION_ALLOW_VLM` | `true` / `false` | enable/disable VLM escalation |
| `EXTRACTION_VLM_BACKEND` | `paddleocr_vl` / `openrouter` | select VLM backend |
| `DEMO_OUT_DIR` / `EXTRACT_VERIFY_DIR` | path | scratch/output directory for demo/verify assets |
| `BROWSE_HEADLESS` | `true` / `false` | headless browser mode |

---

## Presentation demo (recommended order)

```powershell
# 1) Prove the browser automation path
python scripts\verify_browser_pool.py

# 2) Prove the OCR + VLM neural extraction (needs cached PaddleOCR-VL weights)
python scripts\verify_extraction.py

# 3) Live parity: instant calibrated carrier gates + REAL Google Flights prices
$env:SCRAPE_MODE = "hybrid"
python -m services.collectors.dual_feed_runner --route DEL-BOM --horizon 7

# 4) Illustrated assets + report into "Apix output"
python scripts\presentation_run.py --date 2026-09-16 --vlm-backend paddleocr_vl --out-dir "C:\Users\cecilia\Downloads\Apix output"
```

See `DEMO.md` for the full 6-minute narration timeline and
`docs/SCRAPING_OCR_VLM.md` for the pipeline internals.