# SIH Grand Finale: 6-Minute Judge Demonstration Script

> Step-by-step presentation script for the Smart India Hackathon Grand Finale evaluation panel.

---

## 🎬 Full Pipeline in Action (Live Commands)

Run the complete **collect → reconcile → persist → index → forecast → API → dashboard** chain:

```bash
# ONE-COMMAND ENTRY POINT (recommended): seeds DB, collects, warms accuracy, starts servers
python scripts/run_observatory.py                   # focused DEL-BOM T+15 collection
python scripts/run_observatory.py --reset            # wipe & reseed first
python scripts/run_observatory.py --full             # full 10-route x 5-horizon mission
python scripts/run_observatory.py --no-collect       # seed + servers only (no live scraping)
python scripts/run_observatory.py --no-servers       # pipeline only (no API/dashboard)
python scripts/run_observatory.py --help             # all flags
```

Or run the steps manually:

```bash
# STEP 1 — FOCUSED LIVE DEMO: one corridor, one horizon.
#   Feed 1: carrier-direct scraping (IndiGo / SpiceJet / Akasa booking engines)
#   Feed 2: Google-Flights RPC validator & fallback
#   Prints the side-by-side reconciliation table (direct vs RPC vs variance),
#   then normalizes & persists real observations (is_synthetic=False).
#   Hybrid mode = instant calibrated carrier gates + REAL RPC prices (recommended demo).
set SCRAPE_MODE=hybrid
python -m services.collectors.dual_feed_runner --route DEL-BOM --horizon 15

# STEP 1b — FULL MISSION: 10 corridors x 5 horizons (T+1..T+45), then automatically
#   recalculates official daily Laspeyres indices, carrier inflation, and corridor volatility.
python -m services.collectors.production_collector

# STEP 2 — SERVE THE OBSERVATORY API (auto-creates all tables incl. forecast_snapshots).
python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000   # http://localhost:8000/docs
#   The new APIx frontend is served by FastAPI itself:
#     http://localhost:8000/ui   (apps/api/static_ui/index.html, adapter router apix_ui.py)

# STEP 3 — DASHBOARD (Dev-mode server; also serves the built app).
cd apps/dashboard && npm run build && npm run start              # http://localhost:3000
```

What to click to prove each stage:
- `/` — National Overview: headline **T+15** index (proves collection → index engine).
- `/routes/DEL-BOM` — 5-component fare decomposition on real `fare_observations`.
- `/lead-time` — unpooled T+45→T+1 surge curve (proves all 5 horizons collected).
- `/forecast` — 28-day ensemble + **Forecast Backtest Accuracy** panel (proves `forecast_snapshots` persisted and scored vs realized via `/api/v1/forecast/accuracy`).
- `/quality` — SHA-256 raw-payload integrity gate + source health.
- `/docs` → `GET /api/v1/index`, `/api/v1/forecast/history-and-forecast`, `/api/v1/export/...` — researcher bulk exit.

### Statistical-Rigor demo blocks (v2.1)

Proves the methodology hardening round in ~30 seconds, all read/write against the local SQLite observatory DB:

```text
Dual-Series CORE        GET /api/v1/index?series_type=CORE          (HEADLINE=107.07 vs CORE=110.89 shown 2026-09-14)
Multi-OTA Audit         GET /api/v1/validation/source-pair          (OTA_SOURCE_PAIR markup rows: 39 markup / 11 parity)
Feed Correlation        GET /api/v1/validation/source-correlation   (CARRIER_DIRECT vs OTA_AGGREGATOR Pearson r per route)
Run Anomaly Scan        POST /api/v1/analytics/run-anomaly-detection (IQR+MAD scan, persists anomaly_events)
Anomaly Feed           GET /api/v1/analytics/anomalies             (severity counts + open/escalted OPEN alerts)
Index Confidence       GET /api/v1/index                           (now returns confidence_score / confidence_band / outlier_count)
```

- `series_type=HEADLINE|CORE` on `/index`, `/index/daily`, and the CSV export proves the festival-guarded CORE continuity series.
- `source-pair` rows compare every OTA against the authoritative carrier-direct reference (`AGGREGATOR_MARKUP` / `EXACT_PARITY`).
- `run-anomaly-detection` is idempotent (snapshot-replaces per date+series) and returns a live severity histogram.

### Governance & Policy Intelligence demo blocks (v2.2)

The political-economy pitch in ~90 seconds — why this isn't "another airfare website" but a
**policy instrument** for RBI / MoSPI / CCI / MoCA. All read-only against the local SQLite DB:

```text
Policy Signal        GET /api/v1/analytics/policy-signal          (STRUCTURAL 107.07 vs baseline 100.01, +7.06%;
                                                                   ATF +3.82% co-movement, 4 carriers → CPI passthrough call)
Leading Indicator    GET /api/v1/analytics/leading-indicator      (Billion-Prices weekly lead-lag vs MoSPI CPI,
                                                                   6 aligned weeks, lags 0-4, confident-r windows only)
Explainable Alerts   GET /api/v1/analytics/alerts                 (6 alerts, 0 unexplained: every event has an ATF/
                                                                   festival/availability/DOW correlation, plain English text)
HHI Concentration    GET /api/v1/analytics/concentration         (avg HHI 2259.9; DEL-IXS 3335.8 & DEL-DHM 3261.7 HIGH;
                                                                   r(HHI↔fare)=0.888, r(HHI↔vol)=0.872 — CCI case)
Intraday Volatility  GET /api/v1/analytics/intraday-volatility   (network CV 11.1%; best-time-to-book EVENING_1800 ₹4,552;
                                                                   DEL-BOM: book at NIGHT_2300 ₹5,370 vs NOON ₹7,058)
Availability-Adjusted GET /api/v1/analytics/availability-adjusted (SOLD_OUT scarcity premium, saturating max +35%,
                                                                   model parameter disclosed — never a quoted fare)
UDAN Monitor         GET /api/v1/analytics/udan                  (2 BREACHES: DEL-IXS 2.31x & DEL-DHM 2.40x vs ₹2,500
                                                                   UDAN affordability target; trunk median ₹5,378)
```

Talking points, one per check:
1. **Policy Signal (RBI MPC).** "Structural, not transient" is a one-line answer a monetary-policy
   analyst can act on — the spike is multi-carrier and ATF-aligned, so it's a passthrough to flag,
   not a festival blip. (Classifier: structural = 21+ day persistence, multi-carrier, ATF-aligned;
   transient = reversal within 14 days / festival-calendar aligned / single-carrier.)
2. **Leading Indicator (MoSPI).** Harvard PriceStats proved private high-frequency daily price data
   forecasts official CPI weeks ahead. We're instrumenting the same for Indian airfares — honest
   "no leading edge yet" at 6 weeks of prototype history, and the pipeline is live for when it
   accumulates: higher-frequency weekly sub-sampling + monthly CPI re-anchoring.
3. **Explainable Alerts (#11).** Every anomaly has a cause attributed (ATF up 1.7% over the window),
   not a bare red dot. Governance reviewers need the *why*.
4. **HHI Concentration (CCI).** Two regional routes are `HIGH`-concentration (HHI > 2500) and look like
   monopoly pricing — and the correlation proof (HHI vs fare 0.888) is a ready-made competition-monitoring brief.
5. **Intraday Volatility (consumer/IRDA).** "When to book" is now a data answer, not folklore —
   DEL-BOM fares swing ₹1,700 from noon to night.
6. **Availability-Adjusted.** SOLD_OUT quotes are demand, not missing data — scarcity premium corrects
   the index upward (capped +35%) for the true consumer-cost position.
7. **UDAN Monitor (MoCA).** The UDAN ₹2,500/1-hour promise is being beaten 2.3× on the very routes
   UDAN was created for — first automated affordability monitor of the scheme.

> **Deferred (roadmap):** seat-class CTDI, Claude natural-language analytics, Merkle audit log,
> and public API keys/webhooks are scoped but not built this round (see TASKS.md v2.2 notes).

### New frontend (APIx UI) demo path

The new dashboard is a static Single-Page App served at **`/ui`** on port 8000 (no Node server needed —
see `apps/api/routers/apix_ui.py`, `apps/api/static_ui/index.html`). It reads live local-SQLite data:

```
http://localhost:8000/ui          # dashboard (single page)
  /routes           -> GET /routes                 (10 DGCA-weighted corridors)
  overview          -> GET /index/headline         (national monthly headline)
  route index       -> GET /index?route=...&benchmark=...
  elasticity        -> GET /analytics/elasticity
  heatmap           -> GET /analytics/heatmap
  fares             -> GET /fares/cleaned?route=DEL-BOM&travel_date_from=2026-09-16&travel_date_to=2026-09-16
  backtest          -> GET /backtest               (vs official MoSPI/CPI series)
```

`/fares/cleaned` filters by observation date (`date_from`/`date_to`) **and** travel
date (`travel_date_from`/`travel_date_to`). The fares tab defaults to tomorrow's
travel date, so a `--horizon 1` collection run makes "tomorrow" rows appear
immediately — no server restart needed.

The frontend resolves `API_BASE` as same-origin (empty string) so no CORS/patch is needed.

> **Port conflict tip:** if port 8000 or 3000 is already occupied by a running instance
> (`[WinError 10048]` / `EADDRINUSE`), just open the already-running dashboard URL instead —
> several launches from previous sessions can leave servers up. Use `netstat -ano | findstr ":8000"`
> to find and stop stale processes before re-running the launcher.

Production automation: 4 daily snapshots (06:00 / 12:00 / 18:00 / 23:00 IST) via APScheduler —
`CollectionScheduler.start()` in `services/scheduler/collection_scheduler.py`.

**Keeping graphs fresh:** after a real collection run, recalculate the official
`index_values` series for the new observation dates so `/index` and `/index/headline`
extend past the seed window:

```powershell
python -m venv-agnostic  # use C:\Users\cecilia\anaconda3\python.exe as usual
python - <<'PY'
import datetime
from database.session import SessionLocal
from services.index_engine.calculator_service import DailyIndexCalculatorService
db = SessionLocal()
for d in (datetime.date(2026,9,10), datetime.date(2026,9,11), datetime.date(2026,9,12),
          datetime.date(2026,9,13), datetime.date(2026,9,14), datetime.date(2026,9,15)):
    DailyIndexCalculatorService.calculate_day_indices(db, observation_date=d)
    db.commit()
db.close()
PY
```

Only dates with unpresent observation coverage (≥1 route with an exact horizon /
APD slot) produce records — low-coverage days are tagged `EXPERIMENTAL`/`BETA`.
Heatmap and elasticity read `fare_observations` live, so they update automatically.

> Live network required for real scraping. If a carrier is blocked/offline, each connector
> degrades transparently: DOM → screenshot OCR → calibrated baseline, tagged
> `CALIBRATED_MODEL` / `is_synthetic`, so the demo always completes and the quality
> dashboard still shows the SHA-256 integrity gate. For a fully offline demo use
> `SCRAPE_MODE=calibrated`; for real RPC prices with instant carrier gates use
> `SCRAPE_MODE=hybrid`.

## 🖼️ OCR & VLM Proof Blocks (slides / appendix)

A PPT-ready set of images is produced by the presentation runner into
`C:\Users\cecilia\Downloads\Apix output` (see `docs/SCRAPING_OCR_VLM.md` for the
full pipeline explainer):

```powershell
# Verified end-to-end: OCR (PP-OCRv6, conf 0.99+) + VLM (PaddleOCR-VL-1.6) extraction chain
python scripts/verify_extraction.py

# Verified: real Playwright Chromium through the collector browser pool
python scripts/verify_browser_pool.py

# Live reconcile with REAL Google Flights prices vs calibrated carrier gates
set SCRAPE_MODE=hybrid
python -m services.collectors.dual_feed_runner --route DEL-BOM --horizon 7

# Full illustrated demo assets into "Apix output":
#   01_full_page.png 02_ocr_left_strip.png 03_ocr_price_strip.png
#   04_vlm_feed.png  05_vlm_output.png     06_report.md
python scripts/presentation_run.py --date 2026-09-16 --vlm-backend paddleocr_vl --out-dir "C:\Users\cecilia\Downloads\Apix output"

# Multi-airline OCR+VLM extraction over the 28-day horizon, DB-persisted
python scripts/demo_ocr_vlm_pipeline.py --days 7 --vlm-every 7
```

Timing notes (verified on this machine): OCR ≈ 10.5 s/card strip, local
PaddleOCR-VL ≈ 106 s/inference after weights are cached under
`~\.paddlex\official_models`. Keep at least one image-based slide so the
audience sees the genuine neural extraction (tokens → fare cards → VLM fields).

## ⏱️ Presentation Timeline (Total: 6 Minutes)

### 0:00 – 0:45 | The Real-World Problem
- **Narrative:** "Respected judges, official CPI captures airfare inflation through retrospective monthly surveys on fixed sample dates. However, modern airline revenue management operates on dynamic booking horizons and ticket families. A sudden surge in flexi-fare availability or last-minute purchases can artificially distort inflation figures. We present the **India Airfare Price Observatory (APIX-2.0)**: a high-frequency, unpooled statistical index built with explicit fare-mix protection."
- **Screen:** National Overview (`http://localhost:3000/`)

### 0:45 – 1:30 | The Confounding Defense (Lowest-Economy Estimator)
- **Narrative:** "Notice our Hero Metric: the **Headline Index is anchored strictly at T+15** (two weeks out). We never average T+1 and T+45 prices together. Crucially, we defend against fare-mix confounding: if airlines release hundreds of expensive Flexi Economy seats with free cancellations, naive averages spike by +20%, falsely signaling inflation. Our estimator extracts strictly the lowest available basic economy fare per carrier before computing cross-carrier medians. Ticket-mix shifts have **zero mathematical impact** on our index."
- **Screen:** Route Detail (`http://localhost:3000/routes/DEL-BOM`) — point out the 5-component fare decomposition and lowest-economy defense.

### 1:30 – 2:30 | Route Basket & DGCA Normalization
- **Narrative:** "Our basket covers 10 representative corridors — 8 high-density metro trunk routes plus 2 critical regional thin corridors (Silchar `DEL-IXS` and Dharamshala `DEL-DHM`). Weights are strictly derived from official DGCA monthly domestic passenger traffic and normalized to an exact 1.000000. Metro trunks reflect 89% of volume; regional corridors protect remote connectivity visibility."
- **Screen:** Route Matrix (`http://localhost:3000/routes`)

### 2:30 – 3:30 | The "WOW" Lead-Time Elasticity Curve
- **Narrative:** "Here is our signature feature: **Lead-Time Elasticity**. By tracking unpooled booking horizons across $T+45, T+30, T+15, T+7$, and $T+1$, we reveal how carrier yield management escalates prices. As you can see, the **Dynamic Surge Multiplier reaches 2.45x** between 45 days and 24 hours before takeoff. Economists and policymakers can now monitor dynamic pricing pressure in real time."
- **Screen:** Lead-Time WOW (`http://localhost:3000/lead-time`)

### 3:30 – 4:30 | MoSPI Benchmark Directional Co-Movement
- **Narrative:** "Rather than claiming artificial identical levels with official retrospective surveys, we reframe benchmark comparison honestly as **Directional Co-Movement Analysis**. On frequency-matched monthly series, our prototype achieves **100% Directional Sign Concordance** and a Pearson correlation of **r = 0.997** ($p < 0.001$). We include our prominent methodological disclosure explaining the structural differences between forward search quotes and retrospective survey points."
- **Screen:** Benchmark Validation (`http://localhost:3000/validation`)

### 4:30 – 5:15 | ATF (Jet Fuel) Macro Context & Quality Gate
- **Narrative:** "We provide real-time metropolitan ATF fuel context (~38% airline operating cost share). We explicitly include an econometric non-causal disclosure: 12–18 month fuel hedges and dynamic yield management mean spot fuel swings do not cause 1-to-1 immediate daily fare changes. Furthermore, our Section 62 Data Quality Gate audits every quote with SHA-256 cryptographic payload integrity. And in v2.2 we turned that ATF rig over to a *policy layer*: the same API now classifies today's elevation as **Transient vs Structural** (`/analytics/policy-signal`), so an MPC analyst gets a one-line verdict — structural, multi-carrier, ATF +3.8% co-movement — not a spreadsheet."
- **Screen:** Fuel Context (`http://localhost:3000/fuel-context`) & Data Quality (`http://localhost:3000/quality`) & Governance endpoints (`/docs` → "Governance & Policy Intelligence").

### 5:15 – 6:00 | Developer API, Governance Intelligence & Researcher Bulk Exports
- **Narrative:** "Finally, everything is open and programmatic — and this build adds a full governance intelligence vertical: **HHI carrier concentration** for CCI (avg 2259.9; two UDAN routes HIGH at >3300; r=0.888 with fares), **Billion-Prices lead-lag** vs MoSPI CPI for early-warning, **explainable anomaly alerts** with a cause attributed to every event, **intraday best-time-to-book**, and a **UDAN affordability monitor** flagging both subsidized routes at 2.3× the ₹2,500 target. Institutional researchers can download full daily index series in RFC 4180 CSV or JSON, protected by sliding-window rate limiting. Production-hardened and policy-ready."
- **Screen:** Swagger Docs (`http://localhost:8000/docs`) → "Governance & Policy Intelligence" tag, CSV export download.
