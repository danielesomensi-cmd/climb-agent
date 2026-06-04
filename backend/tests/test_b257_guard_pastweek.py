"""B257: past weeks are immutable — GET /api/week/{past} must never regenerate.

The latent hole (D242): a cache-miss on a past week ran generate_phase_week with
today_str=None → all 7 days regenerated, regenerate_preserving_completed and
merge_prev_week_sessions did not fire (old_plan=None / not current) → completed
sessions + feedback of paying users silently lost.

Guard (B257):
- GET /api/week/{past}: serve the cached plan read-only if present (ignoring
  force); if absent, fail closed with {week_plan: None, past_week_unavailable:
  True} — never regenerate, never write.
- POST /api/replanner/override on a past week → 422.

"Past" = week Monday < this_monday() (canonical, via deps.is_past_week).
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


def _monday(weeks_offset: int) -> str:
    """Monday of the week *weeks_offset* from the current one (negative = past)."""
    d = date.today() + timedelta(weeks=weeks_offset)
    return (d - timedelta(days=d.weekday())).isoformat()


def _make_week_plan(start_date: str, session_id: str = "strength_long",
                    status: str | None = None) -> dict:
    """Minimal valid 1-week plan anchored at *start_date* (Monday)."""
    days = []
    start = date.fromisoformat(start_date)
    for i in range(7):
        day_iso = (start + timedelta(days=i)).isoformat()
        entry = {"date": day_iso,
                 "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][i],
                 "sessions": []}
        if i == 0:
            sess = {"session_id": session_id, "slot": "evening",
                    "resolved": {"resolved_session": {"exercise_instances": [
                        {"exercise_id": "pullup_weighted"}]}}}
            if status:
                sess["status"] = status
            entry["sessions"].append(sess)
        days.append(entry)
    return {"start_date": start_date, "weeks": [{"phase": "base", "days": days}]}


def _seed(*, mc_start_offset: int = -3, week_plans: dict[str, dict],
          phase0_weeks: int = 6) -> None:
    """Seed state: macrocycle anchored mc_start_offset weeks back, given cache."""
    state = deps.load_state(None)
    assert (state.get("user", {}).get("name", "") or "").strip().lower().startswith("daniele"), \
        "fixture must be Daniele's test state"
    state["week_plans"] = {k: deepcopy(v) for k, v in week_plans.items()}
    state["current_week_plan"] = None
    mc_start = _monday(mc_start_offset)
    assert state.get("macrocycle"), "fixture needs a macrocycle"
    state["macrocycle"]["start_date"] = mc_start
    phases = state["macrocycle"].get("phases") or []
    assert phases, "fixture macrocycle needs phases"
    phases[0]["duration_weeks"] = max(phases[0].get("duration_weeks", 1), phase0_weeks)
    deps.save_state(state, None)


# week_num mapping with mc_start = 3 weeks ago, phase0 long enough:
#   week 1 → -3 (past), week 2 → -2 (past), week 3 → -1 / N-1 (past), week 4 → 0 (current)
PAST_NUM = 1            # 3 weeks ago
PAST_KEY = _monday(-3)
CURRENT_NUM = 4         # this week
CURRENT_KEY = _monday(0)


# ── helper / canonical check ────────────────────────────────────────────────

class TestIsPastWeek:
    def test_canonical_boundary(self):
        assert deps.is_past_week(_monday(-1)) is True      # N-1 is past
        assert deps.is_past_week(_monday(-3)) is True
        assert deps.is_past_week(_monday(0)) is False       # current is not past
        assert deps.is_past_week(_monday(+1)) is False      # future is not past


# ── core proof: fail-closed, no regen, no data loss ─────────────────────────

class TestPastWeekFailClosed:
    def test_cache_miss_returns_fail_closed_signal(self):
        """Past week absent from cache → explicit empty signal, status 200."""
        _seed(week_plans={CURRENT_KEY: _make_week_plan(CURRENT_KEY)})  # PAST_KEY absent
        r = client.get(f"/api/week/{PAST_NUM}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["week_plan"] is None
        assert body["past_week_unavailable"] is True

    def test_cache_miss_does_not_regenerate_or_write(self):
        """The fail-closed path must not call the planner nor persist anything."""
        _seed(week_plans={CURRENT_KEY: _make_week_plan(CURRENT_KEY)})
        client.get(f"/api/week/{PAST_NUM}")
        state = deps.load_state(None)
        # No fabricated past week written to the cache.
        assert PAST_KEY not in state.get("week_plans", {}), \
            "guard must not persist a regenerated past week"

    def test_cached_past_week_with_completed_session_served_unchanged(self):
        """A past week that exists (done session + feedback) is returned intact."""
        past = _make_week_plan(PAST_KEY, status="done")
        past["weeks"][0]["days"][0]["sessions"][0]["feedback_summary"] = "hard"
        _seed(week_plans={PAST_KEY: past, CURRENT_KEY: _make_week_plan(CURRENT_KEY)})
        r = client.get(f"/api/week/{PAST_NUM}")
        assert r.status_code == 200, r.text
        sess = r.json()["week_plan"]["weeks"][0]["days"][0]["sessions"][0]
        assert sess["status"] == "done"
        assert sess["feedback_summary"] == "hard"
        assert sess["resolved"]["resolved_session"]["exercise_instances"][0]["exercise_id"] \
            == "pullup_weighted"
        # The stored completed session is untouched.
        state = deps.load_state(None)
        stored = state["week_plans"][PAST_KEY]["weeks"][0]["days"][0]["sessions"][0]
        assert stored["status"] == "done"

    def test_force_does_not_regenerate_past_week(self):
        """force=true must be ignored for past weeks: cached served, never regen."""
        past = _make_week_plan(PAST_KEY, status="done")
        _seed(week_plans={PAST_KEY: past, CURRENT_KEY: _make_week_plan(CURRENT_KEY)})
        r = client.get(f"/api/week/{PAST_NUM}?force=true")
        assert r.status_code == 200, r.text
        assert r.json()["week_plan"]["weeks"][0]["days"][0]["sessions"][0]["status"] == "done"

    def test_force_cache_miss_past_week_fails_closed(self):
        """force=true + absent past week → still fail closed, no regen."""
        _seed(week_plans={CURRENT_KEY: _make_week_plan(CURRENT_KEY)})
        r = client.get(f"/api/week/{PAST_NUM}?force=true")
        assert r.status_code == 200, r.text
        assert r.json()["week_plan"] is None
        assert PAST_KEY not in deps.load_state(None).get("week_plans", {})


# ── regression: current / future generation unchanged ───────────────────────

class TestCurrentFutureUnaffected:
    def test_current_week_generates_on_cache_miss(self):
        """Current week absent from cache → still generated normally (not blocked)."""
        _seed(week_plans={})  # nothing cached
        r = client.get("/api/week/0")
        assert r.status_code == 200, r.text
        wp = r.json()["week_plan"]
        assert wp is not None
        assert wp["start_date"] == CURRENT_KEY
        # It was persisted.
        assert CURRENT_KEY in deps.load_state(None)["week_plans"]

    def test_future_week_generates_on_cache_miss(self):
        """Future week absent → generated normally."""
        _seed(week_plans={})
        r = client.get("/api/week/5")  # week 5 = +1 from current (future)
        assert r.status_code == 200, r.text
        assert r.json()["week_plan"] is not None

    def test_current_week_force_regen_preserves_completed(self):
        """Guard must not block the current week: force-regen still preserves
        completed sessions via regenerate_preserving_completed."""
        cur = _make_week_plan(CURRENT_KEY, status="done")
        _seed(week_plans={CURRENT_KEY: cur})
        r = client.get("/api/week/0?force=true")
        assert r.status_code == 200, r.text
        # The done session anchored on Monday must survive the regen.
        days = r.json()["week_plan"]["weeks"][0]["days"]
        mon = next(d for d in days if d["date"] == CURRENT_KEY)
        done = [s for s in mon["sessions"] if s.get("status") == "done"]
        assert done, "current-week force-regen must preserve completed sessions"


# ── regression: N-1 merge through macrocycle regen ──────────────────────────

class TestPrevWeekMergeStillWorks:
    def test_prev_week_completed_merged_into_current_regen(self):
        """merge_prev_week_sessions (B114) must still fire for the current week:
        a completed session stashed in _prev_week_plan is merged into the freshly
        regenerated current week. The guard blocks past-week *regen*, not the
        current-week merge that reads prior completed data."""
        state = deps.load_state(None)
        state["macrocycle"]["start_date"] = _monday(-3)
        phases = state["macrocycle"].get("phases") or []
        phases[0]["duration_weeks"] = max(phases[0].get("duration_weeks", 1), 6)
        state["week_plans"] = {}
        # Stash a prior current-week plan with a done session anchored on Monday.
        state["_prev_week_plan"] = _make_week_plan(CURRENT_KEY, status="done")
        state["current_week_plan"] = None
        deps.save_state(state, None)

        r = client.get("/api/week/0?force=true")
        assert r.status_code == 200, r.text
        days = r.json()["week_plan"]["weeks"][0]["days"]
        mon = next(d for d in days if d["date"] == CURRENT_KEY)
        assert any(s.get("status") == "done" for s in mon["sessions"]), \
            "completed session from _prev_week_plan must be merged into current week"


# ── replanner guard ─────────────────────────────────────────────────────────

class TestReplannerRejectsPastWeek:
    def test_override_on_past_week_rejected(self):
        _seed(week_plans={PAST_KEY: _make_week_plan(PAST_KEY, status="done"),
                          CURRENT_KEY: _make_week_plan(CURRENT_KEY)})
        r = client.post("/api/replanner/override", json={
            "intent": "rest", "location": "home", "reference_date": PAST_KEY,
            "week_plan": _make_week_plan(PAST_KEY, status="done"),
            "target_date": PAST_KEY,
        })
        assert r.status_code == 422, r.text
        assert "past" in r.json()["detail"].lower()

    def test_override_on_current_week_not_rejected_by_guard(self):
        """The past-week guard must not block the current week. (May still fail
        downstream for other reasons, but never with the past-week 422.)"""
        _seed(week_plans={CURRENT_KEY: _make_week_plan(CURRENT_KEY)})
        r = client.post("/api/replanner/override", json={
            "intent": "rest", "location": "home", "reference_date": CURRENT_KEY,
            "week_plan": _make_week_plan(CURRENT_KEY),
            "target_date": CURRENT_KEY,
        })
        assert not (r.status_code == 422 and "past" in r.json().get("detail", "").lower()), \
            "current week must not be rejected by the past-week guard"
