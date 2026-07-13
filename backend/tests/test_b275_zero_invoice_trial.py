"""B275 — $0 trial-start invoice must not mask trialing status.

The trial-start invoice is $0 and "paid" immediately. Pre-B275,
invoice.payment_succeeded promoted the row to active (hiding the trial
banner/countdown) and — on newer Stripe API versions where the invoice has no
top-level `subscription` — overwrote stripe_subscription_id with None.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import patch

from backend.api import stripe_webhook as sw


class TestZeroInvoiceSkipped:
    def test_zero_amount_invoice_writes_nothing(self):
        """$0 invoice (trial start) → no upsert, status stays trialing."""
        with patch.object(sw, "upsert_subscription") as upsert_spy:
            sw._handle_payment_succeeded({
                "amount_paid": 0,
                "subscription": None,
                "customer": "cus_b275",
            })
        upsert_spy.assert_not_called()

    def test_missing_amount_paid_also_skipped(self):
        with patch.object(sw, "upsert_subscription") as upsert_spy:
            sw._handle_payment_succeeded({
                "subscription": "sub_b275",
                "customer": "cus_b275",
            })
        upsert_spy.assert_not_called()

    def test_real_payment_still_sets_active(self):
        upsert_calls = []

        with patch.object(sw, "find_subscription_by_stripe_subscription_id",
                          return_value={"user_id": "user_b275"}), \
             patch.object(sw, "upsert_subscription",
                          side_effect=lambda u, f: upsert_calls.append((u, f))):
            sw._handle_payment_succeeded({
                "amount_paid": 999,
                "subscription": "sub_b275",
                "customer": "cus_b275",
                "lines": {"data": [{"period": {"start": 1780000000, "end": 1782592000}}]},
            })

        assert len(upsert_calls) == 1
        user_id, fields = upsert_calls[0]
        assert user_id == "user_b275"
        assert fields["status"] == "active"
        assert fields["stripe_subscription_id"] == "sub_b275"

    def test_null_subscription_id_never_clobbers_stored_one(self):
        """Newer Stripe API: invoice has no top-level subscription — the upsert
        must not include the key at all (upsert would overwrite with None)."""
        upsert_calls = []

        with patch.object(sw, "find_subscription_by_stripe_customer",
                          return_value={"user_id": "user_b275"}), \
             patch.object(sw, "upsert_subscription",
                          side_effect=lambda u, f: upsert_calls.append((u, f))):
            sw._handle_payment_succeeded({
                "amount_paid": 999,
                "subscription": None,
                "customer": "cus_b275",
            })

        assert len(upsert_calls) == 1
        _, fields = upsert_calls[0]
        assert "stripe_subscription_id" not in fields
        assert fields["status"] == "active"
