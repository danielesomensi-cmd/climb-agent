"""Subscription guard — check and enforce Stripe subscription status.

Design:
- If STRIPE_SECRET_KEY is not set → bypass all checks (dev/test mode).
- If STORAGE_BACKEND != 'supabase' → bypass (pytest uses file backend).
- If no subscription row in DB → user hasn't checked out yet → allow.
- status trialing/active → allow full access.
- status past_due/canceled/expired → block interactive actions (402).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
_STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "file")


def _stripe_enabled() -> bool:
    return bool(_STRIPE_KEY)


def _supabase_enabled() -> bool:
    return _STORAGE_BACKEND == "supabase"


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def get_subscription_row(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the subscription row for user_id. Returns None if not found."""
    if not _supabase_enabled():
        return None
    from backend.engine.storage_supabase import _sb
    r = _sb().table("subscriptions").select("*").eq("user_id", user_id).limit(1).execute()
    if r.data:
        return r.data[0]
    return None


def upsert_subscription(user_id: str, fields: Dict[str, Any]) -> None:
    """Create or update subscription row for user_id."""
    if not _supabase_enabled():
        return
    from backend.engine.storage_supabase import _sb
    payload = {"user_id": user_id, **fields}
    _sb().table("subscriptions").upsert(payload, on_conflict="user_id").execute()


def find_subscription_by_stripe_customer(stripe_customer_id: str) -> Optional[Dict[str, Any]]:
    """Fetch subscription row by stripe_customer_id."""
    if not _supabase_enabled():
        return None
    from backend.engine.storage_supabase import _sb
    r = (
        _sb()
        .table("subscriptions")
        .select("*")
        .eq("stripe_customer_id", stripe_customer_id)
        .limit(1)
        .execute()
    )
    if r.data:
        return r.data[0]
    return None


def find_subscription_by_stripe_subscription_id(
    stripe_subscription_id: str,
) -> Optional[Dict[str, Any]]:
    """Fetch subscription row by stripe_subscription_id."""
    if not _supabase_enabled():
        return None
    from backend.engine.storage_supabase import _sb
    r = (
        _sb()
        .table("subscriptions")
        .select("*")
        .eq("stripe_subscription_id", stripe_subscription_id)
        .limit(1)
        .execute()
    )
    if r.data:
        return r.data[0]
    return None


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------

_ACTIVE_STATUSES = {"trialing", "active"}

_ALLOW_ALL: Dict[str, Any] = {
    "status": "active",
    "is_active": True,
    "trial_days_remaining": None,
    "can_interact": True,
}


def check_subscription(user_id: Optional[str]) -> Dict[str, Any]:
    """Return subscription status for a user.

    Returns a dict:
        status               str — 'trialing'|'active'|'past_due'|'canceled'|'expired'
        is_active            bool — status in (trialing, active)
        trial_days_remaining int|None — days left if trialing
        can_interact         bool — same as is_active

    Bypass cases (returns ALLOW_ALL):
    - Stripe not configured (dev/test)
    - STORAGE_BACKEND != 'supabase' (pytest)
    - user_id is None (unauthenticated dev request)
    - No subscription row (user hasn't completed checkout yet = still onboarding)
    """
    if not _stripe_enabled() or not _supabase_enabled() or not user_id:
        return _ALLOW_ALL.copy()

    row = get_subscription_row(user_id)
    if row is None:
        # No row = not onboarded yet = full access
        return _ALLOW_ALL.copy()

    status = row.get("status", "active")
    is_active = status in _ACTIVE_STATUSES

    trial_days_remaining: Optional[int] = None
    if status == "trialing" and row.get("trial_end"):
        try:
            trial_end_str = row["trial_end"]
            # Normalize timezone
            if trial_end_str.endswith("Z"):
                trial_end_str = trial_end_str[:-1] + "+00:00"
            trial_end = datetime.fromisoformat(trial_end_str)
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=timezone.utc)
            delta = trial_end - datetime.now(timezone.utc)
            trial_days_remaining = max(0, delta.days)
        except (ValueError, TypeError):
            pass

    return {
        "status": status,
        "is_active": is_active,
        "trial_days_remaining": trial_days_remaining,
        "can_interact": is_active,
    }
