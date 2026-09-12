# APIX Research Material & Industry Benchmarks

> Living research repository for the **India Airfare Price Observatory**. Every claim below
> was gathered while building/prototyping and is stored so future work can cite sources,
> challenge assumptions, and extend the roadmap. Last updated: 2026-09-11.

---

## 1. Why full-record extraction (incl. travel date) — and how comparison works

**Issue.** The prototype originally extracted only `price` (+ route) from DOM/OCR and let the
**query context** decide `travel_date` and most flight attributes. That means:

- a screenshot could be for the *wrong* date/nearby route and we would never know;
- `flight_number`, `departure_time`, `stops`, `duration` were hardcoded fallbacks in
  `carrier_direct_scraper._extract_via_ocr`;
- comparison logic (cross-feed discrepancy audits, DGCA backtest, forecast-vs-realized)
  matched on **series + route + travel_date** — all query-supplied, none verified on-page.

**Now fixed** (implemented this session). `services/extraction/adaptive_extractor.py` extracts the
**full record** from every stage (DOM, OCR tokens, VLM):

| Field | Source regex / target | Why it matters |
|---|---|---|
| `price` | `INR/Rs/₹` + digits | headline fare |
| `origin` / `destination` | 3-letter `XXX -> YYY` | route verification |
| `travel_date` / `return_date` | ISO, `15 Sep 2026`, `Sep 15, 2026`, year-less (resolved against the queried date, ±60d window) | **on-page truth** for the record; mismatches are logged so comparison can't silently hit the wrong day |
| `flight_number` | 2-char code + 3–4 digits (`6E-205`, `AI-011`) | links quotes to a timetabled flight |
| `airline` / `airline_name` | carrier-code map (6E, AI, SG, QP, IX, UK, I5, G8) | carrier-level analytics |
| `departure_time` / `arrival_time` | `HH:MM` | time-of-day pricing (known to move accuracy ~10% if dropped) |
| `stops` | `Nonstop`, `1 stop`, `2 stops` | fare-quality of the *cheapest* quote |
| `duration_minutes` | `2h 15m` | schedule sanity |

`carrier_direct_scraper._extract_via_ocr` now merges these fields (real flight number, times,
stops, on-page travel date) instead of hardcoding. `ExtractionContext.reference_date` passes the
queried travel date so year-less card dates resolve deterministically.

**How comparison uses it.** Realized-vs-forecast scoring (`/api/v1/forecast/accuracy`) matches
snapshots to `index_values` by `series + index_type + period_start == target_date`. Discrepancy
audits match by `route + airline + flight_number + travel_date`. Extracting the date on-page lets
us *validate* the match key instead of trusting it, and gives us `return_date` for round-trip
work, which the industry treats as a first-class fare attribute (see OAG column list below).

---

## 2. Index-methodology benchmarks for the official index design

Our headline `T+15` Laspeyres index, lowest-economy estimator, unpooled lead times, 28-day
moving average, spot window, and DGCA-weights basket are all traceable to official practice:

- **BLS CPI Airline Fares** (the canonical reference). Monthly, area-weighted sample drawn with
  probability proportional to DOT O&D passenger counts; each month fixes the **advance-reservation
  spec and day-of-week** for every quote; prices the *lowest available* plus other discount fares;
  includes taxes and (probabilistically) one checked bag.
  https://www.bls.gov/cpi/factsheets/airline-fares.htm
  - CPI vs PPI vs ATPI vs expenditures: https://www.bls.gov/cpi/factsheets/prices-spending-comparison-airline-fares.htm
  - Airline-fares CPI time series: https://data.bls.gov/timeseries/CUSR0000SETG01
- **BLS Monthly Labor Review 2005 — "A transaction price index for air travel."** Explains why
  the airline CPI drifted from transaction fares (SABRE-sourced vs O&D Survey), the itinerary/segment
  matching problem, and compares modified-Laspeyres vs Jevons vs Fisher CPI formulas. Direct support
  for our "never pool unpooled lead times" rule.
  https://www.bls.gov/opub/mlr/2005/06/art2full.pdf
- **BTS Average Fares / ATPI.** DOT switched ticket sampling 10% → **40%** (OD40) on 1 Jul 2025;
  Q3 2025 average domestic fare $370 (+today's baseline for US analog). O&D Survey = the sampling
  frame the BLS uses, just as DGCA route volumes are ours.
  https://www.bts.gov/air-fares  ·  https://www.bts.gov/newsroom/third-quarter-2025-average-air-fare-decreases-47-second-quarter-2025

**Design takeaways for APIX** — we already match the *two hardest* BLS practices:
1. fixed per-horizon "spot" specs (our `SUB_T1/T7/T15/T30/T45` unpooled indices);
2. lowest-available-fare-within-a-horizon (our lowest-economy estimator).
Next-level gaps vs BLS: publishing monthly seasonally-adjusted series; explicit
advance-reservation + day-of-week quote specs persisted per observation; checked-bag inclusion rule.

---

## 3. Commercial data providers we are (legitimately) positioned against

| Provider | What they sell | Notes we can exploit |
|---|---|---|
| **OAG Airfare Data / Airfare Analytics / Altus / Market Trends** | 4T historical fares, +4B/day, 1,500+ booking sites, up to 200 columns | Columns: booking-site name, channel, O&D, connection type, cabin/fare type, price incl/excl tax, **advance-purchase window**, **seat availability**, **minimum stay**, one-way/round-trip. "Give-to-get" airline data model. Forward 1 year. **This is the "extract everything, clean later" template the user asked for.** |
| | | https://www.oag.com/airfare-data · https://www.oag.com/airfare-analytics · https://www.oag.com/altus-data · https://www.oag.com/blog/airfare-data-an-insiders-guide |
| **ARC (Airlines Reporting Corp)** | US agency ticket database, fare trend reporting | ARC + US Travel Assoc. computed 2026 spring domestic fares +20%; ARC does not cover exempt carriers — route-coverage gaps are a known (fixable) weakness. https://www2.arccorp.com/about-us/arc-data-explained/ |
| **BTS OD40 / ATPI** | quarterly average fares | 3–6 month lag (per 2005 MLR) — **we are real-time; they are retrospective**. |
| **IATA / GDS-distributed (Amadeus, Sabre, Travelport)** | fare engines, NDC | Real-time but *fee-bundled*; no open transparent public index; our open benchmark ≠ their monetized feed. |

---

## 4. The consumer-prediction competitive set (buy-now/wait world)

| Tool | Method | Published/observed accuracy | Weakness we can expose |
|---|---|---|---|
| **Hopper** | ML on ~300B prices/month, black-box Buy/Wait + Price Freeze | claims 95%; independent ~82% price-drop accuracy; **falls to ≈51% inside 14 days of departure** | "Black box w/o calibration"; last-minute advice ≈ coin flip; unverifiable claims |
| **Google Flights** | historical typical/low/high + confidence scores, price tracking, date grid | strong historical context; Price Guarantee **paused in 2022 volatility**, re-launched 2023 partial | consumer-only, no index discipline, no published error |
| **Kayak** | Price Forecast + confidence meter | ~85% short-term; **falls below ~50% beyond 3 months** | horizon collapse |
| **AirHint** | per-carrier ML models | claims 80%+ | EU/budget-centric |
| **Farecast → Microsoft (2000s)** | academic lineage (Etzioni) proving public data can predict | — | the origin of the whole space |

Sources: https://platinumflyer.com/ai-flight-price-predictor-accuracy/ ·
https://www.kayak.com/news/flight-price-alerts/ ·
https://dnyuz.com/2026/06/09/airfare-prediction-apps-cant-handle-a-summer-like-this-one/ ·
https://travelaidaily.com/blog/best-ai-flight-price-predictor-app/ ·
https://www.gomeltourist.com/airfare-prediction-tools-and-accuracy-comparisons/ ·
https://earnifyhub.com/blog/hopper-vs-kayak

**Our differentiated stance (backed by the literature):** publish **calibrated horizons + honest
error** (MAE/RMSE/MAPE + interval coverage exposed on `/forecast/accuracy`), Google-style
transparency ("typical/low/high") over Hopper-style prescriptions, and treat exogenous shocks
(West Asia crisis, festivals) as regime breaks — the exact failure mode that "prediction apps
can't handle a summer like this one" documents. Industry sweet-spot facts to encode in the UI:
Expedia air-hacks note domestic economy bottoms **15–30 days** before departure, international
**31–45 days**; community tracking puts the volatility sweet-spot at **45–21 days** out.

---

## 5. Academic literature (airfare forecasting) — our model stack sits in this lineage

- Hybrid GRU+XGBoost + meta-learner on **Indian domestic** data w/ fuel-price & holiday features →
  best R² 0.947 tabular / 0.694 time-series (LUT thesis, 2025).
  https://lutpub.lut.fi/handle/10024/169248
- Bi-LSTM best of RNN family on **Google-Flights-scraped** data (7 months, 6 US airports) (2024, IEEE).
  https://doi.org/10.1109/ddp64453.2024.00012
- GRU with 44 features on Ethiopian Airlines data; attention-BiGRU (2025, ACM).
  https://doi.org/10.3390/app13106032 · https://doi.org/10.1145/3770177.3770311
- MADA Seq2Seq dual-attention; states **optimal-purchase-time prediction** as the open research
  direction (2021). https://doi.org/10.1007/s10489-021-02602-0
- **Optimal-purchase-timing regression (Groves & Gini, 2011)** — the Farecast academic core.
  https://conservancy.umn.edu/handle/11299/113303
- Ensemble/incremental (Learn++.NSE, multi-step ahead) forecast service (2015, IEEE Big Data).
  https://doi.org/10.1109/bigdata.2015.7363846
- Bayesian NN first applied to airfare; Random Forest best cost/accuracy trade-off (Politecnico Torino).
  https://iris.polito.it/handle/11583/2980935
- **Tolerance-metric idea worth copying:** a ±10%-band "Regression Weighted Accuracy" for
  buy-now/wait evaluation on 49.7M search records (Pateh, 2026).
  https://iai.sbu.ac.ir/fa/Home/Article/1076be80-53d0-46de-8e51-73f6350016db

**Grounded signals we already use / must keep:** advance-purchase period and time-of-day are the
strongest features (dropping dep/arr time hurts ~10% accuracy); day-of-week is weak; fuel price +
holiday flags are decisive in Indian data; competition count per route lowers fares.

---

## 6. Scraping & anti-bot landscape (the blockades, and what we do)

### Industry state (Zyte State of Web Access 2026 — Travel & Tourism)
WAF 81%, JavaScript challenge 55%, rate limiting 31%, antibot 27%, CAPTCHA 8%, TLS 26%, robots.txt
present 78%, AI-crawler blocking 21% (highest of any vertical). Airlines: WAF 76%, antibot 24%,
CAPTCHA 11%. Active challenge layers, not firewalls, carry the load.
https://www.zyte.com/sowa/2026/industry/travel-and-tourism/

### Blockade → mitigation mapping (what this project already implements + what to add)
| Blockade | Industry reality (2026) | APIX today | APIX roadmap |
|---|---|---|---|
| CAPTCHA (reCAPTCHA v2/v3, Turnstile, DataDome) | triggers after ~30–80 automated quests; residential proxies 30%→<10% trigger rate; session persistence −40–60% | `CaptchaSolver` (2Captcha), proxy rotation penalty on CAPTCHA, robots-cached fallback | **prefer NOT to solve**: degrade to OCR/VLM screenshot stage → calibrated baseline; document each CAPTCHA as a source-availability metric |
| IP blocks / rate limiting | look-to-book now 10k–20k searches/ticket; 49% of travel bot traffic | per-domain token bucket (30/min, 500/hr, jittered backoff), browser pool, circuit breaker (5 fails → 60s OPEN), exponential backoff | add RFC 9421-style request-id headers? No — instead publish transparent UA + robots audit trail (regulators read robots.txt compliance as good faith) |
| JS fingerprinting (TLS, canvas/WebGL/audio, `navigator.webdriver`) | Akamai Bot Mgr / HUMAN / Cloudflare profile before page load | Playwright stealth within an unmodified browser context | keep headless *slow* (4x/day, 10 routes): low volume is the strongest fingerprint defense |
| Silent throttling ("degraded results") | OTAs serve stale/fewer results rather than block | `SEATS`/price-anomaly checks + drift detector + dual-feed cross-parity | add explicit per-source "served-stale? y/n" flag to `quality` dashboard |
| Schema changes | `SCHEMA_CHANGED` | circuit breaker permanent OPEN + `REVIEW_REQUIRED` re-registration | automated "selector health" heartbeat per source |
| Mobile-app APIs | reverse-engineered app endpoints = cheapest surface | n/a | do NOT pursue (ToS/permission risk); public-website pass only |

### Legal frame we must keep quoting (it shapes ethics checks in code)
- `hiQ v. LinkedIn` (9th Cir 2022) + `Van Buren` (2021): public, unauthenticated pages ≈ not CFAA
  "without authorization". Discipline: fetch only URLs any logged-out user can fetch.
- `Meta v. Bright Data` (2024) / `X Corp v. Bright Data`: ToS binds a **logged-in session**, not an IP;
  copyright claims over public data pre-empted.
- `Ziff Davis v. OpenAI` (Dec 2025): robots.txt is **not** a DMCA technological protection measure.
- `Robots Exclusion Protocol` = **RFC 9309** (IETF, Sep 2022): voluntary, not access authorization;
  France's CNIL weighs robots.txt compliance in the Article 6(1)(f) balancing test.
- **DMCA §1201 anti-circumvention:** never bypass access controls on *private* content; a CAPTCHA on
  otherwise-public listings is still treated as risky in commercial products → our policy: back off.
- Industry commentary: an AirShopping request fans out to ~450 upstream calls (cost argument for why
  sites gate search); blanket blocking is dying (tarpit > block; verified-identity agent standards
  RFC 9421 / Ed25519 on Cloudflare/AWS/Akamai edge).

Sources: https://www.eknix.com/blog/fare-scraping-api-abuse/ ·
https://bytetunnels.com/posts/bypassing-anti-bot-travel-sites-without-violating-tos/ ·
https://forage.ai/blog/web-scraping-legal-compliance/ ·
https://finedata.ai/blog/web-scraping-legal-guide/ ·
https://www.capsolver.com/blog/web-scraping/how-to-collect-travel-availability-data-for-ai-agents ·
https://market.xproxy.io/blog/travel-fare-scraping-flights-hotels-proxies-2026 ·
https://www.kindproxy.com/blog/en/blog/travel-aggregation-compliance-faq-2026/

---

## 7. India regulatory context — the strongest USP evidence

- **DGCA Tariff Monitoring Unit (TMU):** monitors **78 routes (72 domestic + 6 international),**
  *monthly, on a random basis*, by visiting airline websites — exactly the method we automate at
  **4x/day with full audit trail**. Lok Sabha Q902/Q712 (23 Jul 2026).
  https://sansad.in/getFile/lsapps/loksabhaquestions/annex/188/AU902_YcOcex.pdf ·
  https://sansad.in/getFile/lsapps/loksabhaquestions/annex/188/AU712_L2QPdJ.pdf ·
  https://www.indianaviationnews.net/home/2026/07/dgca-monitors-airfares-on-78-routes-airsewa-handles-fare-complaints-govt.html
- **Airlines refuse to share ticket-level data.** FIA (carriers) resisted DGCA's 2022–2024 fare
  data request for ~2 years; DGCA (Jul 2026) agreed to accept *aggregated* data. → **No public,
  granular, real-time index exists in India; anyone publishing one owns the vacuum.**
  https://aviationtoday.in/civilaviation/airlines/dgca-to-use-ai-for-airfare-monitoring-airlines-agree-to-share-pricing-data/
- **Parliament wants exactly this:** Standing Committee 375th Report ("Demands for Grants 2025-26,
  MoCA") proposed **"AirPrice Guardian"** — an AI monitoring + prediction system (Phase I major
  routes; Phase II national, targeting 2026) and a **"Pricing Transparency Index"** consumer portal.
  → Our 13-view dashboard maps 1:1 onto the government's own stated requirements.
  (Same sources as above / AviationToday.)
- **Market:** average domestic fare **+20.5%** Mar-2025→Jun-2026 (~₹7,000–7,500 vs ~₹5,000–5,500);
  ATF ≈ 35–40% of opex; fuel surcharge introduced Mar 2026 (West Asia crisis); ATF capped at +25%
  over the 1-Mar-2026 base (Apr–May 2026); ₹10,000 cr OMC support. → our `ATF_context` and
  `fuel-context` dashboard page is *the* causal overlay regulators cite.
  https://economictimes.indiatimes.com/industry/transportation/airlines-/-aviation/average-airfare-on-72-domestic-routes-rose-20-5-pc-in-june-compared-to-may-2025-dgca-data/articleshow/132663680.cms ·
  https://www.livemint.com/industry/india-domestic-airfares-rise-airline-capacity-falls-passenger-traffic-11787539828384.html ·
  https://www.newindianexpress.com/business/2026/Jul/28/over-20-increase-in-domestic-air-fare-in-15-months-aviation-ministry
- **Rule 135, Aircraft Rules 1937:** airlines file their own tariffs; India does not regulate fares
  except through fare caps in crisis → monitoring (not regulation) is the sanctioned role.

---

## 8. USP distillation & roadmap (industry-grade upgrades)

**USP in one line:** *The only open, real-time, methodologically-explicit domestic airfare price
index for India — daily (4x/day), 10-route/5-horizon, DGCA-weighted, with forecast backtests you
can audit, engineered to become the public counterpart to DGCA's internal TMU and Parliament's
proposed AirPrice Guardian.*

**What makes it defensible (vs OAG/ARC/BTS/consumer apps):**
1. Explicit, published methodology (README/ARCHITECTURE/DATA_MODEL/METHODOLOGY) — OAG/ARC sell
   feeds, BTS lags 3–6 months, consumer apps are black-box.
2. Honest forecast error on `/forecast/accuracy` (MAE/RMSE/MAPE, interval coverage) — nobody in the
   consumer set publishes this.
3. Regulatory alignment: TMU = monthly + random + 78 routes; APIX = daily + full audit + 10 routes.
4. Deterministic-first extraction (DOM→OCR→VLM) with full-record capture incl. **on-page travel
   date verification** (added this session).
5. Non-causal guardrails (ATF hedging disclosures, ML labeled "auxiliary", cleanly separated from
   the official Laspeyres index).

**Roadmap (ranked by impact):**
- **P1 — Data breadth:** 10 routes → 20+ (all 72 TMU-monitored), add return-trip records (we now
  extract `return_date`), capture `checked_bag` flag, `seat_availability`, `min_stay` (OAG columns).
- **P1 — Publication discipline:** monthly seasonally-adjusted index series + per-observation
  advance-reservation + day-of-week specs (BLS parity); publish a `typical/low/high` band (Google
  parity) driven by our own calibrated percentiles.
- **P1 — Forecast honesty layer:** publish horizon-collapse curve (our equivalent: `by_horizon`
  buckets already exist); add the ±10%-band RWA tolerance metric from the Pateh paper to the
  accuracy panel; gate Buy/Wait-type advice behind it.
- **P2 — Data-cleaning layer (the user request):** schema-driven "extract-everything → clean"
  pipeline: raw fields → canonical (ISO dates, 24h times, IATA codes, INR) → validation rules
  (drift detector, duplicate finder, cross-feed parity) → typed `FareObservation`. All raw
  artifacts already SHA-256 hashed in `data/raw/YYYY/MM/DD/`.
- **P2 — Engineering:** Time-seriesDB for the index store; backfill snapshots; alert thresholds
  per corridor (SURGE) with daily digests; export both raw + cleaned CSVs (existing `/export`).
- **P2 — Governance:** per-source robots.txt audit log (RFC 9309 semantics), per-record lawful-basis
  tag (GDPR Art 6(1)(f) framing), session-state predicate proving logged-out-only collection
  (Meta v. Bright Data posture). 90% already exists in `ethical_scraping.py` + `source_registry.py`.
- **P3 — Public good:** publish the 2026 price-surge evidence trail (Mar-2025→Jun-2026 +20.5%) as a
  transparent, reproducible dashboard the ministry/regulators can cite; position as the consumer-
  facing **Pricing Transparency Index** Parliament wants.

---

## 9. Consolidated link list (for future reference)

**Index methodology (official):**
- BLS CPI Airline Fares: https://www.bls.gov/cpi/factsheets/airline-fares.htm
- CPI vs PPI vs ATPI: https://www.bls.gov/cpi/factsheets/prices-spending-comparison-airline-fares.htm
- Airline-fares CPI data: https://data.bls.gov/timeseries/CUSR0000SETG01
- Transaction price index for air travel (MLR 2005): https://www.bls.gov/opub/mlr/2005/06/art2full.pdf
- BTS Air Fares / OD40: https://www.bts.gov/air-fares · https://www.bts.gov/newsroom/third-quarter-2025-average-air-fare-decreases-47-second-quarter-2025

**Commercial data providers:**
- OAG Airfare Data: https://www.oag.com/airfare-data
- OAG Airfare Analytics: https://www.oag.com/airfare-analytics
- OAG Altus Data: https://www.oag.com/altus-data
- OAG insider's guide: https://www.oag.com/blog/airfare-data-an-insiders-guide
- ARC: https://www2.arccorp.com/about-us/arc-data-explained/

**Consumer prediction tools:**
- Google Flights tracking/insights: https://www.google.com/travel/flights
- KAYAK Price Alerts/Forecast: https://www.kayak.com/news/flight-price-alerts/
- Hopper vs Kayak (tests): https://earnifyhub.com/blog/hopper-vs-kayak
- Prediction accuracy deep dives: https://platinumflyer.com/ai-flight-price-predictor-accuracy/ ·
  https://travelaidaily.com/blog/best-ai-flight-price-predictor-app/ ·
  https://airtripmasters.com/how-accurate-are-flight-price-prediction-tools/ ·
  https://www.gomeltourist.com/airfare-prediction-tools-and-accuracy-comparisons/ ·
  https://dnyuz.com/2026/06/09/airfare-prediction-apps-cant-handle-a-summer-like-this-one/

**Academic airfare forecasting:**
- https://lutpub.lut.fi/handle/10024/169248 · https://doi.org/10.1109/ddp64453.2024.00012 ·
  https://doi.org/10.3390/app13106032 · https://doi.org/10.1145/3770177.3770311 ·
  https://doi.org/10.1007/s10489-021-02602-0 · https://doi.org/10.1109/bigdata.2015.7363846 ·
  https://iris.polito.it/handle/11583/2980935 ·
  https://iai.sbu.ac.ir/fa/Home/Article/1076be80-53d0-46de-8e51-73f6350016db

**India regulatory:**
- Lok Sabha Q902 (23 Jul 2026): https://sansad.in/getFile/lsapps/loksabhaquestions/annex/188/AU902_YcOcex.pdf
- Lok Sabha Q712 (23 Jul 2026): https://sansad.in/getFile/lsapps/loksabhaquestions/annex/188/AU712_L2QPdJ.pdf
- DGCA-AI monitoring / FIA data refusal: https://aviationtoday.in/civilaviation/airlines/dgca-to-use-ai-for-airfare-monitoring-airlines-agree-to-share-pricing-data/
- TMU 78 routes / AirSewa: https://www.indianaviationnews.net/home/2026/07/dgca-monitors-airfares-on-78-routes-airsewa-handles-fare-complaints-govt.html
- +20.5% fare rise: https://economictimes.indiatimes.com/.../articleshow/132663680.cms ·
  https://www.livemint.com/industry/india-domestic-airfares-rise-airline-capacity-falls-passenger-traffic-11787539828384.html ·
  https://www.newindianexpress.com/business/2026/Jul/28/over-20-increase-in-domestic-air-fare-in-15-months-aviation-ministry

**Web scraping / anti-bot / legal:**
- Zyte State of Web Access 2026 (Travel): https://www.zyte.com/sowa/2026/industry/travel-and-tourism/
- Fare scraping & API abuse (Eknix): https://www.eknix.com/blog/fare-scraping-api-abuse/
- Anti-bot travel sites (ByteTunnels): https://bytetunnels.com/posts/bypassing-anti-bot-travel-sites-without-violating-tos/
- Legal compliance 2026 (forage.ai): https://forage.ai/blog/web-scraping-legal-compliance/
- Legal guide (finedata): https://finedata.ai/blog/web-scraping-legal-guide/
- CAPTCHA pipeline at scale (CapSolver): https://www.capsolver.com/blog/web-scraping/how-to-collect-travel-availability-data-for-ai-agents
- Proxies & OTA compliance (KindProxy): https://www.kindproxy.com/blog/en/blog/travel-aggregation-compliance-faq-2026/