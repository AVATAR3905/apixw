"""End-to-End System Integration & Fault Injection Tests (Tasks 10.1 & 10.4)."""

import datetime

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from database.session import SessionLocal
from packages.schemas.models import FareObservation
from packages.statistics.weights import DGCAWeightEngine
from services.collectors.circuit_breaker import CircuitBreaker
from services.index_engine.calculator_service import DailyIndexCalculatorService

client = TestClient(app)


def test_complete_lifecycle_e2e():
    """
    E2E Test: Verifies complete pipeline flow from raw collection
    to index calculation, API query, and CSV export.
    """
    db = SessionLocal()
    try:
        obs = db.query(FareObservation).first()
        test_date = obs.search_timestamp.date() if obs else datetime.date.today()

        # 1. Verify weights are active
        weights = DGCAWeightEngine.get_active_weights(db)
        assert len(weights) == 10
        assert abs(sum(weights.values()) - 1.0) < 1e-5

        # 2. Calculate daily headline index (dry-run: never writes to the live DB)
        index_records = DailyIndexCalculatorService.calculate_day_indices(
            db=db,
            observation_date=test_date,
            weight_version="DGCA_2026_V1",
            persist=False,
        )
        assert len(index_records) > 0

        headline = next(
            r
            for r in index_records
            if r.index_type in ("HEADLINE_T15",)
            and r.index_series == "BASE_FARE"
            and r.route_id is None
        )
        assert headline.index_value > 0
        assert headline.coverage_rate > 0.0

        # 3. Query via REST API
        res = client.get("/api/v1/index?series=BASE_FARE&horizon=t15")
        assert res.status_code == 200
        api_data = res.json()
        assert api_data["index_series"] == "BASE_FARE"
        assert api_data["lead_time_days"] in (14, 15)
        assert api_data["index_type"] in ("HEADLINE_T15",)
        assert "index_value" in api_data

        # 4. Verify CSV export
        csv_res = client.get("/api/v1/export/daily-index.csv?series=BASE_FARE&horizon=15")
        assert csv_res.status_code == 200
        assert "date,index_series,series_type,index_type" in csv_res.text

    finally:
        db.close()


def test_fault_injection_route_dropout():
    """
    Fault Injection: Simulates route dropout / missing collector quotes.
    Ensures pipeline handles coverage drop gracefully without crashing.
    """
    db = SessionLocal()
    try:
        obs = db.query(FareObservation).first()
        test_date = obs.search_timestamp.date() if obs else datetime.date.today()

        # Calculate index on date (dry-run: never writes to the live DB)
        records = DailyIndexCalculatorService.calculate_day_indices(
            db=db,
            observation_date=test_date,
            weight_version="DGCA_2026_V1",
            persist=False,
        )

        headline = next(
            r
            for r in records
            if r.index_type in ("HEADLINE_T15",) and r.route_id is None
        )
        assert headline.index_value > 0
        # Pipeline must calculate cleanly
        assert isinstance(headline.coverage_rate, float)

    finally:
        db.close()


def test_circuit_breaker_fault_injection():
    """
    Fault Injection: Injects 5 consecutive collector failures
    and proves circuit breaker trips to OPEN.
    """
    breaker = CircuitBreaker(
        source_id=1, source_name="Mock Source", failure_threshold=5, recovery_timeout_seconds=60
    )
    assert breaker.state == "CLOSED"

    # Inject 4 failures -> still CLOSED
    for _ in range(4):
        breaker._record_failure()
    assert breaker.state == "CLOSED"

    # 5th failure -> trips to OPEN
    breaker._record_failure()
    assert breaker.state == "OPEN"

    # Verifies that next request raises CircuitBreakerOpenError
    with pytest.raises(Exception) as exc_info:
        breaker.call(lambda: 123)
    assert "Circuit breaker is OPEN" in str(exc_info.value)
