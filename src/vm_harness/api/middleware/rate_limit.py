
"""
Rate limiting middleware for the vm-harness API.

Implements token-bucket rate limiting per API key (or per IP for
unauthenticated requests). Configurable burst size and refill rate
per role or globally.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web

log = logging.getLogger("vmharness.api.rate_limit")


@dataclass
class TokenBucket:
    """Classic token-bucket rate limiter."""
    rate: float        # tokens added per second
    burst: int         # maximum bucket size
    tokens: float = 0
    last_refill: float = 0

    def __post_init__(self) -> None:
        self.tokens = float(self.burst)
        self.last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate limited."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.last_refill = now
        # Refill tokens
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    @property
    def remaining(self) -> int:
        self.consume(0)  # trigger refill
        return int(self.tokens)


# ── Configuration ────────────────────────────────────────────────────────────

@dataclass
class RateLimitConfig:
    """Global rate limit configuration."""
    default_rate: float = 10.0    # 10 requests per second
    default_burst: int = 50       # allow bursts of 50
    enabled: bool = True
    # Per-role overrides
    role_overrides: dict[str, dict[str, float]] = field(default_factory=lambda: {
        "viewer": {"rate": 5.0, "burst": 20},
        "operator": {"rate": 20.0, "burst": 100},
        "admin": {"rate": 50.0, "burst": 200},
        "auditor": {"rate": 10.0, "burst": 50},
    })


# ── Middleware ────────────────────────────────────────────────────────────────

@web.middleware
async def rate_limit_middleware(
    request: web.Request, handler: Any
) -> web.StreamResponse:
    """
    Rate limiting middleware.

    Uses token-bucket algorithm. Identifies the caller by API key ID
    (from auth context) or falls back to client IP. Adds X-RateLimit-*
    headers to responses.
    """
    config: RateLimitConfig = request.app.get(
        "rate_limit_config", RateLimitConfig()
    )

    if not config.enabled:
        return await handler(request)

    # Identify the caller
    auth_context = request.get("auth_context")
    if auth_context and auth_context.get("key_id"):
        caller_id = auth_context["key_id"]
        roles = auth_context.get("roles", ["viewer"])
    else:
        caller_id = _get_client_ip(request)
        roles = ["viewer"]

    # Determine rate limit for this caller
    rate = config.default_rate
    burst = config.default_burst
    for role in roles:
        override = config.role_overrides.get(role)
        if override:
            rate = override.get("rate", rate)
            burst = int(override.get("burst", burst))
            break  # use first matching role override

    # Get or create bucket
    buckets: dict[str, TokenBucket] = request.app.setdefault(
        "_rate_limit_buckets", {}
    )
    bucket = buckets.get(caller_id)
    if bucket is None:
        bucket = TokenBucket(rate=rate, burst=burst)
        buckets[caller_id] = bucket

    # Check rate limit
    allowed = bucket.consume()

    if not allowed:
        log.warning("Rate limited: caller=%s", caller_id)
        response = web.json_response(
            {"error": "rate_limit_exceeded", "retry_after": 1.0 / rate},
            status=429,
            headers={
                "X-RateLimit-Limit": str(burst),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + 1.0 / rate)),
                "Retry-After": str(int(1.0 / rate) + 1),
            },
        )
        return response

    # Call handler
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        exc.content_type = "application/json"
        if not exc.text or not exc.text.startswith("{"):
            exc.text = json.dumps({"error": exc.reason or "http_error"})
        # Add rate limit headers to error responses too
        exc.headers["X-RateLimit-Limit"] = str(burst)
        exc.headers["X-RateLimit-Remaining"] = str(bucket.remaining)
        raise

    # Add rate limit headers
    if isinstance(response, web.Response):
        response.headers["X-RateLimit-Limit"] = str(burst)
        response.headers["X-RateLimit-Remaining"] = str(bucket.remaining)

    return response


def _get_client_ip(request: web.Request) -> str:
    """Extract client IP, preferring X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    peername = request.transport.get_extra_info("peername")
    if peername:
        return peername[0]
    return "unknown"
