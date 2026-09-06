"""A285: SUBSCRIPTION_ENFORCED — the billing pause switch.

The whole point of these tests is that pytest's default configuration
(STORAGE_BACKEND=file, no Stripe key) already bypasses the guard, so a test
written the easy way would pass no matter what this brief does. Every test
here therefore *simulates production* — `_stripe_enabled` and
`_supabase_enabled` patched True — and only then asks what the switch does.

Two things are pinned in both directions:
- OFF ("0") opens the three states that today wall every user out: expired
  local trial, abandoned checkout, and no row at all.
- Anything else — unset, "", "false", "00" — leaves the paywall standing.
  The switch fails safe, like RATE_LIMIT_ENABLED which it is modelled on.
"""

from __future__ import annotations

from importlib import reload
from unittest.mock import patch

import pytest


@pytest.fixture
def guard(monkeypatch):
    """Yield the guard module, restoring pristine import state afterwards.

    The module reads its env vars at import time, so every test that changes
    one must reload — and must reload again on the way out, or it leaks a
    disabled paywall into the rest of the suite.
    """
    import backend.engine.subscription_guard as guard_mod

    def _configure(value: str | None):
        if value is None:
            monkeypatch.delenv("SUBSCRIPTION_ENFORCED", raising=False)
        else:
            monkeypatch.setenv("SUBSCRIPTION_ENFORCED", value)
        reload(guard_mod)
        return guard_mod

    yield _configure

    monkeypatch.delenv("SUBSCRIPTION_ENFORCED", raising=False)
    reload(guard_mod)


def _prod():
    """Context managers that make the guard believe it is in production."""
    return (
        patch("backend.engine.subscription_guard._stripe_enabled", return_value=True),
        patch("backend.engine.subscription_guard._supabase_enabled", return_value=True),
    )


# ---------------------------------------------------------------------------
# OFF — the three walled-out states open up
# ---------------------------------------------------------------------------

class TestPauseOpensAccess:
    """With the switch off, the states that 402 today are let through."""

    @pytest.mark.parametrize(
        "row",
        [
            pytest.param(None, id="no_row"),
            pytest.param({"status": "pending_checkout"}, id="abandoned_checkout"),
            pytest.param(
                {"status": "trialing", "trial_end": "2026-01-01T00:00:00+00:00"},
                id="expired_local_trial",
            ),
            pytest.param({"status": "canceled"}, id="canceled"),
        ],
    )
    def test_blocked_states_are_allowed_when_paused(self, guard, row):
        guard_mod = guard("0")
        stripe_p, supa_p = _prod()
        with stripe_p, supa_p, patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value=row,
        ):
            result = guard_mod.check_subscription("some-user-uuid")

        assert result["can_interact"] is True
        assert result["is_active"] is True
        assert result["status"] == "active"

    def test_pause_reads_nothing_from_the_database(self, guard):
        """The decision needs no row — so it must not pay for one."""
        guard_mod = guard("0")
        stripe_p, supa_p = _prod()
        with stripe_p, supa_p, patch(
            "backend.engine.subscription_guard.get_subscription_row",
        ) as mock_row:
            guard_mod.check_subscription("some-user-uuid")

        mock_row.assert_not_called()


# ---------------------------------------------------------------------------
# The switch fails safe
# ---------------------------------------------------------------------------

class TestFailsSafe:
    """Only the literal "0" disables. Everything else keeps the paywall up."""

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param(None, id="unset"),
            pytest.param("", id="empty"),
            pytest.param("1", id="one"),
            pytest.param("false", id="false_string"),
            pytest.param("off", id="off_string"),
            pytest.param("00", id="double_zero"),
            pytest.param(" 0", id="zero_with_space"),
        ],
    )
    def test_paywall_stands_unless_value_is_exactly_zero(self, guard, value):
        guard_mod = guard(value)
        assert guard_mod._SUBSCRIPTION_ENFORCED is True

        stripe_p, supa_p = _prod()
        with stripe_p, supa_p, patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value=None,
        ):
            result = guard_mod.check_subscription("some-user-uuid")

        assert result["can_interact"] is False

    def test_zero_disables(self, guard):
        assert guard("0")._SUBSCRIPTION_ENFORCED is False


# ---------------------------------------------------------------------------
# The `enforced` field — how the UI tells the two "active" apart
# ---------------------------------------------------------------------------

class TestEnforcedField:
    """`enforced` distinguishes 'active because they pay' from 'billing paused'."""

    def test_false_when_paused(self, guard):
        guard_mod = guard("0")
        stripe_p, supa_p = _prod()
        with stripe_p, supa_p:
            assert guard_mod.check_subscription("u1")["enforced"] is False

    def test_true_for_a_genuinely_active_subscriber(self, guard):
        guard_mod = guard(None)
        stripe_p, supa_p = _prod()
        with stripe_p, supa_p, patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value={"status": "active", "has_payment_method": True},
        ):
            result = guard_mod.check_subscription("paying-user")

        assert result["enforced"] is True
        assert result["can_interact"] is True

    def test_true_when_denied(self, guard):
        """A blocked user is blocked *because* enforcement is on — say so."""
        guard_mod = guard(None)
        stripe_p, supa_p = _prod()
        with stripe_p, supa_p, patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value=None,
        ):
            result = guard_mod.check_subscription("blocked-user")

        assert result["enforced"] is True
        assert result["can_interact"] is False

    @pytest.mark.anyio
    async def test_status_endpoint_exposes_it(self):
        """GET /api/subscription/status carries the field (additive payload)."""
        from httpx import AsyncClient, ASGITransport
        from backend.api.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/subscription/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["enforced"] is True
        # Pre-A285 fields untouched
        assert body["is_active"] is True
        assert body["can_interact"] is True


# ---------------------------------------------------------------------------
# A232 — the pause must not burn anyone's single lifetime trial
# ---------------------------------------------------------------------------

class TestTrialNotStartedWhilePaused:
    """A trial granted during the pause would expire unused and lock the user
    out the day enforcement returns (the TRIAL-LOCKOUT shape B331 repaired)."""

    def test_no_row_written_when_paused(self, guard):
        guard_mod = guard("0")
        stripe_p, supa_p = _prod()
        with stripe_p, supa_p, patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value=None,
        ), patch(
            "backend.engine.subscription_guard.upsert_subscription",
        ) as mock_upsert:
            started = guard_mod.start_trial_if_new("brand-new-user")

        assert started is False
        mock_upsert.assert_not_called()

    def test_trial_still_starts_when_enforcing(self, guard):
        """Positive control: without the pause, A250 behaviour is unchanged."""
        guard_mod = guard(None)
        stripe_p, supa_p = _prod()
        with stripe_p, supa_p, patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value=None,
        ), patch(
            "backend.engine.subscription_guard.upsert_subscription",
        ) as mock_upsert:
            started = guard_mod.start_trial_if_new("brand-new-user")

        assert started is True
        mock_upsert.assert_called_once()
        fields = mock_upsert.call_args[0][1]
        assert fields["status"] == "trialing"
        assert fields["has_payment_method"] is False


# ---------------------------------------------------------------------------
# Positive control on the dependency itself
# ---------------------------------------------------------------------------

class TestGuardDependency:
    """require_active_subscription must still 402 while enforcement is on."""

    def test_402_when_enforcing(self, guard):
        from fastapi import HTTPException
        from backend.api.deps import require_active_subscription

        guard(None)
        stripe_p, supa_p = _prod()
        with stripe_p, supa_p, patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value={"status": "canceled"},
        ):
            with pytest.raises(HTTPException) as exc_info:
                require_active_subscription(user_id="u1")

        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["error"] == "subscription_required"
        # B258: a canceled subscriber had a trial — "ended", not "start"
        assert "ended" in exc_info.value.detail["message"].lower()

    def test_no_402_when_paused(self, guard):
        from backend.api.deps import require_active_subscription

        guard("0")
        stripe_p, supa_p = _prod()
        with stripe_p, supa_p, patch(
            "backend.engine.subscription_guard.get_subscription_row",
            return_value={"status": "canceled"},
        ):
            # No exception: the same user who 402s above walks through.
            require_active_subscription(user_id="u1")
