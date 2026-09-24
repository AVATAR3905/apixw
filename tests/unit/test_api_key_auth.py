"""Tests for APIKeyAuthMiddleware: off-by-default behavior and gated enforcement."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.middleware.api_key_auth import APIKeyAuthMiddleware
from packages.shared.config import settings

client = TestClient(app)


def test_disabled_by_default_lets_everything_through():
    """API_KEY_REQUIRED defaults to false: no header needed, dashboard/UI unaffected."""
    assert settings.API_KEY_REQUIRED is False
    res = client.get("/api/v1/index")
    assert res.status_code == 200


def _mini_app_with_auth(monkeypatch, keys="secret-key-1,secret-key-2"):
    monkeypatch.setattr(settings, "API_KEY_REQUIRED", True)
    monkeypatch.setattr(settings, "API_KEYS", keys)

    mini = FastAPI()

    @mini.get("/api/v1/protected")
    def protected():
        return {"ok": True}

    @mini.get("/health")
    def health():
        return {"ok": True}

    mini.add_middleware(APIKeyAuthMiddleware)
    return TestClient(mini)


def test_enabled_rejects_missing_key(monkeypatch):
    mc = _mini_app_with_auth(monkeypatch)
    res = mc.get("/api/v1/protected")
    assert res.status_code == 401
    assert res.json()["error"] == "Unauthorized"


def test_enabled_rejects_wrong_key(monkeypatch):
    mc = _mini_app_with_auth(monkeypatch)
    res = mc.get("/api/v1/protected", headers={"X-API-Key": "not-a-real-key"})
    assert res.status_code == 401


def test_enabled_accepts_valid_key(monkeypatch):
    mc = _mini_app_with_auth(monkeypatch)
    res = mc.get("/api/v1/protected", headers={"X-API-Key": "secret-key-1"})
    assert res.status_code == 200


def test_enabled_still_exempts_non_api_paths(monkeypatch):
    """Only /api/v1/* is gated -- health/docs/dashboard/UI stay reachable."""
    mc = _mini_app_with_auth(monkeypatch)
    res = mc.get("/health")
    assert res.status_code == 200
