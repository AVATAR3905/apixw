"""Statistical tests verifying DGCA route weight ingestion, normalization, and versioning."""

import datetime

import pytest

from database.session import SessionLocal
from packages.schemas.models import RouteWeight
from packages.statistics.weights import DGCAWeightEngine, WeightCalculationError

CSV_PATH = "data/reference/dgca_traffic.csv"


def test_dgca_traffic_csv_bidirectional_parsing():
    """Verifies that directional flows (DEL->BOM and BOM->DEL) are aggregated into city pairs."""
    volumes = DGCAWeightEngine.parse_traffic_csv(CSV_PATH)
    assert len(volumes) == 10
    # DEL-BOM: 1,650,000 + 1,600,000 = 3,250,000
    assert volumes["DEL-BOM"] == 3250000.0
    # DEL-BLR: 1,270,000 + 1,240,000 = 2,510,000
    assert volumes["DEL-BLR"] == 2510000.0
    # Regional routes
    assert volumes["DEL-IXS"] == 1020000.0
    assert volumes["DEL-DHM"] == 920000.0


def test_weights_sum_to_one():
    """Verifies strict normalization: sum(w_j) == 1.0 within 1e-6."""
    volumes = DGCAWeightEngine.parse_traffic_csv(CSV_PATH)
    weights = DGCAWeightEngine.compute_normalized_weights(volumes)

    assert len(weights) == 10
    total_weight = sum(weights.values())
    assert abs(total_weight - 1.0) <= 1e-6

    # Verify hierarchy: DEL-BOM is highest volume, DHM is lowest
    assert weights["DEL-BOM"] > weights["DEL-BLR"] > weights["DEL-IXS"] > weights["DEL-DHM"]


def test_normalization_error_on_zero_volume():
    """Zero or negative volume raises WeightCalculationError."""
    with pytest.raises(WeightCalculationError):
        DGCAWeightEngine.compute_normalized_weights({"DEL-BOM": 0.0, "DEL-BLR": 0.0})


def test_persist_weights_and_lineage_versioning():
    """Verifies database persistence, version tagging, and historical expiry."""
    db = SessionLocal()
    try:
        new_version_tag = "DGCA_2026_Q2_TEST"
        effective_date = datetime.date(2026, 4, 1)

        weights = DGCAWeightEngine.persist_weights_version(
            db=db,
            csv_path=CSV_PATH,
            version_tag=new_version_tag,
            effective_from=effective_date,
            period="2026-Q1",
        )

        assert len(weights) == 10

        # Query active weights on effective_date
        active = DGCAWeightEngine.get_active_weights(db, target_date=effective_date)
        assert len(active) == 10
        assert abs(sum(active.values()) - 1.0) <= 1e-4

        # Verify prior weights were closed (have effective_to date set)
        prior = db.query(RouteWeight).filter(RouteWeight.effective_from < effective_date).all()
        assert all(p.effective_to is not None for p in prior)

    finally:
        # Cleanup test version
        db.query(RouteWeight).filter(RouteWeight.methodology_version == new_version_tag).delete()
        # Re-open initial weights
        db.query(RouteWeight).filter(
            RouteWeight.effective_from == datetime.date(2026, 1, 1)
        ).update({"effective_to": None})
        db.commit()
        db.close()


def test_methodology_limitation_disclosure():
    """Verifies that the methodological disclosure on boarded vs price exposure is documented."""
    note = DGCAWeightEngine.METHODOLOGY_LIMITATION_NOTE
    assert "boarded passenger volumes" in note
    assert "consumer price exposure" in note
    assert "regional/thin corridors" in note
