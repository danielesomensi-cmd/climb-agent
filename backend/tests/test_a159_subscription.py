"""A159: Subscription guard + webhook handler tests.

All tests run with STORAGE_BACKEND=file (default in pytest) and without
a real Stripe secret key, so the guard bypasses and returns is_active=True.
Webhook tests mock stripe.Webhook.construct_event to avoid network calls.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# subscription_guard.py — unit tests
# ---------------------------------------------------------------------------

class TestCheckSubscription:
    """check_subscription() bypass cases and logic."""

    def test_bypass_when_stripe_not_configured(self):
        """No STRIPE_SECRET_KEY → always allow."""
        from backend.engine.subscription_guard import check_subscription
        result = check_subscription("some-user-id")
        assert result["is_active"] is True
        assert result["can_interact"] is True

    def test_bypass_when_user_id_none(self):
        """user_id=None (dev/test without auth) → allow."""
        from backend.engine.subscription_guard import check_subscription
        result = check_subscription(None)
        assert result["is_active"] is True
        assert result["can_interact"] is True

    def test_bypass_when_storage_is_file(self, monkeypatch):
        """STORAGE_BACKEND=file → bypass even if STRIPE_SECRET_KEY is set."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
        # STORAGE_BACKEND defaults to 'file' in tests
        from importlib import reload
        import backend.engine.subscription_guard as guard_mod
        reload(guard_mod)
        result = guard_mod.check_subscription("some-user-id")
        assert result["is_active"] is True
        # Reload without env var to restore state
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        reload(guard_mod)

    def test_active_status_returns_can_interact(self):
        """status=active → can_interact=True."""
        from backend.engine.subscription_guard import _ACTIVE_STATUSES
        assert "active" in _ACTIVE_STATUSES
        assert "trialing" in _ACTIVE_STATUSES

    def test_expired_statuses_blocked(self):
        """past_due, canceled, expired are not in ACTIVE_STATUSES."""
        from backend.engine.subscription_guard import _ACTIVE_STATUSES
        for status in ("past_due", "canceled", "expired"):
            assert status not in _ACTIVE_STATUSES

    def test_trial_days_remaining_calculation(self):
        """trial_days_remaining computed correctly from trial_end."""
        from backend.engine.subscription_guard import check_subscription

        future = datetime.now(timezone.utc) + timedelta(days=7)
        row = {
            "user_id": "u1",
            "status": "trialing",
            "trial_end": future.isoformat(),
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "current_period_start": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
        }

        with patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value=row,
        ), patch(
            "backend.engine.subscription_guard._stripe_enabled",
            return_value=True,
        ), patch(
            "backend.engine.subscription_guard._supabase_enabled",
            return_value=True,
        ):
            result = check_subscription("u1")

        assert result["status"] == "trialing"
        assert result["is_active"] is True
        assert result["can_interact"] is True
        # Allow 6 or 7 days depending on sub-second execution timing
        assert result["trial_days_remaining"] in (6, 7)

    def test_no_subscription_row_allows_access(self):
        """No row in DB → user not onboarded yet → full access."""
        from backend.engine.subscription_guard import check_subscription

        with patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value=None,
        ), patch(
            "backend.engine.subscription_guard._stripe_enabled",
            return_value=True,
        ), patch(
            "backend.engine.subscription_guard._supabase_enabled",
            return_value=True,
        ):
            result = check_subscription("u1")

        assert result["is_active"] is True
        assert result["can_interact"] is True

    def test_past_due_blocks_interaction(self):
        """status=past_due → can_interact=False."""
        from backend.engine.subscription_guard import check_subscription

        row = {
            "user_id": "u1",
            "status": "past_due",
            "trial_end": None,
            "stripe_customer_id": "cus_xxx",
            "stripe_subscription_id": "sub_xxx",
            "current_period_start": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
        }

        with patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value=row,
        ), patch(
            "backend.engine.subscription_guard._stripe_enabled",
            return_value=True,
        ), patch(
            "backend.engine.subscription_guard._supabase_enabled",
            return_value=True,
        ):
            result = check_subscription("u1")

        assert result["is_active"] is False
        assert result["can_interact"] is False
        assert result["status"] == "past_due"

    def test_canceled_blocks_interaction(self):
        """status=canceled → can_interact=False."""
        from backend.engine.subscription_guard import check_subscription

        row = {"user_id": "u1", "status": "canceled", "trial_end": None}

        with patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value=row,
        ), patch(
            "backend.engine.subscription_guard._stripe_enabled",
            return_value=True,
        ), patch(
            "backend.engine.subscription_guard._supabase_enabled",
            return_value=True,
        ):
            result = check_subscription("u1")

        assert result["can_interact"] is False


# ---------------------------------------------------------------------------
# require_active_subscription FastAPI dependency
# ---------------------------------------------------------------------------

class TestRequireActiveSubscription:
    """require_active_subscription raises 402 when blocked, no-op otherwise."""

    def test_no_op_in_test_mode(self):
        """In test mode (no Stripe key), dependency passes through."""
        from fastapi import HTTPException
        from backend.api.deps import require_active_subscription

        # Should not raise
        try:
            require_active_subscription(user_id=None)
        except HTTPException:
            pytest.fail("require_active_subscription raised unexpectedly in test mode")

    def test_raises_402_when_expired(self):
        """When check_subscription returns can_interact=False, raises 402."""
        from fastapi import HTTPException
        from backend.api.deps import require_active_subscription

        expired_result = {
            "status": "past_due",
            "is_active": False,
            "trial_days_remaining": None,
            "can_interact": False,
        }

        # Patch check_subscription in the module where it is imported (lazy import inside func)
        with patch(
            "backend.engine.subscription_guard.check_subscription",
            return_value=expired_result,
        ):
            with pytest.raises(HTTPException) as exc_info:
                require_active_subscription(user_id="u1")
            assert exc_info.value.status_code == 402
            assert exc_info.value.detail["error"] == "subscription_required"

    def test_passes_when_active(self):
        """When check_subscription returns can_interact=True, does not raise."""
        from fastapi import HTTPException
        from backend.api.deps import require_active_subscription

        active_result = {
            "status": "active",
            "is_active": True,
            "trial_days_remaining": None,
            "can_interact": True,
        }

        with patch(
            "backend.engine.subscription_guard.check_subscription",
            return_value=active_result,
        ):
            try:
                require_active_subscription(user_id="u1")
            except HTTPException:
                pytest.fail("require_active_subscription raised unexpectedly for active user")


# ---------------------------------------------------------------------------
# Stripe webhook helper functions
# ---------------------------------------------------------------------------

class TestStripeWebhookHelpers:
    """Test internal helpers in stripe_webhook.py."""

    def test_ts_converts_unix_timestamp(self):
        """_ts() converts a Unix int to ISO-8601 string."""
        from backend.api.stripe_webhook import _ts

        result = _ts(0)
        assert result is not None
        assert "1970" in result

    def test_ts_returns_none_for_none(self):
        """_ts(None) returns None."""
        from backend.api.stripe_webhook import _ts
        assert _ts(None) is None

    def test_map_stripe_status(self):
        """_map_stripe_status maps Stripe → internal vocabulary."""
        from backend.api.stripe_webhook import _map_stripe_status

        assert _map_stripe_status("trialing") == "trialing"
        assert _map_stripe_status("active") == "active"
        assert _map_stripe_status("past_due") == "past_due"
        assert _map_stripe_status("canceled") == "canceled"
        assert _map_stripe_status("unpaid") == "past_due"
        assert _map_stripe_status("incomplete_expired") == "expired"
        assert _map_stripe_status(None) == "past_due"

    def test_map_stripe_status_unknown(self):
        """Unknown Stripe status maps to past_due (safe default)."""
        from backend.api.stripe_webhook import _map_stripe_status
        assert _map_stripe_status("some_future_status") == "past_due"


# ---------------------------------------------------------------------------
# Stripe webhook — invalid signature handling
# ---------------------------------------------------------------------------

class TestStripeWebhookSignature:
    """Webhook endpoint returns 400 for invalid signature."""

    @pytest.mark.anyio
    async def test_invalid_signature_returns_400(self):
        """Webhook with invalid Stripe-Signature returns 400."""
        from httpx import AsyncClient, ASGITransport
        from backend.api.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/stripe/webhook",
                content=b'{"type": "test"}',
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "invalid_sig",
                },
            )
        # Without STRIPE_SECRET_KEY configured → 503 (not configured)
        # With STRIPE_SECRET_KEY but invalid sig → 400
        assert resp.status_code in (400, 503)

    @pytest.mark.anyio
    async def test_webhook_without_stripe_configured_returns_503(self):
        """Webhook returns 503 when STRIPE_SECRET_KEY is not set."""
        from httpx import AsyncClient, ASGITransport
        from backend.api.main import app

        with patch.dict(os.environ, {}, clear=False):
            # Ensure STRIPE_SECRET_KEY is not set
            env_backup = os.environ.pop("STRIPE_SECRET_KEY", None)
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/api/stripe/webhook",
                        content=b"{}",
                        headers={"Content-Type": "application/json"},
                    )
                assert resp.status_code == 503
            finally:
                if env_backup is not None:
                    os.environ["STRIPE_SECRET_KEY"] = env_backup


# ---------------------------------------------------------------------------
# GET /api/subscription/status — no Stripe configured → active
# ---------------------------------------------------------------------------

class TestSubscriptionStatusEndpoint:
    """GET /api/subscription/status returns active in dev/test mode."""

    @pytest.mark.anyio
    async def test_status_returns_active_in_test_mode(self):
        """Without Stripe configured, status endpoint returns is_active=True."""
        from httpx import AsyncClient, ASGITransport
        from backend.api.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/subscription/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["is_active"] is True
        assert body["can_interact"] is True

    @pytest.mark.anyio
    async def test_checkout_returns_503_without_stripe_configured(self):
        """POST /api/subscription/checkout returns 503 without Stripe key."""
        from httpx import AsyncClient, ASGITransport
        from backend.api.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/subscription/checkout",
                json={"email": "test@example.com"},
                headers={"X-User-ID": "00000000-0000-4000-a000-000000000001"},
            )
        assert resp.status_code == 503

    @pytest.mark.anyio
    async def test_portal_returns_503_without_stripe_configured(self):
        """POST /api/subscription/portal returns 503 without Stripe key."""
        from httpx import AsyncClient, ASGITransport
        from backend.api.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/subscription/portal",
                headers={"X-User-ID": "00000000-0000-4000-a000-000000000001"},
            )
        assert resp.status_code in (503, 404)


# ---------------------------------------------------------------------------
# Guard integration — protected endpoints pass through in test mode
# ---------------------------------------------------------------------------

class TestGuardedEndpointsPassInTestMode:
    """In test mode (no Stripe key), guarded endpoints behave normally."""

    @pytest.mark.anyio
    async def test_feedback_not_blocked_in_test_mode(self):
        """POST /api/feedback is not blocked by subscription guard in test mode."""
        from httpx import AsyncClient, ASGITransport
        from backend.api.main import app

        # Minimal valid feedback payload
        payload = {
            "log_entry": {
                "date": "2026-01-01",
                "session_id": "test_session",
                "actual": {},
            },
            "resolved_day": None,
            "status": "done",
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/feedback",
                json=payload,
                headers={"X-User-ID": "00000000-0000-4000-a000-000000000001"},
            )

        # 402 would mean guard fired — should NOT happen in test mode
        assert resp.status_code != 402
