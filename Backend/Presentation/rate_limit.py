"""Rate limiting: one shared limit per client IP for the whole API.

Every request to any endpoint counts towards the same limit (RATE_LIMIT in
the settings, 60 per minute by default). The request after the limit, within
the same minute, gets a 429 with a Retry-After header and never reaches the
endpoint.

Built on the `limits` library instead of slowapi: slowapi's middleware can't
find the routes of FastAPI 0.141 (they sit inside _IncludedRouter objects)
and then silently skips every request.

The counters live in memory, per API process. That's enough for one
container; with several replicas each one counts on its own.
"""

import math
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from limits import RateLimitItem, parse
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from Backend.config import get_settings

_storage = MemoryStorage()
_limiter = FixedWindowRateLimiter(_storage)


def client_ip(request: Request) -> str:
    """The IP the limit is counted for.

    Behind Azure Container Apps every request comes from the ingress proxy,
    so request.client is the same address for every user. The proxy puts the
    real client IP at the END of X-Forwarded-For; anything before it was sent
    by the client itself and can be made up, so only the last entry is used.
    Locally there is no proxy and no header, so the direct address is used.
    """
    forwarded = request.headers.get("x-forwarded-for")

    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last

    return request.client.host if request.client else "unknown"


def reset_rate_limits() -> None:
    """Forget every counter. Used by the tests."""
    _storage.reset()


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, limit: RateLimitItem) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        ip = client_ip(Request(scope))

        if _limiter.hit(self.limit, ip):
            await self.app(scope, receive, send)
            return

        reset_at = _limiter.get_window_stats(self.limit, ip).reset_time
        response = JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please wait a moment and try again."
            },
            headers={
                "Retry-After": str(max(1, math.ceil(reset_at - time.time()))),
                "X-RateLimit-Limit": str(self.limit.amount),
                "X-RateLimit-Remaining": "0",
            },
        )
        await response(scope, receive, send)


def add_rate_limiting(app: FastAPI) -> None:
    app.add_middleware(RateLimitMiddleware, limit=parse(get_settings().rate_limit))
