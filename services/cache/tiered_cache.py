"""Tiered Caching Service (FareLens/Edge-native pattern).

Implements multi-layer caching with tiered TTLs:
- L1: In-memory (dict) - sub-millisecond, for hot paths
- L2: Redis/Valkey - milliseconds, distributed (optional)
- L3: Database materialized views - seconds, persistent

TTL Strategy (FareLens inspired):
- Search results: 5 min TTL (prices change slowly)
- Watchlist checks: 30 min TTL (background refresh 2x/day)
- Index values: 15 min TTL (recomputed daily)
- Corridor details: 10 min TTL
- Live quotes: 2 min TTL (high freshness requirement)
"""

import datetime
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import redis
from sqlalchemy.orm import Session


@dataclass
class CacheEntry:
    value: Any
    expires_at: float
    tier: str
    key: str


class TieredCache:
    """Multi-tier cache with automatic tier promotion/demotion."""

    # TTL configuration (seconds)
    TTL_CONFIG = {
        "search_results": 300,      # 5 min
        "watchlist": 1800,          # 30 min
        "index_values": 900,        # 15 min
        "corridor_detail": 600,     # 10 min
        "live_quotes": 120,         # 2 min
        "route_metadata": 3600,     # 1 hour
    }

    def __init__(self, redis_url: Optional[str] = None):
        self._l1_cache: Dict[str, CacheEntry] = {}  # In-memory
        self._redis = None
        if redis_url:
            try:
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    def _make_key(self, namespace: str, *parts: str) -> str:
        return f"apix:{namespace}:{':'.join(parts)}"

    def _is_expired(self, entry: CacheEntry) -> bool:
        return time.time() > entry.expires_at

    def get(self, namespace: str, *parts: str) -> Optional[Any]:
        """Get value from cache, checking L1 -> L2 -> L3."""
        key = self._make_key(namespace, *parts)

        # L1: In-memory
        if key in self._l1_cache:
            entry = self._l1_cache[key]
            if not self._is_expired(entry):
                return entry.value
            else:
                del self._l1_cache[key]

        # L2: Redis
        if self._redis:
            try:
                val = self._redis.get(key)
                if val is not None:
                    import json
                    parsed = json.loads(val)
                    # Promote to L1
                    self._l1_cache[key] = CacheEntry(
                        value=parsed, expires_at=time.time() + 60, tier="L1", key=key
                    )
                    return parsed
            except Exception:
                pass

        # L3: Database (materialized view / computed on demand)
        return None

    def set(self, namespace: str, value: Any, *parts: str, ttl: Optional[int] = None) -> None:
        """Set value in all cache tiers."""
        key = self._make_key(namespace, *parts)
        ttl = ttl or self.TTL_CONFIG.get(namespace, 300)
        expires_at = time.time() + ttl

        entry = CacheEntry(value=value, expires_at=expires_at, tier="L1", key=key)
        self._l1_cache[key] = entry

        # L2: Redis
        if self._redis:
            try:
                import json
                self._redis.setex(key, ttl, json.dumps(value, default=str))
            except Exception:
                pass

    def invalidate(self, namespace: str, *parts: str) -> None:
        """Invalidate cache entry across all tiers."""
        key = self._make_key(namespace, *parts)
        if key in self._l1_cache:
            del self._l1_cache[key]
        if self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass

    def invalidate_namespace(self, namespace: str) -> None:
        """Invalidate all keys in a namespace."""
        prefix = f"apix:{namespace}:"
        keys_to_del = [k for k in self._l1_cache if k.startswith(prefix)]
        for k in keys_to_del:
            del self._l1_cache[k]
        if self._redis:
            try:
                for k in self._redis.scan_iter(match=f"{prefix}*"):
                    self._redis.delete(k)
            except Exception:
                pass

    def get_or_compute(
        self,
        namespace: str,
        compute_fn: Callable[[], Any],
        *parts: str,
        ttl: Optional[int] = None,
    ) -> Any:
        """Get from cache or compute and cache."""
        cached = self.get(namespace, *parts)
        if cached is not None:
            return cached
        value = compute_fn()
        self.set(namespace, value, *parts, ttl=ttl)
        return value


# Global cache instance (lazy-initialized)
_cache_instance: Optional[TieredCache] = None


def get_cache(redis_url: Optional[str] = None) -> TieredCache:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = TieredCache(redis_url)
    return _cache_instance


def invalidate_index_cache() -> None:
    """Invalidate all index-related caches."""
    cache = get_cache()
    cache.invalidate_namespace("index")
    cache.invalidate_namespace("corridor")
    cache.invalidate_namespace("search")


def cache_index_computation(
    observation_date: str,
    series: str,
    horizon: str,
    db_factory: Callable[[], Session],
) -> Dict[str, Any]:
    """Cached index computation with tiered TTL."""
    cache = get_cache()
    key = f"{series}:{horizon}:{observation_date}"

    def compute() -> Dict[str, Any]:
        db = db_factory()
        try:
            # Import here to avoid circular imports
            from services.index_engine.calculator_service import DailyIndexCalculatorService

            obs_date = datetime.datetime.strptime(observation_date, "%Y-%m-%d").date()
            recs = DailyIndexCalculatorService.calculate_day_indices(
                db, observation_date=obs_date, persist=False
            )
            return {"records": len(recs), "date": observation_date}
        finally:
            db.close()

    return cache.get_or_compute("index", compute, key, ttl=900)
