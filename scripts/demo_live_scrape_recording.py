#!/usr/bin/env python3
"""Live, on-camera demo of the real scrape -> screenshot -> OCR pipeline.

Two source modes, both opening a VISIBLE Chromium window against a real
site and ALWAYS running the real OCR extraction on a real screenshot in
addition to whatever structured extraction finds -- so the recording always
has genuine OCR output to show, regardless of which path the production
degrade-chain would actually have used:

  --source carrier (default): SpiceJet's real deep-link results page (the
      only carrier whose URL is verified in this codebase to load real
      results rather than a landing/selection page). Structured extraction
      here is real network-JSON interception; OCR runs on the same real
      screenshot but this codebase's card-detection heuristics were tuned
      for OTA aggregator layouts, not SpiceJet's own page, so it will
      typically find 0 cards here even on a real fare-containing page --
      that's a real, honestly-reported limitation, not a bug.

  --source ota: EaseMyTrip's real interactive search (fills the real city
      autocomplete fields, picks a real calendar date, clicks real search --
      "verified live: real IndiGo/Air India Express flights and prices
      rendered straight into the DOM", per the scraper's own docstring).
      This is the layout OCR's card-detection was actually tuned against,
      so it's the mode that reliably shows OCR extracting real cards.

Nothing here is faked, pre-rendered, or replayed. Nothing is persisted to
the production database by default (pass --persist to opt in); raw
payloads/screenshots land under --out-dir, not the scrapers' normal
data/raw/live/* locations.

Usage:
    python scripts/demo_live_scrape_recording.py --source carrier
    python scripts/demo_live_scrape_recording.py --source ota
    python scripts/demo_live_scrape_recording.py --source ota --route DEL-BOM --advance-days 7
    python scripts/demo_live_scrape_recording.py --no-open
"""

import argparse
import asyncio
import datetime
import json
import os
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

GREEN, CYAN, GREY, YELLOW, BOLD, RESET = "\033[92m", "\033[96m", "\033[90m", "\033[93m", "\033[1m", "\033[0m"
_t0 = time.time()


def _log(stage: str, *lines: str):
    print(f"\n{BOLD}{CYAN}== {stage} =={RESET}  {GREY}+{time.time() - _t0:.0f}s{RESET}")
    for line in lines:
        print(f"    {line}")


def _open(path: str):
    try:
        os.startfile(path)  # noqa: S606 -- Windows-only demo helper, local files only
    except Exception as e:
        print(f"    {YELLOW}(could not auto-open {path}: {e}){RESET}")


async def _run_carrier_demo(args) -> dict:
    from packages.shared.config import settings

    settings.BROWSE_HEADLESS = False
    settings.SCRAPE_MODE = "live"

    from playwright.async_api import async_playwright

    from services.collectors.carrier_direct_scraper import (
        _BLOCK_PAGE_MARKERS,
        _CARRIER_SEARCH_URLS,
        _ROBOTS_CHECKER,
        CarrierDirectScraper,
    )
    from services.collectors.ota.card_extraction import extract_cards_from_screenshot

    origin, dest = args.route.upper().split("-")
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    scraper = CarrierDirectScraper(raw_dir=out_dir)
    today = datetime.date.today()
    travel_date = today + datetime.timedelta(days=args.advance_days)
    travel_date_str = travel_date.isoformat()
    target_url = _CARRIER_SEARCH_URLS.get(args.carrier, _CARRIER_SEARCH_URLS["SG"])(
        origin, dest, travel_date_str
    )

    _log(
        "1. LAUNCH BROWSER (visible)",
        f"Carrier:  {args.carrier} ({scraper._carrier_name(args.carrier)})",
        f"Route:    {origin} -> {dest}",
        f"Travel date: {travel_date_str} (T+{args.advance_days})",
        f"Target URL: {target_url}",
        "A real Chromium window will open now and navigate to the live site...",
    )

    if not _ROBOTS_CHECKER.can_fetch(target_url):
        _log("STOPPED", f"robots.txt disallows {target_url}; refusing to scrape.")
        return {"error": "robots_disallowed", "target_url": target_url}

    structured_quotes = []
    ocr_quotes = []
    screenshot_path = os.path.join(
        out_dir, f"screenshot_{args.carrier}_{origin}_{dest}_{travel_date_str}.png"
    )
    blocked = False
    api_responses = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"],
        )
        try:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            async def handle_response(res):
                try:
                    ct = res.headers.get("content-type", "")
                    if "json" in ct and res.request.resource_type in ("xhr", "fetch"):
                        api_responses.append({"url": res.url, "body": await res.json()})
                except Exception:
                    pass

            page.on("response", handle_response)
            _log("2. NAVIGATE", f"Loading {target_url} ...")
            resp = await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(4000)

            if resp is not None and resp.status in (403, 429, 503):
                blocked = True
            else:
                body_lower = (await page.inner_text("body"))[:4000].lower()
                if any(marker in body_lower for marker in _BLOCK_PAGE_MARKERS):
                    blocked = True

            if blocked:
                _log("STOPPED", "Bot-challenge / block page detected -- refusing to extract or screenshot.")
            else:
                _log("3. SCREENSHOT", "Capturing the real, currently-loaded results page...")
                await page.screenshot(path=screenshot_path, full_page=True)

                if args.carrier == "SG":
                    structured_quotes = scraper._parse_spicejet_availability(
                        api_responses, origin, dest, travel_date_str, args.advance_days
                    )
                else:
                    structured_quotes = await scraper._extract_generic_dom_prices(
                        page, args.carrier, origin, dest, travel_date_str, args.advance_days
                    )
                    if not structured_quotes:
                        structured_quotes = scraper._extract_generic_json_prices(
                            api_responses, args.carrier, origin, dest, travel_date_str, args.advance_days
                        )

                _log(
                    "4. STRUCTURED EXTRACTION (network-JSON / DOM)",
                    f"{len(structured_quotes)} quote(s) found this way."
                    if structured_quotes
                    else "Nothing found this way on this run.",
                )

                _log("5. OCR EXTRACTION (on the same real screenshot)", "Running PaddleOCR...")
                cards = extract_cards_from_screenshot(
                    image_path=screenshot_path, reference_date=travel_date_str, allow_vlm=False
                )
                for card in cards:
                    price = card.get("price")
                    if not price:
                        continue
                    ocr_quotes.append(
                        {
                            "carrier_code": args.carrier,
                            "flight_number": card.get("flight_number") or "?",
                            "departure_time": card.get("departure_time"),
                            "arrival_time": card.get("arrival_time"),
                            "total_fare": float(price),
                            "extraction_method": card.get("_extraction_method", "OCR"),
                        }
                    )
                _log("5. OCR EXTRACTION (on the same real screenshot)", f"{len(ocr_quotes)} card(s) extracted.")
        finally:
            await browser.close()

    return {
        "target_url": target_url,
        "blocked": blocked,
        "screenshot_path": screenshot_path if os.path.exists(screenshot_path) else None,
        "structured_quotes": structured_quotes,
        "ocr_quotes": ocr_quotes,
        "carrier": args.carrier,
        "carrier_name": scraper._carrier_name(args.carrier),
        "origin": origin,
        "dest": dest,
        "travel_date": travel_date_str,
        "advance_days": args.advance_days,
    }


def _run_ota_demo(args) -> dict:
    from packages.shared.config import settings

    settings.BROWSE_HEADLESS = False

    from playwright.sync_api import sync_playwright

    from services.collectors.ota.card_extraction import (
        extract_cards_from_dom,
        extract_cards_from_screenshot,
    )
    from services.collectors.ota.easemytrip_scraper import EaseMyTripScraper

    origin, dest = args.route.upper().split("-")
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    scraper = EaseMyTripScraper()
    today = datetime.date.today()
    travel_date = today + datetime.timedelta(days=args.advance_days)
    travel_date_str = travel_date.isoformat()
    from services.collectors.ota.easemytrip_scraper import _EMT_CITY_NAMES

    origin_name = _EMT_CITY_NAMES.get(origin.upper())
    dest_name = _EMT_CITY_NAMES.get(dest.upper())
    target_url = "https://www.easemytrip.com/"

    _log(
        "1. LAUNCH BROWSER (visible)",
        f"Source:   EaseMyTrip (OTA)",
        f"Route:    {origin} -> {dest}",
        f"Travel date: {travel_date_str} (T+{args.advance_days})",
        f"Target URL: {target_url}",
        "A real Chromium window will open, fill the real search form, and click search...",
    )

    if not origin_name or not dest_name:
        _log("STOPPED", f"No verified city name mapping for {origin}/{dest} on EaseMyTrip.")
        return {"error": "unmapped_route", "target_url": target_url}

    structured_quotes, ocr_quotes = [], []
    screenshot_path = os.path.join(out_dir, f"screenshot_EMT_{origin}_{dest}_{travel_date_str}.png")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, args=["--disable-blink-features=AutomationControlled"]
        )
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 1000},
            )
            page = context.new_page()
            _log("2. NAVIGATE", f"Loading {target_url} ...")
            page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2500)

            _log("3. FILL SEARCH FORM", f"From: {origin_name}  To: {dest_name}  Date: {travel_date_str}")
            if not scraper._fill_emt_city(page, "#FromSector_show", "#frmcity", origin, origin_name):
                _log("STOPPED", "Could not fill the FROM field (site layout may have changed).")
                return {"error": "form_fill_failed", "target_url": target_url}
            if not scraper._fill_emt_city(page, "#Editbox13_show", "#tocity", dest, dest_name):
                _log("STOPPED", "Could not fill the TO field (site layout may have changed).")
                return {"error": "form_fill_failed", "target_url": target_url}

            page.locator("#ddate").click()
            page.wait_for_timeout(800)
            if not scraper._click_emt_calendar_date(page, travel_date):
                _log("STOPPED", "Could not pick the travel date on the calendar.")
                return {"error": "calendar_pick_failed", "target_url": target_url}
            page.wait_for_timeout(500)

            _log("4. SEARCH", "Clicking the real search button...")
            page.locator(".srchBtnSe").click()
            page.wait_for_timeout(13000)

            _log("5. SCREENSHOT", "Capturing the real, currently-loaded results page...")
            page.screenshot(path=screenshot_path, full_page=True)

            structured_cards = extract_cards_from_dom(page, "div.nw_listing_bx", travel_date_str)
            structured_quotes = scraper._to_raw_quotes(
                structured_cards, origin, dest, travel_date, args.advance_days, "DOM_BROWSER"
            )
            _log(
                "6. STRUCTURED EXTRACTION (real DOM)",
                f"{len(structured_quotes)} quote(s) found this way."
                if structured_quotes
                else "Nothing found this way on this run.",
            )

            _log("7. OCR EXTRACTION (on the same real screenshot)", "Running PaddleOCR...")
            ocr_cards = extract_cards_from_screenshot(screenshot_path, travel_date_str)
            ocr_quotes = scraper._to_raw_quotes(
                ocr_cards, origin, dest, travel_date, args.advance_days, "OCR"
            )
            _log("7. OCR EXTRACTION (on the same real screenshot)", f"{len(ocr_quotes)} card(s) extracted.")
        finally:
            browser.close()

    return {
        "target_url": target_url,
        "blocked": False,
        "screenshot_path": screenshot_path if os.path.exists(screenshot_path) else None,
        "structured_quotes": structured_quotes,
        "ocr_quotes": ocr_quotes,
        "carrier": "EMT",
        "carrier_name": "EaseMyTrip",
        "origin": origin,
        "dest": dest,
        "travel_date": travel_date_str,
        "advance_days": args.advance_days,
    }


def _print_quotes(label, quotes):
    print(f"    {label}: {len(quotes)} quote(s)")
    for q in quotes[:10]:
        print(
            f"      {str(q.get('flight_number','?')):>10}  "
            f"{str(q.get('departure_time') or '?'):>5} -> {str(q.get('arrival_time') or '?'):>5}  "
            f"Rs.{q.get('total_fare','?')}  [{q.get('extraction_method')}]"
        )


def main():
    parser = argparse.ArgumentParser(description="Live scrape + screenshot + OCR demo")
    parser.add_argument(
        "--source", default="carrier", choices=["carrier", "ota"],
        help="carrier = SpiceJet real deep-link results page (structured extraction works, "
             "OCR usually finds 0 here -- untuned layout). ota = EaseMyTrip real interactive "
             "search (the layout OCR's card-detection was actually tuned against).",
    )
    parser.add_argument(
        "--carrier", default="SG", choices=["SG", "6E", "AI", "IX"],
        help="Only used with --source carrier. Default SG/SpiceJet -- the only deep-link URL "
             "verified in this codebase to load real results rather than a search form.",
    )
    parser.add_argument("--route", default="DEL-BOM", help="ORIGIN-DEST airport codes")
    parser.add_argument("--advance-days", type=int, default=15)
    parser.add_argument("--out-dir", default=os.path.expanduser("~/Downloads/APIx Live Scrape Demo"))
    parser.add_argument("--persist", action="store_true", help="Write structured results into the real database")
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open results when done")
    args = parser.parse_args()

    if args.source == "ota":
        result = _run_ota_demo(args)
    else:
        result = asyncio.run(_run_carrier_demo(args))

    if result.get("error"):
        print(f"\n{YELLOW}Stopped: {result['error']} ({result.get('target_url')}){RESET}\n")
        return

    _log("6. RESULTS")
    _print_quotes("Structured extraction (network-JSON/DOM)", result["structured_quotes"])
    _print_quotes("OCR extraction (screenshot)", result["ocr_quotes"])

    if args.persist and result["structured_quotes"] and args.source == "carrier":
        from database.session import SessionLocal
        from services.collectors.carrier_direct_scraper import CarrierDirectScraper

        db = SessionLocal()
        try:
            scraper = CarrierDirectScraper(raw_dir=args.out_dir)
            scraper._store_raw_payload(
                db, result["structured_quotes"], result["carrier"], result["origin"],
                result["dest"], result["travel_date"],
            )
            db.commit()
        finally:
            db.close()
    elif args.persist and args.source == "ota":
        print(f"    {YELLOW}(--persist isn't wired up for --source ota in this demo script; "
              f"results were extracted but not saved to the database){RESET}")

    out_dir = args.out_dir
    report_path = os.path.join(out_dir, "live_scrape_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Live Carrier Scrape + Screenshot + OCR Demo\n\n")
        f.write(f"- **Carrier**: {result['carrier']} ({result['carrier_name']})\n")
        f.write(f"- **Route**: {result['origin']} -> {result['dest']}\n")
        f.write(f"- **Travel date**: {result['travel_date']} (T+{result['advance_days']})\n")
        f.write(f"- **Target URL**: {result['target_url']}\n")
        f.write(f"- **Run at**: {datetime.datetime.now().isoformat(timespec='seconds')}\n")
        if result["screenshot_path"]:
            f.write(f"- **Screenshot**: `{result['screenshot_path']}`\n")
        f.write("\n## Structured extraction (network-JSON / DOM parsing)\n\n")
        f.write("| Flight | Departure | Arrival | Fare (INR) | Method |\n|---|---|---|---|---|\n")
        for q in result["structured_quotes"]:
            f.write(
                f"| {q.get('flight_number','?')} | {q.get('departure_time','?')} | "
                f"{q.get('arrival_time') or '?'} | {q.get('total_fare','?')} | {q.get('extraction_method')} |\n"
            )
        f.write("\n## OCR extraction (same real screenshot)\n\n")
        f.write("| Flight | Departure | Arrival | Fare (INR) | Method |\n|---|---|---|---|---|\n")
        for q in result["ocr_quotes"]:
            f.write(
                f"| {q.get('flight_number','?')} | {q.get('departure_time') or '?'} | "
                f"{q.get('arrival_time') or '?'} | {q.get('total_fare','?')} | {q.get('extraction_method')} |\n"
            )
        f.write("\n## Raw records (JSON)\n\n```json\n")
        f.write(json.dumps(
            {"structured": result["structured_quotes"], "ocr": result["ocr_quotes"]}, indent=2, default=str
        ))
        f.write("\n```\n")

    _log("7. REPORT", f"Written to: {report_path}")

    if not args.no_open:
        _log("8. OPENING RESULTS")
        if result["screenshot_path"]:
            _open(result["screenshot_path"])
            time.sleep(1)
        _open(report_path)

    print(f"\n{GREEN}{BOLD}Done in {time.time() - _t0:.0f}s.{RESET} Output folder: {out_dir}\n")


if __name__ == "__main__":
    main()
