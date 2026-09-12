"""Unit tests for the fare response cache (memory backend)."""

import pytest

from services.collectors.response_cache import FareResponseCache


@pytest.fixture
def cache() -> FareResponseCache:
    return FareResponseCache(ttl=60)


def test_cache_roundtrip(cache):
    key = "rpc:DEL:BOM:2026-09-18"
    quotes = [{"flight_number": "6E-205", "total_fare": 3540.0}]
    assert cache.set(key, quotes) is True
    assert cache.get(key) == quotes


def test_cache_miss_returns_none(cache):
    assert cache.get("nope") is None


def test_cache_ttl_expiry():
    cache = FareResponseCache(ttl=0)
    cache.set("k", [{"price": 1.0}])
    assert cache.get("k") is None


def test_hit_or_miss_produces_and_caches(cache):
    calls = {"n": 0}

    def producer():
        calls["n"] += 1
        return [{"price": 100.0}]

    first = cache.hit_or_miss("key-a", producer)
    second = cache.hit_or_miss("key-a", producer)
    assert first == second == [{"price": 100.0}]
    assert calls["n"] == 1


def test_hit_or_miss_empty_result_not_cached(cache):
    calls = {"n": 0}

    def producer():
        calls["n"] += 1
        return []

    assert cache.hit_or_miss("key-b", producer) == []
    assert cache.hit_or_miss("key-b", producer) == []
    assert calls["n"] == 2


def test_clear_and_delete(cache):
    cache.set("x", [{"price": 1.0}])
    cache.delete("x")
    assert cache.get("x") is None
    cache.set("y", [{"price": 2.0}])
    cache.clear()
    assert cache.get("y") is None


def test_disable_flag_no_caching():
    cache = FareResponseCache(ttl=60)
    cache.enabled = False
    cache.set("k", [{"price": 1.0}])
    assert cache.get("k") is None
    assert cache.backend == "disabled"
