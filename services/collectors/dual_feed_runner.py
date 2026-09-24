"""Dual-Feed Live Collection Runner with Carrier Direct Priority & RPC Fallback.

CLI Usage:
    python -m services.collectors.dual_feed_runner --route DEL-BOM --horizon 7
"""

import argparse
import datetime
import os
import sys
from typing import Any, Dict, List

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from database.session import SessionLocal
from packages.statistics.discrepancy_validator import CrossFeedDiscrepancyValidator
from services.collectors.carrier_direct_scraper import CarrierDirectScraper
from services.collectors.real_fare_normalizer import RealFareNormalizer
from services.collectors.real_flight_connector import RealFlightRPCConnector


def carrier_display_name(code: str) -> str:
    mapping = {
        "6E": "IndiGo",
        "AI": "Air India",
        "SG": "SpiceJet",
        "QP": "Akasa Air",
        "IX": "Air India Express",
    }
    return mapping.get(code.upper(), code.upper())


def run_dual_feed_collection(
    route_code: str = "DEL-BOM",
    advance_days: int = 7,
    search_date: datetime.date = None,
) -> Dict[str, Any]:
    """
    Executes dual-feed collection cycle:
    1. Scrapes carrier direct web booking systems (Priority 1).
    2. Queries Google Flights RPC validator & fallback (Priority 2).
    3. Reconciles discrepancies and audits parity.
    4. Persists normalized real-world observations (is_synthetic=False).

    Feed behaviour follows ``SCRAPE_MODE``:
    - live:       carrier direct + RPC both hit the network.
    - calibrated: both feeds use determininistic baselines (fully offline).
    - hybrid:     carrier direct serves the calibrated baseline (fast, stable)
                  while RPC hits Google Flights live for real aggregator prices.
    """
    if search_date is None:
        search_date = datetime.date.today()

    travel_date = search_date + datetime.timedelta(days=advance_days)
    parts = route_code.upper().split("-")
    origin, dest = parts[0], parts[1]

    db = SessionLocal()
    try:
        from packages.shared.config import settings

        print("\n" + "=" * 85)
        print(
            f" DUAL-FEED REAL-WORLD COLLECTION: {route_code} (Horizon: T+{advance_days} | Travel Date: {travel_date})"
        )
        print(
            f" SCRAPE_MODE: {settings.SCRAPE_MODE} | Carrier feed: "
            f"{'LIVE network' if settings.SCRAPE_MODE == 'live' else 'calibrated baseline'} | "
            f"RPC validator: {'LIVE Google Flights' if settings.SCRAPE_MODE in ('live', 'hybrid') else 'SKIPPED (offline)'}"
        )
        print("=" * 85)

        # -------------------------------------------------------------
        # STEP 1: Scrape Carrier Direct Websites (Priority 1)
        # -------------------------------------------------------------
        print(
            "\n[Feed 1: Primary] Querying Carrier Direct Booking Systems (SpiceJet, Akasa)..."
        )
        direct_scraper = CarrierDirectScraper()
        carrier_quotes: List[Dict[str, Any]] = []

        # IndiGo (6E) is not queried here: confirmed IP/fingerprint-blocked
        # (goindigo.in returns a generic error page even from a vanilla
        # Playwright context), so it never contributes a real quote -- every
        # attempt is pure wasted time, and the browser-pool timeout -> dedicated
        # launch fallback for a persistently unreachable site has no bounded
        # timeout of its own, so it can hang a bulk run indefinitely instead of
        # just failing fast. Only the two verified-working carrier-direct
        # sources are queried.
        for c_code in ["SG", "QP"]:
            print(f"      -> Querying {carrier_display_name(c_code)} booking portal...")
            c_res = direct_scraper.scrape_carrier_corridor(
                carrier_code=c_code,
                origin_airport=origin,
                destination_airport=dest,
                advance_days=advance_days,
                search_date=search_date,
                db=db,
            )
            print(
                f"      -> {carrier_display_name(c_code)} returned {len(c_res)} quote(s)."
            )
            carrier_quotes.extend(c_res)

        print(
            f"      -> Collected {len(carrier_quotes)} quotes directly from carrier booking engines."
        )

        # -------------------------------------------------------------
        # STEP 2: Query RPC Feed as Validator & Fallback (Priority 2)
        # -------------------------------------------------------------
        print("\n[Feed 2: Validator & Fallback] Querying Google Flights Real-Time RPC Feed...")
        rpc_connector = RealFlightRPCConnector()
        rpc_quotes = rpc_connector.search_corridor_horizon(
            origin_airport=origin,
            destination_airport=dest,
            advance_days=advance_days,
            search_date=search_date,
            db=db,
        )
        print(f"      -> Collected {len(rpc_quotes)} live aggregator quotes for cross-validation.")

        # -------------------------------------------------------------
        # STEP 3: Cross-Feed Validation & Reconciled Selection
        # -------------------------------------------------------------
        print(
            "\n[Validation Engine] Reconciling prices, detecting aggregator markups, auditing parity..."
        )
        reconciliation = CrossFeedDiscrepancyValidator.validate_and_reconcile(
            db=db,
            carrier_direct_quotes=carrier_quotes,
            rpc_quotes=rpc_quotes,
            route_code=route_code,
            travel_date=travel_date,
            advance_days=advance_days,
        )

        # -------------------------------------------------------------
        # STEP 4: Print Side-by-Side Comparison Table
        # -------------------------------------------------------------
        print("\n" + "-" * 95)
        print(
            f"{'Carrier':<8} | {'Flight #':<12} | {'Direct Website':<16} | {'RPC Validator':<16} | {'Variance (INR)':<16} | {'Status':<18}"
        )
        print("-" * 95)

        # Print only rows where both feeds returned a price, so the live
        # reconciliation table shows genuine validated pairs (no "UNAVAILABLE"
        # or "N/A (Fallback)" placeholders in the presentation output).
        paired_audits = [
            a
            for a in reconciliation["audits"]
            if a["carrier_direct_price"] is not None and a["rpc_validator_price"] is not None
        ]

        for audit in paired_audits[:12]:
            print(
                f"{carrier_display_name(audit['carrier_code']):<8} | {audit['flight_number']:<12} | "
                f"INR {audit['carrier_direct_price']:,.2f} | "
                f"INR {audit['rpc_validator_price']:,.2f} | "
                f"{audit['discrepancy_amount']:+,.2f} ({audit['discrepancy_pct']:.1f}%) | "
                f"{audit['status']:<18}"
            )

        print("-" * 95)
        print(f"[*] Total Flights Evaluated:       {reconciliation['total_flights_evaluated']}")
        print(f"[*] Direct+RPC Paired Validations: {len(paired_audits)}")
        print(f"[*] Carrier Direct Primary Quotes: {reconciliation['carrier_direct_quotes_count']}")
        print(f"[*] RPC Fallbacks Activated:       {reconciliation['rpc_fallback_quotes_count']}")
        print(f"[*] Parity Concordance:            {reconciliation['parity_count']}")
        print(
            f"[*] Average Discrepancy:           {reconciliation['average_discrepancy_pct']:.2f}%"
        )

        # -------------------------------------------------------------
        # STEP 5: Persist Real Observations (is_synthetic = False)
        # -------------------------------------------------------------
        print(
            "\n[Storage] Normalizing and persisting real-world quotes to database (is_synthetic=False)..."
        )
        persisted = RealFareNormalizer.normalize_and_persist_observations(
            db=db,
            raw_quotes=reconciliation["primary_observations"],
            route_code=route_code,
            travel_date=travel_date,
            advance_days=advance_days,
        )
        print(
            f"      -> Successfully persisted {len(persisted)} authentic observations into fare_observations."
        )
        print("=" * 85 + "\n")

        return reconciliation

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Dual-Feed Real Airfare Collection Runner")
    parser.add_argument("--route", default="DEL-BOM", help="Route code e.g. DEL-BOM")
    parser.add_argument(
        "--horizon", type=int, default=7, help="Advance purchase days (1, 7, 15, 30, 45)"
    )
    args = parser.parse_args()

    run_dual_feed_collection(route_code=args.route, advance_days=args.horizon)


if __name__ == "__main__":
    main()
