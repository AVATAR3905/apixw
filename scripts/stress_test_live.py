#!/usr/bin/env python3
"""Bounded concurrent-load smoke test against the live Vercel deployment.

Not a DDoS/extreme load test -- a realistic burst (dozens of concurrent
"users" hitting the real endpoints the dashboard/UI actually calls) to
verify the deployed API + shared Neon Postgres hold up before a demo.
Reports status-code distribution, latency percentiles, and error details
per endpoint.

Usage:
    python scripts/stress_test_live.py
    python scripts/stress_test_live.py --concurrency 50 --requests 300
"""

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE = "https://apix-observatory-api.vercel.app"

ENDPOINTS = [
    "/health",
    "/ui/",
    "/api/v1/index",
    "/api/v1/index/dual-series",
    "/api/v1/routes",
    "/routes",
    "/api/v1/corridors/DEL-BOM",
    "/api/v1/weights",
    "/api/v1/data-quality",
    "/api/v1/methodology",
]


def hit(path: str) -> dict:
    t0 = time.time()
    try:
        r = requests.get(BASE + path, timeout=15)
        return {"path": path, "status": r.status_code, "latency": time.time() - t0, "error": None}
    except Exception as e:
        return {"path": path, "status": None, "latency": time.time() - t0, "error": str(e)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=30)
    parser.add_argument("--requests", type=int, default=200)
    args = parser.parse_args()

    jobs = [ENDPOINTS[i % len(ENDPOINTS)] for i in range(args.requests)]

    print(f"Firing {args.requests} requests at {args.concurrency} concurrency across {len(ENDPOINTS)} endpoints...")
    t_start = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(hit, p) for p in jobs]
        for f in as_completed(futures):
            results.append(f.result())
    total_time = time.time() - t_start

    by_endpoint = {}
    for r in results:
        by_endpoint.setdefault(r["path"], []).append(r)

    print(f"\nTotal wall time: {total_time:.1f}s  ({args.requests / total_time:.1f} req/s)\n")
    print(f"{'Endpoint':<35} {'N':>4} {'2xx':>5} {'429':>5} {'5xx':>5} {'err':>5} {'p50(ms)':>9} {'p95(ms)':>9} {'max(ms)':>9}")
    print("-" * 100)

    overall_errors = []
    for path, rs in sorted(by_endpoint.items()):
        latencies = sorted(r["latency"] * 1000 for r in rs)
        n = len(rs)
        ok2xx = sum(1 for r in rs if r["status"] and 200 <= r["status"] < 300)
        n429 = sum(1 for r in rs if r["status"] == 429)
        n5xx = sum(1 for r in rs if r["status"] and r["status"] >= 500)
        nerr = sum(1 for r in rs if r["error"] is not None)
        p50 = latencies[len(latencies) // 2] if latencies else 0
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
        pmax = latencies[-1] if latencies else 0
        print(f"{path:<35} {n:>4} {ok2xx:>5} {n429:>5} {n5xx:>5} {nerr:>5} {p50:>9.0f} {p95:>9.0f} {pmax:>9.0f}")
        for r in rs:
            if r["error"] or (r["status"] and r["status"] >= 500):
                overall_errors.append(r)

    if overall_errors:
        print(f"\n{len(overall_errors)} hard errors (network failure or 5xx):")
        for e in overall_errors[:20]:
            print(f"  {e['path']}: status={e['status']} error={e['error']}")
    else:
        print("\nNo hard errors (network failures or 5xx) across the whole run.")


if __name__ == "__main__":
    main()
