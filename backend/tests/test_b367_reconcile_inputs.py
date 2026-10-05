"""B367 (#5, #6 + same class) — every reconcile gets the same inputs as /events.

A294 gave ``apply_events`` two reconcile inputs: ``prev_days`` (the trailing
days of the previous week, so the Sunday→Monday finger gap is seen) and
``today`` (days before it are frozen: they count, they are never rewritten).
The other paths that reconcile did not get them:

#5  ``apply_day_override`` reconciled with neither → a Monday override after a
    finger Sunday stayed finger-hard, and a past unmarked day could be rewritten.
#6  ``apply_day_add`` (quick-add) passed ``prev_days`` but not ``today`` → a
    past, unmarked finger Monday was downshifted by a Thursday quick-add.
Same class: /feedback, the outdoor-log sync and the body-part picker called
``apply_events`` with neither.

A301 (guards are alerts): no user action downshifts anything any more. The
same inputs now feed the ALERTS (``guards_v1``): the Sunday→Monday gap is
still seen, and nothing before today is flagged or rewritten.
"""
from __future__ import annotations

import copy
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine.planner_v2 import _SESSION_META
from backend.engine import guards_v1
from backend.engine.replanner_v1 import apply_day_add, apply_day_override

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

FINGER = "strength_long"
MON = "2026-10-05"


def _sess(sid, slot="evening", **kw):
    m = _SESSION_META[sid]
    s = {"slot": slot, "session_id": sid, "location": "gym", "intensity": m["intensity"],
         "tags": {"hard": m["hard"], "finger": m["finger"]}, "constraints_applied": []}
    s.update(kw)
    return s


def _plan(days_sessions, start=MON):
    d0 = date.fromisoformat(start)
    days = [{"date": (d0 + timedelta(i)).isoformat(), "sessions": copy.deepcopy(days_sessions.get(i, []))}
            for i in range(7)]
    return {"start_date": start, "plan_revision": 1,
            "profile_snapshot": {"phase_id": "strength_power", "hard_cap_per_week": 3,
                                 "recovery_multiplier": 1.0},
            "weeks": [{"week_index": 1, "days": days}], "adaptations": []}


def _prev_sunday_finger(start=MON):
    sun = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
    return [{"date": sun, "sessions": [_sess(FINGER, status="done")]}]


def _day(plan, i):
    return plan["weeks"][0]["days"][i]


# ── #6: quick-add freezes the past ──────────────────────────────────────────

class TestQuickAddToday:
    def test_past_unmarked_monday_is_not_downshifted(self):
        plan = _plan({0: [_sess(FINGER)]})
        before_mon = copy.deepcopy(_day(plan, 0))
        out, _w, adj = apply_day_add(plan, session_id="regeneration_easy", target_date="2026-10-08",
                                     location="gym", prev_days=_prev_sunday_finger(), today="2026-10-08")
        assert _day(out, 0) == before_mon, "a past (frozen) day was rewritten"
        assert adj == []

    def test_without_today_nothing_is_rewritten_either(self):
        """A301: the Sunday→Monday gap is an alert on Monday, never a downshift."""
        plan = _plan({0: [_sess(FINGER)]})
        before_mon = copy.deepcopy(_day(plan, 0))
        out, _w, adj = apply_day_add(plan, session_id="regeneration_easy", target_date="2026-10-08",
                                     location="gym", prev_days=_prev_sunday_finger())
        assert adj == [] and _day(out, 0) == before_mon
        alerts = guards_v1.evaluate(out, _prev_sunday_finger())
        assert [(w["code"], w["date"]) for w in alerts] == [("finger_gap", MON)]
        # with today after Monday, Monday is history: counted, not flagged
        assert guards_v1.evaluate(out, _prev_sunday_finger(), "2026-10-08") == []

    def test_frozen_past_still_constrains_today(self):
        """A past finger day counts: a finger quick-add the day after is kept,
        and the gap is said."""
        plan = _plan({0: [_sess(FINGER)]})
        before_mon = copy.deepcopy(_day(plan, 0))
        out, warnings, adj = apply_day_add(plan, session_id=FINGER, target_date="2026-10-06",
                                           location="gym", today="2026-10-06")
        assert _day(out, 0) == before_mon
        assert adj == []
        assert _day(out, 1)["sessions"][0]["session_id"] == FINGER
        assert any("2026-10-06" in w and "finger" in w.lower() for w in warnings)


# ── #5: override sees the previous week and the frozen past ──────────────────

class TestOverrideInputs:
    def test_monday_override_after_finger_sunday_is_an_alert(self):
        out = apply_day_override(_plan({}), intent="strength", location="gym",
                                 reference_date="2026-10-04", target_date=MON,
                                 prev_days=_prev_sunday_finger(), today=MON)
        mon = _day(out, 0)["sessions"][0]
        assert mon["session_id"] == FINGER and "downshifted_from" not in mon
        assert out["adaptations"][-1]["adjustments"] == []
        alerts = guards_v1.evaluate(out, _prev_sunday_finger(), MON)
        assert any(w["code"] == "finger_gap" and w["date"] == MON for w in alerts)

    def test_without_prev_days_no_alert(self):
        out = apply_day_override(_plan({}), intent="strength", location="gym",
                                 reference_date="2026-10-04", target_date=MON)
        assert _day(out, 0)["sessions"][0]["session_id"] == FINGER
        assert guards_v1.evaluate(out) == []

    def test_override_never_rewrites_a_past_unmarked_day(self):
        plan = _plan({0: [_sess(FINGER)], 1: [_sess(FINGER, slot="morning")]})
        before = [copy.deepcopy(_day(plan, i)) for i in (0, 1)]
        out = apply_day_override(plan, intent="rest", location="home",
                                 reference_date="2026-10-07", target_date="2026-10-09",
                                 today="2026-10-08")
        assert [_day(out, i) for i in (0, 1)] == before

    def test_done_and_skipped_sessions_byte_identical(self):
        done = _sess(FINGER, status="done", feedback_summary="hard")
        skipped = _sess("regeneration_easy", slot="morning", status="skipped",
                        skipped_session_id=FINGER, skipped_tags={"hard": True, "finger": True})
        plan = _plan({1: [skipped, done]})
        before = copy.deepcopy(_day(plan, 1))
        out = apply_day_override(plan, intent="strength", location="gym",
                                 reference_date="2026-10-06", target_date="2026-10-07",
                                 prev_days=_prev_sunday_finger(), today="2026-10-07")
        assert _day(out, 1) == before
        # and the override itself, the day after a done finger day, stays — said
        assert _day(out, 2)["sessions"][0]["session_id"] == FINGER
        alerts = guards_v1.evaluate(out, _prev_sunday_finger(), "2026-10-07")
        assert any(w["code"] == "finger_gap" and w["date"] == "2026-10-07" for w in alerts)


# ── server-side floor for callers without a client today ────────────────────

class TestEventFloor:
    def test_floor_is_the_event_date(self):
        from backend.api.routers.replanner import _event_floor
        assert _event_floor("2020-01-02") == "2020-01-02"

    def test_floor_never_beyond_server_today(self):
        from backend.api.routers.replanner import _event_floor
        assert _event_floor("2999-01-01") == date.today().isoformat()

    def test_unusable_date_means_no_floor(self):
        from backend.api.routers.replanner import _event_floor
        assert _event_floor(None) is None
        assert _event_floor("garbage") is None


# ── API: the routers pass the inputs through ────────────────────────────────

@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


def _current_monday() -> str:
    d = date.today()
    return (d - timedelta(days=d.weekday())).isoformat()


def _seed_prev_week_finger_sunday(monday: str) -> None:
    prev_monday = (date.fromisoformat(monday) - timedelta(days=7)).isoformat()
    prev = _plan({6: [_sess(FINGER, status="done")]}, start=prev_monday)
    state = deps.load_state(None)
    state.setdefault("week_plans", {})[prev_monday] = prev
    state.pop("macrocycle_paused", None)
    deps.save_state(state, None)


class TestRoutersPassInputs:
    def test_override_endpoint_seeds_prev_week(self, isolated_state):
        monday = _current_monday()
        _seed_prev_week_finger_sunday(monday)
        r = client.post("/api/replanner/override", json={
            "intent": "strength", "location": "gym",
            "reference_date": (date.fromisoformat(monday) - timedelta(days=1)).isoformat(),
            "target_date": monday, "week_plan": _plan({}, start=monday), "today": monday,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        mon = body["week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert mon["session_id"] == FINGER
        assert body["adjustments"] == []
        # A301: the previous week seeds the alerts of the response.
        assert any(w["code"] == "finger_gap" and w["date"] == monday for w in body["guard_warnings"])
        assert any("finger" in w.lower() for w in body["warnings"])

    def test_quick_add_endpoint_freezes_the_past(self, isolated_state):
        monday = _current_monday()
        _seed_prev_week_finger_sunday(monday)
        plan = _plan({0: [_sess(FINGER)]}, start=monday)
        before_mon = copy.deepcopy(_day(plan, 0))
        target = (date.fromisoformat(monday) + timedelta(days=6)).isoformat()
        r = client.post("/api/replanner/quick-add", json={
            "week_plan": plan, "session_id": "regeneration_easy", "target_date": target,
            "slot": "morning", "location": "gym", "today": target,
        })
        assert r.status_code == 200, r.text
        mon = r.json()["week_plan"]["weeks"][0]["days"][0]
        assert mon["sessions"][0]["session_id"] == before_mon["sessions"][0]["session_id"]
        assert "downshifted_from" not in mon["sessions"][0]
