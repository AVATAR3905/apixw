# Statistical Methodology & Mathematical Formulation (APIX-2.0)

> Official Methodology Documentation for the India Airfare Price Observatory (MoSPI / NSO).

---

## 1. Mathematical Index Formulation (Modified Laspeyres)

The daily **India Airfare Price Index** ($I_t$) is computed using a Modified Laspeyres price index formula:

$$I_t = 100 \times \sum_{j=1}^{M} w_j \times \left( \frac{P_{j,t,T+15}}{P_{j,0,T+15}} \right)$$

Where:
- $I_t$: National headline airfare price index on observation day $t$.
- $w_j$: Fixed normalized passenger volume weight for domestic route corridor $j$ (source: DGCA domestic scheduled traffic), satisfying $\sum_{j=1}^{M} w_j = 1.000000 \pm 10^{-6}$.
- $P_{j,t,T+15}$: Representative airfare on route corridor $j$ on observation date $t$ anchored at **$T+15$** advance purchase.
- $P_{j,0,T+15}$: Base period representative airfare on route corridor $j$ (Base Period: August 1, 2026 = 100.00).
- $M$: Number of monitored corridors in the basket ($M=10$).

---

## 2. Real-World Confounding Defenses

### Defense 1: Lowest-Economy Estimator (Fare-Mix Protection)
- **The Real-World Confounding Problem:** When an airline expands inventory or introduces premium/flexi economy seats (e.g. flexi ticket with free cancellation for INR 7,500 alongside basic economy at INR 4,200), a naive pooled average would report a price surge of +20–30%, falsely signaling airfare inflation.
- **The Observatory Guarantee:** For each carrier on corridor $j$ and horizon $h$, we extract strictly the lowest available basic economy fare:
  $$P_{j,t,h,c} = \min_{k \in \text{Basic Economy}} (\text{Base Fare}_{j,t,h,c,k})$$
- The corridor representative price is the median across scheduled carriers:
  $$P_{j,t,h} = \text{median}_{c \in \text{Airlines}} (P_{j,t,h,c})$$
- **Result:** Changes in ticket mix or premium seat ratios have **0% mathematical impact** on the index.

### Defense 2: Unpooled Lead Times ($T+15$ Headline Anchor)
- **The Real-World Confounding Problem:** Averaging $T+1$ (departure eve) with $T+45$ (early bird) distorts the series, because last-minute prices reflect passenger urgency rather than systemic macroeconomic inflation.
- **The Observatory Guarantee:** The headline index is anchored strictly at **$T+15$** (standard 2-week advance purchase). All other horizons are published as isolated, unpooled sub-indices:
  - $\text{SUB\_T1}$: 1-day advance (urgent travel)
  - $\text{SUB\_T7}$: 7-day advance (weekly business)
  - $\text{SUB\_T15}$: 15-day advance (official headline anchor)
  - $\text{SUB\_T30}$: 30-day advance (monthly planned travel)
  - $\text{SUB\_T45}$: 45-day advance (early bird holiday)

### Defense 3: Dual Price Series
- **Base Fare Index:** Reflects pure airline yield management and behavioral pricing (excluding government GST, airport UDF/ADF charges, and platform convenience fees).
- **Total Price Index:** Reflects the full consumer out-of-pocket expenditure.

---

## 3. Route Basket & DGCA Normalization

Corridors are chosen across both high-density trunk routes and regional/thin corridors:

| Corridor | Corridor Type | Base Representative Fare | DGCA Passenger Volume | Normalized Weight ($w_j$) |
|---|---|---|---|---|
| **DEL-BOM** | Metro Trunk | INR 4,115.00 | 3,250,000 | **0.184** (18.4%) |
| **DEL-BLR** | Metro Trunk | INR 4,450.00 | 2,510,000 | **0.142** (14.2%) |
| **BOM-BLR** | Metro Trunk | INR 3,380.00 | 2,140,000 | **0.121** (12.1%) |
| **DEL-CCU** | Metro Trunk | INR 4,320.00 | 1,860,000 | **0.105** (10.5%) |
| **DEL-HYD** | Metro Trunk | INR 3,750.00 | 1,730,000 | **0.098** (9.8%) |
| **BOM-MAA** | Metro Trunk | INR 3,420.00 | 1,520,000 | **0.086** (8.6%) |
| **BLR-HYD** | Metro Trunk | INR 2,850.00 | 1,390,000 | **0.079** (7.9%) |
| **DEL-MAA** | Metro Trunk | INR 4,680.00 | 1,320,000 | **0.075** (7.5%) |
| **DEL-IXS** (Silchar) | Regional Thin | INR 6,250.00 | 1,020,000 | **0.058** (5.8%) |
| **DEL-DHM** (Dharamshala)| Regional Thin | INR 5,800.00 | 920,000 | **0.052** (5.2%) |

$$\sum_{j=1}^{10} w_j = 1.000000 \quad (\pm 10^{-6})$$

---

## 4. Directional Co-Movement & MoSPI Validation

- **Directional Accuracy:** Measures month-over-month price movement concordance:
  $$\text{Directional Accuracy} = \frac{1}{N} \sum_{t=1}^N \mathbf{1}(\text{sign}(\Delta \text{Prototype}_t) == \text{sign}(\Delta \text{MoSPI}_t)) \times 100\%$$
- **Pearson Correlation ($r$):** Evaluates linear co-movement independent of base year scaling differences ($r = 0.997$).
- **Methodological Disclosure:** High-frequency search quotes measure forward-looking expectations across 5 lead-time windows, whereas MoSPI CPI reflects retrospective survey collection on fixed routes and dates. Co-movement indicates alignment with broader macroeconomic inflation trends.
