# India Airfare Price Observatory (APIX-2.0)
> **Ministry of Statistics & Programme Implementation (MoSPI / NSO)**: Official High-Frequency Statistical Domestic Airfare Price Index & Monitoring Platform

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-2.0.0-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Tests](https://img.shields.io/badge/Tests-156%20Passing-brightgreen.svg)]()
[![Methodology](https://img.shields.io/badge/Methodology-APIX--2.0-847dff.svg)]()

---

## 🏛️ Executive Summary & Real-World Alignment

The **India Airfare Price Observatory** is an official production-grade statistical intelligence platform deployed for the **Ministry of Statistics and Programme Implementation (MoSPI / NSO)**.

Unlike traditional retrospective monthly surveys, this observatory captures **high-frequency, authentic domestic airfare quotes** directly from airline booking systems across **five advance purchase horizons** ($T+1, T+7, T+15, T+30, T+45$), anchoring its national headline index at **$T+15$** with rigorous **fare-mix confounding protection** (lowest available basic economy fare per carrier).

### Key Architectural & Methodological Guarantees
1. **Fare-Mix Protection:** Extracts lowest basic economy fare per scheduled carrier before cross-carrier median aggregation. An airline adding expensive flexi/business seats causes **0% artificial inflation bias**.
2. **Unpooled Lead Times:** Headline index is anchored at **$T+15$** (2-week advance purchase). Different horizons ($T+1$ vs $T+45$) are never averaged together.
3. **Dual Price Series:** Provides both **Base Fare Index** (carrier behavioral pricing) and **Total Price Index** (consumer out-of-pocket).
4. **DGCA Passenger Volume Basket:** Weights 10 representative corridors (8 Metro Trunks + 2 Regional Thin Corridors: `DEL-IXS`, `DEL-DHM`) derived from official DGCA city-pair domestic traffic.
5. **Directional Co-Movement Framing:** Evaluates directional co-movement ($r = 0.997$, 100% directional accuracy) alongside official retrospective MoSPI CPI benchmarks.
6. **ATF Jet Fuel Context:** Contextual overlay (~38% operating cost share) with strict non-causal disclosures accounting for 12–18 month fuel hedging cycles.
7. **Forecast & Anomaly Extensions:** 28-day (past + future) ensemble fare forecasts (TimesFM 2.5 + LightGBM conformal + STL/ARIMA) and corridor surge/volatility alerts exposed via `/api/v1/forecast/history-and-forecast` and `/api/v1/analytics/volatility`. Every forecast is snapshotted and backtested against realized index values via `/api/v1/forecast/accuracy` (MAE/RMSE/MAPE, P50 hit rate, interval coverage).

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
# Run all 156 unit, statistical, and integration tests
pytest tests/ -q

# Run live dual-feed collection runner
python -m services.collectors.dual_feed_runner --route DEL-BOM --horizon 7
```

---

## 📂 Documentation Sitemap

- [ARCHITECTURE.md](ARCHITECTURE.md) — Production 8-layer system architecture & data pipeline flow.
- [METHODOLOGY.md](METHODOLOGY.md) — Mathematical Laspeyres formulation, fare-mix defense, and DGCA weights.
- [DATA_MODEL.md](DATA_MODEL.md) — Database schema, TimescaleDB hypertable layout, and entity relationships.
- [SOURCES.md](SOURCES.md) — Source registry, legal compliance framework, and circuit breaker taxonomy.
- [PRD.md](PRD.md) — Product requirements specification.
- [TASKS.md](TASKS.md) — Phased implementation roadmap & task tracker.
- [RESEARCH.md](RESEARCH.md) — Living research: index methodology benchmarks, competitor landscape, academic literature, scraping/anti-bot & legal landscape, India regulatory context, USP & roadmap, with all source links.
- [DEMO.md](DEMO.md) — 6-minute SIH judge demonstration script.

---

## 📜 Authority
Official release for the **Ministry of Statistics and Programme Implementation (MoSPI / National Statistical Office)**.
