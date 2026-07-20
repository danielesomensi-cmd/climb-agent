"""Clerk JWT verification and user lookup.

Flow:
1. Frontend sends Authorization: Bearer <clerk_jwt>
2. Backend verifies signature via Clerk JWKS
3. Extracts clerk_user_id from JWT 'sub' claim
4. Looks up user_id in Supabase via clerk_id column
5. If not found → creates new user (generates UUID, links clerk_id)

When CLERK_JWKS_URL is not set (dev/test), this module is a no-op
and deps.py falls back to X-User-ID header.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from functools import lru_cache
from typing import Optional

import jwt
from jwt import PyJWKClient

from backend.engine import storage
from backend.engine.log_utils import mask_uid

logger = logging.getLogger(__name__)

CLERK_JWKS_URL = os.environ.get("CLERK_JWKS_URL", "")


def is_clerk_configured() -> bool:
    """Return True if Clerk env vars are set (production)."""
    return bool(CLERK_JWKS_URL)


@lru_cache(maxsize=1)
def _get_jwk_client() -> PyJWKClient:
    return PyJWKClient(CLERK_JWKS_URL)


def verify_clerk_token(token: str) -> dict:
    """Verify a Clerk JWT and return the payload.

    Raises jwt.exceptions.PyJWTError if the token is invalid.
    """
    jwk_client = _get_jwk_client()
    signing_key = jwk_client.get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"verify_aud": False},  # Clerk doesn't use audience by default
    )
    return payload


def get_clerk_user_id(token: str) -> str:
    """Extract the Clerk user ID (sub claim) from a JWT."""
    payload = verify_clerk_token(token)
    return payload["sub"]


_clerk_id_cache: dict[str, tuple[str, float]] = {}  # {clerk_id: (user_id, timestamp)}
_CACHE_TTL = 300  # 5 minutes


def lookup_or_create_user(clerk_id: str) -> str:
    """Find the internal user_id for a clerk_id, or create a new user.

    Results are cached in-memory for _CACHE_TTL seconds — the mapping
    clerk_id → user_id is immutable after creation, so this is safe.
    """
    now = time.time()
    cached = _clerk_id_cache.get(clerk_id)
    if cached and now - cached[1] < _CACHE_TTL:
        return cached[0]

    from backend.engine.storage_supabase import _sb

    result = _sb().table("users").select("user_id").eq("clerk_id", clerk_id).execute()
    if result.data:
        user_id = result.data[0]["user_id"]
        _clerk_id_cache[clerk_id] = (user_id, now)
        return user_id

    # New user — generate UUID + bootstrap empty state
    new_user_id = str(uuid.uuid4())
    _sb().table("users").insert({
        "user_id": new_user_id,
        "clerk_id": clerk_id,
        "state": {},
    }).execute()
    # B285/SEC-4: identifiers are masked — a full internal UUID in the log
    # stream is an account-recovery vector, not a debugging aid.
    logger.info(
        "Created new user %s for clerk_id %s",
        mask_uid(new_user_id), mask_uid(clerk_id),
    )
    _clerk_id_cache[clerk_id] = (new_user_id, now)
    return new_user_id
