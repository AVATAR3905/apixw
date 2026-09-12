"""Production Synthetic Data Purge & Index Recalculation Engine.

Permanently removes all synthetic/simulated observations from the database,
deactivates the synthetic verification source, and recomputes national headline
and sub-index series exclusively from authentic real-world observations.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.session import SessionLocal
from packages.schemas.models import FareObservation, IndexValue, Source
from services.index_engine.calculator_service import DailyIndexCalculatorService


def purge_and_recalculate():
    db = SessionLocal()
    try:
        print("\n" + "=" * 80)
        print(" PURGING SYNTHETIC DATA & RECALCULATING REAL-WORLD PRODUCTION INDICES")
        print("=" * 80)

        # 1. Count existing data
        total_obs = db.query(FareObservation).count()
        synth_count = (
            db.query(FareObservation).filter(FareObservation.is_synthetic.is_(True)).count()
        )
        real_count = (
            db.query(FareObservation).filter(FareObservation.is_synthetic.is_(False)).count()
        )

        print(f"[*] Total observations before purge: {total_obs}")
        print(f"[*] Synthetic observations to delete: {synth_count}")
        print(f"[*] Authentic real-world observations: {real_count}")

        # 2. Delete synthetic observations
        if synth_count > 0:
            db.query(FareObservation).filter(FareObservation.is_synthetic.is_(True)).delete()
            db.commit()
            print(
                f"[+] Successfully purged {synth_count} synthetic records from fare_observations."
            )

        # 3. Deactivate Synthetic Source
        synth_source = (
            db.query(Source).filter(Source.name == "Synthetic Pipeline Verification Feed").first()
        )
        if synth_source:
            synth_source.enabled = False
            synth_source.permission_status = "DEPRECATED_DEVELOPMENT"
            db.commit()
            print("[+] Deactivated 'Synthetic Pipeline Verification Feed' in source registry.")

        # 4. Verify clean state
        remaining_synth = (
            db.query(FareObservation).filter(FareObservation.is_synthetic.is_(True)).count()
        )
        remaining_real = (
            db.query(FareObservation).filter(FareObservation.is_synthetic.is_(False)).count()
        )
        print(f"[*] Post-purge verification: Synthetic={remaining_synth}, Real={remaining_real}")
        assert remaining_synth == 0, "Error: Synthetic data was not completely purged!"

        # 5. Recalculate Index on Real-World Data
        today = datetime.date.today()
        print(f"\n[*] Recalculating daily indices on real-world data for date: {today}...")

        # Purge prior synthetic index values to avoid mixing
        db.query(IndexValue).delete()
        db.commit()
        print("[+] Reset index_values table for fresh real-world computation.")

        indices = DailyIndexCalculatorService.calculate_day_indices(
            db=db,
            observation_date=today,
            base_date=today,
        )
        print(
            f"[+] Successfully calculated {len(indices)} production index records from real observations."
        )

        print("=" * 80)
        print(" PRODUCTION PURGE & RECALCULATION COMPLETE - 100% REAL DATA PLATFORM")
        print("=" * 80 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    purge_and_recalculate()
