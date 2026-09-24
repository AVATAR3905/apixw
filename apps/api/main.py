import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from apps.api.middleware.rate_limit import RateLimitMiddleware
from apps.api.routers.ai_router import router as ai_router
from apps.api.routers.api_v1 import router as api_v1_router
from apps.api.routers.apix_ui import router as apix_ui_router
from apps.api.routers.exports import router as export_router
from apps.api.routers.ota_router import router as ota_router
from database.session import init_db
from packages.shared.config import settings
from services.scheduler.collection_scheduler import CollectionScheduler

scheduler = CollectionScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: apply additive schema migrations, then activate daily background scheduler
    try:
        init_db()
        print("[*] Database schema synchronized (incl. additive migrations).")
    except Exception as e:
        print(f"[!] Warning: Database schema sync exception: {e}")
    try:
        scheduler.start(cron_hour=18, cron_minute=0)
        print("[*] Background CollectionScheduler running: Daily cron set to 18:00 IST.")
    except Exception as e:
        print(f"[!] Warning: CollectionScheduler startup exception: {e}")
    yield
    # Shutdown
    scheduler.stop()
    print("[*] CollectionScheduler cleanly stopped.")


openapi_tags = [
    {
        "name": "Public National Indices",
        "description": "Official daily Laspeyres Headline Index (T+15), the volatility-guarded CORE dual-series, and advance purchase Sub-Indices (T+1, T+7, T+15, T+30, T+45) with day-on-day rates of change, sample coverage rates, and daily/monthly CSV exports.",
    },
    {
        "name": "Corridor Intelligence",
        "description": "City-pair analytics across 10 monitored domestic corridors, DGCA passenger weights, advance yield curves, and statutory 5-component fare deconstruction.",
    },
    {
        "name": "Forecasting",
        "description": "Ensemble time-series forecasts (Prophet, XGBoost, theta) with prediction intervals, historical accuracy tracking against rolling cutoffs, and backfill validation.",
    },
    {
        "name": "Live Scraper Pipeline",
        "description": "Real-time dual-feed ingestion engine (Carrier Direct + Google Flights RPC), live quote feeds, collection triggers, and automated scheduler controls.",
    },
    {
        "name": "Statistical Analytics",
        "description": "Carrier-level inflation decomposition, volatility regime metrics, and automated market briefings.",
    },
    {
        "name": "Governance & Policy Intelligence",
        "description": "RBI MPC policy-transmission classifier, Billion-Prices lead-lag vs official CPI, "
        "explainable anomaly alerts, carrier HHI competition monitoring, intraday pricing volatility "
        "index, availability-adjusted index, and UDAN route affordability — the Observatory's "
        "policy-instrument layer for MoSPI evaluators, RBI monetary policy, and CCI competition.",
    },
    {
        "name": "Multi-OTA & Carrier Pricing",
        "description": "Side-by-side airfare comparison across Direct Carriers and top 6 Indian OTAs (MakeMyTrip, EaseMyTrip, Ixigo, Cleartrip, Yatra, Skyscanner): canonical pricing, source-pair markup audits, and feed-cohort correlation tracking.",
    },
    {
        "name": "Observatory AI Intelligence",
        "description": "Econometric matrix queries and macro context synthesis via OpenRouter inference.",
    },
    {
        "name": "Researcher Data Exports",
        "description": "OSI-compliant bulk data export endpoints (daily index CSV/JSON, DGCA basket weights) with strict rate limiting.",
    },
    {
        "name": "APIx Viewer",
        "description": "Single-file HTML viewer endpoints serving the APIx dashboard UI (routes, index, heatmaps, backtests).",
    },
]

app = FastAPI(
    title="India Airfare Price Observatory Public API",
    summary="Production High-Frequency Statistical Airfare Price Index & Monitoring Platform (APIX-2.0)",
    description=r"""
### Ministry of Statistics and Programme Implementation (MoSPI / NSO)

The **India Airfare Price Observatory** is an institutional econometric platform providing high-frequency, tamper-evident airfare indices, carrier inflation dynamics, and corridor yield curves across the Indian domestic aviation network.

#### Core Public API Endpoints
* **`GET /api/v1/index/daily`**: Daily Laspeyres Headline and Sub-Index time-series.
* **`GET /api/v1/corridors/{pair}`**: Deep-dive corridor intelligence and 5-part fee decomposition.
* **`GET /api/v1/corridors`**: Overview of all 10 monitored domestic corridors.
* **`GET /api/v1/quotes/live`**: Live verified quotes stream with authentic source badges & timestamps.
* **`POST /api/v1/collection/run`**: Trigger real scraper ingestion across routes & horizons.

#### Econometric Methodology
* **Formula**: Fixed-Base Laspeyres Price Index ($I_t = \frac{\sum P_t \cdot Q_0}{\sum P_0 \cdot Q_0} \times 100$)
* **Base Period**: August 1, 2026 ($I_0 = 100.00$)
* **Anchor Horizon**: Departure minus 15 days ($T+15$)
* **Passenger Weights**: Official DGCA City-Pair Traffic Statistics (DGCA_2026_V1)

#### Dual-Series Architecture
* **HEADLINE**: Raw all-feed Laspeyres series — the market's fastest readout.
* **CORE**: Festival/peak-exclusion-guarded series that skips days lacking a continuous, non-fallback base reference (resilient against peak-week distortion).
* Fetch either via `GET /api/v1/index?series_type=HEADLINE|CORE`.

#### Governance & Policy Intelligence (RBI MPC / CCI / MoCA layer)
* **`GET /api/v1/analytics/policy-signal`** — Transient vs Structural fare-elevation classifier with a one-line monetary-policy readout.
* **`GET /api/v1/analytics/leading-indicator`** — Billion-Prices lead-lag (1-4 week) vs official MoSPI CPI airfare.
* **`GET /api/v1/analytics/alerts`** — Explainable anomaly feed (ATF / festival / availability / day-of-week correlation).
* **`GET /api/v1/analytics/concentration`** — Route HHI carrier concentration, CCI-relevant.
* **`GET /api/v1/analytics/intraday-volatility`** — Coefficient-of-variation index + best-time-to-book signal.
* **`GET /api/v1/analytics/availability-adjusted`** — Scarcity-corrected index for SOLD_OUT pressure.
* **`GET /api/v1/analytics/udan`** — UDAN scheme affordability monitor for REGIONAL_THIN routes.

#### Rate Limiting
* **General limit**: **120 requests/minute** per client IP on all API endpoints.
* **Export endpoints** (`/api/v1/export/*`): **20 requests/minute**.
* Limiter is a fixed sliding window; breaches return **`429 Too Many Requests`** with a `Retry-After: 60` header.
* Every response carries `X-RateLimit-Limit` and `X-RateLimit-Remaining`.
* Exempt: `/`, `/health`, `/docs/*`, `/redoc`, `/openapi.json`, and `/ui/*` viewer paths.
""",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router)
app.include_router(export_router)
app.include_router(ai_router)
app.include_router(ota_router)
app.include_router(apix_ui_router)

# New single-file APIx viewer (AyushyaRanjan/APIx frontend) at /ui
_ui_dir = os.path.join(os.path.dirname(__file__), "static_ui")
if os.path.isdir(_ui_dir):
    app.mount("/ui", StaticFiles(directory=_ui_dir, html=True), name="ui")


@app.get("/")
def root():
    """Root metadata & service identity."""
    return {
        "service": "India Airfare Price Observatory API",
        "authority": "Ministry of Statistics & Programme Implementation (MoSPI / NSO)",
        "active_methodology_version": settings.ACTIVE_METHODOLOGY_VERSION,
        "active_weight_version": settings.ACTIVE_WEIGHT_VERSION,
        "anchor_lead_time": settings.ANCHOR_LEAD_TIME,
        "base_period": settings.BASE_PERIOD,
        "documentation": "/docs",
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "methodology": settings.ACTIVE_METHODOLOGY_VERSION,
    }
