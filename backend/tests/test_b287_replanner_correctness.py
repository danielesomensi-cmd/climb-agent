"""B287 tranche 2 — replanner correctness (R-5, R-6, R-7).

R-5  apply_day_add skipped _reconcile entirely: the 48h finger gap and the
     weekly hard cap were warned about but never enforced, and the enforcers
     scanned only weeks[0] with last_finger_date=None, so the Sunday->Monday
     boundary was never checked. Now reconciliation runs, is seeded with the
     previous week's trailing days, and every downshift is reported in a
     machine-readable `adjustments` list (decision: enforce, never silently).
R-6  persist_week_plan and _is_current_macrocycle_monday recomputed the current
     week's Monday from the RAW macrocycle start_date, ignoring the A223 pause
     offset, so with a pause current_week_plan was never refreshed.
R-7  _auto_resolve never passed `phase`, so resolve_session fell back to
     date.today() and ordered a future week's exercises with today's phase.
R-8  (found while verifying R-5) the in-week scan excluded status == "done"
     from the WHOLE finger computation: a session actually trained on Tuesday
     neither constrained Wednesday — a hole in the 48h invariant — nor was
     protected from the downshift loop, which rewrote every finger session on a
     violating day, completed ones included. Same rewrite hole in _enforce_caps.
     Done sessions are constraints but never targets; skipped are neither.
"""
from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.api import deps
from backend.api.routers import replanner as replanner_router
from backend.api.routers.feedback import _is_current_macrocycle_monday
from backend.engine.replanner_v1 import (
    _enforce_caps,
    _enforce_no_consecutive_finger,
    _reconcile,
    apply_day_add,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
FINGER_SESSION = "finger_strength_home"   # hard + finger
EASY_SESSION = "regeneration_easy"


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


def _monday(weeks_offset: int = 0) -> str:
    d = date.today() + timedelta(weeks=weeks_offset)
    return (d - timedelta(days=d.weekday())).isoformat()


def _plan(start_date: str, *, finger_on: tuple[int, ...] = (),
          hard_cap: int = 3) -> dict:
    start = date.fromisoformat(start_date)
    days = []
    for i in range(7):
        entry = {
            "date": (start + timedelta(days=i)).isoformat(),
            "weekday": WEEKDAYS[i],
            "sessions": [],
        }
        if i in finger_on:
            entry["sessions"].append({
                "session_id": FINGER_SESSION,
                "slot": "evening",
                "location": "home",
                "phase_id": "base",
                "tags": {"hard": True, "finger": True},
            })
        days.append(entry)
    return {
        "start_date": start_date,
        "profile_snapshot": {
            "phase_id": "base",
            "discipline": "lead",
            "hard_cap_per_week": hard_cap,
            "recovery_multiplier": 1.0,
        },
        "weeks": [{"phase": "base", "days": days}],
    }


def _session_on(plan: dict, index: int, slot: str = "evening") -> dict | None:
    day = plan["weeks"][0]["days"][index]
    return next((s for s in day.get("sessions", []) if s.get("slot") == slot), None)


# ── R-5a: _reconcile actually runs on the quick-add path ────────────────────

class TestR5ReconcileRuns:
    def test_finger_gap_enforced_not_just_warned(self):
        """Tuesday finger quick-add next to a Monday finger session is downshifted."""
        plan = _plan(_monday(), finger_on=(0,))
        updated, _warnings, adjustments = apply_day_add(
            plan,
            session_id=FINGER_SESSION,
            target_date=plan["weeks"][0]["days"][1]["date"],
            slot="evening",
            location="home",
        )
        tue = _session_on(updated, 1)
        assert tue is not None, "quick-add must still fill the slot"
        assert tue["session_id"] == EASY_SESSION, \
            "48h finger gap must be enforced, not merely warned"
        assert adjustments, "the downshift must be reported"

    def test_adjustment_payload_is_machine_readable(self):
        """No silent mutation: the reason must be inspectable by the client."""
        plan = _plan(_monday(), finger_on=(0,))
        target = plan["weeks"][0]["days"][1]["date"]
        _updated, _warnings, adjustments = apply_day_add(
            plan, session_id=FINGER_SESSION, target_date=target,
            slot="evening", location="home",
        )
        entry = next(a for a in adjustments if a["date"] == target)
        assert entry["action"] == "downgraded"
        assert entry["reason"] == "finger_spacing_downshift"
        assert entry["previous_session_id"] == FINGER_SESSION
        assert entry["session_id"] == EASY_SESSION
        assert entry["slot"] == "evening"

    def test_no_adjustments_when_nothing_violated(self):
        """A legal quick-add must report an empty list, not a phantom entry."""
        plan = _plan(_monday())
        _updated, _warnings, adjustments = apply_day_add(
            plan, session_id="prehab_maintenance", target_date=plan["weeks"][0]["days"][2]["date"],
            slot="morning", location="home",
        )
        assert adjustments == []

    def test_adjustments_recorded_in_adaptations(self):
        """The plan itself carries the trace, so it survives persistence."""
        plan = _plan(_monday(), finger_on=(0,))
        updated, _w, adjustments = apply_day_add(
            plan, session_id=FINGER_SESSION,
            target_date=plan["weeks"][0]["days"][1]["date"],
            slot="evening", location="home",
        )
        entry = next(a for a in updated["adaptations"] if a["type"] == "quick_add")
        assert entry["adjustments"] == adjustments


# ── R-5b: cross-week seeding (Sunday → Monday) ──────────────────────────────

class TestR5CrossWeekSeeding:
    def test_sunday_finger_blocks_monday_finger(self):
        """The boundary the in-week scan could never see."""
        prev = _plan(_monday(-1), finger_on=(6,))       # finger last Sunday
        cur = _plan(_monday(), finger_on=(0,))          # finger this Monday
        _reconcile(cur, prev_days=prev["weeks"][0]["days"])
        assert _session_on(cur, 0)["session_id"] == EASY_SESSION

    def test_without_seed_behaviour_is_unchanged(self):
        """Regression guard: no prev_days → exactly the previous behaviour."""
        cur = _plan(_monday(), finger_on=(0,))
        _reconcile(cur)
        assert _session_on(cur, 0)["session_id"] == FINGER_SESSION

    def test_completed_previous_session_still_seeds(self):
        """A finger session actually PERFORMED last Sunday must block Monday:
        for the seed, what happened counts even though the in-week scan skips
        done sessions."""
        prev = _plan(_monday(-1), finger_on=(6,))
        prev["weeks"][0]["days"][6]["sessions"][0]["status"] = "done"
        cur = _plan(_monday(), finger_on=(0,))
        _reconcile(cur, prev_days=prev["weeks"][0]["days"])
        assert _session_on(cur, 0)["session_id"] == EASY_SESSION

    def test_distant_previous_finger_does_not_block(self):
        """Seeding must not over-trigger: last Monday is far enough away."""
        prev = _plan(_monday(-1), finger_on=(0,))
        cur = _plan(_monday(), finger_on=(0,))
        _enforce_no_consecutive_finger(cur, prev_days=prev["weeks"][0]["days"])
        assert _session_on(cur, 0)["session_id"] == FINGER_SESSION

    def test_router_helper_reads_previous_week(self):
        state = {"week_plans": {_monday(-1): _plan(_monday(-1), finger_on=(6,))}}
        days = replanner_router._prev_week_days(state, _monday())
        assert days and len(days) == 7

    def test_router_helper_tolerates_missing_neighbour(self):
        assert replanner_router._prev_week_days({}, _monday()) is None
        assert replanner_router._prev_week_days({"week_plans": {}}, None) is None
        assert replanner_router._prev_week_days({"week_plans": {}}, "not-a-date") is None


# ── R-8: done sessions constrain, but are never rewritten ───────────────────

class TestR8DoneSessionsAreConstraints:
    """Mirror of the seeding rule, inside the week.

    Found while verifying the seed asymmetry: the in-week scan excluded
    ``status == "done"`` from the WHOLE computation, which meant a completed
    finger session neither constrained the following days (hole in the 48h
    invariant) nor was protected from the downshift loop, which rewrote every
    finger session on a violating day — completed ones included.
    """

    def _week(self, sessions_by_index: dict) -> dict:
        plan = _plan(_monday())
        for idx, sessions in sessions_by_index.items():
            plan["weeks"][0]["days"][idx]["sessions"] = sessions
        return plan

    def _finger(self, *, status: str | None = None, slot: str = "evening") -> dict:
        s = {
            "session_id": FINGER_SESSION, "slot": slot, "location": "home",
            "phase_id": "base", "tags": {"hard": True, "finger": True},
        }
        if status:
            s["status"] = status
        return s

    def test_completed_session_constrains_the_next_day(self):
        """A finger session TRAINED on Tuesday must block a Wednesday one."""
        plan = self._week({1: [self._finger(status="done")], 2: [self._finger()]})
        _enforce_no_consecutive_finger(plan)
        assert _session_on(plan, 2)["session_id"] == EASY_SESSION

    def test_completed_session_is_never_rewritten(self):
        """Immutability: the downshift must not touch what was already trained."""
        plan = self._week({
            0: [self._finger()],
            1: [self._finger(status="done", slot="morning"), self._finger(slot="evening")],
        })
        _enforce_no_consecutive_finger(plan)
        done = _session_on(plan, 1, slot="morning")
        assert done["session_id"] == FINGER_SESSION, "a completed session was rewritten"
        assert done["status"] == "done"
        assert _session_on(plan, 1, slot="evening")["session_id"] == EASY_SESSION

    def test_completed_session_keeps_anchoring_after_a_downshift(self):
        """The day stays a finger day thanks to its immutable done session, so
        the day after is still constrained."""
        plan = self._week({
            0: [self._finger()],
            1: [self._finger(status="done", slot="morning"), self._finger(slot="evening")],
            2: [self._finger()],
        })
        _enforce_no_consecutive_finger(plan)
        assert _session_on(plan, 2)["session_id"] == EASY_SESSION

    def test_skipped_session_constrains_nothing(self):
        """A skipped session never happened — it must not block the next day."""
        plan = self._week({1: [self._finger(status="skipped")], 2: [self._finger()]})
        _enforce_no_consecutive_finger(plan)
        assert _session_on(plan, 2)["session_id"] == FINGER_SESSION

    def test_skipped_session_is_never_rewritten(self):
        """Skipped is preservable too (_is_preservable), so it must survive."""
        plan = self._week({
            0: [self._finger()],
            1: [self._finger(status="skipped", slot="morning"), self._finger(slot="evening")],
        })
        _enforce_no_consecutive_finger(plan)
        assert _session_on(plan, 1, slot="morning")["session_id"] == FINGER_SESSION

    def test_cap_enforcer_never_rewrites_a_completed_session(self):
        """Same hole in _enforce_caps' inner loop."""
        def hard(status=None, slot="evening"):
            s = {"session_id": "strength_long", "slot": slot, "location": "home",
                 "tags": {"hard": True, "finger": False}}
            if status:
                s["status"] = status
            return s

        plan = _plan(_monday(), hard_cap=3)
        for i in range(3):
            plan["weeks"][0]["days"][i]["sessions"] = [hard()]
        plan["weeks"][0]["days"][3]["sessions"] = [
            hard(status="done", slot="morning"), hard(slot="evening"),
        ]

        _enforce_caps(plan)

        assert _session_on(plan, 3, slot="morning")["session_id"] == "strength_long"
        assert _session_on(plan, 3, slot="morning")["status"] == "done"
        assert _session_on(plan, 3, slot="evening")["session_id"] == EASY_SESSION

    def test_quick_add_blocked_by_a_session_trained_yesterday(self):
        """End-to-end: the real user path this invariant exists for."""
        plan = self._week({0: [self._finger(status="done")]})
        updated, _w, adjustments = apply_day_add(
            plan, session_id=FINGER_SESSION,
            target_date=plan["weeks"][0]["days"][1]["date"],
            slot="evening", location="home",
        )
        assert _session_on(updated, 1)["session_id"] == EASY_SESSION
        assert adjustments[0]["reason"] == "finger_spacing_downshift"


# ── R-6: pause-aware current-week anchor ────────────────────────────────────

def _seed_macrocycle(*, offset_days: int) -> dict:
    """State whose macrocycle started 2 weeks ago with a pause offset."""
    state = deps.load_state(None)
    mc = state["macrocycle"]
    mc["start_date"] = _monday(-2)
    mc["phases"][0]["duration_weeks"] = max(mc["phases"][0].get("duration_weeks", 1), 8)
    mc["pause"] = {"offset_days": offset_days}
    deps.save_state(state, None)
    return state


class TestR6PauseAwareAnchor:
    def test_persist_week_plan_updates_current_with_pause_offset(self):
        """With a 7-day pause offset the current week is the macrocycle's week 2
        anchor shifted by a week; the raw computation missed it entirely."""
        state = _seed_macrocycle(offset_days=7)
        expected = deps.week_num_to_phase_context(state["macrocycle"], 0)["start_date"]
        plan = _plan(expected)

        replanner_router.persist_week_plan(plan, state, None)

        assert state.get("current_week_plan") is plan, \
            "paused plan: the current week must still refresh current_week_plan"

    def test_persist_week_plan_ignores_non_current_week(self):
        state = _seed_macrocycle(offset_days=7)
        state["current_week_plan"] = None
        other = _plan(_monday(+3))

        replanner_router.persist_week_plan(other, state, None)

        assert state["current_week_plan"] is None
        assert _monday(+3) in state["week_plans"]

    def test_is_current_macrocycle_monday_pause_aware(self):
        state = _seed_macrocycle(offset_days=7)
        expected = deps.week_num_to_phase_context(state["macrocycle"], 0)["start_date"]
        assert _is_current_macrocycle_monday(state, expected) is True
        assert _is_current_macrocycle_monday(state, _monday(+2)) is False

    def test_no_pause_behaviour_unchanged(self):
        """offset_days = 0 must reduce to exactly the previous result."""
        state = _seed_macrocycle(offset_days=0)
        expected = deps.week_num_to_phase_context(state["macrocycle"], 0)["start_date"]
        assert _is_current_macrocycle_monday(state, expected) is True

    def test_missing_macrocycle_is_not_current(self):
        assert _is_current_macrocycle_monday({}, _monday()) is False


# ── R-7: phase comes from the plan, not from today ──────────────────────────

class TestR7PhaseFromPlan:
    def test_auto_resolve_passes_session_phase(self, monkeypatch):
        """A future week in a different phase must not be resolved with today's."""
        captured: list = []

        def _fake_resolve(**kwargs):
            captured.append(kwargs.get("phase"))
            return {"resolved_session": {"exercise_instances": []}}

        monkeypatch.setattr(replanner_router, "resolve_session", _fake_resolve)

        plan = _plan(_monday(+2))
        plan["profile_snapshot"]["phase_id"] = "performance"
        plan["weeks"][0]["days"][1]["sessions"].append({
            "session_id": "prehab_maintenance", "slot": "evening",
            "location": "home", "phase_id": "performance",
        })

        replanner_router._auto_resolve(plan, deps.load_state(None), None)

        assert captured, "resolver was never called"
        assert set(captured) == {"performance"}, \
            f"phase must come from the plan, got {set(captured)}"

    def test_falls_back_to_plan_snapshot_when_session_has_no_phase(self, monkeypatch):
        captured: list = []

        def _fake_resolve(**kwargs):
            captured.append(kwargs.get("phase"))
            return {"resolved_session": {"exercise_instances": []}}

        monkeypatch.setattr(replanner_router, "resolve_session", _fake_resolve)

        plan = _plan(_monday(+2))
        plan["profile_snapshot"]["phase_id"] = "power_endurance"
        plan["weeks"][0]["days"][1]["sessions"].append({
            "session_id": "prehab_maintenance", "slot": "evening", "location": "home",
        })

        replanner_router._auto_resolve(plan, deps.load_state(None), None)

        assert set(captured) == {"power_endurance"}
