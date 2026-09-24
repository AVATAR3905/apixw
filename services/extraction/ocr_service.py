"""OCR extraction service (PP-OCRv5 first, neutral fallback).

paddleocr / paddlepaddle are optional heavyweight dependencies: import them
lazily and degrade to a clear ``ExtractionNotAvailable`` when absent so the
rest of the pipeline stays runnable in plain dev environments.
"""

import logging
import os
import shutil
import subprocess
from typing import List

from services.extraction.layout_clusterer import (
    OCRToken,
    token_from_ocr_line,
    tokens_from_paddle_result,
    tokens_from_tesseract_tsv,
)

logger = logging.getLogger(__name__)

# In-process memo of OCR results keyed by (abs path, mtime). PP-OCR loads and
# runs are the pipeline's slowest stage, and several callers OCR the *same*
# strip images (parse pass, then presentation annotation). Deduplicating those
# repeated reads cuts a presentation run from ~10+ min to the single real pass.
_token_cache: dict = {}


class ExtractionNotAvailable(Exception):
    """Raised when no OCR engine can be provisioned."""


def _cache_key(image_path: str):
    abspath = os.path.abspath(image_path)
    try:
        mtime = os.stat(abspath).st_mtime
    except OSError:
        mtime = -1.0
    return (abspath, mtime)


class OCRService:
    """Thin wrapper over PP-OCR that returns geometry-aware OCR tokens."""

    def __init__(self, engine: str = "paddle", language: str = "en"):
        self.engine = engine
        self.language = language
        self._ocr = None

    def supports(self) -> bool:
        # Probe the *configured* backend exactly like paddleocr is probed: the
        # rung is only reportable when its engine can actually be provisioned.
        if self.engine == "tesseract":
            return shutil.which("tesseract") is not None
        try:
            import paddleocr  # noqa: F401

            return True
        except ImportError:
            return False

    @staticmethod
    def _load_tesseract(language: str, psm: str | None = None):
        """Provision a lazy tesseract CLI handle (v4/v5 TSV word geometry)."""
        binary = shutil.which("tesseract")
        if binary is None:
            raise ExtractionNotAvailable(
                "tesseract is not on PATH. Install tesseract-ocr (e.g. "
                "`apt install tesseract-ocr tesseract-ocr-eng`) or set "
                "EXTRACTION_OCR_BACKEND=paddle."
            )
        return {"binary": binary, "language": language, "psm": psm}

    def _load_engine(self):
        if self._ocr is not None:
            return self._ocr
        if self.engine == "tesseract":
            return self._load_tesseract(self.language)
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
        """Run OCR on an image file and return geometry-aware OCRTokens.

        Results are memoized per file (path + mtime) so repeat reads of the same
        image — e.g. the pipeline pass and the presentation annotation pass —
        reuse the first expensive inference instead of re-running PP-OCR.
        """
        key = _cache_key(image_path)
        cached = _token_cache.get(key)
        if cached is not None:
            logger.info("OCR cache hit for %s (%d tokens)", image_path, len(cached))
            return cached

        engine = self._load_engine()
        tokens: List[OCRToken] = []
        if self.engine == "tesseract":
            tokens = self._tesseract_run(engine, image_path)
        elif self._v3():
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
        _token_cache[key] = list(tokens)
        return tokens

    @staticmethod
    def _tesseract_run(handle: dict, image_path: str) -> List[OCRToken]:
        """Run the provisioned tesseract CLI in TSV mode; map TSV to geoTokens.

        ``handle`` is the ``{"binary", "language", "psm"}`` dict from
        ``_load_tesseract``. Word rows carry their own pixel geometry, so no
        per-page coordinate transform is needed — same neutral contract the
        paddle rungs emit, so the clusterer and OCR→VLM ladder never see a
        second token shape.
        """
        cmd = [
            handle["binary"],
            image_path,
            "stdout",
            "tsv",
            "-l",
            handle["language"],
            "--psm",
            str(handle.get("psm") or 3),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise ExtractionNotAvailable(
                "tesseract failed on %s: %s", image_path, (proc.stderr or "").strip()
            ) from subprocess.SubprocessError(proc.stderr or "")
        return tokens_from_tesseract_tsv(proc.stdout)

    def cards(self, image_path: str):
        from services.extraction.layout_clusterer import LayoutClusterer

        return LayoutClusterer.cards(self.extract(image_path))


def supports_ocr() -> bool:
    return OCRService().supports()
