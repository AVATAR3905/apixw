"""Vision-language extraction backend (PaddleOCR-VL / OpenRouter).

PaddleOCR-VL-1.6 (0.9B) is the preferred visual backend for raw fare-card
semantics; OpenRouter is the network fallback for ambiguous fields. Both are
lazy imports so the module imports cleanly without either dependency.
"""

import html
import logging
import re
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"(?:INR|Rs\.?|₹|USD|\$)\s?([\d][\d,]*)")
_ORIG_DEST_RE = re.compile(r"\b([A-Z]{3})\s*[-→>]{1,2}\s*([A-Z]{3})\b")
_FLIGHT_RE = re.compile(r"\b([A-Z0-9]{2})\s*-?\s*(\d{2,4})\b")
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")

_AIRLINE_NAMES = {
    "6E": "IndiGo",
    "AI": "Air India",
    "SG": "SpiceJet",
    "QP": "Akasa Air",
    "IX": "Air India Express",
    "UK": "Vistara",
    "I5": "Air India Express",
    "G8": "Go First",
}


class VLMNotConfigured(Exception):
    """Raised when no VLM backend is available."""


def _walk_strings(obj: Any) -> List[str]:
    """Recursively collect string leaves from a parsed JSON-ish structure."""
    out: List[str] = []
    if isinstance(obj, str):
        if obj.strip():
            out.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            out.extend(_walk_strings(value))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            out.extend(_walk_strings(item))
    return out


class _PaddleOCRVLBackend:
    """Local PaddleOCR-VL-1.6 (0.9B) card-field extractor."""

    def __init__(self):
        self._pipeline: Optional[Any] = None

    @staticmethod
    def _parse_fields(text: str) -> Dict[str, Any]:
        text = html.unescape(text)  # markdown -> HTML-escaped entities (e.g. -&gt;)
        fields: Dict[str, Any] = {}
        price = _PRICE_RE.search(text)
        if price:
            try:
                fields["price"] = float(price.group(1).replace(",", ""))
            except ValueError:
                pass
        route = _ORIG_DEST_RE.search(text)
        if route:
            fields["origin"], fields["destination"] = route.groups()
        flight = _FLIGHT_RE.search(text)
        if flight and _AIRLINE_NAMES.get(flight.group(1).upper()):
            code, number = flight.groups()
            fields["airline"] = code.upper()
            fields["airline_name"] = _AIRLINE_NAMES.get(code.upper())
            fields["flight_number"] = f"{code.upper()}-{number}"
        times = _TIME_RE.findall(text)
        if len(times) >= 1:
            fields["departure_time"] = f"{times[0][0]}:{times[0][1]}"
        if len(times) >= 2:
            fields["arrival_time"] = f"{times[1][0]}:{times[1][1]}"
        return fields

    def _text_of(self, image_path: str) -> str:
        if self._pipeline is None:
            from paddleocr import PaddleOCRVL

            self._pipeline = PaddleOCRVL(pipeline_version="v1.6")
        results = self._pipeline.predict(image_path)
        blob: List[str] = []
        for result in results or []:
            res = (result.json or {}).get("res") if hasattr(result, "json") else {}
            blob.extend(_walk_strings(res))
        return "\n".join(blob)

    def extract_card_fields(
        self, image_path: str, prompt: str = "", schema: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        return self._parse_fields(self._text_of(image_path))


class VLMService:
    """Registry of lazy VLM backends for structured field extraction."""

    def __init__(self, prefer: str = "paddleocr_vl"):
        self.prefer = prefer
        self.backends: Dict[str, Callable[..., Any]] = {
            "paddleocr_vl": self._paddleocr_vl,
            "openrouter": self._openrouter,
            "none": self._none,
        }

    @staticmethod
    def _none(*args, **kwargs):  # pragma: no cover - trivial sentinel
        raise VLMNotConfigured("No VLM backend configured.")

    @staticmethod
    def _paddleocr_vl():
        # Lazy so the pipeline runs without the 0.9B vision model weights.
        import importlib.util

        if importlib.util.find_spec("paddleocr") is None:
            raise VLMNotConfigured("paddleocr-VL not installed.")
        return _PaddleOCRVLBackend()

    @staticmethod
    def _openrouter():
        try:
            from services.ai.openrouter_client import OpenRouterClient  # type: ignore

            return OpenRouterClient
        except ImportError as e:
            raise VLMNotConfigured("OpenRouter client unavailable.") from e

    def available_backends(self) -> List[str]:
        out = []
        for name in self.backends:
            if name == "none":
                continue
            try:
                self.backends[name]()
                out.append(name)
            except VLMNotConfigured:
                continue
        return out

    def extract_fields(
        self, image_path: str, prompt: str, schema: Dict[str, str]
    ) -> Dict[str, Any]:
        """Ask a VLM to fill a small set of typed fields for an image (fare card)."""
        order = [self.prefer] + [b for b in self.backends if b != self.prefer and b != "none"]
        errors: List[str] = []
        for name in order:
            try:
                loader = self.backends[name]
                impl = loader()
                return self._invoke(impl, image_path, prompt, schema)
            except VLMNotConfigured as e:
                errors.append(f"{name}: {e}")
            except Exception as e:  # noqa: BLE001 - a failing backend must not block others
                errors.append(f"{name}: {e}")
        raise VLMNotConfigured("; ".join(errors) or "No fields extracted by any VLM backend.")

    @staticmethod
    def _invoke(impl, image_path: str, prompt: str, schema: Dict[str, str]) -> Dict[str, Any]:
        if hasattr(impl, "extract_card_fields"):
            return impl.extract_card_fields(image_path, prompt, schema)
        # Fallback heuristic for a model-agnostic client: ask for a JSON-only answer.
        sample = getattr(impl, "chat_completion", None)
        if callable(sample):
            raw = sample(
                prompt=f"{prompt}\nReturn strictly JSON.",
            )
            if isinstance(raw, dict):
                return raw
        raise VLMNotConfigured("Backend does not expose a card-field interface.")


def supports_vlm() -> bool:
    return len(VLMService().available_backends()) > 0
