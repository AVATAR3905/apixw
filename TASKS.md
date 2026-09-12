# INDIA AIRFARE PRICE OBSERVATORY
## Phased Implementation Roadmap & Engineering Task Tracker
### *Statistical Rigor & Official Methodology Standards for MoSPI / NSO*

> **Authority:** Ministry of Statistics and Programme Implementation (MoSPI / NSO)  
> **Domain:** Travel & Tourism / High-Frequency Price Statistics  
> **Core Principle:** *"The scraper is replaceable. The measurement methodology is the product."*  
> **Target Delivery:** Production-grade statistical observatory featuring:
> - **Zero Fare-Mix Confounding:** Lowest available economy fare per carrier estimator
> - **Unpooled Lead-Time Architecture:** Standardized **T+15 headline index** + independent sub-indices ($T+1, T+7, T+15, T+30, T+45$)
> - **Dual Index Series:** Base Fare Index (airline pricing behavior) & Total Price Index (consumer out-of-pocket)
> - **DGCA Passenger Volume Weighting:** Metro trunk corridors + regional/thin-route inclusion
> - **Honest Benchmark Alignment:** Directional co-movement analysis with MoSPI CPI airfare component
> - **Macro Context Layer:** Non-causal ATF (jet fuel) cost structure overlay
> - **Dark Observatory UX:** Origin Financial dark gallery design tokens

---

## 🏛️ Methodological Corrections Summary (v2.0)

| Previous Design Flaw | Real-World Critique | Fixed Production Specification |
|---|---|---|
| **Fare-Mix Confounding** | Median across all visible tickets conflates Economy Flexi / Business with inflation | **Lowest Available Economy:** Filters for lowest non-refundable Economy seat per carrier before computing cross-carrier median |
| **Lead-Time Pooling** | Blending T+1 (₹14k panic buy) with T+45 (₹4k advance) produces meaningless prices | **Headline T+15 Anchor:** Primary index anchored at T+15; $T+1, T+7, T+15, T+30, T+45$ tracked as distinct sub-indices |
| **Index Price Basis** | Total fare includes government-mandated taxes/fees unrelated to carrier pricing | **Dual Price Series:** Base Fare Index (carrier behavior) + Total Consumer Price Index (out-of-pocket) |
| **MoSPI CPI "Validation"** | Apples-to-oranges (field collection vs search-date scrape, fixed route vs dynamic) | **Directional Co-movement:** Reframed as directional tracking & co-movement analysis with explicit methodology differences |
| **ATF "Causal" Correlation** | 30 days cannot prove causality; airlines hedge fuel 12–18 months out | **Macro Fuel Overlay:** Explanatory context layer showing fuel price movements & 38% cost-share benchmark without unproven regressions |
| **"30-Day Back-Test" Label** | Synthetic data matching a parametric model is circular validation | **Statistical Pipeline Verification:** Transparently labeled synthetic verification dataset; live collection runs in parallel |
| **Basket Representation** | Pure volume weights ignore thin/regional monopoly route inflation | **Balanced Basket:** 8 high-volume metro corridors + 2 regional/thin routes (e.g. DEL-IXS Silchar, DEL-DHM Dharamshala) |

---

## 📊 Summary of Phases & Execution Flow

```text
Phase 0: Foundation & Environment Setup (Monorepo, Docker, DB, Next.js)
   ↓
Phase 1: Statistical Core & Synthetic Verification Pipeline (Zero Fare-Mix, T+15 Anchor)
   ↓
Phase 2: Source Registry & Acquisition Architecture (Compliance-first, Lineage Hashing)
   ↓
Phase 3: Live / Permitted Fare Collection Engine (5 Horizons, Fare Decomposition)
   ↓
Phase 4: DGCA Passenger Weights & Route Basket (Metro + Regional Corridors)
   ↓
Phase 5: Daily Airfare Index Engine & Aggregations (Headline T+15, Lead-Time Sub-indices)
   ↓
Phase 6: Statistical Observatory Dashboard (Next.js + Origin Financial Design Tokens)
   ↓
Phase 7: MoSPI Benchmark Directional Co-Movement Module (Honest Statistical Scorecard)
   ↓
Phase 8: ATF Jet Fuel Macro Context Vertical (Non-causal Explanatory Layer)
   ↓
Phase 9: Production REST API & Researcher Data Exports (Base & Total Series)
   ↓
Phase 10: System Hardening, E2E Verification & SIH Demo Script Rehearsal
   ↓
Phase 11: Machine Learning & Anomaly Detection Foundations (P2/P3 Future Scope)
```

---

## Phase 0: Foundation & Environment Setup
**Objective:** Establish a clean monorepo, robust database container, dependency configurations, and linting/formatting standards.

- [x] **Task 0.1: Monorepo Architecture Setup**
  - **PRD Ref:** Section 57
  - Initialize directory structure:
    ```text
    airfare_analyser/
    ├── apps/
    │   ├── api/          # FastAPI application
    │   └── dashboard/    # Next.js 14/15 React dashboard
    ├── services/
    │   ├── collectors/   # Scraper/API connectors & payload store
    │   ├── scheduler/    # APScheduler cron jobs
    │   └── index-engine/ # Statistical index calculation
    ├── packages/
    │   ├── schemas/      # Pydantic v2 & TypeScript data models
    │   ├── statistics/   # Core statistical math, estimators, Laspeyres engine
    │   └── shared/       # DB client, logging, configuration
    ├── database/
    │   ├── migrations/   # Alembic migration scripts
    │   └── seeds/        # DGCA weights, route basket, carriers, mock fixtures
    ├── data/
    │   ├── raw/          # Immutable hashed raw response payloads
    │   ├── reference/    # DGCA traffic, MoSPI CPI, ATF price CSVs
    │   └── synthetic/    # Deterministic pipeline verification fixtures
    ├── tests/
    │   ├── unit/
    │   ├── statistical/
    │   ├── integration/
    │   └── e2e/
    ├── docker-compose.yml
    ├── .env.example
    └── Makefile
    ```
  - **Acceptance Criteria:** Directory layout created with standard package markers (`__init__.py`, `pyproject.toml`, `package.json`).

- [x] **Task 0.2: Python Environment & Dependencies**
  - **PRD Ref:** Section 39
  - Configure `pyproject.toml` / `requirements.txt` with:
    - FastAPI, Uvicorn, Pydantic v2
    - SQLAlchemy 2.x, Alembic, psycopg2-binary / asyncpg
    - Polars, Pandas, NumPy, SciPy, statsmodels
    - Playwright, httpx, beautifulsoup4
    - APScheduler, pytest, pytest-asyncio, ruff, black
  - Verify clean installation on Python 3.13.
  - **Acceptance Criteria:** Package installation succeeds without dependency conflicts.

- [x] **Task 0.3: Database Infrastructure (PostgreSQL / TimescaleDB)**
  - **PRD Ref:** Section 39, 40
  - Write `docker-compose.yml` defining:
    - PostgreSQL 16 (TimescaleDB extension enabled)
    - Redis (for caching & job coordination)
    - Health checks and persistent volumes
  - Write `.env.example` with standard development credentials and ports.
  - **Acceptance Criteria:** `docker compose up -d postgres` runs cleanly and accepts connections.

- [x] **Task 0.4: Database Schema Migrations (Alembic) with Corrected Fields**
  - **PRD Ref:** Section 40.1 - 40.13; `real_world_critique.md`
  - Define declarative SQLAlchemy models matching all 13 PRD entities with required statistical refinements:
    - `sources`: `id`, `name`, `type`, `access_method`, `permission_status`, `tos_status`, `robots_status`, `rate_limit`, `enabled`, `last_reviewed_at`.
    - `routes`: `id`, `origin`, `destination`, `origin_airport`, `destination_airport`, `route_code`, `corridor_type` (`METRO_TRUNK`, `REGIONAL_THIN`), `active`.
    - `airlines`: `id`, `code`, `name`, `is_scheduled`, `active`.
    - `fare_observations`: `id`, `source_id`, `route_id`, `airline_id`, `search_timestamp`, `travel_date`, `advance_purchase_days`, `flight_number`, `cabin_class` (`ECONOMY`), `fare_family` (`BASIC`, `FLEXI`), `stops`, `availability_status` (`AVAILABLE`, `SOLD_OUT`, `CANCELLED`), `is_carrier_min_fare` (boolean flag for lowest economy quote), `base_fare`, `fuel_surcharge`, `tax_amount`, `development_fee`, `convenience_fee`, `other_fee`, `total_fare`, `currency`, `is_synthetic`, `quality_score`, `quality_status`, `raw_payload_id`.
    - `raw_payloads`: `id`, `source_id`, `collection_job_id`, `payload_uri`, `payload_hash` (SHA-256), `content_type`, `captured_at`.
    - `route_weights`: `id`, `route_id`, `passenger_volume`, `weight`, `methodology_version`, `effective_from`, `effective_to`.
    - `collection_jobs`: `id`, `route_id`, `source_id`, `search_date`, `travel_date`, `advance_days`, `status`, `attempt_count`, `started_at`, `completed_at`, `error_code`, `error_message`.
    - `index_values`: `id`, `index_series` (`BASE_FARE`, `TOTAL_PRICE`), `index_type` (`HEADLINE_T15`, `SUB_T1`, `SUB_T7`, `SUB_T15`, `SUB_T30`, `SUB_T45`, `ROUTE_LEVEL`), `lead_time_days`, `period_start`, `period_end`, `route_id`, `index_value`, `coverage_rate`, `methodology_version`, `weight_version`, `calculated_at`.
    - `benchmark_values`: `id`, `period`, `indicator`, `value`, `source`, `source_version`.
    - `validation_results`: `id`, `period_start`, `period_end`, `series_evaluated`, `correlation`, `mae`, `rmse`, `directional_accuracy`, `methodology_notes`, `created_at`.
    - `atf_prices`: `id`, `location`, `date`, `price_per_kl`, `source`.
    - `atf_tax_rates`: `id`, `effective_from`, `effective_to`, `tax_type`, `rate`, `source`.
    - `methodology_versions`: `id`, `version`, `name`, `base_period`, `anchor_lead_time` (`T+15`), `price_estimator`, `missing_data_method`, `weight_method`, `formula`, `effective_from`, `notes`.
  - Generate and run baseline Alembic migration.
  - **Acceptance Criteria:** `alembic upgrade head` executes and creates all 13 tables with constraints.

- [x] **Task 0.5: Next.js Frontend Initialization & Design Tokens Integration**
  - **PRD Ref:** Section 39, 66; `Design rules/`
  - Initialize Next.js app in `apps/dashboard` (React 19 / TypeScript / Tailwind CSS / Lucide icons).
  - Integrate tokens from `Design rules/tokens (2).json`, `variables (2).css`, and `theme (2).css`:
    - Obsidian (`#0f1011`), Abyss (`#090a0b`), Graphite (`#2e2e2e`), Steel (`#3f4041`)
    - Iris Gleam (`#847dff`), Cyan Signal (`#00b3dd`), Orchid Bloom (`#dd90d8`)
    - Typography rules: Lyon Display / Serif headings, Suisse Int'l / Sans body, Roboto Mono uppercase tickers.
  - **Acceptance Criteria:** Frontend boots dark-theme layout with design tokens configured.

- [x] **Task 0.6: Orchestration, Makefile & Linting Setup**
  - **PRD Ref:** Section 56, 71
  - Create `Makefile` with targets: `make dev`, `make test`, `make lint`, `make migrate`, `make seed`.
  - Configure `ruff` and `prettier`.
  - **Acceptance Criteria:** `make lint` runs without errors.

---

## Phase 1: Statistical Core & Synthetic Verification Pipeline
**Objective:** Deliver a mathematically verified, deterministic index pipeline implementing the lowest-economy estimator and unpooled lead-time architecture before scraping.

- [x] **Task 1.1: Balanced Route Basket & Airlines Seeding**
  - **PRD Ref:** Section 22; `real_world_critique.md` Problem 2
  - Define 10-route basket balancing major high-density metro corridors with regional connectivity:
    - **Metro Trunk Corridors (High Volume):**
      1. `DEL-BOM` (Delhi — Mumbai)
      2. `DEL-BLR` (Delhi — Bengaluru)
      3. `BOM-BLR` (Mumbai — Bengaluru)
      4. `DEL-CCU` (Delhi — Kolkata)
      5. `DEL-HYD` (Delhi — Hyderabad)
      6. `BOM-MAA` (Mumbai — Chennai)
      7. `BLR-HYD` (Bengaluru — Hyderabad)
      8. `DEL-MAA` (Delhi — Chennai)
    - **Regional / Thin Corridors (Price Vulnerability / Airfare Inequality):**
      9. `DEL-IXS` (Delhi — Silchar, Assam: remote northeastern corridor with limited direct capacity)
      10. `DEL-DHM` (Delhi — Dharamshala / Kangra: regional tourism monopoly corridor)
  - Define domestic scheduled carriers: IndiGo (6E), Air India (AI), SpiceJet (SG), Akasa Air (QP), AI Express (IX).
  - Seed database with routes, corridor types, and carriers.
  - **Acceptance Criteria:** Database returns 10 routes with corridor tags and 5 carriers.

- [x] **Task 1.2: Deterministic Synthetic Pipeline Verification Generator**
  - **PRD Ref:** Section 14, 15, 30, 34; `real_world_critique.md` Problem 5
  - Create `services/synthetic_generator.py`:
    - Generates 30+ days of historical observations across all 10 routes.
    - Simulates 5 distinct lead times: **T+1, T+7, T+15, T+30, T+45**.
    - Realistic yield curve dynamics: steep surge near T+1, moderate T+7, stable T+15, early-bird discounts T+45.
    - Captures multiple fares per flight (Economy Basic vs Economy Flexi).
    - Decomposes mandatory fare elements: `base_fare`, `fuel_surcharge`, `tax_amount` (GST), `development_fee` (UDF), `convenience_fee`.
    - Explicit availability states: `AVAILABLE`, `SOLD_OUT`, `CANCELLED`.
    - Sets `is_synthetic = True` flag on all generated records for audit transparency.
  - **Acceptance Criteria:** Script produces 30 days of deterministic multi-route observations with explicit synthetic provenance.

- [x] **Task 1.3: Fare Normalization & Component Validation**
  - **PRD Ref:** Section 16, 17, 18; `real_world_critique.md` Fix 4
  - Create `packages/statistics/normalizer.py`:
    - Validates fare equation:
      $$\text{Total Fare} \approx \text{Base Fare} + \text{Fuel Surcharge} + \text{Taxes} + \text{UDF} + \text{Convenience Fee} \quad (\pm ₹5\text{ tolerance})$$
    - Sold-out flights handling: Explicitly marks as missing for price estimation ($\text{SOLD\_OUT} \ne ₹0$).
    - Tags lowest available Economy fare per carrier per flight (`is_carrier_min_fare = True`).
  - **Acceptance Criteria:** Tests verify sold-out flights are excluded from price calculations and component sums match totals.

- [x] **Task 1.4: Data Quality & Plausibility Scoring Engine**
  - **PRD Ref:** Section 19, 20, 62
  - Create `packages/statistics/quality.py`:
    - Evaluates: Route validity, Date validity, Plausibility range ($₹1,200 \le \text{Base Fare} \le ₹60,000$), Decomposition match, Duplicate check.
    - Computes composite quality score (0–100):
      - 90–100: `ACCEPT`
      - 70–89: `ACCEPT_WITH_WARNING`
      - 50–69: `REVIEW`
      - 0–49: `REJECT`
  - **Acceptance Criteria:** Unit tests covering all 8 quality test cases in PRD Section 62 pass with 100% accuracy.

- [x] **Task 1.5: Lowest-Economy Representative Price Estimator (Fare-Mix Protected)**
  - **PRD Ref:** Section 21, 24; `real_world_critique.md` Problem 1 & Fix 1
  - Create `packages/statistics/estimators.py`:
    - **Step 1:** For route $j$, date $t$, horizon $h$, filter observations to: `cabin_class == 'ECONOMY'` and `fare_family == 'BASIC'` (lowest non-refundable fare).
    - **Step 2:** For each active carrier $c$, extract the minimum available base fare:
      $$P_{\text{min}}(j, t, h, c) = \min_{f \in \text{flights}(c)} (\text{base\_fare}_{f})$$
    - **Step 3:** Calculate representative price as the median across active carriers:
      $$P_{j,t,h} = \text{Median}_{c} \left( P_{\text{min}}(j, t, h, c) \right)$$
    - Prevents fare-mix distortion (e.g. flexi ticket surges masquerading as inflation).
    - Also computes equivalent representative price for `total_fare` for the consumer out-of-pocket series.
  - **Acceptance Criteria:** Unit test demonstrates that when Economy Flexi tickets enter the observation pool, $P_{j,t,h}$ remains completely unaffected.

- [x] **Task 1.6: Unpooled Modified Laspeyres Airfare Price Index Engine**
  - **PRD Ref:** Section 23, 26, 27, 28; `real_world_critique.md` Problem 3 & Fix 2
  - Create `packages/statistics/index_engine.py`:
    - **Headline Index ($I_t^{\text{Headline}}$):** Anchored exclusively at **T+15**:
      $$I_t^{\text{Headline}} = 100 \sum_{j=1}^{n} w_j \cdot \frac{P_{j,t,T+15}}{P_{j,0,T+15}}$$
    - **Independent Horizon Sub-Indices:** Computes separate series for $T+1, T+7, T+15, T+30, T+45$ without pooling across lead times.
    - **Dual Series Generation:** Generates both `BASE_FARE_INDEX` (carrier pricing behavior) and `TOTAL_PRICE_INDEX` (consumer out-of-pocket).
    - Coverage rate guard: If route coverage $< 80\%$, flags index record with `LOW_COVERAGE`.
  - **Acceptance Criteria:** Calculations produce distinct headline and lead-time sub-indices without blending different booking horizons.

- [x] **Task 1.7: Deterministic Statistical Test Suite**
  - **PRD Ref:** Section 61; `real_world_critique.md`
  - Write `tests/statistical/test_index_deterministic.py`:
    - Fixture with 2 routes ($w_1=0.6, w_2=0.4$), base prices [100, 100], day 1 prices [100, 120].
    - Asserts $I_1 = 100 \times (0.6 \times 1.0 + 0.4 \times 1.2) = 108.000$ exactly.
    - Asserts that sold-out flights do not default to ₹0 or distort the median.
    - Asserts $T+1$ fares and $T+45$ fares are never mixed into the same representative price calculation.
  - **Acceptance Criteria:** `pytest tests/statistical/` passes with 100% deterministic precision.

---

## Phase 2: Source Registry & Data Collection Framework
**Objective:** Construct a compliance-first, multi-source collection architecture with rate limiting, health tracking, and raw payload auditability.

- [x] **Task 2.1: Source Registry Service**
  - **PRD Ref:** Section 12, 40.1
  - Implement source management service:
    - Registry for sources (Airlines, OTAs, Public aggregators, Mock feeds).
    - Tracks: `permission_status`, `tos_status`, `robots_status`, `rate_limit`, `enabled`.
    - Enforces state machine: `DISCOVERED` → `REVIEW_REQUIRED` → `APPROVED` → `ACTIVE` → `DEGRADED` → `DISABLED`.
    - Rejection guard: Unapproved sources cannot be scheduled for live collection.
  - **Acceptance Criteria:** Service rejects activation of sources without approval audit flag.

- [x] **Task 2.2: Abstract Connector Interface & Base Collector**
  - **PRD Ref:** Section 13, 14
  - Create `services/collectors/base.py`:
    - `BaseConnector` abstract class with methods: `search(route, date, horizon)`, `health_check()`.
    - `CollectionJob` data model generating jobs for $(S, S+1, S+7, S+14, S+30, S+45)$.
    - Standardized return structure: `CollectionResult(raw_payload, parsed_fares, error_code, latency_ms)`.
  - **Acceptance Criteria:** Mock connector implements `BaseConnector` and executes search contract.

- [x] **Task 2.3: Raw Payload Storage & Cryptographic Lineage Tracking**
  - **PRD Ref:** Section 18, 40.5, 78
  - Create `services/collectors/payload_store.py`:
    - Immutable storage for raw responses (JSON / HTML) in `data/raw/YYYY/MM/DD/`.
    - Generates SHA-256 hash of every payload for tamper-evident auditability.
    - Links `fare_observations.raw_payload_id -> raw_payloads.id`.
  - **Acceptance Criteria:** Raw response written to disk, hashed, and database record points to raw storage.

- [x] **Task 2.4: Bounded Retry, Circuit Breaker & Error Taxonomy**
  - **PRD Ref:** Section 54, 63
  - Create error handling module:
    - Standard error types: `SOURCE_UNAVAILABLE`, `PERMISSION_DENIED`, `TIMEOUT`, `PARSER_ERROR`, `SCHEMA_CHANGED`, `NO_RESULTS`.
    - Exponential backoff retry with max 3 attempts.
    - Tripping circuit breaker after 5 consecutive failures, transitioning source to `DEGRADED`.
  - **Acceptance Criteria:** Collector simulates 5 failures, transitions to degraded, and ceases hammering endpoint.

- [x] **Task 2.5: Collector Health Telemetry & Metric Emission**
  - **PRD Ref:** Section 49, 52, 53
  - Track per-source telemetry:
    - Success rate, valid quote rate, parser error rate, average latency (ms), timestamp of last successful run.
  - **Acceptance Criteria:** Telemetry stored in DB/cache and accessible via health query.

---

## Phase 3: Live / Permitted Fare Collection Pipeline
**Objective:** Implement authorized/public live flight price collection across all 5 lead-time windows and parse fare decompositions.

- [x] **Task 3.1: Live Connector Implementation (Playwright / Public API)**
  - **PRD Ref:** Section 11.1, 11.2, 13
  - Create `services/collectors/live_connector.py`:
    - Playwright / Headless browser / Permitted API client for domestic search.
    - Queries configured routes for $T+1, T+7, T+15, T+30, T+45$.
    - Captures domestic flight options, carrier codes, flight numbers, cabin classes, departure times.
  - **Acceptance Criteria:** Single invocation queries 5 horizon dates and returns raw response payloads.

- [x] **Task 3.2: Fare Component Parser & Decomposition**
  - **PRD Ref:** Section 15, 16, 17; `real_world_critique.md` Fix 4
  - Build parser extracting:
    - Base fare, Fuel surcharge/fees, GST/taxes, UDF/ADF airport charges, Convenience charges.
    - Total quoted consumer fare.
    - Handles sold-out badges explicitly (`availability_status = SOLD_OUT`).
  - **Acceptance Criteria:** Parser extracts fare components from live payloads and verifies component sum matches total.

- [x] **Task 3.3: Schema Drift Detection & Protection**
  - **PRD Ref:** Section 64
  - Validate parsed results against strict Pydantic models before saving.
  - If unexpected layout or 0 fares returned on a popular route: trigger `SCHEMA_CHANGED` warning event without saving corrupt zeros.
  - **Acceptance Criteria:** Corrupt mock HTML payload triggers schema warning and prevents zero-fare insertion.

- [x] **Task 3.4: Automated Collection Scheduler**
  - **PRD Ref:** Section 14, 39
  - Set up APScheduler daily cron job (e.g., runs daily at 06:00 IST and 18:00 IST).
  - Triggers collection jobs for all 10 active routes $\times 5$ lead times.
  - **Acceptance Criteria:** Scheduler executes test job run and records completed runs in `collection_jobs`.

---

## Phase 4: DGCA Route Weights & Basket Engine
**Objective:** Ingest authentic DGCA domestic passenger traffic volumes, compute normalized corridor weights, and document statistical coverage limitations.

- [x] **Task 4.1: DGCA Scheduled Domestic Passenger Traffic Ingestion**
  - **PRD Ref:** Section 22, 35; `real_world_critique.md` Problem 2
  - Source and format DGCA city-pair monthly passenger traffic report in `data/reference/dgca_traffic.csv`.
  - Ingestion parser normalizes airport codes (DEL, BOM, BLR, CCU, HYD, MAA, IXS, DHM).
  - Handles bidirectional traffic: Combines DEL $\rightarrow$ BOM and BOM $\rightarrow$ DEL volumes to represent city-pair corridor.
  - **Acceptance Criteria:** Ingestion script parses CSV and returns passenger traffic volumes for all 10 route corridors.

- [x] **Task 4.2: Route Weight Calculation & Normalization**
  - **PRD Ref:** Section 23
  - Calculate weight for route $j$: $w_j = \frac{V_j}{\sum_{k=1}^n V_k}$.
  - Strict assertion: Verify $\sum_{j=1}^n w_j = 1.000000 \pm 10^{-6}$.
  - Compute weights for the 10 selected routes and persist to `route_weights`.
  - **Acceptance Criteria:** Sum of weights equals 1.0; top routes (DEL-BOM, DEL-BLR) exhibit proportional weights.

- [x] **Task 4.3: Weight Versioning & Lineage Metadata**
  - **PRD Ref:** Section 23, 40.6, 41
  - Add version tags (e.g., `DGCA_2025_Q4`, `DGCA_2026_Q1`) with `effective_from` and `effective_to` dates.
  - Maintain historical weights without mutating prior records.
  - **Acceptance Criteria:** Index calculations query weights based on observation date and methodology version.

- [x] **Task 4.4: Methodology Transparency Documentation (Weighting Limitations)**
  - **PRD Ref:** `real_world_critique.md` Problem 2
  - Add explicit methodological note in metadata and documentation:
    *"Route weights reflect boarded passenger volumes, not route-level consumer price exposure. High-volume competitive corridors receive large weights, while regional/thin corridors with high inflation vulnerability have smaller weights."*
  - **Acceptance Criteria:** Note is stored in `methodology_versions.notes` and exposed via API.

---

## Phase 5: Daily Airfare Index Engine & Aggregations
**Objective:** Calculate daily national and route-level price indices, unpooled lead-time indices, and compute multi-frequency temporal aggregations.

- [x] **Task 5.1: Daily Headline Index Pipeline ($T+15$ Anchor)**
  - **PRD Ref:** Section 27, 28, 40.8; `real_world_critique.md` Fix 2
  - Create daily calculation service:
    - Gathers cleaned observations for date $t$ at horizon $h = T+15$.
    - Computes representative price $P_{j,t,T+15}$ using lowest-economy median estimator.
    - Computes route relatives $R_{j,t} = P_{j,t} / P_{j,0}$.
    - Calculates National Headline Index: $I_t^{\text{Headline}} = 100 \sum w_j R_{j,t}$.
    - Calculates both `BASE_FARE` and `TOTAL_PRICE` variants.
    - Records daily deltas: 1D, 7D, 30D percentage change.
  - **Acceptance Criteria:** Service produces daily headline index anchored at T+15 with both price bases.

- [x] **Task 5.2: Unpooled Lead-Time Sub-Indices ($T+1, T+7, T+15, T+30, T+45$)**
  - **PRD Ref:** Section 28, 30; `real_world_critique.md` Problem 3
  - Calculate independent sub-indices for each lead-time horizon:
    - $I_{t, T+1}, I_{t, T+7}, I_{t, T+15}, I_{t, T+30}, I_{t, T+45}$.
    - Enables tracking inflation divergence between last-minute bookings ($T+1$) and advance bookings ($T+45$).
  - **Acceptance Criteria:** Sub-indices generated independently without cross-horizon blending.

- [x] **Task 5.3: Multi-Frequency Aggregations (Weekly & Monthly)**
  - **PRD Ref:** Section 28, 32
  - Implement time-aggregation engine:
    - Weekly index: Geometric mean of daily headline indices over 7 days.
    - Monthly index: Monthly calendar average of daily headline series suitable for MoSPI CPI alignment.
  - **Acceptance Criteria:** Aggregation script converts 30 daily observations into monthly index matching benchmark frequency.

- [x] **Task 5.4: Missing Data & Low Coverage Guard**
  - **PRD Ref:** Section 29
  - Calculate active route coverage rate: $\text{coverage\_rate} = \frac{\text{routes with valid quotes}}{\text{total basket routes}}$.
  - If coverage $< 80\%$, assign status `LOW_COVERAGE` into `index_values`.
  - Prevent zero substitution for missing route prices; apply carry-forward imputation with audit flag.
  - **Acceptance Criteria:** Partial data day generates index with `LOW_COVERAGE` warning flag.

- [x] **Task 5.5: Index Lineage & Snapshot Freezing**
  - **PRD Ref:** Section 41, 78
  - Each calculation run persists: `methodology_version`, `weight_version`, `data_snapshot_timestamp`, `calculated_at`.
  - Ensures complete reproducibility for MoSPI statistical audit.
  - **Acceptance Criteria:** Any historical index number can be recomputed and proven identical from frozen snapshots.

---

## Phase 6: Statistical Observatory Dashboard (Next.js + Design System)
**Objective:** Deliver an executive, judge-ready statistical dashboard implementing the Origin Financial dark aesthetic with corrected statistical framing. Evolved from the 9 PRD screens into 13 views / 17 Next.js routes (Original 9 + Forecast, Market Dynamics, Fluctuations, Corridors, Governance, Route Detail).

- [x] **Task 6.1: Dark Observatory Design System & Component Library**
  - **PRD Ref:** `Design rules/DESIGN (2).md`, `variables (2).css`
  - Implement reusable UI primitives in `apps/dashboard/components/ui`:
    - `StatCard`: Dark graphite background, Suisse Int'l typography, pure white metrics, pill indicators.
    - `PrimaryButton`: High contrast #ffffff fill with black text, 8px radius, right arrow `→`.
    - `Badge`: Monospace labels (`Roboto Mono`), uppercase, 11px, tracked.
    - `Surface`: Obsidian `#0f1011` canvas, Abyss `#090a0b` nested sections, Graphite `#2e2e2e` cards.
    - Color accents: Iris Gleam `#847dff` for feature focus, Cyan Signal `#00b3dd` for charts.
  - **Acceptance Criteria:** Component showcase page renders all primitives matching design rules.

- [x] **Task 6.2: Screen 1 — National Overview (Executive Observatory)**
  - **PRD Ref:** Section 43, 74; `real_world_critique.md` Fix 5
  - Build `/` landing dashboard:
    - Hero Metric Card: **India Airfare Price Index** (e.g. `108.42`), +1.72% Today, +3.81% 7D, +6.10% 30D.
    - Sub-header tag: `HEADLINE ANCHOR: T+15 ADVANCE PURCHASE | BASE FARE BASIS | BASE: 2026-08-01 = 100`.
    - Price Basis Toggle: Switch between **Base Fare Index** (carrier behavior) and **Total Price Index** (consumer out-of-pocket).
    - KPI Grid: National Coverage % (`94.6%`), Basket Corridors (`10`), Valid Quotes Today (`12,482`), Active Version (`APIX-2.0`).
    - Primary Interactive Time Series Chart: 30-day daily national airfare index with hover tooltips and lead-time horizon selector overlay.
    - Route contribution drawer: Quantifies which routes drove the headline index delta.
  - **Acceptance Criteria:** Screen loads in $< 2$ seconds with live API data and formatted tooltips.

- [x] **Task 6.3: Screen 2 — Route Heatmap & Matrix**
  - **PRD Ref:** Section 44
  - Build `/routes` matrix:
    - Table columns: Route (`DEL-BOM`), Corridor Type (`Metro Trunk` vs `Regional Thin`), Current Route Index, 1D Delta, 7D Delta, 30D Delta, DGCA Weight %, Coverage Status.
    - Color-coded delta badges (cool cyan / muted slate, avoiding garish saturated greens/reds).
    - Sortable and filterable by origin city and price movement.
  - **Acceptance Criteria:** All 10 routes render with real weights and clickable row navigation to route detail.

- [x] **Task 6.4: Screen 3 — Route Detail & Distribution**
  - **PRD Ref:** Section 45; `real_world_critique.md` Problem 1
  - Build `/routes/[route_id]`:
    - Header: Origin $\rightarrow$ Destination with airport codes.
    - Current representative price ($P_{j,t}$) and historical price chart.
    - Carrier breakdown: IndiGo vs Air India vs SpiceJet vs Akasa lowest economy fares on this corridor.
    - Fare decomposition bar: Base Fare vs Fuel Surcharge vs GST vs UDF vs Convenience Fee.
    - Fare dispersion chart (Box plot / Percentile distribution: 10th, 25th, Median, 75th, 90th).
  - **Acceptance Criteria:** Route detail page displays multi-carrier price comparison and fare component breakdown.

- [x] **Task 6.5: Screen 4 — Lead-Time Elasticity ("The Signature WOW Feature")**
  - **PRD Ref:** Section 31, 46, 76; `real_world_critique.md` Fix 2
  - Build `/lead-time`:
    - Interactive controls: Route selector, Carrier filter, Date selector.
    - Dynamic Lead-Time Curve: $T+45 \rightarrow T+30 \rightarrow T+15 \rightarrow T+7 \rightarrow T+1$.
    - Dynamic Lead-Time Multiplier metric display:
      $$\text{Surge Multiplier} = \frac{\text{Price}_{T+1}}{\text{Price}_{T+45}} \quad (\text{e.g. } 2.45\times)$$
    - Lead-Time spread comparison across airlines (which airline escalates last-minute fares highest).
  - **Acceptance Criteria:** User toggles routes and instantly views dynamic non-hardcoded lead-time curves with multiplier callouts.

- [x] **Task 6.6: Screen 5 — MoSPI Benchmark Directional Co-Movement**
  - **PRD Ref:** Section 32, 33, 47, 74; `real_world_critique.md` Problem 4 & Fix 5
  - Build `/validation`:
    - Dual-series comparative chart: **Prototype Airfare Index (Monthly Aggregated)** vs **Official MoSPI Benchmark (CPI Airfare / Transport)**.
    - Honest Statistical Scorecard:
      - Directional Accuracy % (percentage of periods where price change direction matches)
      - Pearson Correlation ($r$)
      - MAE and RMSE with explicit unit and base period disclosures.
    - Prominent Methodological Footnote:
      *"Directional co-movement analysis. The prototype measures high-frequency forward-looking search-date quotes across five horizons, whereas MoSPI CPI reflects retrospective survey collection on fixed routes and dates. Co-movement indicates alignment with broader macroeconomic inflation trends."*
  - **Acceptance Criteria:** Screen renders dual series with honest statistical scorecard and methodological disclaimer.

- [x] **Task 6.7: Screen 6 — Data Quality & Integrity Monitor**
  - **PRD Ref:** Section 48, 62
  - Build `/quality`:
    - Integrity metric cards: Valid Quotes Today, Rejected Quotes, Missing/Unavailable Quotes, Deduplicated Fares, Parser Warnings.
    - Daily quote capture rate time-series chart.
    - Quality score distribution histogram (0–100 score distribution).
    - Audit log table displaying recent validation warning events.
  - **Acceptance Criteria:** Quality dashboard renders daily coverage and quality audit tables.

- [x] **Task 6.8: Screen 7 — Source Health & Reliability**
  - **PRD Ref:** Section 49, 52
  - Build `/sources`:
    - Source registry status cards: Source name, Type, Permission status, Health state (`HEALTHY`, `WARNING`, `DEGRADED`, `DOWN`).
    - Operational metrics: Success Rate %, Valid Fare %, Latency (ms), Last Successful Run timestamp.
    - Admin action: Toggle source active/disabled without restarting server.
  - **Acceptance Criteria:** Status badges reflect live health and source toggle updates immediately.

- [x] **Task 6.9: Screen 8 — ATF (Jet Fuel) Macro Context Overlay**
  - **PRD Ref:** Section 36, 37, 50; `real_world_critique.md` Problem 6 & Fix 5
  - Build `/fuel-context`:
    - Dual-axis chart: Metropolitan ATF Price per kL vs India Airfare Price Index.
    - Macro cost context card: *"Aviation Turbine Fuel (ATF) represents approximately 35–45% of Indian domestic airline operating expenses."*
    - Strict non-causal disclosure:
      *"ATF price movements are shown as macroeconomic context. Airline fuel hedging cycles (12–18 months) and revenue management pricing models mean short-term price variations do not exhibit direct daily pass-through."*
  - **Acceptance Criteria:** ATF vs Airfare chart loads synchronized dates and non-causal explanatory summary.

- [x] **Task 6.10: Screen 9 — Transparent Methodology & Governance**
  - **PRD Ref:** Section 51, 78; `real_world_critique.md`
  - Build `/methodology`:
    - Mathematical formulation visualizer: Modified Laspeyres formula with LaTeX KaTeX equations.
    - Active Route Basket table: 10 city pairs, corridor types, DGCA passenger volume, calculated weights $w_j$.
    - Estimator documentation: Lowest available Economy fare rationale (fare-mix protection).
    - Anchor window rationale: Why T+15 was chosen as headline.
    - Documented limitations: Boarded passenger weighting nuances and thin-route representation.
    - Version history: Active version `APIX-2.0`, effective date, change log.
  - **Acceptance Criteria:** Analyst can understand full calculation methodology and documented limitations without inspecting code.

- [x] **Task 6.11: Responsive Layout, Navigation Bar & Global Time Controls**
  - **PRD Ref:** Section 66; `Design rules/`
  - Top navigation bar with:
    - Brand title: **INDIA AIRFARE PRICE OBSERVATORY**
    - Live Status Pill: `● SYSTEM OPERATIONAL | ANCHOR: T+15 | BASE: 2026-08-01 = 100`
    - Date range picker (7D, 30D, 90D, Custom)
    - Direct links to: Overview, Routes, Lead-Time, Benchmark, Quality, Health, Fuel Context, Methodology.
  - **Acceptance Criteria:** Navigation works smoothly across all 13 views with shared date filters.

---

## Phase 7: MoSPI Benchmark Directional Co-Movement Module
**Objective:** Ingest official MoSPI CPI transport indices, compute frequency-matched series, and evaluate statistical tracking performance.

- [x] **Task 7.1: MoSPI CPI Transport Data Ingestion**
  - **PRD Ref:** Section 32, 40.9
  - Ingest official CPI Transport & Communication / Airfare index series in `data/reference/mospi_cpi_benchmark.csv`.
  - Store parsed benchmarks in `benchmark_values` table with period, indicator name, and source metadata.
  - **Acceptance Criteria:** Script successfully populates benchmark data table.

- [x] **Task 7.2: Frequency Matching & Monthly Aggregation Engine**
  - **PRD Ref:** Section 32
  - Create `packages/statistics/benchmark_matcher.py`:
    - Bridges daily high-frequency prototype index with monthly official CPI reporting frequency.
    - Computes monthly calendar-weighted average of prototype daily series.
  - **Acceptance Criteria:** Converts 30 daily observations into monthly aggregated index matching benchmark timestamp.

- [x] **Task 7.3: Statistical Directional Co-Movement Suite**
  - **PRD Ref:** Section 33, 40.10; `real_world_critique.md` Problem 4
  - Calculate co-movement metrics:
    - Pearson correlation coefficient: $r = \frac{\sum (P_t - \bar{P})(O_t - \bar{O})}{\sqrt{\sum (P_t - \bar{P})^2 \sum (O_t - \bar{O})^2}}$
    - Directional Accuracy: $\% \text{ periods where } \text{sign}(\Delta P) = \text{sign}(\Delta O)$
    - Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) with scale normalization.
  - Save results to `validation_results`.
  - **Acceptance Criteria:** Function outputs metric dictionary with automated test verification.

- [x] **Task 7.4: Automated Directional Report Generator**
  - **PRD Ref:** Section 33, 75
  - Output summary report for executive presentation / MoSPI statistical audit.
  - **Acceptance Criteria:** Generates structured JSON and printable Markdown summary of co-movement metrics.

---

## Phase 8: ATF (Jet Fuel) Macro Context Vertical
**Objective:** Ingest jet fuel price histories (IOCL / PPAC) to provide macro fuel context alongside airfare movements.

- [x] **Task 8.1: ATF Historical Price & Tax Rate Ingestion**
  - **PRD Ref:** Section 36, 40.11, 40.12
  - Collect domestic ATF prices across metro hubs (Delhi, Mumbai, Bengaluru, Kolkata) in `data/reference/atf_prices.csv`.
  - Ingest applicable VAT/excise duty metadata in `atf_tax_rates`.
  - **Acceptance Criteria:** Ingestion script populates `atf_prices` table with date and price per kL.

- [x] **Task 8.2: Fuel-Airfare Context Overlay Generator**
  - **PRD Ref:** Section 37; `real_world_critique.md` Problem 6
  - Implement analysis module:
    - Synchronizes ATF price movements with National Airfare Index series.
    - Prepares macro cost structure summary (fuel expense share as percentage of total airline operating costs).
  - **Acceptance Criteria:** Generates synchronized time-series data without unsubstantiated daily causality claims.

- [x] **Task 8.3: Non-Causal Explanatory Summary**
  - **PRD Ref:** Section 37, 77
  - Prepare explanatory data feed for dashboard display adhering strictly to non-causal statistical terminology.
  - **Acceptance Criteria:** Explanatory text uses validated terms (*"macroeconomic context layer"* instead of *"ATF caused airfares to rise"*).

---

## Phase 9: Production REST API & Researcher Data Exports
**Objective:** Provide documented, high-performance API endpoints for developers, economists, and institutional researchers.

- [x] **Task 9.1: Core Statistical API Routers**
  - **PRD Ref:** Section 42, 65; `real_world_critique.md`
  - Implement FastAPI router endpoints (actual surface verified in `apps/api/routers/api_v1.py`):
    - `GET /api/v1/index?series={base_fare|total_price}&horizon={t15|t1|t7|t30|t45}`: Current headline index and sub-indices, 1D/7D/30D deltas, coverage rate.
    - `GET /api/v1/index/timeseries`: Daily time-series with coverage (with `from`/`to` slicing).
    - `GET /api/v1/index/monthly`: Monthly aggregated time-series.
    - `GET /api/v1/routes`: Route basket summary with corridor types, current index, and weights.
    - `GET /api/v1/routes/{route_code}`: Route analytics, fare components, lowest economy carrier breakdown.
    - `GET /api/v1/lead-time`: T+1, T+7, T+15, T+30, T+45 prices and surge multiplier ($T+1/T+45$).
    - `GET /api/v1/weights`: Current and historical DGCA route weights.
    - `GET /api/v1/validation`: Official MoSPI benchmark comparison & directional co-movement metrics.
    - `GET /api/v1/data-quality`: Ingestion health, valid vs rejected quotes, coverage rates.
    - `GET /api/v1/source-health`: Real-time source statuses, latencies, and success rates.
    - `GET /api/v1/fuel-context`: ATF prices vs airfare index time-series.
    - `GET /api/v1/methodology`: Active formulas, estimator configuration, and basket documentation.
    - ML extensions: `GET /api/v1/forecast`, `/api/v1/forecast/all`, `/api/v1/forecast/history-and-forecast` (ensemble projections).
    - Analytics: `GET /api/v1/analytics/carrier-inflation{/timeseries}`, `/api/v1/analytics/volatility{/{route_code}}`.
  - **Acceptance Criteria:** All endpoints return valid Pydantic JSON with HTTP 200 and schema validation.

- [x] **Task 9.2: Data Export Endpoints (CSV / JSON for Economists)**
  - **PRD Ref:** Section 7.2, 82
  - Endpoints:
    - `GET /api/v1/export/daily-index.csv`: Downloadable daily index series (both Base Fare and Total Price).
    - `GET /api/v1/export/daily-index.json`: Structured JSON series export.
    - `GET /api/v1/export/basket-weights.csv`: DGCA basket weights export.
    - `GET /api/v1/export/route-observations.csv`: Filtered cleaned observations for statistical research.
  - **Acceptance Criteria:** Endpoints stream valid RFC 4180 CSV files with appropriate Content-Disposition headers.

- [x] **Task 9.3: API Performance Optimization & Query Caching**
  - **PRD Ref:** Section 67
  - Cache heavy time-series responses using in-memory sliding window and optimized indexed lookups.
  - Rate limiting middleware: Sliding window per client IP (120 req/min, 429 status code with Retry-After).
  - **Acceptance Criteria:** Response latency for `/api/v1/index` is $< 100\text{ ms}$; full daily series $< 500\text{ ms}$.

- [x] **Task 9.4: OpenAPI Specification & Interactive Documentation**
  - **PRD Ref:** Section 42, 79
  - Configure FastAPI Swagger UI (`/docs`) and ReDoc (`/redoc`) with complete field descriptions, examples, and version metadata.
  - **Acceptance Criteria:** Swagger UI loads cleanly and all endpoints can be executed interactively.

---

## Phase 10: System Hardening, E2E Verification & SIH Demo Readiness
**Objective:** Execute full end-to-end integration tests, package 30-day realistic demonstration data, and prepare judge demo scripts.

- [x] **Task 10.1: Comprehensive End-to-End Test Suite**
  - **PRD Ref:** Section 61, 86
  - Write test suite:
    - Synthetic dataset generation $\rightarrow$ Normalization $\rightarrow$ Lowest-economy estimator $\rightarrow$ Route weighting $\rightarrow$ Daily headline index calculation $\rightarrow$ Monthly aggregation $\rightarrow$ Benchmark co-movement $\rightarrow$ REST API output.
  - **Acceptance Criteria:** Single test command `pytest tests/` runs all unit, statistical, and integration tests with zero errors.

- [x] **Task 10.2: 30-Day Pipeline Verification Seed Package**
  - **PRD Ref:** Section 34, 74; `real_world_critique.md` Problem 5
  - Create single CLI command: `python -m services.seed_demo_data`
    - Ingests reference DGCA passenger weights (10 routes).
    - Seeds 30 consecutive days of realistic, deterministic domestic fare observations across all 5 lead-time windows.
    - Explicitly tags records with `is_synthetic = True` for audit transparency.
    - Computes daily route and national headline indices ($T+15$), lead-time sub-indices, and monthly aggregations.
    - Seeds MoSPI CPI benchmark and ATF fuel series.
    - Computes directional co-movement metrics.
  - **Acceptance Criteria:** Running the command on a fresh database boots the entire platform with full 30-day historical data.

- [x] **Task 10.3: Documentation Suite**
  - **PRD Ref:** Section 79; `real_world_critique.md`
  - Complete repository documentation files:
    - `README.md`: Quick start guide (`docker compose up`, seed data, access dashboard).
    - `ARCHITECTURE.md`: Eight-layer system architecture diagram and data pipeline.
    - `DATA_MODEL.md`: Database ER diagram and table definitions.
    - `METHODOLOGY.md`: Full mathematical formula derivations, lowest-economy estimator defense, unpooled lead-time rationale, and documented DGCA weight limitations.
    - `SOURCES.md`: Source registry, robots rules, and compliance framework.
    - `DEMO.md`: Exact walkthrough instructions following the 6-minute Judge Demo Script.
  - **Acceptance Criteria:** All 6 markdown documents exist and pass link and markdown linting.

- [x] **Task 10.4: 6-Minute Judge Demo Dry-Run Verification**
  - **PRD Ref:** Section 75; `real_world_critique.md`
  - Rehearse and verify the 6-minute presentation script:
    - **0:00–0:45:** The real-world problem: official monthly CPI cannot capture high-frequency or lead-time dynamics.
    - **0:45–1:30:** Collection & 5 advance purchase horizons ($T+1$ to $T+45$) with lowest-economy fare-mix protection.
    - **1:30–2:30:** National Headline Index ($T+15$ anchor), DGCA corridor weights, and route contribution attribution.
    - **2:30–3:30:** The "WOW" Lead-Time Elasticity curve & surge multiplier ($T+1 / T+45$).
    - **3:30–4:30:** MoSPI benchmark directional co-movement analysis and honest methodology comparison.
    - **4:30–5:15:** Data quality, quote capture rate, and source health monitoring.
    - **5:15–6:00:** Programmatic REST API & researcher export demo.
  - **Acceptance Criteria:** All screens, interactions, and metrics operate smoothly without console errors or layout glitches.

- [x] **Task 10.5: Docker Compose One-Click Deployment**
  - **PRD Ref:** Section 39, 58 (Phase 0 Criteria)
  - Verify complete stack launches with:
    ```bash
    docker compose up --build
    ```
  - Starts PostgreSQL/TimescaleDB, FastAPI backend (`localhost:8000`), Next.js dashboard (`localhost:3000`).
  - **Acceptance Criteria:** Entire system boots on clean clone with one command.

---

## Phase 11: Machine Learning & Anomaly Extensions (P2 / P3 Future Scope)
**Objective:** Deliver non-interfering secondary analytical intelligence (price anomalies and fare forecasting), explicitly separated from the official CPI index.

- [x] **Task 11.1: Route Fare Anomaly Detection Engine**
  - **PRD Ref:** Section 41, 85
  - Delivered corridor-level volatility / surge alert engine (`packages/statistics/volatility.py`):
    - Computes intraday min/max/mean/median, spread %, and std-dev per route/date.
    - Classifies each corridor: `CALM` / `MODERATE` / `HIGH_VOLATILITY` / `SURGE_ALERT`.
    - Persists to metadata table `route_volatility_records` and exposes `GET /api/v1/analytics/volatility{/{route_code}}`.
    - Feed drift detection (`services/collectors/drift_detector.py`) flags collection anomalies without touching index math.
  - **Acceptance Criteria:** Surge alerts flagged in metadata table and visible on the Fluctuations dashboard view.

- [x] **Task 11.2: Booking Pressure & Lead-Time Forecast Engine**
  - **PRD Ref:** Section 85
  - Delivered a full ensemble forecasting engine (`services/ml/`) rather than a skeleton:
    - **TimesFM 2.5** neural forecaster (50%) + **LightGBM with conformal intervals** (35%) + **Statistical STL+ARIMA** (15%).
    - Combined **Past 28 days observed + Future 28 days** projections with P10/P50/P90 confidence bands (`packages/statistics/confidence.py`).
    - API: `GET /api/v1/forecast`, `/api/v1/forecast/all`, `/api/v1/forecast/history-and-forecast` (past 28d + future 28d), `/api/v1/forecast/accuracy` (backtest vs realized).
    - Dashboard: `/forecast` with horizon toggle + lead-time ribbon + backtest accuracy panel; training pipeline in `services/ml/training_pipeline.py`; snapshots in `forecast_snapshots`.
  - **Explicit guardrail:** ML forecasts are labeled auxiliary projections and remain fully separated from the official Laspeyres CPI-eligible indices.
  - **Acceptance Criteria:** Forecast endpoints return 28-day horizon projections with tail confidence bands.

- [x] **Task 11.3: Full-Record Extraction & Industry Research Dossier**
  - Extended `adaptive_extractor.py` to extract the full fare-card record: `travel_date`/`return_date` (ISO, `DD MMM YYYY`, `MMM DD YYYY`, and year-less resolved to the queried date ±60d), `flight_number` (digit-leading codes like `6E-205` supported), airline, departure/arrival times, stops, duration.
  - `carrier_direct_scraper._extract_via_ocr` now merges on-page fields (incl. verified travel date with mismatch logging) instead of hardcoding fallbacks; VLM enabled by default behind a safe `VLMNotConfigured` guard.
  - Comparison/backtest match keys (`route + flight_number + travel_date`) are now grounded in on-page truth, not just query context.
  - Added `RESEARCH.md` (linked from README + PRD sitemaps): BLS/OAG/BTS index-methodology benchmarks, consumer prediction tools (Hopper/Kayak/Google/Farecast), academic literature, Zyte 2026 anti-bot landscape + legal frame (RFC 9309, hiQ/Van Buren/Meta-v-Bright Data, DMCA §1201), India regulatory context (DGCA TMU 78 routes, FIA data refusal, AirPrice Guardian, +20.5% fare surge), USP distillation + P1-P3 roadmap — all with source links.
  - **Acceptance Criteria:** extraction captures full record incl. on-page dates; full suite 156 passed; ruff clean.

---

## 🎯 Verification Matrix & Progress Summary

| Phase | Description | Priority | Prerequisite | Status |
|---|---|---|---|---|
| **Phase 0** | Foundation & Environment Setup | P0 | None | ✅ Completed |
| **Phase 1** | Statistical Core & Synthetic Verification (T+15 Anchor) | P0 | Phase 0 | ✅ Completed |
| **Phase 2** | Source Registry & Collection Architecture | P0 | Phase 1 | ✅ Completed |
| **Phase 3** | Live / Permitted Fare Collection Pipeline | P0 | Phase 2 | ✅ Completed |
| **Phase 4** | DGCA Route Weights & Basket Engine | P0 | Phase 1 | ✅ Completed |
| **Phase 5** | Daily Airfare Index Engine & Aggregations | P0 | Phase 1, 4 | ✅ Completed |
| **Phase 6** | Statistical Observatory Dashboard (Next.js) | P0 | Phase 5 | ✅ Completed |
| **Phase 7** | MoSPI Benchmark Directional Co-Movement | P0 | Phase 5 | ✅ Completed |
| **Phase 8** | ATF Jet Fuel Macro Context Vertical | P1 | Phase 5 | ✅ Completed |
| **Phase 9** | Production REST API & Data Exports | P0 | Phase 5, 7, 8 | ✅ Completed |
| **Phase 10** | Hardening, E2E Tests & SIH Demo Readiness | P0 | Phase 6, 9 | ✅ Completed |
| **Phase 11** | ML Anomaly & Forecasting Extensions | P2/P3 | Phase 10 | ✅ Completed |

---
*All 12 phases complete. The project is production-ready: 144 test suite green, dashboard builds cleanly, and the full API surface (index, corridors, forecast, OTA, AI copilot, exports) is operational on both Postgres and the SQLite fallback.*
