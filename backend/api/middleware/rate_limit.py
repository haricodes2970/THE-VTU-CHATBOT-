"""
backend/api/middleware/rate_limit.py
Simple in-memory IP-based rate limiter middleware (60 req/min per IP).
"""
import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

RATE_LIMIT = 60
RATE_WINDOW = 60.0  # seconds

_ip_store: dict[str, list[float]] = defaultdict(list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """60 requests per minute per IP address."""

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - RATE_WINDOW

        # Clean old entries
        _ip_store[ip] = [t for t in _ip_store[ip] if t > window_start]

        if len(_ip_store[ip]) >= RATE_LIMIT:
            retry_after = int(RATE_WINDOW - (now - _ip_store[ip][0]))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RateLimitExceeded",
                    "message": f"Too many requests. Limit: {RATE_LIMIT}/minute.",
                    "retry_after_seconds": max(retry_after, 1),
                },
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        _ip_store[ip].append(now)
        return await call_next(request)
