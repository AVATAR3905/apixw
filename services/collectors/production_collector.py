"""Production Bulk Airfare Collector.

Executes dual-feed collection across all 10 monitored corridors and 5 horizons:
- Feed 1: Carrier Direct Booking Scraper (IndiGo, SpiceJet, Akasa Air, Air India)
- Feed 2: Google Flights RPC Validator & Resilient Fallback
- Normalizes and stores authentic observations (is_synthetic=False).
"""

import datetime
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.collectors.dual_feed_runner import run_dual_feed_collection

CORRIDORS = [
    "DEL-BOM",
    "DEL-BLR",
    "BOM-BLR",
    "DEL-CCU",
    "DEL-HYD",
    "BOM-MAA",
    "BLR-HYD",
    "DEL-MAA",
    "DEL-IXS",
    "DEL-DHM",
]

HORIZONS = [1, 7, 15, 30, 45]


def run_production_collection(
    corridors: List[str] = None,
    horizons: List[int] = None,
    delay_seconds: float = 1.0,
) -> Dict[str, Any]:
    """
    Executes real-world airfare collection across specified corridors and horizons.
    """
    if corridors is None:
        corridors = CORRIDORS
    if horizons is None:
        horizons = HORIZONS

    start_time = datetime.datetime.now(datetime.timezone.utc)
    print("\n" + "=" * 90)
    print(" MINISTRY OF STATISTICS & PROGRAMME IMPLEMENTATION (MoSPI / NSO)")
    print(" INDIA AIRFARE PRICE OBSERVATORY - PRODUCTION DATA INGESTION ENGINE")
    print("=" * 90)
    print(f"Target Corridors: {len(corridors)} | Target Horizons: {horizons}")
    print(f"Total Flight Search Matrices: {len(corridors) * len(horizons)}")
    print("=" * 90 + "\n")

    total_quotes_collected = 0
    total_evaluated = 0
    successful_runs = 0
    failed_runs = 0

    for c_idx, corridor in enumerate(corridors, 1):
        print(f"\n>>> [{c_idx}/{len(corridors)}] Processing Corridor: {corridor}")
        for h in horizons:
            try:
                res = run_dual_feed_collection(
                    route_code=corridor,
                    advance_days=h,
                    search_date=datetime.date.today(),
                )
                total_quotes_collected += len(res.get("primary_observations", []))
                total_evaluated += res.get("total_flights_evaluated", 0)
                successful_runs += 1
            except Exception as e:
                print(f"    [!] Error collecting {corridor} at T+{h}: {e}")
                failed_runs += 1

            if delay_seconds > 0:
                time.sleep(delay_seconds)

    duration = (datetime.datetime.now(datetime.UTC) - start_time).total_seconds()

    # Recalculate official Laspeyres indices, carrier inflation, and volatility
    from database.session import SessionLocal
    from packages.schemas.models import Route
    from packages.statistics.carrier_inflation import CarrierInflationService
    from packages.statistics.volatility import VolatilityService
    from services.index_engine.calculator_service import DailyIndexCalculatorService

    db_calc = SessionLocal()
    today = datetime.date.today()
    indices_count = 0
    try:
        calc_res = DailyIndexCalculatorService.calculate_day_indices(
            db=db_calc, observation_date=today
        )
        indices_count = len(calc_res) if calc_res else 0
        CarrierInflationService.calculate_carrier_indices(
            db=db_calc, observation_date=today, horizon_days=15
        )
        for r in db_calc.query(Route).filter(Route.active).all():
            VolatilityService.calculate_corridor_volatility(
                db=db_calc, route_id=r.id, calculation_date=today, horizon_days=15, save_to_db=True
            )
    except Exception as e:
        print(f"[!] Post-collection index calculation error: {e}")
    finally:
        db_calc.close()

    summary = {
        "status": "COMPLETED",
        "corridors_processed": len(corridors),
        "horizons_processed": len(horizons),
        "successful_search_matrices": successful_runs,
        "failed_search_matrices": failed_runs,
        "total_authentic_quotes_persisted": total_quotes_collected,
        "total_flights_evaluated": total_evaluated,
        "indices_recalculated": indices_count,
        "duration_seconds": round(duration, 2),
    }

    print("\n" + "=" * 90)
    print(" PRODUCTION COLLECTION RUN COMPLETE")
    print(f" Total Authentic Quotes Persisted: {total_quotes_collected}")
    print(f" Total Flights Evaluated:          {total_evaluated}")
    print(f" Search Matrices Completed:        {successful_runs}/{successful_runs + failed_runs}")
    print(f" Execution Duration:               {duration:.2f} seconds")
    print("=" * 90 + "\n")

    return summary


if __name__ == "__main__":
    run_production_collection()
