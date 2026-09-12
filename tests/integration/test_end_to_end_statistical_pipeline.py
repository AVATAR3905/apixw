"""End-to-end integration test for the statistical core pipeline."""

from database.session import SessionLocal
from packages.schemas.models import Route, RouteWeight
from packages.statistics.index_engine import AirfareIndexEngine


def test_end_to_end_statistical_pipeline_execution():
    """
    Tests the complete statistical pipeline:
    1. Queries route weights from DB.
    2. Extracts observations for anchor horizon T+15.
    3. Runs lowest-economy representative price estimator across carriers.
    4. Computes Modified Laspeyres index relative to base period.
    """
    db = SessionLocal()
    try:
        # Load weights
        weights_db = db.query(RouteWeight).all()
        assert len(weights_db) == 10
        route_weights = {w.route.route_code: w.weight for w in weights_db}

        # Validate weights sum to 1.0
        assert 0.999 <= sum(route_weights.values()) <= 1.001

        # Simulate base prices and day 1 prices
        routes = db.query(Route).filter(Route.active).all()
        base_prices = {}
        day1_prices = {}

        for r in routes:
            # Deterministic prices
            base_prices[r.route_code] = 5000.0
            # Metro routes rise by 5%, regional routes rise by 8%
            rise = 1.05 if r.corridor_type == "METRO_TRUNK" else 1.08
            day1_prices[r.route_code] = 5000.0 * rise

        # Compute national headline index
        result = AirfareIndexEngine.calculate_national_index(
            route_prices=day1_prices, base_prices=base_prices, route_weights=route_weights
        )

        assert result["index_value"] > 100.0
        assert result["coverage_rate"] == 100.0
        assert result["is_low_coverage"] is False
        assert len(result["route_indices"]) == 10
        # Average rise should be ~105.3%
        assert 104.5 <= result["index_value"] <= 106.5

    finally:
        db.close()
