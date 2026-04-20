"""B216: Monday rollover — stale current_week_plan cache + broad except in feedback.

Defect A: week.py cache-hit branch did not refresh state["current_week_plan"]
          when the per-week cache was already correct for today; downstream
          readers (feedback.py, free_session.py) continued to see last week.

Defect B: feedback.py:82 caught `except Exception` and silent-skipped the
          mark_done when `_find_day` raised ValueError against a stale
          current_week_plan. Feedback persisted, but the session stayed
          Planned forever. Fix narrows to ValueError + retries against
          week_plans[target_monday] before giving up.

Tests T1..T6 spec'd in docs/briefs/B216_phase1_analysis.md §1.4.
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
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


def _this_monday() -> str:
    d = date.today()
    return (d - timedelta(days=d.weekday())).isoformat()


def _prev_monday() -> str:
    d = date.today() - timedelta(days=7)
    return (d - timedelta(days=d.weekday())).isoformat()


def _make_week_plan(start_date: str, session_id: str = "strength_long", status: str | None = None) -> dict:
    """Build a minimal valid 1-week plan anchored at *start_date* (Monday)."""
    days = []
    start = date.fromisoformat(start_date)
    for i in range(7):
        day_iso = (start + timedelta(days=i)).isoformat()
        day_entry = {"date": day_iso, "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][i], "sessions": []}
        if i == 0:
            sess = {
                "session_id": session_id,
                "slot": "evening",
                "resolved": {"resolved_session": {"exercise_instances": []}},
            }
            if status:
                sess["status"] = status
            day_entry["sessions"].append(sess)
        days.append(day_entry)
    return {
        "start_date": start_date,
        "weeks": [{"phase": "base", "days": days}],
    }


def _seed_rollover_state(
    *,
    legacy_start: str | None,
    week_plans: dict[str, dict],
    mc_start: str | None = None,
    completion_log: list | None = None,
) -> None:
    """Write a synthetic state simulating a rollover.

    legacy_start: start_date for state["current_week_plan"], or None to clear.
    week_plans: dict[start_date -> plan] for state["week_plans"].
    mc_start: override macrocycle.start_date (default: prev_monday so current
              macrocycle week == this_monday).
    """
    state = deps.load_state(None)
    state["week_plans"] = {k: deepcopy(v) for k, v in week_plans.items()}
    if legacy_start and legacy_start in week_plans:
        state["current_week_plan"] = deepcopy(week_plans[legacy_start])
    elif legacy_start is None:
        state["current_week_plan"] = None
    else:
        # legacy points to a plan not in week_plans — simulate out-of-sync drift
        state["current_week_plan"] = _make_week_plan(legacy_start)
    state["session_completion_log"] = completion_log if completion_log is not None else []
    # Force macrocycle.start_date so current_phase_and_week returns a known value
    if mc_start is None:
        mc_start = _prev_monday()
    if state.get("macrocycle"):
        state["macrocycle"]["start_date"] = mc_start
        # Ensure phases[0] has enough duration that today falls inside phase 0
        phases = state["macrocycle"].get("phases") or []
        if phases:
            phases[0]["duration_weeks"] = max(phases[0].get("duration_weeks", 1), 4)
    deps.save_state(state, None)


# ============================================================================
# T1 — cache-hit refreshes current_week_plan on calendar advance (Defect A)
# ============================================================================

class TestT1CacheHitSelfHeal:
    def test_cache_hit_refreshes_stale_legacy_slot(self):
        """GET /api/week/0 with stale current_week_plan + fresh week_plans[this]
        should self-heal current_week_plan to this_monday."""
        this_mon = _this_monday()
        prev_mon = _prev_monday()
        _seed_rollover_state(
            legacy_start=prev_mon,
            week_plans={
                prev_mon: _make_week_plan(prev_mon, status="done"),
                this_mon: _make_week_plan(this_mon),
            },
            mc_start=prev_mon,
        )

        r = client.get("/api/week/0")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["week_plan"]["start_date"] == this_mon

        state = deps.load_state(None)
        assert state["current_week_plan"]["start_date"] == this_mon, (
            f"Defect A not healed: legacy current_week_plan.start_date is "
            f"{state['current_week_plan']['start_date']!r}, expected {this_mon!r}"
        )
        # Both weeks still present in per-week cache
        assert prev_mon in state["week_plans"]
        assert this_mon in state["week_plans"]


# ============================================================================
# T2 — cache-hit no-op when already fresh (no self-heal save)
# ============================================================================

class TestT2CacheHitNoOpWhenFresh:
    def test_no_save_when_legacy_already_matches(self, monkeypatch):
        this_mon = _this_monday()
        _seed_rollover_state(
            legacy_start=this_mon,
            week_plans={this_mon: _make_week_plan(this_mon)},
            mc_start=_prev_monday(),
        )

        # Count save_state calls from within week router
        from backend.api.routers import week as week_router
        save_calls = []
        orig_save = week_router.save_state

        def counting_save(*args, **kwargs):
            save_calls.append(True)
            return orig_save(*args, **kwargs)

        monkeypatch.setattr(week_router, "save_state", counting_save)

        r = client.get("/api/week/0")
        assert r.status_code == 200, r.text

        # Steady state: self-heal branch must not fire → no save from the
        # cache-hit path. (Fresh-generation branch also doesn't fire since
        # we seeded a valid cached plan.)
        assert len(save_calls) == 0, (
            f"Expected 0 save_state calls in steady-state cache-hit, got {len(save_calls)}"
        )


# ============================================================================
# T3 — feedback fallback to week_plans[target_monday] (Defect B)
# ============================================================================

class TestT3FeedbackFallback:
    def test_mark_done_lands_in_week_plans_when_legacy_stale(self):
        """Replica Daniele: current_week_plan.start_date = prev_monday,
        feedback for target_date in this_monday — mark_done must land in
        week_plans[this_monday], not be silent-dropped."""
        this_mon = _this_monday()
        prev_mon = _prev_monday()
        _seed_rollover_state(
            legacy_start=prev_mon,
            week_plans={
                prev_mon: _make_week_plan(prev_mon, status="done"),
                this_mon: _make_week_plan(this_mon, session_id="upper_body_weights"),
            },
            mc_start=prev_mon,
        )

        r = client.post("/api/feedback", json={
            "log_entry": {
                "date": this_mon,
                "session_id": "upper_body_weights",
                "actual": {"exercise_feedback_v1": []},
            },
        })
        assert r.status_code == 200, r.text

        state = deps.load_state(None)
        # mark_done landed in the date-indexed cache
        target_sess = state["week_plans"][this_mon]["weeks"][0]["days"][0]["sessions"][0]
        assert target_sess.get("status") == "done", (
            "Defect B not healed: mark_done still silent-skipped when legacy is stale"
        )
        # completion log has the entry
        log = state.get("session_completion_log", [])
        assert any(
            e.get("date") == this_mon
            and e.get("session_id") == "upper_body_weights"
            and e.get("status") == "done"
            for e in log
        ), "session_completion_log missing the mark_done entry"


# ============================================================================
# T4 — malformed plan → non-ValueError propagates (no silent-swallow)
# ============================================================================

class TestT4MalformedPlanPropagates:
    def test_malformed_plan_propagates_exception(self):
        """A piano malformato (weeks=None) trigger TypeError inside apply_events.
        Fix B narrows except to ValueError so TypeError propagates out of the
        handler — the TestClient re-raises it (server-side 500 in production).
        Key assertion: feedback is NOT silently persisted on corrupted state."""
        this_mon = _this_monday()
        state = deps.load_state(None)
        # Malformed: weeks key present but set to None → plan.get('weeks',[]) returns None
        state["current_week_plan"] = {"start_date": this_mon, "weeks": None}
        state["week_plans"] = {}  # no fallback target
        state["session_completion_log"] = []
        if state.get("macrocycle"):
            state["macrocycle"]["start_date"] = _prev_monday()
        deps.save_state(state, None)

        # Use a TestClient that returns 500 instead of re-raising, matching
        # production FastAPI behaviour where unhandled exceptions become 500.
        strict_client = TestClient(app, raise_server_exceptions=False)

        r = strict_client.post("/api/feedback", json={
            "log_entry": {
                "date": this_mon,
                "session_id": "upper_body_weights",
                "actual": {"exercise_feedback_v1": []},
            },
        })
        # Before B216 this returned 200 with silent-swallow. After: 500.
        assert r.status_code == 500, (
            f"Expected 500 on malformed plan, got {r.status_code}: {r.text}"
        )

        # No feedback should have been persisted on corrupted state
        state_after = deps.load_state(None)
        assert state_after.get("session_completion_log", []) == [], (
            "Feedback silent-persisted despite malformed plan"
        )


# ============================================================================
# T5 — past-session immutability under rollover self-heal
# ============================================================================

class TestT5PastImmutability:
    def test_prev_week_done_sessions_untouched_by_self_heal(self):
        """CLAUDE.md non-negotiable: past completed sessions MUST NEVER be
        modified by any regeneration or cache sync. Verify T1's self-heal
        doesn't corrupt week_plans[prev_monday]."""
        this_mon = _this_monday()
        prev_mon = _prev_monday()
        # Build prev plan with a done session carrying real payload
        prev_plan = _make_week_plan(prev_mon, session_id="strength_long", status="done")
        prev_sess = prev_plan["weeks"][0]["days"][0]["sessions"][0]
        prev_sess["actual_exercises"] = [{"exercise_id": "fe_deadhang", "feedback": "hard"}]
        prev_sess["feedback_summary"] = {"difficulty": "hard"}
        prev_sess["completed_at"] = "2026-01-01T10:00:00+00:00"

        _seed_rollover_state(
            legacy_start=prev_mon,
            week_plans={
                prev_mon: prev_plan,
                this_mon: _make_week_plan(this_mon),
            },
            mc_start=prev_mon,
        )

        pre_snapshot = json.dumps(deps.load_state(None)["week_plans"][prev_mon], sort_keys=True)

        r = client.get("/api/week/0")
        assert r.status_code == 200

        post_snapshot = json.dumps(deps.load_state(None)["week_plans"][prev_mon], sort_keys=True)
        assert post_snapshot == pre_snapshot, (
            "Past-immutability violated: week_plans[prev_mon] changed during self-heal.\n"
            f"Pre:  {pre_snapshot[:500]}\nPost: {post_snapshot[:500]}"
        )


# ============================================================================
# T6 — end-to-end Daniele rollover scenario replay
# ============================================================================

class TestT6E2EDanieleScenario:
    def test_full_rollover_then_feedback_then_refetch(self):
        """Replay the D215 trace: stale legacy + fresh per-week → GET /api/week/0
        self-heals → POST /api/feedback marks done in the right slot → refetch
        sees the done status."""
        this_mon = _this_monday()
        prev_mon = _prev_monday()
        _seed_rollover_state(
            legacy_start=prev_mon,
            week_plans={
                prev_mon: _make_week_plan(prev_mon, status="done"),
                this_mon: _make_week_plan(this_mon, session_id="upper_body_weights"),
            },
            mc_start=prev_mon,
        )

        # Step 1: GET /api/week/0 — simulates the morning PWA fetch
        r1 = client.get("/api/week/0")
        assert r1.status_code == 200, r1.text
        assert r1.json()["week_plan"]["start_date"] == this_mon

        # After step 1, legacy slot is healed
        state = deps.load_state(None)
        assert state["current_week_plan"]["start_date"] == this_mon

        # Step 2: POST /api/feedback — simulate session submit
        r2 = client.post("/api/feedback", json={
            "log_entry": {
                "date": this_mon,
                "session_id": "upper_body_weights",
                "actual": {"exercise_feedback_v1": []},
                "session_duration_seconds": 1868,
            },
        })
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "ok"

        # Step 3: verify persistence
        state = deps.load_state(None)
        sess_after = state["week_plans"][this_mon]["weeks"][0]["days"][0]["sessions"][0]
        assert sess_after.get("status") == "done"
        assert any(
            e.get("session_id") == "upper_body_weights"
            and e.get("date") == this_mon
            for e in state.get("session_completion_log", [])
        )

        # Step 4: refetch GET /api/week/0 — should see the done status
        r3 = client.get("/api/week/0")
        assert r3.status_code == 200
        refetched = r3.json()["week_plan"]
        refetched_sess = refetched["weeks"][0]["days"][0]["sessions"][0]
        assert refetched_sess.get("status") == "done", (
            "Refetch still shows Planned after feedback — the original Daniele symptom"
        )

        # Past immutability: prev_monday plan still has its done status intact
        prev_sess = state["week_plans"][prev_mon]["weeks"][0]["days"][0]["sessions"][0]
        assert prev_sess.get("status") == "done"
