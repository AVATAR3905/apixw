"""Rate limiting middleware protecting API endpoints from abuse (Security Standard Sec 65)."""

import time
from typing import Dict, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window rate limiter per client IP.

    Exempts /, /health, /docs*, /redoc, /openapi.json, and /ui* viewer paths.
    Export paths (/export/*) receive their own, independent 20 req/min budget
    -- separate from the general-traffic budget, so neither class can starve
    the other for the same client.
    """

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        # (client_ip, is_export) -> list of timestamps
        self.client_records: Dict[Tuple[str, bool], list] = {}

    async def dispatch(self, request: Request, call_next):
        # Exclude docs, health, static viewer, and openapi from strict rate limiting
        path = request.url.path
        if (
            path in ("/health", "/redoc", "/openapi.json", "/")
            or path.startswith(("/docs", "/ui"))
        ):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        window_start = now - 60.0

        # Export and general traffic are tracked as *independent* budgets per
        # client. They used to share one counter keyed only by IP, which meant
        # ordinary browsing (/api/v1/index, etc.) could burn through the same
        # window and lock a client out of exports entirely despite never
        # having called an export endpoint -- and conversely, a burst of
        # export calls could starve that client's regular API access. Keying
        # by (client_ip, is_export) gives each traffic class its own window.
        is_export = "/export/" in request.url.path
        record_key = (client_ip, is_export)
        limit = 20 if is_export else self.requests_per_minute

        # Clean old timestamps
        timestamps = self.client_records.get(record_key, [])
        timestamps = [t for t in timestamps if t > window_start]

        if len(timestamps) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded ({limit} requests/minute). Please slow down.",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )

        timestamps.append(now)
        self.client_records[record_key] = timestamps

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(timestamps)))
        return response
