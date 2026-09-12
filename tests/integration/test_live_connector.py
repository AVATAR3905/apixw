"""Integration test for LiveFlightConnector."""

import datetime

from services.collectors.live_connector import LiveFlightConnector


def test_live_flight_connector_query():
    """Queries simulated permitted live flight search across 5 horizons."""
    connector = LiveFlightConnector(source_id=1, source_name="Test Gateway")
    assert connector.health_check() is True

    today = datetime.date(2026, 9, 1)

    for h in [1, 7, 15, 30, 45]:
        result = connector.fetch_route_horizon("DEL-BOM", search_date=today, advance_days=h)
        assert result["status"] == "OK"
        fares = result["fares"]
        assert len(fares) >= 4  # 6E, AI, SG, QP

        # Check fare decomposition
        for f in fares:
            assert f["carrier"] in ("6E", "AI", "SG", "QP")
            assert f["base_fare"] > 0
            assert f["total_fare"] > f["base_fare"]
            # Verify component decomposition equality
            component_sum = (
                f["base_fare"]
                + f["fuel_surcharge"]
                + f["tax_amount"]
                + f["development_fee"]
                + f["convenience_fee"]
                + f["other_fee"]
            )
            assert abs(f["total_fare"] - component_sum) < 0.1
