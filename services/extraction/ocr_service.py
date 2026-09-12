"""OCR extraction service (PP-OCRv5 first, neutral fallback).

paddleocr / paddlepaddle are optional heavyweight dependencies: import them
lazily and degrade to a clear ``ExtractionNotAvailable`` when absent so the
rest of the pipeline stays runnable in plain dev environments.
"""

import logging
from typing import List

from services.extraction.layout_clusterer import (
    OCRToken,
    token_from_ocr_line,
    tokens_from_paddle_result,
)

logger = logging.getLogger(__name__)


class ExtractionNotAvailable(Exception):
    """Raised when no OCR engine can be provisioned."""


class OCRService:
    """Thin wrapper over PP-OCR that returns geometry-aware OCR tokens."""

    def __init__(self, engine: str = "paddle", language: str = "en"):
        self.engine = engine
        self.language = language
        self._ocr = None

    def supports(self) -> bool:
        try:
            import paddleocr  # noqa: F401

            return True
        except ImportError:
            return False

    def _load_engine(self):
        if self._ocr is not None:
            return self._ocr
        try:
            from paddleocr import PaddleOCR

            if self._v3():
                # PaddleOCR 3.x: PP-OCRv5/v6 pipelines; CPU oneDNN path can
                # crash on some paddle builds, so keep it off (slightly slower,
                # deterministic).
                self._ocr = PaddleOCR(lang=self.language, enable_mkldnn=False)
            else:
                self._ocr = PaddleOCR(use_angle_cls=True, lang=self.language, show_log=False)
            return self._ocr
        except ImportError as e:
            raise ExtractionNotAvailable(
                "paddleocr is not installed. Run `pip install paddleocr paddlepaddle` first."
            ) from e

    @staticmethod
    def _v3() -> bool:
        import paddleocr

        try:
            major = int(paddleocr.__version__.split(".")[0])
        except (AttributeError, ValueError):
            major = 2
        return major >= 3

    def extract(self, image_path: str) -> List[OCRToken]:
        """Run OCR on an image file and return geometry-aware OCRTokens."""
        engine = self._load_engine()
        tokens: List[OCRToken] = []
        if self._v3():
            results = engine.predict(image_path)
            for result in results or []:
                res = (result.json or {}).get("res") if hasattr(result, "json") else {}
                if res:
                    tokens.extend(tokens_from_paddle_result(res))
        else:
            legacy = engine.ocr(image_path, cls=True)
            for page in legacy or []:
                if not page:
                    continue
                tokens.extend(token_from_ocr_line(line) for line in page)
        logger.info("OCR extracted %d tokens from %s", len(tokens), image_path)
        return tokens

    def cards(self, image_path: str):
        from services.extraction.layout_clusterer import LayoutClusterer

        return LayoutClusterer.cards(self.extract(image_path))


def supports_ocr() -> bool:
    return OCRService().supports()
