# Statistical Methodology & Mathematical Formulation (APIX-2.0 / APIX-2.1)

> Official Methodology Documentation for the India Airfare Price Observatory (MoSPI / NSO).

---

## 1. Mathematical Index Formulation (Hybrid Laspeyres–Jevons)

The daily **India Airfare Price Index** ($I_t$) is computed using a **two-stage hybrid
Laspeyres–Jevons** formulation (IMF CPI Manual 2020, Chapter 10 — Elementary Aggregates;
ONS used-price web-scraping guidance). Fares are aggregated **geometrically (Jevons) within
each route–horizon cell** to handle the price dispersion observed across carriers, then the
cell means are combined **arithmetically with Laspeyres weights** across the DGCA-weighted
route basket:

$$I_t = 100 \times \sum_{j=1}^{M} w_j \times \left( \frac{P_{j,t,T+15}}{P_{j,0,T+15}} \right)$$

Where:
- $I_t$: National headline airfare price index on observation day $t$.
- $w_j$: Fixed normalized passenger volume weight for domestic route corridor $j$ (source: DGCA domestic scheduled traffic), satisfying $\sum_{j=1}^{M} w_j = 1.000000 \pm 10^{-6}$.
- $P_{j,t,T+15}$: **Jevons cell mean** — the geometric mean of carrier-level lowest basic
  economy fares on route corridor $j$ on observation date $t$ anchored at **$T+15$** advance
  purchase (elementary aggregate, see §1.1).
- $P_{j,0,T+15}$: Base period representative airfare on route corridor $j$ (Base Period: August 1, 2026 = 100.00).
- $M$: Number of monitored corridors in the basket ($M=10$).

### 1.1 Elementary Aggregates: Jevons Geometric Mean (IMF CPI Manual 2020, Ch.10)

At the elementary route–horizon cell level — the level at which individual fare quotes are
collected — prices are aggregated with the **Jevons geometric mean** rather than an
arithmetic mean. This is the IMF-recommended choice for web-scraped price data and is the
approach the UK ONS applies to its online item indices:

$$P_{j,t,h} = \left( \prod_{c \in \text{Airlines}(j)} P_{j,t,h,c} \right)^{1/N} = \exp\left( \frac{1}{N} \sum_{c \in \text{Airlines}(j)} \ln P_{j,t,h,c} \right)$$

Where $P_{j,t,h,c}$ is carrier $c$'s lowest available basic economy fare on corridor $j$,
horizon $h$, date $t$, and $N = |\text{Airlines}(j)|$.

**Why this matters for statistical credibility:**
1. **Price-dispersion robustness.** Geometric means are invariant to the *direction* of
   relative price changes and are less affected by high-priced outliers than arithmetic
   means — important because cross-carrier dispersion on a single corridor is routinely large
   (e.g. a full-service carrier at ₹6,900 alongside an LCC at ₹5,060).
2. **No unit-value bias.** With arithmetic elementary aggregates, a single expensive
   carrier mechanically inflates the cell price. The geometric mean avoids this upward
   unit-value bias while remaining a legitimate index-number formula (Jevons 1863; IMF CPI
   Manual 2020 §7–10).
3. **Consistency with the Laspeyres upper level.** By chaining a geometric elementary
   stage to a weighted arithmetic index stage, the Observatory obtains the ONS's recommended
   "Jevons-within-cell, Laspeyres-across-cell" hybrid for official analytics.

**Implementation.** `RepresentativePriceEstimator.estimate_route_price(estimator="JEVONS")`
(`packages/statistics/estimators.py`) computes the geometric mean of outlier-filtered,
per-carrier minimum basic-economy fares; `DailyIndexCalculatorService` feeds those cell
means into the Laspeyres aggregation in `AirfareIndexEngine`.

### 1.2 Dual-Series Architecture: HEADLINE vs CORE (v2.1)

The index is published as **two companion series** so a statistically valid base reference is
never silently contaminated by India's dense festival/holiday calendar:

- **HEADLINE** — the raw all-feed Laspeyres series. The market's fastest readout; every valid
  travel date contributes, including peak weekends.
- **CORE** — the **festival-guarded continuity series**. A travel date whose price model would
  fall on a festival window (e.g. the **Independence Day long-weekend window** containing
  August 16) is treated as structurally unrepresentative. CORE only prints on days that retain a
  **continuous, non-fallback base reference**; otherwise the day's CORE value is skipped rather
  than fabricated.

**Re-anchoring rule.** The base-period reference for a CORE-eligible day is re-anchored to the
nearest **festival-free** base day — searched forward first, then backward, up to 21 days, and
never beyond the observation date (no future leakage). If no route in the basket can furnish a
genuine non-fallback base price, the CORE series for that day is not published (no fake
100.00 prints). Implementation: `_find_core_anchor` in
`services/index_engine/calculator_service.py`.

**API + export surface:** `GET /api/v1/index?series_type=HEADLINE|CORE`,
`GET /api/v1/index/daily?series_type=...`, and the CSV export
(`date,index_series,series_type,index_type,...`).

**Verified example (2026-09-14):** BASE_FARE HEADLINE = 107.07 vs CORE = **110.89**;
TOTAL_PRICE HEADLINE = 100.79 vs CORE = **105.35** — the festival-adjacent weeks moved the
raw series; CORE keeps the continuous reference intact.

### 1.3 ENSEMBLE Estimator: Feed-Quality-Weighted Median (v2.1)

Alongside Jevons, the estimator suite offers `ENSEMBLE` — a **feed-quality-weighted median** of
per-carrier minimum fares that hears all feeds but discounts low-trust sources:

$$I^{\text{ENS}}_t = \text{weighted-median}\left\{ P_{j,t,c} \times w_{\text{feed}(c)} \right\}_{c}$$

with weights per feed cohort: CARRIER_DIRECT = 1.0, RPC_FALLBACK = 0.9,
OTA_AGGREGATOR = 0.7, SYNTHETIC_BASELINE = 0.3. Survivor-set alignment is applied after the
MAD/IQR outlier filter so the median is not dragged by a cheap low-quality OTA quote or a
rogue spike. It is used by the feed-cohort correlation layer
(`packages/statistics/source_correlation.py`) and exposed for analytics consumption.

---

## 2. Real-World Confounding Defenses

### Defense 1: Lowest-Economy Estimator (Fare-Mix Protection)
- **The Real-World Confounding Problem:** When an airline expands inventory or introduces premium/flexi economy seats (e.g. flexi ticket with free cancellation for INR 7,500 alongside basic economy at INR 4,200), a naive pooled average would report a price surge of +20–30%, falsely signaling airfare inflation.
- **The Observatory Guarantee:** For each carrier on corridor $j$ and horizon $h$, we extract strictly the lowest available basic economy fare:
  $$P_{j,t,h,c} = \min_{k \in \text{Basic Economy}} (\text{Base Fare}_{j,t,h,c,k})$$
- The corridor representative price is the **Jevons geometric mean** across scheduled carriers (see §1.1):
  $$P_{j,t,h} = \exp\left( \frac{1}{N} \sum_{c \in \text{Airlines}(j)} \ln P_{j,t,h,c} \right)$$
- **Result:** Changes in ticket mix or premium seat ratios have **0% mathematical impact** on the index.

### Defense 2: Unpooled Lead Times ($T+15$ Headline Anchor)
- **The Real-World Confounding Problem:** Averaging $T+1$ (departure eve) with $T+45$ (early bird) distorts the series, because last-minute prices reflect passenger urgency rather than systemic macroeconomic inflation.
- **The Observatory Guarantee:** The headline index is anchored strictly at **$T+15$** (standard 2-week advance purchase). All other horizons are published as isolated, unpooled sub-indices:
  - $\text{SUB\_T1}$: 1-day advance (urgent travel)
  - $\text{SUB\_T7}$: 7-day advance (weekly business)
  - $\text{SUB\_T15}$: 15-day advance (official headline anchor)
  - $\text{SUB\_T30}$: 30-day advance (monthly planned travel)
  - $\text{SUB\_T45}$: 45-day advance (early bird holiday)
- **Justification:** See [docs/T15_anchor_analysis.md](docs/T15_anchor_analysis.md) for the booking-window analysis motivating the T+15 anchor.

### Defense 3: Dual Price Series
- **Base Fare Index:** Reflects pure airline yield management and behavioral pricing (excluding government GST, airport UDF/ADF charges, and platform convenience fees).
- **Total Price Index:** Reflects the full consumer out-of-pocket expenditure.

---

## 3. Route Basket & DGCA Normalization

Corridors are chosen across both high-density trunk routes and regional/thin corridors. Passenger
volumes below are **real** trailing-12-month (Aug 2025-Jul 2026) DGCA city-pair traffic figures —
sourced from DGCA's own Monthly Domestic Air Transport Statistics via the public
[Vonter/india-aviation-traffic](https://github.com/Vonter/india-aviation-traffic) aggregation
(`data/reference/dgca_traffic.csv`), replacing earlier placeholder numbers:

| Corridor | Corridor Type | DGCA Passenger Volume (TTM) | Normalized Weight ($w_j$) |
|---|---|---|---|
| **DEL-BOM** | Metro Trunk | 6,778,337 | **0.2376** (23.76%) |
| **DEL-BLR** | Metro Trunk | 4,877,158 | **0.1710** (17.10%) |
| **BOM-BLR** | Metro Trunk | 4,129,165 | **0.1448** (14.48%) |
| **DEL-HYD** | Metro Trunk | 3,105,466 | **0.1089** (10.89%) |
| **DEL-CCU** | Metro Trunk | 2,912,808 | **0.1021** (10.21%) |
| **BOM-MAA** | Metro Trunk | 2,219,067 | **0.0778** (7.78%) |
| **DEL-MAA** | Metro Trunk | 2,184,325 | **0.0766** (7.66%) |
| **BLR-HYD** | Metro Trunk | 2,169,407 | **0.0761** (7.61%) |
| **DEL-DHM** (Dharamsala)| Regional Thin | 131,205 | **0.0046** (0.46%) |
| **DEL-IXS** (Silchar) | Regional Thin | 16,610 | **0.0006** (0.06%) |

$$\sum_{j=1}^{10} w_j = 1.000000 \quad (\pm 10^{-6})$$

Note the regional-thin ordering flips vs. earlier placeholder data: real DGCA traffic shows
DEL-DHM (Dharamsala) carrying roughly 8x the passenger volume of DEL-IXS (Silchar) over this
window, so DHM now carries the larger of the two small weights.

---

## 4. Directional Co-Movement & MoSPI Validation

- **Directional Accuracy:** Measures month-over-month price movement concordance:
  $$\text{Directional Accuracy} = \frac{1}{N} \sum_{t=1}^N \mathbf{1}(\text{sign}(\Delta \text{Prototype}_t) == \text{sign}(\Delta \text{MoSPI}_t)) \times 100\%$$
- **Pearson Correlation ($r$):** Evaluates linear co-movement independent of base year scaling differences.
- **Methodological Disclosure:** High-frequency search quotes measure forward-looking expectations across 5 lead-time windows, whereas MoSPI CPI reflects retrospective survey collection on fixed routes and dates. Co-movement indicates alignment with broader macroeconomic inflation trends. MoSPI does not publish a standalone domestic-airfare-only CPI sub-index; the benchmark used is item 07.3 "Passenger transport services" (Combined, 2024=100) -- a composite across rail/air/road fares, not air fare alone.
- **Current real-data status:** MoSPI's 2024=100 series (`data/reference/mospi_cpi_benchmark.csv`) is transcribed from real Press Release PDFs and currently covers Jan-Jul 2026 (one gap month, May). The prototype's own operating history starts 2026-08-01, so **there is presently no real overlapping month** between the two series -- `GET /api/v1/validation` honestly reports `status=INSUFFICIENT_REAL_OVERLAP` with `is_live_computation=false` and an illustrative reference scorecard (not a live $r$), rather than fabricating a correlation. This will become a genuine computation automatically once both series accumulate 3+ overlapping months (MoSPI publishes with a 5-6 week lag, so August 2026's release is expected in October 2026).

### 4.1 Governance & Policy Intelligence Definitions (v2.2)

- **Transient vs Structural elevation (Policy Signal):** An elevation is measured against a
  **pre-spike first-half median baseline** (so a long structural rise does not pull up its own
  reference). STRUCTURAL evidence = persistence ≥ 21 days, multi-carrier breadth (≥ 3 carriers
  simultaneously elevated), ATF co-movement in the trailing window; TRANSIENT evidence = reversal
  within 14 days, festival-calendar alignment, single-carrier. Cumulative evidence score decides
  `STRUCTURAL / TRANSIENT / MIXED / NO_ELEVATION / NO_DATA`.
- **Lead-lag (Billion-Prices):** Pearson $r$ and directional accuracy of the weekly high-frequency
  series vs a monthly MoSPI CPI airfare series expanded to weekly, evaluated at lags 0–4 weeks.
  Zero-variance windows (months not yet updated) are excluded as "no evidence" rather than $r=0$.
- **HHI carrier concentration:** $HHI = \sum_i s_i^2 \times 10^4$ on observed carrier quote share;
  CCI bands: < 1500 LOW, 1500–2500 MODERATE, > 2500 HIGH.
- **Intraday volatility:** Coefficient of variation of same-travel-date fares across the four IST
  snapshot windows (06:00 / 12:00 / 18:00 / 23:00); **best-time-to-book** = lowest-mean window.
- **Availability-Adjusted Index:** SOLD_OUT pressure is treated as a demand signal with a
  saturating scarcity premium $\text{premium} = \beta \cdot \min(\text{sold\_out\_ratio}, 1)$,
  $\beta = 0.35$ (max +35% at full sell-out). Disclosed as a **model parameter** for consumer-cost
  estimation, never conflated with quoted fares.
- **UDAN affordability monitor:** Route median vs the UDAN ₹2,500 one-hour benchmark →
  `AFFORDABLE / ELEVATED / BREACH` (ratio vs target > 1.0 = ELEVATED; > 1.5× target or trunk
  median = BREACH).

---

## 5. References

1. **International Monetary Fund (2020).** *Consumer Price Index Manual: Concepts and
   Methods* — Chapter 10 (Elementary Indices), §§7–10 (Jevons / geometric mean). Geneva:
   IMF/OECD/ILO/UNECE/Eurostat/World Bank.
2. **Jevons, W. S. (1863).** *A Serious Fall in the Value of Gold Ascertained.* London:
   Edward Stanford.
3. **Office for National Statistics (UK).** *Consumer Price Indices: A Technical Guide* —
   web-scraped used-internet price index methodology (geometric elementary aggregation).
4. **Directorate General of Civil Aviation (DGCA).** Monthly *Air Transport Statistics* —
   sector-wise traffic volumes used for the DGCA route-weight basket (`DGCA_2026_V1`).
5. **Ministry of Statistics & Programme Implementation (MoSPI).** *CPI (Combined) Manual* —
   airfare sub-group definition used for directional co-movement benchmarking.
