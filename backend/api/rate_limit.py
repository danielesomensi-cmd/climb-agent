"""B165d: Rate limiter instance — shared across routers."""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

# A245 E-1 (B4) — the limiter used to key on `get_remote_address`, which behind
# Railway's load balancer is the PROXY's IP, identical for every user. That made
# `PUT /api/state` 30/min, `POST /api/feedback` 30/min and `/api/user/recover`
# 5/min effectively GLOBAL limits: one busy user could 429 everyone else, and
# gym peak hours are exactly when several users hit feedback at once.
#
# Priority: the authenticated identity when we have one (a real per-user limit
# that a shared IP cannot dilute), then the client IP parsed out of
# X-Forwarded-For, then the peer address.


def _client_ip(request: Request) -> str:
    """Left-most entry of X-Forwarded-For — the original client, not the proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return get_remote_address(request)


def rate_limit_key(request: Request) -> str:
    """Per-user where possible, per-client-IP otherwise.

    `request.state.user_id` is set by the auth dependency for authenticated
    routes. It is deliberately read defensively: the limiter runs on unauth'd
    routes too (e.g. /api/user/recover, which is the one an attacker would
    hammer), and those must still be limited by IP rather than silently sharing
    one bucket.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{_client_ip(request)}"


limiter = Limiter(
    key_func=rate_limit_key,
    enabled=os.environ.get("RATE_LIMIT_ENABLED", "1") != "0",
)
