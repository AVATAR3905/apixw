"""SQLAlchemy Declarative Models for the India Airfare Price Observatory (v2.0)."""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

from packages.shared.time_utils import utcnow

Base = declarative_base()


class Source(Base):
    """Data source registry tracking compliance, access methods, and health states."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    type = Column(String(50), nullable=False)  # AIRLINE, OTA, GDS_API, PUBLIC_FEED
    access_method = Column(String(50), nullable=False)  # PLAYWRIGHT, REST_API, PUBLIC_SCRAPE
    permission_status = Column(
        String(50), default="REVIEW_REQUIRED"
    )  # REVIEW_REQUIRED, APPROVED, REJECTED
    tos_status = Column(String(50), default="PENDING")
    robots_status = Column(String(50), default="PENDING")
    license_status = Column(String(50), default="NOT_REQUIRED")
    access_mode = Column(
        String(20), default="PUBLIC"
    )  # PUBLIC, CONDITIONAL, PARTNER_ONLY (collection access policy)
    rate_limit = Column(Integer, default=10)  # requests per minute
    enabled = Column(Boolean, default=False)
    health_status = Column(String(50), default="HEALTHY")  # HEALTHY, WARNING, DEGRADED, DOWN
    last_reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    # Relationships
    observations = relationship("FareObservation", back_populates="source")
    raw_payloads = relationship("RawPayload", back_populates="source")
    collection_jobs = relationship("CollectionJob", back_populates="source")


class Route(Base):
    """Domestic route / city-pair corridors with corridor type classification."""

    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    origin = Column(String(50), nullable=False)  # Delhi
    destination = Column(String(50), nullable=False)  # Mumbai
    origin_airport = Column(String(10), nullable=False)  # DEL
    destination_airport = Column(String(10), nullable=False)  # BOM
    route_code = Column(String(20), unique=True, nullable=False)  # DEL-BOM
    corridor_type = Column(String(50), default="METRO_TRUNK")  # METRO_TRUNK, REGIONAL_THIN
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    observations = relationship("FareObservation", back_populates="route")
    weights = relationship("RouteWeight", back_populates="route")
    collection_jobs = relationship("CollectionJob", back_populates="route")
    index_values = relationship("IndexValue", back_populates="route")


class Airline(Base):
    """Operating domestic scheduled carriers."""

    __tablename__ = "airlines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), unique=True, nullable=False)  # 6E, AI, SG, QP, IX
    name = Column(String(100), nullable=False)
    is_scheduled = Column(Boolean, default=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    observations = relationship("FareObservation", back_populates="airline")


class RawPayload(Base):
    """Immutable, tamper-evident raw response payloads with SHA-256 hashes."""

    __tablename__ = "raw_payloads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    collection_job_id = Column(Integer, nullable=True)
    payload_uri = Column(String(255), nullable=False)
    payload_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hex
    content_type = Column(String(50), default="application/json")
    captured_at = Column(DateTime, default=utcnow)

    # Relationships
    source = relationship("Source", back_populates="raw_payloads")
    observations = relationship("FareObservation", back_populates="raw_payload")


class FareObservation(Base):
    """Standardized high-frequency fare observations with decomposition and quality scoring."""

    __tablename__ = "fare_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    airline_id = Column(Integer, ForeignKey("airlines.id"), nullable=False)

    search_timestamp = Column(DateTime, nullable=False, index=True)
    travel_date = Column(Date, nullable=False, index=True)
    advance_purchase_days = Column(Integer, nullable=False, index=True)  # 1, 7, 15, 30, 45

    flight_number = Column(String(20), nullable=False)
    cabin_class = Column(String(20), default="ECONOMY")  # ECONOMY, PREMIUM_ECONOMY, BUSINESS
    fare_family = Column(String(50), default="BASIC")  # BASIC, FLEXI, COMFORT
    stops = Column(Integer, default=0)

    availability_status = Column(String(30), default="AVAILABLE")  # AVAILABLE, SOLD_OUT, CANCELLED
    is_carrier_min_fare = Column(
        Boolean, default=False, index=True
    )  # True if cheapest economy quote for carrier

    # Fare Decomposition Components (INR)
    base_fare = Column(Float, nullable=False)
    fuel_surcharge = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)  # GST
    development_fee = Column(Float, default=0.0)  # UDF / ADF
    convenience_fee = Column(Float, default=0.0)
    other_fee = Column(Float, default=0.0)
    total_fare = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")

    # Quality & Provenance
    is_synthetic = Column(Boolean, default=False, index=True)  # Provenance tracking
    feed_type = Column(
        String(30), default="CALIBRATED_BASELINE"
    )  # CARRIER_DIRECT, RPC_FALLBACK, CALIBRATED_BASELINE
    extraction_method = Column(
        String(40), default="NETWORK"
    )  # DOM_BROWSER, NETWORK_XHR, EMBEDDED, OCR, VLM, LLM, RPC, CALIBRATED_MODEL, SYNTHETIC
    quality_score = Column(Float, default=100.0)
    quality_status = Column(
        String(30), default="ACCEPT"
    )  # ACCEPT, ACCEPT_WITH_WARNING, REVIEW, REJECT

    collector_version = Column(String(20), default="1.0.0")
    schema_version = Column(String(20), default="2.0.0")
    raw_payload_id = Column(Integer, ForeignKey("raw_payloads.id"), nullable=True)

    created_at = Column(DateTime, default=utcnow)

    # Relationships
    source = relationship("Source", back_populates="observations")
    route = relationship("Route", back_populates="observations")
    airline = relationship("Airline", back_populates="observations")
    raw_payload = relationship("RawPayload", back_populates="observations")

    __table_args__ = (
        Index("idx_fare_lookup", "route_id", "travel_date", "advance_purchase_days", "cabin_class"),
        Index("idx_search_carrier", "search_timestamp", "airline_id"),
    )


class RouteWeight(Base):
    """DGCA passenger traffic volume route weights."""

    __tablename__ = "route_weights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    passenger_volume = Column(Float, nullable=False)  # Annual or quarterly boarded passengers
    weight = Column(Float, nullable=False)  # Normalized weight (sum = 1.0)
    source = Column(String(100), default="DGCA Domestic Scheduled Passenger Traffic")
    period = Column(String(50), nullable=False)  # 2025-Q4, 2026-Q1
    methodology_version = Column(String(50), default="APIX-2.0")
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    route = relationship("Route", back_populates="weights")


class CollectionJob(Base):
    """Asynchronous collection job execution records."""

    __tablename__ = "collection_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    search_date = Column(Date, nullable=False)
    travel_date = Column(Date, nullable=False)
    advance_days = Column(Integer, nullable=False)
    status = Column(String(30), default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    attempt_count = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    route = relationship("Route", back_populates="collection_jobs")
    source = relationship("Source", back_populates="collection_jobs")


class IndexValue(Base):
    """Calculated airfare price index values (headline T+15, lead-time sub-indices, route indices)."""

    __tablename__ = "index_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_series = Column(String(30), default="BASE_FARE", nullable=False)  # BASE_FARE, TOTAL_PRICE
    series_type = Column(
        String(20), default="HEADLINE", nullable=False, index=True
    )  # HEADLINE (all travel dates) | CORE (volatility-guarded)
    index_type = Column(
        String(30), default="HEADLINE_T15", nullable=False
    )  # HEADLINE_T15, SUB_T1, SUB_T7, SUB_T15, SUB_T30, SUB_T45, ROUTE_LEVEL
    lead_time_days = Column(Integer, default=15, nullable=False)

    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False)
    route_id = Column(
        Integer, ForeignKey("routes.id"), nullable=True
    )  # Null for national aggregate

    index_value = Column(Float, nullable=False)
    daily_change_pct = Column(Float, nullable=True)
    weekly_change_pct = Column(Float, nullable=True)
    monthly_change_pct = Column(Float, nullable=True)

    coverage_rate = Column(Float, default=100.0)  # Percentage of valid observed routes
    is_low_coverage = Column(Boolean, default=False)

    methodology_version = Column(String(50), default="APIX-2.0")
    weight_version = Column(String(50), default="DGCA_2026_V1")
    calculated_at = Column(DateTime, default=utcnow)

    # Quality & governance fields (Skytra/FAX methodology)
    index_status = Column(
        String(20), default="EXPERIMENTAL", nullable=False
    )  # EXPERIMENTAL, BETA, LIVE, DEPRECATED
    quality_score = Column(Float, default=0.0)  # 0-100 composite quality
    data_completeness = Column(Float, default=0.0)  # 0-100 % of expected routes
    carrier_diversity = Column(Integer, default=0)  # Number of contributing carriers
    feed_quality_score = Column(Float, default=0.0)  # Weighted feed quality
    outlier_count = Column(Integer, default=0)  # Outliers detected
    index_divisor = Column(Float, default=1.0)  # Continuity divisor (Skytra)
    moving_avg_28d = Column(Float, nullable=True)  # 28-day moving average
    spot_window_start = Column(Date, nullable=True)  # BLS-style spot window
    spot_window_end = Column(Date, nullable=True)

    # Variance estimation (NSO-standard uncertainty around the point estimate).
    # Filled by bootstrap / jackknife resampling of the elementary route-horizon
    # cells so every published index value carries a standard error and CI.
    standard_error = Column(Float, nullable=True)  # Bootstrap SE of index_value
    index_ci_lower = Column(Float, nullable=True)  # Percentile-CI lower bound
    index_ci_upper = Column(Float, nullable=True)  # Percentile-CI upper bound
    bootstrap_replications = Column(Integer, nullable=True)  # Resample count
    variance_method = Column(
        String(40), nullable=True
    )  # BOOTSTRAP_PERCENTILE_95 / JACKKNIFE_LEAVE_ONE_ROUTE_OUT

    # Relationships
    route = relationship("Route", back_populates="index_values")

    __table_args__ = (Index("idx_index_lookup", "index_series", "index_type", "series_type", "period_start"),)


class BenchmarkValue(Base):
    """Official benchmark series (MoSPI CPI Transport & Communication / Airfare component)."""

    __tablename__ = "benchmark_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    period = Column(String(20), nullable=False, index=True)  # YYYY-MM
    indicator = Column(String(100), default="CPI_TRANSPORT_AIRFARE")
    value = Column(Float, nullable=False)
    base_year = Column(String(20), default="2012=100")
    source = Column(String(100), default="MoSPI / NSO / eSankhyiki")
    source_version = Column(String(50), default="CPI_2026_M")
    created_at = Column(DateTime, default=utcnow)


class ValidationResult(Base):
    """Directional co-movement & statistical tracking metrics between prototype and official benchmark."""

    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    series_evaluated = Column(String(50), default="HEADLINE_T15_BASE_FARE")
    correlation = Column(Float, nullable=False)  # Pearson r
    mae = Column(Float, nullable=False)  # Mean Absolute Error
    rmse = Column(Float, nullable=False)  # Root Mean Squared Error
    directional_accuracy = Column(
        Float, nullable=False
    )  # % where sign(delta_prototype) == sign(delta_official)
    prototype_series_version = Column(String(50), default="APIX-2.0")
    benchmark_version = Column(String(50), default="MoSPI_CPI_AIRFARE")
    methodology_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class DiscrepancyAudit(Base):
    """Cross-feed and source-pair validation audits.

    Two audit modes are persisted into this table:
    1. CROSS_FEED (legacy): carrier direct website quotes vs RPC aggregator feed.
    2. OTA_SOURCE_PAIR (Phase 2): pairwise markup of any source (OTA vs OTA or
       OTA vs carrier-direct reference) for the same physical flight entity.
    """

    __tablename__ = "discrepancy_audits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    airline_id = Column(Integer, ForeignKey("airlines.id"), nullable=False)
    flight_number = Column(String(20), nullable=False)
    travel_date = Column(Date, nullable=False, index=True)
    advance_purchase_days = Column(Integer, nullable=False)

    carrier_direct_price = Column(Float, nullable=True)
    rpc_validator_price = Column(Float, nullable=True)
    discrepancy_amount = Column(Float, default=0.0)  # reference - comparator
    discrepancy_pct = Column(Float, default=0.0)  # |delta| / reference * 100
    validation_status = Column(
        String(50), default="EXACT_PARITY"
    )  # EXACT_PARITY, AGGREGATOR_MARKUP, AGGREGATOR_DISCOUNT, FALLBACK_RPC_USED, DIRECT_ONLY

    # Source-pair markup audit fields (Phase 2). Null for legacy CROSS_FEED rows.
    audit_type = Column(
        String(30), default="CROSS_FEED", nullable=False
    )  # CROSS_FEED, OTA_SOURCE_PAIR
    source_a_id = Column(Integer, nullable=True)  # reference source (cheapest observed)
    source_b_id = Column(Integer, nullable=True)  # comparator source
    source_a_name = Column(String(100), nullable=True)
    source_b_name = Column(String(100), nullable=True)
    feed_type_a = Column(String(30), nullable=True)
    feed_type_b = Column(String(30), nullable=True)
    price_a = Column(Float, nullable=True)  # reference price (INR)
    price_b = Column(Float, nullable=True)  # comparator price (INR)
    markup_amount = Column(Float, nullable=True)  # price_b - price_a
    markup_pct = Column(Float, nullable=True)  # (price_b - price_a) / price_a * 100

    notes = Column(String(255), nullable=True)
    verified_at = Column(DateTime, default=utcnow)

    # Relationships
    route = relationship("Route")
    airline = relationship("Airline")

    __table_args__ = (
        Index("idx_audit_type_travel", "audit_type", "travel_date"),
    )


class SourceCorrelation(Base):
    """Rolling-window Pearson correlation between feed cohorts (Phase 5).

    Tracks whether OTA_AGGREGATOR observations track the authoritative
    carrier-direct reference per route/horizon over a trailing window, so a
    divergence (falling r) can be escalated as a data-quality alert.
    """

    __tablename__ = "source_correlations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)
    horizon_days = Column(Integer, nullable=False)
    correlation_type = Column(
        String(40), default="OTA_VS_CARRIER_DIRECT", nullable=False
    )  # OTA_VS_CARRIER_DIRECT, OTA_ENSEMBLE_VS_HEADLINE
    source_a = Column(String(100), nullable=False)  # descriptive series name
    source_b = Column(String(100), nullable=False)
    pearson_r = Column(Float, nullable=False)
    sample_size = Column(Integer, default=0)
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    route = relationship("Route")

    __table_args__ = (
        Index("idx_corr_lookup", "correlation_type", "period_end", "route_id"),
    )


class AnomalyEvent(Base):
    """Persisted price anomaly / spike alerts surfaced via the detector pipeline.

    Each row is a single point-in-time anomaly hit on a national index series
    (or route-level series when route_id is set) and tracks escalation status
    so operations can triage and resolve alerts.
    """

    __tablename__ = "anomaly_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series = Column(String(20), default="BASE_FARE", nullable=False)
    series_type = Column(String(20), default="HEADLINE", nullable=False)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)

    observation_date = Column(Date, nullable=False)
    anomaly_type = Column(
        String(40), default="PRICE_OUTLIER", nullable=False
    )  # PRICE_OUTLIER, INDEX_SPIKE, FEED_DIVERGENCE
    severity = Column(
        String(20), default="LOW", nullable=False
    )  # LOW, MODERATE, SEVERE

    z_score = Column(Float, nullable=True)
    reference_median = Column(Float, nullable=True)
    detected_value = Column(Float, nullable=True)
    reference_values_sample = Column(String(255), nullable=True)
    notes = Column(String(255), nullable=True)

    status = Column(
        String(20), default="OPEN", nullable=False
    )  # OPEN, ESCALATED, RESOLVED
    detected_at = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime, nullable=True)

    route = relationship("Route")

    __table_args__ = (
        Index("idx_anomaly_lookup", "observation_date", "series", "status"),
    )


class ATFPrice(Base):
    """Metropolitan Aviation Turbine Fuel (ATF / Jet Fuel) price records."""

    __tablename__ = "atf_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    location = Column(String(50), nullable=False)  # Delhi, Mumbai, Kolkata, Chennai
    date = Column(Date, nullable=False, index=True)
    price_per_kl = Column(Float, nullable=False)  # INR per kilo litre (kL)
    source = Column(String(50), default="IOCL / PPAC")
    created_at = Column(DateTime, default=utcnow)


class ATFTaxRate(Base):
    """VAT and excise duty rates applicable to Aviation Turbine Fuel."""

    __tablename__ = "atf_tax_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    tax_type = Column(String(50), nullable=False)  # CENTRAL_EXCISE, STATE_VAT
    rate = Column(Float, nullable=False)  # Percentage rate
    source = Column(String(50), default="PPAC")
    created_at = Column(DateTime, default=utcnow)


class MethodologyVersion(Base):
    """Transparent statistical methodology registry."""

    __tablename__ = "methodology_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), unique=True, nullable=False)  # APIX-2.0
    name = Column(String(100), nullable=False)
    base_period = Column(String(50), default="2026-08-01")
    anchor_lead_time = Column(String(20), default="T+15")
    price_estimator = Column(String(50), default="LOWEST_ECONOMY_JEVONS_GEOMETRIC_MEAN")
    missing_data_method = Column(String(50), default="EXCLUDE_SOLD_OUT_RECORD_COVERAGE")
    outlier_method = Column(String(50), default="ROBUST_MEDIAN_FILTER")
    weight_method = Column(String(50), default="DGCA_BIDIRECTIONAL_PASSENGER_VOLUME")
    formula = Column(Text, nullable=False)
    effective_from = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class DGCAMonthlyFare(Base):
    """Monthly average fares per domestic sector from DGCA scheduled traffic reports.

    DGCA publishes `Air Transport Statistics` (table 6 / 7) with sector-wise
    average fare data.  This table stores the official published fare series so
    that the Observatory can benchmark its high-frequency prototype index against
    the authoritative government reference.
    """

    __tablename__ = "dgca_monthly_fares"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    period = Column(String(20), nullable=False, index=True)  # YYYY-MM
    sector_type = Column(String(20), default="METRO_TRUNK")  # METRO_TRUNK, REGIONAL_THIN, ALL
    average_fare = Column(Float, nullable=False)  # INR one-way average economy
    total_passengers = Column(Float, nullable=True)  # boarded pax
    source = Column(String(100), default="DGCA Air Transport Statistics")
    source_version = Column(String(50), default="DGCA_ATS_2026")
    created_at = Column(DateTime, default=utcnow)

    route = relationship("Route")

    __table_args__ = (
        Index("idx_dgca_fare_lookup", "route_id", "period", "sector_type"),
    )


class CarrierIndex(Base):
    """Carrier-specific Laspeyres airfare price index series for tracking independent pricing strategies."""

    __tablename__ = "carrier_indices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    carrier_code = Column(String(10), nullable=False, index=True)  # '6E', 'AI', 'SG', 'QP'
    period_date = Column(Date, nullable=False, index=True)
    horizon_days = Column(Integer, nullable=False, default=15)  # T+15 anchor
    carrier_index_value = Column(Float, nullable=False)
    base_period_date = Column(Date, nullable=False)
    daily_change_pct = Column(Float, nullable=True)
    weekly_change_pct = Column(Float, nullable=True)
    monthly_change_pct = Column(Float, nullable=True)
    routes_covered = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class ForecastSnapshot(Base):
    """Persisted forecast snapshot for backtesting accuracy against realized index values."""

    __tablename__ = "forecast_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    generated_at = Column(DateTime, default=utcnow, index=True)
    series = Column(String(30), default="BASE_FARE", nullable=False)  # BASE_FARE, TOTAL_PRICE
    index_type = Column(String(30), nullable=False)  # HEADLINE_T15, SUB_T1, ...
    forecast_date = Column(Date, nullable=False, index=True)  # last observed index date
    target_date = Column(Date, nullable=False, index=True)  # day being forecast
    horizon_days = Column(Integer, nullable=False)

    p10 = Column(Float, nullable=True)
    p25 = Column(Float, nullable=True)
    p50 = Column(Float, nullable=True)
    p75 = Column(Float, nullable=True)
    p90 = Column(Float, nullable=True)
    model_confidence = Column(Float, nullable=True)

    ensemble_weights = Column(Text, nullable=True)  # JSON dump of model weights
    model_versions = Column(Text, nullable=True)  # JSON dump of ensemble model versions
    history_days = Column(Integer, nullable=True)  # context length used to forecast

    __table_args__ = (
        Index("idx_forecast_snapshot_lookup", "series", "index_type", "forecast_date", "target_date"),
    )


class RouteVolatilityRecord(Base):
    """Corridor-level price volatility metrics and intraday range spread."""

    __tablename__ = "route_volatility_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    calculation_date = Column(Date, nullable=False, index=True)
    horizon_days = Column(Integer, nullable=False, default=14)
    min_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    mean_price = Column(Float, nullable=False)
    median_price = Column(Float, nullable=False)
    spread_pct = Column(Float, nullable=False)  # (max - min) / mean * 100
    std_dev = Column(Float, nullable=False)  # sigma
    volatility_status = Column(
        String(30), default="CALM"
    )  # CALM, MODERATE, HIGH_VOLATILITY, SURGE_ALERT
    sample_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    route = relationship("Route")
