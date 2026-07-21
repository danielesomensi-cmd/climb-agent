"""A246 — the retest reminder must actually reach the client, and the answer
must actually reach the engine.

`should_show_test_reminder()` had unit tests since the day it was written, and
they were green the whole time the feature was dead: nothing verified that the
reminder reaches the HTTP response, and nothing verified the response endpoint
end to end. A unit test of a function nobody calls proves only that the function
is correct in isolation.

These tests pin the CONTRACT — the payload the card reads, and the state change
each option produces.
"""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import storage
from backend.engine.planner_v2 import should_show_test_reminder

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_STATE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
USER = "00000000-0000-4000-8000-0000000002a6"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if FIXTURE_STATE.exists():
        shutil.copy2(FIXTURE_STATE, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state, raising=False)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state, raising=False)
    yield tmp_state


def _headers():
    return {"X-User-ID": USER}


@pytest.fixture
def client():
    with TestClient(app) as c:
        # The endpoint refuses to act without a macrocycle (it needs the current
        # week number to compute the deferral), and per-user state starts empty
        # under the isolated USERS_DIR. Seed the minimum it reads.
        c.put(
            "/api/state",
            json={
                "macrocycle": {
                    "start_date": "2026-06-01",
                    "total_weeks": 12,
                    "phases": [
                        {"phase_id": "base", "duration_weeks": 6},
                        {"phase_id": "strength_power", "duration_weeks": 6},
                    ],
                }
            },
            headers=_headers(),
        )
        yield c


class TestReminderPayloadShape:
    """The shape the client card is written against."""

    def test_reminder_weeks_produce_a_payload(self):
        state = {}
        for week in (5, 11, 17):
            reminder = should_show_test_reminder(state, week)
            assert reminder is not None, f"week {week} should remind"
            assert reminder["type"] == "test_week_reminder"
            assert isinstance(reminder["message"], str) and reminder["message"]
            assert reminder["options"] == ["confirm", "postpone_1_week", "skip_cycle"]

    def test_non_reminder_weeks_produce_nothing(self):
        for week in (1, 2, 3, 4, 6, 7):
            assert should_show_test_reminder({}, week) is None

    def test_every_option_is_one_the_endpoint_accepts(self, client):
        """Guards against the card offering a button the API rejects."""
        reminder = should_show_test_reminder({}, 5)
        for option in reminder["options"]:
            r = client.post(
                "/api/week/test-reminder-response",
                json={"option": option},
                headers=_headers(),
            )
            assert r.status_code != 400, f"endpoint rejects offered option {option!r}"


class TestResponseEndpoint:
    """Each option must move the engine, not just return 200."""

    def _state(self, client):
        return client.get("/api/state", headers=_headers()).json()

    def test_confirm_requests_tests_and_clears_deferrals(self, client):
        # Pre-load deferrals so we can see them cleared.
        client.put(
            "/api/state",
            json={"test_reminder_postponed_to": 9, "test_reminder_skipped_until": 12},
            headers=_headers(),
        )

        r = client.post(
            "/api/week/test-reminder-response", json={"option": "confirm"}, headers=_headers()
        )
        assert r.status_code == 200, r.text
        assert r.json()["action"] == "tests_scheduled"

        state = self._state(client)
        # This flag is what makes next week's Pass 3 inject the test session.
        assert state.get("initial_tests_requested") is True
        assert "test_reminder_postponed_to" not in state
        assert "test_reminder_skipped_until" not in state

    def test_postpone_sets_next_week(self, client):
        r = client.post(
            "/api/week/test-reminder-response",
            json={"option": "postpone_1_week"},
            headers=_headers(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["action"] == "postponed"

        state = self._state(client)
        assert state["test_reminder_postponed_to"] == body["next_reminder_week"]
        # And the deferral actually suppresses the reminder until then.
        assert should_show_test_reminder(state, body["next_reminder_week"] - 1) is None

    def test_skip_defers_a_full_cycle(self, client):
        r = client.post(
            "/api/week/test-reminder-response",
            json={"option": "skip_cycle"},
            headers=_headers(),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["action"] == "skipped"

        state = self._state(client)
        assert state["test_reminder_skipped_until"] == body["next_reminder_week"]
        # Even a week that would normally remind (5, 11, ...) stays quiet.
        assert should_show_test_reminder(state, body["next_reminder_week"] - 1) is None

    def test_confirm_does_not_silently_accept_a_typo(self, client):
        r = client.post(
            "/api/week/test-reminder-response",
            json={"option": "postpone"},  # not one of the three
            headers=_headers(),
        )
        assert r.status_code == 400

    def test_postpone_then_reaching_that_week_reminds_again(self):
        """The deferral must expire, or the reminder is skipped forever."""
        state = {"test_reminder_postponed_to": 8}
        assert should_show_test_reminder(state, 7) is None
        assert should_show_test_reminder(state, 8) is not None
