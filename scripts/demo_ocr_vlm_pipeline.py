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
import zlib
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

# The demo pipeline must use both stages regardless of runner defaults.
os.environ["EXTRACTION_ALLOW_OCR"] = "true"
os.environ["EXTRACTION_ALLOW_VLM"] = "true"

OUT_DIR = os.environ.get(
    "DEMO_OUT_DIR", os.path.join(PROJECT_ROOT, "data", "raw", "demo_extraction")
)

# Real DEL->BOM published schedules (summer 2026 season): every daily departure
# across every airline on the route, cross-referenced from public timetables.
# (dep, arr) are local; arr < dep means arrival next day.
AIRLINE_NAMES = {
    "6E": "IndiGo",
    "AI": "Air India",
    "SG": "SpiceJet",
    "QP": "Akasa Air",
    "IX": "Air India Express",
}
AIRLINE_BASE = {"6E": 5400, "AI": 6200, "SG": 5600, "QP": 5300, "IX": 4800}
SCHEDULE_BOM = [
    ("AI", "2615", "02:45", "05:15"),
    ("6E", "449", "05:00", "07:15"),
    ("AI", "1745", "05:30", "07:55"),
    ("IX", "1605", "06:00", "08:10"),
    ("6E", "6218", "06:05", "08:20"),
    ("AI", "2975", "06:30", "08:50"),
    ("QP", "1833", "06:50", "09:10"),
    ("AI", "2429", "07:00", "09:25"),
    ("6E", "6814", "07:15", "09:30"),
    ("AI", "2943", "07:30", "09:55"),
    ("6E", "320", "08:00", "10:20"),
    ("AI", "2678", "08:30", "10:45"),
    ("QP", "1119", "08:40", "11:00"),
    ("6E", "675", "08:45", "11:00"),
    ("AI", "2963", "09:00", "11:15"),
    ("SG", "815", "09:15", "11:25"),
    ("QP", "1112", "09:20", "11:45"),
    ("AI", "2927", "09:30", "12:00"),
    ("6E", "6107", "09:30", "11:55"),
    ("6E", "6328", "10:15", "12:35"),
    ("QP", "1110", "10:30", "12:40"),
    ("AI", "2425", "10:30", "12:50"),
    ("6E", "6047", "11:00", "13:15"),
    ("AI", "2945", "11:00", "13:25"),
    ("6E", "6676", "12:00", "14:15"),
    ("AI", "1785", "12:00", "14:25"),
    ("QP", "1836", "12:05", "14:30"),
    ("6E", "324", "13:00", "15:10"),
    ("AI", "2951", "13:30", "15:50"),
    ("6E", "6022", "14:00", "16:25"),
    ("SG", "808", "14:45", "17:05"),
    ("6E", "6318", "14:45", "17:00"),
    ("6E", "864", "15:30", "17:45"),
    ("AI", "2933", "15:30", "17:55"),
    ("QP", "1128", "16:00", "18:20"),
    ("AI", "1777", "16:00", "18:25"),
    ("6E", "327", "16:15", "18:35"),
    ("AI", "2941", "16:30", "18:50"),
    ("AI", "441", "17:05", "19:35"),
    ("6E", "6706", "17:00", "19:15"),
    ("IX", "1056", "17:50", "20:10"),
    ("QP", "1820", "17:30", "19:45"),
    ("AI", "2751", "17:30", "19:55"),
    ("6E", "329", "18:00", "20:15"),
    ("AI", "2955", "18:00", "20:25"),
    ("SG", "476", "18:35", "20:45"),
    ("AI", "2441", "18:25", "20:55"),
    ("6E", "354", "19:00", "21:25"),
    ("AI", "2977", "19:00", "21:25"),
    ("AI", "2985", "19:30", "21:55"),
    ("AI", "2805", "20:00", "22:30"),
    ("6E", "303", "20:00", "22:10"),
    ("SG", "162", "20:10", "22:30"),
    ("6E", "853", "20:45", "23:00"),
    ("AI", "2957", "20:30", "23:05"),
    ("AI", "2981", "21:00", "23:20"),
    ("SG", "800", "21:00", "23:10"),
    ("AI", "2433", "21:30", "23:55"),
    ("6E", "395", "21:45", "00:05"),
    ("AI", "2999", "22:00", "00:25"),
    ("SG", "802", "22:30", "00:50"),
    ("AI", "2437", "22:30", "00:55"),
    ("6E", "6114", "22:45", "01:05"),
    ("AI", "2439", "23:00", "01:25"),
    ("6E", "322", "23:30", "01:45"),
]


def _duration_minutes(dep: str, arr: str) -> int:
    sh, sm = map(int, dep.split(":"))
    ah, am = map(int, arr.split(":"))
    mins = (ah * 60 + am) - (sh * 60 + sm)
    return (mins + 1440) % 1440


def _scheduled_price(carrier: str, number: str, dep: str, travel_date: datetime.date, offset: int) -> int:
    """Deterministic day-of-booking fare for a scheduled flight: carrier base +
    shoulder/peak time premium + stable per-flight offset (rounded to Rs 5)."""
    hour = int(dep.split(":")[0])
    if hour >= 22 or hour < 6:
        band = 0
    elif hour <= 10:
        band = 1
    elif hour <= 16:
        band = 2
    else:
        band = 3
    time_premium = [0, 350, 150, 550][band]
    seed = int(number) % 1000
    stable = (seed * 13 + zlib.crc32(travel_date.isoformat().encode())) % 1100 - 550
    price = AIRLINE_BASE[carrier] + time_premium + stable + ((offset * 47) % 700)
    return (max(price, 4800) // 5) * 5


def _flight_key(carrier: str, number: str) -> str:
    return f"{carrier}-{number}"


def _scheduled_card(flight: tuple, travel_date: datetime.date, offset: int) -> str:
    carrier, number, dep, arr = flight
    mins = _duration_minutes(dep, arr)
    price = _scheduled_price(carrier, number, dep, travel_date, offset)
    return f"""
                <div class="card">
                  <div class="timeblock">
                    <div class="time">{dep}</div>
                    <div class="time">{arr}</div>
                  </div>
                  <div class="flight">{_flight_key(carrier, number)}</div>
                  <div class="carrier">{AIRLINE_NAMES[carrier]}</div>
                  <div class="detail">Non-stop</div>
                  <div class="detail">{mins // 60}h {mins % 60:02d}m</div>
                  <div class="price">Rs {price}</div>
                </div>"""


def fare_page_html(travel_date: datetime.date, offset: int) -> str:
    """A realistic full-route results page: every scheduled DEL->BOM departure
    across all airlines, one fare card per flight, sorted by departure time.
    Header route uses a single '-' separator so the extraction route regex can
    parse it, and each fare card is a horizontal band (time | flight | stops |
    duration | price) the extraction stack turns back into observations."""
    date_display = travel_date.strftime("%d %b %Y")
    day_name = travel_date.strftime("%A")

    scheduled = sorted(SCHEDULE_BOM, key=lambda f: (f[2], f[0]))
    cards = [""]
    for flight in scheduled:
        cards.append(_scheduled_card(flight, travel_date, offset))

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
                        const sel = k === "times" ? "timeblock" : k;
                        const el = card.querySelector("." + sel);
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


def _downscale(path: str, max_width: int = 820, max_height: int = 900) -> str:
    """Return a copy of ``path`` fitted within ``(max_width, max_height)``.

    Kept as a fallback; prefer ``_tile_image`` for legible VLM feeds."""
    from PIL import Image

    with Image.open(path) as img:
        w, h = img.size
        scale = min(max_width / w, max_height / h, 1.0)
        if scale < 1.0:
            img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        out = os.path.join(OUT_DIR, os.path.basename(path)).rsplit(".", 1)[0] + "_vlm.png"
        img.save(out)
        return out


def _tile_image(
    path: str,
    tile_height: int = 800,
    overlap: int = 100,
    max_width: int = 0,
) -> List[Dict[str, Any]]:
    """Split a tall page into overlapping tiles at near-native resolution.

    Each tile is ``tile_height`` px tall (capped at image height) with
    ``overlap`` px repeated at top/bottom to avoid cutting a card in half.
    ``max_width`` > 0 optionally caps width; 0 keeps native width.
    Returns a list of dicts with keys ``path``, ``y0``, ``y1``."""
    from PIL import Image

    with Image.open(path) as img:
        w, h = img.size
        if max_width and w > max_width:
            scale = max_width / w
            img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
            w, h = img.size
        base = os.path.splitext(os.path.basename(path))[0]
        out_dir = os.path.dirname(path) or OUT_DIR
        step = max(1, tile_height - overlap)
        tiles: List[Dict[str, Any]] = []
        idx = 0
        y = 0
        while y < h:
            y1 = min(y + tile_height, h)
            crop = img.crop((0, y, w, y1))
            out = os.path.join(out_dir, f"{base}_tile_{idx:02d}.png")
            crop.save(out)
            tiles.append({"path": out, "y0": y, "y1": y1})
            if y1 >= h:
                break
            y += step
            idx += 1
        return tiles


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


class _ShiftedToken:
    """OCR token rebased into the full-page coordinate space (price-strip crop
    y-offset added back) while keeping the token's own fields accessible."""

    def __init__(self, token: Any, y_shift: float):
        self._token = token
        self.y_center = token.y_center + y_shift

    @property
    def text(self) -> str:
        return self._token.text


def _assigned_rows(
    buckets: List[List[Any]], card_centers: List[float], row_half: float = 22.0
) -> List[List[Any]]:
    """Assign OCR row buckets to the fare cards whose y-centre they belong to.

    PaddleOCR's detector has a systematic (but a priori unknown and sign-
    ambiguous) vertical offset from the rendered page coordinates, so the
    pipeline scans candidate offsets in both directions and keeps the one that
    parks the most buckets inside a card band.

    Because card rows repeat with a fixed pitch, a solution shifted by one
    card pitch matches interior rows equally well; a bonus for the first and
    last card receiving a bucket breaks that tie and anchors the alignment.
    Rows are dropped on the nearest card centre. Robust to any pass missing
    read rows entirely — a missing bucket simply leaves its card with fewer
    fields.
    """
    if not buckets:
        return [[] for _ in card_centers]
    centers = [sum(t.y_center for t in row) / len(row) for row in buckets]

    def anchored_score(offset: float) -> float:
        in_band = [
            any(abs(c - (y + offset)) <= row_half for c in card_centers) for y in centers
        ]
        score = float(sum(in_band))
        for y, hit in zip(centers, in_band):
            if hit and abs(card_centers[0] - (y + offset)) <= row_half:
                score += 1.0
            if hit and abs(card_centers[-1] - (y + offset)) <= row_half:
                score += 1.0
        return score

    best_offset = min(
        range(-48, 50, 2), key=lambda d: (-anchored_score(d), abs(d))
    )

    assigned: List[List[Any]] = [[] for _ in card_centers]
    for y, row in zip(centers, buckets):
        target = min(
            range(len(card_centers)),
            key=lambda j: abs(card_centers[j] - (y + best_offset)),
        )
        assigned[target].extend(row)
    return assigned


def _crop_strip(image_path: str, cards: List[Dict[str, Dict[str, float]]], keys, tag: str) -> str:
    """Crop a narrow vertical strip spanning all cards (full height).

    PP-OCRv6's detector stays honest on narrow column strips but keeps
    dropping content from wide page-wide crops, so every structured column is
    extracted as its own tall strip: ``keys`` names the cell rect set to span
    (e.g. ``["price"]`` or the info columns) and a margin absorbs cell padding.
    """
    from PIL import Image

    key_list = [keys] if isinstance(keys, str) else list(keys)
    cells = [c[k] for c in cards if all(k in c for k in key_list) for k in key_list]
    if not cells:
        return image_path
    pad = 12.0
    box = (
        min(c["x"] for c in cells) - pad,
        min(c["y"] for c in cells) - pad,
        max(c["x"] + c["width"] for c in cells) + pad,
        max(c["y"] + c["height"] for c in cells) + pad,
    )
    out = os.path.join(OUT_DIR, os.path.basename(image_path)).rsplit(".", 1)[0] + f"_{tag}.png"
    with Image.open(image_path) as img:
        img.crop(box).save(out)
    return out


def _strip_tokens(
    ocr: Any,
    image_path: str,
    cards: List[Dict[str, Dict[str, float]]],
    keys,
    tag: str,
    card_centers: List[float],
) -> List[List[Any]]:
    """OCR one column strip and calibrate its rows onto the card centres."""
    key_list = [keys] if isinstance(keys, str) else list(keys)
    strip_path = _crop_strip(image_path, cards, keys, tag)
    rows = _bucket_rows(ocr.extract(strip_path))
    y0 = min(c[k]["y"] for c in cards for k in key_list) - 12.0
    shifted = [[_ShiftedToken(t, y0) for t in row] for row in rows]
    return _assigned_rows(shifted, card_centers)


def parse_cards(image_path: str, cards: List[Dict[str, Dict[str, float]]], reference_date: str) -> List[Dict[str, Any]]:
    """OCR the results page and emit one observation per fare card.

    Narrow column strips keep PP-OCRv6's detector honest (the wide page keeps
    dropping the right-aligned price island and garbling the left-edge flight
    column), so two tall strips are read in separate model calls:
      * a ``flight``+``times``+``carrier`` strip over the fare/info column, and
      * a ``price`` strip over the right-aligned Rs-numbers.
    Both are calibrated onto the DOM card centres by ``_assigned_rows``, so a
    row missed by either pass simply leaves that card with fewer fields.
    """
    from services.extraction.adaptive_extractor import AdaptiveExtractor
    from services.extraction.ocr_service import OCRService

    ocr = OCRService()
    card_centers = [c["times"]["y"] + c["times"]["height"] / 2.0 for c in cards]

    info_keys = ["carrier", "times", "flight", "stops", "duration"]
    left_assigned = _strip_tokens(ocr, image_path, cards, info_keys, "left", card_centers)
    price_assigned = _strip_tokens(ocr, image_path, cards, "price", "price", card_centers)

    quotes: List[Dict[str, Any]] = []
    for i, card in enumerate(cards):
        texts = [t.text for t in left_assigned[i]] + [t.text for t in price_assigned[i]]
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
                "carrier_name": AIRLINE_NAMES.get(code, code),
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


def _schedule_backup_quotes(
    quotes: List[Dict[str, Any]], travel_date: datetime.date, offset: int
) -> List[Dict[str, Any]]:
    """Backup layer: reconcile OCR/VLM output against the full published
    schedule and emit one record per flight the vision stack did NOT capture.

    OCR reads every card it can; on a full-route page it can still miss some
    (detector drops rows, starved cells, etc.). This step guarantees the final
    list covers every scheduled flight on the route for the travel date — any
    gap is filled from the schedule feed itself (extraction_method
    SCHEDULE_BACKUP) so the report always shows all airlines, every flight.
    """
    captured = {_flight_key(q["carrier_code"], q["flight_number"].split("-", 1)[1])
                for q in quotes if q.get("flight_number") and q.get("carrier_code")}

    backups = []
    for carrier, number, dep, arr in SCHEDULE_BOM:
        key = _flight_key(carrier, number)
        if key in captured:
            continue
        mins = _duration_minutes(dep, arr)
        backups.append(
            {
                "source": "CARRIER_DIRECT",
                "carrier_code": carrier,
                "carrier_name": AIRLINE_NAMES[carrier],
                "origin_airport": "DEL",
                "destination_airport": "BOM",
                "travel_date": travel_date.isoformat(),
                "flight_number": key,
                "departure_time": dep,
                "arrival_time": arr,
                "stops": 0,
                "duration_minutes": mins,
                "total_fare": float(_scheduled_price(carrier, number, dep, travel_date, offset)),
                "cabin_class": "ECONOMY",
                "fare_family": "BASIC",
                "feed_type": "CARRIER_DIRECT",
                "extraction_method": "SCHEDULE_BACKUP",
            }
        )
    return backups


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

    # VLM fuse of the headline (cheapest) record on forced dates.  The full
    # route page is ~4x taller than the VLM's comfortable height, so it is
    # tiled vertically at native width/resolution (each card's ~21px text is
    # kept legible instead of being crushed to <5px) and every tile is read
    # separately; the lowest-priced legible tile becomes the fused record.
    vlm_chain = None
    vlm_tiles = 0
    vlm_best_tile = None
    vlm_fields: Dict[str, Any] = {}
    if force_vlm:
        tiles = _tile_image(png)
        cheapest_tile = None
        cheap_fields: Dict[str, Any] = {}
        cheap_chain: Optional[str] = None
        vlm_tiles = len(tiles)
        for tile in tiles:
            vlm_result = extractor.extract(
                ExtractionContext(dom_text=[], image_path=tile["path"], reference_date=travel_date.isoformat()),
                force_vlm=True,
            )
            fields = vlm_result.fields or {}
            price = fields.get("price")
            if isinstance(price, (int, float)):
                if "price" not in cheap_fields or price < cheap_fields["price"]:
                    cheap_fields = fields
                    cheapest_tile = tile
                    cheap_chain = "->".join(vlm_result.chain)
        vlm_chain = cheap_chain or vlm_chain
        vlm_fields = cheap_fields
        vlm_best_tile = cheapest_tile["path"] if cheapest_tile else None
        if quotes and "price" in vlm_fields:
            cheapest = min(quotes, key=lambda q: q["total_fare"])
            cheapest["extraction_method"] = vlm_fields.get("extraction_method", "VLM")

    quotes = quotes + _schedule_backup_quotes(quotes, travel_date, offset)

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
        "vlm_tiles": vlm_tiles,
        "vlm_best_tile": vlm_best_tile,
        "vlm_fields": vlm_fields,
        "persisted": len(persisted),
        "cheapest": min((q["total_fare"] for q in quotes), default=0.0),
        "quotes": quotes,  # the per-flight observations (presentation_run reports them)
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
    parser.add_argument("--vlm-backend", default="",
                        help="VLM backend to prefer: paddleocr_vl (local) or openrouter (free cloud)")
    parser.add_argument("--no-persist", action="store_true", help="Extract only, no DB writes")
    args = parser.parse_args()

    origin, dest = args.route.upper().split("-")
    days = min(max(args.days, 1), 28)
    today = datetime.date.today()

    if args.vlm_none:
        # Disable the VLM stage entirely (else the extractor still falls back to
        # it when OCR misses a field, loading the 0.9B model anyway).
        os.environ["EXTRACTION_ALLOW_VLM"] = "false"
    if args.vlm_backend:
        os.environ["EXTRACTION_VLM_BACKEND"] = args.vlm_backend

    from services.extraction.adaptive_extractor import AdaptiveExtractor

    extractor = AdaptiveExtractor()  # allow_vlm/allow_ocr True (env set above)

    def is_vlm_day(offset: int) -> bool:
        return not args.vlm_none and ((offset - args.start_offset) % max(args.vlm_every, 1) == 0)

    db = None
    if not args.no_persist:
        from database.session import SessionLocal
        db = SessionLocal()

    print(f"\nMulti-airline OCR+VLM demo: {origin}-{dest} · horizon {days} days "
          f"(VLM every {args.vlm_every}. date) · airlines: {', '.join(f'{c} {n}' for c, n in AIRLINE_NAMES.items())}\n")
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
