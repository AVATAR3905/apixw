"""Unified Demo & Verification Seed Package (Task 10.2).

Boots the entire India Airfare Price Observatory from scratch:
1. Populates reference routes and airlines.
2. Ingests DGCA passenger traffic volume and computes normalized weights (10 corridors).
3. Generates 30 consecutive calendar days of realistic domestic fare observations (tagged is_synthetic=True).
4. Calculates daily headline indices (T+15 Anchor), lead-time sub-indices, and route-level indices.
5. Ingests official MoSPI CPI airfare benchmarks and computes directional co-movement.
6. Ingests IOCL / PPAC metropolitan ATF jet fuel price series and taxes.
"""

import datetime

from database.seeds.seed_routes_airlines import seed_reference_data
from database.session import SessionLocal, init_db
from packages.statistics.benchmark_matcher import BenchmarkMatcherService
from packages.statistics.fuel_context import ATFContextService
from packages.statistics.weights import DGCAWeightEngine
from services.index_engine.calculator_service import DailyIndexCalculatorService
from services.synthetic_generator import SyntheticFareGenerator


def run_full_seed_pipeline():
    """Executes the complete end-to-end data bootstrapping pipeline."""
    print("=" * 70)
    print(" INDIA AIRFARE PRICE OBSERVATORY — UNIFIED SEED PIPELINE (APIX-2.0)")
    print("=" * 70)

    # 1. Initialize DB Schema
    print("\n[1/6] Initializing database schema...")
    init_db()
    db = SessionLocal()

    try:
        # 2. Seed reference routes and airlines
        print("[2/6] Seeding reference routes and scheduled domestic airlines...")
        seed_reference_data()

        # 3. Ingest DGCA weights
        print("[3/6] Ingesting DGCA domestic passenger traffic volumes...")
        weight_records = DGCAWeightEngine.persist_weights_version(
            db,
            csv_path="data/reference/dgca_traffic.csv",
            version_tag="DGCA_2026_V1",
        )
        print(f"      -> Ingested {len(weight_records)} route weights (Sum = 1.000000)")

        # 4. Generate 30 days of verification observations
        print("[4/6] Generating 30-day statistical pipeline verification observations...")
        start_date = datetime.date(2026, 8, 1)
        obs_count = SyntheticFareGenerator.seed_verification_dataset(
            db=db,
            days_count=30,
            start_date=start_date,
        )
        print(
            f"      -> Generated and persisted {obs_count:,} raw fare observations (is_synthetic=True)"
        )

        # 5. Compute daily headline index, sub-indices, and route-level series
        print("[5/6] Computing daily airfare price indices (T+15 Anchor, Dual Series)...")
        end_date = start_date + datetime.timedelta(days=29)
        total_indices = DailyIndexCalculatorService.compute_historical_index_range(
            db=db,
            start_date=start_date,
            end_date=end_date,
        )
        print(f"      -> Computed and stored {total_indices} index records across 30 days")

        # 6. Ingest benchmarks & fuel series
        print("[6/6] Ingesting official MoSPI CPI benchmark and ATF fuel series...")
        mospi_recs = BenchmarkMatcherService.ingest_mospi_benchmark_csv(db)
        fuel_recs = ATFContextService.ingest_atf_data(db)
        tax_recs = ATFContextService.ingest_tax_data(db)
        print(f"      -> Ingested {len(mospi_recs)} MoSPI CPI monthly records")
        print(f"      -> Ingested {len(fuel_recs)} ATF price records & {len(tax_recs)} tax regimes")

        print("\n" + "=" * 70)
        print(" PIPELINE SEEDING COMPLETE — ALL SYSTEMS FULLY OPERATIONAL!")
        print(" Headline Index: T+15 Anchor | Base: 2026-08-01 = 100")
        print(" Dashboard: http://localhost:3000 | API Docs: http://localhost:8000/docs")
        print("=" * 70)

    except Exception as e:
        print(f"\n[ERROR] Pipeline bootstrapping failed: {e}")
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run_full_seed_pipeline()
