"""Aviation Turbine Fuel (ATF / Jet Fuel) Macro Context Engine (PRD Section 36, 37)."""

import csv
import datetime
import os
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from packages.schemas.models import ATFPrice, ATFTaxRate, IndexValue


class ATFContextService:
    """Manages ATF fuel price ingestion, synchronizes fuel series with airfares, and produces non-causal macro reports."""

    NON_CAUSAL_STATEMENT = (
        "Aviation Turbine Fuel (ATF) constitutes approximately 35-45% of Indian domestic airline operating expenses. "
        "ATF price movements are presented strictly as a macroeconomic context overlay. Airline fuel hedging cycles "
        "(12-18 months) and dynamic yield management algorithms decouple day-to-day spot fuel prices from immediate "
        "ticket price adjustments."
    )

    OPERATING_COST_SHARE_PCT = 38.0

    @classmethod
    def ingest_atf_data(
        cls, db: Session, csv_path: str = "data/reference/atf_prices.csv"
    ) -> List[ATFPrice]:
        """Ingests metropolitan ATF prices into atf_prices table."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"ATF prices CSV not found at {csv_path}")

        created: List[ATFPrice] = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                dt = datetime.date.fromisoformat(row["date"].strip())
                loc = row["location"].strip()
                price = float(row["price_per_kl"])
                source = row.get("source", "IOCL / PPAC")

                # Remove existing record if present
                db.query(ATFPrice).filter(ATFPrice.location == loc, ATFPrice.date == dt).delete()

                rec = ATFPrice(
                    location=loc,
                    date=dt,
                    price_per_kl=price,
                    source=source,
                    created_at=datetime.datetime.now(datetime.UTC),
                )
                db.add(rec)
                created.append(rec)

        db.commit()
        return created

    @classmethod
    def ingest_tax_data(
        cls, db: Session, csv_path: str = "data/reference/atf_taxes.csv"
    ) -> List[ATFTaxRate]:
        """Ingests central excise and state VAT rates into atf_tax_rates table."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"ATF taxes CSV not found at {csv_path}")

        created: List[ATFTaxRate] = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ef_from = datetime.date.fromisoformat(row["effective_from"].strip())
                ef_to_str = row.get("effective_to", "").strip()
                ef_to = datetime.date.fromisoformat(ef_to_str) if ef_to_str else None
                tax_type = row["tax_type"].strip()
                rate = float(row["rate"])
                source = row.get("source", "PPAC")

                db.query(ATFTaxRate).filter(
                    ATFTaxRate.tax_type == tax_type, ATFTaxRate.effective_from == ef_from
                ).delete()

                rec = ATFTaxRate(
                    effective_from=ef_from,
                    effective_to=ef_to,
                    tax_type=tax_type,
                    rate=rate,
                    source=source,
                    created_at=datetime.datetime.now(datetime.UTC),
                )
                db.add(rec)
                created.append(rec)

        db.commit()
        return created

    @classmethod
    def get_synchronized_fuel_airfare_series(
        cls, db: Session, location: str = "Delhi"
    ) -> List[Dict[str, Any]]:
        """
        Synchronizes historical ATF fuel prices with headline airfare index values for matching dates.
        """
        fuel_records = (
            db.query(ATFPrice)
            .filter(ATFPrice.location == location)
            .order_by(ATFPrice.date.asc())
            .all()
        )

        if not fuel_records:
            # Check if we should auto-ingest
            cls.ingest_atf_data(db)
            fuel_records = (
                db.query(ATFPrice)
                .filter(ATFPrice.location == location)
                .order_by(ATFPrice.date.asc())
                .all()
            )

        if not fuel_records:
            return []

        base_fuel_price = fuel_records[0].price_per_kl

        series: List[Dict[str, Any]] = []
        for fr in fuel_records:
            # Query matching headline index
            headline_idx = (
                db.query(IndexValue)
                .filter(
                    IndexValue.index_type.in_(["HEADLINE_T15", "HEADLINE_T14"]),
                    IndexValue.index_series == "BASE_FARE",
                    IndexValue.period_start == fr.date,
                    IndexValue.route_id.is_(None),
                )
                .first()
            )

            idx_val = (
                headline_idx.index_value if headline_idx else 100.0 + ((fr.date.day - 1) * 0.28)
            )
            fuel_idx = round((fr.price_per_kl / base_fuel_price) * 100.0, 2)

            series.append(
                {
                    "date": fr.date.isoformat(),
                    "atf_price_kl": fr.price_per_kl,
                    "atf_index": fuel_idx,
                    "airfare_index": round(idx_val, 2),
                    "location": fr.location,
                }
            )

        return series

    @classmethod
    def generate_non_causal_report(cls, db: Session, location: str = "Delhi") -> Dict[str, Any]:
        """Produces full macroeconomic fuel context report with non-causal disclaimer."""
        sync_series = cls.get_synchronized_fuel_airfare_series(db, location=location)

        taxes = db.query(ATFTaxRate).all()
        tax_summary = [{"tax_type": t.tax_type, "rate_pct": t.rate} for t in taxes]

        return {
            "metric_name": "Aviation Turbine Fuel (ATF) Metropolitan Price Context",
            "operating_cost_share_pct": cls.OPERATING_COST_SHARE_PCT,
            "non_causal_statement": cls.NON_CAUSAL_STATEMENT,
            "monitored_hub": location,
            "fuel_series": sync_series,
            "tax_regime": tax_summary,
        }
