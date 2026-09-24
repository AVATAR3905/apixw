"""Tests for RateLimitMiddleware: header injection, 429 enforcement, and exemptions."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.middleware.rate_limit import RateLimitMiddleware

client = TestClient(app)


def test_exempt_paths_skip_rate_limit_headers():
    """Docs, health, root, and the /ui viewer mount are not rate limited."""
    for path in ("/", "/health", "/docs/oauth2-redirect", "/openapi.json"):
        res = client.get(path)
        assert "X-RateLimit-Limit" not in res.headers, f"expected exemption for {path}"
    # /ui viewer mount (subresources included) is exempt even though the path 404s
    res = client.get("/ui/nonexistent.js")
    assert "X-RateLimit-Limit" not in res.headers


def test_rate_limited_path_has_headers():
    res = client.get("/api/v1/index")
    assert res.status_code == 200
    assert res.headers["X-RateLimit-Limit"] == "120"
    assert int(res.headers["X-RateLimit-Remaining"]) <= 119


def test_sliding_window_429_and_retry_after():
    """A 2/min instance must reject the 3rd request with 429 + Retry-After."""
    mini = FastAPI()

    @mini.get("/limited")
    def limited():
        return {"ok": True}

    mini.add_middleware(RateLimitMiddleware, requests_per_minute=2)
    mc = TestClient(mini)

    assert mc.get("/limited").status_code == 200
    assert mc.get("/limited").status_code == 200
    third = mc.get("/limited")
    assert third.status_code == 429
    assert third.json()["error"] == "Too Many Requests"
    assert third.headers.get("Retry-After") == "60"


def test_export_endpoints_stricter_limit():
    """Export endpoints get a 20/min ceiling, surfaced via X-RateLimit-Limit."""
    mini = FastAPI()

    @mini.get("/export/x")
    def export_x():
        return {"ok": True}

    mini.add_middleware(RateLimitMiddleware, requests_per_minute=120)
    mc = TestClient(mini)

    for _ in range(3):
        res = mc.get("/export/x")
        assert res.status_code == 200
    assert res.headers["X-RateLimit-Limit"] == "20"
