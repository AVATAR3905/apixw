#!/usr/bin/env python3
"""Multi-airline OCR + VLM end-to-end extraction demo for the Airfare Observatory.

Renders a realistic multi-carrier results page (IndiGo / Air India / SpiceJet /
Akasa) for every travel date from today through +N days, screenshots it with
Playwright, then pushes it through the REAL extraction stack:

    screenshot -> OCR geometry (PP-OCRv6) -> LayoutClusterer ->
        per-fare-card field parsing (every card becomes its own observation)

On ``--vlm-every`` N-th dates the slow local PaddleOCR-VL-0.9B stage also runs
and fuses the headline (cheapest) record, giving genuine OCR->VLM provenance
for those dates. Every fare card from every airline is persisted, not just the
cheapest, so the dashboard shows the full multi-airline supply curve.

Usage:
    python scripts/demo_ocr_vlm_pipeline.py                    # DEL-BOM, next 28 days, persist
    python scripts/demo_ocr_vlm_pipeline.py --days 1 --start-offset 1   # just 14 Sep
    python scripts/demo_ocr_vlm_pipeline.py --vlm-every 1      # force VLM on EVERY date (slow)
    python scripts/demo_ocr_vlm_pipeline.py --vlm-none          # OCR only, no VLM at all
    python scripts/demo_ocr_vlm_pipeline.py --no-persist       # extract only, no DB writes
"""

import argparse
import datetime
import os
import re
import sys
from typing import Any, Dict, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

# The demo pipeline must use both stages regardless of runner defaults.
os.environ["EXTRACTION_ALLOW_OCR"] = "true"
os.environ["EXTRACTION_ALLOW_VLM"] = "true"

OUT_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "demo_extraction")

# Airline base fares keep a realistic spread: premium legacy (AI) vs budget LCCs.
AIRLINES = [
    ("6E", "IndiGo", 6200),
    ("AI", "Air India", 8400),
    ("SG", "SpiceJet", 6700),
    ("QP", "Akasa Air", 6900),
]
FLIGHT_TIMES = [
    ("06:30", "08:40", "Non-stop", "2h 10m"),
    ("08:15", "10:20", "Non-stop", "2h 05m"),
    ("10:45", "12:55", "Non-stop", "2h 10m"),
    ("13:20", "15:30", "1 Stop", "3h 40m"),
    ("16:40", "18:50", "Non-stop", "2h 10m"),
    ("19:10", "21:15", "Non-stop", "2h 05m"),
]
FLIGHT_TAIL = [8471, 8493, 8510, 8522, 8534, 8561]

CARRIER_NAMES = {code: name for code, name, _ in AIRLINES}


def _flight_number(carrier: str, index: int) -> str:
    return f"{carrier}-{FLIGHT_TAIL[index % len(FLIGHT_TAIL)]}"


def fare_page_html(travel_date: datetime.date, offset: int) -> str:
    """A realistic multi-airline results page. Header route uses a single '-'
    separator so the extraction route regex can parse it, and each fare card is
    a horizontal band (time | flight | stops | duration | price) that the
    layout clusterer turns back into one observation per card."""
    date_display = travel_date.strftime("%d %b %Y")
    day_name = travel_date.strftime("%A")

    cards = []
    for flight_i in range(len(FLIGHT_TIMES)):
        dep, arr, stops, duration = FLIGHT_TIMES[flight_i]
        for carrier, carrier_name, base in AIRLINES:
            price = base + ((flight_i * 530) % 1700) + ((offset * 47) % 700)
            price = (price // 5) * 5
            cards.append(
                f"""
                <div class="card">
                  <div class="timeblock">
                    <div class="time">{dep}</div>
                    <div class="time">{arr}</div>
                  </div>
                  <div class="flight">{_flight_number(carrier, flight_i)}</div>
                  <div class="carrier">{carrier_name}</div>
                  <div class="detail">{stops}</div>
                  <div class="detail">{duration}</div>
                  <div class="price">Rs {price}</div>
                </div>"""
            )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 0; background: #fff; color: #111; }}
  .topbar {{ display: flex; align-items: center; justify-content: space-between;
              padding: 16px 24px; border-bottom: 2px solid #eee; }}
  .brand {{ font-size: 20px; font-weight: 700; color: #c8102e; }}
  .routechip {{ font-size: 30px; font-weight: 800; font-stretch: condensed; }}
  .datechip {{ font-size: 17px; color: #444; text-align: right; }}
  .cards {{ padding: 10px 24px; }}
  .card {{ display: flex; align-items: center; border-bottom: 1px solid #eee;
            padding: 13px 0; gap: 18px; }}
  .carrier {{ width: 132px; font-size: 16px; color: #555; }}
  .timeblock {{ display: flex; gap: 14px; width: 168px; }}
  .time {{ font-size: 21px; font-weight: 700; }}
  .flight {{ width: 150px; font-size: 21px; font-weight: 700; }}
  .detail {{ width: 92px; font-size: 16px; color: #333; }}
  .price {{ margin-left: auto; font-size: 22px; font-weight: 800; color: #0a7d32; }}
</style></head><body>
  <div class="topbar">
    <div class="brand">Flight Search</div>
    <div class="routechip">DEL - BOM</div>
    <div class="datechip">{day_name}<br>{date_display}</div>
  </div>
  <div class="cards">{''.join(cards)}</div>
</body></html>"""


def element_rects(html: str, path: str) -> List[Dict[str, Dict[str, float]]]:
    """Render the fixture page and return per-card cell rectangles (in PNG
    pixel space, scale 1): flight, times, carrier, stops, duration, price.

    Real fare scrapers hold exactly this kind of results-list layout knowledge;
    the OCR below reads the pixels cut from those cells rather than guessing
    row geometry from detection boxes.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1120, "height": 620})
            page.set_content(html, wait_until="load")
            cards = page.eval_on_selector_all(
                ".card",
                """(els) => els.map(card => {
                    const out = {};
                    for (const k of ["flight", "times", "carrier", "price"]) {
                        const el = card.querySelector("." + k);
                        if (!el) continue;
                        const r = el.getBoundingClientRect();
                        out[k] = {x: r.x, y: r.y, width: r.width, height: r.height};
                    }
                    const details = card.querySelectorAll(".detail");
                    for (const [k, el] of [["stops", details[0]], ["duration", details[1]]]) {
                        if (!el) continue;
                        const r = el.getBoundingClientRect();
                        out[k] = {x: r.x, y: r.y, width: r.width, height: r.height};
                    }
                    return out;
                })""",
            )
            page.screenshot(path=path, full_page=True)
            return cards
        finally:
            browser.close()


def _downscale(path: str, max_width: int = 820) -> str:
    """Return a width-capped copy of ``path`` (PNG); keeps OCR readable while
    shrinking the slow local VLM's feed well down."""
    from PIL import Image

    with Image.open(path) as img:
        w, h = img.size
        if w > max_width:
            img = img.resize((max_width, round(h * max_width / w)), Image.LANCZOS)
        out = os.path.join(OUT_DIR, os.path.basename(path)).rsplit(".", 1)[0] + "_vlm.png"
        img.save(out)
        return out


def _bucket_rows(tokens: List[Any], y_gap: float = 40.0) -> List[List[Any]]:
    """Buckets y-sorted OCR tokens into text rows; ``y_gap`` is the max spread
    allowed within one row (cards sit ~57px apart, cell text ~21px tall)."""
    rows: List[List[Any]] = []
    for token in sorted(tokens, key=lambda t: t.y_center):
        if rows and token.y_center - rows[-1][-1].y_center <= y_gap:
            rows[-1].append(token)
        else:
            rows.append([token])
    return rows


def _price_strip(image_path: str, cards: List[Dict[str, Dict[str, float]]]) -> str:
    """Crop the price column out of the full-page screenshot.

    One narrow strip keeps PP-OCRv6's detector honest: a wide full-page pass
    keeps dropping the right-aligned price island, while the 160px-wide strip
    reads every Rs-number cleanly in a single model call.
    """
    from PIL import Image

    cells = [c["price"] for c in cards if "price" in c]
    if not cells:
        return image_path
    pad = 8.0
    box = (
        min(c["x"] for c in cells) - pad,
        min(c["y"] for c in cells) - pad,
        max(c["x"] + c["width"] for c in cells) + pad,
        max(c["y"] + c["height"] for c in cells) + pad,
    )
    out = os.path.join(OUT_DIR, os.path.basename(image_path)).rsplit(".", 1)[0] + "_price.png"
    with Image.open(image_path) as img:
        img.crop(box).save(out)
    return out


def parse_cards(image_path: str, cards: List[Dict[str, Dict[str, float]]], reference_date: str) -> List[Dict[str, Any]]:
    """OCR the results page and emit one observation per fare card.

    Two model passes over the same screenshot:
      * a full-page pass whose row-buckets yield flight / times / carrier /
        stops / duration, and
      * a dedicated price-column strip whose 160px-wide crop reads every
        right-aligned Rs-number (the wide page keeps losing the island).
    Rows are merged by rank — both passes return the same visual row order, so
    no pixel-space calibration is needed.
    """
    from services.extraction.adaptive_extractor import AdaptiveExtractor
    from services.extraction.ocr_service import OCRService

    ocr = OCRService()
    rows = _bucket_rows(ocr.extract(image_path))
    price_strip = _price_strip(image_path, cards)
    price_rows = _bucket_rows(ocr.extract(price_strip))

    quotes: List[Dict[str, Any]] = []
    for i in range(min(len(rows), len(price_rows))):
        texts = [t.text for t in rows[i]] + [t.text for t in price_rows[i]]
        fields = AdaptiveExtractor.fields_from_dom(texts, reference_date)
        flight = fields.get("flight_number")
        price = fields.get("price")
        if not flight or not price:
            continue
        flight = re.sub(r"^(Al|A1|Bl)-", "AI-", flight)
        code = re.match(r"([A-Z0-9]{2})-?\d", flight)
        code = code.group(1) if code else "6E"
        quotes.append(
            {
                "source": "CARRIER_DIRECT",
                "carrier_code": code,
                "carrier_name": CARRIER_NAMES.get(code, code),
                "origin_airport": fields.get("origin") or "DEL",
                "destination_airport": fields.get("destination") or "BOM",
                "travel_date": fields.get("travel_date") or reference_date,
                "flight_number": flight,
                "departure_time": fields.get("departure_time"),
                "arrival_time": fields.get("arrival_time"),
                "stops": fields.get("stops", 0),
                "duration_minutes": fields.get("duration_minutes"),
                "total_fare": float(price),
                "cabin_class": "ECONOMY",
                "fare_family": "BASIC",
                "feed_type": "CARRIER_DIRECT",
                "extraction_method": "OCR",
            }
        )
    return quotes


def run_day(
    extractor,
    origin: str,
    dest: str,
    travel_date: datetime.date,
    offset: int,
    persist: bool,
    db,
    force_vlm: bool = False,
) -> Dict[str, Any]:
    from services.extraction.adaptive_extractor import ExtractionContext

    os.makedirs(OUT_DIR, exist_ok=True)
    png = os.path.join(OUT_DIR, f"{origin}-{dest}_{travel_date.isoformat()}.png")
    cards = element_rects(fare_page_html(travel_date, offset), png)

    quotes = parse_cards(png, cards, travel_date.isoformat())

    # VLM fuse of the headline (cheapest) record on forced dates.
    vlm_chain = None
    if force_vlm:
        vlm_result = extractor.extract(
            ExtractionContext(dom_text=[], image_path=_downscale(png), reference_date=travel_date.isoformat()),
            force_vlm=True,
        )
        vlm_chain = "->".join(vlm_result.chain)
        if quotes:
            cheapest = min(quotes, key=lambda q: q["total_fare"])
            cheapest["extraction_method"] = vlm_result.extraction_method or "VLM"

    persisted = []
    if persist:
        from services.collectors.real_fare_normalizer import RealFareNormalizer

        persisted = RealFareNormalizer.normalize_and_persist_observations(
            db=db,
            raw_quotes=quotes,
            route_code=f"{origin}-{dest}",
            travel_date=travel_date,
            advance_days=offset,
        )

    methods: Dict[str, int] = {}
    for q in quotes:
        methods[q["extraction_method"]] = methods.get(q["extraction_method"], 0) + 1

    return {
        "date": travel_date.isoformat(),
        "cards": len(quotes),
        "complete": sum(1 for q in quotes if q["total_fare"] and q["flight_number"]),
        "methods": methods,
        "vlm_chain": vlm_chain,
        "persisted": len(persisted),
        "cheapest": min((q["total_fare"] for q in quotes), default=0.0),
    }


def main():
    parser = argparse.ArgumentParser(description="Multi-airline OCR + VLM end-to-end demo pipeline")
    parser.add_argument("--route", default="DEL-BOM", help="Route code, e.g. DEL-BOM")
    parser.add_argument("--days", type=int, default=28, help="Horizon in days (1..28)")
    parser.add_argument("--start-offset", type=int, default=0, help="First travel date offset")
    parser.add_argument("--vlm-every", type=int, default=7,
                        help="Run the (slow) local VLM on every N-th travel date (default 7)")
    parser.add_argument("--vlm-none", action="store_true",
                        help="Skip the VLM stage entirely; OCR-only extraction")
    parser.add_argument("--no-persist", action="store_true", help="Extract only, no DB writes")
    args = parser.parse_args()

    origin, dest = args.route.upper().split("-")
    days = min(max(args.days, 1), 28)
    today = datetime.date.today()

    if args.vlm_none:
        # Disable the VLM stage entirely (else the extractor still falls back to
        # it when OCR misses a field, loading the 0.9B model anyway).
        os.environ["EXTRACTION_ALLOW_VLM"] = "false"

    from services.extraction.adaptive_extractor import AdaptiveExtractor

    extractor = AdaptiveExtractor()  # allow_vlm/allow_ocr True (env set above)

    def is_vlm_day(offset: int) -> bool:
        return not args.vlm_none and ((offset - args.start_offset) % max(args.vlm_every, 1) == 0)

    db = None
    if not args.no_persist:
        from database.session import SessionLocal
        db = SessionLocal()

    print(f"\nMulti-airline OCR+VLM demo: {origin}-{dest} · horizon {days} days "
          f"(VLM every {args.vlm_every}. date) · airlines: {', '.join(f'{c} {n}' for c, n, _ in AIRLINES)}\n")
    print(f"{'Travel date':<12} | {'cards':<6} | {'methods':<16} | {'cheapest':<9} | {'persisted':<9} | VLM chain")
    print("-" * 100)

    rows: List[Dict[str, Any]] = []
    try:
        for offset in range(args.start_offset, args.start_offset + days):
            travel_date = today + datetime.timedelta(days=offset)
            force_vlm = is_vlm_day(offset)
            row = run_day(
                extractor, origin, dest, travel_date, offset,
                persist=not args.no_persist, db=db, force_vlm=force_vlm,
            )
            rows.append(row)
            marker = " " + row["vlm_chain"] if force_vlm and row["vlm_chain"] else ""
            print(
                f"{row['date']:<12} | {row['cards']:<6} | {str(row['methods']):<16} | "
                f"{row['cheapest']:>9,.0f} | {row['persisted']:<9} |{marker}"
            )
    finally:
        if db is not None:
            db.close()

    total_cards = sum(r["cards"] for r in rows)
    total_complete = sum(r["complete"] for r in rows)
    total_persisted = sum(r["persisted"] for r in rows)
    vlm_dates = [r["date"] for r in rows if "VLM" in r["methods"]]
    print("-" * 100)
    print(f"\nSummary: {len(rows)} travel dates · {total_cards} fare cards extracted "
          f"({total_complete} complete) · {total_persisted} persisted")
    print(f"   VLM-scored dates: {', '.join(vlm_dates) if vlm_dates else 'none'}")
    print(f"   screenshots in {OUT_DIR}")


if __name__ == "__main__":
    main()
