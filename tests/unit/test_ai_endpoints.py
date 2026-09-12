"""Unit tests for AI Copilot FastAPI Endpoints."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_ai_pre_made_prompts_endpoint():
    """Verifies that the pre-made question chips endpoint returns valid prompts."""
    res = client.get("/api/v1/ai/pre-made-prompts")
    assert res.status_code == 200
    data = res.json()
    assert "prompts" in data
    assert len(data["prompts"]) >= 5

    first = data["prompts"][0]
    assert "id" in first
    assert "title" in first
    assert "prompt" in first


def test_ai_query_without_key_returns_401():
    """Verifies that 100% cloud execution rejects requests without an API key."""
    # Ensure empty key
    from packages.shared.config import settings

    old_key = settings.OPENROUTER_API_KEY
    settings.OPENROUTER_API_KEY = ""

    try:
        res = client.post(
            "/api/v1/ai/query",
            json={"prompt": "Which airline is cheapest right now?"},
        )
        assert res.status_code == 401
        data = res.json()
        assert data["detail"]["error_code"] == "OPENROUTER_API_KEY_REQUIRED"
    finally:
        settings.OPENROUTER_API_KEY = old_key
