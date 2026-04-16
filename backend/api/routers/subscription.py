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
    check_subscription,
    get_subscription_row,
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
    "FRONTEND_BASE_URL", "https://climb-agent.vercel.app"
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
    - 15-day trial (card required upfront)
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
    existing_customer_id: Optional[str] = row.get("stripe_customer_id") if row else None

    checkout_params: dict = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "subscription_data": {
            "trial_period_days": 15,
            # Propagated to the Subscription object — survives race conditions
            # where invoice events arrive before checkout.session.completed.
            "metadata": {"user_id": user_id},
        },
        "success_url": f"{_FRONTEND_BASE}/today?checkout=success",
        "cancel_url": f"{_FRONTEND_BASE}/today?checkout=canceled",
        "allow_promotion_codes": True,
        "payment_method_types": ["card"],
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
    except stripe.StripeError as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")

    # Mark subscription as pending_checkout (row created here if not yet existing)
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
    except stripe.StripeError as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")

    return {"portal_url": portal.url}
