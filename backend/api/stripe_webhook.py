"""Stripe webhook handler — POST /api/stripe/webhook.

Registered directly on the FastAPI app (not via router) so it can
read the raw request body before any JSON parsing.

Events handled:
    checkout.session.completed      → link stripe_customer_id, set trialing
    customer.subscription.updated   → sync status, period dates, cancel flag
    customer.subscription.deleted   → set canceled
    invoice.payment_succeeded       → set active, update period dates
    invoice.payment_failed          → set past_due
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

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

    event_type = event["type"]
    data_object = event["data"]["object"]

    logger.info("Stripe webhook received: %s", event_type)

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(data_object)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(data_object)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(data_object)
        elif event_type == "invoice.payment_succeeded":
            _handle_payment_succeeded(data_object)
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(data_object)
        else:
            logger.debug("Stripe webhook: unhandled event type %s", event_type)
    except Exception as exc:
        logger.error("Error handling Stripe webhook %s: %s", event_type, exc)
        # Return 200 anyway — Stripe will not retry on 200
        # Log the error for alerting

    return JSONResponse({"received": True}, status_code=200)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def _handle_checkout_completed(session: Dict[str, Any]) -> None:
    """checkout.session.completed — link Stripe customer to internal user_id."""
    user_id = (session.get("metadata") or {}).get("user_id")
    if not user_id:
        logger.warning("checkout.session.completed: no user_id in metadata")
        return

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    # Fetch subscription details from Stripe for trial dates
    trial_start = None
    trial_end = None
    period_start = None
    period_end = None

    if subscription_id and _STRIPE_SECRET_KEY:
        try:
            client = stripe.StripeClient(_STRIPE_SECRET_KEY)
            sub = client.subscriptions.retrieve(subscription_id)
            trial_start = _ts(sub.get("trial_start"))
            trial_end = _ts(sub.get("trial_end"))
            period_start = _ts((sub.get("current_period_start")))
            period_end = _ts(sub.get("current_period_end"))
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
    })
    logger.info("checkout.session.completed: user_id=%s linked to customer=%s", user_id, customer_id)


def _handle_subscription_updated(sub: Dict[str, Any]) -> None:
    """customer.subscription.updated — sync status and period dates."""
    subscription_id = sub.get("id")
    customer_id = sub.get("customer")
    stripe_status = sub.get("status")  # Stripe statuses: trialing/active/past_due/canceled/unpaid

    # Map Stripe status to our status vocabulary
    status = _map_stripe_status(stripe_status)

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
        "stripe_subscription_id": subscription_id,
        "status": status,
        "trial_start": _ts(sub.get("trial_start")),
        "trial_end": _ts(sub.get("trial_end")),
        "current_period_start": _ts(sub.get("current_period_start")),
        "current_period_end": _ts(sub.get("current_period_end")),
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
    })
    logger.info("subscription.updated: user_id=%s status=%s", user_id, status)


def _handle_subscription_deleted(sub: Dict[str, Any]) -> None:
    """customer.subscription.deleted — mark canceled."""
    subscription_id = sub.get("id")
    customer_id = sub.get("customer")

    row = find_subscription_by_stripe_subscription_id(subscription_id)
    if row is None:
        row = find_subscription_by_stripe_customer(customer_id)
    if row is None:
        logger.warning(
            "subscription.deleted: no row for subscription_id=%s customer=%s",
            subscription_id, customer_id,
        )
        return

    upsert_subscription(row["user_id"], {"status": "canceled"})
    logger.info("subscription.deleted: user_id=%s → canceled", row["user_id"])


def _handle_payment_succeeded(invoice: Dict[str, Any]) -> None:
    """invoice.payment_succeeded — set status=active, update period."""
    subscription_id = invoice.get("subscription")
    customer_id = invoice.get("customer")

    row = find_subscription_by_stripe_subscription_id(subscription_id)
    if row is None:
        row = find_subscription_by_stripe_customer(customer_id)
    if row is None:
        logger.warning(
            "invoice.payment_succeeded: no row for subscription_id=%s customer=%s",
            subscription_id, customer_id,
        )
        return

    # Fetch updated period from Stripe
    period_start = None
    period_end = None
    lines = (invoice.get("lines") or {}).get("data") or []
    if lines:
        period = lines[0].get("period") or {}
        period_start = _ts(period.get("start"))
        period_end = _ts(period.get("end"))

    upsert_subscription(row["user_id"], {
        "status": "active",
        "current_period_start": period_start,
        "current_period_end": period_end,
    })
    logger.info("invoice.payment_succeeded: user_id=%s → active", row["user_id"])


def _handle_payment_failed(invoice: Dict[str, Any]) -> None:
    """invoice.payment_failed — set status=past_due."""
    subscription_id = invoice.get("subscription")
    customer_id = invoice.get("customer")

    row = find_subscription_by_stripe_subscription_id(subscription_id)
    if row is None:
        row = find_subscription_by_stripe_customer(customer_id)
    if row is None:
        logger.warning(
            "invoice.payment_failed: no row for subscription_id=%s customer=%s",
            subscription_id, customer_id,
        )
        return

    upsert_subscription(row["user_id"], {"status": "past_due"})
    logger.info("invoice.payment_failed: user_id=%s → past_due", row["user_id"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
