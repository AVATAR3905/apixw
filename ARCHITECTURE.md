# Architecture & System Design (APIX-2.0)

> Technical reference architecture for the India Airfare Price Observatory (MoSPI / NSO).

---

## 1. High-Level Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                            PRESENTATION & CONSUMPTION                             |
|  Next.js 14 Observatory Dashboard             FastAPI Core & Export REST Endpoints|
|  (Origin Dark Aesthetic: 13 Views / 17 Routes) (/api/v1/index, /forecast, /export)|
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        ACCESS CONTROL & RATE LIMITING                             |
|  Sliding Window IP Limiter (120 req/min API, 20 req/min Export endpoints)         |
|  X-RateLimit-* headers; 429 + Retry-After; exempts /, /health, /docs*, /redoc,   |
|  /openapi.json and /ui* viewer paths                                              |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                           STATISTICAL COMPUTATION ENGINE                          |
|  - Lowest-Economy Estimator (packages/statistics/estimators.py)                   |
|  - ENSEMBLE feed-quality-weighted median estimator (same module, weight map:      |
|    CARRIER_DIRECT 1.0 / RPC 0.9 / OTA 0.7 / SYNTHETIC 0.3)                        |
|  - DGCA Passenger Weight Engine (packages/statistics/weights.py)                  |
|  - Daily Hybrid Laspeyres-Jevons Index (services/index_engine/calculator_service) |
|    + Dual-Series: HEADLINE (all travel dates) vs CORE (festival-guarded,          |
|      re-anchoring _find_core_anchor, continuity-gated)                            |
|  - Temporal Aggregations: Weekly & Monthly (temporal_aggregations.py)             |
|  - MoSPI Directional Co-Movement Matcher (benchmark_matcher.py)                   |
|  - DGCA Monthly Benchmark Comparator (services/validation/dgca_benchmark_comp...) |
|  - ATF Jet Fuel Macro Context Engine (fuel_context.py)                            |
|  - OTA Source-Pair Markup Auditor (source_pair_auditor.py)                        |
|  - Feed-Cohort Correlation Tracker (source_correlation.py, Pearson r per route)   |
|  - IQR/MAD Anomaly Detector + Escalation (anomaly_detector.py, anomaly_service.py)|
|  - Confidence Scoring (confidence.py: composite quality x feed trust + band)      |
|  - Volatility/Surge + Feed Drift (volatility.py, drift_detector.py)               |
|  - Forecast Ensemble (services/ml/): TimesFM 2.5 50% + LightGBM/Conformal 35% +   |
|    Statistical STL+ARIMA 15% (services/ml/forecast_service/)                      |
|  - Forecast Backtesting (forecast_snapshots -> /forecast/accuracy vs realized)   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                         DATA QUALITY GATE (PRD SEC 62)                            |
|  Cabin class filter (Economy Y), Price range bounds, Route matching, Deduplication|
|  - Per-quote feed tagging (feed_type: CARRIER_DIRECT / RPC_FALLBACK /             |
|    OTA_AGGREGATOR / SYNTHETIC_BASELINE) for OTA quotes from the 6 aggregators     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                         INGESTION & COLLECTION WORKFLOW                           |
|  - GitHub Actions 4x Daily Cycle: 06:00 / 12:00 / 18:00 / 23:00 IST, independent  |
|    of the local machine (.github/workflows/collect.yml); local syncs via pull     |
|    (see Section 2 "Where Collection Actually Runs" below)                         |
|  - Resume-on-crash: skips route/horizons already COMPLETED for the date/source,   |
|    marks orphaned PENDING jobs FAILED and retries them (collection_scheduler.py)  |
|  - Circuit Breakers & Exponential Backoff Retries (circuit_breaker.py)            |
|  - Source Compliance & Permission State-Machine (source_registry.py)              |
|  - SHA-256 Tamper-Evident Raw Payload Storage (payload_store.py)                  |
|  - Carrier-Direct + 6 OTA scrapers + Google Flights RPC (dual_feed_runner.py)     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                             STORAGE & PERSISTENCE                                 |
|  Dual-Engine: PostgreSQL/TimescaleDB with automatic fallback to local SQLite      |
|  21 Normalized Tables: routes, airlines, fare_observations, index_values,         |
|  route_volatility_records, discrepancy_audits (+audit_type/source-pair columns),  |
|  dgca_monthly_fares, validation_results, source_correlations, anomaly_events,     |
|  benchmark_values, atf_prices, atf_tax_rates, carrier_indices, forecast_          |
|  snapshots (persisted forecasts for accuracy backtesting), etc.                  |
+-----------------------------------------------------------------------------------+
```

---

## 1a. REST API Surface (5 Routers)

| Router | Prefix | Endpoints |
|---|---|---|
| `apps/api/routers/api_v1.py` | `/api/v1` | index (HEADLINE\|CORE via `series_type`), index/timeseries, index/dual-series, index/monthly, forecast, forecast/all, forecast/history-and-forecast, forecast/accuracy (backtest vs realized), weights, routes, routes/{route_code}, lead-time, validation, validation/dgca, data-quality, validation/cross-feed, validation/source-pair, ota/source-pair-audit, validation/source-correlation, validation/compute-source-correlation, analytics/anomalies, analytics/run-anomaly-detection, live/collect, collection/trigger-cycle, source-health, fuel-context, methodology, analytics/carrier-inflation{/timeseries}, analytics/volatility{/{route_code}}, analytics/market-briefing, **Governance & Policy Intelligence (v2.2)**: analytics/policy-signal, analytics/leading-indicator, analytics/alerts, analytics/concentration{/{route_code}}, analytics/intraday-volatility{/{route_code}}, analytics/availability-adjusted, analytics/udan |
| `apps/api/routers/apix_ui.py` | `/` root level | **New frontend bridge**: `/routes`, `/index`, `/index/headline`, `/fares/cleaned`, `/analytics/heatmap`, `/analytics/elasticity`, `/backtest`, `/ingest/dummy` — adapter router that serves the new APIx UI (`apps/api/static_ui/index.html` mounted at `/ui`) directly from the local SQLite observatory DB |
| `apps/api/routers/exports.py` | `/api/v1/export` | daily-index.csv (dual-series header `date,index_series,series_type,...`), daily-index.json, basket-weights.csv, route-observations.csv |
| `apps/api/routers/ai_router.py` | `/api/v1/ai` | pre-made-prompts, query (OpenRouter econometric copilot) |
| `apps/api/routers/ota_router.py` | `/api/v1/ota` | common-flights, dispersion-ranking, sources-status (Multi-OTA comparison) |

> **v2.2 — Governance & Policy Intelligence** endpoints are implemented in
> `packages/statistics/` (`policy_signal.py`, `leading_indicator.py`, `anomaly_explainer.py`,
> `concentration.py`, `intraday_volatility.py`, `availability_index.py`, `udan_monitor.py`)
> and wired into `api_v1.py` under the OpenAPI tag **"Governance & Policy Intelligence"**.

---

## 2. Ingestion & Collection Layer

### 2.0 Source Map — Every Candidate Site, Current Status, and Why

Every source in scope for this project falls into exactly one adapter interface (below),
and every source has a definitive, tested status — not "we haven't tried" but "we tried,
and here is exactly what happened":

| Source | Interface | Status | Why |
|---|---|---|---|
| **SpiceJet (SG)** | `CarrierDirectScraper` | ✅ Real (`NETWORK_API`) | Real `api/v3/search/availability` JSON intercept; genuine base/tax/fee split |
| **Akasa Air (QP)** | `CarrierDirectScraper` | ✅ Real (`DOM_BROWSER`), locally | Homepage-form flow + `/api/ibe/availability/search` intercept. **Blocked on GitHub Actions specifically** — Akasa's server won't serve `robots.txt` to GitHub's datacenter IP range, and `RobotsTxtChecker` correctly fails safe rather than scrape unverified |
| **Google Flights RPC** | `RealFlightRPCConnector` | ✅ Real | Via the `fast_flights` library — a documented client for Google Flights' own public search backend, not scraping google.com's HTML. Works from both local and GitHub IPs |
| **Ixigo** | `BaseOTAScraper` (`IxigoScraper`) | ✅ Real, all 10 routes locally; ⚠️ unreliable from GitHub Actions | Real homepage-form + DOM/OCR card extraction. GitHub-runner failures are UI-interaction timeouts (`Locator.click`), not a clean block signature — not yet root-caused |
| **EaseMyTrip** | `BaseOTAScraper` (`EaseMyTripScraper`) | ✅ Real, all 10 routes locally; ⚠️ unreliable from GitHub Actions | Same pattern as Ixigo |
| **Skyscanner (RapidAPI "Sky Scrapper")** | `BaseOTAScraper` (`SkyscannerScraper`) | ✅ Real when quota available | Licensed RapidAPI wrapper around Skyscanner's backend, not a scrape of skyscanner.co.in. Free tier is 100 req/month; currently exhausted |
| **Amadeus** | `PARTNER_API` (`AmadeusScraper`) | ⚙️ Wired, no credentials | Self-service developer portal was decommissioned 2026-07-17; only the Enterprise (paid, commercial-agreement) API remains. Adapter raises `AmadeusCredentialsMissing` and degrades to calibrated baseline until real credentials are supplied |
| **Sabre** | `PARTNER_API` (`SabreScraper`) | ⚙️ Wired, no credentials | Free self-service test/cert environment exists (`developer.sabre.com`) but requires manual account registration; adapter is built and ready the moment `SABRE_USERNAME`/`SABRE_PASSWORD` land in `.env` |
| **IndiGo (6E)** | `CarrierDirectScraper` | 🚫 Blocked, confirmed | IP-reputation block on datacenter/cloud egress — even a stealth-free vanilla Playwright context gets the same generic error page. Removed from the active collection loop entirely (it was also causing multi-minute hangs with no bounded timeout) |
| **MakeMyTrip** | `BaseOTAScraper` (`MakeMyTripScraper`) | 🚫 Blocked, confirmed | TLS/HTTP2-level block (`ERR_HTTP2_PROTOCOL_ERROR`) before any content loads — connection refused, no page to extract from by any method (DOM, OCR, or VLM) |
| **Yatra** | `BaseOTAScraper` (`YatraScraper`) | 🚫 Blocked, confirmed | Same TLS/HTTP2-level block as MakeMyTrip |
| **Air India** | `CarrierDirectScraper` | 🚫 Blocked, confirmed | Same TLS/HTTP2-level block |
| **Air India Express (IX)** | `CarrierDirectScraper` | 🚫 Rate-limited, confirmed | Site's own "search after some time" throttle after repeated automated attempts — respected, not pushed through |
| **Cleartrip** | `BaseOTAScraper` (`CleartripScraper`) | 🚫 Blocked, confirmed | Not a network-level block — the full form flow (origin, destination, calendar) works, but the results page rejects Cleartrip's own generated URL ("wrong url") reproducibly. Most likely needs in-app AJAX session state a hard navigation doesn't carry; not a guessable fix |

**Every entry above with a 🚫 was individually investigated, not assumed.** The
`ethical_scraping.py` module gates every attempt through a real `urllib.robotparser`
check and a bot-challenge-page detector (so a block page is never misread as "zero
fares"), and building tooling to route around any of these — IP rotation, TLS/fingerprint
spoofing, CAPTCHA solving — remains out of scope regardless of how the request is framed.
That boundary doesn't change what's genuinely achievable here: five real sources work
today, two more (Amadeus/Sabre) are one credential away from working, and the six
`🚫` rows are the actual site owner's decision, not a gap in this system's design.

### 2.1 Unified Adapter Pattern

Every source implements one of three consistent interfaces, so adding a new *legitimate*
source (a new OTA, a licensed partner feed) is a bounded, well-defined extension:

```
BaseOTAScraper (abstract)
  .scrape_corridor(origin, dest, travel_date, advance_days, db) -> List[quote]
  ._execute_scrape(...)          # subclass: real network/DOM logic
  ._generate_calibrated_quotes() # subclass: deterministic offline fallback
  -- circuit breaker + calibrated-fallback degrade built into the base class,
     never duplicated per-scraper

CarrierDirectScraper
  .scrape_carrier_corridor(carrier_code, origin, dest, advance_days, db)
  -- pooled browser context -> dedicated launch -> calibrated baseline,
     same three-tier degrade chain for every carrier

PARTNER_API adapters (Amadeus, Sabre)
  .scrape_corridor(...) same signature as BaseOTAScraper
  -- OAuth2 credential fetch -> raise *CredentialsMissing -> calibrated
     fallback; never silently promotes a fallback to "real"
```

Every adapter, regardless of interface, ultimately produces the same normalized quote
shape (`feed_type`, `extraction_method`, `carrier_code`, fare fields) and flows through
the single `RealFareNormalizer.normalize_and_persist_observations` gate, which now
actually runs `QualityEngine.evaluate()` per observation (route validity,
fare-decomposition-sum consistency, plausible-range review) rather than stamping a fixed
score — see TASKS.md v2.7.

### 2.2 Where Collection Actually Runs

```
┌─────────────────────────────┐        commits          ┌──────────────────────┐
│   GitHub Actions             │  updated airfare_       │   GitHub (main)      │
│   (ubuntu-latest, free/      │  observatory.db  ─────► │   source of truth    │
│   unlimited on this public   │  every run               │   for collected data │
│   repo)                      │                          └───────────┬──────────┘
│                               │                                      │
│  06:00 / 12:00 / 18:00 /     │                                      │ git pull
│  23:00 IST cron, or manual   │                                      │ (every 30 min,
│  workflow_dispatch            │                                      │  only when new
└───────────────────────────────┘                                      │  commits exist)
                                                                        ▼
                                                          ┌──────────────────────┐
                                                          │  Local machine        │
                                                          │  "APIx GitHub Sync"   │
                                                          │  task: stops the API  │
                                                          │  server (releases the │
                                                          │  DB file lock), pulls,│
                                                          │  restarts it          │
                                                          └──────────────────────┘
```

Local collection (`scripts/collect_full_real_coverage.py` run directly, or via the
now-**disabled** "APIx Collection Cycle" Task Scheduler entry) remains available as a
fallback/comparison path — it generally gets *better* source coverage than GitHub Actions
runs (Akasa Air works locally, for instance), at the cost of depending on the local
machine staying awake and online. See RESTART.md for the operational runbook and how to
switch back.

- **Source Registry:** Implements a strict permission state machine (`DISCOVERED` $\rightarrow$ `REVIEW_REQUIRED` $\rightarrow$ `APPROVED` $\rightarrow$ `ACTIVE`). Unapproved sources cannot be scheduled.
- **Circuit Breaker:** Tracks consecutive errors per source. Trips from `CLOSED` to `OPEN` after 5 failures, protecting upstream airline servers and system reliability.
- **Payload Immutability:** Raw API/HTML responses are saved with SHA-256 hashes in `data/raw/` before parsing. Tamper detection guarantees scientific reproducibility.
- **Dual-Feed Design:** Every corridor is collected from two independent feeds — airline direct booking portals (priority) and Google Flights RPC (validator/fallback) — and reconciled by `CrossFeedDiscrepancyValidator` before persistence. In v2.1 this is extended to a **multi-OTA design**: six OTA aggregates (`BaseOTAScraper.FEED_TYPE="OTA_AGGREGATOR"`) are ingested alongside the direct feed and feed-tagged at normalize time so `SourcePairAuditor` can price each OTA against the authoritative carrier-direct reference. See [docs/SCRAPING_OCR_VLM.md](docs/SCRAPING_OCR_VLM.md).
- **SCRAPE_MODE gating:** `packages/shared/config.py` switches the whole collector suite between network and deterministic behaviour at runtime:
  - `live` — both feeds hit the network (production/rehearsal);
  - `calibrated` — both feeds use deterministic offline baselines (presentations without network, hermetic tests);
  - `hybrid` — **recommended for demos**: carrier gates serve the fast calibrated baseline while the RPC feed hits real Google Flights, so the parity/markup table is populated with genuine aggregator prices (~3s).

## 2a. Extraction Layer (OCR & VLM)
- **OCR:** `services/extraction/ocr_service.py` wraps PaddleOCR **PP-OCRv6** (lazy import, mtime-keyed inference memo so repeated strip reads cost one real pass). `layout_clusterer.py` groups tokens into per-flight cards by y-band geometry; `adaptive_extractor.py` parses fields (price/route/airline/flight/times/stops/duration) with deterministic regexes.
- **VLM:** `services/extraction/vlm_service.py` — local **PaddleOCR-VL-1.6 (0.9B)** preferred (`~106s`/image, fully offline, weights cached under `~\.paddlex\official_models`) with **OpenRouter** vision as the network fallback.
- **Adaptive chain:** DOM $\rightarrow$ OCR $\rightarrow$ VLM (VLM only escalates for fields OCR couldn't resolve). `AdaptiveExtractor(allow_vlm=False)` pins VLM off in the carrier-scraper OCR fallback so live scraping stays responsive.

---

## 3. Statistical Calculation Pipeline
1. **Raw Collection:** Collects lowest quotes across 5 horizons ($T+1, T+7, T+15, T+30, T+45$) from Carrier Direct, 6 OTAs, and the Google-Flights RPC validator, each quote tagged with its `feed_type`.
2. **Quality Verification:** Rule-based filtering (PRD Sec 62) drops invalid fares, anomalies, and duplicates.
3. **Representative Price:** For each route, carrier, and date, the lowest economy fare is selected. The route cell price is the **Jevons geometric mean** across carriers (see METHODOLOGY.md §1.1); the optional **ENSEMBLE** estimator applies a feed-quality-weighted median. MAD + IQR outlier filters run before aggregation.
4. **DGCA Route Weighting:** Aggregates bidirectional passenger traffic across 10 corridors, strictly normalized so $\sum w_j = 1.000000$.
5. **Headline Index Calculation:** Computed using the Hybrid Laspeyres–Jevons formulation anchored at $T+15$; produced as two series — **HEADLINE** (all travel dates) and **CORE** (festival-guarded continuity series with `_find_core_anchor` re-anchoring).
6. **Benchmark Validation:** Frequency-matched monthly aggregation evaluated against official MoSPI CPI Airfare series (`benchmark_matcher.py`) and against DGCA monthly fare statistics (`dgca_benchmark_comparator.py`, `GET /validation/dgca`).
7. **Data-Quality & Audit Layers (v2.1):**
   - **OTA source-pair markup audits** — `SourcePairAuditor` compares each OTA against the authoritative reference (carrier-direct when present, else cheapest), persists `OTA_SOURCE_PAIR` rows, `GET /validation/source-pair`.
   - **Feed-cohort correlation** — `SourceCorrelationTracker` computes rolling Pearson r between CARRIER_DIRECT and OTA_AGGREGATOR series; `r < 0.7` flags divergence, `GET /validation/source-correlation`.
8. **Anomaly Detection & Alerting (v2.1):** `anomaly_detector.py` scores each index point with IQR fences + MAD z-scores, applies a 2% practical-significance floor, classifies `LOW/MODERATE/SEVERE`, and escalates (SEVERE, or ≥2 consecutive MODERATE). Hits persist as `anomaly_events`; `GET /analytics/anomalies`, `POST /analytics/run-anomaly-detection`.
9. **Confidence Scores (v2.1):** `confidence.py` computes a 0–100 composite (quality × extraction-method trust, + cross-source agreement) mapped to HIGH/MEDIUM/LOW bands; `/api/v1/index` returns `confidence_score`, `confidence_band`, and `outlier_count`.
10. **Forecast & Anomaly Extensions:** Ensemble forecast engine (TimesFM 2.5 + LightGBM conformal + STL/ARIMA) produces 28-day (past 28d observed + future 28d) projections with P10/P50/P90 confidence bands; volatility engine flags corridor surge alerts (`CALM` / `MODERATE` / `HIGH_VOLATILITY` / `SURGE_ALERT`).
