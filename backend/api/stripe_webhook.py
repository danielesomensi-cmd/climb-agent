"""Stripe webhook handler — POST /api/stripe/webhook.

Registered directly on the FastAPI app (not via router) so it can
read the raw request body before any JSON parsing.

Events handled:
    checkout.session.completed      → link stripe_customer_id, set trialing
    customer.subscription.updated   → sync status, period dates, cancel flag
    customer.subscription.deleted   → set canceled
    customer.subscription.trial_will_end → log + founder alert (A232, fires ~3 days before)
    customer.deleted                → clear stripe IDs, mark canceled (B226)
    invoice.payment_succeeded       → set active, update period dates
    invoice.payment_failed          → set past_due

A232: card-free trials — has_payment_method is synced from the Stripe
subscription's default_payment_method on checkout.session.completed and
customer.subscription.updated, so the frontend can show an "Add payment
method" CTA to trialing users without a card.

B226 hardening:
    - Handler exceptions return HTTP 500 → Stripe retries (was: swallowed 200).
    - In-memory LRU dedup of event.id within ~last 1024 events (~hours of traffic).
      Survives in-process Stripe retries; does NOT survive Railway restart.
      Mitigated by the fact that all handlers are upsert-based (naturally idempotent).
    - customer.deleted handled (closes B203 gap).
"""

from __future__ import annotations

import logging
import os
from collections import OrderedDict
from threading import Lock
from typing import Any, Dict, Optional

import stripe
from fastapi import Request
from fastapi.responses import JSONResponse

from backend.engine.subscription_guard import (
    find_subscription_by_stripe_customer,
    find_subscription_by_stripe_subscription_id,
    upsert_subscription,
)

logger = logging.getLogger(__name__)

_STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
_STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# B226: LRU dedup for Stripe event IDs. Stripe sends the same event.id on
# retries, so we can short-circuit duplicate deliveries within the in-process
# window. Persistence would require a Supabase table (deferred — see roadmap).
_EVENT_LRU_MAX = 1024
_processed_events: "OrderedDict[str, None]" = OrderedDict()
_processed_events_lock = Lock()


def _is_event_processed(event_id: str) -> bool:
    """Return True if event_id was processed recently (in-process LRU)."""
    with _processed_events_lock:
        if event_id in _processed_events:
            _processed_events.move_to_end(event_id)
            return True
        return False


def _mark_event_processed(event_id: str) -> None:
    """Record event_id as processed; evict oldest if cache full."""
    with _processed_events_lock:
        _processed_events[event_id] = None
        _processed_events.move_to_end(event_id)
        while len(_processed_events) > _EVENT_LRU_MAX:
            _processed_events.popitem(last=False)


def _reset_event_dedup_for_tests() -> None:
    """Test-only helper to clear the dedup cache between cases."""
    with _processed_events_lock:
        _processed_events.clear()


def _stripe_to_dict(obj: Any) -> Dict[str, Any]:
    """Convert a StripeObject to a plain dict regardless of stripe-python version."""
    if hasattr(obj, "to_dict_recursive"):
        return obj.to_dict_recursive()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return dict(obj)


async def handle_stripe_webhook(request: Request) -> JSONResponse:
    """Validate Stripe signature and dispatch to event handlers."""
    if not _STRIPE_SECRET_KEY:
        return JSONResponse({"error": "Stripe not configured"}, status_code=503)

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # Verify signature
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, _STRIPE_WEBHOOK_SECRET
        )
    except stripe.SignatureVerificationError:
        logger.warning("Stripe webhook: invalid signature")
        return JSONResponse({"error": "Invalid signature"}, status_code=400)
    except Exception as exc:
        logger.error("Stripe webhook construct_event failed: %s", exc)
        return JSONResponse({"error": "Bad request"}, status_code=400)

    # B259: construct_event returns a StripeObject (stripe.Event), which in
    # stripe-python >=8 does NOT support dict.get() — `event.get("id")` raises
    # AttributeError and (being outside the try) 500s every real delivery while
    # dict-mocked tests pass. Convert to a plain dict once so all access is
    # version-agnostic, consistent with how data_object was already handled.
    event_dict = _stripe_to_dict(event)
    event_id = event_dict.get("id") or ""
    event_type = event_dict["type"]
    data_object = event_dict["data"]["object"]

    # DIAG: surface env state on every event so Railway logs show the truth
    import os as _os
    _sb_backend = _os.environ.get("STORAGE_BACKEND", "<unset>")
    _has_stripe_key = bool(_os.environ.get("STRIPE_SECRET_KEY", ""))
    _has_webhook_secret = bool(_os.environ.get("STRIPE_WEBHOOK_SECRET", ""))
    _has_supabase_url = bool(_os.environ.get("SUPABASE_URL", ""))
    _has_supabase_key = bool(_os.environ.get("SUPABASE_SERVICE_KEY", ""))
    logger.info(
        "DIAG stripe_webhook recv event_id=%s event_type=%s | STORAGE_BACKEND=%s stripe_key=%s "
        "webhook_secret=%s supabase_url=%s supabase_key=%s",
        event_id, event_type, _sb_backend, _has_stripe_key,
        _has_webhook_secret, _has_supabase_url, _has_supabase_key,
    )

    # B226: idempotency — short-circuit if Stripe is retrying the same event.
    if event_id and _is_event_processed(event_id):
        logger.info(
            "Stripe webhook: duplicate event_id=%s type=%s — skipping (LRU hit)",
            event_id, event_type,
        )
        return JSONResponse({"received": True, "duplicate": True}, status_code=200)

    # B226: fail-loud — handler exceptions propagate as HTTP 500 so Stripe
    # retries with exponential backoff (was: swallowed with 200, events lost).
    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(data_object)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(data_object)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(data_object)
        elif event_type == "customer.subscription.trial_will_end":
            _handle_trial_will_end(data_object)
        elif event_type == "customer.deleted":
            _handle_customer_deleted(data_object)
        elif event_type == "invoice.payment_succeeded":
            _handle_payment_succeeded(data_object)
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(data_object)
        else:
            logger.info("Stripe webhook: unhandled event type %s", event_type)
    except Exception as exc:
        logger.error(
            "Stripe webhook handler failed event_id=%s type=%s: %s",
            event_id, event_type, exc, exc_info=True,
        )
        # B226: do NOT mark as processed — let Stripe retry.
        return JSONResponse(
            {"error": "handler_failed", "event_id": event_id, "event_type": event_type},
            status_code=500,
        )

    if event_id:
        _mark_event_processed(event_id)

    return JSONResponse({"received": True}, status_code=200)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def _handle_checkout_completed(session: Dict[str, Any]) -> None:
    """checkout.session.completed — link Stripe customer to internal user_id."""
    metadata = session.get("metadata") or {}
    client_ref = session.get("client_reference_id")
    user_id = metadata.get("user_id") or client_ref

    logger.info(
        "DIAG checkout_completed metadata=%s client_reference_id=%s → user_id=%s",
        metadata, client_ref, user_id,
    )

    if not user_id:
        logger.warning("checkout.session.completed: no user_id in metadata or client_reference_id")
        return

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    logger.info(
        "DIAG checkout_completed customer_id=%s subscription_id=%s",
        customer_id, subscription_id,
    )

    # Fetch subscription details from Stripe for trial dates
    trial_start = None
    trial_end = None
    period_start = None
    period_end = None
    has_payment_method = False

    if subscription_id and _STRIPE_SECRET_KEY:
        try:
            client = stripe.StripeClient(_STRIPE_SECRET_KEY)
            sub = _stripe_to_dict(client.subscriptions.retrieve(subscription_id))
            trial_start = _ts(sub.get("trial_start"))
            trial_end = _ts(sub.get("trial_end"))
            period_start = _ts(sub.get("current_period_start"))
            period_end = _ts(sub.get("current_period_end"))
            has_payment_method = bool(sub.get("default_payment_method"))
            logger.info(
                "DIAG checkout_completed sub fetched trial_start=%s trial_end=%s has_pm=%s",
                trial_start, trial_end, has_payment_method,
            )
        except Exception as exc:
            logger.warning("Could not fetch subscription from Stripe: %s", exc)

    upsert_subscription(user_id, {
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "status": "trialing",
        "trial_start": trial_start,
        "trial_end": trial_end,
        "current_period_start": period_start,
        "current_period_end": period_end,
        "has_payment_method": has_payment_method,
    })
    logger.info("checkout.session.completed: user_id=%s linked to customer=%s", user_id, customer_id)

    # Founder alert (fire-and-forget). Must never raise — a 500 here makes
    # Stripe retry the webhook (B226).
    try:
        from backend.api.notifications import notify
        card = "carta inserita" if has_payment_method else "senza carta (A232)"
        notify(
            f"💳 Trial avviato ({card})\n"
            f"User: {user_id}\n"
            f"Customer: {customer_id}"
        )
    except Exception:
        pass


def _handle_subscription_updated(sub: Dict[str, Any]) -> None:
    """customer.subscription.updated — sync status and period dates."""
    subscription_id = sub.get("id")
    customer_id = sub.get("customer")
    stripe_status = sub.get("status")  # Stripe statuses: trialing/active/past_due/canceled/unpaid

    # Map Stripe status to our status vocabulary
    status = _map_stripe_status(stripe_status)

    # Prefer metadata.user_id (propagated via subscription_data.metadata at checkout) —
    # this survives race conditions where the DB row hasn't been linked yet.
    user_id = (sub.get("metadata") or {}).get("user_id")
    if not user_id:
        row = find_subscription_by_stripe_subscription_id(subscription_id)
        if row is None:
            row = find_subscription_by_stripe_customer(customer_id)
        if row is None:
            logger.warning(
                "subscription.updated: no row found for subscription_id=%s customer=%s",
                subscription_id, customer_id,
            )
            return
        user_id = row["user_id"]

    upsert_subscription(user_id, {
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "status": status,
        "trial_start": _ts(sub.get("trial_start")),
        "trial_end": _ts(sub.get("trial_end")),
        "current_period_start": _ts(sub.get("current_period_start")),
        "current_period_end": _ts(sub.get("current_period_end")),
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
        "has_payment_method": bool(sub.get("default_payment_method")),
    })
    logger.info("subscription.updated: user_id=%s status=%s", user_id, status)


def _handle_subscription_deleted(sub: Dict[str, Any]) -> None:
    """customer.subscription.deleted — mark canceled."""
    subscription_id = sub.get("id")
    customer_id = sub.get("customer")

    user_id = (sub.get("metadata") or {}).get("user_id")
    if not user_id:
        row = find_subscription_by_stripe_subscription_id(subscription_id)
        if row is None:
            row = find_subscription_by_stripe_customer(customer_id)
        if row is None:
            logger.warning(
                "subscription.deleted: no row for subscription_id=%s customer=%s",
                subscription_id, customer_id,
            )
            return
        user_id = row["user_id"]

    upsert_subscription(user_id, {"status": "canceled"})
    logger.info("subscription.deleted: user_id=%s → canceled", user_id)


def _handle_trial_will_end(sub: Dict[str, Any]) -> None:
    """customer.subscription.trial_will_end — fires ~3 days before trial end.

    A232 minimum viable: log + founder alert so no-card trials about to expire
    are visible. No DB write, no email — the frontend banner already turns
    urgent at ≤3 days via trial_days_remaining.
    """
    subscription_id = sub.get("id")
    customer_id = sub.get("customer")

    user_id = (sub.get("metadata") or {}).get("user_id")
    if not user_id:
        row = find_subscription_by_stripe_subscription_id(subscription_id)
        if row is None:
            row = find_subscription_by_stripe_customer(customer_id)
        user_id = row["user_id"] if row else None

    has_pm = bool(sub.get("default_payment_method"))
    logger.info(
        "subscription.trial_will_end: user_id=%s subscription_id=%s has_payment_method=%s",
        user_id, subscription_id, has_pm,
    )

    try:
        from backend.api.notifications import notify
        card = "carta inserita" if has_pm else "SENZA carta → cancellerà"
        notify(
            f"⏳ Trial in scadenza tra ~3 giorni ({card})\n"
            f"User: {user_id or '?'}\n"
            f"Subscription: {subscription_id}"
        )
    except Exception:
        pass


def _handle_customer_deleted(customer: Dict[str, Any]) -> None:
    """customer.deleted — clear stripe IDs and mark canceled.

    Triggered when a Stripe customer is deleted (e.g., via dashboard or API).
    Without this handler, the user would retain an active subscription row
    pointing to a non-existent Stripe customer (B203 gap).
    """
    customer_id = customer.get("id")
    if not customer_id:
        logger.warning("customer.deleted: missing customer id")
        return

    row = find_subscription_by_stripe_customer(customer_id)
    if row is None:
        logger.warning(
            "customer.deleted: no subscription row for customer=%s — nothing to update",
            customer_id,
        )
        return

    user_id = row["user_id"]
    upsert_subscription(user_id, {
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "status": "canceled",
        "cancel_at_period_end": False,
    })
    logger.info(
        "customer.deleted: user_id=%s customer=%s → cleared + canceled",
        user_id, customer_id,
    )


def _handle_payment_succeeded(invoice: Dict[str, Any]) -> None:
    """invoice.payment_succeeded — set status=active, update period.

    B275: the trial-start invoice is $0 and "paid" immediately — promoting it
    to active masked the trialing status (no banner, no countdown) and, on
    newer Stripe API versions where the invoice has no top-level
    `subscription`, overwrote stripe_subscription_id with None. A real payment
    is never $0: skip zero-amount invoices entirely.
    """
    if not invoice.get("amount_paid"):
        logger.info(
            "invoice.payment_succeeded: $0 invoice (trial start) — skipping, "
            "status stays trialing"
        )
        return

    subscription_id = invoice.get("subscription")
    customer_id = invoice.get("customer")

    user_id = _resolve_user_id(subscription_id, customer_id)
    if not user_id:
        logger.warning(
            "invoice.payment_succeeded: no row for subscription_id=%s customer=%s",
            subscription_id, customer_id,
        )
        return

    period_start = None
    period_end = None
    lines = (invoice.get("lines") or {}).get("data") or []
    if lines:
        period = lines[0].get("period") or {}
        period_start = _ts(period.get("start"))
        period_end = _ts(period.get("end"))

    fields: Dict[str, Any] = {
        "stripe_customer_id": customer_id,
        "status": "active",
        "current_period_start": period_start,
        "current_period_end": period_end,
    }
    # B275: never clobber a stored subscription id with None (newer Stripe API
    # versions carry the id under parent.subscription_details, not top-level).
    if subscription_id:
        fields["stripe_subscription_id"] = subscription_id
    upsert_subscription(user_id, fields)
    logger.info("invoice.payment_succeeded: user_id=%s → active", user_id)


def _handle_payment_failed(invoice: Dict[str, Any]) -> None:
    """invoice.payment_failed — set status=past_due."""
    subscription_id = invoice.get("subscription")
    customer_id = invoice.get("customer")

    user_id = _resolve_user_id(subscription_id, customer_id)
    if not user_id:
        logger.warning(
            "invoice.payment_failed: no row for subscription_id=%s customer=%s",
            subscription_id, customer_id,
        )
        return

    upsert_subscription(user_id, {
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "status": "past_due",
    })
    logger.info("invoice.payment_failed: user_id=%s → past_due", user_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_user_id(
    subscription_id: "str | None",
    customer_id: "str | None",
) -> "str | None":
    """Resolve internal user_id for invoice events.

    Priority:
    1. DB lookup by stripe_subscription_id (fast path post-checkout)
    2. DB lookup by stripe_customer_id
    3. Stripe API: retrieve subscription → read metadata.user_id
       (set via subscription_data.metadata at checkout creation)
    4. Stripe API: list checkout sessions → read client_reference_id
       (last resort for legacy rows without subscription metadata)
    """
    if subscription_id:
        row = find_subscription_by_stripe_subscription_id(subscription_id)
        if row:
            return row["user_id"]
    if customer_id:
        row = find_subscription_by_stripe_customer(customer_id)
        if row:
            return row["user_id"]

    # Stripe API fallback — handles race condition where invoice.payment_succeeded
    # arrives before checkout.session.completed has written the Stripe IDs to DB.
    if subscription_id and _STRIPE_SECRET_KEY:
        try:
            client = stripe.StripeClient(_STRIPE_SECRET_KEY)
            sub = _stripe_to_dict(client.subscriptions.retrieve(subscription_id))
            uid = (sub.get("metadata") or {}).get("user_id")
            if uid:
                logger.info("_resolve_user_id: found user_id=%s via subscription metadata", uid)
                return uid
        except Exception as exc:
            logger.warning("_resolve_user_id: could not retrieve subscription: %s", exc)

    if customer_id and _STRIPE_SECRET_KEY:
        try:
            client = stripe.StripeClient(_STRIPE_SECRET_KEY)
            sessions = client.checkout.sessions.list({"customer": customer_id, "limit": 5})
            for s in (sessions.data or []):
                s_dict = _stripe_to_dict(s)
                uid = s_dict.get("client_reference_id")
                if uid:
                    logger.info("_resolve_user_id: found user_id=%s via checkout client_reference_id", uid)
                    return uid
        except Exception as exc:
            logger.warning("_resolve_user_id: could not list checkout sessions: %s", exc)

    return None


def _ts(unix_ts) -> str | None:
    """Convert a Unix timestamp (int) to ISO-8601 string, or None."""
    if unix_ts is None:
        return None
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _map_stripe_status(stripe_status: str | None) -> str:
    """Map Stripe subscription status to our internal vocabulary."""
    _map = {
        "trialing": "trialing",
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
        "incomplete": "pending_checkout",
        "incomplete_expired": "expired",
        "paused": "active",  # treat paused as active (read access)
    }
    return _map.get(stripe_status or "", "past_due")
