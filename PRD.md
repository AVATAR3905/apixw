# PRODUCT REQUIREMENT DOCUMENT
# Real-Time Airfare Price Index for India

**Project:** SIH26056  
**Organization:** Ministry of Statistics and Programme Implementation (MoSPI)  
**Domain:** Travel & Tourism  
**Category:** Software  
**Product Type:** Statistical Data & Intelligence Platform  
**Prototype Name:** India Airfare Price Observatory  
**Document Status:** Prototype Development PRD  
**Target Development Approach:** LLM-Assisted / Vibe Coding  
**Primary Users:** Government/statistics analysts, economists, researchers  
**Secondary Users:** Aviation analysts, airlines, OTAs, institutional researchers

---

# 1. EXECUTIVE SUMMARY

The India Airfare Price Observatory is a software system designed to collect, standardize, validate, analyze and expose domestic airfare observations at high frequency.

The system converts fare observations from permitted airline, OTA, API and public-data sources into a transparent, consumer-weighted airfare price index.

The prototype will focus on five standardized advance-purchase windows:

- T+1
- T+7
- T+15
- T+30
- T+45

The research recommends collecting fare attributes including search date, travel date, origin, destination, carrier, flight number, cabin class, stops, fare type, inventory availability, base fare, taxes, development fees and convenience charges. Sold-out flights are to be treated as unavailable observations rather than zero-price observations.

Route weights will be derived from DGCA city-pair passenger traffic so that the national index reflects actual travel volumes rather than an arbitrary route mix.

Historical CPI information from MoSPI will provide the official benchmark for validation.

The system may additionally integrate commercial travel APIs for cross-checking and ATF/fuel information for explanatory analysis.

The core prototype output will be:

> **A daily India Airfare Price Index with route-level analysis, five lead-time curves, source/data-quality monitoring and comparison against an official MoSPI benchmark.**

---

# 2. PROBLEM STATEMENT

Airfare is a highly dynamic price category.

The same origin-destination pair can have materially different quoted fares depending on:

- travel date
- booking date
- airline
- fare family
- inventory
- route capacity
- demand
- taxes
- fees
- fuel conditions
- market disruptions

A low-frequency or manually collected price observation can therefore fail to capture the actual dynamics experienced by consumers.

The proposed system addresses this by creating a repeatable observation framework in which:

```text
Search date
      +
Travel date
      +
Route
      +
Carrier
      +
Fare characteristics
      +
Availability
      +
Total mandatory price
```

become a standardized fare observation.

These observations are then transformed into:

```text
Individual Fare
       ↓
Cleaned Fare
       ↓
Route Price
       ↓
Route Relative
       ↓
Traffic-Weighted Index
       ↓
India Airfare Price Index
```

---

# 3. PRODUCT VISION

## Vision

Create India's transparent, high-frequency statistical layer for observing domestic airfare inflation and price behavior.

## Product Statement

> The India Airfare Price Observatory converts standardized high-frequency domestic airfare observations into a transparent, consumer-weighted price index that can complement traditional CPI measurement and provide deeper visibility into airfare dynamics.

---

# 4. PRODUCT PRINCIPLES

The product will follow six principles.

## 4.1 Statistical First

The objective is not to maximize the number of scraped pages.

The objective is to produce a **statistically defensible price measure**.

## 4.2 Transparent

Every index value must be traceable to:

- observations
- routes
- weights
- methodology version
- data-quality decisions

## 4.3 Reproducible

Given the same input data and methodology version, the same index value should be reproducible.

## 4.4 Compliance First

Data acquisition must respect:

- Terms of Service
- robots rules
- API/data licenses
- explicit source permissions

The architecture must not depend on bypassing access controls.

## 4.5 Failure Visible

A failed collector must never silently produce apparently valid data.

## 4.6 Methodology Versioned

Changes to:

- weights
- base period
- missing-data treatment
- outlier treatment
- aggregation

must create a new methodology/index version.

---

# 5. GOALS

## Primary Goals

1. Build a working automated airfare observation pipeline.
2. Implement standardized T+1/T+7/T+15/T+30/T+45 searches.
3. Store raw and cleaned fare observations.
4. Separate fare components.
5. Correctly handle sold-out/cancelled/unavailable flights.
6. Calculate route-level fares.
7. Apply DGCA-based route weights.
8. Produce daily, weekly and monthly indexes.
9. Compare the resulting index with an official MoSPI benchmark.
10. Show lead-time price behavior.
11. Expose results through an API.
12. Provide a judge-ready analytical dashboard.

## Secondary Goals

1. Integrate ATF data.
2. Detect source failures.
3. provide data-quality metrics.
4. Support route-level drill-down.
5. Provide historical analytical capability.
6. Prepare the architecture for future ML.

---

# 6. NON-GOALS

The first prototype will not attempt to:

- sell airline tickets
- process payments
- manage bookings
- bypass CAPTCHAs
- defeat anti-bot protections
- circumvent access controls
- collect prohibited data
- cover every Indian route
- cover every airline and OTA
- build an advanced forecasting model
- replace official CPI methodology
- claim causal relationships from simple correlations

---

# 7. TARGET USERS

## 7.1 Primary User — Government/Statistics Analyst

Needs to:

- observe current airfare movements
- inspect route contributions
- understand index methodology
- compare the new series against official statistics
- audit data quality

## 7.2 Economist/Researcher

Needs to:

- analyze airfare inflation
- study lead-time pricing
- investigate fuel relationships
- download/query historical data

## 7.3 Aviation Analyst

Needs to:

- compare route pricing
- analyze carrier pricing behavior
- identify unusual fare movement
- understand advance-purchase patterns

---

# 8. PRODUCT SCOPE

## MVP

Initial target:

- 5–10 representative routes
- 3–5 permitted/usable data sources
- 5 advance-purchase windows
- scheduled collection
- fare normalization
- data-quality engine
- DGCA-derived weights
- index engine
- MoSPI benchmark integration
- dashboard
- API
- source health monitoring

## Extended Prototype

Add:

- ATF data
- historical series
- anomaly detection
- more routes
- more sources
- advanced route analytics

## Future

Add:

- 50–100+ routes
- institutional integrations
- forecasting
- alerts
- commercial API subscriptions
- partner data feeds

---

# 9. CORE SYSTEM CONCEPT

The system consists of eight logical layers.

```text
1. Source Management
        ↓
2. Collection
        ↓
3. Raw Data Storage
        ↓
4. Normalization & Quality
        ↓
5. Statistical Aggregation
        ↓
6. Index Construction
        ↓
7. Validation & Analytics
        ↓
8. Dashboard + API
```

External reference data enters the system through:

```text
DGCA → Route Weights
MoSPI → Benchmark
ATF/PPAC/IOCL → Fuel Context
```

---

# 10. CORE USER JOURNEY

A statistical analyst opens the application.

### Step 1

Sees:

> India Airfare Price Index = 108.4

### Step 2

Sees daily/weekly/monthly movements.

### Step 3

Clicks:

> Why did it move?

The system shows route contributions.

### Step 4

Clicks a route.

The system shows:

- fare distribution
- carriers
- lead-time behavior
- observations
- availability

### Step 5

Opens:

> Lead-Time Elasticity

The system shows:

```text
T+45 → T+30 → T+15 → T+7 → T+1
```

### Step 6

Opens validation.

The system compares the prototype series against the official benchmark.

### Step 7

Opens methodology.

The system explains exactly how the number was produced.

---

# 11. DATA SOURCES

The system will support multiple source categories.

## 11.1 Airline Sources

Examples identified in the research include:

- IndiGo
- Air India
- SpiceJet
- Akasa Air

The actual production eligibility of each source depends on authorization and access conditions.

The research proposes Playwright/headless-browser collection for dynamic booking systems.

## 11.2 OTA Sources

Examples include:

- MakeMyTrip
- Yatra

Again, production use is governed by permissions and source terms.

## 11.3 Government Sources

### DGCA

Purpose:

- passenger volumes
- city-pair route weighting

### MoSPI

Purpose:

- CPI benchmark

### IOCL / PPAC

Purpose:

- ATF prices
- taxation/fuel context

The attached research specifies these sources and their intended roles. 
## 11.4 Commercial APIs

Potentially:

- Amadeus
- other licensed travel APIs

Purpose:

- secondary validation
- development cross-checking

The research specifically suggests commercial API validation.

---

# 12. SOURCE COMPLIANCE MODEL

Every source must have a registry record.

## Source Registry

```text
source_id
name
source_type
access_method
permission_status
tos_status
robots_status
license_status
rate_limit
collection_frequency
enabled
last_reviewed
review_notes
```

## Source States

```text
DISCOVERED
REVIEW_REQUIRED
APPROVED
ACTIVE
DEGRADED
DISABLED
```

## Rule

A source with unresolved permission status must not be automatically enabled for production collection.

---

# 13. COLLECTION ENGINE

## Technology

Primary:

- Python
- Playwright

Optional orchestration:

- Scrapy
- Celery/Redis

The attached research recommends a distributed Python environment using Scrapy and Playwright/Selenium for JavaScript-heavy booking interfaces.

## Collector Responsibilities

1. Receive search job.
2. Verify source eligibility.
3. Create compliant request/session.
4. Search route/date.
5. Capture response.
6. Parse fare information.
7. Validate response structure.
8. Store raw payload.
9. Normalize observations.
10. assign quality score.
11. Persist observation.
12. emit collection metrics.

---

# 14. COLLECTION JOB MODEL

Each collection job contains:

```text
job_id
route_id
source_id
search_date
travel_date
advance_days
passenger_count
cabin
status
created_at
started_at
completed_at
attempt_count
error_code
```

## Advance-Date Calculation

Given:

```text
search_date = S
```

generate:

```text
travel_date = S + 1 day
travel_date = S + 7 days
travel_date = S + 15 days
travel_date = S + 30 days
travel_date = S + 45 days
```

---

# 15. FARE OBSERVATION MODEL

The fundamental analytical entity is:

> **Fare Observation**

Each observation should contain:

```text
observation_id

search_timestamp
travel_date

origin
destination

carrier
flight_number

cabin_class
fare_family
stops

availability_status
inventory_bucket

base_fare
tax_amount
development_fee
convenience_fee
other_mandatory_fees
total_fare

currency

advance_purchase_days

source
source_type

collector_version
schema_version

quality_score
quality_status

raw_payload_reference
```

---

# 16. FARE COMPONENT NORMALIZATION

The system should attempt to separate:

```text
Base Fare
+
Taxes
+
User Development Fee
+
Convenience Charge
+
Other Mandatory Charges
=
Total Consumer Price
```

This structure follows the data fields identified in the research.

## Validation Rule

The system should verify:

```text
total ≈ base + taxes + fees
```

within a configurable tolerance.

If not:

```text
quality_status = WARNING
```

or:

```text
quality_status = REJECTED
```

depending on severity.

---

# 17. AVAILABILITY STATES

Availability must be represented explicitly.

Allowed states:

```text
AVAILABLE
SOLD_OUT
CANCELLED
UNAVAILABLE
SOURCE_ERROR
PARSER_ERROR
UNKNOWN
```

## Critical Rule

```text
SOLD_OUT ≠ ₹0
SOLD_OUT ≠ very high fare
```

Sold-out observations are missing observations for price calculation.

This follows the research requirement that sold-out flights must be treated as unavailable rather than zero.

---

# 18. RAW DATA VS CLEAN DATA

The pipeline must never overwrite raw observations.

```text
RAW
 ↓
PARSED
 ↓
NORMALIZED
 ↓
VALIDATED
 ↓
INDEX-ELIGIBLE
```

Each stage retains lineage.

Example:

```text
raw_payload_id
      ↓
observation_id
      ↓
quality_decision
      ↓
index_value
```

This provides auditability.

---

# 19. DATA QUALITY ENGINE

Every observation receives a quality score.

## Proposed components

```text
Route Validity
Date Validity
Fare Validity
Availability Validity
Fare Decomposition
Duplicate Check
Price Plausibility
Response Completeness
Parser Confidence
Freshness
```

## Example Score

```text
90–100    ACCEPT
70–89     ACCEPT_WITH_WARNING
50–69     REVIEW
0–49      REJECT
```

The scoring rules must be configuration-driven.

---

# 20. DUPLICATE DETECTION

Potential duplicate key:

```text
source
search_date
travel_date
origin
destination
carrier
flight_number
fare_family
cabin_class
total_fare
```

The system should avoid duplicate ingestion while preserving multiple legitimate observations from different search times where appropriate.

---

# 21. OUTLIER HANDLING

Airfares can have large natural variation.

Therefore an observation must not be deleted merely because it is expensive.

The prototype should use:

- route-level distribution
- carrier-level distribution
- robust statistics
- configurable thresholds

Recommended first prototype approach:

### Route-level median

Use median as the primary robust representative price.

Also retain:

- mean
- minimum
- maximum
- standard deviation
- percentile distribution

for diagnostics.

---

# 22. ROUTE BASKET

The route basket should not be arbitrarily selected.

Process:

```text
DGCA passenger traffic
        ↓
rank city pairs
        ↓
select representative basket
        ↓
calculate traffic volumes
        ↓
calculate normalized route weights
```

The research proposes filtering DGCA city-pair scheduled domestic passenger traffic and converting volumes into relative route weights.

## Prototype

Use approximately:

**5–10 routes**

with the exact routes documented and justified.

---

# 23. ROUTE WEIGHTS

For route \(j\):

\[
w_j =
\frac{V_j}
{\sum_{k=1}^{n} V_k}
\]

Where:

- \(V_j\) = passenger volume for route \(j\)
- \(w_j\) = normalized route weight

Validation:

\[
\sum_j w_j = 1
\]

Weights must be versioned.

Example:

```text
weight_version = DGCA_2026_V1
effective_from = YYYY-MM-DD
```

---

# 24. REPRESENTATIVE PRICE

For a given route/date/advance window, calculate:

\[
P_{j,t,h}
\]

where:

- \(j\) = route
- \(t\) = observation date
- \(h\) = advance-purchase window

This is the standardized representative fare.

The initial implementation should support configurable estimators:

```text
MEDIAN
MEAN
TRIMMED_MEAN
WINSORIZED_MEAN
```

Prototype default:

**MEDIAN**

because it reduces sensitivity to extreme airfare observations.

---

# 25. BASE PERIOD

The index needs a clearly defined base period.

Prototype recommendation:

```text
Base Period = first complete validated observation period
```

or a fixed calendar period once enough historical data exists.

The base-period choice must be stored in:

```text
index_versions
```

It must not be hard-coded in application logic.

---

# 26. ROUTE PRICE RELATIVE

For route \(j\):

\[
R_{j,t} =
\frac{P_{j,t}}
{P_{j,0}}
\]

Where:

- \(P_{j,t}\) = current representative route price
- \(P_{j,0}\) = base-period representative route price

---

# 27. AIRFARE PRICE INDEX

Prototype modified Laspeyres formulation:

\[
I_t =
100
\sum_{j=1}^{n}
w_j
R_{j,t}
\]

Where:

- \(I_t\) = airfare index
- \(w_j\) = route weight
- \(R_{j,t}\) = route price relative

Base index:

\[
I_0 = 100
\]

The PRD treats this as the prototype methodology, not as a claim that it is identical to the official MoSPI CPI methodology.

---

# 28. INDEX LEVELS

The system will produce:

## Daily

```text
AIRFARE_INDEX_DAILY
```

## Weekly

```text
AIRFARE_INDEX_WEEKLY
```

## Monthly

```text
AIRFARE_INDEX_MONTHLY
```

## Route-Level

```text
ROUTE_INDEX
```

## Lead-Time-Level

```text
LEAD_TIME_INDEX
```

---

# 29. HANDLING MISSING DATA

Missing observations may occur because:

- flight sold out
- flight cancelled
- route unavailable
- source unavailable
- parser failed
- source schema changed
- no fare returned

These states must be differentiated.

## Rule

Do not automatically substitute:

```text
0
```

for missing observations.

## Recommended prototype behavior

Calculate an index from available valid observations while recording:

```text
coverage_rate
missing_rate
route_coverage
lead_time_coverage
```

If coverage falls below a configurable threshold, flag the resulting index as:

```text
LOW_COVERAGE
```

rather than silently presenting it as normal.

---

# 30. LEAD-TIME ANALYSIS

The product will explicitly compare:

```text
T+45
T+30
T+15
T+7
T+1
```

For each route, calculate representative price by lead time.

Example:

```text
DEL-BOM

T+45  ₹4,000
T+30  ₹4,250
T+15  ₹4,800
T+7   ₹6,100
T+1   ₹9,500
```

These values are illustrative only.

The system must never hard-code the desired result.

---

# 31. LEAD-TIME CURVE

Chart:

```text
Fare
 │
 │                        ● T+1
 │                   ●
 │              ● T+7
 │          ●
 │      ● T+30
 │  ● T+45
 └────────────────────────────
          Advance Purchase
```

The user should be able to:

- select route
- select airline
- select date
- select fare type
- compare periods

---

# 32. MoSPI VALIDATION

The prototype will ingest historical official CPI data from MoSPI/eSankhyiki.

The research identifies the CPI dataset and the Transport and Communication group as the benchmark source.

## Important distinction

The prototype produces daily observations.

The official benchmark may be monthly.

Therefore:

```text
Daily Airfare Index
        ↓
Monthly Aggregation
        ↓
Benchmark Comparison
```

rather than treating a monthly official observation as if it were a daily observation.

---

# 33. VALIDATION METRICS

The validation module should calculate:

## Correlation

\[
r
\]

## Mean Absolute Error

\[
MAE =
\frac{1}{n}
\sum_{t=1}^{n}
|P_t-O_t|
\]

## Root Mean Squared Error

\[
RMSE =
\sqrt{
\frac{1}{n}
\sum_{t=1}^{n}
(P_t-O_t)^2
}
\]

## Directional Accuracy

Percentage of periods where:

```text
sign(ΔPrototype) = sign(ΔOfficial)
```

These statistics should be displayed next to the comparison chart.

---

# 34. 30-DAY BACK-TEST

The core demonstration should contain approximately 30 days of prototype index production.

The system should show:

```text
Prototype daily series
        ↓
monthly aggregation
        ↓
official benchmark comparison
```

The prototype must clearly distinguish:

- historical source data
- live collected observations
- synthetic development data

Synthetic data must never be presented as real historical collection.

---

# 35. DGCA DATA MODULE

The DGCA module imports:

- city pair
- passenger traffic
- period
- route volume

The attached research proposes using the DGCA scheduled domestic passenger traffic report for route weights.

Pipeline:

```text
DGCA file
   ↓
parser
   ↓
route normalization
   ↓
city-pair matching
   ↓
passenger volume
   ↓
weight calculation
   ↓
weight version
```

---

# 36. ATF MODULE

The research recommends an additional ATF data vertical to help analyze fuel-related airfare pressure.

The prototype can ingest:

- ATF price
- location
- date
- source
- tax rate
- duty information

The research identifies IOCL for recent metropolitan ATF prices and PPAC for historical and taxation information.

---

# 37. ATF ANALYTICS

The dashboard may compare:

```text
ATF Price
    vs
Airfare Index
```

and calculate:

- correlation
- rolling correlation
- lagged relationship
- visual comparison

Do not call this causal analysis unless a rigorous econometric methodology has been implemented.

Preferred terminology:

> “Fuel-price relationship”

or:

> “Explanatory decomposition”

rather than:

> “ATF caused X% of airfare inflation”

unless statistically justified.

---

# 38. SYSTEM ARCHITECTURE

## MVP Architecture

```text
                    ┌────────────────────┐
                    │   Source Registry  │
                    └─────────┬──────────┘
                              │
               ┌──────────────┴───────────────┐
               │                              │
       Permitted Web Sources            Licensed APIs
               │                              │
          Playwright                       API Client
               │                              │
               └──────────────┬───────────────┘
                              ↓
                    ┌──────────────────┐
                    │ Collection Engine│
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Raw Data Store   │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Normalizer       │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Quality Engine   │
                    └────────┬─────────┘
                             ↓
                 ┌───────────┴────────────┐
                 │                        │
          DGCA Route Weights        ATF Data
                 │                        │
                 └───────────┬────────────┘
                             ↓
                    ┌──────────────────┐
                    │ Index Engine     │
                    └────────┬─────────┘
                             ↓
              ┌──────────────┴─────────────┐
              ↓                            ↓
        FastAPI Backend              Dashboard
```

---

# 39. RECOMMENDED TECHNOLOGY STACK

## Backend

**Python + FastAPI**

Reason:

- easy API development
- good data-science ecosystem
- strong Pydantic validation
- easy LLM-assisted development

## Collection

**Python + Playwright**

For JavaScript-rendered permitted sources.

## Orchestration

MVP:

**APScheduler / simple scheduler**

Scalable:

**Celery + Redis**

Optional:

**Scrapy**

## Database

**PostgreSQL + TimescaleDB**

Reason:

- relational integrity
- SQL analytics
- time-series optimization
- mature ecosystem

## Data Processing

**Polars/Pandas**

## Statistical Processing

**NumPy**
**SciPy**
**statsmodels**

## Frontend

**Next.js / React**

## Visualization

**Plotly / ECharts**

## Infrastructure

**Docker + Docker Compose**

## Monitoring

MVP:

**structured logging + application metrics**

Scalable:

**Prometheus + Grafana**

---

# 40. DATABASE SCHEMA

## 40.1 sources

```text
id
name
type
access_method
permission_status
tos_status
robots_status
license_status
rate_limit
enabled
last_reviewed_at
created_at
updated_at
```

## 40.2 routes

```text
id
origin
destination
origin_airport
destination_airport
route_code
active
created_at
```

## 40.3 airlines

```text
id
code
name
active
```

## 40.4 fare_observations

```text
id
source_id
route_id
airline_id

search_timestamp
travel_date
advance_purchase_days

flight_number
cabin_class
fare_family
stops

availability_status

base_fare
tax_amount
development_fee
convenience_fee
other_fee
total_fare
currency

quality_score
quality_status

collector_version
schema_version

raw_payload_id

created_at
```

## 40.5 raw_payloads

```text
id
source_id
collection_job_id
payload_uri
payload_hash
content_type
captured_at
```

## 40.6 route_weights

```text
id
route_id
passenger_volume
weight
source
period
methodology_version
effective_from
effective_to
```

## 40.7 collection_jobs

```text
id
route_id
source_id
search_date
travel_date
advance_days
status
attempt_count
started_at
completed_at
error_code
error_message
```

## 40.8 index_values

```text
id
index_type
period_start
period_end
route_id
index_value
coverage_rate
methodology_version
weight_version
calculated_at
```

## 40.9 benchmark_values

```text
id
period
indicator
value
source
source_version
```

## 40.10 validation_results

```text
id
period_start
period_end
correlation
mae
rmse
directional_accuracy
prototype_series_version
benchmark_version
created_at
```

## 40.11 atf_prices

```text
id
location
date
price_per_kl
source
```

## 40.12 atf_tax_rates

```text
id
effective_from
effective_to
tax_type
rate
source
```

## 40.13 methodology_versions

```text
id
version
name
base_period
price_estimator
missing_data_method
outlier_method
weight_method
formula
effective_from
notes
```

---

# 41. INDEX VERSIONING

Every index value must be associated with:

```text
methodology_version
weight_version
data_snapshot_version
```

Example:

```text
Methodology: APIX-1.0
Weights: DGCA-2026-Q1
Data Snapshot: 2026-09-03T18:00
```

This prevents unexplained revisions.

---

# 42. API REQUIREMENTS

## GET /api/v1/index

Returns current index.

Example:

```json
{
  "index": 108.42,
  "daily_change": 1.72,
  "weekly_change": 3.81,
  "monthly_change": 6.10,
  "coverage_rate": 94.6,
  "methodology_version": "APIX-1.0"
}
```

## GET /api/v1/index/daily

Query:

```text
from
to
```

Returns daily time series.

## GET /api/v1/index/monthly

Returns monthly index.

## GET /api/v1/routes

Returns route basket.

## GET /api/v1/routes/{route_id}

Returns route analytics.

## GET /api/v1/routes/{route_id}/index

Returns route index.

## GET /api/v1/routes/{route_id}/lead-time

Returns T+45/T+30/T+15/T+7/T+1 data.

## GET /api/v1/weights

Returns current and historical weights.

## GET /api/v1/validation

Returns benchmark comparison.

## GET /api/v1/data-quality

Returns data-quality metrics.

## GET /api/v1/source-health

Returns source status.

## GET /api/v1/methodology

Returns methodology metadata.

---

# 43. DASHBOARD

The dashboard should resemble a **statistical observatory**, not a generic admin panel.

---

## SCREEN 1 — NATIONAL OVERVIEW

Display:

```text
INDIA AIRFARE PRICE INDEX

108.42

+1.72% Today
+3.81% 7D
+6.10% 30D

Coverage
94.6%

Routes
10

Valid Quotes Today
12,482
```

Main chart:

**Daily Airfare Index**

---

# 44. SCREEN 2 — ROUTE HEATMAP

Columns:

```text
Route
Current Index
1D
7D
30D
Coverage
```

Example:

```text
DEL-BOM   111.4   +1.2   +4.7   +8.1
DEL-BLR   108.7   +0.8   +3.5   +5.2
BOM-BLR   104.2   -0.4   +1.1   +3.8
```

---

# 45. SCREEN 3 — ROUTE DETAIL

Display:

- current representative fare
- historical price
- price distribution
- carriers
- fare families
- availability
- lead-time curve
- source coverage

---

# 46. SCREEN 4 — LEAD-TIME ELASTICITY

Controls:

```text
Route
Date
Carrier
Fare Class
```

Chart:

```text
Fare
│
│              ●
│         ●
│      ●
│   ●
│ ●
└──────────────────
 T+45          T+1
```

Show actual observed values.

---

# 47. SCREEN 5 — VALIDATION

Two-series chart:

```text
Prototype Index
Official Benchmark
```

Metrics:

```text
Correlation
MAE
RMSE
Directional Accuracy
```

Add a methodological note:

> “Prototype series is independently constructed from collected fare observations and aggregated to the benchmark reporting frequency.”

---

# 48. SCREEN 6 — DATA QUALITY

Cards:

```text
Valid Quotes
Rejected Quotes
Missing
Duplicate
Low Coverage
Parser Warnings
```

Chart:

**Coverage over time**

---

# 49. SCREEN 7 — SOURCE HEALTH

For every source:

```text
Source
Status
Success Rate
Valid Fare Rate
Latency
Last Successful Run
Schema Version
```

Statuses:

```text
HEALTHY
WARNING
DEGRADED
DOWN
DISABLED
```

---

# 50. SCREEN 8 — ATF ANALYTICS

Display:

```text
ATF Price
Airfare Index
```

with synchronized dates.

Optional:

```text
Rolling Correlation
```

---

# 51. SCREEN 9 — METHODOLOGY

This page is critical for government/statistics users.

Display:

- basket
- weights
- base period
- price estimator
- missing-data method
- outlier method
- index formula
- data sources
- source coverage
- methodology version

The user should be able to answer:

> “How did you calculate this number?”

without reading the source code.

---

# 52. SOURCE HEALTH SYSTEM

Every collection run should emit:

```text
collection_started
collection_completed
collection_failed
parser_failed
schema_changed
empty_response
permission_blocked
```

Metrics:

```text
collection_success_rate
valid_quote_rate
empty_response_rate
parser_error_rate
latency
last_successful_run
```

---

# 53. OBSERVABILITY

Minimum metrics:

```text
collection_jobs_total
collection_jobs_success
collection_jobs_failed

quotes_total
quotes_valid
quotes_rejected

source_latency
parser_errors
schema_errors

index_calculation_duration

api_latency
api_error_rate
```

---

# 54. ERROR HANDLING

Errors must be classified.

Example:

```text
SOURCE_UNAVAILABLE
PERMISSION_DENIED
TIMEOUT
PARSER_ERROR
SCHEMA_CHANGED
NO_RESULTS
INVALID_FARE
DATABASE_ERROR
UNKNOWN
```

Do not silently retry forever.

Use bounded retry policies.

---

# 55. SECURITY REQUIREMENTS

## Secrets

All secrets must be supplied through:

```text
.env
```

or secure deployment secrets.

Never commit:

- API keys
- database passwords
- tokens
- credentials

## Access

Administrative functions should be protected.

Public statistical API endpoints can be read-only.

## Data Privacy

Only necessary fare information should be collected.

Do not retain unnecessary personal/user information.

---

# 56. LLM / VIBE-CODING DEVELOPMENT PRINCIPLES

The system will be built through incremental LLM-assisted development.

## Rule 1

Never ask an LLM to build the complete system in one task.

## Rule 2

Build one vertical slice at a time.

## Rule 3

Every coding prompt should define:

```text
Context
Task
Files
Interfaces
Constraints
Acceptance Criteria
Tests
Expected Output
```

## Rule 4

The coding agent must inspect the existing repository before modifying code.

## Rule 5

The coding agent must not silently alter statistical formulas.

## Rule 6

Statistical logic must have deterministic tests.

## Rule 7

Every major module must have an owner/interface.

## Rule 8

Dependencies must be justified before addition.

## Rule 9

Raw observations must remain auditable.

## Rule 10

The LLM must not invent unavailable source data.

---

# 57. RECOMMENDED DEVELOPMENT REPOSITORY

```text
airfare-index/
│
├── apps/
│   ├── api/
│   └── dashboard/
│
├── services/
│   ├── collectors/
│   ├── scheduler/
│   └── index-engine/
│
├── packages/
│   ├── schemas/
│   ├── statistics/
│   └── shared/
│
├── database/
│   └── migrations/
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── reference/
│   └── synthetic/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── statistical/
│   └── e2e/
│
├── scripts/
│
├── docs/
│
├── docker-compose.yml
├── .env.example
├── README.md
└── Makefile
```

---

# 58. PHASED DEVELOPMENT ROADMAP

# PHASE 0 — FOUNDATION

### Objective

Create a stable development environment.

### Tasks

- Git repository
- Python environment
- frontend project
- Docker
- PostgreSQL
- database migrations
- environment variables
- basic CI
- code formatting
- linting

### Output

The application starts locally.

### Acceptance Criteria

```text
docker compose up
```

starts:

- database
- backend
- frontend

---

# PHASE 1 — SYNTHETIC DATA + STATISTICAL CORE

### Objective

Prove that the statistical engine works without any scraping.

### Build

- routes
- fare observation schema
- synthetic data generator
- normalization
- quality engine
- route weights
- representative fare calculation
- price relatives
- Laspeyres index
- daily aggregation

### Critical Deliverable

```text
Synthetic Fare Data
        ↓
Index Engine
        ↓
Daily Index
```

### Acceptance Criteria

Given a deterministic dataset, the index engine produces a known expected result.

---

# PHASE 2 — SOURCE REGISTRY + COLLECTION FRAMEWORK

### Objective

Build the generic data-acquisition architecture.

### Build

- source registry
- source eligibility
- connector interface
- scheduler
- collection jobs
- logging
- retries
- raw payload storage
- collector health

### Acceptance Criteria

A test connector can insert observations through the full pipeline.

---

# PHASE 3 — LIVE/PERMITTED FARE COLLECTION

### Objective

Connect one or more real/authorized data sources.

### Build

- first permitted connector
- route scheduler
- five lead-time searches
- parser
- normalization
- fare component extraction
- availability detection
- quality engine

### Acceptance Criteria

Daily real observations enter the production schema.

---

# PHASE 4 — DGCA WEIGHTS

### Objective

Replace development weights with traffic-derived weights.

### Build

- DGCA ingestion
- city-pair normalization
- volume calculation
- route matching
- weight generation
- versioning

### Acceptance Criteria

Sum of active route weights = 1.

---

# PHASE 5 — DAILY AIRFARE INDEX

### Objective

Create the main product metric.

### Build

- daily route index
- national index
- coverage calculation
- missing-data treatment
- revision metadata

### Acceptance Criteria

Dashboard can display a valid daily index.

---

# PHASE 6 — DASHBOARD

### Objective

Create judge-ready visualization.

### Build

- overview
- national index chart
- route heatmap
- route detail
- lead-time curve
- data quality
- source health

### Acceptance Criteria

A judge can understand the product without opening the database.

---

# PHASE 7 — MoSPI VALIDATION

### Objective

Demonstrate statistical credibility.

### Build

- benchmark ingestion
- monthly aggregation
- comparison chart
- correlation
- MAE
- RMSE
- directional accuracy

### Acceptance Criteria

Dashboard shows prototype versus official benchmark.

---

# PHASE 8 — ATF ANALYTICS

### Objective

Add macro/fuel context.

### Build

- ATF ingestion
- historical time series
- chart
- relationship metrics
- taxation metadata

### Acceptance Criteria

User can compare airfare and ATF movements.

---

# PHASE 9 — API

### Objective

Expose the system to external consumers.

### Build

- versioned API
- schemas
- documentation
- route endpoints
- index endpoints
- validation endpoints
- metadata endpoints

### Acceptance Criteria

API returns documented structured results.

---

# PHASE 10 — HARDENING

### Objective

Make the prototype reliable.

### Build

- test suite
- structured logging
- monitoring
- source health
- error handling
- database optimization
- backup
- documentation

---

# PHASE 11 — OPTIONAL ML

Only after the statistical system is stable.

Possible features:

- price anomaly detection
- fare forecasting
- booking-pressure score
- route-demand inference
- price-change probability

ML must not be allowed to interfere with the core official-style index calculation.

---

# 59. PRIORITY MATRIX

## P0 — Must Have

- database
- fare observation schema
- source registry
- collection framework
- five lead-time windows
- data cleaning
- sold-out handling
- route weights
- index engine
- daily index
- dashboard
- validation
- API
- data-quality monitoring

## P1 — Important

- ATF integration
- source health
- weekly/monthly index
- route analytics
- methodology page

## P2 — Enhancement

- anomaly detection
- advanced API filters
- historical comparisons
- more routes

## P3 — Future

- ML forecasting
- commercial subscriptions
- alerts
- large-scale route coverage

---

# 60. USER STORIES

## US-001

As a government analyst, I want to see the current airfare index so that I can understand current airfare pressure.

## US-002

As a statistician, I want to inspect route weights so that I can understand how the national index was constructed.

## US-003

As a researcher, I want to see T+45 to T+1 fares so that I can study booking-time price behavior.

## US-004

As a data engineer, I want to know when a source stops producing valid data so that bad observations do not enter the index.

## US-005

As a statistician, I want sold-out flights to be treated as missing rather than zero so that the index is not artificially distorted.

## US-006

As a researcher, I want monthly aggregation so that I can compare the prototype with monthly official statistics.

## US-007

As an analyst, I want to inspect route-level contribution so that I can understand changes in the national index.

## US-008

As an analyst, I want to inspect fare components so that I can distinguish base fares from taxes and fees.

## US-009

As a data engineer, I want raw observations retained so that index values remain auditable.

## US-010

As a statistician, I want methodology versions so that historical index values remain reproducible.

## US-011

As a researcher, I want to compare ATF prices with airfare so that I can investigate fuel-price relationships.

## US-012

As an API consumer, I want to retrieve daily index values programmatically.

## US-013

As an analyst, I want to inspect data coverage before using the index.

## US-014

As a developer, I want connector interfaces to be standardized so that new sources can be added without rewriting the core system.

## US-015

As an analyst, I want benchmark statistics so that I can evaluate whether the prototype tracks the official series.

## US-016

As a developer, I want deterministic statistical tests so that future code changes do not silently alter the index.

## US-017

As a user, I want to know whether a source is healthy so that I can judge confidence in today's data.

## US-018

As an administrator, I want to disable a source without changing the statistical engine.

## US-019

As a researcher, I want to compare airlines on a common route.

## US-020

As a government analyst, I want a methodology page that explains the index without reading source code.

---

# 61. TESTING STRATEGY

# Unit Testing

Test:

- lead-date calculation
- route normalization
- fare parsing
- fare decomposition
- availability
- duplicate detection
- quality score
- weight calculation
- index calculation

# Statistical Testing

Create deterministic fixtures:

```text
known route prices
known weights
known expected index
```

Example:

```text
Route A = 100
Route B = 120
Weight A = 0.6
Weight B = 0.4

Expected index =
100 × (0.6×1 + 0.4×1.2)
= 108
```

The test must verify exactly 108.

# Integration Testing

Test:

```text
collector
→ parser
→ database
→ quality
→ index
→ API
```

# E2E

Test:

```text
synthetic dataset
→ backend
→ API
→ dashboard
```

---

# 62. DATA QUALITY TEST CASES

Test cases must include:

### Valid fare

Expected:

```text
ACCEPT
```

### Sold-out flight

Expected:

```text
MISSING_FOR_INDEX
```

### Negative price

Expected:

```text
REJECT
```

### Missing route

Expected:

```text
REJECT
```

### Total ≠ components

Expected:

```text
WARNING / REJECT
```

### Duplicate observation

Expected:

```text
DEDUPLICATED
```

### Extreme but valid price

Expected:

```text
REVIEW
```

not automatic deletion.

### Source unavailable

Expected:

```text
SOURCE_ERROR
```

not:

```text
fare = 0
```

---

# 63. COLLECTION FAILURE POLICY

Suppose a source fails.

The system must:

1. Record failure.
2. Retry according to policy.
3. Mark source health.
4. Do not fabricate fare.
5. Continue other sources.
6. Calculate coverage.
7. Flag low-confidence index where necessary.

---

# 64. SCHEMA DRIFT

If a source changes its response structure:

```text
schema validation
       ↓
failure
       ↓
schema-change event
       ↓
connector marked DEGRADED
       ↓
engineering alert
```

The system must not silently parse wrong fields.

---

# 65. API QUALITY REQUIREMENTS

API must:

- return valid JSON
- use consistent schemas
- provide HTTP status codes
- validate parameters
- include methodology version
- include data coverage where relevant
- provide timestamps

---

# 66. DASHBOARD NON-FUNCTIONAL REQUIREMENTS

The dashboard should:

- load core metrics quickly
- have responsive layout
- support desktop demo resolution
- have accessible labels
- support date filtering
- provide clear units
- distinguish missing data visually
- expose methodology context

---

# 67. PERFORMANCE TARGETS

These are proposed prototype targets, not official requirements.

### API

Typical query:

```text
< 1 second
```

for cached/index data.

### Dashboard

Core overview:

```text
< 2 seconds
```

under normal local/cloud prototype conditions.

### Collection

Jobs should run asynchronously.

A failed source should not block unrelated routes.

---

# 68. SCALABILITY

The architecture should allow:

```text
10 routes
   ↓
50 routes
   ↓
100 routes
   ↓
500+ routes
```

without rewriting:

- index engine
- data model
- API architecture

Scaling should mainly involve:

- more workers
- better queueing
- better storage
- additional connectors

---

# 69. DATA RETENTION

Recommended:

### Raw payloads

Long-term retention where licensing allows.

### Clean observations

Long-term analytical retention.

### Index values

Permanent versioned retention.

### Logs

Configurable operational retention.

Retention policies must follow source/license constraints.

---

# 70. VERSION CONTROL

Use Git.

Suggested:

```text
main
develop
feature/*
fix/*
```

Every statistical methodology change must appear in a dedicated commit/PR description.

Example:

```text
feat(index): introduce APIX-1.1 trimmed mean estimator
```

---

# 71. CODE QUALITY

Use:

- type hints
- Pydantic
- Ruff/Black
- meaningful function names
- small modules
- dependency injection where useful
- tests for statistical logic
- structured logging

Avoid:

- giant scripts
- hidden global state
- hard-coded routes
- hard-coded weights
- hard-coded dates
- statistical magic numbers

---

# 72. CONFIGURATION

Configuration should be externalized.

Example:

```yaml
index:
  base_period: "2026-08-01"
  representative_estimator: "median"

collection:
  windows:
    - 1
    - 7
    - 15
    - 30
    - 45

quality:
  minimum_score: 70
```

Do not embed these directly inside business logic.

---

# 73. MVP ACCEPTANCE CRITERIA

The MVP is considered successful when:

### A.

At least one permitted/usable source provides real observations.

### B.

The system supports all five lead-time windows.

### C.

Fare observations are stored in a normalized schema.

### D.

Sold-out observations are not treated as zero-price observations.

### E.

Route weights can be loaded from DGCA-derived data.

### F.

The system produces a daily airfare index.

### G.

The system produces weekly and monthly aggregation.

### H.

A dashboard displays the index.

### I.

The dashboard displays a lead-time curve.

### J.

The system displays data quality.

### K.

The system displays source health.

### L.

The system compares its aggregated series against an official benchmark.

### M.

The API exposes index data.

### N.

All major statistical calculations have automated tests.

---

# 74. SIH DEMO ACCEPTANCE CRITERIA

The live demo must be capable of showing:

## 1. Current Index

Example placeholder:

```text
108.42
```

## 2. 30-Day Series

```text
Day 1 → Day 30
```

## 3. Official Benchmark

Comparison at the appropriate reporting frequency.

## 4. Lead-Time Curve

```text
T+45
T+30
T+15
T+7
T+1
```

## 5. Route Contribution

Explain why the index moved.

## 6. Data Quality

Show actual collection coverage.

## 7. Methodology

Explain the calculation.

---

# 75. JUDGE DEMO SCRIPT

## 0:00–0:45

Explain the problem.

> “Airfare is highly dynamic, but conventional low-frequency observation cannot fully capture what an online consumer is quoted throughout the booking horizon.”

## 0:45–1:30

Show collection.

> “We collect standardized observations across representative routes and five booking horizons.”

## 1:30–2:30

Show index.

> “These observations are cleaned, normalized and weighted according to passenger traffic.”

## 2:30–3:30

Show lead-time curve.

> “This allows us to observe how the same journey changes in price as departure approaches.”

## 3:30–4:30

Show validation.

> “We aggregate our high-frequency series and compare it against the published benchmark.”

## 4:30–5:15

Show source/data-quality monitoring.

> “The system also knows when its data is unreliable.”

## 5:15–6:00

Show API.

> “The index is available programmatically for downstream statistical users.”

---

# 76. THE “WOW” FEATURE

The signature feature is:

## Lead-Time Elasticity

The user selects:

```text
DEL → BOM
```

and sees:

```text
T+45     ₹4,000
T+30     ₹4,200
T+15     ₹4,900
T+7      ₹6,100
T+1      ₹9,800
```

The system then calculates:

```text
T+1 / T+45 = 2.45×
```

This should be dynamically calculated from actual observations.

---

# 77. “WHY DID AIRFARES RISE?” ANALYTICS

Future/advanced dashboard feature.

Example:

```text
National Index
     +4.7%

Route Contribution       +2.3%
Lead-Time Effect         +1.2%
Carrier Mix              +0.6%
Fuel Relationship        +0.4%
Other                    +0.2%
```

Every contribution needs a documented calculation.

Do not generate arbitrary explanatory percentages.

---

# 78. DATA LINEAGE

Every published index must be traceable.

```text
Index
 ↓
Route indices
 ↓
Representative prices
 ↓
Clean fare observations
 ↓
Raw payload
 ↓
Source
```

API response should optionally expose:

```text
data_snapshot
methodology_version
weight_version
```

---

# 79. DOCUMENTATION REQUIREMENTS

The repository must include:

### README

How to run project.

### ARCHITECTURE.md

System architecture.

### DATA_MODEL.md

Database schema.

### METHODOLOGY.md

Statistical methodology.

### SOURCES.md

Source registry and permissions.

### RESEARCH.md

Research material: index methodology benchmarks, competitor landscape, academic literature, scraping/anti-bot & legal landscape, India regulatory context, USP & roadmap, with all source links.

### API.md

API documentation.

### DEMO.md

How to reproduce the SIH demo.

### CONTRIBUTING.md

Development process.

---

# 80. RISK REGISTER

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| Source ToS restriction | High | Very High | Compliance-first source registry |
| Source outage | Medium | High | Multiple sources |
| Schema change | High | High | Schema validation + monitoring |
| Anti-bot change | High | High | Authorized alternatives |
| Missing fares | High | High | Explicit missing-data methodology |
| Bad fare parsing | Medium | High | Quality engine |
| Incorrect weights | Medium | High | Versioned DGCA workflow |
| Benchmark mismatch | Medium | High | Document frequency/base differences |
| Insufficient 30-day history | High | Very High | Start collection immediately |
| Database growth | Low | Medium | TimescaleDB |
| LLM-generated bugs | Medium | High | Tests + incremental implementation |
| Statistical methodology drift | Medium | Very High | Versioned methodology |
| Synthetic data mistaken for real data | Medium | Very High | Explicit provenance flags |

---

# 81. BIGGEST PROJECT RISKS

## Risk 1 — Data Access

This is the largest external dependency.

The system must remain useful even if one source becomes unavailable.

## Risk 2 — Calendar

The 30-day demonstration requires real historical collection time.

Therefore collection should begin immediately.

## Risk 3 — Missing Data

A missing fare must not be converted into a high or zero price.

## Risk 4 — Statistical Credibility

A beautiful dashboard cannot compensate for a weak methodology.

## Risk 5 — Silent Collector Failure

A scraper that appears healthy but returns empty/bad data is more dangerous than an obvious failure.

---

# 82. COMMERCIALIZATION

The hackathon product can evolve into:

# INDIA AIRFARE INTELLIGENCE PLATFORM

Potential products:

### Airfare Index API

For:

- researchers
- institutions
- financial companies
- government

### Airline Competitive Intelligence

For:

- airline analysts
- pricing teams

### OTA Intelligence

For:

- travel platforms

### Route Intelligence

For:

- airports
- airlines
- investors

### Research Data

Historical cleaned observations as licensed datasets.

---

# 83. BUSINESS MODELS

Potential models:

## SaaS

Monthly dashboard subscription.

## API Licensing

Subscription based on:

- requests
- data coverage
- features

## Enterprise Analytics

Custom analytical deployments.

## Institutional/Government Licensing

Private deployments.

## Research Reports

Periodic airfare intelligence reports.

These are potential models, not validated revenue forecasts.

---

# 84. FUTURE MOAT

The long-term defensibility is not the scraper.

It is:

```text
Historical observations
+
Cleaned data
+
Route weights
+
Methodology
+
Longitudinal index
+
Lead-time patterns
+
Event intelligence
```

After sufficient accumulation, the system becomes a historical airfare intelligence database.

---

# 85. FUTURE MACHINE LEARNING

Once enough historical observations exist:

## Fare Forecast

Predict expected T+7/T+15/T+30 pricing.

## Anomaly Detection

Identify unusually high fares.

## Event Detection

Detect unusual national or route-level shocks.

## Price Increase Probability

Estimate probability of future fare increases.

## Booking Recommendation

Potential future consumer-facing product:

> “Current fare is below the historical range for this lead time.”

ML is intentionally secondary to the core statistical index.

---

# 86. DEFINITION OF DONE

A feature is complete only when:

- code exists
- acceptance criteria pass
- tests exist
- error handling exists
- logging exists
- documentation exists
- configuration is externalized
- no credentials are committed
- API schemas are documented where applicable

---

# 87. DEFINITION OF DONE — COLLECTOR

A collector is complete only when:

- source is registered
- permission status is documented
- input parameters are validated
- responses are logged
- raw payload is stored
- normalized observations are produced
- sold-out handling exists
- parser errors are surfaced
- retries are bounded
- health metrics are emitted
- integration tests pass

---

# 88. DEFINITION OF DONE — STATISTICAL ENGINE

Complete only when:

- formulas are documented
- deterministic tests exist
- base period is configurable
- route weights are versioned
- missing observations are documented
- outliers are traceable
- results are reproducible
- methodology version is persisted

---

# 89. DEFINITION OF DONE — DASHBOARD

Complete only when:

- all P0 screens are available
- API is connected
- empty/error states are handled
- loading states exist
- data timestamps are shown
- methodology is accessible
- charts use real backend data

---

# 90. DEVELOPMENT ORDER

The correct implementation order is:

```text
1. Foundation
        ↓
2. Database
        ↓
3. Synthetic fare model
        ↓
4. Index engine
        ↓
5. API
        ↓
6. Dashboard
        ↓
7. Source registry
        ↓
8. First permitted collector
        ↓
9. DGCA weights
        ↓
10. MoSPI validation
        ↓
11. ATF
        ↓
12. Monitoring
        ↓
13. Scale
```

Do not reverse this by starting with complex web scraping.

---

# 91. FIRST 10 ENGINEERING TASKS

## TASK 1

Initialize monorepo and development tooling.

## TASK 2

Create Docker Compose with:

- PostgreSQL/TimescaleDB
- FastAPI
- Next.js

## TASK 3

Implement database migrations.

## TASK 4

Create:

```text
routes
airlines
fare_observations
route_weights
index_values
methodology_versions
```

## TASK 5

Build a deterministic synthetic fare generator.

## TASK 6

Implement fare normalization and quality engine.

## TASK 7

Implement route-weight calculation.

## TASK 8

Implement index engine.

## TASK 9

Expose:

```text
GET /api/v1/index
GET /api/v1/routes
GET /api/v1/routes/{route_id}/lead-time
```

## TASK 10

Build the first dashboard screen:

```text
National Index
+
30-day chart
+
Coverage
```

---

# 92. FIRST DEVELOPMENT MILESTONE

The first milestone is intentionally independent of live scraping.

It must achieve:

```text
Synthetic Fare Dataset
          ↓
Normalization
          ↓
Quality Engine
          ↓
Route Weights
          ↓
Index Engine
          ↓
FastAPI
          ↓
Dashboard
```

### Success condition

A developer can run:

```bash
docker compose up
```

and see a working airfare index generated from reproducible synthetic observations.

---

# 93. SECOND DEVELOPMENT MILESTONE

Add the first permitted real data source.

The system should then become:

```text
Real Source
    ↓
Collector
    ↓
Raw Payload
    ↓
Fare Observation
    ↓
Quality Engine
    ↓
Index
    ↓
Dashboard
```

Synthetic data remains available for testing.

---

# 94. THIRD DEVELOPMENT MILESTONE

Replace development route weights with DGCA-derived route weights.

Add:

```text
DGCA import
→ route matching
→ passenger volume
→ weights
```

---

# 95. FOURTH DEVELOPMENT MILESTONE

Add:

```text
MoSPI benchmark
→ monthly aggregation
→ validation
→ correlation/MAE/RMSE
```

At this point the product becomes SIH-demo-ready.

---

# 96. FINAL MVP DEFINITION

The MVP is:

> **A compliance-aware, automated Indian airfare observation platform that collects permitted fare data across representative domestic routes and five advance-purchase windows, standardizes and validates observations, calculates a DGCA-weighted daily airfare index, aggregates it to monthly frequency, compares it against an official MoSPI benchmark, and visualizes route-level, lead-time and data-quality behavior through a web dashboard and API.**

---

# 97. WHAT THE PRODUCT IS NOT

It is not:

> “a scraper that collects as many fares as possible.”

It is not:

> “a flight booking website.”

It is not:

> “an AI prediction engine.”

It is not:

> “a dashboard on top of random airline prices.”

It is:

> **a measurement system for airfare inflation.**

---

# 98. STRATEGIC POSITIONING

The product should be positioned as:

## India Airfare Price Observatory

### Input

High-frequency airfare observations.

### Intelligence

Statistical normalization + consumer weighting.

### Output

Transparent airfare inflation indicators.

### Validation

Official statistical benchmark.

### Differentiator

India-specific route weighting + lead-time analysis + auditability.

---

# 99. FINAL PRODUCT ARCHITECTURE

```text
                         INDIA AIRFARE
                       PRICE OBSERVATORY
                              │
       ┌──────────────────────┼─────────────────────┐
       │                      │                     │
   Fare Sources           Government Data       Macro Data
       │                      │                     │
 Airlines / OTAs         DGCA / MoSPI           ATF / PPAC
 APIs / feeds                 │                     │
       │                      │                     │
       └───────────────┬──────┴─────────────┬───────┘
                       ↓                    ↓
                COLLECTION LAYER      REFERENCE DATA
                       │
                       ↓
                  RAW STORAGE
                       │
                       ↓
                NORMALIZATION
                       │
                       ↓
                 DATA QUALITY
                       │
                       ↓
                FARE OBSERVATORY
                       │
                       ↓
                STATISTICAL ENGINE
                       │
              ┌────────┼─────────┐
              │        │         │
           ROUTE     LEAD-TIME   NATIONAL
           INDEX       INDEX      INDEX
              │        │         │
              └────────┼─────────┘
                       ↓
                VALIDATION ENGINE
                       │
              ┌────────┴─────────┐
              ↓                  ↓
         DASHBOARD              API
              │
        ┌─────┼──────┐
        ↓     ↓      ↓
      Trends Routes  Lead-Time
        ↓     ↓      ↓
     Quality Health Validation
```

---

# 100. FINAL RECOMMENDATION

The development team should **not begin with scraping**.

The recommended sequence is:

> **Statistical core → synthetic end-to-end pipeline → dashboard/API → source framework → real collection → DGCA weights → MoSPI validation → ATF → scale.**

This significantly reduces project risk.

The core intellectual property of the prototype should remain independent of the collection mechanism.

That means if one airline/OTA source disappears tomorrow, the system should still work with another permitted source.

The most important engineering principle is:

> **The scraper is replaceable. The measurement methodology is the product.**

The most important demonstration principle is:

> **Don't merely show that you collected fares. Show that those observations produce a defensible statistical signal.**

The final SIH story should therefore be:

```text
We observe
      ↓
We standardize
      ↓
We validate
      ↓
We weight
      ↓
We calculate
      ↓
We explain
      ↓
We compare with official statistics
```

That is the product.