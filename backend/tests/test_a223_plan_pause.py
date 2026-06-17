"""A223 — Plan pause / resume (Option B from D246).

Covers the 13 invariant tests from the brief. Two layers:
- unit tests on the deps helpers (compute_pause_offset, _effective_anchor,
  current_phase_and_week, week_num_to_phase_context) — deterministic, no client;
- integration tests on POST /api/plan/{pause,resume} and the mutation gating,
  via TestClient with an isolated state file (B216 pattern).

The overarching invariant: start_date is immutable, the offset is a multiple of
7, completed/past sessions are never mutated, and non-paused behavior is
byte-identical to pre-A223.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine.macrocycle_archive import _build_completion_summary

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage, storage_file
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    # Archive into a tmp dir so the cold-store tests never touch backend/data.
    # For user_id=None the archive path derives from storage_file.DATA_DIR.
    monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
    yield tmp_state


# ── date helpers ───────────────────────────────────────────────────────────

def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _this_monday() -> date:
    return _monday(date.today())


def _weeks_ago_monday(n: int) -> str:
    return (_this_monday() - timedelta(weeks=n)).isoformat()


def _mc(start_iso: str, *, end_iso: str | None = None, pause: dict | None = None) -> dict:
    """Synthetic macrocycle: 3 phases x (4,4,4) = 12 weeks, minimal but valid for
    the forward consumers."""
    phases = [
        {"phase_id": "base", "duration_weeks": 4, "domain_weights": {}, "session_pool": [], "intensity_cap": None, "start_week": 1, "end_week": 4},
        {"phase_id": "strength_power", "duration_weeks": 4, "domain_weights": {}, "session_pool": [], "intensity_cap": None, "start_week": 5, "end_week": 8},
        {"phase_id": "power_endurance", "duration_weeks": 4, "domain_weights": {}, "session_pool": [], "intensity_cap": None, "start_week": 9, "end_week": 12},
    ]
    start = date.fromisoformat(start_iso)
    mc = {
        "start_date": start_iso,
        "end_date": end_iso or (start + timedelta(weeks=12) - timedelta(days=1)).isoformat(),
        "total_weeks": 12,
        "phases": phases,
    }
    if pause is not None:
        mc["pause"] = pause
    return mc


def _week_plan(start_iso: str, *, edited: bool = False, status: str | None = None,
               loads=None, feedback=None) -> dict:
    """Minimal 1-week plan anchored at *start_iso* (Monday)."""
    start = date.fromisoformat(start_iso)
    days = []
    for i in range(7):
        day = {"date": (start + timedelta(days=i)).isoformat(),
               "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][i],
               "sessions": []}
        if i == 0:
            sess = {"session_id": "strength_long", "slot": "evening",
                    "resolved": {"resolved_session": {"exercise_instances": []}}}
            if status:
                sess["status"] = status
            if edited:
                sess["_user_edited"] = True
            if loads is not None:
                sess["loads"] = loads
            if feedback is not None:
                sess["feedback_summary"] = feedback
            day["sessions"].append(sess)
        days.append(day)
    return {"start_date": start_iso, "weeks": [{"phase": "base", "days": days}]}


def _seed(mc: dict, *, week_plans: dict | None = None, completion_log: list | None = None) -> None:
    state = deps.load_state(None)
    state["macrocycle"] = deepcopy(mc)
    state["week_plans"] = {k: deepcopy(v) for k, v in (week_plans or {}).items()}
    state["current_week_plan"] = None
    state["session_completion_log"] = completion_log or []
    deps.save_state(state, None)


# ===========================================================================
# Unit: compute_pause_offset (#5 Monday-to-Monday, multiple of 7; #6 sub-week)
# ===========================================================================

class TestComputeOffset:
    def test_same_week_is_zero(self):
        # Mon..Sun of one ISO week → 0 (sub-week pause, product decision "a").
        mon = _this_monday()
        for off in range(0, 7):
            d = (mon + timedelta(days=off)).isoformat()
            assert deps.compute_pause_offset(mon.isoformat(), d) == 0

    def test_one_week(self):
        mon = _this_monday()
        assert deps.compute_pause_offset(mon.isoformat(), (mon + timedelta(days=7)).isoformat()) == 7

    def test_mid_week_to_mid_week_two_weeks(self):
        # paused Wed, resumed Fri two calendar weeks later → 14 (Monday-to-Monday).
        paused = _this_monday() + timedelta(days=2)          # Wed
        resumed = _this_monday() + timedelta(weeks=2, days=4)  # Fri +2w
        assert deps.compute_pause_offset(paused.isoformat(), resumed.isoformat()) == 14

    def test_always_multiple_of_seven(self):
        mon = _this_monday()
        for dd in range(0, 40):
            n = deps.compute_pause_offset(mon.isoformat(), (mon + timedelta(days=dd)).isoformat())
            assert n % 7 == 0 and n >= 0


# ===========================================================================
# Unit: effective anchor / current_phase_and_week (#7 shift; freeze on pause)
# ===========================================================================

class TestEffectiveAnchor:
    def test_no_pause_is_identity(self):
        mc = _mc(_weeks_ago_monday(5))  # 5 weeks in → phase 1 (strength_power), week 1
        pi, wi = deps.current_phase_and_week(mc)
        assert (pi, wi) == (1, 1)  # weeks 0-3 base, week 4 = phase1 wk0, week5 = phase1 wk1

    def test_offset_shifts_position_back(self):
        # Same calendar position, but +14d offset → 2 weeks earlier in the plan.
        mc = _mc(_weeks_ago_monday(5), pause={"active_since": None, "offset_days": 14, "log": []})
        pi, wi = deps.current_phase_and_week(mc)
        assert (pi, wi) == (0, 3)  # week 5 - 2 = week 3 → still base (phase 0), wk 3

    def test_active_pause_freezes_position(self):
        # Plan started 5 weeks ago; pause opened 2 weeks ago. Position must freeze
        # at the pause week (week 3), not advance to week 5.
        mc = _mc(_weeks_ago_monday(5),
                 pause={"active_since": _weeks_ago_monday(2), "offset_days": 0, "log": []})
        pi, wi = deps.current_phase_and_week(mc)
        assert (pi, wi) == (0, 3)

    def test_week_num_context_uses_effective_anchor(self):
        start = _weeks_ago_monday(5)
        mc = _mc(start, pause={"active_since": None, "offset_days": 14, "log": []})
        # Explicit week_num=1 → first Monday at effective_start = start + 14d.
        ctx = deps.week_num_to_phase_context(mc, 1)
        expected = (date.fromisoformat(start) + timedelta(days=14)).isoformat()
        assert ctx["start_date"] == expected


# ===========================================================================
# Integration: pause / resume endpoints
# ===========================================================================

class TestPauseResumeEndpoints:
    def test_pause_sets_active_since_today(self):
        _seed(_mc(_weeks_ago_monday(3)))
        r = client.post("/api/plan/pause")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["paused"] is True
        assert body["active_since"] == date.today().isoformat()
        # persisted
        st = deps.load_state(None)
        assert st["macrocycle"]["pause"]["active_since"] == date.today().isoformat()

    def test_pause_idempotent(self):
        _seed(_mc(_weeks_ago_monday(3)))
        client.post("/api/plan/pause")
        r2 = client.post("/api/plan/pause")
        assert r2.status_code == 200
        st = deps.load_state(None)
        # exactly one open pause, no log entry added yet
        assert st["macrocycle"]["pause"]["active_since"] == date.today().isoformat()
        assert st["macrocycle"]["pause"]["log"] == []

    def test_resume_not_paused_is_noop(self):
        _seed(_mc(_weeks_ago_monday(3)))
        r = client.post("/api/plan/resume")
        assert r.status_code == 200
        assert r.json()["paused"] is False
        assert r.json()["offset_days"] == 0

    def test_resume_extends_offset_and_end_date(self):
        start = _weeks_ago_monday(5)
        end = (date.fromisoformat(start) + timedelta(weeks=12) - timedelta(days=1)).isoformat()
        # Seed an already-open pause that started 2 weeks ago → resume gives N=14.
        _seed(_mc(start, end_iso=end,
                  pause={"active_since": _weeks_ago_monday(2), "offset_days": 0, "log": []}))
        r = client.post("/api/plan/resume")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["shifted_days"] == 14
        assert body["offset_days"] == 14
        st = deps.load_state(None)
        mc = st["macrocycle"]
        assert mc["start_date"] == start                      # immutable
        assert mc["pause"]["active_since"] is None             # cleared
        assert mc["pause"]["log"] == [{"from": _weeks_ago_monday(2), "to": date.today().isoformat()}]
        assert mc["end_date"] == (date.fromisoformat(end) + timedelta(days=14)).isoformat()

    def test_double_pause_resume_cumulative_offset(self):
        start = _weeks_ago_monday(8)
        # First cycle: pause 2w ago resumed today → +14.
        _seed(_mc(start, pause={"active_since": _weeks_ago_monday(2), "offset_days": 0, "log": []}))
        client.post("/api/plan/resume")
        # Second cycle: open a new pause 1w ago, resume → +7. Cumulative = 21.
        st = deps.load_state(None)
        st["macrocycle"]["pause"]["active_since"] = _weeks_ago_monday(1)
        deps.save_state(st, None)
        r = client.post("/api/plan/resume")
        assert r.json()["offset_days"] == 21
        st2 = deps.load_state(None)
        assert len(st2["macrocycle"]["pause"]["log"]) == 2

    def test_offset_always_multiple_of_seven(self):
        start = _weeks_ago_monday(5)
        # Pause opened 9 days ago (not a whole week) → Monday-to-Monday = 7.
        _seed(_mc(start, pause={"active_since": (date.today() - timedelta(days=9)).isoformat(),
                                "offset_days": 0, "log": []}))
        r = client.post("/api/plan/resume")
        assert r.json()["offset_days"] % 7 == 0


# ===========================================================================
# Immutability of past / completed (#1, #2, #9)
# ===========================================================================

class TestImmutability:
    def test_completed_past_week_untouched_after_resume(self):
        start = _weeks_ago_monday(5)
        past = _weeks_ago_monday(4)  # a completed week, before the pause week
        wp = _week_plan(past, status="done", loads={"total_kg": 42}, feedback="hard")
        before = deepcopy(wp)
        _seed(_mc(start, pause={"active_since": _weeks_ago_monday(2), "offset_days": 0, "log": []}),
              week_plans={past: wp})
        client.post("/api/plan/resume")
        st = deps.load_state(None)
        assert past in st["week_plans"], "past week key must be preserved as-is"
        assert st["week_plans"][past] == before, "completed past week mutated!"

    def test_session_table_byte_identical_for_past(self):
        """#9: snapshot every session in past keys before/after pause+resume."""
        start = _weeks_ago_monday(6)
        past_keys = [_weeks_ago_monday(5), _weeks_ago_monday(4), _weeks_ago_monday(3)]
        wps = {k: _week_plan(k, status="done", loads={"x": i}) for i, k in enumerate(past_keys)}
        snapshot = deepcopy(wps)
        _seed(_mc(start, pause={"active_since": _weeks_ago_monday(2), "offset_days": 0, "log": []}),
              week_plans=wps)
        client.post("/api/plan/resume")
        st = deps.load_state(None)
        for k in past_keys:
            assert st["week_plans"][k] == snapshot[k], f"past week {k} changed"

    def test_archived_week_untouched(self):
        """#2: a week in the cold store is never read-modified-written by resume."""
        from backend.engine import storage
        start = _weeks_ago_monday(6)
        arch_key = _weeks_ago_monday(5)
        arch_plan = _week_plan(arch_key, status="done")
        storage.archive_week(None, arch_key, arch_plan)
        before = deepcopy(storage.read_archived_week(None, arch_key))
        _seed(_mc(start, pause={"active_since": _weeks_ago_monday(2), "offset_days": 0, "log": []}))
        client.post("/api/plan/resume")
        assert storage.read_archived_week(None, arch_key) == before


# ===========================================================================
# Future-week handling on resume (#8)
# ===========================================================================

class TestFutureWeekHandling:
    def test_edited_future_week_shifted_and_rekeyed(self):
        start = _weeks_ago_monday(3)
        pause_week = _weeks_ago_monday(1)        # pause opened last week
        future = _this_monday().isoformat()      # a cached future week, > pause week
        wp = _week_plan(future, edited=True)
        _seed(_mc(start, pause={"active_since": pause_week, "offset_days": 0, "log": []}),
              week_plans={future: wp})
        client.post("/api/plan/resume")  # N = 7
        st = deps.load_state(None)
        new_key = (date.fromisoformat(future) + timedelta(days=7)).isoformat()
        assert future not in st["week_plans"], "edited week should have been rekeyed"
        assert new_key in st["week_plans"], "edited week missing at shifted key"
        # content preserved + day dates shifted
        assert st["week_plans"][new_key]["start_date"] == new_key
        assert st["week_plans"][new_key]["weeks"][0]["days"][0]["date"] == new_key

    def test_unedited_future_week_dropped(self):
        start = _weeks_ago_monday(3)
        pause_week = _weeks_ago_monday(1)
        future = _this_monday().isoformat()
        wp = _week_plan(future, edited=False)  # no user edits, no completed sessions
        _seed(_mc(start, pause={"active_since": pause_week, "offset_days": 0, "log": []}),
              week_plans={future: wp})
        client.post("/api/plan/resume")
        st = deps.load_state(None)
        new_key = (date.fromisoformat(future) + timedelta(days=7)).isoformat()
        assert future not in st["week_plans"] and new_key not in st["week_plans"], \
            "unedited future week should be dropped (regenerated lazily)"


# ===========================================================================
# Display classification (#6 paused not missed)
# ===========================================================================

class TestPausedClassification:
    def test_undone_session_in_pause_window_counts_as_paused(self):
        start = _weeks_ago_monday(4)
        end = (date.fromisoformat(start) + timedelta(weeks=12) - timedelta(days=1)).isoformat()
        # The pause week contains a planned-but-undone session.
        pause_week = _weeks_ago_monday(1)
        wp = _week_plan(pause_week, status=None)  # planned, not done/skipped
        mc = _mc(start, end_iso=end,
                 pause={"active_since": None, "offset_days": 7,
                        "log": [{"from": pause_week, "to": _this_monday().isoformat()}]})
        state = {"week_plans": {pause_week: wp}, "session_completion_log": []}
        summary = _build_completion_summary(mc, state)
        assert summary["sessions_paused"] >= 1
        assert summary["sessions_skipped"] == 0

    def test_completion_window_preserves_past_after_resume(self):
        """#3: start_date is immutable, so a session completed BEFORE the pause
        stays inside [start_date, end_date] and keeps counting as done after a
        resume that shifts the future forward (the failure mode that ruled out
        Option A)."""
        start = _weeks_ago_monday(5)
        end = (date.fromisoformat(start) + timedelta(weeks=12) - timedelta(days=1)).isoformat()
        done_day = (date.fromisoformat(start) + timedelta(days=2)).isoformat()  # week 0
        clog = [{"date": done_day, "session_id": "strength_long", "status": "done"}]
        _seed(_mc(start, end_iso=end,
                  pause={"active_since": _weeks_ago_monday(2), "offset_days": 0, "log": []}),
              completion_log=clog)
        client.post("/api/plan/resume")
        st = deps.load_state(None)
        mc = st["macrocycle"]
        assert mc["start_date"] == start  # immutable
        summary = _build_completion_summary(mc, st)
        assert summary["sessions_done"] >= 1, "pre-pause completed session fell out of the window"

    def test_no_pause_no_paused_count(self):
        start = _weeks_ago_monday(4)
        mc = _mc(start)
        wp = _week_plan(_weeks_ago_monday(2), status=None)
        summary = _build_completion_summary(mc, {"week_plans": {_weeks_ago_monday(2): wp}, "session_completion_log": []})
        assert summary["sessions_paused"] == 0


# ===========================================================================
# Mutation gating (#10) + reads available
# ===========================================================================

class TestMutationGating:
    def _pause(self):
        client.post("/api/plan/pause")

    def test_macrocycle_generate_blocked_while_paused(self):
        _seed(_mc(_weeks_ago_monday(3)))
        self._pause()
        r = client.post("/api/macrocycle/generate", json={"total_weeks": 12})
        assert r.status_code == 409
        assert r.json()["detail"]["paused"] is True

    def test_replanner_override_blocked_while_paused(self):
        _seed(_mc(_weeks_ago_monday(3)))
        self._pause()
        r = client.post("/api/replanner/override",
                        json={"week_plan": _week_plan(_this_monday().isoformat()),
                              "intent": "rest", "location": "gym",
                              "reference_date": _this_monday().isoformat()})
        assert r.status_code == 409

    def test_replanner_events_blocked_while_paused(self):
        _seed(_mc(_weeks_ago_monday(3)))
        self._pause()
        r = client.post("/api/replanner/events",
                        json={"week_plan": _week_plan(_this_monday().isoformat()), "events": []})
        assert r.status_code == 409

    def test_weekly_override_blocked_while_paused(self):
        _seed(_mc(_weeks_ago_monday(3)))
        self._pause()
        r = client.put(f"/api/weekly-override/{_this_monday().isoformat()}",
                       json={"days": {}})
        assert r.status_code == 409

    def test_reads_available_while_paused(self):
        _seed(_mc(_weeks_ago_monday(3)))
        self._pause()
        # GET state + week are reads → must still work.
        assert client.get("/api/state").status_code == 200
        assert client.get("/api/week/0").status_code in (200, 422)  # 422 only if no plan


# ===========================================================================
# Independence + device reload (#12, #13)
# ===========================================================================

class TestIndependence:
    def test_subscription_status_unaffected_by_pause(self):
        _seed(_mc(_weeks_ago_monday(3)))
        before = client.get("/api/subscription/status").json()
        client.post("/api/plan/pause")
        after = client.get("/api/subscription/status").json()
        assert before == after

    def test_state_reload_while_paused_keeps_active_since(self):
        _seed(_mc(_weeks_ago_monday(3)))
        client.post("/api/plan/pause")
        # simulate device switch: fresh load
        st = deps.load_state(None)
        assert st["macrocycle"]["pause"]["active_since"] == date.today().isoformat()
        assert deps.is_plan_paused(st) is True
