"""Free-tier OpenRouter vision backend for fare-card field extraction.

The local extraction chain (OCR -> layout -> VLM) ends with a vision-language
step that reads a raw screenshot and fills fields neither OCR nor DOM resolved.
``OpenRouterVisionBackend`` is the cloud twin of the local PaddleOCR-VL backend:
same ``extract_card_fields(image_path, prompt, schema)`` contract, driven
entirely by OpenRouter's ``:free`` vision models so the pipeline can be fully
validated with zero GPU/CPU model weights.

Model candidates are ranked vision-capable ``:free`` endpoints verified against
the OpenRouter model catalogue; the client falls through the list on HTTP or
parse failures. A pinned model wins when ``settings.OPENROUTER_VISION_MODEL``
(or the ``model=`` argument) is set.
"""

import base64
import json
import logging
import mimetypes
import os
import re
import time

import httpx

from packages.shared.config import settings

logger = logging.getLogger("airfare.ai.openrouter_vision")

# Ranked free-tier vision endpoints on OpenRouter (live catalogue, prompt $0).
DEFAULT_FREE_VISION_MODELS = [
    "inclusionai/ling-3.0-flash-vl:free",
    "nex-agi/nex-n2.5-pro:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "google/gemma-4-31b-it:free",
    "openrouter/free",
]

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_PRICE_RE = re.compile(r"(?:INR|Rs\.?|₹|USD|\$)?\s?([\d][\d,]*)")
_JSON_DECODER = json.JSONDecoder()


class OpenRouterVisionError(Exception):
    """Base error for the vision backend."""


class OpenRouterVisionUnavailable(OpenRouterVisionError):
    """Missing API key or no responsive model."""


def _image_data_url(image_path: str, _max_bytes: int = 4_000_000) -> str:
    """Base64 data-URL of the image, downscaled if the payload is oversized."""
    import io

    from PIL import Image

    mime = mimetypes.guess_type(image_path)[0] or "image/png"
    with open(image_path, "rb") as fh:
        payload = fh.read()
    if len(payload) > _max_bytes:
        with Image.open(image_path) as img:
            w, h = img.size
            scale = min(1024 / w, 1.0)
            if scale < 1.0:
                img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            payload = buf.getvalue()
    return f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"


def _json_fields(answer: str) -> dict:
    """Best-effort JSON parse of the model answer into a flat field dict.

    Free-tier vision models often preface their answer with chain-of-thought
    prose then close with the JSON object, so every ``{...}`` block is tried via
    ``raw_decode`` and the largest well-formed object wins.
    """
    candidates: list = []
    fences = _FENCE_RE.findall(answer)
    if fences:
        candidates.append(fences[0])
    candidates.append(answer)

    best: dict | None = None
    best_span = 0
    for blob in candidates:
        for match in re.finditer(r"\{", blob):
            try:
                obj, end = _JSON_DECODER.raw_decode(blob[match.start():])
            except json.JSONDecodeError:
                continue
            span = match.start() + end - match.start()
            if isinstance(obj, dict) and span > best_span:
                best, best_span = obj, span
    return _flatten(best) if best else {}


def _flatten(obj, prefix: str = "") -> dict:
    """Flatten nested JSON into scalar leaf values with normalized keys.

    Leaves keep their own normalized name (no prefix), so a nested answer like
    ``{"result": [{"data": {"total_fare": "INR 4,250"}}]}`` still exposes
    ``total_fare`` directly to the schema alias matcher.
    """
    out: dict = {}
    for key, value in obj.items():
        norm = (key or "").strip().lower().replace("-", "_").replace(" ", "_")
        if isinstance(value, dict):
            out.update(_flatten(value))
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                out.update(_flatten(value[0]))
            elif value:
                out[norm] = value[0]
        else:
            if value is not None and str(value).strip() and str(value).lower() != "null":
                out[norm] = value
    return out


_FIELD_ALIASES = {
    "price": ("price", "total_fare", "total_price", "fare", "amount"),
    "origin": ("origin", "origin_iata", "departure_airport", "from", "source"),
    "destination": ("destination", "destination_iata", "arrival_airport", "to", "dest"),
    "airline": ("airline", "airline_code", "carrier", "carrier_code", "airline_iata"),
    "flight_number": ("flight_number", "flight", "flight_no", "flightname"),
    "departure_time": ("departure_time", "departure", "dep_time", "takeoff_time", "start_time"),
    "arrival_time": ("arrival_time", "arrival", "arr_time", "landing_time", "end_time"),
    "stops": ("stops", "stop_count", "number_of_stops"),
    "duration_minutes": ("duration_minutes", "duration", "duracion", "flight_duration"),
    "travel_date": ("travel_date", "date", "flight_date", "journey_date"),
}


def _fields_from_answer(answer: str) -> dict:
    """Map the model answer onto the extraction schema, JSON first, regex last."""
    flat = _json_fields(answer)
    fields: dict = {}
    for field, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if alias in flat:
                value = flat[alias]
                if field == "price":
                    match = _PRICE_RE.search(str(value))
                    if match:
                        try:
                            fields["price"] = float(match.group(1).replace(",", ""))
                        except ValueError:
                            pass
                    break
                if field == "stops":
                    try:
                        fields["stops"] = int(float(str(value).split()[0]))
                    except (ValueError, IndexError):
                        pass
                    break
                if field == "duration_minutes":
                    match = re.search(r"(\d{1,3})", str(value))
                    if match:
                        fields["duration_minutes"] = int(match.group(1))
                    break
                if field == "flight_number":
                    flight = re.sub(r"[^0-9A-Za-z]", "", str(value)).upper()
                    match = re.match(r"([A-Z0-9]{2})(\d{3,4})", flight)
                    if match:
                        fields["flight_number"] = f"{match.group(1)}-{match.group(2)}"
                    break
                if isinstance(value, (int, float)) or str(value).strip():
                    fields[field] = value
                break
    if fields.get("airline") and not fields.get("flight_number"):
        match = re.search(r"([A-Z0-9]{2})\s*-?\s*(\d{3,4})", _FENCE_RE.sub("", answer))
        if match:
            fields["flight_number"] = f"{match.group(1).upper()}-{match.group(2)}"
        fields["flight_number"] = fields.get("flight_number") or ""
    return fields


class OpenRouterVisionBackend:
    """Cloud vision backend implementing the card-field extraction contract."""

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, model: str = "", api_key: str = "", timeout: float = 75.0, attempts: int = 2, max_models: int = 2):
        self.api_key = (api_key or settings.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY") or "").strip()
        self.model = model or (settings.OPENROUTER_VISION_MODEL or "").strip()
        self.timeout = timeout
        self.attempts = attempts
        self.max_models = max_models
        self.candidates = self._candidate_models()

    def _candidate_models(self) -> list:
        names = []
        if self.model:
            names.append(self.model)
        names.extend(m for m in DEFAULT_FREE_VISION_MODELS if m not in names)
        return names

    def extract_card_fields(self, image_path: str, prompt: str = "", schema: dict | None = None) -> dict:
        if not self.api_key:
            raise OpenRouterVisionUnavailable(
                "OPENROUTER_API_KEY is not configured in the environment."
            )
        keys = ", ".join(f"{k}: {v}" for k, v in (schema or {}).items())
        text = (
            (prompt or "Extract the cheapest fare shown in this screenshot.")
            + f"\nReturn STRICTLY a single JSON object using ONLY these keys: {keys or 'price, origin, destination, airline, flight_number, departure_time, arrival_time, stops, duration_minutes, travel_date'}."
            + "\nIgnore the route header, dates and page chrome. Values must be plain strings or numbers. "
            + "Output the JSON object and nothing else — no prose, no code fences, no thinking."
        )
        errors: list = []
        for model in self.candidates[: self.max_models]:
            for attempt in range(self.attempts):
                try:
                    raws = self._chat(model, image_path, text)
                except (httpx.HTTPError, ValueError, OpenRouterVisionUnavailable) as exc:
                    msg = str(exc) or exc.__class__.__name__
                    logger.warning("OpenRouter vision %s attempt %d failed: %s", model, attempt + 1, msg)
                    errors.append(f"{model} ({msg})")
                else:
                    parsed = {}
                    for raw in raws:
                        parsed = _fields_from_answer(raw)
                        if parsed.get("price") is not None or parsed.get("origin"):
                            logger.info("OpenRouter vision %s parsed %d fields", model, len(parsed))
                            return parsed
                    errors.append(f"{model} (unusable answer)")
                # Free-tier endpoints are flaky in BOTH ways: rate-limited HTTP
                # errors AND truncated chain-of-thought with no final JSON. Retry
                # the same model a few times regardless of which one happened.
                if attempt < 2:
                    time.sleep(2.0 * (attempt + 1))
        raise OpenRouterVisionUnavailable("; ".join(errors) or "no responsive model")

    def _chat(self, model: str, image_path: str, text: str) -> list:
        """Chat once and return answer candidates, most authoritative first.

        Free-tier models frequently stuff the structured-output budget into
        chain-of-thought, so both the message's ``content`` (final answer) and
        ``reasoning`` (chain-of-thought) are returned; the caller tries them in
        order until one yields parseable fields.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": settings.OPENROUTER_SITE_URL,
            "X-Title": settings.OPENROUTER_SITE_NAME,
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text},
                        {"type": "image_url", "image_url": {"url": _image_data_url(image_path)}},
                    ],
                }
            ],
            "temperature": 0.0,
            # Free-tier reasoning models spend most of the budget inside chain
            # of thought; stingy caps truncate before the final JSON is emitted.
            "max_tokens": 4000,
        }
        with httpx.Client(timeout=self.timeout) as client:
            res = client.post(self.API_URL, headers=headers, json=payload)
            if res.status_code == 401:
                raise OpenRouterVisionUnavailable("OpenRouter authentication failed (HTTP 401).")
            if res.status_code != 200:
                raise ValueError(f"HTTP {res.status_code}: {res.text[:200]}")
            data = res.json()
            choices = data.get("choices") or []
            if not choices:
                raise ValueError("empty choices")
            message = choices[0].get("message") or {}
            content = (message.get("content") or "").strip()
            reasoning = (message.get("reasoning") or "").strip()
            candidates = [c.strip() for c in (content, reasoning) if c.strip()]
            if not candidates:
                raise ValueError("empty content")
            return candidates
