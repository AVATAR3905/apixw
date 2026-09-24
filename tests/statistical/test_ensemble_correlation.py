"""Tests for Phase 5: ENSEMBLE estimator and feed-cohort correlation tracking."""

import datetime

from database.session import SessionLocal
from packages.schemas.models import FareObservation, Route, Source, SourceCorrelation
from packages.statistics.estimators import RepresentativePriceEstimator
from packages.statistics.source_correlation import SourceCorrelationTracker, _pearson_r


def test_ensemble_estimator_downweights_ota():
    """The ENSEMBLE estimator must resist a low-quality OTA pull toward a cheap
    fare while still hearing the OTA (weighted median differs from plain median)."""
    obs = [
        {"carrier": "6E", "cabin_class": "ECONOMY", "fare_family": "BASIC",
         "availability_status": "AVAILABLE", "base_fare": 3900.0, "feed_type": "CARRIER_DIRECT"},
        {"carrier": "AI", "cabin_class": "ECONOMY", "fare_family": "BASIC",
         "availability_status": "AVAILABLE", "base_fare": 4200.0, "feed_type": "CARRIER_DIRECT"},
        {"carrier": "QP", "cabin_class": "ECONOMY", "fare_family": "BASIC",
         "availability_status": "AVAILABLE", "base_fare": 4300.0, "feed_type": "CARRIER_DIRECT"},
        {"carrier": "SG", "cabin_class": "ECONOMY", "fare_family": "BASIC",
         "availability_status": "AVAILABLE", "base_fare": 3950.0, "feed_type": "OTA_AGGREGATOR"},
    ]

    ens = RepresentativePriceEstimator.estimate_route_price(obs, price_field="base_fare", estimator="ENSEMBLE")
    med = RepresentativePriceEstimator.estimate_route_price(obs, price_field="base_fare", estimator="MEDIAN")

    assert ens is not None and med is not None
    # Weighted median (CARRIER_DIRECT=1.0, OTA=0.7) crosses at the AI price 4200.0
    assert ens["representative_price"] == 4200.0
    # Plain median of [3900, 3950, 4200, 4300] is 4075.0
    assert med["representative_price"] == 4075.0
    assert ens["representative_price"] > med["representative_price"]


def test_pearson_r_basic():
    assert _pearson_r([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0
    assert _pearson_r([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == -1.0
    assert _pearson_r([1.0, 2.0], [5.0]) is None  # mismatched length
    assert _pearson_r([1.0], [1.0]) is None  # too few points
    assert _pearson_r([1.0, 1.0], [2.0, 3.0]) is None  # constant series


def test_ensemble_estimator_is_default_compatible():
    """ENSEMBLE must also work on the classic fare-mix-protection input shape."""
    obs = [
        {"carrier": "6E", "cabin_class": "ECONOMY", "fare_family": "BASIC",
         "availability_status": "AVAILABLE", "base_fare": 4000.0, "feed_type": "CARRIER_DIRECT"},
        {"carrier": "AI", "cabin_class": "ECONOMY", "fare_family": "BASIC",
         "availability_status": "AVAILABLE", "base_fare": 4200.0, "feed_type": "CARRIER_DIRECT"},
        {"carrier": "SG", "cabin_class": "ECONOMY", "fare_family": "BASIC",
         "availability_status": "AVAILABLE", "base_fare": 3900.0, "feed_type": "OTA_AGGREGATOR"},
    ]
    res = RepresentativePriceEstimator.estimate_route_price(obs, price_field="base_fare", estimator="ENSEMBLE")
    assert res is not None and res["representative_price"] > 0
    assert res["dominant_feed_type"] == "CARRIER_DIRECT"


def test_source_correlation_tracker_roundtrip():
    """Insert dual-feed observations for one route across a window and verify the
    tracker persists correlation rows and does not explode on re-runs.

    Uses a dedicated, disposable test route (never a real seeded corridor) and
    cleans up only by that route's id -- this used to reuse ``Route.first()``
    (a real production corridor, e.g. DEL-BOM) and, worse, cleaned up by
    ``source_id IN (carrier_direct_id, ota_id)``, which deletes *every*
    FareObservation using those shared source ids network-wide, not just this
    test's own rows. Confirmed to have been silently deleting real
    SpiceJet/Akasa carrier-direct data (source_id=5, "Carrier Direct Booking
    Scraper") on every full test-suite run. Also explains why the old
    assertion (pearson_r > 0.99 on a "perfectly linear" series) started
    failing once real production data accumulated on DEL-BOM: the tracker
    aggregated the test's synthetic points together with real, noisy
    CARRIER_DIRECT/OTA_AGGREGATOR observations for the same route/horizon/
    window, diluting the correlation. A disposable route can't collide with
    real data at all.
    """
    db = SessionLocal()
    src_direct = db.query(Source).filter(Source.name == "Carrier Direct Booking Scraper").first()
    src_ota = db.query(Source).filter(Source.name == "MakeMyTrip India").first()
    airline = db.query(__import__("packages.schemas.models", fromlist=["Airline"]).Airline).first()

    assert src_direct is not None and src_ota is not None

    route = Route(
        route_code="ZZ-TEST", origin="Testland", destination="Testville",
        origin_airport="ZZT", destination_airport="ZZV",
        corridor_type="METRO_TRUNK", active=False,
    )
    db.add(route)
    db.commit()
    db.refresh(route)

    try:
        # Build perfectly correlated daily series (direct = 2x OTA here is fine;
        # correlation only cares about linearity, so scale both by day).
        base = datetime.date.today() - datetime.timedelta(days=10)
        for i in range(7):
            for src, mult, feed in ((src_direct, 2.0, "CARRIER_DIRECT"), (src_ota, 1.0, "OTA_AGGREGATOR")):
                day = base + datetime.timedelta(days=i)
                price = 3000.0 + i * 100.0
                db.add(FareObservation(
                    source_id=src.id, route_id=route.id, airline_id=airline.id or 1,
                    search_timestamp=datetime.datetime.combine(day, datetime.datetime.min.time()),
                    travel_date=day + datetime.timedelta(days=15),
                    advance_purchase_days=15,
                    flight_number="6E-205", cabin_class="ECONOMY", fare_family="BASIC",
                    availability_status="AVAILABLE", base_fare=price * mult,
                    total_fare=price * mult, feed_type=feed, extraction_method="NETWORK",
                    quality_score=100.0, quality_status="ACCEPT", is_synthetic=False,
                ))
        db.commit()

        res = SourceCorrelationTracker.compute_and_persist(
            db=db, route_code=route.route_code, horizon=15, window_days=28, persist=True
        )
        assert res["routes_with_both_feeds"] >= 1
        r = [x for x in res["results"] if x["route_code"] == route.route_code][0]
        assert r["pearson_r"] > 0.99  # perfectly linear series

        # Re-run must deduplicate (only one snapshot row per window/route/horizon)
        SourceCorrelationTracker.compute_and_persist(
            db=db, route_code=route.route_code, horizon=15, window_days=28, persist=True
        )
        count = (
            db.query(SourceCorrelation)
            .filter(
                SourceCorrelation.route_id == route.id,
                SourceCorrelation.horizon_days == 15,
                SourceCorrelation.period_end == datetime.date.today(),
            )
            .count()
        )
        assert count == 1
    finally:
        # Cleanup by this test's own disposable route id only -- never touch
        # rows belonging to other routes/sources.
        db.query(SourceCorrelation).filter(SourceCorrelation.route_id == route.id).delete()
        db.query(FareObservation).filter(FareObservation.route_id == route.id).delete()
        db.query(Route).filter(Route.id == route.id).delete()
        db.commit()
        db.close()
