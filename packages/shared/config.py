"""Configuration management using Pydantic Settings."""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    POSTGRES_USER: str = "airfare_user"
    POSTGRES_PASSWORD: str = "airfare_pass"
    POSTGRES_DB: str = "airfare_observatory"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql://airfare_user:airfare_pass@localhost:5432/airfare_observatory"
    DATABASE_URL_ASYNC: str = (
        "postgresql+asyncpg://airfare_user:airfare_pass@localhost:5432/airfare_observatory"
    )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"

    # Collection caching & resilience
    USE_CACHE: bool = True
    CACHE_TTL_SECONDS: int = 1800
    BROWSE_POOL_MAX_CONTEXTS: int = 4
    BROWSE_CONTEXT_IDLE_SECONDS: float = 300.0
    BROWSE_HEADLESS: bool = True

    # Scraping mode: "live" hits carrier portals / Google Flights RPC over the
    # network (with OCR escalation); "calibrated" bypasses the network entirely
    # and serves the deterministic, reproducible calibrated baseline so demos
    # and presentations never stall on a flaky/absent connection.
    SCRAPE_MODE: str = "live"  # "live" | "calibrated" | "hybrid"

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_ENV: str = "development"
    API_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # API key auth for the /api/v1/* consumer surface (e.g. NSO/RBI-grade
    # programmatic access). Off by default so local dev, the dashboard, and
    # the static /ui viewer keep working unauthenticated exactly as before;
    # flip API_KEY_REQUIRED=true and populate API_KEYS (comma-separated) to
    # require an X-API-Key header in production.
    API_KEY_REQUIRED: bool = False
    API_KEYS: str = ""

    # Statistical Methodology Configuration
    ACTIVE_METHODOLOGY_VERSION: str = "APIX-2.0"
    ACTIVE_WEIGHT_VERSION: str = "DGCA_2026_V1"
    ANCHOR_LEAD_TIME: str = "T+15"
    BASE_PERIOD: str = "2026-08-01"
    MINIMUM_COVERAGE_RATE: float = 80.0

    # Extraction stage control (OCR / VLM escalation)
    EXTRACTION_ALLOW_VLM: bool = True
    EXTRACTION_ALLOW_OCR: bool = True

    # OCR backend: "paddle" (PP-OCRv5/v6, default) or "tesseract" (local CLI,
    # v4/v5).  Tesseract emits the same geometry OCRTokens (bbox + confidence)
    # and is just another rung in the OCR→VLM ladder; when the binary is absent
    # it raises the same ExtractionNotAvailable as missing paddleocr, so the
    # chain still escalates to VLM.
    EXTRACTION_OCR_BACKEND: str = "paddle"

    # Quality Engine Thresholds
    QUALITY_MINIMUM_ACCEPT_SCORE: int = 70
    QUALITY_MINIMUM_PLAUSIBLE_PRICE: float = 1200.0
    QUALITY_MAXIMUM_PLAUSIBLE_PRICE: float = 60000.0

    # Confidence aggregation thresholds (composite score 0..100)
    CONFIDENCE_HIGH_MIN: float = 90.0
    CONFIDENCE_MEDIUM_MIN: float = 70.0

    # Index variance estimation (NSO-standard bootstrap around the point value).
    # Validated up front so a bad env var can never poison a published CI.
    INDEX_BOOTSTRAP_REPLICATIONS: int = Field(2000, ge=50, le=100_000)
    INDEX_VARIANCE_CI_LEVEL: float = Field(0.95, gt=0.5, lt=1.0)

    # Variance rung selector -- the production *default* is the deterministic
    # jackknife (exact, ~50-90x cheaper than bootstrap for the same SE).
    # Bootstrap stays selectable when a CI *distribution* (percentile tails)
    # is required.  A bad value degrades through IndexVarianceError -- a bad
    # method can never silently publish a variance contract.
    INDEX_VARIANCE_METHOD: str = Field("JACKKNIFE", pattern=r"^(JACKKNIFE|BOOTSTRAP)$")

    # Index variance estimator rung.  The deterministic jackknife is the default
    # (NSO-standard delete-one-route; exact, reproducible, ~10-50x cheaper than
    # bootstrap for the same SE) while bootstrap remains selectable when a CI
    # *distribution* (percentile tails) is required.  Setting it to a value
    # that is not a real rung degrades through ``IndexVarianceError`` -- a bad
    # method can never silently publish a variance contract.
    INDEX_VARIANCE_METHOD: str = Field("JACKKNIFE", pattern=r"^(JACKKNIFE|BOOTSTRAP)$")
    INDEX_VARIANCE_SEED: int | None = Field(
        None, description="Fixed seed => reproducible CI (testing only)"
    )

    # OpenRouter AI Copilot Configuration
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "minimax/minimax-m3:free"
    OPENROUTER_VISION_MODEL: str = ""  # empty -> ranked DEFAULT_FREE_VISION_MODELS
    OPENROUTER_SITE_URL: str = "http://localhost:3000"
    OPENROUTER_SITE_NAME: str = "India Airfare Observatory"

    # Amadeus Self-Service API (licensed GDS partner feed -- no scraping, no
    # evasion). Free test environment at https://developers.amadeus.com with
    # self-service keys; production requires an enterprise agreement. When
    # credentials are absent the AmadeusScraper raises AmadeusCredentialsMissing
    # and the base scraper degrades to the tagged calibrated fallback.
    AMADEUS_CLIENT_ID: str = ""
    AMADEUS_CLIENT_SECRET: str = ""
    AMADEUS_ENV: str = "test"  # "test" | "production"
    AMADEUS_BASE_URL: str = ""  # optional manual override

    # Sabre Developer Hub (self-service test account -> Username/Password ->
    # OAuth2 token -> Flight Shop API). Absent credentials make SabreScraper
    # raise SabreCredentialsMissing and degrade to the tagged calibrated
    # fallback, same as Amadeus.
    SABRE_USERNAME: str = ""
    SABRE_PASSWORD: str = ""
    SABRE_ENV: str = "cert"  # "cert" (PLAY test) | "prod"
    SABRE_TOKEN_URL: str = ""  # optional manual override
    SABRE_SHOP_URL: str = ""  # optional manual override

    # RapidAPI "Sky Scrapper" (Skyscanner wrapper, free tier). Absent key makes
    # SkyscannerScraper raise and degrade to the tagged calibrated fallback.
    RAPIDAPI_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.API_CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
