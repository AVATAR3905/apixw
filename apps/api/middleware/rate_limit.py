"""Rate limiting middleware protecting API endpoints from abuse (Security Standard Sec 65)."""

import time
from typing import Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window rate limiter per client IP."""

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        # client_ip -> list of timestamps
        self.client_records: Dict[str, list] = {}

    async def dispatch(self, request: Request, call_next):
        # Exclude docs, health, and openapi from strict rate limiting
        if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json", "/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        window_start = now - 60.0

        # Clean old timestamps
        timestamps = self.client_records.get(client_ip, [])
        timestamps = [t for t in timestamps if t > window_start]

        limit = self.requests_per_minute
        # Bulk export endpoints have a stricter limit
        if "/export/" in request.url.path:
            limit = 20

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
        self.client_records[client_ip] = timestamps

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(timestamps)))
        return response
