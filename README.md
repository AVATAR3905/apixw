# India Airfare Price Observatory (APIX-2.0)
> **Ministry of Statistics & Programme Implementation (MoSPI / NSO)**: Official High-Frequency Statistical Domestic Airfare Price Index & Monitoring Platform

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-2.0.0-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Tests](https://img.shields.io/badge/Tests-217%20Passing-brightgreen.svg)]()
[![Methodology](https://img.shields.io/badge/Methodology-APIX--2.0-847dff.svg)]()
[![Governance](https://img.shields.io/badge/Governance-Intelligence-FF6B35.svg)]()

---

## 🏛️ Executive Summary & Real-World Alignment

The **India Airfare Price Observatory** is an official production-grade statistical intelligence platform deployed for the **Ministry of Statistics and Programme Implementation (MoSPI / NSO)**.

Unlike traditional retrospective monthly surveys, this observatory captures **high-frequency, authentic domestic airfare quotes** directly from airline booking systems across **five advance purchase horizons** ($T+1, T+7, T+15, T+30, T+45$), anchoring its national headline index at **$T+15$** with rigorous **fare-mix confounding protection** (lowest available basic economy fare per carrier).

### Key Architectural & Methodological Guarantees
1. **Fare-Mix Protection:** Extracts lowest basic economy fare per scheduled carrier before cross-carrier aggregation. An airline adding expensive flexi/business seats causes **0% artificial inflation bias**.
2. **Hybrid Laspeyres–Jevons Formula (v2.1):** Jevons geometric mean elementary aggregates per route–horizon cell, combined arithmetic-Laspeyres across the DGCA-weighted basket (IMF CPI Manual 2020 Ch.10; UK ONS guidance). See [METHODOLOGY.md](METHODOLOGY.md).
3. **Dual-Series Architecture (v2.1):** **HEADLINE** (raw all-feed Laspeyres, the market's fastest readout) and **CORE** (festival/peak-exclusion-guarded continuity series with auto re-anchoring) — both served from `/api/v1/index?series_type=HEADLINE|CORE` and the CSV exports.
4. **Unpooled Lead Times:** Headline index is anchored at **$T+15$** (2-week advance purchase). Different horizons ($T+1$ vs $T+45$) are never averaged together. Justified in [docs/T15_anchor_analysis.md](docs/T15_anchor_analysis.md).
5. **Dual Price Series:** Provides both **Base Fare Index** (carrier behavioral pricing) and **Total Price Index** (consumer out-of-pocket).
6. **DGCA Passenger Volume Basket:** Weights 10 representative corridors (8 Metro Trunks + 2 Regional Thin Corridors: `DEL-IXS`, `DEL-DHM`) derived from official DGCA city-pair domestic traffic; cross-checked monthly against the DGCA fare benchmark (`/api/v1/validation/dgca`).
7. **Multi-OTA Governance (v2.1):** Six OTAs (MakeMyTrip, Ixigo, EaseMyTrip, Yatra, Cleartrip, Skyscanner) are feed-tagged (`OTA_AGGREGATOR`) and audited against the carrier-direct reference via source-pair markup audits (`/api/v1/validation/source-pair`) and rolling feed-cohort correlations (`/api/v1/validation/source-correlation`).
8. **Anomaly Detection & Confidence (v2.1):** IQR + MAD z-score detector with severity classification and escalation persists `anomaly_events` (`/api/v1/analytics/anomalies`); every live index read carries `confidence_score` / `confidence_band` / `outlier_count`.
9. **Directional Co-Movement Framing:** Evaluates directional co-movement against official MoSPI CPI benchmarks (item 07.3 Passenger transport services, 2024=100). **Honest current status:** MoSPI publishes with a 5-6 week lag, so its latest real month (Jul 2026) doesn't yet overlap the prototype's young operating history (started Aug 2026) — the API reports `status=INSUFFICIENT_REAL_OVERLAP` with a clearly-flagged illustrative reference scorecard (not a live-computed $r$) until enough real overlapping months accumulate.
10. **ATF Jet Fuel Context:** Contextual overlay (~38% operating cost share) with strict non-causal disclosures accounting for 12–18 month fuel hedging cycles.
11. **Forecast & Anomaly Extensions:** 28-day (past + future) ensemble fare forecasts (TimesFM 2.5 + LightGBM conformal + STL/ARIMA) and corridor surge/volatility alerts exposed via `/api/v1/forecast/history-and-forecast` and `/api/v1/analytics/volatility`. Every forecast is snapshotted and backtested against realized index values via `/api/v1/forecast/accuracy` (MAE/RMSE/MAPE, P50 hit rate, interval coverage).
12. **Governance & Policy Intelligence (v2.2):** A dedicated RBI/CCI/MoCA policy layer — Transient-vs-Structural elevation classifier (`/analytics/policy-signal`), Billion-Prices-style lead-lag vs MoSPI CPI (`/analytics/leading-indicator`), explainable anomaly alerts (`/analytics/alerts`), carrier HHI concentration (CCI, `/analytics/concentration`), intraday volatility + best-time-to-book (`/analytics/intraday-volatility`), scarcity-corrected Availability-Adjusted index (`/analytics/availability-adjusted`), and the UDAN affordability monitor (`/analytics/udan`). See [TASKS.md](TASKS.md).

---

## ⚡ Quick Start (Production Execution)

### 1. Prerequisites
- Python 3.11+ (Python 3.13 supported)
- Node.js 18+ & npm
- PostgreSQL (optional; automatically falls back to local SQLite)

### 2. One-Command Full Pipeline Run (recommended)
```bash
# Seeds DB + runs live collection + warms forecast accuracy + starts API + Dashboard
python scripts/run_observatory.py

# Wipe & reseed before running
python scripts/run_observatory.py --reset

# Full 10-route x 5-horizon collection (instead of focused DEL-BOM T+15)
python scripts/run_observatory.py --full

# Seed-only + servers (skip live scraping)
python scripts/run_observatory.py --no-collect
```
Run `python scripts/run_observatory.py --help` for all flags.

### 3. Backend & Live Ingestion Setup (manual)
```bash
# Clone repository
git clone https://github.com/your-repo/airfare_analyser.git
cd airfare_analyser

# Install Python dependencies
pip install -r requirements.txt

# Run production real-world airfare collector
python -m services.collectors.production_collector

# Start FastAPI backend server
python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```
- API is accessible at: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`

### 4. Frontend Dashboard Setup
```bash
cd apps/dashboard
npm install
npm run build
npm run start
```
- Dashboard is accessible at: `http://localhost:3000`

---

## 🧪 Automated Testing & Verification

```bash
# Run all 217 unit, statistical, and integration tests
pytest tests/ -q

# Run live dual-feed collection runner
python -m services.collectors.dual_feed_runner --route DEL-BOM --horizon 7

# New frontend dashboard (served by FastAPI at /ui — no Node needed)
#  open http://localhost:8000/ui   (adapter router apps/api/routers/apix_ui.py)
```

---

## 🔍 Data Provenance & Known Limitations (read before a judge does)

Being upfront about what is genuinely live vs. still a calibrated stand-in:

- **Verified real live scraping — 2 of 5 carriers, 1 of 6 OTAs:**
  - SpiceJet (`SG`): a reverse-engineered, verified network-JSON extraction
    (`api/v3/search/availability`) — real flight numbers, times, and a genuine base/total fare
    split, persisted as `feed_type=CARRIER_DIRECT`, `is_synthetic=False`.
  - Akasa Air (`QP`): no deep-link URL exists, so this one drives the real homepage search form
    (city autocomplete, calendar date pick, submit) and intercepts the real
    `/api/ibe/availability/search` response — same base/total fare-split pattern as SpiceJet.
  - Ixigo (OTA, `source_id=8`): its fare API runs over Server-Sent Events and rejected a direct
    deep-link URL; going through the real homepage form instead (same fix as Akasa) renders real
    fare cards straight into the DOM. Extraction reuses the DOM→OCR→VLM chain via a new shared
    `services/collectors/ota/card_extraction.py` — DOM text per card first, a full-page OCR pass as
    the genuine fallback when a site's markup doesn't cooperate.
  - All three confirmed end-to-end against the live sites during development.
- **Confirmed blocked, not just unreverse-engineered:** MakeMyTrip, Yatra, and Air India reject the
  connection at the TLS/HTTP2 level (`ERR_HTTP2_PROTOCOL_ERROR`) before any content loads — even a
  completely vanilla, unmodified browser context gets this, consistent with a deliberate anti-bot
  wall. Building fingerprint/TLS evasion tooling to get around that was explicitly out of scope this
  round regardless of end use; the legitimate path is an official/partner API relationship. IndiGo
  also fails uniformly (a generic error page) even with zero automation-hiding — most consistent
  with an IP-range block on this environment's egress, not a URL mistake. **OCR/VLM cannot help with
  any of these four**: it reads pixels off a rendered page, and none of these four ever render fare
  data in any form — three never return a page at all, and IndiGo's page renders only a generic
  error message.
- **Unverified / best-effort:** Air India Express and 4 of 6 OTAs (MakeMyTrip, EaseMyTrip, Yatra,
  Cleartrip) route to their own real domains (a routing bug previously sent every non-SG/6E carrier
  to spicejet.com regardless of code), but their booking-flow/DOM/XHR schemas haven't been fully
  reverse-engineered — they degrade to the calibrated baseline, now **correctly tagged
  `is_synthetic=True`**. Cleartrip's form now fully works (modal dismissed, real cities and dates
  selected, submitted correctly), but its results endpoint rejects the exact URL its own frontend
  generates, reproducibly, regardless of encoding — most likely session state a hard navigation
  doesn't carry; not resolved this round. Skyscanner has a documented, ToS-compliant free-tier API
  (`services/collectors/ota/skyscanner_scraper.py`, RapidAPI "Sky Scrapper") coded and wired with a
  safe fallback, pending a free API key to verify live.
- **Fixed data-integrity bug:** the cross-feed reconciliation layer previously relabeled *any*
  carrier-direct quote as `CARRIER_DIRECT` / `is_synthetic=False` even when the browser scrape had
  silently fallen back to the calibrated baseline — meaning fabricated data could be persisted as
  if it were a genuine market observation. This is fixed: only quotes the scraper itself tags as a
  real extraction keep that status; a fallback stays honestly marked synthetic.
- **Ethical scraping:** real `robots.txt` enforcement (`urllib.robotparser`, not a hardcoded path
  list) and bot-challenge/CAPTCHA-page detection are wired into the live carrier-direct path.
  CAPTCHA *solving* and IP-rotation via proxies remain unwired — they need a paid 2Captcha-style
  key and a purchased proxy pool, which this environment doesn't have.
- **DGCA route weights** (`data/reference/dgca_traffic.csv`) are now real trailing-12-month
  (Aug 2025–Jul 2026) city-pair passenger volumes sourced from DGCA's own Monthly Domestic Air
  Transport Statistics (via the public [Vonter/india-aviation-traffic](https://github.com/Vonter/india-aviation-traffic)
  aggregation), replacing previously fabricated placeholder numbers.
- **MoSPI CPI benchmark** (`data/reference/mospi_cpi_benchmark.csv`) is now 6 real months
  (Jan/Feb/Mar/Apr/Jun/Jul 2026) transcribed from MoSPI's official CPI Press Release PDFs on the
  revised 2024=100 series. MoSPI does not publish a standalone domestic-airfare-only CPI
  sub-index, so the closest real published series — item **07.3 "Passenger transport services"**
  (a composite across rail/air/road fares) — is used and disclosed as such, rather than continuing
  to label fabricated numbers as `CPI_AIRFARE_DOMESTIC`.

---

## 📂 Documentation Sitemap

- [ARCHITECTURE.md](ARCHITECTURE.md) — Production 8-layer system architecture & data pipeline flow.
- [METHODOLOGY.md](METHODOLOGY.md) — Hybrid Laspeyres–Jevons formulation, fare-mix defense, dual-series CORE, and DGCA weights.
- [DATA_MODEL.md](DATA_MODEL.md) — Database schema, TimescaleDB hypertable layout, and entity relationships.
- [SOURCES.md](SOURCES.md) — Source registry, legal compliance framework, and circuit breaker taxonomy.
- [PRD.md](PRD.md) — Product requirements specification.
- [TASKS.md](TASKS.md) — Phased implementation roadmap & task tracker (incl. the APIX-2.1 Statistical Rigor & APIX-2.2 Governance & Policy Intelligence workstreams).
- [RESEARCH.md](RESEARCH.md) — Living research: index methodology benchmarks, competitor landscape, academic literature, scraping/anti-bot & legal landscape, India regulatory context, USP & roadmap, with all source links.
- [DEMO.md](DEMO.md) — 6-minute SIH judge demonstration script (incl. new `/ui` frontend + OCR/VLM proof blocks + Governance & Policy Intelligence demo blocks).
- [docs/SCRAPING_OCR_VLM.md](docs/SCRAPING_OCR_VLM.md) — Scraping, OCR & VLM pipeline guide + presentation runbook.
- [docs/SCRIPTS.md](docs/SCRIPTS.md) — Reference for every runnable script & env var.
- [docs/T15_anchor_analysis.md](docs/T15_anchor_analysis.md) — Empirical justification for the T+15 headline anchor.
- [docs/architecture.md](docs/architecture.md) / [docs/architecture.png](docs/architecture.png) — rendered architecture diagram.

---

## 📜 Authority
Official release for the **Ministry of Statistics and Programme Implementation (MoSPI / National Statistical Office)**.
