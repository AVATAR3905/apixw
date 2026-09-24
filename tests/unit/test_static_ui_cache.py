"""Regression test: the /ui static viewer must force cache revalidation.

Starlette's default StaticFiles sends no explicit Cache-Control, so browsers
apply their own heuristic freshness and can keep serving a stale index.html
well after the file changes on disk -- confirmed repeatedly during
development. NoCacheStaticFiles (apps/api/main.py) fixes this.
"""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_ui_index_sends_no_cache_header():
    res = client.get("/ui/")
    assert res.status_code == 200
    assert res.headers.get("cache-control") == "no-cache"


def test_ui_static_asset_sends_no_cache_header():
    res = client.get("/ui/index.html")
    assert res.status_code == 200
    assert res.headers.get("cache-control") == "no-cache"
