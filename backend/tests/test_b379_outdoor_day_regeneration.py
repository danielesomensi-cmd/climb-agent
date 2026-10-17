"""B379 — a planned outdoor day stays an outdoor day when the plan regenerates.

2026-10-17 (prod): a Settings availability save marked the weeks stale, the
current week was regenerated (``generate_phase_week(existing_week_plan=old)`` →
``regenerate_preserving_completed``) and Saturday/Sunday — two planned crag days
(spot + pitch ladder, no sessions) — received ``test_repeater_7_3`` and
``route_endurance_gym``. Two defects:

1. the planner looked only at availability to decide whether a day is outdoor,
   never at the outdoor the user declared on the existing plan;
2. the merge took engine sessions off a day only through a recorded removal,
   and ``add_outdoor`` / ``set_outdoor_plan`` record none.

Fix: one predicate (``user_owned.engine_free_dates`` = whole-day overrides +
declared outdoor days) read by the merge (the day is copied as it was), the
planner (the day is treated as unavailable, without the ``outdoor_slot``
marker), the A305 key pass (blocked), the complementary pass (no lunch) and the
retest policy (``locked_dates``). Plus a B297 one-liner: PASS 3 pass 2 never
places a test on a past day (the merge would drop it, silently).

Fixtures are synthetic (no real user state in the repo).
"""

from __future__ import annotations

import shutil
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.api.routers import week as week_router
from backend.engine import user_owned as uo
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.replanner_v1 import apply_events, regenerate_preserving_completed
from backend.engine.stimulus import is_declared_outdoor_day, is_test_session
from backend.tests.test_a300_complementary_slots import daniele_availability, days_of, plan

START = "2026-10-12"  # Monday
MON, TUE, WED, THU, FRI, SAT, SUN = (
    (date.fromisoformat(START) + timedelta(days=i)).isoformat() for i in range(7)
)
PITCHES = {"pitches": [{"grade": "7a", "attempts": 2, "rest_min": 20},
                       {"grade": "7b", "attempts": 3, "rest_min": 25}]}
TEST_SIDS = {sid for sid, m in _SESSION_META.items() if sid.startswith("test_")}


def _strip(wp):
    out = deepcopy(wp)
    out.pop("generated_at", None)
    return out


def _day(wp, d_iso):
    return next(d for d in days_of(wp) if d["date"] == d_iso)


def _sids(day):
    return [s.get("session_id") for s in day.get("sessions") or []]


def _outdoor_weekend_availability():
    """Sat/Sun evenings outdoor-only: the planner leaves them empty."""
    av = daniele_availability()
    for d in ("sat", "sun"):
        av[d]["evening"] = {"available": True, "locations": ["outdoor"], "preferred_location": "outdoor"}
    return av


def _declare_outdoor(wp, dates, *, with_plan=True):
    """The app's way: add_outdoor (+ set_outdoor_plan) events — no day_override."""
    events = []
    for d in dates:
        events.append({"event_type": "add_outdoor", "date": d, "spot_name": "Crag A",
                       "discipline": "lead"})
        if with_plan:
            events.append({"event_type": "set_outdoor_plan", "date": d, "plan": deepcopy(PITCHES)})
    out = apply_events(wp, events)
    for d in dates:
        assert is_declared_outdoor_day(_day(out, d))
    assert not uo.whole_day_override_dates(out)  # the defect's precondition
    return out


def _prod_shape_old(phase="strength_power", **kw):
    """Daniele's 17/18 shape: the week generated with an outdoor weekend
    (no sessions there), the two days then declared outdoor with a ladder."""
    old = plan(phase, availability=_outdoor_weekend_availability(), today=MON, **kw)
    assert _day(old, SAT)["sessions"] == [] and _day(old, SUN)["sessions"] == []
    return _declare_outdoor(old, [SAT, SUN])


def _regen(old, today, *, phase="strength_power", availability=None, **kw):
    """The GET /api/week force path: plan with existing_week_plan, then merge."""
    new = plan(phase, availability=availability if availability is not None else daniele_availability(),
               today=today, existing_week_plan=deepcopy(old), **kw)
    merged = regenerate_preserving_completed(deepcopy(old), deepcopy(new), preserve_before=today)
    return new, merged


# ---------------------------------------------------------------------------
# Predicate
# ---------------------------------------------------------------------------

class TestPredicate:
    def test_engine_free_dates_union(self):
        wp = plan("base", today=MON)
        wp = _declare_outdoor(wp, [SAT], with_plan=False)
        _day(wp, THU)["outdoor_plan"] = deepcopy(PITCHES)
        _day(wp, FRI)["outdoor_slot"] = True  # availability, not a declaration
        wp["adaptations"] = list(wp.get("adaptations") or []) + [
            {"type": "day_override", "target_date": TUE, "outdoor": True}]
        assert uo.engine_free_dates(wp) == [TUE, THU, SAT]

    def test_stimulus_delegates(self):
        for day in ({"outdoor_spot_name": "X"}, {"outdoor_plan": {}}, {"outdoor_plan": PITCHES},
                    {"outdoor_session_status": "planned"}, {"outdoor_session_status": "done"},
                    {"outdoor_slot": True}, {}, None):
            assert is_declared_outdoor_day(day) == uo.is_declared_outdoor_day(day)

    def test_no_outdoor_no_dates(self):
        assert uo.engine_free_dates(plan("base")) == []
        assert uo.engine_free_dates({}) == []


# ---------------------------------------------------------------------------
# The prod repro shape: two consecutive planned outdoor days
# ---------------------------------------------------------------------------

class TestOutdoorWeekend:
    def test_without_the_plan_the_planner_fills_the_weekend(self):
        """Non-vacuity: with gym availability the planner does use Sat/Sun."""
        fresh = plan("strength_power", today=WED, is_last_week_of_phase=True)
        assert _day(fresh, SAT)["sessions"] or _day(fresh, SUN)["sessions"]

    def test_future_outdoor_days_stay_outdoor(self):
        old = _prod_shape_old(is_last_week_of_phase=True)
        new, merged = _regen(old, WED, is_last_week_of_phase=True)
        for d in (SAT, SUN):
            assert _day(new, d)["sessions"] == [], (d, _sids(_day(new, d)))
            assert "outdoor_slot" not in _day(new, d)
            assert _day(merged, d) == _day(old, d)
            assert _day(merged, d)["outdoor_plan"] == PITCHES
            assert _day(merged, d)["outdoor_session_status"] == "planned"
            assert _day(merged, d)["outdoor_spot_name"] == "Crag A"

    def test_outdoor_today_planned(self):
        old = _prod_shape_old()
        new, merged = _regen(old, SAT)
        assert _day(new, SAT)["sessions"] == [] and _day(new, SUN)["sessions"] == []
        assert _day(merged, SAT) == _day(old, SAT)
        assert _day(merged, SUN) == _day(old, SUN)

    def test_tests_never_on_an_outdoor_day_pass3(self):
        """Last week of strength_power (legacy PASS 3): no test on the crag
        days; what cannot be placed is reported, never silent."""
        old = _prod_shape_old(is_last_week_of_phase=True)
        new, merged = _regen(old, WED, is_last_week_of_phase=True)
        for d in (SAT, SUN):
            assert not any(is_test_session(s) for s in _day(merged, d)["sessions"])
        placed = {s["session_id"] for d in days_of(new) for s in d["sessions"] if s["session_id"] in TEST_SIDS}
        reported = {t["test_id"] for t in new.get("skipped_tests") or []}
        assert placed or reported

    def test_tests_never_on_an_outdoor_day_policy(self):
        """PASS 3a: a policy test whose only allowed dates are crag days is
        skipped, not placed."""
        old = _prod_shape_old()
        rd = {"covered_axes": ["finger"], "block_hours": {"hang": 72, "pull": 48},
              "required_sessions": [{"session_id": "test_max_hang_7s", "axis": "finger",
                                     "allowed_dates": [SAT, SUN], "order": 1,
                                     "trigger": "end_of_phase"}],
              "skipped": [], "locked_slots": [], "locked_dates": []}
        new, _ = _regen(old, WED, retest_decisions=rd)
        assert not any(s["session_id"] == "test_max_hang_7s" for d in days_of(new) for s in d["sessions"])
        assert any(t.get("test_id") == "test_max_hang_7s" for t in new.get("skipped_tests") or [])

    def test_no_complementary_lunch_on_an_outdoor_day(self):
        old = plan("base", today=MON)
        _day(old, THU)["sessions"] = []
        old = _declare_outdoor(old, [THU])
        new, merged = _regen(old, TUE, phase="base")
        assert _day(new, THU)["sessions"] == []
        assert _day(merged, THU) == _day(old, THU)
        # Non-vacuity: Thursday lunch is a complementary slot the planner fills.
        assert any(s["slot"] == "lunch" for s in _day(plan("base", today=TUE), THU)["sessions"])

    def test_key_pass_never_targets_an_outdoor_day(self):
        old = plan("power_endurance", today=MON)
        for d in (SAT, SUN):
            _day(old, d)["sessions"] = []
        old = _declare_outdoor(old, [SAT, SUN])
        new, merged = _regen(old, TUE, phase="power_endurance")
        for d in (SAT, SUN):
            assert _day(new, d)["sessions"] == []
            assert _day(merged, d) == _day(old, d)


# ---------------------------------------------------------------------------
# Merge semantics
# ---------------------------------------------------------------------------

class TestMerge:
    def test_user_sessions_on_an_outdoor_day_preserved(self):
        old = plan("base", today=MON)
        custom = {"slot": "lunch", "session_id": "custom_cs_b379", "is_custom": True,
                  "custom_session_id": "cs_b379", "status": "planned",
                  "constraints_applied": ["custom_add"], "tags": {"hard": False, "finger": False}}
        _day(old, SAT)["sessions"] = [custom]
        old = _declare_outdoor(old, [SAT])
        new, merged = _regen(old, WED, phase="base")
        assert _day(new, SAT)["sessions"] == []
        assert _day(merged, SAT) == _day(old, SAT)
        assert _day(merged, SAT)["sessions"] == [custom]

    def test_done_outdoor_today_and_past_byte_identical(self):
        old = _prod_shape_old()
        old = apply_events(old, [{"event_type": "complete_outdoor", "date": SAT,
                                  "outdoor_load_score": 410}])
        # A past done outdoor day too, and a done gym session.
        _day(old, TUE).update({"outdoor_spot_name": "Crag B", "outdoor_session_status": "done",
                               "outdoor_load_score": 300, "sessions": []})
        mon = _day(old, MON)
        mon["sessions"] = [dict(s, status="done") for s in mon["sessions"]]
        _new, merged = _regen(old, SAT)
        for d in (MON, TUE, WED, THU, FRI, SAT, SUN):
            assert _day(merged, d) == _day(old, d), d

    def test_past_days_immutable(self):
        old = _prod_shape_old()
        for d in (MON, TUE):
            day = _day(old, d)
            day["sessions"] = [dict(s, status="done", feedback_summary="ok") for s in day["sessions"]]
        _new, merged = _regen(old, THU)
        for d in (MON, TUE, WED):
            assert _day(merged, d) == _day(old, d), d

    def test_remove_outdoor_gives_the_day_back(self):
        old = _prod_shape_old()
        old = apply_events(old, [{"event_type": "remove_outdoor", "date": SAT}])
        assert not is_declared_outdoor_day(_day(old, SAT))
        new, merged = _regen(old, WED)
        assert _day(new, SAT)["sessions"], "gym availability: the engine plans Saturday again"
        assert _day(merged, SAT)["sessions"] == _day(new, SAT)["sessions"]
        assert _day(merged, SUN) == _day(old, SUN)  # Sunday still a crag day

    def test_idempotent_and_deterministic(self):
        old = _prod_shape_old(is_last_week_of_phase=True)
        new_a, a = _regen(old, WED, is_last_week_of_phase=True)
        new_b, b = _regen(old, WED, is_last_week_of_phase=True)
        assert _strip(new_a) == _strip(new_b)
        assert _strip(a)["weeks"] == _strip(b)["weeks"]
        _new2, twice = _regen(a, WED, is_last_week_of_phase=True)
        assert twice["weeks"] == a["weeks"]


# ---------------------------------------------------------------------------
# Retest policy and PASS 3 pass 2
# ---------------------------------------------------------------------------

def test_locked_by_merge_includes_outdoor_dates():
    from backend.engine.retest_policy import _locked_by_merge

    old = _prod_shape_old()
    _day(old, MON).update({"outdoor_spot_name": "Crag B", "outdoor_session_status": "planned"})
    out = _locked_by_merge({"week_plans": {START: old}}, date.fromisoformat(START), date.fromisoformat(WED))
    assert SAT in out["locked_dates"] and SUN in out["locked_dates"]
    assert MON not in out["locked_dates"]  # past: not the policy's business
    assert len(out["locked_dates"]) == len(set(out["locked_dates"]))


def test_pass3_pass2_never_on_a_past_day():
    """Today Saturday, weekend at the crag: nowhere left to test. Before B379
    pass 2 put the required test on an empty past day (Monday), where the merge
    dropped it silently; now it is reported as no_placement_slot."""
    old = _prod_shape_old(is_last_week_of_phase=True)
    new, merged = _regen(old, SAT, is_last_week_of_phase=True)
    for d in days_of(new):
        if d["date"] < SAT:
            assert not any(s["session_id"] in TEST_SIDS for s in d["sessions"]), d["date"]
    def tests_of(wp):
        return {(d["date"], s["session_id"]) for d in days_of(wp) for s in d["sessions"]
                if s["session_id"] in TEST_SIDS}
    # The merge adds no test: the lived days are the old ones, the crag days too.
    assert tests_of(merged) <= tests_of(old)
    skipped = [t for t in new.get("skipped_tests") or [] if t.get("reason") == "no_placement_slot"]
    assert skipped, new.get("skipped_tests")


def test_pass3_pass2_past_guard_default_without_today():
    """No `today` → no past day: the B297 pass 2 is unchanged."""
    a = plan("strength_power", is_last_week_of_phase=True)
    b = plan("strength_power", is_last_week_of_phase=True)
    assert _strip(a) == _strip(b)


# ---------------------------------------------------------------------------
# End to end: Settings availability save → GET /api/week force
# ---------------------------------------------------------------------------

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"
RAW: dict = {}


@pytest.fixture
def api_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    shutil.copy2(FIXTURE, tmp_state)
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    RAW.clear()
    real = week_router.generate_phase_week

    def recording(*a, **k):
        out = real(*a, **k)
        RAW[out.get("start_date")] = deepcopy(out)
        return out

    monkeypatch.setattr(week_router, "generate_phase_week", recording)
    yield tmp_state


def _monday(offset_weeks=0) -> str:
    t = date.today()
    return (t - timedelta(days=t.weekday()) + timedelta(weeks=offset_weeks)).isoformat()


def test_api_availability_save_then_force_keeps_outdoor(api_state):
    state = deps.load_state(None)
    state["macrocycle"]["start_date"] = _monday(-1)
    state["macrocycle"].pop("pause", None)
    phases = state["macrocycle"].get("phases") or []
    phases[0]["duration_weeks"] = max(phases[0].get("duration_weeks", 1), 6)
    state["week_plans"] = {}
    state["current_week_plan"] = None
    state.pop("_prev_week_plan", None)
    state.pop("weekly_overrides", None)
    deps.save_state(state, None)

    r = client.get("/api/week/0")
    assert r.status_code == 200, r.text
    wn = r.json()["week_num"]
    assert client.get(f"/api/week/{wn + 1}").status_code == 200

    # Declare a crag weekend next week and this week's Sunday (never past).
    state = deps.load_state(None)
    targets = {_monday(1): (5, 6), _monday(0): (6,)}
    expected = {}
    for ws, idxs in targets.items():
        wp = state["week_plans"][ws]
        for i in idxs:
            day = wp["weeks"][0]["days"][i]
            day["sessions"] = []
            day.update({"outdoor_spot_name": "Crag A", "outdoor_discipline": "lead",
                        "outdoor_session_status": "planned", "outdoor_plan": deepcopy(PITCHES)})
            expected[(ws, day["date"])] = deepcopy(day)
        if ws == _monday(0):
            state["current_week_plan"] = deepcopy(wp)
    deps.save_state(state, None)

    # Settings save: weekend evenings at the gym → weeks stale.
    r = client.put("/api/state", json={"availability": {
        "sat": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "BKL"}},
        "sun": {"evening": {"available": True, "preferred_location": "gym", "gym_id": "BKL"}}}})
    assert r.status_code == 200, r.text
    assert client.get("/api/week/0?force=true").status_code == 200
    assert client.get(f"/api/week/{wn + 1}?force=true").status_code == 200

    state = deps.load_state(None)
    for (ws, d_iso), exp in expected.items():
        day = next(d for d in state["week_plans"][ws]["weeks"][0]["days"] if d["date"] == d_iso)
        assert day == exp, (ws, d_iso, _sids(day))
        if ws in RAW:
            raw = next(d for d in RAW[ws]["weeks"][0]["days"] if d["date"] == d_iso)
            assert raw["sessions"] == [] and "outdoor_slot" not in raw, (ws, d_iso, _sids(raw))
    assert _monday(1) in RAW  # the future week really was regenerated
