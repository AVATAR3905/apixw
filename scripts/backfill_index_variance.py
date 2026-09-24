"""Backfill bootstrap variance columns for historical index records.

The NSO-standard variance columns (standard_error / index_ci_lower /
index_ci_upper / bootstrap_replications / variance_method) were introduced
after historical index records were persisted, so those rows carry NULLs until
recomputed. Running this script recomputes the full index history from the
canonical base period so every published record is re-persisted with its CI.

This is intentionally a full, consistent recalculation (not a column-patch):
the index value and its bootstrap CI are rebuilt from the exact same inputs, so
a CI can never drift from the point estimate it describes.

Usage:
    python scripts/backfill_index_variance.py [--dry-run]
"""

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import func

from database.session import SessionLocal
from packages.schemas.models import IndexValue
from packages.shared.config import settings
from services.index_engine.calculator_service import DailyIndexCalculatorService


def _count_missing_variance(db) -> tuple:
    rows = (
        db.query(
            IndexValue.period_start,
            IndexValue.index_series,
            IndexValue.route_id,
            IndexValue.standard_error,
            IndexValue.index_ci_lower,
            IndexValue.index_ci_upper,
        )
        .all()
    )
    national = sum(1 for r in rows if r.route_id is None)
    national_missing = sum(
        1
        for r in rows
        if r.route_id is None
        and (r.standard_error is None or r.index_ci_lower is None or r.index_ci_upper is None)
    )
    route_missing = sum(
        1
        for r in rows
        if r.route_id is not None
        and (r.standard_error is None or r.index_ci_lower is None or r.index_ci_upper is None)
    )
    return national, national_missing, route_missing


def backfill_index_variance(dry_run: bool = False, force: bool = False) -> int:
    db = SessionLocal()
    try:
        national, national_missing, route_missing = _count_missing_variance(db)
        print("=" * 72)
        print(" BACKFILLING NSO-STANDARD BOOTSTRAP VARIANCE (SE + 95% CI)")
        print("=" * 72)
        print(f"[*] National  records total: {national}  (missing variance: {national_missing})")
        print(f"[*] Route-level records missing variance: {route_missing}")
        if national_missing == 0 and route_missing == 0 and not force:
            print("[=] Nothing to backfill - all records already carry variance.")
            return 0

        span = (
            db.query(
                func.min(IndexValue.period_start),
                func.max(IndexValue.period_start),
            )
            .filter(IndexValue.route_id.is_(None))
            .first()
        )
        min_date = span[0] or datetime.date.today()
        max_date = span[1] or min_date
        base_date = settings.BASE_PERIOD
        try:
            base_date = datetime.date.fromisoformat(base_date)
        except ValueError:
            base_date = min_date
        start = min(base_date, min_date)

        print(f"[*] Recomputing index history: {start} -> {max_date}")
        print(f"[*] Base period: {base_date}")
        if dry_run:
            print("[!] DRY RUN - nothing will be persisted (sampling smoke pass).")
            n = DailyIndexCalculatorService.compute_historical_index_range(
                db, start, max_date, persist=False
            )
            print(f"[!] Dry-run would recompute {n} index records.")
        else:
            n = DailyIndexCalculatorService.compute_historical_index_range(
                db, start, max_date, persist=True
            )
            _, national_missing, route_missing = _count_missing_variance(db)
            print(f"[+] Recomputed {n} index records.")
            print(f"[+] Remaining national records missing variance: {national_missing}")
            print(f"[+] Remaining route-level records missing variance: {route_missing}")
        return n
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate without persisting")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute even when every record already carries variance",
    )
    args = parser.parse_args()
    backfill_index_variance(dry_run=args.dry_run, force=args.force)
