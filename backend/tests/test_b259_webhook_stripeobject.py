"""B259 — Stripe webhook must handle a real StripeObject from construct_event.

Root cause of the production outage: `stripe.Webhook.construct_event(...)` returns
a `stripe.Event` (StripeObject), and stripe-python >=8 removed dict-style `.get()`
from StripeObject. The handler did `event.get("id")` OUTSIDE the try/except, so every
real delivery raised AttributeError → 500 → Stripe retried then gave up
(`pending_webhooks=1` forever) → subscription rows never synced.

The pre-existing B226 tests mocked construct_event with a plain *dict* (which has
`.get`), so they passed while production 500'd. These tests reproduce the real type
(StripeObject, including a StripeObject `data.object`) and assert every dispatched
event type reaches its handler with a 200 and a plain-dict payload.
"""
from __future__ import annotations

from typing import Any, Dict

import pytest
import stripe

from backend.api import stripe_webhook as sw


def _stripe_event_object(event_id: str, event_type: str, data_object: Dict[str, Any]):
    """Return a REAL stripe.Event (StripeObject), like construct_event does —
    NOT a plain dict. Nested data.object is itself a StripeObject."""
    return stripe.Event.construct_from(
        {"id": event_id, "type": event_type, "data": {"object": data_object}},
        "sk_test_dummy",
    )


@pytest.fixture(autouse=True)
def _clear_dedup_cache():
    sw._reset_event_dedup_for_tests()
    yield
    sw._reset_event_dedup_for_tests()


def test_real_stripe_event_object_has_no_dict_get():
    """Documents the root cause: StripeObject does not support .get() in this
    stripe version, so `event.get(...)` raises AttributeError."""
    ev = _stripe_event_object("evt_x", "customer.deleted", {"id": "cus_x"})
    with pytest.raises(AttributeError):
        ev.get("id")  # noqa: B009 — intentionally exercising the broken call
    # The fix path works: bracket access + recursive dict conversion.
    assert ev["id"] == "evt_x"
    converted = sw._stripe_to_dict(ev)
    assert converted.get("id") == "evt_x"
    assert isinstance(converted["data"]["object"], dict)


# (handler_attr, event_type, data_object) for every dispatched event type.
_DISPATCH_CASES = [
    ("_handle_checkout_completed", "checkout.session.completed",
     {"id": "cs_1", "customer": "cus_1", "subscription": "sub_1",
      "client_reference_id": "user_1", "metadata": {"user_id": "user_1"}}),
    ("_handle_subscription_updated", "customer.subscription.updated",
     {"id": "sub_1", "customer": "cus_1", "status": "active"}),
    ("_handle_subscription_deleted", "customer.subscription.deleted",
     {"id": "sub_1", "customer": "cus_1"}),
    ("_handle_customer_deleted", "customer.deleted", {"id": "cus_1"}),
    ("_handle_payment_succeeded", "invoice.payment_succeeded",
     {"id": "in_1", "customer": "cus_1", "subscription": "sub_1",
      "lines": {"data": [{"period": {"start": 1, "end": 2}}]}}),
    ("_handle_payment_failed", "invoice.payment_failed",
     {"id": "in_1", "customer": "cus_1", "subscription": "sub_1"}),
]


@pytest.mark.anyio
@pytest.mark.parametrize("handler_attr,event_type,data_object", _DISPATCH_CASES)
async def test_stripeobject_event_dispatches_without_500(handler_attr, event_type, data_object):
    """Each subscribed event type, delivered as a real StripeObject, must return
    200 and reach its handler exactly once with a plain-dict payload (so the
    handler's own .get() calls work)."""
    from httpx import AsyncClient, ASGITransport
    from backend.api.main import app

    event = _stripe_event_object(f"evt_{event_type}", event_type, data_object)

    seen = {"n": 0, "payload": None}

    def _spy(obj):
        seen["n"] += 1
        seen["payload"] = obj

    with patch_ctx(handler_attr, _spy, event):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/stripe/webhook",
                content=b"{}",
                headers={"Content-Type": "application/json", "stripe-signature": "v"},
            )

    assert resp.status_code == 200, (
        f"{event_type}: expected 200, got {resp.status_code}: {resp.text} "
        "(regression: event.get on StripeObject 500s at line 106)"
    )
    assert seen["n"] == 1, f"{event_type}: handler not dispatched exactly once"
    # The payload handed to the handler must be a plain dict — handlers rely on .get().
    assert isinstance(seen["payload"], dict), f"{event_type}: handler got non-dict payload"
    assert seen["payload"].get("id") == data_object["id"]


@pytest.mark.anyio
async def test_payment_succeeded_handler_runs_unpatched_on_stripeobject():
    """Full path (handler NOT mocked) on a StripeObject event: the handler reads
    nested data.object fields via .get() — must not raise even though the source
    was a StripeObject. find/upsert are stubbed to stay offline."""
    from httpx import AsyncClient, ASGITransport
    from backend.api.main import app

    event = _stripe_event_object(
        "evt_paid_real", "invoice.payment_succeeded",
        {"id": "in_9", "customer": "cus_9", "subscription": "sub_9",
         "amount_paid": 999,  # B275: $0 invoices are skipped by design
         "lines": {"data": [{"period": {"start": 1700000000, "end": 1702592000}}]}},
    )

    captured = {}

    def _fake_resolve(sub_id, cust_id):
        return "user_paid"

    def _fake_upsert(user_id, patch_dict):
        captured["user_id"] = user_id
        captured["patch"] = patch_dict

    from unittest.mock import patch
    with patch.object(sw, "_STRIPE_SECRET_KEY", "sk_test_dummy"), \
         patch.object(sw.stripe.Webhook, "construct_event", return_value=event), \
         patch.object(sw, "_resolve_user_id", side_effect=_fake_resolve), \
         patch.object(sw, "upsert_subscription", side_effect=_fake_upsert):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/stripe/webhook",
                content=b"{}",
                headers={"Content-Type": "application/json", "stripe-signature": "v"},
            )

    assert resp.status_code == 200, resp.text
    assert captured.get("user_id") == "user_paid"
    assert captured["patch"]["status"] == "active"
    # Period dates parsed from the nested (originally StripeObject) lines[].period.
    assert captured["patch"]["current_period_start"] is not None
    assert captured["patch"]["current_period_end"] is not None


# ---------------------------------------------------------------------------
# Helper: context manager bundling the three patches used by the dispatch test.
# ---------------------------------------------------------------------------
from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def patch_ctx(handler_attr: str, spy, event):
    with patch.object(sw, "_STRIPE_SECRET_KEY", "sk_test_dummy"), \
         patch.object(sw.stripe.Webhook, "construct_event", return_value=event), \
         patch.object(sw, handler_attr, side_effect=spy):
        yield
