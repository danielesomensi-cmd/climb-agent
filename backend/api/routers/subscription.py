"""Subscription router — Stripe checkout, portal, and status endpoints."""

from __future__ import annotations

import logging
import os
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_user_id
from backend.engine.subscription_guard import (
    _ACTIVE_STATUSES,
    _parse_ts,
    check_subscription,
    get_subscription_row,
    is_local_trial,
    upsert_subscription,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscription", tags=["subscription"])

_STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
_STRIPE_PRICE_ID_STANDARD = os.environ.get("STRIPE_PRICE_ID_STANDARD", "")
_STRIPE_PRICE_ID_FOUNDER = os.environ.get("STRIPE_PRICE_ID_FOUNDER", "")
_STRIPE_PORTAL_ENABLED = os.environ.get("STRIPE_PORTAL_ENABLED", "true").lower() == "true"

_ALLOWED_PRICE_IDS = {pid for pid in (_STRIPE_PRICE_ID_STANDARD, _STRIPE_PRICE_ID_FOUNDER) if pid}

_FRONTEND_BASE = os.environ.get(
    "FRONTEND_BASE_URL", "https://climbagent.app"
)


def _stripe_client() -> stripe.StripeClient:
    if not _STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Stripe not configured",
        )
    return stripe.StripeClient(_STRIPE_SECRET_KEY)


# ---------------------------------------------------------------------------
# GET /api/subscription/status
# ---------------------------------------------------------------------------

@router.get("/status")
def get_subscription_status(user_id: Optional[str] = Depends(get_user_id)):
    """Return current subscription status and trial info."""
    result = check_subscription(user_id)
    return result


# ---------------------------------------------------------------------------
# POST /api/subscription/checkout
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    email: Optional[str] = None  # prefill Stripe Checkout; frontend passes Clerk email
    price_id: Optional[str] = None  # frontend sends the selected tier's price ID


@router.post("/checkout")
def create_checkout_session(
    req: CheckoutRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Create a Stripe Checkout Session and return the hosted URL.

    - mode: subscription
    - 15-day trial without card (A232): payment_method_collection=if_required;
      trial ends with no card on file → subscription cancels cleanly (no
      invoice, no dunning) and the fail-closed guard (B202) takes over.
    - One trial per user, ever: a row with trial_end already set means the
      trial was consumed — the new checkout charges immediately (Stripe then
      requires the card because an amount is due).
    - Redirects back to /today on success/cancel
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not _STRIPE_PRICE_ID_STANDARD:
        raise HTTPException(status_code=503, detail="Stripe price not configured")

    # Validate price_id — only allow known prices, fallback to standard
    price_id = req.price_id
    if not price_id or price_id not in _ALLOWED_PRICE_IDS:
        if price_id:
            logger.warning("Unknown price_id received: %s — falling back to standard", price_id)
        price_id = _STRIPE_PRICE_ID_STANDARD

    client = _stripe_client()

    # Check if user already has a stripe_customer_id
    row = get_subscription_row(user_id)

    # A250: a local trial (auto-started at onboarding, no Stripe objects) must
    # NOT short-circuit — checkout is exactly how that user subscribes/adds a
    # card. Stripe-managed trialing/active rows keep the B212 short-circuit.
    local_trial = is_local_trial(row)

    # B212: short-circuit if user is already trialing/active.  Prevents the
    # incondizional "pending_checkout" upsert below from clobbering a live
    # trial/subscription when the frontend re-hits /checkout (e.g. after
    # Reset & Restart or a misrouted /subscribe tap).  Users with past_due
    # or canceled can still proceed to checkout.
    if row and row.get("status") in _ACTIVE_STATUSES and not local_trial:
        return {
            "already_active": True,
            "status": row.get("status"),
            "redirect_url": "/today",
        }

    existing_customer_id: Optional[str] = row.get("stripe_customer_id") if row else None

    # A232 anti-abuse: trial_end set on the row (past or future) means this
    # user already consumed their one trial — do not grant another. Abandoned
    # checkouts (pending_checkout rows) have no trial_end and keep full trial.
    trial_already_used = bool(row and row.get("trial_end"))

    subscription_data: dict = {
        # Propagated to the Subscription object — survives race conditions
        # where invoice events arrive before checkout.session.completed.
        "metadata": {"user_id": user_id},
    }
    if local_trial:
        # A250: carry the REMAINING local-trial days into the Stripe
        # subscription (no double trial, no lost days). Stripe Checkout
        # requires trial_end ≥ 48h in the future — with less than that left,
        # the subscription starts immediately (no trial), same as expired.
        from datetime import datetime, timedelta, timezone
        trial_end = _parse_ts(row.get("trial_end"))
        if trial_end and trial_end > datetime.now(timezone.utc) + timedelta(hours=48):
            subscription_data["trial_end"] = int(trial_end.timestamp())
            subscription_data["trial_settings"] = {
                "end_behavior": {"missing_payment_method": "cancel"},
            }
    elif not trial_already_used:
        subscription_data["trial_period_days"] = 15
        subscription_data["trial_settings"] = {
            "end_behavior": {"missing_payment_method": "cancel"},
        }

    checkout_params: dict = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "subscription_data": subscription_data,
        "success_url": f"{_FRONTEND_BASE}/today?checkout=success",
        "cancel_url": f"{_FRONTEND_BASE}/today?checkout=canceled",
        "allow_promotion_codes": True,
        "payment_method_types": ["card"],
        # A232: no card during the free trial; Stripe still collects one when
        # an amount is due (i.e. trial already consumed → immediate charge).
        "payment_method_collection": "if_required",
        # Stripe-native field — surfaced on checkout session and child sessions.
        "client_reference_id": user_id,
        "metadata": {"user_id": user_id},
    }

    if existing_customer_id:
        checkout_params["customer"] = existing_customer_id
    elif req.email:
        checkout_params["customer_email"] = req.email

    try:
        session = client.checkout.sessions.create(checkout_params)
    except stripe.InvalidRequestError as exc:
        if "No such customer" in str(exc) and existing_customer_id:
            logger.warning(
                "Stale stripe_customer_id %s for user %s — clearing and retrying",
                existing_customer_id, user_id,
            )
            upsert_subscription(user_id, {"stripe_customer_id": None})
            del checkout_params["customer"]
            if not req.email:
                raise HTTPException(
                    status_code=500,
                    detail="Stripe customer was deleted and no email available to create a new one. "
                           "Please retry from a page where your email is available.",
                )
            checkout_params["customer_email"] = req.email
            session = client.checkout.sessions.create(checkout_params)
        else:
            raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")
    except stripe.StripeError as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")

    # Mark subscription as pending_checkout (row created here if not yet existing).
    # A250: NOT for a local trial — abandoning the checkout must not demote a
    # running trial to pending_checkout (the webhook overwrites the row anyway
    # when the checkout completes).
    if not local_trial:
        upsert_subscription(user_id, {"status": "pending_checkout"})

    return {"checkout_url": session.url}


# ---------------------------------------------------------------------------
# POST /api/subscription/portal
# ---------------------------------------------------------------------------

@router.post("/portal")
def create_billing_portal(user_id: Optional[str] = Depends(get_user_id)):
    """Create a Stripe Customer Portal session for managing/canceling subscription."""
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not _STRIPE_PORTAL_ENABLED:
        raise HTTPException(status_code=503, detail="Billing portal not enabled")

    row = get_subscription_row(user_id)
    customer_id = row.get("stripe_customer_id") if row else None

    # A250: a local trial has no Stripe customer yet — "Add payment method"
    # from the trial banner lands here. Serve a Checkout session instead of a
    # portal: it collects the card (payment_method_collection=always, the
    # user's explicit intent) and carries over the remaining trial days, so
    # completing it converts the local trial into a Stripe-managed one.
    if not customer_id and is_local_trial(row):
        if not _STRIPE_PRICE_ID_STANDARD:
            raise HTTPException(status_code=503, detail="Stripe price not configured")
        from datetime import datetime, timedelta, timezone
        subscription_data: dict = {"metadata": {"user_id": user_id}}
        trial_end = _parse_ts(row.get("trial_end"))
        if trial_end and trial_end > datetime.now(timezone.utc) + timedelta(hours=48):
            subscription_data["trial_end"] = int(trial_end.timestamp())
            subscription_data["trial_settings"] = {
                "end_behavior": {"missing_payment_method": "cancel"},
            }
        client = _stripe_client()
        try:
            session = client.checkout.sessions.create({
                "mode": "subscription",
                "line_items": [{"price": _STRIPE_PRICE_ID_STANDARD, "quantity": 1}],
                "subscription_data": subscription_data,
                "success_url": f"{_FRONTEND_BASE}/settings?billing=updated",
                "cancel_url": f"{_FRONTEND_BASE}/settings",
                "allow_promotion_codes": True,
                "payment_method_types": ["card"],
                "payment_method_collection": "always",
                "client_reference_id": user_id,
                "metadata": {"user_id": user_id},
            })
        except stripe.StripeError as exc:
            raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")
        return {"portal_url": session.url}

    if not customer_id:
        raise HTTPException(
            status_code=404,
            detail="No active subscription found. Complete checkout first.",
        )

    client = _stripe_client()
    try:
        portal = client.billing_portal.sessions.create(
            {
                "customer": customer_id,
                "return_url": f"{_FRONTEND_BASE}/settings",
            }
        )
    except stripe.InvalidRequestError as exc:
        if "No such customer" in str(exc):
            logger.warning(
                "Stale stripe_customer_id %s for user %s in portal — clearing",
                customer_id, user_id,
            )
            upsert_subscription(user_id, {"stripe_customer_id": None})
            raise HTTPException(
                status_code=404,
                detail="Subscription not found. The linked Stripe customer no longer exists.",
            )
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")
    except stripe.StripeError as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")

    return {"portal_url": portal.url}
