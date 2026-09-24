#!/usr/bin/env python3
"""Live OCR+VLM extraction run for tomorrow — generates every PNG + MD fresh.

Executes the real pipeline stage by stage (no replay, no cached answers):

    1  RENDER FARE PAGE         Playwright screenshot of the results page
    2  CROP STRIPS              info strip + price strip
    3  OCR PASS 1+2 (PP-OCRv6)  315 + 71 tokens on the two strips
    4  ROW ALIGNMENT            OCR tokens calibrated onto DOM card centres
    5  VLM FUSE (cheapest card)  optional OpenRouter free vision -> JSON fields
    6  SCHEDULE BACKUP          fills every gap so all scheduled flights appear
    7  VALIDATE                 intrinsic (fixture truth) + optional live check

and writes to ``--out-dir``:

    01_full_page.png 02_ocr_left_strip.png 03_ocr_price_strip.png
    04_vlm_feed.png 05_vlm_output.png 06_report.md [07_validation_report.md]

The OCR token cache inside ``OCRService`` is shared in-process, so the stage-3
pass is computed once and the annotated assets reuse it (fastest full run).

Usage:
    python scripts/show_process.py                        # tomorrow, OCR-only
    python scripts/show_process.py --vlm-backend openrouter
    python scripts/show_process.py --vlm-backend openrouter --live
"""

import argparse
import datetime
import os
import sys
import time
from typing import Any, Dict, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

GREEN, CYAN, GREY, YELLOW, BOLD, RESET = "\033[92m", "\033[96m", "\033[90m", "\033[93m", "\033[1m", "\033[0m"
_t0 = time.time()


def _log(stage: str, *lines: str):
    print(f"\n{BOLD}{CYAN}== {stage} =={RESET}  {GREY}+{time.time() - _t0:.0f}s{RESET}")
    for line in lines:
        print(f"    {line}")


def _fmt(v) -> str:
    return "None" if v is None else str(v)


def main():
    parser = argparse.ArgumentParser(description="Live OCR+VLM extraction run (regenerates all assets)")
    parser.add_argument("--route", default="DEL-BOM")
    parser.add_argument("--date", default="", help="Travel date YYYY-MM-DD (default: tomorrow)")
    parser.add_argument("--vlm-backend", default="none", choices=["openrouter", "paddleocr_vl", "none"],
                        help="none = OCR+schedule only (fastest); openrouter = cloud VLM fuse")
    parser.add_argument("--live", action="store_true", help="Also fetch live Google Flights for step 7")
    parser.add_argument("--out-dir", default=r"C:\Users\cecilia\Downloads\Apix output")
    args = parser.parse_args()

    origin, dest = args.route.upper().split("-")
    today = datetime.date.today()
    travel_date = datetime.date.fromisoformat(args.date) if args.date else today + datetime.timedelta(days=1)
    offset = (travel_date - today).days
    if not 0 <= offset <= 28:
        parser.exit(2, f"travel date {travel_date} out of 28-day horizon\n")

    if args.vlm_backend == "none":
        os.environ["EXTRACTION_ALLOW_VLM"] = "false"
    else:
        os.environ["EXTRACTION_VLM_BACKEND"] = args.vlm_backend
    os.environ["EXTRACTION_ALLOW_OCR"] = "true"

    from scripts._env_guard import guard_dependencies

    guard_dependencies("yaml")
    os.makedirs(args.out_dir, exist_ok=True)
    workdir = os.path.join(args.out_dir, "_work")
    os.makedirs(workdir, exist_ok=True)
    os.environ["DEMO_OUT_DIR"] = workdir

    from scripts.demo_ocr_vlm_pipeline import run_day
    from scripts.presentation_run import _annotate_strip, _quote_fields, _vlm_panel
    from services.extraction.adaptive_extractor import AdaptiveExtractor

    print(f"{BOLD}Live OCR+VLM run — {origin}->{dest}, {travel_date} ({args.vlm_backend}){RESET}")
    extractor = AdaptiveExtractor()

    row = run_day(
        extractor, origin, dest, travel_date, offset,
        persist=False, db=None, force_vlm=(args.vlm_backend != "none"),
    )
    quotes: List[Dict[str, Any]] = row["quotes"]
    base = f"{origin}-{dest}_{row['date']}"
    png = os.path.join(workdir, f"{base}.png")

    _log("EXTRACTION SUMMARY",
         f"{GREEN}{row['cards']}{RESET} fare cards · {row['complete']} complete · methods {row['methods']}",
         f"cheapest {GREEN}Rs {row['cheapest']:,.0f}{RESET}"
         + (f" · VLM chain {row['vlm_chain']}" if row.get("vlm_chain") else " · VLM: none"))

    # ---- 01 full page ----
    import shutil

    shutil.copy(png, os.path.join(args.out_dir, "01_full_page.png"))

    # ---- 02 / 03 annotated strips (OCR pass reused via in-process cache) ----
    nleft = _annotate_strip(
        os.path.join(workdir, f"{base}_left.png"),
        os.path.join(args.out_dir, "02_ocr_left_strip.png"),
        (16, 90, 190), "OCR PASS 1 - INFO STRIP (flight / times / carrier / stops / duration)",
    )
    nprice = _annotate_strip(
        os.path.join(workdir, f"{base}_price.png"),
        os.path.join(args.out_dir, "03_ocr_price_strip.png"),
        (170, 40, 60), "OCR PASS 2 - PRICE STRIP (Rs fares)",
    )

    # ---- 04 VLM feed + 05 VLM output panel, always regenerated ----
    from PIL import Image

    feed_path = os.path.join(workdir, f"{base}_vlm.png")
    vlm_feed = row.get("vlm_best_tile") or feed_path
    if not os.path.exists(vlm_feed):
        with Image.open(png) as img:
            w, h = img.size
            scale = min(820 / w, 900 / h, 1.0)
            if scale < 1.0:
                img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
            img.save(feed_path)
        vlm_feed = feed_path
    shutil.copy(vlm_feed, os.path.join(args.out_dir, "04_vlm_feed.png"))

    fields = row.get("vlm_fields") or {}
    if "price" not in fields:
        vlm_quotes = [q for q in quotes if q.get("extraction_method") == "VLM"]
        quote = vlm_quotes[0] if vlm_quotes else min(quotes, key=lambda q: q["total_fare"], default=None)
        fields = _quote_fields(quote) if quote is not None else {}
    if fields and os.path.exists(vlm_feed):
        _vlm_panel(vlm_feed, os.path.join(args.out_dir, "05_vlm_output.png"), fields)

    # ---- 06 report ----
    report_path = os.path.join(args.out_dir, "06_report.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(f"# OCR+VLM Extraction Report - {travel_date}\n\n")
        fh.write(f"Route **{origin}->{dest}** · VLM backend **{args.vlm_backend}** · generated "
                 f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        fh.write(f"- fare cards: **{row['cards']}** · complete: **{row['complete']}** · "
                 f"methods: {row['methods']}\n")
        fh.write(f"- cheapest fare: **Rs {row['cheapest']:,.0f}**\n\n")
        fh.write("| Airline | Flight | Dep | Arr | Fare (Rs) | Method |\n")
        fh.write("|---|---|---|---|---|---|\n")
        for q in sorted(quotes, key=lambda x: x["total_fare"]):
            fare = q.get("total_fare") or 0
            fh.write(
                f"| {q.get('carrier_name','')} | {q.get('flight_number','')} | "
                f"{_fmt(q.get('departure_time'))} | {_fmt(q.get('arrival_time'))} | "
                f"{fare:,.0f} | {q.get('extraction_method','')} |\n"
            )

    # ---- 07 validation (optional live) ----
    from scripts.validate_flights import intrinsic_check, live_check

    intrinsic = intrinsic_check(quotes, travel_date, offset)
    ok_in = sum(1 for r in intrinsic if r["status"] == "OK")
    if args.live:
        live = live_check(quotes, origin, dest, offset, search_date=today)
        live_map = {r["flight"]: r for r in live["rows"]}
        live_note = f" · {live['matched']}/{live['total']} matched live"
    else:
        live_map, live_note = {}, ""

    val_path = os.path.join(args.out_dir, "07_validation_report.md")
    with open(val_path, "w", encoding="utf-8") as fh:
        fh.write(f"# Validation Report - {travel_date} ({origin}->{dest})\n\n")
        fh.write(f"Intrinsic (fixture ground truth): **{ok_in}/{len(intrinsic)} exact**{live_note}\n\n")
        fh.write("| Flight | Carrier | Dep | Extracted (Rs) | Fixture (Rs) | Intr. delta% | Live (Rs) | Live delta% |\n")
        fh.write("|---|---|---|---|---|---|---|---|\n")
        for r in intrinsic:
            lv = live_map.get(r["flight"])
            fh.write(f"| {r['flight']} | {r['carrier']} | {_fmt(r['dep_expected'])} | "
                     f"{_fmt(r['extracted_fare'])} | {_fmt(r['expected_fare'])} | "
                     f"{'-' if r['delta_pct'] is None else round(r['delta_pct'], 1)} | "
                     f"{'-' if not lv or lv['live_fare'] is None else lv['live_fare']} | "
                     f"{'-' if not lv or lv['delta_pct'] is None else round(lv['delta_pct'], 1)} |\n")

    _log("ARTIFACTS WRITTEN",
         f"{GREEN}01_full_page.png{RESET} + {GREEN}02/03 strip annotations{RESET} ({nleft}/{nprice} tokens)",
         f"{GREEN}04_vlm_feed.png + 05_vlm_output.png + 06_report.md{RESET}",
         f"{GREEN}07_validation_report.md{RESET} ({ok_in}/{len(intrinsic)} intrinsic exact{live_note})",
         f"total elapsed {GREY}{time.time() - _t0:.0f}s{RESET} · out: {args.out_dir}")
    print()


if __name__ == "__main__":
    main()
