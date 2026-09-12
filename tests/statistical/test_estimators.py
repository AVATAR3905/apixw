"""Statistical tests verifying fare-mix protection in RepresentativePriceEstimator."""

from packages.statistics.estimators import RepresentativePriceEstimator, available_fares


def test_available_fares_excludes_sold_out_and_zero():
    obs = [
        {"availability_status": "AVAILABLE", "base_fare": 4000.0},
        {"availability_status": "AVAILABLE", "base_fare": 0.0},
        {"availability_status": "SOLD_OUT", "base_fare": 3500.0},
        {"availability_status": "CANCELLED", "base_fare": 2500.0},
        {"availability_status": "AVAILABLE", "total_fare": 5000.0},
    ]
    assert available_fares(obs[:3]) == [4000.0]
    assert available_fares(obs, "total_fare") == [5000.0]
    assert available_fares([]) == []


class _Orm:
    def __init__(self, status, fare):
        self.availability_status = status
        self.base_fare = fare


def test_available_fares_handles_orm_objects():
    rows = [
        _Orm("AVAILABLE", 4100.0),
        _Orm("AVAILABLE", 0.0),
        _Orm("SOLD_OUT", 1900.0),
        _Orm("AVAILABLE", None),
        _Orm("AVAILABLE", 5120.5),
    ]
    assert available_fares(rows) == [4100.0, 5120.5]


def test_fare_mix_protection_against_flexi_fares():
    """
    Proves that adding expensive Economy Flexi tickets to the observation pool
    does NOT distort the representative price when measuring standard Economy Basic pricing.
    """
    # Day 1: Only Economy Basic available across 3 carriers
    day1_obs = [
        {"carrier": "6E", "cabin_class": "ECONOMY", "fare_family": "BASIC", "base_fare": 4000.0},
        {"carrier": "AI", "cabin_class": "ECONOMY", "fare_family": "BASIC", "base_fare": 4200.0},
        {"carrier": "SG", "cabin_class": "ECONOMY", "fare_family": "BASIC", "base_fare": 3900.0},
    ]

    res1 = RepresentativePriceEstimator.estimate_route_price(day1_obs, price_field="base_fare")
    assert res1 is not None
    # Median of [3900, 4000, 4200] is 4000.0
    assert res1["representative_price"] == 4000.0

    # Day 2: Same Economy Basic fares, but airline algorithms make 10 expensive Flexi tickets visible
    day2_obs = [
        {"carrier": "6E", "cabin_class": "ECONOMY", "fare_family": "BASIC", "base_fare": 4000.0},
        {"carrier": "AI", "cabin_class": "ECONOMY", "fare_family": "BASIC", "base_fare": 4200.0},
        {"carrier": "SG", "cabin_class": "ECONOMY", "fare_family": "BASIC", "base_fare": 3900.0},
        # Flexi tickets (same flights, same carriers, but higher tier)
        {"carrier": "6E", "cabin_class": "ECONOMY", "fare_family": "FLEXI", "base_fare": 7500.0},
        {"carrier": "AI", "cabin_class": "ECONOMY", "fare_family": "FLEXI", "base_fare": 8200.0},
        {"carrier": "SG", "cabin_class": "ECONOMY", "fare_family": "FLEXI", "base_fare": 7100.0},
        {"carrier": "6E", "cabin_class": "ECONOMY", "fare_family": "FLEXI", "base_fare": 9000.0},
    ]

    res2 = RepresentativePriceEstimator.estimate_route_price(day2_obs, price_field="base_fare")
    assert res2 is not None
    # Fare-mix protected price must still equal 4000.0 exactly!
    assert res2["representative_price"] == 4000.0


def test_carrier_minimum_fare_selection():
    """
    Verifies that for a carrier with multiple flights, the lowest available
    basic fare is chosen to represent that carrier's accessible price point.
    """
    obs = [
        # IndiGo has 3 flights at 3 different departure times
        {"carrier": "6E", "cabin_class": "ECONOMY", "fare_family": "BASIC", "base_fare": 4800.0},
        {
            "carrier": "6E",
            "cabin_class": "ECONOMY",
            "fare_family": "BASIC",
            "base_fare": 3800.0,
        },  # cheapest
        {"carrier": "6E", "cabin_class": "ECONOMY", "fare_family": "BASIC", "base_fare": 5200.0},
        # Air India has 2 flights
        {"carrier": "AI", "cabin_class": "ECONOMY", "fare_family": "BASIC", "base_fare": 4500.0},
        {
            "carrier": "AI",
            "cabin_class": "ECONOMY",
            "fare_family": "BASIC",
            "base_fare": 4100.0,
        },  # cheapest
        # SpiceJet has 1 flight
        {"carrier": "SG", "cabin_class": "ECONOMY", "fare_family": "BASIC", "base_fare": 3900.0},
    ]

    res = RepresentativePriceEstimator.estimate_route_price(obs, price_field="base_fare")
    assert res is not None
    assert res["carrier_fares"]["6E"] == 3800.0
    assert res["carrier_fares"]["AI"] == 4100.0
    assert res["carrier_fares"]["SG"] == 3900.0
    # Median of [3800, 3900, 4100] is 3900.0
    assert res["representative_price"] == 3900.0


def test_sold_out_flights_do_not_distort_median():
    """
    Verifies that sold-out flights are not treated as ₹0, and do not pull down the price.
    """
    obs = [
        {
            "carrier": "6E",
            "cabin_class": "ECONOMY",
            "fare_family": "BASIC",
            "base_fare": 5000.0,
            "availability_status": "AVAILABLE",
        },
        {
            "carrier": "AI",
            "cabin_class": "ECONOMY",
            "fare_family": "BASIC",
            "base_fare": 5500.0,
            "availability_status": "AVAILABLE",
        },
        # SpiceJet is completely sold out on this date
        {
            "carrier": "SG",
            "cabin_class": "ECONOMY",
            "fare_family": "BASIC",
            "base_fare": None,
            "availability_status": "SOLD_OUT",
        },
    ]

    res = RepresentativePriceEstimator.estimate_route_price(obs, price_field="base_fare")
    assert res is not None
    assert "SG" not in res["carrier_fares"]
    # Median of [5000, 5500] is 5250.0
    assert res["representative_price"] == 5250.0
