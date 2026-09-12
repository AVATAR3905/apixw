# Data Model & Database Architecture

> Database schema specifications for the India Airfare Price Observatory (APIX-2.0).
> Sources of truth: `packages/schemas/models.py` (17 SQLAlchemy tables) and `database/migrations/versions/fdf05b42557c_initial_schema_v2.py`.

---

## 1. Dual-Engine Architecture
The observatory supports **PostgreSQL / TimescaleDB** in production environments and automatically falls back to local **SQLite** (`airfare_observatory.db`) in standalone development mode. All schema tables, foreign keys, indexes, and migrations are 100% compatible with both engines (`database/session.py`).

## 2. Core Entities & Tables (16)

### 1. `sources`
- `id` (Integer, Primary Key)
- `name` (String 100, unique)
- `type` (String: AIRLINE, OTA, GDS_API, PUBLIC_FEED)
- `access_method` (String: PLAYWRIGHT, REST_API, PUBLIC_SCRAPE)
- `permission_status` (String: REVIEW_REQUIRED, APPROVED, REJECTED)
- `tos_status` (String: PENDING, APPROVED, ...)
- `robots_status` (String: PENDING, ...)
- `license_status` (String: NOT_REQUIRED, ...)
- `access_mode` (String: PUBLIC, CONDITIONAL, PARTNER_ONLY)
- `rate_limit` (Integer: requests per minute)
- `enabled` (Boolean)
- `health_status` (String: HEALTHY, WARNING, DEGRADED, DOWN)
- `last_reviewed_at` (DateTime, Nullable)
- `created_at` / `updated_at` (DateTime)

### 2. `routes`
- `id` (Integer, Primary Key)
- `origin` (String: Delhi, Mumbai, ...)
- `destination` (String: Mumbai, Bengaluru, ...)
- `origin_airport` (String: DEL, BOM, ...)
- `destination_airport` (String: BOM, BLR, ...)
- `route_code` (String: DEL-BOM, unique)
- `corridor_type` (String: METRO_TRUNK, REGIONAL_THIN)
- `active` (Boolean)
- `created_at` (DateTime)

### 3. `airlines`
- `id` (Integer, Primary Key)
- `code` (String: 6E, AI, SG, QP, IX)
- `name` (String: IndiGo, Air India, ...)
- `is_scheduled` (Boolean)
- `active` (Boolean)
- `created_at` (DateTime)

### 4. `raw_payloads`
- `id` (Integer, Primary Key)
- `source_id` (Integer, Foreign Key)
- `collection_job_id` (Integer, Nullable)
- `payload_uri` (String: file path under `data/raw/`)
- `payload_hash` (String: SHA-256 hex digest, indexed)
- `content_type` (String: application/json)
- `captured_at` (DateTime)

### 5. `fare_observations` (TimescaleDB Hypertable)
- `id` (Integer, Primary Key)
- `source_id`, `route_id`, `airline_id` (Integer, Foreign Keys)
- `search_timestamp` (DateTime, indexed)
- `travel_date` (Date, indexed)
- `advance_purchase_days` (Integer: 1, 7, 15, 30, 45, indexed)
- `flight_number` (String)
- `cabin_class` (String: ECONOMY, PREMIUM_ECONOMY, BUSINESS)
- `fare_family` (String: BASIC, FLEXI, COMFORT)
- `stops` (Integer)
- `availability_status` (String: AVAILABLE, SOLD_OUT, CANCELLED)
- `is_carrier_min_fare` (Boolean: True if cheapest economy quote for carrier)
- `base_fare` (Float, INR)
- `fuel_surcharge` (Float, INR)
- `tax_amount` (Float, GST)
- `development_fee` (Float, UDF/ADF)
- `convenience_fee` (Float, INR)
- `other_fee` (Float, INR)
- `total_fare` (Float, INR)
- `currency` (String: INR)
- `is_synthetic` (Boolean: Provenance flag)
- `feed_type` (String: CARRIER_DIRECT, RPC_FALLBACK, CALIBRATED_BASELINE)
- `extraction_method` (String: DOM_BROWSER, NETWORK_XHR, EMBEDDED, OCR, VLM, LLM, RPC, CALIBRATED_MODEL, SYNTHETIC)
- `quality_score` (Float: 0–100)
- `quality_status` (String: ACCEPT, ACCEPT_WITH_WARNING, REVIEW, REJECT)
- `collector_version` / `schema_version` (String)
- `raw_payload_id` (Integer, Foreign Key, Nullable)
- `created_at` (DateTime)
- **Indexes:** `idx_fare_lookup (route_id, travel_date, advance_purchase_days, cabin_class)`, `idx_search_carrier (search_timestamp, airline_id)`

### 6. `route_weights`
- `id` (Integer, Primary Key)
- `route_id` (Integer, Foreign Key)
- `passenger_volume` (Float)
- `weight` (Float: normalized sum = 1.0)
- `source` (String: DGCA Domestic Scheduled Passenger Traffic)
- `period` (String: 2026-Q1)
- `methodology_version` (String: APIX-2.0)
- `effective_from` (Date)
- `effective_to` (Date, Nullable)
- `created_at` (DateTime)

### 7. `collection_jobs`
- `id` (Integer, Primary Key)
- `route_id`, `source_id` (Integer, Foreign Keys)
- `search_date`, `travel_date` (Date)
- `advance_days` (Integer)
- `status` (String: PENDING, RUNNING, COMPLETED, FAILED)
- `attempt_count` (Integer)
- `started_at`, `completed_at` (DateTime, Nullable)
- `error_code` (String, Nullable)
- `error_message` (Text, Nullable)
- `created_at` (DateTime)

### 8. `index_values`
- `id` (Integer, Primary Key)
- `index_series` (String: BASE_FARE, TOTAL_PRICE)
- `index_type` (String: HEADLINE_T15, SUB_T1, SUB_T7, SUB_T15, SUB_T30, SUB_T45, ROUTE_LEVEL)
- `lead_time_days` (Integer: 15)
- `period_start` (Date, indexed) / `period_end` (Date)
- `route_id` (Integer, Nullable — null for national aggregate)
- `index_value` (Float)
- `daily_change_pct`, `weekly_change_pct`, `monthly_change_pct` (Float, Nullable)
- `coverage_rate` (Float: 0–100)
- `is_low_coverage` (Boolean)
- `methodology_version` (String: APIX-2.0) / `weight_version` (String: DGCA_2026_V1)
- `calculated_at` (DateTime)
- **Governance fields:** `index_status` (EXPERIMENTAL, BETA, LIVE, DEPRECATED), `quality_score`, `data_completeness`, `carrier_diversity`, `feed_quality_score`, `outlier_count`, `index_divisor`, `moving_avg_28d`, `spot_window_start`, `spot_window_end`
- **Index:** `idx_index_lookup (index_series, index_type, period_start)`

### 9. `benchmark_values`
- `id` (Integer, Primary Key)
- `period` (String: YYYY-MM, indexed)
- `indicator` (String: CPI_TRANSPORT_AIRFARE)
- `value` (Float)
- `base_year` (String: 2012=100)
- `source` (String: MoSPI / NSO / eSankhyiki)
- `source_version` (String: CPI_2026_M)
- `created_at` (DateTime)

### 10. `validation_results`
- `id` (Integer, Primary Key)
- `period_start`, `period_end` (Date)
- `series_evaluated` (String: HEADLINE_T15_BASE_FARE)
- `correlation` (Float: Pearson r)
- `mae` (Float) / `rmse` (Float)
- `directional_accuracy` (Float)
- `prototype_series_version` (String: APIX-2.0)
- `benchmark_version` (String: MoSPI_CPI_AIRFARE)
- `methodology_notes` (Text, Nullable)
- `created_at` (DateTime)

### 11. `discrepancy_audits`
- `id` (Integer, Primary Key)
- `route_id`, `airline_id` (Integer, Foreign Keys)
- `flight_number` (String)
- `travel_date` (Date, indexed)
- `advance_purchase_days` (Integer)
- `carrier_direct_price`, `rpc_validator_price` (Float, Nullable)
- `discrepancy_amount`, `discrepancy_pct` (Float)
- `validation_status` (String: EXACT_PARITY, CARRIER_CHEAPER, AGGREGATOR_MARKUP, FALLBACK_RPC_USED)
- `notes` (String, Nullable)
- `verified_at` (DateTime)

### 12. `atf_prices`
- `id` (Integer, Primary Key)
- `location` (String: Delhi, Mumbai, Kolkata, Chennai)
- `date` (Date, indexed)
- `price_per_kl` (Float, INR per kL)
- `source` (String: IOCL / PPAC)
- `created_at` (DateTime)

### 13. `atf_tax_rates`
- `id` (Integer, Primary Key)
- `effective_from` (Date, indexed) / `effective_to` (Date, Nullable)
- `tax_type` (String: CENTRAL_EXCISE, STATE_VAT)
- `rate` (Float: percentage)
- `source` (String: PPAC)
- `created_at` (DateTime)

### 14. `methodology_versions`
- `id` (Integer, Primary Key)
- `version` (String, unique: APIX-2.0)
- `name` (String)
- `base_period` (String: 2026-08-01)
- `anchor_lead_time` (String: T+15)
- `price_estimator` (String: LOWEST_ECONOMY_CARRIER_MEDIAN)
- `missing_data_method` (String: EXCLUDE_SOLD_OUT_RECORD_COVERAGE)
- `outlier_method` (String: ROBUST_MEDIAN_FILTER)
- `weight_method` (String: DGCA_BIDIRECTIONAL_PASSENGER_VOLUME)
- `formula` (Text)
- `effective_from` (Date)
- `notes` (Text, Nullable)
- `created_at` (DateTime)

### 15. `carrier_indices`
- `id` (Integer, Primary Key)
- `carrier_code` (String: 6E, AI, SG, QP, indexed)
- `period_date` (Date, indexed)
- `horizon_days` (Integer: 15)
- `carrier_index_value` (Float)
- `base_period_date` (Date)
- `daily_change_pct`, `weekly_change_pct`, `monthly_change_pct` (Float, Nullable)
- `routes_covered` (Integer)
- `created_at` (DateTime)

### 16. `route_volatility_records`
- `id` (Integer, Primary Key)
- `route_id` (Integer, Foreign Key)
- `calculation_date` (Date, indexed)
- `horizon_days` (Integer: 14)
- `min_price`, `max_price`, `mean_price`, `median_price` (Float)
- `spread_pct` (Float) / `std_dev` (Float)
- `volatility_status` (String: CALM, MODERATE, HIGH_VOLATILITY, SURGE_ALERT)
- `sample_size` (Integer)
- `created_at` (DateTime)

### 17. `forecast_snapshots`
One row **per forecasted day**, persisted every time a forecast is generated, so accuracy can be backtested once realized index values arrive.
- `id` (Integer, Primary Key)
- `generated_at` (DateTime, indexed)
- `series` (String: BASE_FARE, TOTAL_PRICE)
- `index_type` (String: HEADLINE_T15, SUB_T1, ...)
- `forecast_date` (Date, indexed) — last observed index date
- `target_date` (Date, indexed) — day being forecast
- `horizon_days` (Integer)
- `p10`, `p25`, `p50`, `p75`, `p90` (Float, Nullable) — prediction intervals
- `model_confidence` (Float, Nullable)
- `ensemble_weights` (Text, Nullable JSON), `model_versions` (Text, Nullable JSON)
- `history_days` (Integer, Nullable)
- Index: `(series, index_type, forecast_date, target_date)`