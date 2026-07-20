"""B287 tranche 1 — past-session immutability in the replanner.

Four confirmed findings, all on paths that regenerate a week in place:

R-1  apply_events(set_availability) replaced updated["weeks"] with a freshly
     generated week and NO preserve step → every done/skipped session in the
     week was destroyed. Now routed through regenerate_preserving_completed.
R-2  POST /api/replanner/events had no B257 past-week guard (only /override
     did), so the same regeneration was reachable on an immutable past week.
R-3  the replanner called _build_session_pool(phase_id) without discipline →
     a boulder user got boulder domain weights + a LEAD session pool.
R-4  merge_prev_week_sessions' weekday fallback re-stamped copied["date"],
     moving another day's completed sessions onto a past date (fabricated
     history; _attach_feedback then binds feedback by the wrong (date,
     session_id) key).

preserve_before floor (B287 decision 4): max(today, week start_date).
"""
from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine.macrocycle_v1 import _SESSION_POOL, _SESSION_POOL_BOULDER, _build_session_pool
from backend.engine.replanner_v1 import apply_events, merge_prev_week_sessions

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


def _monday(weeks_offset: int) -> str:
    d = date.today() + timedelta(weeks=weeks_offset)
    return (d - timedelta(days=d.weekday())).isoformat()


PAST_KEY = _monday(-3)
CURRENT_KEY = _monday(0)
FUTURE_KEY = _monday(+1)


def _availability(all_available: bool = True) -> dict:
    """Availability grid in the shape the engine expects."""
    return {
        wd: {
            slot: {
                "available": all_available and slot == "evening",
                "preferred_location": "home",
                "gym_id": None,
                "locations": ["home"],
            }
            for slot in ("morning", "lunch", "evening")
        }
        for wd in WEEKDAYS
    }


def _plan(start_date: str, *, discipline: str = "lead",
          done_on: tuple[int, ...] = ()) -> dict:
    """1-week plan anchored at *start_date*, with done sessions on given offsets."""
    start = date.fromisoformat(start_date)
    days = []
    for i in range(7):
        day_iso = (start + timedelta(days=i)).isoformat()
        entry = {"date": day_iso, "weekday": WEEKDAYS[i], "sessions": []}
        if i in done_on:
            entry["sessions"].append({
                "session_id": "strength_long",
                "slot": "evening",
                "status": "done",
                "feedback_summary": "hard",
                "resolved": {"resolved_session": {"exercise_instances": [
                    {"exercise_id": "pullup_weighted", "load_kg": 12.5}]}},
                "completed_at": f"{day_iso}T19:30:00Z",
            })
        days.append(entry)
    return {
        "start_date": start_date,
        "plan_revision": 1,
        "profile_snapshot": {
            "phase_id": "base",
            "discipline": discipline,
            "allowed_locations": ["home", "gym"],
            "hard_cap_per_week": 3,
        },
        "weeks": [{"phase": "base", "days": days}],
    }


def _set_availability_event(target_date: str) -> dict:
    return {
        "event_type": "set_availability",
        "date": target_date,
        "availability": {"slot": "evening", "available": False},
    }


def _done_sessions(plan: dict) -> list[dict]:
    return [
        s
        for d in plan["weeks"][0]["days"]
        for s in d.get("sessions", [])
        if s.get("status") == "done"
    ]


# ── R-1: set_availability must not destroy completed sessions ───────────────

class TestR1SetAvailabilityPreserves:
    def test_completed_session_survives_regeneration(self):
        """The bug: updated["weeks"] = regenerated["weeks"] wiped done sessions."""
        plan = _plan(CURRENT_KEY, done_on=(0,))
        before = deepcopy(_done_sessions(plan)[0])

        out = apply_events(
            plan,
            [_set_availability_event(CURRENT_KEY)],
            availability=_availability(),
        )

        survivors = _done_sessions(out)
        assert survivors, "set_availability regeneration destroyed the done session"
        after = survivors[0]
        # Full immutability contract: id, load, feedback, status, timestamp.
        assert after["session_id"] == before["session_id"]
        assert after["status"] == "done"
        assert after["feedback_summary"] == before["feedback_summary"]
        assert after["completed_at"] == before["completed_at"]
        assert (after["resolved"]["resolved_session"]["exercise_instances"]
                == before["resolved"]["resolved_session"]["exercise_instances"])

    def test_past_days_of_current_week_copied_wholesale(self):
        """Days before today are frozen even if regeneration would re-plan them."""
        today = date.today()
        offset = today.weekday()
        if offset == 0:
            pytest.skip("no past day inside the current week on a Monday")
        plan = _plan(CURRENT_KEY, done_on=(0,))
        # Mark Monday's session skipped: skipped is preservable too.
        plan["weeks"][0]["days"][0]["sessions"][0]["status"] = "skipped"

        out = apply_events(
            plan,
            [_set_availability_event(CURRENT_KEY)],
            availability=_availability(),
        )

        mon = out["weeks"][0]["days"][0]
        assert [s.get("status") for s in mon["sessions"]] == ["skipped"]

    def test_future_week_completed_ahead_of_time_preserved(self):
        """Decision 4: floor = max(today, start_date) → a future week's completed
        session is still preserved by the session-level merge."""
        plan = _plan(FUTURE_KEY, done_on=(2,))
        out = apply_events(
            plan,
            [_set_availability_event(FUTURE_KEY)],
            availability=_availability(),
        )
        assert _done_sessions(out), "session completed ahead of time was lost"

    def test_regeneration_still_happens(self):
        """Guard against over-correcting: the plan must still be re-planned
        (revision bumped), not just returned untouched."""
        plan = _plan(CURRENT_KEY, done_on=(0,))
        out = apply_events(
            plan,
            [_set_availability_event(CURRENT_KEY)],
            availability=_availability(),
        )
        assert out.get("plan_revision", 1) > plan["plan_revision"]


class TestPreserveFloor:
    # Imported lazily: at pre-B287 HEAD the helper does not exist, and a
    # module-level import would turn the whole file into a collection error,
    # hiding whether the other tests actually catch their bug.
    def test_current_week_floor_is_today(self):
        from backend.engine.replanner_v1 import _preserve_floor
        today = date.today().isoformat()
        assert _preserve_floor(_plan(CURRENT_KEY), today=today) == today

    def test_future_week_floor_is_its_monday(self):
        from backend.engine.replanner_v1 import _preserve_floor
        today = date.today().isoformat()
        assert _preserve_floor(_plan(FUTURE_KEY), today=today) == FUTURE_KEY

    def test_missing_start_date_falls_back_to_today(self):
        from backend.engine.replanner_v1 import _preserve_floor
        today = date.today().isoformat()
        assert _preserve_floor({}, today=today) == today


# ── R-2: /events must refuse regenerating events on a past week ─────────────

class TestR2EventsPastWeekGuard:
    def _seed(self) -> None:
        state = deps.load_state(None)
        state["availability"] = _availability()
        deps.save_state(state, None)

    def test_set_availability_on_past_week_rejected(self):
        self._seed()
        r = client.post("/api/replanner/events", json={
            "week_plan": _plan(PAST_KEY, done_on=(0,)),
            "events": [_set_availability_event(PAST_KEY)],
        })
        assert r.status_code == 422, r.text
        assert "past" in r.json()["detail"].lower()

    def test_override_on_past_week_still_rejected(self):
        """The sibling entry point keeps its B257 guard (no regression)."""
        self._seed()
        r = client.post("/api/replanner/override", json={
            "intent": "rest", "location": "home", "reference_date": PAST_KEY,
            "week_plan": _plan(PAST_KEY, done_on=(0,)), "target_date": PAST_KEY,
        })
        assert r.status_code == 422, r.text
        assert "past" in r.json()["detail"].lower()

    def test_set_availability_on_current_week_allowed(self):
        """The guard must not block the current week."""
        self._seed()
        r = client.post("/api/replanner/events", json={
            "week_plan": _plan(CURRENT_KEY, done_on=(0,)),
            "events": [_set_availability_event(CURRENT_KEY)],
        })
        assert not (r.status_code == 422
                    and "past" in str(r.json().get("detail", "")).lower()), \
            "current week must not be rejected by the past-week guard"

    def test_mark_done_on_past_week_still_allowed(self):
        """Scoped guard: retroactively ticking a forgotten session is explicit
        user edit (the pillar's one exception) and must keep working — the UI
        renders past weeks whenever a saved plan exists."""
        self._seed()
        r = client.post("/api/replanner/events", json={
            "week_plan": _plan(PAST_KEY),
            "events": [{"event_type": "mark_done", "date": PAST_KEY,
                        "session_id": "strength_long"}],
        })
        assert not (r.status_code == 422
                    and "past" in str(r.json().get("detail", "")).lower()), \
            "mark_done on a past week must not hit the regeneration guard"


# ── R-3: session pool must follow the discipline ────────────────────────────

class TestR3DisciplinePool:
    def test_pools_actually_differ(self):
        """Precondition: without this the finding would be untestable."""
        assert _build_session_pool("base", discipline="boulder") != \
            _build_session_pool("base", discipline="lead")

    def test_boulder_user_gets_boulder_pool(self):
        """The bug: _build_session_pool(phase_id) defaulted to lead, so a boulder
        snapshot produced boulder weights + lead sessions."""
        plan = _plan(CURRENT_KEY, discipline="boulder")
        out = apply_events(
            plan,
            [_set_availability_event(CURRENT_KEY)],
            availability=_availability(),
        )
        scheduled = {
            s.get("session_id")
            for d in out["weeks"][0]["days"]
            for s in d.get("sessions", [])
        }
        lead_only = set(_SESSION_POOL["base"]) - set(_SESSION_POOL_BOULDER["base"])
        assert not (scheduled & lead_only), (
            f"boulder user was scheduled lead-only sessions: {scheduled & lead_only}"
        )

    def test_lead_user_unaffected(self):
        plan = _plan(CURRENT_KEY, discipline="lead")
        out = apply_events(
            plan,
            [_set_availability_event(CURRENT_KEY)],
            availability=_availability(),
        )
        scheduled = {
            s.get("session_id")
            for d in out["weeks"][0]["days"]
            for s in d.get("sessions", [])
        }
        boulder_only = set(_SESSION_POOL_BOULDER["base"]) - set(_SESSION_POOL["base"])
        assert not (scheduled & boulder_only)


# ── R-4: weekday fallback must never re-stamp a date ────────────────────────

class TestR4NoDateRestamping:
    def test_past_day_not_filled_from_a_different_date(self):
        """Non-overlapping ranges (macrocycle start_date shifted): below the
        floor the weekday fallback used to copy another week's day wholesale and
        re-stamp its date, inventing a completed session that never happened on
        that date. Days >= the floor keep the sanctioned B114 fallback (see
        test_future_day_weekday_fallback_still_merges_sessions) — this test
        targets the frozen region only.
        """
        prev = _plan(PAST_KEY, done_on=(0, 1))         # done on PAST_KEY Mon+Tue
        new = _plan(CURRENT_KEY)                        # different date range
        # Floor mid-week so Mon/Tue are strictly below it and therefore frozen.
        floor = (date.fromisoformat(CURRENT_KEY) + timedelta(days=2)).isoformat()

        out = merge_prev_week_sessions(prev, new, preserve_before=floor)

        for day in out["weeks"][0]["days"][:2]:
            assert day["date"] < floor
            for sess in day.get("sessions", []):
                assert sess.get("status") != "done", (
                    f"fabricated a done session on {day['date']} from another week"
                )

    def test_dates_are_never_rewritten(self):
        """Every day in the merged plan keeps the new plan's own date."""
        prev = _plan(PAST_KEY, done_on=(0, 2))
        new = _plan(CURRENT_KEY)
        expected = [d["date"] for d in new["weeks"][0]["days"]]

        out = merge_prev_week_sessions(prev, new, preserve_before=date.today().isoformat())

        assert [d["date"] for d in out["weeks"][0]["days"]] == expected

    def test_same_date_merge_still_works(self):
        """Regression: the legitimate same-date path (B114) is untouched."""
        prev = _plan(CURRENT_KEY, done_on=(0,))
        new = _plan(CURRENT_KEY)
        today = date.today().isoformat()

        out = merge_prev_week_sessions(prev, new, preserve_before=today)

        mon = out["weeks"][0]["days"][0]
        assert any(s.get("status") == "done" for s in mon["sessions"]), \
            "same-date preservation must keep working"

    def test_future_day_weekday_fallback_still_merges_sessions(self):
        """The fallback stays allowed for days >= preserve_before, where it only
        merges preservable sessions and never rewrites a date."""
        prev = _plan(PAST_KEY, done_on=(3,))
        new = _plan(CURRENT_KEY)
        # Floor at the week's Monday → every day is >= preserve_before.
        out = merge_prev_week_sessions(prev, new, preserve_before=CURRENT_KEY)

        thu = out["weeks"][0]["days"][3]
        assert thu["date"] == new["weeks"][0]["days"][3]["date"]
        assert any(s.get("status") == "done" for s in thu["sessions"])
