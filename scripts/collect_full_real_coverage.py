"""One-shot full-basket real-data collection: 10 routes x 5 advance-purchase
horizons (T+1/7/15/30/45), using every verified-working live source (SpiceJet
and Akasa carrier-direct, the Google Flights RPC validator, and the Ixigo /
EaseMyTrip OTA scrapers). Delegates to CollectionScheduler.trigger_collection_cycle
so a manual run and the automated 4x-daily cron share identical logic.
"""

import datetime
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from database.session import SessionLocal  # noqa: E402
from services.scheduler.collection_scheduler import CollectionScheduler  # noqa: E402


def main():
    search_date = datetime.date.today()
    print(f"\n[*] Starting full-basket real-data collection for {search_date} "
          f"(10 routes x 5 horizons = 50 corridor-jobs, each hitting SpiceJet, "
          f"Akasa, Google Flights RPC, Ixigo, EaseMyTrip)...\n")

    db = SessionLocal()
    try:
        scheduler = CollectionScheduler()
        summary = scheduler.trigger_collection_cycle(db, search_date=search_date)
        print("\n" + "=" * 80)
        print(" FULL-BASKET COLLECTION COMPLETE")
        print("=" * 80)
        for k, v in summary.items():
            print(f"  {k}: {v}")
        print("=" * 80 + "\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
