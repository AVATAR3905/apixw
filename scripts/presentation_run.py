#!/usr/bin/env python3
"""One-command presentable demo run for the Airfare Observatory.

Runs the real multi-airline extraction pipeline (OCR strips -> calibrated
row alignment -> VLM fuse -> schedule backup) for the requested travel dates,
then writes presentation-ready assets plus a full flight report into an
output folder:

    <out>/01_full_page.png       rendered flight-results page (Playwright)
    <out>/02_ocr_left_strip.png  OCR pass 1: info strip with token boxes
    <out>/03_ocr_price_strip.png OCR pass 2: price strip with token boxes
    <out>/04_vlm_feed.png        the bounded image the VLM reads
    <out>/05_vlm_output.png      VLM feed + structured fields panel
    <out>/06_report.md           per-flight fare table + methods summary

Usage:
    python scripts/presentation_run.py --date 2026-09-14
    python scripts/presentation_run.py --vlm-backend paddleocr_vl --persist
    python scripts/presentation_run.py --out-dir "C:\\Present\\out"
"""

import argparse
import datetime
import os
import shutil
import sys
from typing import Any, Dict, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)
os.environ["EXTRACTION_ALLOW_OCR"] = "true"
os.environ["EXTRACTION_ALLOW_VLM"] = "true"

from scripts._env_guard import guard_dependencies  # noqa: E402

guard_dependencies("yaml")


def _font(size: int):
    from PIL import ImageFont

    for cand in ("C:\\Windows\\Fonts\\consola.ttf", "C:\\Windows\\Fonts\\segoeui.ttf"):
        if os.path.exists(cand):
            return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


def _annotate_strip(path: str, out: str, color: tuple, title: str, max_overlay: int = 60) -> int:
    """OCR one strip and overlay the detected token boxes + labels."""
    from PIL import Image, ImageDraw

    from services.extraction.ocr_service import OCRService

    img = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(img)
    f_lab, f_title = _font(13), _font(16)
    tokens = OCRService().extract(path)
    for t in tokens[:max_overlay]:
        x1, y1, x2, y2 = (int(v) for v in t.bbox)
        draw.rectangle([x1, y1 - 2, x2, y2 + 6], outline=color, width=1)
        text = (t.text or "")[:40]
        if text.strip():
            w = f_lab.getbbox(text)[2]
            draw.rectangle([x1, max(0, y1 - 16), x1 + w + 2, y1], fill=color)
            draw.text((x1 + 1, max(0, y1 - 15)), text, fill="white", font=f_lab)
    draw.rectangle([0, 0, img.width, 36], fill=color)
    draw.text((8, 8), title, fill="white", font=f_title)
    img.save(out)
    return len(tokens)


def _vlm_panel(image_path: str, out: str, fields: Dict[str, Any]):
    """Feed image on top, the VLM's structured fields panel below."""
    from PIL import Image, ImageDraw

    feed = Image.open(image_path).convert("RGB")
    scale = min(1.0, 1000 / feed.size[0])
    feed = feed.resize((round(feed.size[0] * scale), round(feed.size[1] * scale)))

    panel = Image.new("RGB", (1000, feed.size[1] + 320), (18, 18, 24))
    panel.paste(feed, (0, 0))
    draw = ImageDraw.Draw(panel)
    f_head, f_fld, f_key = _font(18), _font(16), _font(13)
    draw.text(
        (12, feed.size[1] + 10),
        "VLM STRUCTURED OUTPUT (PaddleOCR-VL / OpenRouter free)",
        fill=(120, 220, 160),
        font=f_head,
    )
    rows = [
        ("origin", fields.get("origin")),
        ("destination", fields.get("destination")),
        ("price", fields.get("price")),
        ("airline", fields.get("airline")),
        ("airline_name", fields.get("airline_name")),
        ("flight_number", fields.get("flight_number")),
        ("departure_time", fields.get("departure_time")),
        ("arrival_time", fields.get("arrival_time")),
        ("stops", fields.get("stops")),
        ("duration_minutes", fields.get("duration_minutes")),
        ("travel_date", fields.get("travel_date")),
    ]
    y = feed.size[1] + 46
    for k, v in rows:
        draw.rectangle([12, y - 1, 988, y + 24], outline=(60, 60, 70), width=1)
        draw.text((16, y + 2), k.ljust(16), fill=(140, 140, 160), font=f_key)
        draw.text((150, y + 2), "" if v is None else str(v), fill=(245, 245, 245), font=f_fld)
        y += 30
    panel.save(out)


def _quote_fields(quote: Dict[str, Any]) -> Dict[str, Any]:
    """Map a fused per-flight observation onto the VLM panel rows."""
    return {
        "origin": quote.get("origin"),
        "destination": quote.get("destination"),
        "price": quote.get("total_fare"),
        "airline": quote.get("carrier_code"),
        "airline_name": quote.get("carrier_name"),
        "flight_number": quote.get("flight_number"),
        "departure_time": quote.get("departure_time"),
        "arrival_time": quote.get("arrival_time"),
        "stops": quote.get("stops"),
        "duration_minutes": quote.get("duration_minutes"),
        "travel_date": quote.get("travel_date"),
    }


def main():
    parser = argparse.ArgumentParser(description="Presentable demo run for the Airfare Observatory")
    parser.add_argument("--route", default="DEL-BOM")
    parser.add_argument("--date", default="", help="Optional single travel date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--start-offset", type=int, default=0)
    parser.add_argument("--vlm-backend", default="openrouter",
                        choices=["openrouter", "paddleocr_vl", "none"])
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--out-dir", default=r"C:\Users\cecilia\Downloads\Apix output")
    args = parser.parse_args()

    import datetime as dt

    origin, dest = args.route.upper().split("-")
    today = dt.date.today()

    if args.date:
        travel = dt.date.fromisoformat(args.date)
        offsets = [(travel - today).days]
        if not (0 <= offsets[0] <= 28):
            parser.exit(2, f"--date {args.date} out of the 28-day horizon\n")
        days = len(offsets)
    else:
        days = min(max(args.days, 1), 28)
        offsets = list(range(args.start_offset, args.start_offset + days))

    if args.vlm_backend == "none":
        os.environ["EXTRACTION_ALLOW_VLM"] = "false"
    else:
        os.environ["EXTRACTION_VLM_BACKEND"] = args.vlm_backend

    os.makedirs(args.out_dir, exist_ok=True)
    workdir = os.path.join(args.out_dir, "_work")
    os.makedirs(workdir, exist_ok=True)
    os.environ["DEMO_OUT_DIR"] = workdir

    from scripts.demo_ocr_vlm_pipeline import run_day
    from services.extraction.adaptive_extractor import AdaptiveExtractor

    extractor = AdaptiveExtractor()

    db = None
    if args.persist:
        from database.session import SessionLocal

        db = SessionLocal()

    print(f"\nPresentable demo: {origin}-{dest} · {len(offsets)} travel date(s) "
          f"· VLM backend: {args.vlm_backend} · output: {args.out_dir}\n")
    header = f"{'Travel date':<12} | {'cards':<6} | {'methods':<34} | {'cheapest':<9} | persisted"
    print(header)
    print("-" * 90)

    rows: List[Dict[str, Any]] = []
    try:
        for offset in offsets:
            travel_date = today + dt.timedelta(days=offset)
            row = run_day(
                extractor, origin, dest, travel_date, offset,
                persist=args.persist, db=db, force_vlm=(args.vlm_backend != "none"),
            )
            rows.append(row)
            print(f"{row['date']:<12} | {row['cards']:<6} | {str(row['methods']):<34} | "
                  f"{row['cheapest']:>9,.0f} | {row['persisted']}")
    finally:
        if db is not None:
            db.close()

    # ---- presentation assets (first date) ----
    first = rows[0]
    date = first["date"]
    base = f"{origin}-{dest}_{date}"
    png = os.path.join(workdir, f"{base}.png")
    if os.path.exists(png):
        shutil.copy(png, os.path.join(args.out_dir, "01_full_page.png"))
        _annotate_strip(
            os.path.join(workdir, f"{base}_left.png"),
            os.path.join(args.out_dir, "02_ocr_left_strip.png"),
            (16, 90, 190), "OCR PASS 1 - INFO STRIP (flight / times / carrier / stops / duration)",
        )
        _annotate_strip(
            os.path.join(workdir, f"{base}_price.png"),
            os.path.join(args.out_dir, "03_ocr_price_strip.png"),
            (170, 40, 60), "OCR PASS 2 - PRICE STRIP (Rs fares)",
        )

        def _downscale_to(path: str) -> str:
            from PIL import Image

            with Image.open(path) as img:
                w, h = img.size
                scale = min(820 / w, 900 / h, 1.0)
                if scale < 1.0:
                    img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
                out = os.path.join(workdir, f"{base}_vlm.png")
                img.save(out)
                return out

        # The VLM feed is a legible tile (native width, ~800px tall) instead of
        # the whole page crushed to 261x900, so fare-card text stays readable.
        vlm_feed = first.get("vlm_best_tile")
        vlm_feed = vlm_feed if os.path.exists(vlm_feed) else (first.get("quotes") and _downscale_to(png))
        if vlm_feed:
            shutil.copy(vlm_feed, os.path.join(args.out_dir, "04_vlm_feed.png"))
        fields = first.get("vlm_fields") or {}
        if "price" not in fields:
            vlm_quotes = [q for q in first.get("quotes", []) if q.get("extraction_method") == "VLM"]
            quote = vlm_quotes[0] if vlm_quotes else min(
                first.get("quotes", []), key=lambda x: x["total_fare"], default=None
            )
            fields = _quote_fields(quote) if quote is not None else {}
        if fields and vlm_feed:
            _vlm_panel(
                vlm_feed,
                os.path.join(args.out_dir, "05_vlm_output.png"),
                fields,
            )

    # ---- report ----
    report_path = os.path.join(args.out_dir, "06_report.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("# Airfare Observatory - Illustrated Demo Report\n\n")
        fh.write(f"Route **{origin}->{dest}** · VLM backend **{args.vlm_backend}** · generated "
                 f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        for row in rows:
            fh.write(f"## {row['date']}\n\n")
            fh.write(f"- fare cards: **{row['cards']}** · complete: **{row['complete']}** · "
                     f"persisted: **{row['persisted']}**\n")
            fh.write(f"- extraction methods: {row['methods']}\n")
            fh.write(f"- cheapest fare: **Rs {row['cheapest']:,.0f}**\n\n")
            fh.write("| Airline | Flight | Dep | Arr | Fare (Rs) | Method |\n")
            fh.write("|---|---|---|---|---|---|\n")
            for q in sorted(row.get("quotes", []), key=lambda x: x["total_fare"]):
                fare = q.get("total_fare") or 0
                fh.write(
                    f"| {q.get('carrier_name','')} | {q.get('flight_number','')} | "
                    f"{q.get('departure_time','') or '-'} | {q.get('arrival_time','') or '-'} | "
                    f"{fare:,.0f} | {q.get('extraction_method','')} |\n"
                )

    print("-" * 90)
    print(f"\nPresentation run complete: {len(rows)} travel date(s), "
          f"{sum(r['cards'] for r in rows)} fare cards, {sum(r['complete'] for r in rows)} complete")
    print(f"Assets + report written to {args.out_dir}")
    print("   01_full_page.png / 02_ocr_left_strip.png / 03_ocr_price_strip.png")
    print("   04_vlm_feed.png / 05_vlm_output.png / 06_report.md")


if __name__ == "__main__":
    main()
