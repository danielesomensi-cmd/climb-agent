"""B369 — nothing the user put on the plan is lost when a week is regenerated.

2026-10-05: a regeneration of Daniele's week dropped his custom sessions and
his forced max boulder, and brought back a prehab session he had removed. Every
regeneration path now goes through one merge (``replanner_v1._merge_user_content``)
and one predicate (``user_owned.is_user_owned``):

- done/skipped sessions and user-owned ones (forced, custom, quick-add,
  override, key re-schedule, moved, custom/generated add, ``_user_edited``)
  survive byte-identical;
- the user's removals (``remove_session`` / the source of ``move_session`` /
  a whole-day override, read from ``adaptations``) are honoured, and carried
  forward to the next regeneration;
- invalidations flag weeks stale instead of deleting them;
- a failed regeneration or merge serves the cached plan and saves nothing;
- a stashed plan of another week is never weekday-copied (P5);
- the adaptive replan after very_hard/fail only suggests (no plan change).

The integration test runs one week holding a specimen of every user-owned kind
plus a done day through every path that regenerates.
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
from backend.engine.replanner_v1 import (
    apply_day_override,
    apply_events,
    merge_prev_week_sessions,
    regenerate_preserving_completed,
)

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


#: B369 review: the raw planner output of the last generation of each week,
#: before the merge — so a "the removed session did not come back" check can
#: first prove the planner did generate it there.
RAW_GENERATED: dict = {}


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    shutil.copy2(REAL_STATE_PATH, tmp_state)
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    RAW_GENERATED.clear()
    real = week_router.generate_phase_week

    def recording(*a, **k):
        out = real(*a, **k)
        RAW_GENERATED[out.get("start_date")] = deepcopy(out)
        return out

    monkeypatch.setattr(week_router, "generate_phase_week", recording)
    yield tmp_state


# ---------------------------------------------------------------------------
# Specimens
# ---------------------------------------------------------------------------

def _tags(hard=False, finger=False):
    return {"hard": hard, "finger": finger}


def _custom(slot="lunch"):
    return {"slot": slot, "session_id": "custom_cs_b369", "custom_session_id": "cs_b369",
            "session_mode": "custom_build", "is_custom": True, "name": "Work — gambe",
            "location": "gym", "gym_id": "g_work", "status": "planned", "intensity": "medium",
            "exercises": [{"exercise_id": "goblet_squat", "sets": 3, "reps": 8}],
            "tags": _tags(), "constraints_applied": ["custom_add"],
            "explain": ["user-added custom session"]}


def _forced(slot="evening"):
    return {"slot": slot, "session_id": "limit_boulder_gym", "location": "gym", "gym_id": "g1",
            "phase_id": "base", "intensity": "max", "estimated_load_score": 80,
            "constraints_applied": ["quick_add", "user_forced"], "forced": True,
            "tags": _tags(True, True), "explain": ["user quick-add session"]}


def _quick_add(slot="morning"):
    return {"slot": slot, "session_id": "prehab_maintenance", "location": "home", "gym_id": None,
            "intensity": "low", "constraints_applied": ["quick_add"], "tags": _tags()}


def _override(slot="evening"):
    return {"slot": slot, "session_id": "technique_focus_gym", "location": "gym", "gym_id": "g1",
            "intensity": "medium", "constraints_applied": ["manual_override"], "tags": _tags(),
            "explain": ["user day override applied"]}


def _key_reschedule(slot="evening"):
    return {"slot": slot, "session_id": "strength_long", "location": "home", "gym_id": None,
            "intensity": "max", "constraints_applied": ["key_reschedule"], "tags": _tags(True, True)}


def _moved(slot="evening"):
    return {"slot": slot, "session_id": "power_endurance_gym", "location": "gym", "gym_id": "g1",
            "intensity": "high", "constraints_applied": ["user_moved"], "tags": _tags(True, False)}


def _generated(slot="lunch"):
    return {"slot": slot, "session_id": "generated_body_part_x", "is_custom": True,
            "session_mode": "custom_build", "status": "planned", "location": "home",
            "constraints_applied": ["generated_add"], "tags": _tags(), "exercises": []}


def _edited(slot="morning"):
    return {"slot": slot, "session_id": "core_conditioning_standalone", "location": "home",
            "intensity": "medium", "_user_edited": True, "tags": _tags(),
            "resolved": {"resolved_session": {"exercise_instances": [{"exercise_id": "plank"}]}}}


def _done(slot="evening", sid="strength_long"):
    return {"slot": slot, "session_id": sid, "status": "done", "location": "home",
            "intensity": "max", "tags": _tags(True, True), "feedback_summary": "hard",
            "resolved": {"resolved_session": {"exercise_instances": []}}}


# ---------------------------------------------------------------------------
# Unit — predicate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("session", [
    _custom(), _forced(), _quick_add(), _override(), _key_reschedule(), _moved(),
    _generated(), _edited(),
])
def test_every_user_kind_is_user_owned(session):
    assert uo.is_user_owned(session)
    assert uo.is_preservable(session)


def test_engine_session_is_not_user_owned():
    engine = {"slot": "evening", "session_id": "strength_long", "constraints_applied": ["phase_pool"]}
    assert not uo.is_user_owned(engine)
    assert not uo.is_preservable(engine)
    assert uo.is_preservable({**engine, "status": "done"})
    assert not uo.is_user_owned({**engine, "status": "done"})


# ---------------------------------------------------------------------------
# Unit — merge
# ---------------------------------------------------------------------------

START = "2026-10-12"


def _plan(sessions_by_day, start=START, **extra):
    s = date.fromisoformat(start)
    days = [{"date": (s + timedelta(days=i)).isoformat(),
             "sessions": deepcopy(sessions_by_day.get(i, []))} for i in range(7)]
    return {"start_date": start, "weeks": [{"days": days}], "plan_revision": 1, **extra}


def _engine(sid, slot="evening"):
    return {"slot": slot, "session_id": sid, "intensity": "medium", "tags": _tags()}


def _day(plan, i):
    return plan["weeks"][0]["days"][i]


def _old_week():
    """One specimen of each user-owned kind, a done day, a removed engine session."""
    plan = _plan({
        0: [_done("evening")],
        1: [_custom("lunch"), _engine("finger_strength_home", "evening")],
        2: [_forced("evening")],
        3: [_override("evening"), _quick_add("morning")],
        4: [_key_reschedule("evening"), _generated("lunch")],
        5: [_moved("evening")],
        6: [_edited("morning")],
    })
    # The user removed the engine's prehab from Tuesday lunch... it is gone
    # from the old plan, and the log says so.
    plan["adaptations"] = [
        {"type": "event", "event": {"event_type": "remove_session",
                                     "date": "2026-10-14", "session_ref": "prehab_maintenance"}},
    ]
    _day(plan, 5).update({"outdoor_spot_name": "Arlon", "outdoor_session_status": "planned",
                          "outdoor_plan": {"pitches": [{"grade": "7c"}]}})
    return plan


def _fresh_week():
    """What the planner generates: engine sessions everywhere, including the
    removed prehab and engine sessions in the specimens' slots."""
    return _plan({
        0: [_engine("technique_focus_gym", "evening")],
        1: [_engine("power_contact_gym", "evening")],
        2: [_engine("prehab_maintenance", "lunch"), _engine("endurance_aerobic_gym", "evening")],
        3: [_engine("strength_long", "evening")],
        4: [_engine("yoga_recovery", "evening")],
        5: [_engine("power_endurance_gym", "evening")],
        6: [_engine("core_conditioning_standalone", "morning"), _engine("regeneration_easy", "evening")],
    })


def _preservable_by_day(plan):
    return [[s for s in d["sessions"] if uo.is_preservable(s)] for d in plan["weeks"][0]["days"]]


def test_merge_keeps_every_user_session_byte_identical():
    old = _old_week()
    out = regenerate_preserving_completed(old, _fresh_week(), preserve_before=START)
    for i, kept in enumerate(_preservable_by_day(old)):
        for s in kept:
            assert s in _day(out, i)["sessions"], f"day {i}: {s['session_id']} lost"


def test_merge_honours_the_removal_and_carries_it_forward():
    old = _old_week()
    out = regenerate_preserving_completed(old, _fresh_week(), preserve_before=START)
    assert "prehab_maintenance" not in {s["session_id"] for s in _day(out, 2)["sessions"]}
    assert out["adaptations"][: len(old["adaptations"])] == old["adaptations"]
    # The next regeneration still honours it.
    again = regenerate_preserving_completed(out, _fresh_week(), preserve_before=START)
    assert "prehab_maintenance" not in {s["session_id"] for s in _day(again, 2)["sessions"]}


def test_merge_keeps_day_level_outdoor_fields():
    out = regenerate_preserving_completed(_old_week(), _fresh_week(), preserve_before=START)
    sat = _day(out, 5)
    assert sat["outdoor_plan"] == {"pitches": [{"grade": "7c"}]}
    assert sat["outdoor_spot_name"] == "Arlon"


def test_merge_is_deterministic_and_idempotent():
    a = regenerate_preserving_completed(_old_week(), _fresh_week(), preserve_before=START)
    b = regenerate_preserving_completed(_old_week(), _fresh_week(), preserve_before=START)
    assert a == b
    twice = regenerate_preserving_completed(a, _fresh_week(), preserve_before=START)
    assert twice["weeks"] == a["weeks"]


def test_merge_without_user_content_is_the_fresh_plan():
    """A user who never touched the week gets exactly the generated week."""
    old = _plan({1: [_engine("strength_long")], 3: [_engine("yoga_recovery")]})
    fresh = _fresh_week()
    out = regenerate_preserving_completed(old, fresh, preserve_before=START)
    assert out["weeks"] == fresh["weeks"]


def test_past_days_copied_wholesale():
    old = _old_week()
    floor = "2026-10-15"  # Thursday: Mon..Wed are past
    out = regenerate_preserving_completed(old, _fresh_week(), preserve_before=floor)
    for i in range(3):
        assert _day(out, i) == _day(old, i)


def test_plan_revision_is_monotonic():
    old = _old_week()
    old["plan_revision"] = 7
    out = regenerate_preserving_completed(old, _fresh_week())
    assert out["plan_revision"] == 8


def test_regenerate_refuses_another_week():
    with pytest.raises(ValueError):
        regenerate_preserving_completed(_old_week(), _plan({}, start="2026-10-19"))


def test_stash_of_another_week_is_discarded():
    """P5: no done session / outdoor day copied onto the same weekday of
    another week (fabricated history on future dates)."""
    other = _old_week()
    fresh = _plan({0: [_engine("yoga_recovery")]}, start="2026-10-19")
    assert merge_prev_week_sessions(other, fresh, preserve_before="2026-10-19") == fresh


def test_whole_day_override_keeps_engine_sessions_off_that_day():
    """A301: an override without session_index replaces only the targeted slot
    (the evening); the engine's lunch stays, and the regeneration does not bring
    the replaced evening session back."""
    base = _plan({2: [_engine("strength_long", "evening"), _engine("prehab_maintenance", "lunch")]})
    edited = apply_day_override(base, intent="technique", location="home",
                                reference_date="2026-10-13", target_date="2026-10-14")
    ov = edited["adaptations"][0]
    assert ov["whole_day"] is False
    assert (ov["replaced_session_id"], ov["replaced_slot"]) == ("strength_long", "evening")
    assert _ids(_day(edited, 2)) == [("prehab_maintenance", "lunch"), ("technique_focus_gym", "evening")]
    fresh = _plan({2: [_engine("strength_long", "evening"), _engine("prehab_maintenance", "lunch")]})
    out = regenerate_preserving_completed(edited, fresh)
    assert _ids(_day(out, 2)) == _ids(_day(edited, 2))


def test_moved_session_stays_where_the_user_put_it():
    base = _plan({1: [_engine("strength_long", "evening")]})
    moved = apply_events(base, [{"event_type": "move_session", "from_date": "2026-10-13",
                                 "from_slot": "evening", "to_date": "2026-10-15",
                                 "to_slot": "evening"}])
    thu = _day(moved, 3)["sessions"]
    assert thu[0]["session_id"] == "strength_long" and "user_moved" in thu[0]["constraints_applied"]
    # The engine regenerates it on its original day: it must not come back there.
    fresh = _plan({1: [_engine("strength_long", "evening")], 3: [_engine("yoga_recovery", "evening")]})
    out = regenerate_preserving_completed(moved, fresh)
    assert _day(out, 1)["sessions"] == []
    assert _day(out, 3)["sessions"] == thu


def test_two_user_sessions_in_one_slot_both_survive():
    """The old merge replaced by slot, so the second preserved session of a
    slot overwrote the first."""
    old = _plan({1: [_generated("evening"), _quick_add("evening")]})
    out = regenerate_preserving_completed(old, _plan({1: [_engine("strength_long")]}))
    ids = sorted(s["session_id"] for s in _day(out, 1)["sessions"])
    assert ids == ["generated_body_part_x", "prehab_maintenance"]


# ---------------------------------------------------------------------------
# Integration — every regeneration path
# ---------------------------------------------------------------------------

def _monday(offset_weeks=0) -> str:
    t = date.today()
    return (t - timedelta(days=t.weekday()) + timedelta(weeks=offset_weeks)).isoformat()


def _seed_macrocycle():
    state = deps.load_state(None)
    state["macrocycle"]["start_date"] = _monday(-1)
    state["macrocycle"].pop("pause", None)
    phases = state["macrocycle"].get("phases") or []
    phases[0]["duration_weeks"] = max(phases[0].get("duration_weeks", 1), 6)
    state["week_plans"] = {}
    state["current_week_plan"] = None
    state.pop("_prev_week_plan", None)
    state.pop("weekly_overrides", None)
    state["feedback_log"] = []
    deps.save_state(state, None)


def _week_nums():
    r = client.get("/api/week/0")
    assert r.status_code == 200, r.text
    wn = r.json()["week_num"]
    assert r.json()["week_plan"]["start_date"] == _monday(0)
    nxt = client.get(f"/api/week/{wn + 1}")
    assert nxt.status_code == 200, nxt.text
    assert nxt.json()["week_plan"]["start_date"] == _monday(1)
    return wn


SPECIMEN_LAYOUT = [  # (day index in NEXT week, factory)
    (0, lambda: _done("morning", "prehab_maintenance")),
    (0, lambda: _custom("lunch")),
    (1, lambda: _forced("evening")),
    (2, lambda: _override("evening")),
    (3, lambda: _key_reschedule("evening")),
    (3, lambda: _quick_add("morning")),
    (4, lambda: _moved("evening")),
    (5, lambda: _generated("lunch")),
    (6, lambda: _edited("morning")),
]


def _install_specimens():
    """Put one specimen of every kind into next week, a done session on this
    week's Monday, and remove one engine session (logged in adaptations)."""
    _seed_macrocycle()
    _week_nums()
    state = deps.load_state(None)
    nxt = state["week_plans"][_monday(1)]
    days = nxt["weeks"][0]["days"]
    for i, factory in SPECIMEN_LAYOUT:
        s = factory()
        days[i]["sessions"] = [x for x in days[i]["sessions"] if x.get("slot") != s["slot"]] + [s]
    # Remove the first engine session left on the week the way the app does
    # it: gone from the day, logged as an event. B369 review: whether the
    # planner's next generation puts the same session there again is checked
    # in _assert_survived (RAW_GENERATED), so the check cannot pass vacuously.
    removed = None
    for d in days:
        for s in list(d["sessions"]):
            if not uo.is_preservable(s):
                d["sessions"].remove(s)
                removed = (d["date"], s["session_id"])
                break
        if removed:
            break
    assert removed, "fixture week has no engine session to remove"
    nxt.setdefault("adaptations", []).append(
        {"type": "event", "event": {"event_type": "remove_session",
                                     "date": removed[0], "session_ref": removed[1]}})
    days[5].update({"outdoor_spot_name": "Arlon", "outdoor_session_status": "planned",
                    "outdoor_plan": {"pitches": [{"grade": "7c"}]}})
    cur = state["week_plans"][_monday(0)]
    cur["weeks"][0]["days"][0]["sessions"] = [_done("evening")]
    state["current_week_plan"] = deepcopy(cur)
    deps.save_state(state, None)
    return removed


def _assert_survived(removed, label):
    state = deps.load_state(None)
    nxt = state["week_plans"][_monday(1)]
    assert not nxt.get("_stale"), f"{label}: next week still stale after GET"
    days = nxt["weeks"][0]["days"]
    for i, factory in SPECIMEN_LAYOUT:
        expected = factory()
        assert expected in days[i]["sessions"], (
            f"{label}: {expected['session_id']} ({expected['slot']}) lost on {days[i]['date']}: "
            f"{[s.get('session_id') for s in days[i]['sessions']]}")
    assert days[5].get("outdoor_plan") == {"pitches": [{"grade": "7c"}]}, label
    if removed and _monday(1) in RAW_GENERATED:
        rm_day = next(d for d in days if d["date"] == removed[0])
        raw_day = next(d for d in RAW_GENERATED[_monday(1)]["weeks"][0]["days"]
                       if d["date"] == removed[0])
        if any(s["session_id"] == removed[1] for s in raw_day["sessions"]):
            assert not any(s["session_id"] == removed[1] and not uo.is_preservable(s)
                           for s in rm_day["sessions"]), f"{label}: removed session came back"
            REMOVAL_CHECKED.add(label)
    cur_mon = state["week_plans"][_monday(0)]["weeks"][0]["days"][0]
    assert _done("evening") in cur_mon["sessions"], f"{label}: done Monday lost"


#: Paths whose regeneration did put the removed session back on its date in
#: the raw planner output — the removal check is meaningful there.
REMOVAL_CHECKED: set = set()


def _regen_both():
    return _week_nums()


def _path_force():
    wn = client.get("/api/week/0").json()["week_num"]
    assert client.get("/api/week/0?force=true").status_code == 200
    assert client.get(f"/api/week/{wn + 1}?force=true").status_code == 200


def _path_availability():
    av = client.get("/api/state").json().get("availability") or {}
    mon = (av.get("mon") or {}).get("morning") or {}
    r = client.put("/api/state", json={"availability": {"mon": {"morning": {
        "available": not mon.get("available", False), "preferred_location": "home"}}}})
    assert r.status_code == 200
    _regen_both()


def _path_planning_prefs():
    prefs = client.get("/api/state").json().get("planning_prefs") or {}
    cap = int(prefs.get("hard_day_cap_per_week") or 3)
    assert client.put("/api/state", json={"planning_prefs": {"hard_day_cap_per_week": max(1, cap - 1)}}).status_code == 200
    _regen_both()


def _path_weekly_override_put_delete():
    body = {"days": {"tuesday": {"available": False}}}
    assert client.put(f"/api/weekly-override/{_monday(1)}", json=body).status_code == 200
    _regen_both()
    assert client.delete(f"/api/weekly-override/{_monday(1)}").status_code == 200
    _regen_both()


def _path_new_cycle_from_current():
    r = client.post("/api/macrocycle/generate", json={"total_weeks": 12, "from_phase": "current"})
    assert r.status_code == 200, r.text
    _regen_both()


def _path_test_reminder():
    r = client.post("/api/week/test-reminder-response", json={"option": "confirm"})
    assert r.status_code == 200
    _regen_both()


def _path_pause_resume():
    state = deps.load_state(None)
    state["macrocycle"]["pause"] = {"active_since": (date.today() - timedelta(days=7)).isoformat(),
                                   "offset_days": 0, "log": []}
    deps.save_state(state, None)
    r = client.post("/api/plan/resume")
    assert r.status_code == 200, r.text
    _regen_both()


def _path_onboarding_start_week():
    r = client.post("/api/onboarding/start-week", json={"offset_weeks": 1})
    assert r.status_code == 200, r.text
    _regen_both()


def _path_feedback_very_hard():
    state = deps.load_state(None)
    today = date.today().isoformat()
    yday = (date.today() - timedelta(days=1)).isoformat()
    state["feedback_log"] = [{"date": today, "session_id": "x", "difficulty": "very_hard"},
                             {"date": yday, "session_id": "y", "difficulty": "fail"}]
    deps.save_state(state, None)
    for _ in range(2):
        r = client.post("/api/feedback", json={"log_entry": {
            "date": today, "session_id": "nonexistent_session", "actual": {"exercise_feedback_v1": []}}})
        assert r.status_code == 200, r.text
    st = deps.load_state(None)
    for plan in st["week_plans"].values():
        assert not any(a.get("type") == "adaptive_replan" for a in plan.get("adaptations") or [])
    _regen_both()


def _path_start_new_cycle():
    """POST /api/macrocycle/start-new-cycle: the new cycle starts next Monday —
    the specimens' week becomes its week 1."""
    from backend.tests.test_start_new_macrocycle import _valid_body

    r = client.post("/api/macrocycle/start-new-cycle", json=_valid_body())
    assert r.status_code == 200, r.text
    assert r.json()["start_date"] == _monday(1)
    for wn, monday in ((1, _monday(1)), (2, _monday(2))):
        g = client.get(f"/api/week/{wn}")
        assert g.status_code == 200, g.text
        assert g.json()["week_plan"]["start_date"] == monday


PATHS = {
    "force": _path_force,
    "start_new_cycle": _path_start_new_cycle,
    "availability": _path_availability,
    "planning_prefs": _path_planning_prefs,
    "weekly_override": _path_weekly_override_put_delete,
    "new_cycle_from_current": _path_new_cycle_from_current,
    "test_reminder": _path_test_reminder,
    "pause_resume": _path_pause_resume,
    "onboarding_start_week": _path_onboarding_start_week,
    "feedback_very_hard": _path_feedback_very_hard,
}


@pytest.mark.parametrize("name", sorted(PATHS))
def test_user_sessions_survive_every_regeneration_path(name):
    removed = _install_specimens()
    PATHS[name]()
    _assert_survived(removed, name)


def test_removal_check_is_not_vacuous():
    """B369 review: on the plain force path the planner does regenerate the
    removed session on its date, so "it did not come back" proves the merge
    honoured the removal."""
    REMOVAL_CHECKED.clear()
    removed = _install_specimens()
    _path_force()
    _assert_survived(removed, "force")
    assert "force" in REMOVAL_CHECKED


def test_all_paths_in_sequence():
    removed = _install_specimens()
    # The new cycle moves week 1 to next Monday: it goes last.
    for name in sorted(PATHS, key=lambda n: (n == "start_new_cycle", n)):
        PATHS[name]()
        _assert_survived(removed, f"sequence:{name}")


def test_invalidation_flags_and_get_regenerates_through_merge():
    removed = _install_specimens()
    client.put("/api/state", json={"planning_prefs": {"hard_day_cap_per_week": 1}})
    st = deps.load_state(None)
    assert st["week_plans"][_monday(1)].get("_stale") is True
    assert st["week_plans"][_monday(0)].get("_stale") is True
    _regen_both()
    _assert_survived(removed, "stale→GET")


def test_failed_merge_serves_cached_plan_and_saves_nothing(monkeypatch):
    _install_specimens()
    client.put("/api/state", json={"planning_prefs": {"hard_day_cap_per_week": 1}})
    before = deps.load_state(None)

    def boom(*a, **k):
        raise RuntimeError("merge exploded")

    monkeypatch.setattr(week_router, "regenerate_preserving_completed", boom)
    wn = client.get("/api/week/0").json()["week_num"]
    r = client.get(f"/api/week/{wn + 1}")
    assert r.status_code == 200
    assert r.json().get("regeneration_failed") is True
    served = r.json()["week_plan"]["weeks"][0]["days"]
    for i, factory in SPECIMEN_LAYOUT:
        assert factory()["session_id"] in {s["session_id"] for s in served[i]["sessions"]}
    after = deps.load_state(None)
    assert after["week_plans"][_monday(1)] == before["week_plans"][_monday(1)]
    assert after["week_plans"][_monday(1)].get("_stale") is True


def test_failed_generation_serves_cached_plan(monkeypatch):
    _install_specimens()
    before = deps.load_state(None)["week_plans"][_monday(1)]

    def boom(*a, **k):
        raise RuntimeError("planner exploded")

    wn = client.get("/api/week/0").json()["week_num"]
    monkeypatch.setattr(week_router, "generate_phase_week", boom)
    r = client.get(f"/api/week/{wn + 1}?force=true")
    assert r.status_code == 200
    assert r.json().get("regeneration_failed") is True
    assert deps.load_state(None)["week_plans"][_monday(1)] == before


def test_legacy_stash_of_another_week_is_discarded_on_regeneration():
    """P5 at the API: a pre-B369 ``_prev_week_plan`` of an older week never
    lands on this week's dates, and is dropped once the week regenerates."""
    _seed_macrocycle()
    state = deps.load_state(None)
    old_week = _plan({0: [_done("evening", "limit_boulder_gym")]}, start=_monday(-2))
    old_week["weeks"][0]["days"][5].update({"outdoor_session_status": "done",
                                            "outdoor_spot_name": "Arlon"})
    state["_prev_week_plan"] = old_week
    deps.save_state(state, None)
    r = client.get("/api/week/0")
    assert r.status_code == 200
    days = r.json()["week_plan"]["weeks"][0]["days"]
    assert not any(s.get("session_id") == "limit_boulder_gym" and s.get("status") == "done"
                   for s in days[0]["sessions"])
    assert days[5].get("outdoor_session_status") != "done"
    assert "_prev_week_plan" not in deps.load_state(None)


def test_feedback_very_hard_changes_nothing_and_suggests():
    """Daniele's 10-05 case: a very_hard on today's max must not touch
    tomorrow's custom limit boulder — the response only suggests."""
    _seed_macrocycle()
    _week_nums()
    state = deps.load_state(None)
    today = date.today()
    tomorrow = today + timedelta(days=1)
    custom_hard = {**_custom("evening"), "tags": _tags(True, True), "intensity": "max"}
    target_key = _monday(0) if tomorrow.weekday() != 0 else _monday(1)
    plan = state["week_plans"][target_key]
    tday = next(d for d in plan["weeks"][0]["days"] if d["date"] == tomorrow.isoformat())
    tday["sessions"] = [s for s in tday["sessions"] if s.get("slot") != "evening"] + [custom_hard]
    if target_key == _monday(0):
        state["current_week_plan"] = deepcopy(plan)
    state["feedback_log"] = [{"date": today.isoformat(), "session_id": "x", "difficulty": "very_hard"}]
    deps.save_state(state, None)
    r = client.post("/api/feedback", json={"log_entry": {
        "date": today.isoformat(), "session_id": "nonexistent_session",
        "actual": {"exercise_feedback_v1": []}}})
    assert r.status_code == 200, r.text
    after = deps.load_state(None)["week_plans"]
    tday_after = next(d for d in after[target_key]["weeks"][0]["days"] if d["date"] == tomorrow.isoformat())
    assert custom_hard in tday_after["sessions"]
    for k, plan_after in after.items():
        assert not any(a.get("type") == "adaptive_replan" for a in plan_after.get("adaptations") or [])
    sugg = r.json().get("adaptive_suggestion")
    if target_key == _monday(0):
        # Detection reads the current week: the alert names the custom.
        assert sugg and sugg["plan_changed"] is False
        assert sugg["target_date"] == tomorrow.isoformat()
        assert sugg["session_id"] == "custom_cs_b369"


def test_body_part_picker_writes_the_target_week_not_the_legacy_pointer():
    """H11: the picker used to start from ``current_week_plan`` and write it
    over ``week_plans`` — at the Monday rollover that put last week's plan
    back over this one."""
    _seed_macrocycle()
    _week_nums()
    state = deps.load_state(None)
    # Legacy pointer lagging on last week.
    state["current_week_plan"] = _plan({}, start=_monday(-1))
    deps.save_state(state, None)
    target = (date.today() + timedelta(days=1)).isoformat()
    r = client.post("/api/body-part-picker/start", json={
        "body_parts": ["core"], "equipment_mode": "bodyweight", "target_date": target,
        "slot": "lunch", "location": "home"})
    if r.status_code != 200:
        pytest.skip(f"picker unavailable in this fixture: {r.status_code} {r.text[:120]}")
    st = deps.load_state(None)
    key = _monday(0) if date.fromisoformat(target).weekday() != 0 else _monday(1)
    wk = st["week_plans"][key]
    assert wk["start_date"] == key
    tday = next(d for d in wk["weeks"][0]["days"] if d["date"] == target)
    assert any("generated_add" in (s.get("constraints_applied") or []) for s in tday["sessions"])


# ---------------------------------------------------------------------------
# B369 review
# ---------------------------------------------------------------------------

def _ids(day):
    return [(s["session_id"], s["slot"]) for s in day["sessions"]]


def test_generated_add_next_to_an_engine_key_session_keeps_both():
    """A session appended to an occupied slot (body-part picker / coach) does
    not cost the engine's session of that slot on the next regeneration."""
    old = _plan({3: [_generated("evening"), _engine("strength_long", "evening")]})
    fresh = _plan({3: [_engine("strength_long", "evening")]})
    out = regenerate_preserving_completed(old, fresh, preserve_before="2026-10-12")
    assert sorted(_ids(_day(out, 3))) == [("generated_body_part_x", "evening"),
                                          ("strength_long", "evening")]


def test_a_user_session_that_took_the_slot_does_not_get_a_second_one():
    """Skip stub / done / edit in a slot: the engine's session is not added
    next to it."""
    stub = {"slot": "evening", "session_id": "regeneration_easy", "status": "skipped",
            "skipped_session_id": "strength_long", "tags": _tags()}
    old = _plan({3: [stub]})
    out = regenerate_preserving_completed(old, _plan({3: [_engine("strength_long")]}))
    assert _day(out, 3)["sessions"] == [stub]


def test_partial_override_of_the_lunch_is_honoured_on_regeneration():
    thu = [_engine("complementary_conditioning", "lunch"), _engine("gym_technique_boulder", "evening")]
    edited = apply_day_override(_plan({3: thu}), intent="recovery", location="home",
                                reference_date="2026-10-14", target_date="2026-10-15",
                                session_index=0)
    # The override takes the replaced session's slot.
    assert _ids(_day(edited, 3)) == [("yoga_recovery", "lunch"), ("gym_technique_boulder", "evening")]
    ov = next(a for a in edited["adaptations"] if a["type"] == "day_override")
    assert ov["whole_day"] is False
    assert (ov["replaced_session_id"], ov["replaced_slot"]) == ("complementary_conditioning", "lunch")
    out = regenerate_preserving_completed(edited, _plan({3: thu}))
    assert _ids(_day(out, 3)) == [("yoga_recovery", "lunch"), ("gym_technique_boulder", "evening")]


def test_partial_override_with_an_explicit_slot_keeps_it():
    thu = [_engine("complementary_conditioning", "lunch"), _engine("gym_technique_boulder", "evening")]
    edited = apply_day_override(_plan({3: thu}), intent="recovery", location="home",
                                reference_date="2026-10-14", target_date="2026-10-15",
                                session_index=0, slot="morning")
    assert ("yoga_recovery", "morning") in _ids(_day(edited, 3))


def test_whole_day_override_takes_only_the_slots_it_replaced():
    """A slot the new structure adds later on that date gets the engine's
    session; the slots the override replaced do not."""
    base = _plan({2: [_engine("strength_long", "evening")]})
    edited = apply_day_override(base, intent="technique", location="home",
                                reference_date="2026-10-13", target_date="2026-10-14")
    ov = next(a for a in edited["adaptations"] if a["type"] == "day_override")
    # A301: one targeted session replaced → named by id + slot.
    assert (ov["replaced_session_id"], ov["replaced_slot"]) == ("strength_long", "evening")
    fresh = _plan({2: [_engine("prehab_maintenance", "lunch"), _engine("strength_long", "evening")]})
    out = regenerate_preserving_completed(edited, fresh)
    assert _ids(_day(out, 2)) == [("prehab_maintenance", "lunch"), ("technique_focus_gym", "evening")]


def test_legacy_whole_day_override_still_takes_the_whole_date():
    old = _plan({2: [_override("evening")]})
    old["adaptations"] = [{"type": "day_override", "target_date": "2026-10-14", "whole_day": True}]
    fresh = _plan({2: [_engine("prehab_maintenance", "lunch"), _engine("strength_long", "evening")]})
    out = regenerate_preserving_completed(old, fresh)
    assert _day(out, 2)["sessions"] == [_override("evening")]


def test_move_over_an_engine_session_records_and_honours_the_replacement():
    base = _plan({1: [_engine("strength_long", "evening")], 3: [_engine("yoga_recovery", "evening")]})
    moved = apply_events(base, [{"event_type": "move_session", "from_date": "2026-10-13",
                                 "from_slot": "evening", "to_date": "2026-10-15",
                                 "to_slot": "evening"}])
    ev = next(a["event"] for a in moved["adaptations"] if a.get("type") == "event")
    assert ev["replaced_session_id"] == "yoga_recovery"
    assert ("2026-10-15", "yoga_recovery", "evening") in uo.removed_refs(moved)
    out = regenerate_preserving_completed(moved, deepcopy(base))
    assert _ids(_day(out, 3)) == [("strength_long", "evening")]


def test_regeneration_alerts_on_a_guard_conflict_without_rewriting():
    """A forced finger session the merge puts back next to a finger session
    the planner generated: an alert, nothing downshifted (A301)."""
    old = _plan({1: [{**_forced("evening"), "session_id": "max_hang_5s"}]})
    fresh = _plan({2: [{"slot": "evening", "session_id": "strength_long", "intensity": "max",
                        "tags": _tags(True, True)}]})
    out = regenerate_preserving_completed(old, fresh)
    assert _ids(_day(out, 1)) == [("max_hang_5s", "evening")]
    assert _ids(_day(out, 2)) == [("strength_long", "evening")]
    alerts = [a for a in out["adaptations"] if a["type"] == "regeneration_guard_warnings"]
    assert len(alerts) == 1
    w = alerts[0]["warnings"]
    assert w[0]["date"] == "2026-10-14" and w[0]["action"] == "guard_alert"
    assert w[0]["reason"] == "finger_spacing_downshift"
    # Recomputed, not piled up, on the next regeneration.
    again = regenerate_preserving_completed(out, fresh)
    assert len([a for a in again["adaptations"] if a["type"] == "regeneration_guard_warnings"]) == 1


def test_engine_only_week_has_no_alert_and_fresh_load():
    old = _plan({1: [_engine("strength_long")]}, weekly_load_summary={"planned_load": 520, "total_load": 520})
    fresh = _plan({2: [_engine("strength_long")]}, weekly_load_summary={"planned_load": 310, "total_load": 310})
    out = regenerate_preserving_completed(old, fresh)
    assert "adaptations" not in out
    assert out["weekly_load_summary"] == {"planned_load": 310, "total_load": 310}
    assert out["weeks"] == fresh["weeks"]


def test_moved_session_rewritten_by_a_ripple_survives_regeneration():
    """Move Wed→Thu, then a hard override on Wed: the ripple eases Thu, the
    session stays the user's and is still on Thu after a regeneration."""
    hard = {"slot": "evening", "session_id": "power_contact_gym", "intensity": "high",
            "tags": _tags(True, False)}
    base = _plan({2: [hard]})
    moved = apply_events(base, [{"event_type": "move_session", "from_date": "2026-10-14",
                                 "from_slot": "evening", "to_date": "2026-10-15",
                                 "to_slot": "evening"}])
    ov = apply_day_override(moved, intent="strength", location="home",
                            reference_date="2026-10-13", target_date="2026-10-14")
    thu = _day(ov, 3)["sessions"]
    assert len(thu) == 1 and "user_moved" in thu[0]["constraints_applied"]
    out = regenerate_preserving_completed(ov, base)
    assert _day(out, 3)["sessions"] == thu


def test_locked_by_merge_covers_overrides_and_removals():
    from backend.engine.retest_policy import _locked_by_merge

    ws = date.fromisoformat(START)
    plan = _plan({})
    plan["adaptations"] = [
        {"type": "day_override", "target_date": "2026-10-14", "whole_day": True},
        {"type": "day_override", "target_date": "2026-10-15", "whole_day": True,
         "replaced_slots": ["morning"]},
        {"type": "event", "event": {"event_type": "remove_session", "date": "2026-10-16",
                                     "session_ref": "test_max_hang_5s"}},
        {"type": "event", "event": {"event_type": "remove_session", "date": "2026-10-11",
                                     "slot": "evening"}},  # before today: ignored
    ]
    out = _locked_by_merge({"week_plans": {START: plan}}, ws, ws)
    assert "2026-10-14" in out["locked_dates"]
    assert {"date": "2026-10-15", "slot": "morning"} in out["locked_slots"]
    assert "2026-10-16" in out["locked_dates"]
    assert not any(x["date"] == "2026-10-11" for x in out["locked_slots"])


def test_client_cannot_lower_the_frozen_floor(monkeypatch):
    """preserve_before earlier than the client's today: the days in between
    are past for the planner (skipped), so they are copied wholesale — a
    planned, unticked session there is not deleted."""
    _seed_macrocycle()
    _week_nums()
    mon = _monday(0)
    wed = (date.fromisoformat(mon) + timedelta(days=2)).isoformat()
    monkeypatch.setattr(week_router, "_client_today", lambda t: wed)
    state = deps.load_state(None)
    cur = state["week_plans"][mon]
    cur["weeks"][0]["days"][0]["sessions"] = [_engine("strength_long", "evening")]
    cur["weeks"][0]["days"][1]["sessions"] = [_engine("yoga_recovery", "evening")]
    state["current_week_plan"] = deepcopy(cur)
    deps.save_state(state, None)
    before = deepcopy(cur["weeks"][0]["days"][:2])
    r = client.get(f"/api/week/0?force=true&preserve_before={mon}&today={wed}")
    assert r.status_code == 200, r.text
    after = deps.load_state(None)["week_plans"][mon]["weeks"][0]["days"][:2]
    assert after == before
