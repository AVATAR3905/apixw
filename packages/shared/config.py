"""Configuration management using Pydantic Settings."""

from typing import List

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

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_ENV: str = "development"
    API_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Statistical Methodology Configuration
    ACTIVE_METHODOLOGY_VERSION: str = "APIX-2.0"
    ACTIVE_WEIGHT_VERSION: str = "DGCA_2026_V1"
    ANCHOR_LEAD_TIME: str = "T+15"
    BASE_PERIOD: str = "2026-08-01"
    MINIMUM_COVERAGE_RATE: float = 80.0

    # Extraction stage control (OCR / VLM escalation)
    EXTRACTION_ALLOW_VLM: bool = True
    EXTRACTION_ALLOW_OCR: bool = True

    # Quality Engine Thresholds
    QUALITY_MINIMUM_ACCEPT_SCORE: int = 70
    QUALITY_MINIMUM_PLAUSIBLE_PRICE: float = 1200.0
    QUALITY_MAXIMUM_PLAUSIBLE_PRICE: float = 60000.0

    # Confidence aggregation thresholds (composite score 0..100)
    CONFIDENCE_HIGH_MIN: float = 90.0
    CONFIDENCE_MEDIUM_MIN: float = 70.0

    # OpenRouter AI Copilot Configuration
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "minimax/minimax-m3:free"
    OPENROUTER_SITE_URL: str = "http://localhost:3000"
    OPENROUTER_SITE_NAME: str = "India Airfare Observatory"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.API_CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
