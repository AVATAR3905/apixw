#!/usr/bin/env python3
"""Validate extracted fares against ground truth AND a live fare website.

Two independent checks per flight on a route/travel date:

1. INTRINSIC — compares each OCR/VLM-extracted observation against the
   fixture page's own authoritative fare (``demo_ocr_vlm_pipeline``'s
   deterministic ``_scheduled_price``), proving the extraction pipeline reads
   what the page actually displays. Any delta here is an extraction bug.

2. LIVE — reconciles extracted observations against real prices fetched from
   Google Flights (via the existing ``RealFlightRPCConnector``, matched on
   carrier code + departure time within a tolerance) and reports the price
   delta % vs the live market. This confirms the extracted data lands in the
   right ballpark, not just internally-consistent.

Writes a per-flight markdown report ``07_validation_report.md`` next to the
presentation assets.

Usage:
    python scripts/validate_flights.py --date 2026-09-15
    python scripts/validate_flights.py --route DEL-BOM --date 2026-09-16 --live-only
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

os.environ["EXTRACTION_ALLOW_OCR"] = "true"

from scripts._env_guard import guard_dependencies  # noqa: E402

guard_dependencies("yaml")


def _mm(hhmm: Optional[str]) -> int:
    """'09:30' -> minutes since midnight (None-safe)."""
    if not hhmm:
        return -1
    h, m = map(int, str(hhmm).split(":"))
    return h * 60 + m


def _flight_number(q: Dict[str, Any]) -> str:
    return str(q.get("flight_number") or "")


def _carrier(q: Dict[str, Any]) -> str:
    return str(q.get("carrier_code") or (q.get("carrier_name") or "?")[:2]).upper()


def intrinsic_check(quotes: List[Dict[str, Any]], travel_date, offset) -> List[Dict[str, Any]]:
    """Match each observation to its SCHEDULE_BOM entry and diff vs the fixture fare."""
    import scripts.demo_ocr_vlm_pipeline as demo

    schedule = {(c, num): (dep, arr) for c, num, dep, arr in demo.SCHEDULE_BOM}
    rows = []
    for q in quotes:
        carrier = _carrier(q)
        fn = _flight_number(q)
        number = fn.split("-", 1)[1] if "-" in fn else fn
        entry = schedule.get((carrier, number))
        expected = None
        if entry:
            dep, _arr = entry
            expected = demo._scheduled_price(carrier, number, dep, travel_date, offset)
        actual = q.get("total_fare")
        delta = None
        sign = None
        if expected is not None and actual:
            delta = ((float(actual) - expected) / expected) * 100.0
            sign = "OK" if abs(delta) < 0.5 else ("OVER" if delta > 0 else "UNDER")
        rows.append(
            {
                "flight": fn or f"{carrier}-???",
                "carrier": carrier,
                "dep_expected": entry[0] if entry else None,
                "extracted_fare": actual,
                "expected_fare": expected,
                "delta_pct": delta,
                "status": sign,
            }
        )
    return rows


def _live_client():
    from services.collectors.real_flight_connector import RealFlightRPCConnector

    return RealFlightRPCConnector()


def live_check(quotes: List[Dict[str, Any]], origin, dest, advance_days, search_date,
               tolerance_min: int = 25) -> Dict[str, Any]:
    """Fetch Google Flights for the corridor and match to extracted observations."""
    client = _live_client()
    live = client.search_corridor_horizon(origin, dest, advance_days, search_date=search_date)

    live_by = {}
    for lq in live:
        key = (_carrier(lq), _mm(lq.get("departure_time")))
        live_by.setdefault(key, []).append(float(lq.get("total_fare", 0)))

    rows = []
    matched = 0
    for q in quotes:
        carrier = _carrier(q)
        dep_min = _mm(q.get("departure_time"))
        best = None
        best_dist = tolerance_min + 1
        for (lc, lm), fares in live_by.items():
            if lc != carrier:
                continue
            if lm < 0 or dep_min < 0:
                continue
            dist = abs(lm - dep_min)
            if dist <= tolerance_min and dist < best_dist:
                best_dist = dist
                best = min(fares)
        actual = q.get("total_fare")
        if best is not None:
            matched += 1
            delta = ((float(actual) - best) / best) * 100.0 if best else None
            rows.append(
                {
                    "flight": _flight_number(q) or f"{carrier}-???",
                    "carrier": carrier,
                    "dep": q.get("departure_time"),
                    "extracted_fare": actual,
                    "live_fare": best,
                    "delta_pct": delta,
                    "match": "LIVE_MATCH" if delta is not None and abs(delta) <= 15 else "LIVE_NEAR",
                }
            )
        else:
            rows.append(
                {
                    "flight": _flight_number(q) or f"{carrier}-???",
                    "carrier": carrier,
                    "dep": q.get("departure_time"),
                    "extracted_fare": actual,
                    "live_fare": None,
                    "delta_pct": None,
                    "match": "NO_LIVE_MATCH",
                }
            )
    return {"rows": rows, "live_count": len(live), "matched": matched, "total": len(quotes)}


def main():
    parser = argparse.ArgumentParser(description="Validate extracted fares vs fixture & live Google Flights")
    parser.add_argument("--route", default="DEL-BOM")
    parser.add_argument("--date", default="", help="Travel date YYYY-MM-DD (default: tomorrow)")
    parser.add_argument("--vlm-backend", default="none", choices=["openrouter", "paddleocr_vl", "none"])
    parser.add_argument("--live-only", action="store_true", help="Skip extraction, only fetch live fares")
    parser.add_argument("--out-dir", default=r"C:\Users\cecilia\Downloads\Apix output")
    args = parser.parse_args()

    import datetime as dt

    origin, dest = args.route.upper().split("-")
    today = dt.date.today()
    travel_date = dt.date.fromisoformat(args.date) if args.date else today + dt.timedelta(days=1)
    offset = (travel_date - today).days
    if not 0 <= offset <= 28:
        parser.exit(2, f"travel date {travel_date} out of 28-day horizon\n")

    quotes: List[Dict[str, Any]] = []
    if not args.live_only:
        from scripts.demo_ocr_vlm_pipeline import run_day
        from services.extraction.adaptive_extractor import AdaptiveExtractor

        if args.vlm_backend == "none":
            os.environ["EXTRACTION_ALLOW_VLM"] = "false"
        else:
            os.environ["EXTRACTION_VLM_BACKEND"] = args.vlm_backend

        workdir = os.path.join(args.out_dir, "_work")
        os.makedirs(workdir, exist_ok=True)
        os.environ["DEMO_OUT_DIR"] = workdir

        extractor = AdaptiveExtractor()
        row = run_day(
            extractor, origin, dest, travel_date, offset,
            persist=False, db=None, force_vlm=(args.vlm_backend != "none"),
        )
        quotes = row["quotes"]
        print(f"\nExtraction: {len(quotes)} observations, "
              f"{sum(1 for q in quotes if q['total_fare'] and q['flight_number'])} complete")
    else:
        print("\n--live-only: skipping extraction.")

    print("\n[1/2] INTRINSIC vs fixture ground truth")
    print(f"{'flight':<12} {'carrier':<8} {'extracted':>10} {'fixture':>9} {'delta%':>8}  status")
    intrinsic = intrinsic_check(quotes, travel_date, offset)
    for r in intrinsic:
        print(f"{r['flight']:<12} {r['carrier']:<8} {r['extracted_fare'] or '-':>10} "
              f"{r['expected_fare'] or '-':>9} {r['delta_pct'] if r['delta_pct'] is not None else '-':>8}  {r['status'] or '?'}")
    ok = sum(1 for r in intrinsic if r["status"] == "OK")
    print(f"=> {ok}/{len(intrinsic)} exact, {len(intrinsic) - ok} off")

    print("\n[2/2] LIVE vs Google Flights")
    live = live_check(quotes, origin, dest, offset, search_date=today)
    print(f"fetched {live['live_count']} live results for {origin}->{dest} on {travel_date}")
    print(f"{'flight':<12} {'carrier':<8} {'dep':>6} {'extracted':>10} {'live':>9} {'delta%':>8}  match")
    for r in live["rows"]:
        print(f"{r['flight']:<12} {r['carrier']:<8} {str(r['dep']):>6} "
              f"{r['extracted_fare'] or '-':>10} {r['live_fare'] or '-':>9} "
              f"{r['delta_pct'] if r['delta_pct'] is not None else '-':>8}  {r['match']}")
    print(f"=> matched {live['matched']}/{live['total']} to live fares")

    report = os.path.join(args.out_dir, "07_validation_report.md")
    with open(report, "w", encoding="utf-8") as fh:
        fh.write(f"# Validation Report: {origin}->{dest} on {travel_date} (booked {today})\n\n")
        fh.write(f"- extraction method: {'live-only' if args.live_only else 'OCR(+VLM)'}\n")
        fh.write(f"- observations: **{len(quotes)}**\n\n")
        fh.write("| Flight | Carrier | Dep | Extracted (Rs) | Fixture (Rs) | Intr. delta% | Live (Rs) | Live delta% |\n")
        fh.write("|---|---|---|---|---|---|---|---|\n")
        live_map = {r["flight"]: r for r in live["rows"]}
        for r in intrinsic:
            lv = live_map.get(r["flight"])
            live_fare = lv["live_fare"] if lv else None
            live_delta = lv["delta_pct"] if lv else None
            fh.write(f"| {r['flight']} | {r['carrier']} | {r['dep_expected'] or '-'} | "
                     f"{r['extracted_fare'] or '-'} | {r['expected_fare'] or '-'} | "
                     f"{r['delta_pct'] if r['delta_pct'] is not None else '-'} | "
                     f"{live_fare or '-'} | {live_delta if live_delta is not None else '-'} |\n")
    print(f"\nReport written to {report}")


if __name__ == "__main__":
    main()
