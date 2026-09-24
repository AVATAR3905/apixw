"""Optional API-key authentication for the /api/v1/* consumer surface.

Off by default (``API_KEY_REQUIRED=false``) so local development, the
dashboard, and the static /ui viewer keep working exactly as before. A
production deployment serving NSO/RBI-grade programmatic consumers flips
``API_KEY_REQUIRED=true`` and populates ``API_KEYS`` (comma-separated) in
``.env`` to require an ``X-API-Key`` header on every ``/api/v1/*`` call.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from packages.shared.config import settings


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Requires a valid ``X-API-Key`` header on ``/api/v1/*`` when enabled.

    Every other path (docs, health, root, the dashboard/UI's own static
    assets, exports) is left untouched -- this only gates the versioned
    programmatic API surface, not the demo frontends.
    """

    def __init__(self, app):
        super().__init__(app)
        self.valid_keys = {k.strip() for k in settings.API_KEYS.split(",") if k.strip()}

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.API_KEY_REQUIRED or not request.url.path.startswith("/api/v1"):
            return await call_next(request)

        supplied = request.headers.get("X-API-Key")
        if not supplied or supplied not in self.valid_keys:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "message": "A valid X-API-Key header is required for this endpoint.",
                },
            )

        return await call_next(request)
