"""Vercel serverless entrypoint -- re-exports the existing FastAPI app.

Vercel's Python runtime auto-detects a module-level ASGI ``app`` in a file
under /api and serves it directly, so the whole apps/api/main.py app (all
its routers, CORS, etc.) works unchanged. All actual logic stays in
apps/api/main.py; this file only makes the repo root importable so
`apps.api.main`, `packages`, `services`, and `database` resolve the same
way they do locally (PYTHONPATH=repo root) and in GitHub Actions.
"""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from apps.api.main import app  # noqa: E402
