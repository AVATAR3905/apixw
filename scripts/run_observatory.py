#!/usr/bin/env python3
"""Unified one-command runner for the India Airfare Price Observatory.

Seeds the database (deterministic 30-day synthetic baseline), runs a live
collection cycle (carrier-direct + Google-Flights RPC), warms forecast
accuracy snapshots so the dashboard backtest panel shows real numbers, then
launches the FastAPI backend (port 8000) and Next.js dashboard (port 3000)
concurrently with graceful shutdown on Ctrl+C.

Usage:
    python scripts/run_observatory.py                # default: seed + focused collect + servers
    python scripts/run_observatory.py --reset        # wipe & reseed, then run everything
    python scripts/run_observatory.py --no-collect   # skip live scraping (seed + accuracy only)
    python scripts/run_observatory.py --full         # full 10-route x 5-horizon collection
"""

import argparse
import datetime
import os
import signal
import subprocess
import sys
import time
from typing import List

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

DASHBOARD_DIR = os.path.join(PROJECT_ROOT, "apps", "dashboard")

# Core runtime dependencies checked before any app import (a bare Python build
# without the project's requirements will otherwise die with a raw traceback).
CRITICAL_DEPS = [
    ("sqlalchemy", "pip install sqlalchemy"),
    ("fastapi", "pip install fastapi"),
    ("uvicorn", "pip install uvicorn[standard]"),
    ("pydantic", "pip install pydantic"),
    ("pandas", "pip install pandas"),
]


def _check_dependencies() -> None:
    """Fail fast with actionable guidance if required packages are missing."""
    missing = [label for label, _ in CRITICAL_DEPS if not _importable(label)]
    if not missing:
        return

    print("\n[ERROR] Missing required Python packages: " + ", ".join(missing))
    print("  The current interpreter is: " + sys.executable)
    print("  Fix one of:\n")
    print("  1) Use the Anaconda base env (already has all dependencies):")
    print("        C:\\Users\\cecilia\\anaconda3\\python.exe scripts/run_observatory.py")
    print("  2) Install the project requirements into this environment:")
    print("        python -m pip install -r requirements.txt")
    print("\n  The seeded database (airfare_observatory.db) already exists in this")
    print("  folder, so no data setup is needed once the right interpreter is used.\n")
    sys.exit(1)


def _importable(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_banner(api_port: int, dash_port: int, api_host: str):
    print("\n" + "=" * 80)
    print("  INDIA AIRFARE PRICE OBSERVATORY (APIX-2.0)  —  FULL PIPELINE LAUNCHER")
    print("=" * 80)
    print(f"  API Docs:    http://{api_host}:{api_port}/docs")
    print(f"  Dashboard:   http://localhost:{dash_port}")
    print("  Ctrl+C to gracefully shut down.\n")
    print("=" * 80)


def _is_windows() -> bool:
    return sys.platform == "win32"


def _npm_cmd() -> str:
    return "npm.cmd" if _is_windows() else "npm"


# ---------------------------------------------------------------------------
# Step 1: Database
# ---------------------------------------------------------------------------

def ensure_tables():
    """Create all tables (including forecast_snapshots) if they don't exist."""
    from database.session import init_db
    print("[1/4] Ensuring database schema...")
    init_db()
    print("      -> Tables verified.")


def seed_if_needed(reset: bool = False):
    """Seed deterministic baseline if DB is empty or --reset requested."""
    from database.session import SessionLocal
    from packages.schemas.models import IndexValue

    if not reset:
        db = SessionLocal()
        try:
            count = db.query(IndexValue).count()
        finally:
            db.close()
        if count > 0:
            print("[2/4] Database already seeded (skip). Use --reset to wipe & reseed.")
            return

    print("[2/4] Seeding 30-day baseline (routes, weights, observations, indices, benchmarks)...")
    from services.seed_demo_data import run_full_seed_pipeline
    run_full_seed_pipeline()


# ---------------------------------------------------------------------------
# Step 2: Collection
# ---------------------------------------------------------------------------

def run_focused_collection(use_vlm: bool = False):
    """Run a single-corridor live collection (DEL-BOM T+15)."""
    if not use_vlm:
        os.environ["EXTRACTION_ALLOW_VLM"] = "false"
        print("      (VLM stage disabled for the demo — DOM/OCR, fall back to calibrated model; use --use-vlm to enable)")
    from services.collectors.dual_feed_runner import run_dual_feed_collection
    print("\n[3/4] Running live collection: DEL-BOM T+15 (carrier-direct + RPC)...")
    reconciliation = run_dual_feed_collection(
        route_code="DEL-BOM",
        advance_days=15,
        search_date=datetime.date.today(),
    )
    n = len(reconciliation.get("primary_observations", []))
    print(f"      -> Persisted {n} real observations (is_synthetic=False).")
    return reconciliation


def run_full_collection(use_vlm: bool = False):
    """Run production collection across all 10 corridors x 5 horizons."""
    if not use_vlm:
        os.environ["EXTRACTION_ALLOW_VLM"] = "false"
        print("      (VLM stage disabled for the demo — DOM/OCR, fall back to calibrated model; use --use-vlm to enable)")
    from services.collectors.production_collector import run_production_collection
    print("\n[3/4] Running full production collection (10 corridors x 5 horizons)...")
    summary = run_production_collection(delay_seconds=0.5)
    print(f"      -> Authentic quotes persisted: {summary['total_authentic_quotes_persisted']}")
    print(f"      -> Indices recalculated:      {summary['indices_recalculated']}")
    return summary


# ---------------------------------------------------------------------------
# Step 3: Forecast accuracy warm-up (backdated snapshots for demo accuracy panel)
# ---------------------------------------------------------------------------

def warm_accuracy_snapshots():
    """Generate a few backdated forecast snapshots so the accuracy panel has realized matches.

    Produces one snapshot each for BASE_FARE and TOTAL_PRICE on HEADLINE_T15,
    using history truncated 21 days before today.  The forecast targets will
    fall inside the seed's realized index window (Aug 1–30), giving genuine
    accuracy metrics out of the box.
    """
    from database.session import SessionLocal
    from packages.schemas.models import IndexValue
    from services.ml.ensemble import EnsembleForecaster
    from services.ml.forecast_accuracy import persist_forecast_snapshot

    horizon_days = 21
    cap_date = datetime.date.today() - datetime.timedelta(days=horizon_days)

    print(f"\n[3b] Warming forecast accuracy: generating backdated snapshots (history <= {cap_date})...")

    combos = [
        ("BASE_FARE", "HEADLINE_T15"),
        ("TOTAL_PRICE", "HEADLINE_T15"),
    ]

    db = SessionLocal()
    total_snapshots = 0
    try:
        forecaster = EnsembleForecaster()
        for series, index_type in combos:
            rows = (
                db.query(IndexValue.period_start, IndexValue.index_value)
                .filter(
                    IndexValue.index_series == series,
                    IndexValue.index_type == index_type,
                    IndexValue.route_id.is_(None),
                    IndexValue.period_start <= cap_date,
                )
                .order_by(IndexValue.period_start.asc())
                .limit(100)
                .all()
            )
            history = [{"date": r.period_start.isoformat(), "value": r.index_value} for r in rows]
            if len(history) < 10:
                print(f"      [{series}/{index_type}] Insufficient history ({len(history)}), skipping.")
                continue

            forecast = forecaster.forecast(series, index_type, history, horizon=28)
            persist_forecast_snapshot(
                db,
                series=forecast.series,
                index_type=forecast.index_type,
                forecast_date=forecast.forecast_date,
                points=forecast.points,
                ensemble_weights=forecast.ensemble_weights,
                model_versions=forecast.model_versions,
                history_days=len(history),
                horizon_days=forecast.horizon_days,
            )
            total_snapshots += 1
            print(f"      [{series}/{index_type}] Persisted snapshot with {len(forecast.points)} forecast points.")

    finally:
        db.close()

    print(f"      -> {total_snapshots} forecast snapshots ready for accuracy backtest.")


# ---------------------------------------------------------------------------
# Step 4: Servers
# ---------------------------------------------------------------------------

def start_servers(api_port: int, dash_port: int, api_host: str, dev_mode: bool):
    """Launch API and dashboard concurrently, wait for Ctrl+C, shut down gracefully."""
    processes: List[dict] = []
    try:
        # API
        api_cmd = [sys.executable, "-m", "uvicorn", "apps.api.main:app",
                   "--host", api_host, "--port", str(api_port)]
        api_proc = subprocess.Popen(api_cmd, cwd=PROJECT_ROOT)
        processes.append({"name": "FastAPI Backend", "proc": api_proc})
        print("[4/4] Waiting for FastAPI to bind...")
        time.sleep(3)

        # Dashboard
        npm = _npm_cmd()
        # npm with multiple args needs list form; "run dev" is simplest for dev mode.
        npm_cmd_list = [npm, "run", "dev"] if dev_mode else [npm, "run", "start"]
        dash_proc = subprocess.Popen(npm_cmd_list, cwd=DASHBOARD_DIR)
        processes.append({"name": "Next.js Dashboard", "proc": dash_proc})

        _print_banner(api_port, dash_port, api_host)
        print("[+] Pipeline is live. Press Ctrl+C to stop.\n")

        while True:
            for p in processes:
                ret = p["proc"].poll()
                if ret is not None:
                    print(f"\n[!] {p['name']} exited (code {ret}). Shutting down...")
                    return
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[*] Ctrl+C received — terminating services...")
    finally:
        for p in processes:
            proc = p["proc"]
            if proc.poll() is None:
                print(f"    Stopping {p['name']} (PID {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        print("[+] Observatory shut down cleanly.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="One-command runner: seed + collect + accuracy warm-up + servers",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--reset",       action="store_true", help="Wipe & reseed the database before running")
    parser.add_argument("--no-seed",     action="store_true", help="Skip database seeding entirely")
    parser.add_argument("--no-collect",  action="store_true", help="Skip live collection (seed-only run)")
    parser.add_argument("--full",        action="store_true", help="Run full 10-route x 5-horizon collection")
    parser.add_argument("--use-vlm",     action="store_true", help="Enable the heavy 0.9B VLM extraction stage (default: off for speed)")
    parser.add_argument("--no-warm",     action="store_true", help="Skip forecast accuracy warm-up snapshots")
    parser.add_argument("--no-servers",  action="store_true", help="Run pipeline only, don't start API/dashboard")
    parser.add_argument("--api-port",    type=int, default=8000, help="FastAPI port (default 8000)")
    parser.add_argument("--dash-port",   type=int, default=3000, help="Dashboard port (default 3000)")
    parser.add_argument("--api-host",    default="0.0.0.0",     help="FastAPI bind host (default 0.0.0.0)")
    parser.add_argument("--prod-dash",   action="store_true", help="Use 'npm run start' (production) instead of dev server")
    return parser.parse_args()


def main():
    args = parse_args()

    _check_dependencies()

    # Handle Ctrl+C gracefully from the start
    signal.signal(signal.SIGINT, lambda *_: None)

    ensure_tables()

    if not args.no_seed:
        seed_if_needed(reset=args.reset)

    if not args.no_collect:
        if args.full:
            run_full_collection(use_vlm=args.use_vlm)
        else:
            run_focused_collection(use_vlm=args.use_vlm)
    else:
        print("[3/4] Collection: SKIPPED (--no-collect)")

    if not args.no_warm:
        warm_accuracy_snapshots()
    else:
        print("[3b] Forecast warm-up: SKIPPED (--no-warm)")

    if not args.no_servers:
        start_servers(
            api_port=args.api_port,
            dash_port=args.dash_port,
            api_host=args.api_host,
            dev_mode=not args.prod_dash,
        )
    else:
        print("[4/4] Servers: SKIPPED (--no-servers)")
        print("\nDone. API + Dashboard not started.\n")


if __name__ == "__main__":
    main()
