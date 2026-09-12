"""Statistical tests for MoSPI benchmark ingestion, frequency matching, and directional co-movement."""

from database.session import SessionLocal
from packages.statistics.benchmark_matcher import BenchmarkMatcherService


def test_mospi_benchmark_csv_ingestion():
    """Verifies that MoSPI CPI benchmark CSV is ingested and persisted to database."""
    db = SessionLocal()
    try:
        records = BenchmarkMatcherService.ingest_mospi_benchmark_csv(db)
        assert len(records) == 20
        assert all(str(r.base_year) == "2012" for r in records)

        # Query series
        series = BenchmarkMatcherService.get_benchmark_series(db)
        assert len(series) == 20
        # Check chronological ordering
        assert series[0]["period"] == "2025-01"
        assert series[-1]["period"] == "2026-08"

    finally:
        db.close()


def test_directional_co_movement_metrics():
    """
    Verifies that directional co-movement achieves >= 80% directional accuracy
    and Pearson r >= 0.85 on aligned monthly series.
    """
    proto_series = [
        {"period": "2025-10", "index_value": 102.1},
        {"period": "2025-11", "index_value": 104.5},
        {"period": "2025-12", "index_value": 107.8},
        {"period": "2026-01", "index_value": 105.2},
        {"period": "2026-02", "index_value": 106.9},
        {"period": "2026-03", "index_value": 108.4},
        {"period": "2026-04", "index_value": 110.1},
        {"period": "2026-05", "index_value": 113.8},
    ]

    mospi_series = [
        {"period": "2025-10", "index_value": 152.6},
        {"period": "2025-11", "index_value": 156.4},
        {"period": "2025-12", "index_value": 161.8},
        {"period": "2026-01", "index_value": 157.3},
        {"period": "2026-02", "index_value": 159.5},
        {"period": "2026-03", "index_value": 162.1},
        {"period": "2026-04", "index_value": 166.4},
        {"period": "2026-05", "index_value": 171.2},
    ]

    scorecard = BenchmarkMatcherService.calculate_directional_co_movement(
        prototype_monthly=proto_series,
        mospi_monthly=mospi_series,
    )

    assert scorecard["status"] == "DIRECTIONAL_TRACKING"
    metrics = scorecard["metrics"]

    # Directional accuracy must be 100% since all period signs match (+, +, -, +, +, +, +)
    assert metrics["directional_accuracy_pct"] == 100.0
    # Pearson r must be > 0.95
    assert metrics["pearson_correlation_r"] > 0.95
    # p-value must be highly significant
    assert metrics["p_value"] < 0.001


def test_scale_invariance_of_directional_metrics():
    """
    Verifies that changing the base scale of one series (e.g. 2012=100 vs 2026=100)
    does not affect Pearson r or Directional Accuracy.
    """
    proto_series = [
        {"period": "2026-01", "index_value": 100.0},
        {"period": "2026-02", "index_value": 105.0},
        {"period": "2026-03", "index_value": 102.0},
        {"period": "2026-04", "index_value": 108.0},
    ]
    # Series with a completely different base level and multiplier
    mospi_series = [
        {"period": "2026-01", "index_value": 250.0},
        {"period": "2026-02", "index_value": 262.5},
        {"period": "2026-03", "index_value": 255.0},
        {"period": "2026-04", "index_value": 270.0},
    ]

    scorecard = BenchmarkMatcherService.calculate_directional_co_movement(
        prototype_monthly=proto_series,
        mospi_monthly=mospi_series,
    )

    metrics = scorecard["metrics"]
    assert metrics["directional_accuracy_pct"] == 100.0
    assert abs(metrics["pearson_correlation_r"] - 1.0) < 1e-4


def test_methodological_disclosure_presence():
    """Verifies that all scorecards contain the mandatory methodological disclosure footnote."""
    scorecard = BenchmarkMatcherService.calculate_directional_co_movement([], [])
    assert "methodology_disclosure" in scorecard
    disclosure = scorecard["methodology_disclosure"]
    assert "Directional co-movement analysis" in disclosure
    assert "retrospective survey collection" in disclosure
