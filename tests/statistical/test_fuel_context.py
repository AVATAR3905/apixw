"""Statistical and integrity tests for ATF fuel context vertical."""

from database.session import SessionLocal
from packages.statistics.fuel_context import ATFContextService


def test_atf_price_and_tax_ingestion():
    """Verifies that metropolitan ATF prices and VAT/excise taxes are ingested."""
    db = SessionLocal()
    try:
        prices = ATFContextService.ingest_atf_data(db)
        assert len(prices) == 20  # 5 dates x 4 locations
        assert all(p.price_per_kl > 70000.0 for p in prices)

        taxes = ATFContextService.ingest_tax_data(db)
        assert len(taxes) == 5
        delhi_vat = next(t for t in taxes if t.tax_type == "STATE_VAT_DELHI")
        assert delhi_vat.rate == 25.0

    finally:
        db.close()


def test_synchronized_fuel_airfare_series():
    """Verifies that fuel prices and airfare headline indices are aligned by calendar date."""
    db = SessionLocal()
    try:
        series = ATFContextService.get_synchronized_fuel_airfare_series(db, location="Delhi")
        assert len(series) >= 5

        # Check August 1 and August 28 reference records
        aug_01 = next(s for s in series if s["date"] == "2026-08-01")
        assert aug_01["atf_price_kl"] == 94200.0
        assert aug_01["atf_index"] >= 100.0
        assert aug_01["airfare_index"] >= 100.0

        aug_28 = next(s for s in series if s["date"] == "2026-08-28")
        assert aug_28["atf_price_kl"] == 97800.0
        assert aug_28["atf_index"] > 103.0

    finally:
        db.close()


def test_non_causal_statement_and_cost_share():
    """
    Verifies that the non-causal disclaimer and ~38% cost-share figure
    are strictly present in the generated report.
    """
    db = SessionLocal()
    try:
        report = ATFContextService.generate_non_causal_report(db, location="Delhi")

        assert report["operating_cost_share_pct"] == 38.0
        assert (
            "Aviation Turbine Fuel (ATF) constitutes approximately 35-45%"
            in report["non_causal_statement"]
        )
        assert "12-18 months" in report["non_causal_statement"]
        assert "decouple day-to-day spot fuel prices" in report["non_causal_statement"]
        assert len(report["tax_regime"]) >= 5

    finally:
        db.close()
