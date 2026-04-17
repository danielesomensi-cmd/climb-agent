"""B212 — /api/subscription/checkout guard tests.

Covers the short-circuit that prevents POST /api/subscription/checkout from
overwriting an already `trialing`/`active` subscription row with
`pending_checkout`.

All tests mock Stripe at two layers:
  - `_STRIPE_PRICE_ID_STANDARD`, `_STRIPE_PRICE_ID_FOUNDER`, `_ALLOWED_PRICE_IDS`
    in the router module (set during import from env) — patched to non-empty
    values so the 503 pre-check passes.
  - `backend.api.routers.subscription.stripe.StripeClient` — patched so the
    Stripe SDK is never called over the network.

`get_subscription_row` / `upsert_subscription` are patched directly in the
router module so we control the row state and observe writes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_PRICE_STANDARD = "price_test_standard"
_FAKE_PRICE_FOUNDER = "price_test_founder"
_TEST_USER_ID = "00000000-0000-4000-a000-000000000212"


def _patched_router(upsert_spy: MagicMock, row: dict | None):
    """Patch the subscription router module so Stripe envvars look configured.

    Returns a context manager stack via `patch.multiple` with all patches
    applied at once.
    """
    import backend.api.routers.subscription as sub_mod

    return patch.multiple(
        sub_mod,
        _STRIPE_SECRET_KEY="sk_test_fake",
        _STRIPE_PRICE_ID_STANDARD=_FAKE_PRICE_STANDARD,
        _STRIPE_PRICE_ID_FOUNDER=_FAKE_PRICE_FOUNDER,
        _ALLOWED_PRICE_IDS={_FAKE_PRICE_STANDARD, _FAKE_PRICE_FOUNDER},
        get_subscription_row=MagicMock(return_value=row),
        upsert_subscription=upsert_spy,
    )


def _mock_stripe_session(url: str = "https://checkout.stripe.test/session/xyz"):
    """Build a StripeClient mock that returns a fake Checkout Session."""
    session = MagicMock()
    session.url = url
    client = MagicMock()
    client.checkout.sessions.create.return_value = session
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCheckoutGuardB212:
    """POST /api/subscription/checkout guard against overwriting active trials."""

    @pytest.mark.anyio
    async def test_checkout_guard_trialing_blocks(self):
        """status=trialing → short-circuit; Stripe not called; no pending_checkout write."""
        from backend.api.main import app

        row = {
            "user_id": _TEST_USER_ID,
            "status": "trialing",
            "stripe_customer_id": "cus_existing",
            "stripe_subscription_id": "sub_existing",
            "trial_end": "2026-05-01T15:31:29+00:00",
        }
        upsert_spy = MagicMock()
        stripe_client = _mock_stripe_session()

        with _patched_router(upsert_spy, row), patch(
            "backend.api.routers.subscription.stripe.StripeClient",
            return_value=stripe_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/subscription/checkout",
                    json={"email": "u@example.com", "price_id": _FAKE_PRICE_STANDARD},
                    headers={"X-User-ID": _TEST_USER_ID},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "already_active": True,
            "status": "trialing",
            "redirect_url": "/today",
        }
        # No checkout session created
        stripe_client.checkout.sessions.create.assert_not_called()
        # No pending_checkout upsert
        upsert_spy.assert_not_called()

    @pytest.mark.anyio
    async def test_checkout_guard_active_blocks(self):
        """status=active → same short-circuit."""
        from backend.api.main import app

        row = {
            "user_id": _TEST_USER_ID,
            "status": "active",
            "stripe_customer_id": "cus_existing",
            "stripe_subscription_id": "sub_existing",
        }
        upsert_spy = MagicMock()
        stripe_client = _mock_stripe_session()

        with _patched_router(upsert_spy, row), patch(
            "backend.api.routers.subscription.stripe.StripeClient",
            return_value=stripe_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/subscription/checkout",
                    json={"email": "u@example.com", "price_id": _FAKE_PRICE_STANDARD},
                    headers={"X-User-ID": _TEST_USER_ID},
                )

        assert resp.status_code == 200
        assert resp.json()["already_active"] is True
        assert resp.json()["status"] == "active"
        stripe_client.checkout.sessions.create.assert_not_called()
        upsert_spy.assert_not_called()

    @pytest.mark.anyio
    async def test_checkout_guard_past_due_passes(self):
        """status=past_due → normal flow; Stripe called; pending_checkout written."""
        from backend.api.main import app

        row = {
            "user_id": _TEST_USER_ID,
            "status": "past_due",
            "stripe_customer_id": "cus_existing",
            "stripe_subscription_id": "sub_existing",
        }
        upsert_spy = MagicMock()
        stripe_client = _mock_stripe_session("https://checkout.stripe.test/s/past_due")

        with _patched_router(upsert_spy, row), patch(
            "backend.api.routers.subscription.stripe.StripeClient",
            return_value=stripe_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/subscription/checkout",
                    json={"email": "u@example.com", "price_id": _FAKE_PRICE_STANDARD},
                    headers={"X-User-ID": _TEST_USER_ID},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert "checkout_url" in body
        assert body["checkout_url"] == "https://checkout.stripe.test/s/past_due"
        assert "already_active" not in body
        stripe_client.checkout.sessions.create.assert_called_once()
        upsert_spy.assert_called_once_with(_TEST_USER_ID, {"status": "pending_checkout"})

    @pytest.mark.anyio
    async def test_checkout_no_existing_row_passes(self):
        """No subscription row yet (new user) → normal flow; pending_checkout written."""
        from backend.api.main import app

        upsert_spy = MagicMock()
        stripe_client = _mock_stripe_session("https://checkout.stripe.test/s/new")

        with _patched_router(upsert_spy, None), patch(
            "backend.api.routers.subscription.stripe.StripeClient",
            return_value=stripe_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/subscription/checkout",
                    json={"email": "u@example.com", "price_id": _FAKE_PRICE_FOUNDER},
                    headers={"X-User-ID": _TEST_USER_ID},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["checkout_url"] == "https://checkout.stripe.test/s/new"
        assert "already_active" not in body
        stripe_client.checkout.sessions.create.assert_called_once()
        upsert_spy.assert_called_once_with(_TEST_USER_ID, {"status": "pending_checkout"})
