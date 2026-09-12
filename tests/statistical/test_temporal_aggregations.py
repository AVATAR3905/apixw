"""Statistical tests for weekly and monthly temporal aggregations."""

import datetime

from packages.statistics.temporal_aggregations import TemporalAggregationEngine


def test_weekly_geometric_mean_aggregation():
    """
    Verifies that weekly aggregation computes the geometric mean of daily index values
    across calendar weeks.
    """
    daily_records = [
        {
            "date": datetime.date(2026, 8, 3),
            "index_value": 100.0,
            "index_series": "BASE_FARE",
            "index_type": "HEADLINE_T15",
            "coverage_rate": 100.0,
        },
        {
            "date": datetime.date(2026, 8, 4),
            "index_value": 102.0,
            "index_series": "BASE_FARE",
            "index_type": "HEADLINE_T15",
            "coverage_rate": 100.0,
        },
        {
            "date": datetime.date(2026, 8, 5),
            "index_value": 104.0,
            "index_series": "BASE_FARE",
            "index_type": "HEADLINE_T15",
            "coverage_rate": 100.0,
        },
        {
            "date": datetime.date(2026, 8, 6),
            "index_value": 106.0,
            "index_series": "BASE_FARE",
            "index_type": "HEADLINE_T15",
            "coverage_rate": 100.0,
        },
        {
            "date": datetime.date(2026, 8, 7),
            "index_value": 108.0,
            "index_series": "BASE_FARE",
            "index_type": "HEADLINE_T15",
            "coverage_rate": 100.0,
        },
    ]

    weekly = TemporalAggregationEngine.aggregate_weekly(daily_records)
    assert len(weekly) == 1
    w = weekly[0]
    assert w["period_type"] == "WEEKLY"
    assert "2026-W32" in w["period_label"]
    assert w["observation_days_count"] == 5
    # Geometric mean of [100, 102, 104, 106, 108] is ~103.95
    assert 103.8 <= w["index_value"] <= 104.1


def test_monthly_calendar_average_aggregation():
    """
    Verifies that monthly aggregation calculates the calendar average matching
    NSO / MoSPI monthly CPI alignment requirements.
    """
    daily_records = [
        {
            "date": datetime.date(2026, 8, 1),
            "index_value": 100.0,
            "index_series": "BASE_FARE",
            "index_type": "HEADLINE_T15",
            "coverage_rate": 100.0,
        },
        {
            "date": datetime.date(2026, 8, 15),
            "index_value": 105.0,
            "index_series": "BASE_FARE",
            "index_type": "HEADLINE_T15",
            "coverage_rate": 100.0,
        },
        {
            "date": datetime.date(2026, 8, 31),
            "index_value": 110.0,
            "index_series": "BASE_FARE",
            "index_type": "HEADLINE_T15",
            "coverage_rate": 100.0,
        },
    ]

    monthly = TemporalAggregationEngine.aggregate_monthly(daily_records)
    assert len(monthly) == 1
    m = monthly[0]
    assert m["period_type"] == "MONTHLY"
    assert m["period_label"] == "2026-08"
    # Arithmetic mean of [100, 105, 110] is exactly 105.0
    assert m["index_value"] == 105.0
    assert m["observation_days_count"] == 3
