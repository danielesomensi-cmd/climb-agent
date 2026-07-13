"""Subscription guard — check and enforce Stripe subscription status.

Design:
- If STRIPE_SECRET_KEY is not set → bypass all checks (dev/test mode).
- If STORAGE_BACKEND != 'supabase' → bypass (pytest uses file backend).
- If no subscription row in DB + Stripe configured → deny (fail-closed).
- status trialing/active → allow full access.
- status past_due/canceled/expired → block interactive actions (402).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
_STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "file")


def _load_bypass_user_ids() -> set[str]:
    """Load user IDs that bypass subscription checks (founder, beta testers)."""
    raw = os.environ.get("BYPASS_USER_IDS", "")
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


_BYPASS_USER_IDS: set[str] = _load_bypass_user_ids()


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
    import logging as _logging
    _log = _logging.getLogger(__name__)
    _log.info(
        "DIAG upsert_subscription called user_id=%s fields_keys=%s supabase_enabled=%s",
        user_id, list(fields.keys()), _supabase_enabled(),
    )
    if not _supabase_enabled():
        _log.warning(
            "DIAG upsert_subscription NO-OP: supabase not enabled "
            "(STORAGE_BACKEND=%s). Row will NOT be written.",
            _STORAGE_BACKEND,
        )
        return
    from backend.engine.storage_supabase import _sb
    payload = {"user_id": user_id, **fields}
    try:
        result = _sb().table("subscriptions").upsert(payload, on_conflict="user_id").execute()
        _log.info("DIAG upsert_subscription OK user_id=%s result_count=%s", user_id, len(result.data or []))
    except Exception as exc:
        _log.error("DIAG upsert_subscription FAILED user_id=%s: %s", user_id, exc, exc_info=True)
        raise


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
    "has_payment_method": True,
}

_DENY_ALL: Dict[str, Any] = {
    "status": "none",
    "is_active": False,
    "trial_days_remaining": None,
    "can_interact": False,
    "has_payment_method": False,
}


def check_subscription(user_id: Optional[str]) -> Dict[str, Any]:
    """Return subscription status for a user.

    Returns a dict:
        status               str — 'none'|'trialing'|'active'|'past_due'|'canceled'|'expired'
        is_active            bool — status in (trialing, active)
        trial_days_remaining int|None — days left if trialing
        can_interact         bool — same as is_active
        has_payment_method   bool — card on file (A232; synced by webhooks)

    Bypass cases (returns ALLOW_ALL) — only when Stripe is NOT configured:
    - Stripe not configured (dev/test)
    - STORAGE_BACKEND != 'supabase' (pytest)
    - user_id is None (unauthenticated dev request)

    Fail-closed (returns DENY_ALL) — when Stripe IS configured:
    - No subscription row in DB → user must subscribe
    """
    if not _stripe_enabled() or not _supabase_enabled() or not user_id:
        return _ALLOW_ALL.copy()

    # Founder / beta bypass — managed via BYPASS_USER_IDS env var
    if user_id in _BYPASS_USER_IDS:
        return _ALLOW_ALL.copy()

    row = get_subscription_row(user_id)
    if row is None:
        return _DENY_ALL.copy()

    status = row.get("status", "none")
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
        "has_payment_method": bool(row.get("has_payment_method")),
    }
