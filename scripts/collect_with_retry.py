"""Retry wrapper around collect_full_real_coverage.py.

The underlying scrape occasionally dies mid-run from an uncaught Node.js
EPIPE crash inside Playwright's driver process (broken pipe on the
websocket to the browser) -- not a Python exception, so it can't be
caught inside the collection script itself. CollectionScheduler already
makes each run resume-safe (it skips route/horizon pairs already
COMPLETED for today), so simply relaunching the subprocess after a crash
is sufficient to eventually finish the full basket; this wrapper does
that automatically instead of leaving a dead run sitting until the next
4x-daily Task Scheduler slot.
"""
import argparse
import datetime
import subprocess
import sys
import time
from pathlib import Path

MAX_ATTEMPTS = 20
RETRY_DELAY_SECONDS = 15

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "logs" / "collection_cycle.log"
SCRIPT_PATH = Path(__file__).resolve().parent / "collect_full_real_coverage.py"


def _log(message: str) -> None:
    with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as log:
        log.write(message)


def progress_for(target_date: datetime.date) -> tuple[int, int]:
    """Returns (completed_pairs, expected_total) for target_date's route x horizon basket."""
    sys.path.insert(0, str(ROOT))
    from database.session import SessionLocal
    from packages.schemas.models import CollectionJob, Route
    from services.scheduler.collection_scheduler import CollectionScheduler

    db = SessionLocal()
    try:
        expected_total = db.query(Route).filter(Route.active).count() * len(CollectionScheduler.HORIZONS)
        completed = db.query(CollectionJob.route_id, CollectionJob.advance_days).filter(
            CollectionJob.search_date == target_date,
            CollectionJob.status == "COMPLETED",
        ).distinct().count()
        return completed, expected_total
    finally:
        db.close()


def run_once(attempt: int, target_date: datetime.date) -> int:
    _log(f"\n---- retry-wrapper attempt {attempt}/{MAX_ATTEMPTS} for {target_date} "
         f":: {datetime.datetime.now().isoformat()} ----\n")
    with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as log:
        log.flush()
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--date", target_date.isoformat()],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        type=lambda s: datetime.date.fromisoformat(s),
        default=None,
        help="Backfill a specific date's basket instead of today's (e.g. to "
             "finish one that got stuck across a midnight rollover).",
    )
    args = parser.parse_args()

    # Pinned once at start so a run that crosses midnight keeps retrying the
    # SAME basket instead of silently drifting onto a new day's empty one.
    target_date = args.date or datetime.date.today()
    _log(f"\n---- retry-wrapper: targeting {target_date} for this whole run ----\n")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        returncode = run_once(attempt, target_date)
        completed, expected_total = progress_for(target_date)
        _log(f"\n---- retry-wrapper: after attempt {attempt}, {completed}/{expected_total} "
             f"route/horizon pairs COMPLETED for {target_date} (exit code {returncode}) ----\n")

        if completed >= expected_total:
            _log(f"---- retry-wrapper: full basket confirmed complete after {attempt} attempt(s) ----\n")
            return 0

        _log(f"---- retry-wrapper: basket incomplete, retrying in {RETRY_DELAY_SECONDS}s ----\n")
        time.sleep(RETRY_DELAY_SECONDS)

    _log(f"\n---- retry-wrapper: giving up after {MAX_ATTEMPTS} attempts, basket still incomplete ----\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
