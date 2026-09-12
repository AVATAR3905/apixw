"""Network-layer extraction helpers for Playwright XHR interception.

Google Flights and several OTAs push the actual fare data over XHR as deeply
nested arrays (batchexecute ``f.req`` payloads). Rendering-driven scraping
misses these — we instead capture every JSON response the page makes and
search the decoded structure for quote-like records using candidate predicates.
"""

import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


def collect_values(payload: Any, target_key: str, max_hits: int = 500) -> List[Any]:
    """Recursively collect all values whose dict key equals ``target_key``."""
    found: List[Any] = []

    def walk(node: Any) -> None:
        if len(found) >= max_hits:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if k == target_key:
                    found.append(v)
                    if len(found) >= max_hits:
                        return
                walk(v)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(payload)
    return found


def find_quote_candidates(
    payload: Any,
    predicates: List[Callable[[Dict[str, Any]], bool]],
    max_candidates: int = 200,
) -> List[Dict[str, Any]]:
    """Locate dicts deep inside nested RPC payloads that look like fare records.

    A record is a candidate only when it passes at least one of the supplied
    predicates (e.g. has both a price and an origin field). This avoids matching
    on unrelated objects such as session tokens or tracking fragments.
    """
    hits: List[Dict[str, Any]] = []

    def walk(node: Any) -> None:
        if len(hits) >= max_candidates:
            return
        if isinstance(node, dict):
            if any(pred(node) for pred in predicates):
                hits.append(node)
                if len(hits) >= max_candidates:
                    return
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(payload)
    return hits


def truncate(payload: Any, limit: int = 4000) -> str:
    """Safe repr of an RPC payload for raw-payload capture, truncated at ``limit`` chars."""
    text = repr(payload)
    if len(text) > limit:
        text = text[:limit] + f"...[truncated {len(text) - limit} chars]"
    return text


async def attach_json_capture(page, predicate=None):
    """Register a response handler on a Playwright page collecting JSON bodies.

    Returns a list that grows as the page fires JSON responses.
    """
    captured: List[Dict[str, Any]] = []

    async def _on_response(res):
        try:
            if predicate is not None and not predicate(res):
                return
            content_type = res.headers.get("content-type", "")
            if "json" in content_type:
                body = await res.json()
                captured.append({"url": res.url, "payload": body})
        except Exception:
            pass

    page.on("response", _on_response)
    return captured
