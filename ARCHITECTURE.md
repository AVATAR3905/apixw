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
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                           STATISTICAL COMPUTATION ENGINE                          |
|  - Lowest-Economy Estimator (packages/statistics/estimators.py)                   |
|  - DGCA Passenger Weight Engine (packages/statistics/weights.py)                  |
|  - Daily Laspeyres Index Engine (services/index_engine/calculator_service.py)     |
|  - Temporal Aggregations: Weekly & Monthly (temporal_aggregations.py)             |
|  - MoSPI Directional Co-Movement Matcher (benchmark_matcher.py)                   |
|  - ATF Jet Fuel Macro Context Engine (fuel_context.py)                            |
|  - Anomaly/Surge Detection (packages/statistics/volatility.py, drift_detector.py) |
|  - Forecast Ensemble (services/ml/): TimesFM 2.5 50% + LightGBM/Conformal 35% +   |
|    Statistical STL+ARIMA 15% (services/ml/forecast_service/)                      |
|  - Forecast Backtesting (forecast_snapshots -> /forecast/accuracy vs realized)   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                         DATA QUALITY GATE (PRD SEC 62)                            |
|  Cabin class filter (Economy Y), Price range bounds, Route matching, Deduplication|
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                         INGESTION & COLLECTION WORKFLOW                           |
|  - APScheduler 4x Daily Snapshot Scheduler: 06:00 / 12:00 / 18:00 / 23:00 IST     |
|    (each snapshot triggers the 10-route x 5-horizon collection cycle)             |
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
|  17 Normalized Tables: routes, airlines, fare_observations, index_values,         |
|  route_volatility_records, carrier_indices, validation_results, forecast_        |
|  snapshots (persisted forecasts for accuracy backtesting), etc.                  |
+-----------------------------------------------------------------------------------+
```

---

## 1a. REST API Surface (4 Routers)

| Router | Prefix | Endpoints |
|---|---|---|
| `apps/api/routers/api_v1.py` | `/api/v1` | index, index/timeseries, index/monthly, forecast, forecast/all, forecast/history-and-forecast, forecast/accuracy (backtest vs realized), weights, routes, routes/{route_code}, lead-time, validation, data-quality, validation/cross-feed, live/collect, collection/trigger-cycle, source-health, fuel-context, methodology, analytics/carrier-inflation{/timeseries}, analytics/volatility{/{route_code}} |
| `apps/api/routers/exports.py` | `/api/v1/export` | daily-index.csv, daily-index.json, basket-weights.csv, route-observations.csv |
| `apps/api/routers/ai_router.py` | `/api/v1/ai` | pre-made-prompts, query (OpenRouter econometric copilot) |
| `apps/api/routers/ota_router.py` | `/api/v1/ota` | common-flights, dispersion-ranking, sources-status (Multi-OTA comparison) |

---

## 2. Ingestion & Collection Layer
- **Source Registry:** Implements a strict permission state machine (`DISCOVERED` $\rightarrow$ `REVIEW_REQUIRED` $\rightarrow$ `APPROVED` $\rightarrow$ `ACTIVE`). Unapproved sources cannot be scheduled.
- **Circuit Breaker:** Tracks consecutive errors per source. Trips from `CLOSED` to `OPEN` after 5 failures, protecting upstream airline servers and system reliability.
- **Payload Immutability:** Raw API/HTML responses are saved with SHA-256 hashes in `data/raw/` before parsing. Tamper detection guarantees scientific reproducibility.

---

## 3. Statistical Calculation Pipeline
1. **Raw Collection:** Collects lowest quotes across 5 horizons ($T+1, T+7, T+15, T+30, T+45$).
2. **Quality Verification:** Rule-based filtering (PRD Sec 62) drops invalid fares, anomalies, and duplicates.
3. **Representative Price:** For each route, carrier, and date, the lowest economy fare is selected. The cross-carrier median represents the route price $P_{j,t,15}$.
4. **DGCA Route Weighting:** Aggregates bidirectional passenger traffic across 10 corridors, strictly normalized so $\sum w_j = 1.000000$.
5. **Headline Index Calculation:** Computed using the Modified Laspeyres formulation anchored at $T+15$.
6. **Benchmark Validation:** Frequency-matched monthly aggregation evaluated against official MoSPI CPI Airfare series.
7. **Forecast & Anomaly Extensions:** Ensemble forecast engine (TimesFM 2.5 + LightGBM conformal + STL/ARIMA) produces 28-day (past 28d observed + future 28d) projections with P10/P50/P90 confidence bands; volatility engine flags corridor surge alerts (`CALM` / `MODERATE` / `HIGH_VOLATILITY` / `SURGE_ALERT`).
