"""A232 — Card-free trial + trial-end handling.

Covers:
    - Checkout Session params: payment_method_collection=if_required and
      trial_settings.end_behavior.missing_payment_method=cancel, for both
      price IDs (Standard + Founding).
    - Anti-abuse: a row with trial_end set (trial consumed) → checkout WITHOUT
      trial_period_days/trial_settings (pay now, Stripe collects the card).
    - Abandoned-checkout rows (pending_checkout, NO trial_end) still get the
      full 15-day trial.
    - Webhook: has_payment_method synced on checkout.session.completed and
      customer.subscription.updated.
    - Webhook: customer.subscription.trial_will_end dispatched (log+notify,
      no DB write).
    - Trial-end cancel: customer.subscription.deleted → row canceled → the
      fail-closed guard (B202) blocks interaction.

Mocking layout mirrors test_b212_checkout_guard.py / test_stripe_webhook_B226.py.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from backend.api import stripe_webhook as sw


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_PRICE_STANDARD = "price_test_standard"
_FAKE_PRICE_FOUNDER = "price_test_founder"
_TEST_USER_ID = "00000000-0000-4000-a000-000000000232"


def _patched_router(upsert_spy: MagicMock, row: dict | None):
    """Patch the subscription router so Stripe envvars look configured."""
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


def _mock_stripe_client():
    session = MagicMock()
    session.url = "https://checkout.stripe.test/session/a232"
    client = MagicMock()
    client.checkout.sessions.create.return_value = session
    return client


async def _post_checkout(price_id: str) -> tuple[int, dict]:
    """POST /api/subscription/checkout and return (status, checkout params)."""
    from backend.api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/subscription/checkout",
            json={"email": "a232@example.com", "price_id": price_id},
            headers={"X-User-ID": _TEST_USER_ID},
        )
    return resp


def _build_event(event_id: str, event_type: str, data_object: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": event_id, "type": event_type, "data": {"object": data_object}}


@pytest.fixture(autouse=True)
def _clear_dedup_cache():
    sw._reset_event_dedup_for_tests()
    yield
    sw._reset_event_dedup_for_tests()


# ---------------------------------------------------------------------------
# Checkout Session params
# ---------------------------------------------------------------------------

class TestCheckoutNoCard:
    """Checkout is created card-free with clean trial-end cancel behavior."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("price_id", [_FAKE_PRICE_STANDARD, _FAKE_PRICE_FOUNDER])
    async def test_fresh_user_gets_cardfree_trial(self, price_id):
        """No row at all → full trial, no card, cancel-on-missing-card. Both prices."""
        stripe_client = _mock_stripe_client()

        with _patched_router(MagicMock(), row=None), patch(
            "backend.api.routers.subscription.stripe.StripeClient",
            return_value=stripe_client,
        ):
            resp = await _post_checkout(price_id)

        assert resp.status_code == 200, resp.text
        params = stripe_client.checkout.sessions.create.call_args.args[0]
        assert params["payment_method_collection"] == "if_required"
        assert params["line_items"] == [{"price": price_id, "quantity": 1}]
        sub_data = params["subscription_data"]
        assert sub_data["trial_period_days"] == 15
        assert sub_data["trial_settings"] == {
            "end_behavior": {"missing_payment_method": "cancel"}
        }
        assert sub_data["metadata"] == {"user_id": _TEST_USER_ID}

    @pytest.mark.anyio
    async def test_abandoned_checkout_still_gets_full_trial(self):
        """pending_checkout row with NO trial_end (abandoned card entry, e.g.
        the pre-A232 drop-offs) → the user never consumed a trial and must
        still get the full 15 days."""
        row = {
            "user_id": _TEST_USER_ID,
            "status": "pending_checkout",
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "trial_end": None,
        }
        stripe_client = _mock_stripe_client()

        with _patched_router(MagicMock(), row=row), patch(
            "backend.api.routers.subscription.stripe.StripeClient",
            return_value=stripe_client,
        ):
            resp = await _post_checkout(_FAKE_PRICE_STANDARD)

        assert resp.status_code == 200, resp.text
        sub_data = stripe_client.checkout.sessions.create.call_args.args[0][
            "subscription_data"
        ]
        assert sub_data["trial_period_days"] == 15
        assert sub_data["trial_settings"] == {
            "end_behavior": {"missing_payment_method": "cancel"}
        }

    @pytest.mark.anyio
    async def test_consumed_trial_means_no_second_trial(self):
        """Row with trial_end set (trial consumed, sub canceled) → checkout
        WITHOUT trial: user pays now, so Stripe requires the card."""
        row = {
            "user_id": _TEST_USER_ID,
            "status": "canceled",
            "stripe_customer_id": "cus_a232_old",
            "stripe_subscription_id": "sub_a232_old",
            "trial_end": "2026-06-01T00:00:00+00:00",
        }
        stripe_client = _mock_stripe_client()

        with _patched_router(MagicMock(), row=row), patch(
            "backend.api.routers.subscription.stripe.StripeClient",
            return_value=stripe_client,
        ):
            resp = await _post_checkout(_FAKE_PRICE_STANDARD)

        assert resp.status_code == 200, resp.text
        params = stripe_client.checkout.sessions.create.call_args.args[0]
        sub_data = params["subscription_data"]
        assert "trial_period_days" not in sub_data
        assert "trial_settings" not in sub_data
        # metadata still propagated for webhook user resolution
        assert sub_data["metadata"] == {"user_id": _TEST_USER_ID}
        # card gets collected because an amount is due
        assert params["payment_method_collection"] == "if_required"


# ---------------------------------------------------------------------------
# Webhook: has_payment_method sync
# ---------------------------------------------------------------------------

class TestHasPaymentMethodSync:
    def test_subscription_updated_syncs_card_presence(self):
        upsert_calls = []

        with patch.object(sw, "upsert_subscription", side_effect=lambda u, f: upsert_calls.append((u, f))):
            sw._handle_subscription_updated({
                "id": "sub_a232",
                "customer": "cus_a232",
                "status": "trialing",
                "metadata": {"user_id": _TEST_USER_ID},
                "default_payment_method": "pm_123",
            })
            sw._handle_subscription_updated({
                "id": "sub_a232",
                "customer": "cus_a232",
                "status": "trialing",
                "metadata": {"user_id": _TEST_USER_ID},
                "default_payment_method": None,
            })

        assert upsert_calls[0][1]["has_payment_method"] is True
        assert upsert_calls[1][1]["has_payment_method"] is False

    def test_checkout_completed_syncs_card_presence(self):
        """checkout.session.completed fetches the sub and stores has_payment_method."""
        upsert_calls = []

        sub_payload = {
            "trial_start": 1780000000,
            "trial_end": 1781296000,
            "current_period_start": 1780000000,
            "current_period_end": 1781296000,
            "default_payment_method": None,  # A232 card-free checkout
        }
        retrieved = MagicMock()
        retrieved.to_dict_recursive.return_value = sub_payload
        client = MagicMock()
        client.subscriptions.retrieve.return_value = retrieved

        with patch.object(sw, "_STRIPE_SECRET_KEY", "sk_test_dummy"), \
             patch.object(sw.stripe, "StripeClient", return_value=client), \
             patch.object(sw, "upsert_subscription", side_effect=lambda u, f: upsert_calls.append((u, f))):
            sw._handle_checkout_completed({
                "metadata": {"user_id": _TEST_USER_ID},
                "client_reference_id": _TEST_USER_ID,
                "customer": "cus_a232",
                "subscription": "sub_a232",
            })

        assert len(upsert_calls) == 1
        _, fields = upsert_calls[0]
        assert fields["status"] == "trialing"
        assert fields["has_payment_method"] is False


# ---------------------------------------------------------------------------
# Webhook: trial_will_end
# ---------------------------------------------------------------------------

class TestTrialWillEnd:
    @pytest.mark.anyio
    async def test_trial_will_end_dispatched_via_endpoint(self):
        from backend.api.main import app

        event = _build_event(
            "evt_a232_twe_001",
            "customer.subscription.trial_will_end",
            {"id": "sub_a232", "customer": "cus_a232",
             "metadata": {"user_id": _TEST_USER_ID}},
        )

        handler_calls = {"n": 0}

        with patch.object(sw, "_STRIPE_SECRET_KEY", "sk_test_dummy"), \
             patch.object(sw.stripe.Webhook, "construct_event", return_value=event), \
             patch.object(sw, "_handle_trial_will_end",
                          side_effect=lambda _o: handler_calls.__setitem__("n", handler_calls["n"] + 1)):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/stripe/webhook",
                    content=b"{}",
                    headers={"Content-Type": "application/json", "stripe-signature": "v"},
                )

        assert resp.status_code == 200
        assert handler_calls["n"] == 1

    def test_trial_will_end_writes_nothing(self):
        """Handler is log+notify only — must never upsert."""
        with patch.object(sw, "upsert_subscription") as upsert_spy, \
             patch.object(sw, "find_subscription_by_stripe_subscription_id", return_value=None), \
             patch.object(sw, "find_subscription_by_stripe_customer", return_value=None):
            sw._handle_trial_will_end({
                "id": "sub_a232", "customer": "cus_a232",
                "default_payment_method": None, "metadata": {},
            })
        upsert_spy.assert_not_called()


# ---------------------------------------------------------------------------
# Trial-end cancel → guard blocks
# ---------------------------------------------------------------------------

class TestTrialEndCancelBlocksAccess:
    def test_deleted_event_sets_canceled_and_guard_blocks(self):
        """The trial-end cancel (missing_payment_method=cancel) fires
        customer.subscription.deleted → local row canceled → B202 guard
        denies interaction."""
        row_state: Dict[str, Any] = {
            "user_id": _TEST_USER_ID,
            "status": "trialing",
            "trial_end": "2026-07-01T00:00:00+00:00",
            "has_payment_method": False,
        }

        def _fake_upsert(user_id: str, fields: Dict[str, Any]) -> None:
            assert user_id == _TEST_USER_ID
            row_state.update(fields)

        with patch.object(sw, "upsert_subscription", side_effect=_fake_upsert):
            sw._handle_subscription_deleted({
                "id": "sub_a232",
                "customer": "cus_a232",
                "metadata": {"user_id": _TEST_USER_ID},
            })

        assert row_state["status"] == "canceled"

        # Guard reads the updated row → deny (fail-closed)
        import backend.engine.subscription_guard as guard_mod
        with patch.object(guard_mod, "_stripe_enabled", return_value=True), \
             patch.object(guard_mod, "_supabase_enabled", return_value=True), \
             patch.object(guard_mod, "get_subscription_row", return_value=row_state):
            result = guard_mod.check_subscription(_TEST_USER_ID)

        assert result["can_interact"] is False
        assert result["status"] == "canceled"

    def test_check_subscription_exposes_has_payment_method(self):
        import backend.engine.subscription_guard as guard_mod
        row = {
            "user_id": _TEST_USER_ID,
            "status": "trialing",
            "trial_end": "2099-01-01T00:00:00+00:00",
            "has_payment_method": False,
        }
        with patch.object(guard_mod, "_stripe_enabled", return_value=True), \
             patch.object(guard_mod, "_supabase_enabled", return_value=True), \
             patch.object(guard_mod, "get_subscription_row", return_value=row):
            result = guard_mod.check_subscription(_TEST_USER_ID)

        assert result["has_payment_method"] is False
        assert result["can_interact"] is True  # trialing still interacts

        row["has_payment_method"] = True
        with patch.object(guard_mod, "_stripe_enabled", return_value=True), \
             patch.object(guard_mod, "_supabase_enabled", return_value=True), \
             patch.object(guard_mod, "get_subscription_row", return_value=row):
            result = guard_mod.check_subscription(_TEST_USER_ID)
        assert result["has_payment_method"] is True
