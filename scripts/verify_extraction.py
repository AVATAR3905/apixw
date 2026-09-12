"""Watch the OCR + VLM extraction pipeline in action, step by step.

This renders a synthetic fare card (or takes an existing screenshot), then runs
each live stage and prints what it sees:

    python scripts/verify_extraction.py                 # rendered demo card
    python scripts/verify_extraction.py --image X.png   # your own screenshot
    python scripts/verify_extraction.py --open          # pop the image in your viewer

Stage 1  OCR  : PP-OCRv5/v6 inference -> per-token text + confidence + geometry
Stage 2  Cards: geometry clustering groups tokens into fare cards
Stage 3  Fields: deterministic parse of OCR text (price + route)
Stage 4  VLM  : PaddleOCR-VL-1.6 vision model -> structured markdown + fields
Stage 5  Chain: which method won (DOM > OCR > VLM) + confidence for downstream use

The first run downloads model weights (~minutes); later runs use the cache.
"""

import argparse
import html
import json
import os
import sys
import tempfile
import time

from PIL import Image, ImageDraw, ImageFont

from services.extraction.adaptive_extractor import AdaptiveExtractor, ExtractionContext
from services.extraction.layout_clusterer import LayoutClusterer
from services.extraction.ocr_service import OCRService, supports_ocr
from services.extraction.vlm_service import (
    _PaddleOCRVLBackend,
    supports_vlm,
)

OUT_DIR = os.environ.get("EXTRACT_VERIFY_DIR") or os.path.join(tempfile.gettempdir(), "opencode")
os.makedirs(OUT_DIR, exist_ok=True)
DEMO_IMAGE = os.path.join(OUT_DIR, "extraction_verify_farecard.png")


def render_farecard(path: str) -> str:
    img = Image.new("RGB", (640, 360), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
    draw.rectangle([30, 30, 610, 330], outline="black", width=2)
    draw.text((60, 70), "DEL -> BOM", fill="black", font=font)
    draw.text((60, 130), "IndiGo 6E-204", fill="black", font=font)
    draw.text((60, 190), "INR 4,250", fill="black", font=font)
    draw.text((60, 250), "Dept 06:40 Arr 08:55", fill="black", font=font)
    img.save(path)
    return path


def line() -> None:
    print("-" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch OCR + VLM extraction live.")
    parser.add_argument("--image", default=None, help="run on your own screenshot")
    parser.add_argument("--open", action="store_true", help="open the image in a viewer")
    args = parser.parse_args()

    print("engine availability:", {"OCR": supports_ocr(), "VLM": supports_vlm()})

    image = args.image or render_farecard(DEMO_IMAGE)
    if args.open:
        try:
            os.startfile(image)  # noqa: S606 - intentional user-facing demo
            print(f"opened image in your viewer: {image}")
        except OSError as e:
            print(f"(could not auto-open image: {e})")

    # ------------------------------------------------------------------ STAGE 1
    line()
    print("STAGE 1 - OCR inference (PP-OCRv5/v6)")
    print(f"  input: {image}")
    t0 = time.time()
    tokens = OCRService().extract(image)
    print(f"  {len(tokens)} tokens in {time.time() - t0:.1f}s:")
    for t in tokens:
        print(f"    {t.text!r:<40} conf={t.score:.3f} bbox={t.bbox}")

    # ------------------------------------------------------------------ STAGE 2
    line()
    print("STAGE 2 - geometry clustering -> fare cards")
    cards = LayoutClusterer.cards(tokens)
    for c in cards:
        print(f"  card #{c['card_index']}  y={c['y_center']:.0f}  text={c['text']!r}")

    # ------------------------------------------------------------------ STAGE 3
    line()
    print("STAGE 3 - deterministic field parse (price, route)")
    ocr_fields = AdaptiveExtractor.fields_from_tokens(tokens)
    print(f"  fields from OCR: {json.dumps(ocr_fields)}")

    # ------------------------------------------------------------------ STAGE 5a
    line()
    print("STAGE 5a - adaptive chain (DOM -> OCR -> VLM)")
    t0 = time.time()
    adaptive = AdaptiveExtractor().extract(ExtractionContext(image_path=image, dom_text=[]))
    print(
        f"  chain={adaptive.chain}  extraction_method={adaptive.extraction_method}  "
        f"in {time.time() - t0:.1f}s"
    )
    print(f"  fields={json.dumps(adaptive.fields)}  confidence={adaptive.confidence}")

    # ------------------------------------------------------------------ STAGE 4
    line()
    print("STAGE 4 - PaddleOCR-VL-1.6 vision model (markdown -> fields)")
    backend = _PaddleOCRVLBackend()
    t0 = time.time()
    blob = backend._text_of(image)
    elapsed = time.time() - t0
    print(f"  inference done in {elapsed:.1f}s")
    size = 320
    print(
        "  markdown excerpt (raw model output): "
        + html.unescape(blob.replace("\n", " | ")[:size])
        + ("..." if len(blob) > size else "")
    )
    vlm_fields = backend._parse_fields(blob)
    print(f"  fields parsed from VLM: {json.dumps(vlm_fields)}")

    # ------------------------------------------------------------------ STAGE 5b
    line()
    print("STAGE 5b - verdict")
    resolved = {**ocr_fields, **vlm_fields}
    price_ok = resolved.get("price") is not None
    route_ok = resolved.get("origin") and resolved.get("destination")
    winner = adaptive.extraction_method if adaptive.fields else "NONE"
    print(
        f"  price={price_ok} route={route_ok}; pipeline winner: {winner} "
        f"(conf={adaptive.confidence})"
    )
    ok = supports_ocr() and supports_vlm() and price_ok
    print("\nRESULT:", "PASS - OCR + VLM extraction chain live" if ok else "FAIL")
    print(
        "tip: chain shows when VLM actually fires - only when OCR/DOM "
        "leave price *or* route unresolved."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
