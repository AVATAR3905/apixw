"""Fault-injection tests for the OCR/VLM extraction chain.

Regression coverage for a real bug found and fixed in this pass: the adaptive
extractor's OCR and VLM stages only caught their own "not configured"
exceptions (``ExtractionNotAvailable`` / ``VLMNotConfigured``). A missing or
corrupt screenshot file -- entirely plausible on a live scraper (disk write
race, deleted mid-cleanup, unsupported format) -- raised an uncaught
``FileNotFoundError`` straight out of ``extract()``, which would have taken
down the whole carrier-scraper OCR fallback path in production.
"""

from services.extraction.adaptive_extractor import AdaptiveExtractor, ExtractionContext
from services.extraction.ocr_service import ExtractionNotAvailable, OCRService
from services.extraction.vlm_service import VLMNotConfigured, VLMService


class _AlwaysCrashesOCR(OCRService):
    """Stand-in for a live OCR engine crashing on a bad file."""

    def extract(self, image_path):
        raise FileNotFoundError(f"[Errno 2] No such file or directory: {image_path!r}")


class _AlwaysCrashesVLM(VLMService):
    """Stand-in for a VLM backend timing out / 5xx-ing mid-call."""

    def extract_fields(self, image_path, prompt, schema):
        raise TimeoutError("upstream vision backend did not respond in time")


class TestOCRStageCrashIsolation:
    def test_missing_screenshot_file_degrades_instead_of_crashing(self):
        extractor = AdaptiveExtractor(ocr=_AlwaysCrashesOCR(), allow_vlm=False, allow_ocr=True)
        result = extractor.extract(
            ExtractionContext(dom_text=[], image_path="/nonexistent/does_not_exist.png")
        )
        assert result.extraction_method == "NONE"
        assert result.fields == {}
        assert "OCR_SKIPPED" in result.chain

    def test_extraction_not_available_still_handled(self):
        """The original (narrower) exception path must keep working too."""

        class _NotInstalled(OCRService):
            def extract(self, image_path):
                raise ExtractionNotAvailable("paddleocr is not installed")

        extractor = AdaptiveExtractor(ocr=_NotInstalled(), allow_vlm=False, allow_ocr=True)
        result = extractor.extract(ExtractionContext(dom_text=[], image_path="/any/path.png"))
        assert result.extraction_method == "NONE"
        assert "OCR_SKIPPED" in result.chain


class TestVLMStageCrashIsolation:
    def test_vlm_backend_timeout_degrades_instead_of_crashing(self):
        # OCR resolves nothing (no image reachable via a working OCR stub),
        # forcing the VLM stage to be attempted, which then explodes.
        class _EmptyOCR(OCRService):
            def extract(self, image_path):
                return []

        extractor = AdaptiveExtractor(
            ocr=_EmptyOCR(), vlm=_AlwaysCrashesVLM(), allow_vlm=True, allow_ocr=True
        )
        result = extractor.extract(
            ExtractionContext(dom_text=[], image_path="/some/real-looking/screenshot.png")
        )
        assert result.extraction_method == "NONE"
        assert "VLM_SKIPPED" in result.chain

    def test_vlm_not_configured_still_handled(self):
        class _EmptyOCR(OCRService):
            def extract(self, image_path):
                return []

        class _Unconfigured(VLMService):
            def extract_fields(self, image_path, prompt, schema):
                raise VLMNotConfigured("no backend available")

        extractor = AdaptiveExtractor(
            ocr=_EmptyOCR(), vlm=_Unconfigured(), allow_vlm=True, allow_ocr=True
        )
        result = extractor.extract(ExtractionContext(dom_text=[], image_path="/any/path.png"))
        assert "VLM_SKIPPED" in result.chain


class TestDOMShortCircuitStillWins:
    def test_dom_price_present_skips_ocr_and_vlm_entirely(self):
        """When DOM already resolved a price, neither OCR nor VLM should even
        be attempted -- a crashing OCR/VLM backend must not matter at all in
        the (cheapest, most common) case where DOM already has the answer.
        """
        extractor = AdaptiveExtractor(
            ocr=_AlwaysCrashesOCR(), vlm=_AlwaysCrashesVLM(), allow_vlm=True, allow_ocr=True
        )
        result = extractor.extract(
            ExtractionContext(dom_text=["INR 5,499 DEL -> BOM 6E-101"], image_path="/x.png")
        )
        assert result.extraction_method == "DOM_BROWSER"
        assert result.chain == ["DOM"]
