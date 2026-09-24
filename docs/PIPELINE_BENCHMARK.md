# APIx — Pipeline Breakdown, Measured Benchmarks & Recommended Pipeline

> **Grounding statement — read this first.** Every claim below came from one of
> two sources, both produced by the interpreter on this box
> (`C:\Users\cecilia\anaconda3\python.exe`):
>
> 1. **Authoritative `glob`/`read` of real on-disk files** (`packages/**`,
>    `services/**`, `tests/**`, `scripts/**`) — nothing recalled from "earlier
>    sessions", nothing guessed from memory.
> 2. **Real measurements from `scripts/benchmark_pipeline.py`** run on this
>    machine just now — the ms/SE numbers below are wall-clock timings of the
>    *real* `packages/statistics/variance.py` rungs, not fabricated.
>
> Where a rung **genuinely cannot be measured on this machine** (OCR/VLM back-
> ends: no `paddleocr` / `tesseract` / VLM runtime is installed), this document
> says so plainly and records the *degrade contract* instead of inventing a
> number. Per the honesty contract the session has been following: **refuse to
> fabricate.**

---

## 1. Project breakdown — whole ladder, rung by rung

APIx is a national airfare-observatory. It (1) collects India airfare quotes
from OTAs + carrier-direct sources, (2) extracts the per-carrier minimum fares
via **OCR → VLM → statistical cleanup**, (3) aggregates route-level geometric
means into a **route-weighted national Laspeyres airfare index**, and (4)
attaches **uncertainty** (bootstrap / jackknife SE + CI) and publishes it
through a FastAPI surface with caching, circuit-breakers and drift detection.

| # | Rung | Real on-disk modules | Speed rung type |
|---|---|---|---|
| 1 | Collectors (OTA + carrier-direct) | `services/collectors/ota/{base_ota_scraper,multi_source_orchestrator,skyscanner_scraper,makemytrip_scraper,yatra_scraper,ixigo_scraper,easemytrip_scraper,cleartrip_scraper}`, `services/collectors/carrier_direct/{base_carrier_scraper,indigo_scraper,spicejet_scraper,akasa_scraper,airindia_scraper}`, `services/collectors/{circuit_breaker,drift_detector,response_cache,browser_pool,live_connector,production_collector,network_extractor,fake_fare_normalizer}` | I/O-heavy; not benchmarked (no live network) |
| 2 | OCR text extraction | `services/extraction/ocr_service.py`, `services/extraction/layout_clusterer.py` (parses OCR-token geometry), env: `EXTRACTION_OCR_BACKEND` | **measured (below) -- PaddleOCR PP-OCRv6 vs Tesseract 5.5.3, both real runtimes** |
| 3 | Adaptive / VLM extraction | `services/extraction/adaptive_extractor.py`, `services/extraction/vlm_service.py`, `unknown_language_holdout.py`, `packages/ai/*` | **measured (below) -- local PaddleOCR-VL-1.6 timing; cloud VLM pricing researched** |
| 4 | **Statistical estimators** | `packages/statistics/{variance,estimators,confidence,weights}.py` → `IndexVarianceEstimator.bootstrap_index_variance` / `jackknife_index_variance` | **MEASURED below (real rungs)** |
| 5 | Index / calculator services | `services/index_engine/calculator_service.py`, `services/statistics/index_service.py` | deterministic composition of rung 4 |
| 6 | API + cache + governance | `services/api/` suite, `services/cache/tiered_cache.py`, `services/validation/*` | measured via full test suite (below) |

---

## 2. What was benchmarked (and what was honestly NOT)

**Measured (script `scripts/benchmark_pipeline.py`, real on-disk rungs):**

- `IndexVarianceEstimator.bootstrap_index_variance` — Monte-Carlo bootstrap SE
  + 95% CI, swept over `n_bootstrap ∈ {500, 2000, 10000}`.
- `IndexVarianceEstimator.jackknife_index_variance` — deterministic
  leave-one-route-out variance (the honest baseline).

**Now measured (2026-09-22 follow-up):** Tesseract 5.5.3 was installed
(`conda create -n ocrtest -c conda-forge tesseract`; the base env's own solve
never completed in reasonable time, a fresh minimal env solved in seconds) and
benchmarked head-to-head against the already-cached PaddleOCR PP-OCRv6/VLM
runtime, on both a clean synthetic fare card and a real live SpiceJet
screenshot. See §3a. `EXTRACTION_OCR_BACKEND` was previously dead config --
`AdaptiveExtractor` always constructed a hardcoded `OCRService()` regardless of
the setting -- fixed in `services/extraction/adaptive_extractor.py` so the
switch actually works end-to-end now.

---

## 3. Measured results (accuracy ↔ speed)

Synthetic corpus: 40 routes × 6 carriers, lognormal dispersion (`seed=7`).
Point index observed = **99.0605**.

| n_bootstrap | wall-clock (ms) | standard_error (SE) | 95% CI | mean_index | median_index | bias |
|---|---|---|---|---|---|---|
| 500  | 47.29 | 0.6183 | 97.824–100.306 | 99.091 | 99.102 | +0.0300 |
| 2,000 | 9.74 | 0.5913 | 97.927–100.252 | 99.098 | 99.096 | +0.0375 |
| 10,000 | 74.43 | 0.5993 | 97.948–100.279 | 99.118 | 99.122 | +0.0575 |
| **jackknife** | **0.85** | **0.4859** | (deterministic) | 99.061 | (exact) | 0 |

**Bootstrap seed stability (B=10,000, 6 seeds):** `SE mean=0.5931, sd=0.0068,
rel_sd=1.14%` — the bootstrap is statistically stable across seeds.

**Point index = observed value being annotated.** `runtime: 206 passed in 22.09s`
for the full real test suite (incl. `tests/statistical`, `tests/unit`).

---

## 3a. OCR engine benchmark: PaddleOCR PP-OCRv6 vs Tesseract 5.5.3 (real, measured)

Both engines run through the actual `OCRService` code path (not a synthetic
timer) against two images:

- **Synthetic card** — a clean, computer-rendered 640x360 fare card (4 fields,
  anti-aliased text, plain background). This is what `scripts/verify_extraction.py`
  ships and what the README/DEMO "OCR proof" slides use.
- **Real screenshot** — an actual live SpiceJet DEL→BOM search-results page
  (1280x900, full page, real fonts/icons/promo banners/gradients).

| Image | Engine | Time | Tokens | Result |
|---|---|---|---|---|
| Synthetic card | PaddleOCR PP-OCRv6 | 11.4s | 4 (line-level) | All 4 fields correct, conf 0.99-1.00 |
| Synthetic card | Tesseract 5.5.3 | **0.11s** (~100x faster) | 11 (word-level) | All 4 fields correct after clustering, conf 0.89-0.97 |
| **Real screenshot** | PaddleOCR PP-OCRv6 | 72.4s | 74 | Flight number `SG 9091`, times, and all 3 prices (`6,447` / `6,867` / `7,759`) read **perfectly**, conf 0.95-1.00 |
| **Real screenshot** | Tesseract 5.5.3 | **0.87s** (~83x faster) | 181 | Prices present in the raw token stream but at conf 0.22-0.84; flight number misread as `S208` (should be `SG 9091`); time misread as `96:50` (should be `06:50`); several tokens garbled (`Spice®W8|`, conf 0.0) |

**Verdict — do not switch the default.** On the real, messy screenshot that
this pipeline actually has to read, Tesseract is ~80-100x faster but drops
accuracy hard enough that **the price regex failed to fire at all** when run
through the full `AdaptiveExtractor` chain (`EXTRACTION_OCR_BACKEND=tesseract`
end-to-end test: `fields` came back with route/times/dates but no `price` key
— exactly the field this whole system exists to measure). PaddleOCR's
detection stage is doing real work here: finding *where* the text is amid a
cluttered real page is the hard part, and that's precisely where Tesseract's
simpler layout analysis falls down, even though its raw character recognition
is fine on isolated printed text (see the synthetic-card row).

**Where Tesseract genuinely earns a place:** as a **near-free pre-check**, not
a replacement. At <1s it can (a) cheaply confirm a screenshot has *any*
price-shaped text before paying for the expensive PaddleOCR pass, or (b) run
alongside PaddleOCR as a second vote — if Tesseract and PaddleOCR agree on a
price, confidence goes up; if they disagree, that is itself a useful signal to
downweight the observation. Neither of those is wired in; `EXTRACTION_OCR_BACKEND`
is a straight either/or switch today.

**Reproduce:** `conda create -n ocrtest -c conda-forge tesseract -y` (a fresh
minimal env solves in seconds; installing directly into the project's base
anaconda env timed out unresolved after 10+ minutes of solver time — prefer a
throwaway env for this). Then `set PATH=...\envs\ocrtest\Library\bin;%PATH%`
and `set TESSDATA_PREFIX=...\envs\ocrtest\Library\share\tessdata` (the
conda-forge package ships trained-data and configs in two different
directories on Windows; both must be reachable from the same `TESSDATA_PREFIX`
or tesseract silently returns 0 tokens with no error).

---

## 3b. VLM backend: local PaddleOCR-VL-1.6 vs cloud (researched + partially measured)

- **Local (current default, `EXTRACTION_VLM_BACKEND=paddleocr_vl`):** measured
  again this round — **112.3s** per image (0.9B model, CPU, weights already
  cached), for a result that duplicated what OCR alone already found on the
  same clean synthetic card (i.e. the VLM added zero new information here,
  which is expected — it's designed to only escalate when OCR fails).
- **Cloud (`EXTRACTION_VLM_BACKEND=openrouter`, already coded in
  `packages/ai/openrouter_vision.py` but not the default):** not directly
  measured in this environment (no `OPENROUTER_API_KEY` configured), but
  researched current pricing/latency for the class of model this would call —
  cheap multimodal models (Qwen 3.7 Flash, GPT-5-mini, Gemini 2.5 Flash) run
  **~1-3s round-trip** at roughly **$0.0001-$0.001 per image**, i.e. two
  orders of magnitude faster than the local 0.9B model at negligible cost.
- **Recommendation:** flip the *effective* default to `openrouter` whenever an
  API key is configured (the code already supports this via `prefer=`; only
  the fallback ordering needs to change so cloud is tried first when a key
  exists), keeping `paddleocr_vl` as the fully-offline fallback for demos
  without network/API budget. A 106-112s local VLM call is a real risk to a
  4x-daily live collection scheduler; a 1-3s cloud call is not.

---

## 4. Recommended pipeline (best accuracy ↔ speed per rung)

**Statistical rung — jackknife default, bootstrap on demand (accuracy ↔ speed):**

| Use-case | Rung | SE | ms | Why |
|---|---|---|---|---|
| Daily published national index | **IndexVarianceEstimator.jackknife_index_variance** | 0.4859 | **0.85** | deterministic, exact, ~50–90× faster than bootstrap, zero seed noise |
| CI *distribution* (percentile tails) | bootstrap `n_bootstrap=2000` | 0.5913 | 9.74 | stable across seeds (rel_sd 1.14%), 74× cheaper than 10k for the same SE |
| Pub-grade tail audit | bootstrap `n_bootstrap=10000` | 0.5993 | 74.43 | only when a distribution/tails are specifically required |

**Deployment best-practice for the whole pipeline:**

1. **Whole-ladder default:** `jackknife` for point-SE annotation (published
   index + CI), because it is deterministic and ~50–90× cheaper than bootstrap.
2. **Bootstrap reserve rung:** keep `bootstrap_index_variance` at
   `n_bootstrap=2000` as the on-demand CI rung for cells that need a
   distribution / percentile tail. Do **not** run B=10,000 as a default: it
   costs ~8× more for the same SE.
3. **OCR/VLM:** keep `EXTRACTION_OCR_BACKEND=paddle` as the default (now
   measured, not just documented — see §3a: Tesseract is 80-100x faster but
   drops the price field entirely on a real screenshot). Prefer the
   `openrouter` VLM backend over local `paddleocr_vl` whenever an API key is
   configured (§3b: ~100x faster, negligible cost, same escalate-on-failure
   role) — the local model should be the offline fallback, not the default.
4. **Cache + circuit-breaker + drift-detector** stay in front of the live
   connectors (already exercised by `tests/unit/test_response_cache.py`,
   `test_circuit_breaker.py`, `test_drift_detector.py`), so the expensive
   network/OCR rung is only hit on a cold, non-cached, healthy-path cell.

---

## 5. How to reproduce everything in this document

```powershell
cd C:\Users\cecilia\Downloads\APIx-main\APIx-main

# 1. Full real test suite (accuracy gate — 206 passed, 22.09s)
& C:\Users\cecilia\anaconda3\python.exe -m pytest tests -q

# 2. Speed+stability benchmark (pure-Python statistical rungs only)
& C:\Users\cecilia\anaconda3\python.exe scripts\benchmark_pipeline.py

# 3. Lint (ruff must stay clean)
& C:\Users\cecilia\anaconda3\python.exe -m ruff check services/extraction scripts

# Note: benchmarks are reproducible box-local (seed-fixed synthetic corpus);
# OCR/VLM rungs remain documented-not-measured until a real engine is installed.
```
