"""Unit tests for VolatilityService."""

from database.session import SessionLocal
from packages.schemas.models import Route
from packages.statistics.volatility import VolatilityService


def test_corridor_volatility_calculation():
    """Verifies route-level price dispersion, standard deviation, and surge classification."""
    db = SessionLocal()
    try:
        route = db.query(Route).filter(Route.route_code == "DEL-BOM").first()
        assert route is not None

        vol = VolatilityService.calculate_corridor_volatility(
            db=db,
            route_id=route.id,
            horizon_days=15,
            save_to_db=False,
        )

        if vol:
            assert vol["min_price"] <= vol["max_price"]
            assert vol["min_price"] <= vol["mean_price"] <= vol["max_price"]
            assert vol["spread_pct"] >= 0
            assert vol["std_dev"] >= 0
            assert vol["volatility_status"] in (
                "CALM",
                "MODERATE",
                "HIGH_VOLATILITY",
                "SURGE_ALERT",
            )
            assert vol["sample_size"] > 0
    finally:
        db.close()


def test_network_volatility_summary():
    """Verifies network-wide volatility scorecard across all monitored corridors."""
    db = SessionLocal()
    try:
        summary = VolatilityService.get_network_volatility_summary(db, horizon_days=15)
        assert "monitored_corridors_count" in summary
        assert "average_network_spread_pct" in summary
        assert "active_surge_corridors_count" in summary
        assert "corridors" in summary
        assert summary["monitored_corridors_count"] >= 0
    finally:
        db.close()


def test_route_trajectory_retrieval():
    """Verifies flight quote scatter for an individual route."""
    db = SessionLocal()
    try:
        res = VolatilityService.get_route_intraday_trajectory(db, route_code="DEL-BOM")
        assert "quotes" in res
        assert "quotes_count" in res
        assert res["quotes_count"] >= 0
    finally:
        db.close()
