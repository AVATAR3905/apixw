"""Unit tests for the browser pool lifecycle (loop + context accounting)."""

import asyncio

import pytest

from services.collectors.browser_pool import BrowserPool


def test_pool_starts_submits_and_stops():
    pool = BrowserPool()
    try:
        pool.start()
        result = pool.submit(asyncio.sleep(0.01, result="ok"))
        assert result == "ok"
        assert pool.stats()["started"] is True
    finally:
        pool.stop()


def test_pool_context_limit_accounting_via_fake_transport():
    """Verify in_use accounting without a real browser using a fake context."""

    class FakeCtx:
        pass

    pool = BrowserPool(max_contexts=1)
    assigned = []

    async def fake_acquire():
        return FakeCtx()

    # Stub provisioning.
    pool._provision_context = fake_acquire
    try:
        pool.start()
        ctx_a = pool.submit(pool.acquire())
        assigned.append(ctx_a)
        assert pool.stats()["in_use"] == 1
        pool.submit(pool.release(ctx_a))
        assert pool.stats()["idle_contexts"] == 1
    finally:
        pool.stop()


def test_pool_raises_browser_unavailable_on_provision_failure():
    """Provisioning failure must surface as BrowserUnavailable, not hang."""

    from services.collectors.browser_pool import BrowserUnavailable

    pool = BrowserPool()

    async def broken_provision():
        raise BrowserUnavailable("no chromium")

    pool._provision_context = broken_provision
    try:
        with pytest.raises(BrowserUnavailable):
            pool.submit(pool.acquire())
        assert pool.stats()["in_use"] == 0
    finally:
        pool.stop()
