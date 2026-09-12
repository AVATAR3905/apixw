"""Fare response cache with Redis primary and thread-safe in-memory TTL fallback.

Redis is preferred when available; if the connection is unavailable (common in
development), we transparently degrade to an in-process TTL store so collection
still works and repeat requests within the TTL window are still deduplicated.
"""

import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from packages.shared.config import settings

logger = logging.getLogger(__name__)

TTL_SECONDS = settings.CACHE_TTL_SECONDS
_ENABLED = settings.USE_CACHE


class FareResponseCache:
    """Deduplicates raw fare responses so repeated corridor/horizon requests are cached."""

    def __init__(self, redis_url: Optional[str] = None, ttl: int = TTL_SECONDS):
        self.ttl = ttl
        self.enabled = _ENABLED
        self._lock = threading.Lock()
        self._store: Dict[str, Dict[str, Any]] = {}
        self._redis = None
        if self.enabled:
            try:
                import redis  # type: ignore

                self._redis = redis.Redis.from_url(
                    redis_url or settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1
                )
                self._redis.ping()
            except Exception as e:
                logger.warning("Redis unavailable (%s); using in-memory fare cache.", e)
                self._redis = None

    @property
    def backend(self) -> str:
        if not self.enabled:
            return "disabled"
        return "redis" if self._redis is not None else "memory"

    def get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        if not self.enabled or not key:
            return None
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                return json.loads(raw) if raw else None
            except Exception:
                return None
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            expires_at = entry["expires_at"]
            if expires_at <= time.time():
                self._store.pop(key, None)
                return None
            return json.loads(entry["payload"])

    def set(self, key: str, value: List[Dict[str, Any]]) -> bool:
        if not self.enabled or not key:
            return False
        serialized = json.dumps(value, default=str)
        if self._redis is not None:
            try:
                self._redis.setex(key, self.ttl, serialized)
            except Exception:
                return False
        with self._lock:
            self._store[key] = {"expires_at": time.time() + self.ttl, "payload": serialized}
        return True

    def delete(self, key: str) -> None:
        if self._redis is not None:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        if self._redis is not None:
            try:
                self._redis.flushdb()
            except Exception:
                pass
        with self._lock:
            self._store.clear()

    def hit_or_miss(self, key: str, producer) -> List[Dict[str, Any]]:
        """Returns cached payload if present, else calls ``producer`` and caches the result."""
        cached = self.get(key)
        if cached is not None:
            return cached
        value = producer()
        if value:
            self.set(key, value)
        return value


_default_cache: Optional[FareResponseCache] = None


def get_fare_cache() -> FareResponseCache:
    """Process-wide shared fare cache instance."""
    global _default_cache
    if _default_cache is None:
        _default_cache = FareResponseCache()
    return _default_cache
