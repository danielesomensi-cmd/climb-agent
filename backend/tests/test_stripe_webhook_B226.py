"""B226 — Stripe webhook hardening tests.

Covers:
    - Fail-loud: handler exception → HTTP 500 (so Stripe retries).
    - Idempotency: same event_id processed twice → 2nd call short-circuits 200.
    - customer.deleted handler: clears stripe IDs + sets canceled.
    - cancel_at_period_end (B205): subscription.updated propagates the flag.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from backend.api import stripe_webhook as sw


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_event(event_id: str, event_type: str, data_object: Dict[str, Any]) -> Dict[str, Any]:
    """Build a minimal Stripe event payload (matches construct_event output)."""
    return {
        "id": event_id,
        "type": event_type,
        "data": {"object": data_object},
    }


@pytest.fixture(autouse=True)
def _clear_dedup_cache():
    """Reset LRU dedup cache before each test."""
    sw._reset_event_dedup_for_tests()
    yield
    sw._reset_event_dedup_for_tests()


# ---------------------------------------------------------------------------
# Fail-loud
# ---------------------------------------------------------------------------

class TestFailLoud:
    """Handler exceptions return 500 so Stripe retries."""

    @pytest.mark.anyio
    async def test_handler_exception_returns_500(self):
        """Subscription update handler raising → 500 (was: swallowed 200)."""
        from httpx import AsyncClient, ASGITransport
        from backend.api.main import app

        event = _build_event(
            "evt_test_failloud_001",
            "customer.subscription.updated",
            {"id": "sub_x", "customer": "cus_x", "status": "active"},
        )

        with patch.object(sw, "_STRIPE_SECRET_KEY", "sk_test_dummy"), \
             patch.object(sw.stripe.Webhook, "construct_event", return_value=event), \
             patch.object(sw, "_handle_subscription_updated", side_effect=RuntimeError("boom")):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/stripe/webhook",
                    content=b'{"raw":"body"}',
                    headers={
                        "Content-Type": "application/json",
                        "stripe-signature": "valid_mocked",
                    },
                )
        assert resp.status_code == 500, f"expected 500, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("error") == "handler_failed"
        assert body.get("event_id") == "evt_test_failloud_001"

    @pytest.mark.anyio
    async def test_failed_event_not_marked_processed(self):
        """A 500-returning event must NOT be cached so the retry can re-attempt."""
        from httpx import AsyncClient, ASGITransport
        from backend.api.main import app

        event = _build_event(
            "evt_test_retry_001",
            "customer.subscription.updated",
            {"id": "sub_x", "customer": "cus_x", "status": "active"},
        )

        with patch.object(sw, "_STRIPE_SECRET_KEY", "sk_test_dummy"), \
             patch.object(sw.stripe.Webhook, "construct_event", return_value=event), \
             patch.object(sw, "_handle_subscription_updated", side_effect=RuntimeError("transient")):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/stripe/webhook",
                    content=b"{}",
                    headers={"Content-Type": "application/json", "stripe-signature": "v"},
                )
                assert resp.status_code == 500

        # Cache must be empty — Stripe retry must NOT short-circuit as duplicate.
        assert not sw._is_event_processed("evt_test_retry_001"), (
            "Failed event was incorrectly added to dedup cache — Stripe retries would be lost."
        )


# ---------------------------------------------------------------------------
# Idempotency / dedup
# ---------------------------------------------------------------------------

class TestIdempotency:
    """LRU dedup short-circuits duplicate event deliveries."""

    def test_mark_then_check(self):
        sw._mark_event_processed("evt_abc")
        assert sw._is_event_processed("evt_abc") is True

    def test_unknown_event_not_processed(self):
        assert sw._is_event_processed("evt_nope") is False

    def test_lru_evicts_oldest_when_full(self):
        # Fill cache to capacity, then push one more.
        # Note: _is_event_processed() refreshes LRU position (move_to_end),
        # so we cannot read it before pushing the overflow without altering order.
        for i in range(sw._EVENT_LRU_MAX):
            sw._mark_event_processed(f"evt_{i:04d}")
        # Cache is full at capacity; the evt_0000 entry is the oldest.
        sw._mark_event_processed("evt_overflow")
        # evt_0000 should now be evicted.
        assert sw._is_event_processed("evt_0000") is False, (
            "Oldest entry was not evicted when cache exceeded _EVENT_LRU_MAX"
        )
        assert sw._is_event_processed("evt_overflow") is True
        # The next-oldest (evt_0001) should still be present.
        assert sw._is_event_processed("evt_0001") is True

    @pytest.mark.anyio
    async def test_duplicate_event_short_circuits_200(self):
        """Same event.id delivered twice → 2nd call returns 200 with duplicate flag,
        and handler is NOT invoked the second time."""
        from httpx import AsyncClient, ASGITransport
        from backend.api.main import app

        event = _build_event(
            "evt_dupe_001",
            "checkout.session.completed",
            {"id": "cs_x", "customer": "cus_x", "client_reference_id": "user_dup"},
        )

        handler_calls = {"n": 0}
        def _spy(_session):
            handler_calls["n"] += 1

        with patch.object(sw, "_STRIPE_SECRET_KEY", "sk_test_dummy"), \
             patch.object(sw.stripe.Webhook, "construct_event", return_value=event), \
             patch.object(sw, "_handle_checkout_completed", side_effect=_spy):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp1 = await client.post(
                    "/api/stripe/webhook",
                    content=b"{}",
                    headers={"Content-Type": "application/json", "stripe-signature": "v"},
                )
                resp2 = await client.post(
                    "/api/stripe/webhook",
                    content=b"{}",
                    headers={"Content-Type": "application/json", "stripe-signature": "v"},
                )

        assert resp1.status_code == 200, resp1.text
        assert resp1.json().get("duplicate") is not True
        assert resp2.status_code == 200, resp2.text
        assert resp2.json().get("duplicate") is True
        assert handler_calls["n"] == 1, (
            f"handler invoked {handler_calls['n']} times; expected 1 (dedup failed)"
        )


# ---------------------------------------------------------------------------
# customer.deleted handler
# ---------------------------------------------------------------------------

class TestCustomerDeleted:
    """customer.deleted clears Stripe IDs and sets canceled."""

    def test_clears_ids_and_sets_canceled(self):
        upsert_calls = []

        def _fake_upsert(user_id: str, patch_dict: Dict[str, Any]) -> None:
            upsert_calls.append((user_id, patch_dict))

        def _fake_lookup(customer_id: str) -> Optional[Dict[str, Any]]:
            if customer_id == "cus_to_delete":
                return {"user_id": "user_42", "stripe_customer_id": customer_id, "status": "active"}
            return None

        with patch.object(sw, "find_subscription_by_stripe_customer", side_effect=_fake_lookup), \
             patch.object(sw, "upsert_subscription", side_effect=_fake_upsert):
            sw._handle_customer_deleted({"id": "cus_to_delete"})

        assert len(upsert_calls) == 1
        user_id, patch_dict = upsert_calls[0]
        assert user_id == "user_42"
        assert patch_dict["status"] == "canceled"
        assert patch_dict["stripe_customer_id"] is None
        assert patch_dict["stripe_subscription_id"] is None
        assert patch_dict["cancel_at_period_end"] is False

    def test_unknown_customer_does_nothing(self):
        upsert_calls = []

        def _fake_upsert(user_id: str, patch_dict: Dict[str, Any]) -> None:
            upsert_calls.append((user_id, patch_dict))

        with patch.object(sw, "find_subscription_by_stripe_customer", return_value=None), \
             patch.object(sw, "upsert_subscription", side_effect=_fake_upsert):
            sw._handle_customer_deleted({"id": "cus_unknown"})

        assert upsert_calls == [], "Should not write when customer row not found"

    def test_missing_customer_id_does_nothing(self):
        upsert_calls = []

        def _fake_upsert(user_id: str, patch_dict: Dict[str, Any]) -> None:
            upsert_calls.append((user_id, patch_dict))

        with patch.object(sw, "find_subscription_by_stripe_customer") as lookup, \
             patch.object(sw, "upsert_subscription", side_effect=_fake_upsert):
            sw._handle_customer_deleted({})  # no id field
            lookup.assert_not_called()

        assert upsert_calls == []

    @pytest.mark.anyio
    async def test_customer_deleted_dispatched_via_endpoint(self):
        """End-to-end: customer.deleted event reaches the handler via dispatch."""
        from httpx import AsyncClient, ASGITransport
        from backend.api.main import app

        event = _build_event(
            "evt_customer_deleted_001",
            "customer.deleted",
            {"id": "cus_e2e_test"},
        )

        handler_calls = {"n": 0}
        def _spy(_obj):
            handler_calls["n"] += 1

        with patch.object(sw, "_STRIPE_SECRET_KEY", "sk_test_dummy"), \
             patch.object(sw.stripe.Webhook, "construct_event", return_value=event), \
             patch.object(sw, "_handle_customer_deleted", side_effect=_spy):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/stripe/webhook",
                    content=b"{}",
                    headers={"Content-Type": "application/json", "stripe-signature": "v"},
                )

        assert resp.status_code == 200
        assert handler_calls["n"] == 1, "customer.deleted handler not invoked"


# ---------------------------------------------------------------------------
# cancel_at_period_end (B205 absorbed)
# ---------------------------------------------------------------------------

class TestCancelAtPeriodEnd:
    """B205: subscription.updated propagates cancel_at_period_end flag."""

    def test_cancel_flag_propagated_to_upsert(self):
        upsert_calls = []

        def _fake_upsert(user_id: str, patch_dict: Dict[str, Any]) -> None:
            upsert_calls.append((user_id, patch_dict))

        def _fake_lookup_sub(_sub_id: str) -> Optional[Dict[str, Any]]:
            return {"user_id": "user_canceller"}

        with patch.object(sw, "find_subscription_by_stripe_subscription_id", side_effect=_fake_lookup_sub), \
             patch.object(sw, "find_subscription_by_stripe_customer", return_value=None), \
             patch.object(sw, "upsert_subscription", side_effect=_fake_upsert):
            sw._handle_subscription_updated({
                "id": "sub_xyz",
                "customer": "cus_xyz",
                "status": "active",
                "cancel_at_period_end": True,
                "current_period_end": 1735689600,  # 2025-01-01 UTC
            })

        assert len(upsert_calls) == 1
        _, patch_dict = upsert_calls[0]
        assert patch_dict["cancel_at_period_end"] is True, (
            "cancel_at_period_end flag not forwarded to upsert (B205)"
        )
        # Status remains active during the grace period — fail-closed guard
        # (B202) honors the period_end timestamp before denying access.
        assert patch_dict["status"] == "active"

    def test_uncancel_resets_flag_to_false(self):
        """If user re-enables billing during grace period, flag flips back."""
        upsert_calls = []

        def _fake_upsert(user_id: str, patch_dict: Dict[str, Any]) -> None:
            upsert_calls.append((user_id, patch_dict))

        with patch.object(sw, "find_subscription_by_stripe_subscription_id",
                          return_value={"user_id": "user_uncancel"}), \
             patch.object(sw, "find_subscription_by_stripe_customer", return_value=None), \
             patch.object(sw, "upsert_subscription", side_effect=_fake_upsert):
            sw._handle_subscription_updated({
                "id": "sub_z", "customer": "cus_z", "status": "active",
                "cancel_at_period_end": False,
            })

        _, patch_dict = upsert_calls[0]
        assert patch_dict["cancel_at_period_end"] is False
