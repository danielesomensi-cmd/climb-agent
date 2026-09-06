"""Subscription guard — check and enforce Stripe subscription status.

Design:
- If SUBSCRIPTION_ENFORCED=0 → bypass all checks (A285, billing paused).
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

# A285: billing pause switch. Same shape as RATE_LIMIT_ENABLED (rate_limit.py):
# default ON, and ONLY the literal "0" turns it off — a missing, empty or
# misspelled value leaves the paywall standing. Read at import time like its
# two siblings above, so flipping it needs a restart (on Railway, changing the
# variable redeploys anyway).
_SUBSCRIPTION_ENFORCED = os.environ.get("SUBSCRIPTION_ENFORCED", "1") != "0"


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

    from backend.engine.log_utils import mask_uid

    _log = _logging.getLogger(__name__)
    # B285/SEC-4: DEBUG + masked id — this fired at INFO on every webhook.
    _log.debug(
        "upsert_subscription called user_id=%s fields_keys=%s supabase_enabled=%s",
        mask_uid(user_id), list(fields.keys()), _supabase_enabled(),
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
        _log.debug(
            "upsert_subscription OK user_id=%s result_count=%s",
            mask_uid(user_id), len(result.data or []),
        )
    except Exception as exc:
        _log.error("upsert_subscription FAILED user_id=%s: %s", mask_uid(user_id), exc, exc_info=True)
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
# Local trial (A250)
# ---------------------------------------------------------------------------

TRIAL_DAYS = 15


def is_local_trial(row: Optional[Dict[str, Any]]) -> bool:
    """A250: a trial provisioned server-side at onboarding — no Stripe objects
    behind it. Stripe-managed rows always carry stripe_subscription_id."""
    return bool(
        row
        and row.get("status") == "trialing"
        and not row.get("stripe_subscription_id")
    )


def start_trial_if_new(user_id: str) -> bool:
    """A250: auto-start the 15-day free trial at onboarding completion.

    No Stripe objects are created — the row alone drives check_subscription.
    Stripe enters the picture only when the user adds a payment method /
    subscribes (checkout carries over the remaining trial days). Expiry is
    enforced lazily by check_subscription (no webhook exists for local rows).

    Idempotent and conservative: never overwrites an existing row (a returning
    user who re-onboards keeps their consumed/canceled trial — A232 one trial
    per user, ever). Returns True only when a fresh trial row was created.
    """
    # A285: with billing paused, a trial grants nothing — access is already
    # free. Starting one anyway would burn the user's single lifetime trial
    # (A232) on 15 days they never spent behind a paywall, and they would find
    # the wall the day enforcement comes back: exactly the TRIAL-LOCKOUT shape
    # B331 had to repair by hand. No row means their first checkout after the
    # pause still gets the full 15 days (subscription.py trial_already_used).
    if not _SUBSCRIPTION_ENFORCED:
        return False
    if not _stripe_enabled() or not _supabase_enabled():
        return False  # dev/test: guard bypasses anyway
    if get_subscription_row(user_id) is not None:
        return False
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    upsert_subscription(user_id, {
        "status": "trialing",
        "trial_start": now.isoformat(),
        "trial_end": (now + timedelta(days=TRIAL_DAYS)).isoformat(),
        "has_payment_method": False,
    })
    return True


def _parse_ts(value: Any) -> Optional[datetime]:
    """Parse an ISO timestamp from the DB, normalizing Z and naive values."""
    if not value or not isinstance(value, str):
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        ts = datetime.fromisoformat(value)
        return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
    except ValueError:
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
        enforced             bool — A285: is the paywall switched on at all?
                             Lets a caller tell "active because they pay" from
                             "active because billing is paused" — the two are
                             indistinguishable from the other fields.

    Bypass cases (returns ALLOW_ALL):
    - SUBSCRIPTION_ENFORCED=0 (A285, billing paused — the only bypass that
      applies with Stripe fully configured in production)
    - Stripe not configured (dev/test)
    - STORAGE_BACKEND != 'supabase' (pytest)
    - user_id is None *in that same dev/test configuration only*

    Fail-closed (returns DENY_ALL) — when Stripe IS configured and enforced:
    - No subscription row in DB → user must subscribe
    - user_id is None → anonymous request (B285/SEC-2). Previously this
      fell through to ALLOW_ALL, letting unauthenticated traffic past every
      gated endpoint — including the paid LLM call in /api/coach/chat, which
      runs before any persistence. deps.get_user_id now 401s first; this is
      defense in depth for any non-HTTP caller.
    """
    result = _check_entitlement(user_id)
    result["enforced"] = _SUBSCRIPTION_ENFORCED
    return result


def _check_entitlement(user_id: Optional[str]) -> Dict[str, Any]:
    """Entitlement decision, without the A285 `enforced` annotation."""
    # A285: billing paused — everyone is entitled, and no DB read is needed to
    # know it. Deliberately ahead of the user_id check: the anonymous DENY of
    # B285/SEC-2 is about authentication, which get_user_id already enforces
    # with a 401 before this runs.
    if not _SUBSCRIPTION_ENFORCED:
        return _ALLOW_ALL.copy()

    if not _stripe_enabled() or not _supabase_enabled():
        return _ALLOW_ALL.copy()

    if not user_id:
        return _DENY_ALL.copy()

    # Founder / beta bypass — managed via BYPASS_USER_IDS env var
    if user_id in _BYPASS_USER_IDS:
        return _ALLOW_ALL.copy()

    row = get_subscription_row(user_id)
    if row is None:
        return _DENY_ALL.copy()

    status = row.get("status", "none")

    # A250 lazy expiry: local trials have no Stripe subscription behind them,
    # so no webhook will ever flip the status — enforce trial_end here.
    # Stripe-managed rows (stripe_subscription_id set) are excluded: their
    # transitions belong to webhooks, and a lagging webhook must not lock out
    # a user whose trial just converted to active.
    if is_local_trial(row):
        trial_end = _parse_ts(row.get("trial_end"))
        if trial_end is None or trial_end <= datetime.now(timezone.utc):
            return {
                "status": "expired",
                "is_active": False,
                "trial_days_remaining": 0,
                "can_interact": False,
                "has_payment_method": False,
            }

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
