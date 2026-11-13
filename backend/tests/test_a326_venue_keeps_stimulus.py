"""A326 (D287 E1/E2/E3) — changing the venue of a session keeps its stimulus.

Before A326 ``change_gym`` replaced every session its new place could not host
with complementary_conditioning: a rope evening moved to a boulder-only gym
(Bkl, Boulder Forest, Eifelblock) lost its stimulus, and an evening moved home
never got the hangboard / pulling sessions the home kit allows — Daniele
rebuilt those evenings by hand (remove + custom + add). Decided with Daniele on
2026-11-13: ``_find_gym_change_replacement`` looks for a session that keeps the
stimulus BEFORE that chain —

1. a key the session carries (``key_sessions_v1.session_keys``) → the first
   ``floor_candidates`` / ``session_ids`` of that key that fits the new place;
2. a primary session → the first primary session of the phase pool with the
   same hard / finger tags that fits (within the phase intensity cap);
3. home → a home session for a key still open this week (the one covering most
   open keys), else strength maintenance (finger_maintenance_home);
4. the B414 chain, unchanged (complementary_conditioning, regeneration_easy).

The three divergences from planner_v2 are settled the planner's way: every gym
has a pull-up bar, a home wall widens the catalog location
(``_expand_session_locations``), a replaced session keeps the user's markers
but not the engine constraints of the session that left. Guards stay alerts
(A301); tests keep their B414 rules; no new event, marker or field.

Real shapes from the D287 appendix (Daniele's gym and home equipment lists, the
sessions of his weeks); synthetic plans only.
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
from backend.engine import key_sessions_v1 as ks
from backend.engine import user_owned as uo
from backend.engine.macrocycle_v1 import PHASE_INTENSITY_CAP, _build_session_pool
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.replanner_v1 import apply_events

REPO = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO / "backend" / "data" / "user_state.json"
client = TestClient(app)

WS = "2026-11-16"  # Monday
MON, TUE, WED, THU, FRI, SAT, SUN = ((date.fromisoformat(WS) + timedelta(days=i)).isoformat() for i in range(7))

# Daniele's places (D287 appendix, equipment lists as saved).
COCQUE = {"gym_id": "cocque", "name": "Cocque",
          "equipment": ["spraywall", "board_kilter", "gym_routes", "hangboard", "campus_board", "pullup_bar"]}
BKL = {"gym_id": "bkl", "name": "Bkl",
       "equipment": ["hangboard", "board_moonboard", "spraywall", "gym_boulder", "campus_board", "pullup_bar",
                     "dumbbell", "rings"]}
FOREST = {"gym_id": "forest", "name": "Boulder Forest", "equipment": ["gym_boulder", "board_kilter", "hangboard", "pullup_bar"]}
EIFEL = {"gym_id": "eifel", "name": "Eifelblock", "equipment": ["gym_boulder", "board_moonboard", "hangboard"]}
DSUMMIT = {"gym_id": "dsummit", "name": "D-Summit", "equipment": ["gym_routes", "gym_boulder", "hangboard", "board_moonboard"]}
WORK = {"gym_id": "work", "name": "Work",
        "equipment": ["ab_wheel", "barbell", "bench", "cable_machine", "dumbbell", "foam_roller", "leg_press",
                      "pullup_bar", "resistance_band", "rings", "treadmill", "weight"]}
WORK_GYM = {"gym_id": "work_gym", "name": "Work Gym", "equipment": []}  # saved with nothing ticked
ROPE_ONLY = {"gym_id": "ropeonly", "name": "Rope only", "equipment": ["gym_routes", "hangboard", "pullup_bar"]}  # synthetic
BLOC = {"gym_id": "bloc", "name": "Bloc", "equipment": ["gym_boulder", "board_moonboard"]}  # synthetic: no bar, no hangboard
GYMS = [COCQUE, BKL, FOREST, EIFEL, DSUMMIT, WORK, WORK_GYM, ROPE_ONLY, BLOC]
HOME = ["hangboard", "pullup_bar", "dumbbell", "band", "resistance_band", "loading_pin"]
HOME_NO_HANGBOARD = ["pullup_bar", "band"]

CC = "complementary_conditioning"


def _s(sid: str, slot: str = "evening", gym: str | None = "cocque", phase: str = "strength_power", **kw) -> dict:
    """A planned session as the planner writes it."""
    m = _SESSION_META[sid]
    s = {"slot": slot, "session_id": sid, "location": "gym" if gym else "home", "gym_id": gym,
         "phase_id": phase, "intensity": m["intensity"], "estimated_load_score": 40,
         "tags": {"hard": m["hard"], "finger": m["finger"]},
         "explain": [f"phase={phase}", f"slot={slot}", "pass1:primary"]}
    s.update(kw)
    return s


def _resolved(*exercise_ids: str) -> dict:
    return {"resolved_session": {"exercise_instances": [{"exercise_id": e} for e in exercise_ids]}}


def _custom(slot: str = "evening") -> dict:
    return {"slot": slot, "session_id": "custom_cs_a326", "custom_session_id": "cs_a326", "is_custom": True,
            "name": "Casa — max hang", "location": "gym", "gym_id": "cocque", "status": "planned",
            "intensity": "high", "tags": {"hard": True, "finger": True}, "constraints_applied": ["custom_add"],
            "exercises": [{"exercise_id": "max_hang_7s", "sets": 5, "work_seconds": 7}]}


def _plan(phase: str, sessions_by_date: dict) -> dict:
    days = [{"date": d, "sessions": deepcopy(sessions_by_date.get(d, []))} for d in (MON, TUE, WED, THU, FRI, SAT, SUN)]
    return {"start_date": WS, "plan_revision": 1,
            "profile_snapshot": {"phase_id": phase, "session_pool": _build_session_pool(phase, "lead"),
                                 "intensity_cap": PHASE_INTENSITY_CAP[phase], "hard_cap_per_week": 3,
                                 "recovery_multiplier": 1.0},
            "weeks": [{"week_index": 1, "days": days}], "adaptations": []}


def _event(d_iso: str, *, gym: str | None = None, location: str = "gym", slot: str | None = "evening") -> dict:
    ev = {"event_type": "change_gym", "date": d_iso, "location": location}
    if gym:
        ev["gym_id"] = gym
    if slot:
        ev["slot"] = slot
    return ev


def _change(plan: dict, d_iso: str = THU, *, gym: str | None = None, location: str = "gym",
            slot: str | None = "evening", home=HOME, today: str = MON) -> dict:
    return apply_events(deepcopy(plan), [_event(d_iso, gym=gym, location=location, slot=slot)],
                        gyms=deepcopy(GYMS), home_equipment=home, today=today)


def _day(plan: dict, d_iso: str) -> list:
    return next(d for d in plan["weeks"][0]["days"] if d["date"] == d_iso)["sessions"]


def _at(plan: dict, d_iso: str = THU, slot: str = "evening") -> dict:
    return next(s for s in _day(plan, d_iso) if s["slot"] == slot)


def _record(plan: dict) -> dict:
    return [a for a in plan["adaptations"] if a.get("type") == "change_gym"][-1]


def _why(s: dict) -> str | None:
    """The A326 note: the third explain entry of a replaced session."""
    ex = s.get("explain") or []
    return ex[2] if len(ex) > 2 and ex[0].startswith("gym_change:") else None


# ---------------------------------------------------------------------------
# A rope evening moved to a boulder-only gym (E1)
# ---------------------------------------------------------------------------

class TestRopeEveningAtABoulderGym:
    def test_route_endurance_keeps_its_power_endurance_key(self):
        # PE week; the route endurance session resolved with linked laps (PE family) carries the PE key.
        re = _s("route_endurance_gym", phase="power_endurance",
                resolved=_resolved("warmup_easy_boulders", "route_linked_laps", "pushup"))
        plan = _plan("power_endurance", {THU: [re]})
        assert ks.session_keys(re, "power_endurance") == ["power_endurance"]
        out = _change(plan, gym="forest")
        s = _at(out)
        assert (s["session_id"], s["location"], s["gym_id"]) == ("power_endurance_gym", "gym", "forest")
        assert s["explain"] == ["gym_change: route_endurance_gym → power_endurance_gym",
                                "missing_equipment={'gym_routes'}", "kept_key=power_endurance"]
        assert s["tags"] == {"hard": True, "finger": False} and "resolved" not in s
        rec = _record(out)
        assert rec["warnings"] == ["route_endurance_gym → power_endurance_gym (missing_equipment={'gym_routes'})"]
        assert "lost_finger" not in rec

    def test_lead_tryhard_with_technique_drills_keeps_the_technique_key(self):
        lt = _s("lead_tryhard_gym", phase="power_endurance",
                resolved=_resolved("fall_practice", "lead_precision_feet_above_bolt", "lead_technique_under_pump"))
        out = _change(_plan("power_endurance", {WED: [lt]}), WED, gym="forest")
        s = _at(out, WED)
        assert (s["session_id"], _why(s)) == ("technique_focus_gym", "kept_key=technique")

    def test_unresolved_lead_tryhard_stays_a_climbing_evening(self):
        # The try-hard itself cannot follow: no boulder session delivers it (D287 e6 matrix).
        out = _change(_plan("power_endurance", {WED: [_s("lead_tryhard_gym", phase="power_endurance")]}), WED,
                      gym="forest")
        s = _at(out, WED)
        assert (s["session_id"], _why(s)) == ("technique_focus_gym", "same_load")

    @pytest.mark.parametrize("gym", ["eifel", "bkl"])
    def test_route_projecting_becomes_limit_bouldering(self, gym):
        out = _change(_plan("performance", {SAT: [_s("route_projecting_gym", phase="performance")]}), SAT, gym=gym)
        s = _at(out, SAT)
        assert (s["session_id"], s["gym_id"], _why(s)) == ("limit_boulder_gym", gym, "same_load")
        assert s["tags"] == {"hard": True, "finger": True} and s["intensity"] == "max"
        assert "lost_finger" not in _record(out)

    def test_technique_at_a_rope_only_gym_climbs_on_ropes(self):
        out = _change(_plan("power_endurance", {SAT: [_s("technique_focus_gym", phase="power_endurance")]}), SAT,
                      gym="ropeonly")
        assert (_at(out, SAT)["session_id"], _why(_at(out, SAT))) == ("endurance_aerobic_gym", "same_load")


class TestSessionThatFitsIsUnchanged:
    @pytest.mark.parametrize("phase,sid,gym", [
        ("power_endurance", "power_endurance_gym", "forest"),  # D287 2d
        ("strength_power", "limit_boulder_gym", "bkl"),
        ("performance", "limit_boulder_gym", "eifel"),
    ])
    def test_only_the_place_changes(self, phase, sid, gym):
        before = _s(sid, phase=phase, resolved=_resolved("limit_bouldering"))
        out = _change(_plan(phase, {THU: [before]}), gym=gym)
        s = _at(out)
        expected = {k: v for k, v in before.items() if k != "resolved"}
        expected["gym_id"] = gym
        assert s == expected
        assert _record(out)["warnings"] == []


# ---------------------------------------------------------------------------
# An evening moved home (E2)
# ---------------------------------------------------------------------------

class TestEveningMovedHome:
    def _week(self, **extra) -> dict:
        sessions = {MON: [_s("limit_boulder_gym", gym="bkl")], THU: [_s("technique_focus_gym", gym="bkl")]}
        for d, ss in extra.items():
            sessions.setdefault(d, []).extend(ss)
        return _plan("strength_power", sessions)

    def test_finger_max_and_pulling_open_give_strength_long(self):
        out = _change(self._week(), location="home")
        s = _at(out)
        assert (s["session_id"], s["location"], s["gym_id"]) == ("strength_long", "home", None)
        assert s["explain"] == ["gym_change: technique_focus_gym → strength_long", "incompatible_location=home",
                                "open_key=finger_max+pulling_max"]
        assert s["tags"] == {"hard": True, "finger": True}

    def test_only_finger_max_open_gives_finger_strength_home(self):
        out = _change(self._week(**{SAT: [_s("pulling_strength_gym", gym="bkl")]}), location="home")
        assert (_at(out)["session_id"], _why(_at(out))) == ("finger_strength_home", "open_key=finger_max")

    def test_keys_covered_give_strength_maintenance(self):
        done = _s("strength_long", gym=None, status="done")
        out = _change(self._week(**{TUE: [done]}), location="home")
        s = _at(out)
        assert (s["session_id"], _why(s)) == ("finger_maintenance_home", "strength_maintenance")
        assert s["tags"] == {"hard": False, "finger": True}

    def test_a_planned_session_before_today_does_not_close_the_key(self):
        plan = self._week(**{TUE: [_s("strength_long", gym=None)]})  # planned, never marked
        assert _at(_change(plan, location="home", today=MON))["session_id"] == "finger_maintenance_home"
        assert _at(_change(plan, location="home", today=WED))["session_id"] == "strength_long"

    def test_a_skipped_key_session_does_not_close_the_key(self):
        stub = _s("regeneration_easy", gym=None, status="skipped", skipped_session_id="strength_long")
        assert _at(_change(self._week(**{TUE: [stub]}), location="home"))["session_id"] == "strength_long"

    def test_power_endurance_evening_gets_the_finger_maintenance_key(self):
        pe = _s("power_endurance_gym", phase="power_endurance", gym="bkl")
        out = _change(_plan("power_endurance", {THU: [pe]}), location="home")
        assert (_at(out)["session_id"], _why(_at(out))) == ("finger_strength_home", "open_key=finger_maintenance")
        covered = _plan("power_endurance", {THU: [pe], SUN: [_s("finger_maintenance_gym", phase="power_endurance")]})
        out = _change(covered, location="home")
        assert (_at(out)["session_id"], _why(_at(out))) == ("finger_maintenance_home", "strength_maintenance")

    @pytest.mark.parametrize("phase,sid", [("strength_power", "limit_boulder_gym"),
                                           ("performance", "route_projecting_gym")])
    def test_hard_finger_evening_keeps_its_load(self, phase, sid):
        out = _change(_plan(phase, {THU: [_s(sid, phase=phase)]}), location="home")
        s = _at(out)
        assert (s["session_id"], _why(s)) == ("finger_strength_home", "same_load")
        assert "lost_finger" not in _record(out)

    def test_whole_day_the_lunch_never_gets_a_key_session(self):
        # The app sends no slot: the whole day moves. A complementary lunch keeps the B414 chain.
        plan = self._week()
        _day(plan, THU).insert(0, _s("treadmill_hiit_4x4", slot="lunch", gym="work"))
        out = _change(plan, location="home", slot=None)
        assert [(s["slot"], s["session_id"]) for s in _day(out, THU)] == [("lunch", CC), ("evening", "strength_long")]
        assert _why(_at(out, THU, "lunch")) is None

    def test_without_a_hangboard_the_chain_is_as_before(self):
        out = _change(self._week(), location="home", home=HOME_NO_HANGBOARD)
        assert (_at(out)["session_id"], _why(_at(out))) == (CC, None)
        out = _change(_plan("strength_power", {THU: [_s("limit_boulder_gym")]}), location="home",
                      home=HOME_NO_HANGBOARD)
        assert _at(out)["session_id"] == CC and _record(out)["lost_finger"] is True

    def test_deload_gets_no_strength_maintenance(self):
        out = _change(_plan("deload", {THU: [_s("easy_climbing_deload", phase="deload")]}), location="home")
        assert (_at(out)["session_id"], _why(_at(out))) == (CC, None)


# ---------------------------------------------------------------------------
# Past and user-owned sessions
# ---------------------------------------------------------------------------

class TestPastAndUserSessions:
    def test_done_and_skipped_sessions_are_never_touched(self):
        done = _s("upper_push_arms_lunch", slot="lunch", gym="work", status="done",
                  actual_exercises=[{"exercise_id": "bench_press", "completed": True}])
        stub = _s("regeneration_easy", slot="morning", gym=None, status="skipped",
                  skipped_session_id="finger_strength_home")
        plan = _plan("strength_power", {THU: [stub, done, _s("technique_focus_gym", gym="bkl")]})
        out = _change(plan, location="home", slot=None)
        assert _at(out, THU, "morning") == stub and _at(out, THU, "lunch") == done
        assert _at(out, THU, "evening")["session_id"] == "strength_long"

    def test_other_days_are_byte_identical(self):
        plan = _plan("strength_power", {
            MON: [_s("limit_boulder_gym", gym="bkl", status="done")],
            TUE: [_s("strength_long", gym=None, status="done")],
            WED: [_custom()],
            THU: [_s("technique_focus_gym", gym="bkl")],
            SAT: [_s("route_projecting_gym", constraints_applied=["user_moved"])],
        })
        out = _change(plan, location="home")
        for b, a in zip(plan["weeks"][0]["days"], out["weeks"][0]["days"]):
            if b["date"] != THU:
                assert a == b, b["date"]

    def test_a_custom_in_the_slot_keeps_its_content(self):
        c = _custom()
        out = _change(_plan("strength_power", {THU: [c]}), location="home")
        s = _at(out)
        assert {k: v for k, v in s.items() if k not in ("location", "gym_id")} == \
            {k: v for k, v in c.items() if k not in ("location", "gym_id")}
        assert (s["location"], s["gym_id"]) == ("home", None)
        assert _record(out)["warnings"] == []

    def test_a_moved_session_stays_the_users(self):
        # Marker semantics unchanged: the user's marker stays on the replacement.
        moved = _s("route_projecting_gym", phase="performance", constraints_applied=["user_moved"])
        out = _change(_plan("performance", {SAT: [moved]}), SAT, gym="bkl")
        s = _at(out, SAT)
        assert s["session_id"] == "limit_boulder_gym" and s["constraints_applied"] == ["user_moved"]
        assert uo.is_user_owned(s)

    def test_stale_engine_constraints_go_the_user_markers_stay(self):
        ar = _s("technique_focus_gym", phase="power_endurance", constraints_applied=["key_reschedule", "auto_reschedule"],
                auto_reschedule_id="ar-1")
        out = _change(_plan("power_endurance", {SAT: [ar]}), SAT, gym="ropeonly")
        s = _at(out, SAT)
        assert s["session_id"] == "endurance_aerobic_gym"
        assert s["constraints_applied"] == ["key_reschedule"] and s["auto_reschedule_id"] == "ar-1"

    def test_a_compatible_session_keeps_its_constraints(self):
        ar = _s("technique_focus_gym", constraints_applied=["key_reschedule", "auto_reschedule"])
        out = _change(_plan("strength_power", {THU: [ar]}), gym="forest")
        assert _at(out)["constraints_applied"] == ["key_reschedule", "auto_reschedule"]


# ---------------------------------------------------------------------------
# The fit check, aligned with planner_v2
# ---------------------------------------------------------------------------

class TestPlannerAlignment:
    @pytest.mark.parametrize("gym", ["bloc", "work_gym"])
    def test_every_gym_has_a_pull_up_bar(self, gym):
        # Neither lists a bar nor a hangboard (which implies one, B159): planner_v2
        # places pull-up sessions there anyway (_equipment_for_location); before
        # A326 change_gym replaced them.
        out = _change(_plan("strength_power", {THU: [_s("pulling_strength_gym")]}), gym=gym)
        assert (_at(out)["session_id"], _at(out)["gym_id"]) == ("pulling_strength_gym", gym)
        assert _record(out)["warnings"] == []

    def test_an_unknown_gym_still_has_nothing(self):
        # A gym id not in the list: no equipment at all (B173 warning), no implicit bar.
        out = _change(_plan("strength_power", {THU: [_s("pulling_strength_gym")]}), gym="nowhere")
        assert _at(out)["session_id"] != "pulling_strength_gym"

    def test_a_home_wall_hosts_a_wall_session(self):
        out = _change(_plan("strength_power", {THU: [_s("technique_focus_gym")]}), location="home",
                      home=["homewall", "hangboard", "pullup_bar"])
        assert (_at(out)["session_id"], _at(out)["location"]) == ("technique_focus_gym", "home")

    def test_missing_equipment_is_printed_in_order(self):
        out = _change(_plan("strength_power", {THU: [_s("upper_push_arms_lunch", slot="lunch", gym="work")]}),
                      gym="forest", slot="lunch")
        assert _at(out, THU, "lunch")["explain"][1] == "missing_equipment={'cable_machine', 'dumbbell'}"

    def test_a_test_keeps_the_b414_rules(self):
        # A test measures: never turned into a training session of its key (here pulling_strength_gym).
        combo = _s("test_max_hang_pullup", tags={"hard": True, "finger": True, "test": True},
                   explain=["pass3:retest_policy", "retest:finger:end_of_phase", "r", "retest:pulling:end_of_phase", "r"])
        out = _change(_plan("strength_power", {FRI: [combo]}), FRI, gym="work")
        s = _at(out, FRI)
        assert (s["session_id"], _why(s)) == (CC, None) and _record(out)["lost_finger"] is True


# ---------------------------------------------------------------------------
# Dry run and determinism
# ---------------------------------------------------------------------------

class TestDryRunAndDeterminism:
    @pytest.mark.parametrize("ev", [
        _event(THU, location="home"),
        _event(SAT, gym="bkl"),
    ])
    def test_check_insertion_returns_the_same_substitution(self, ev):
        plan = _plan("strength_power", {MON: [_s("limit_boulder_gym", gym="bkl")],
                                        THU: [_s("technique_focus_gym", gym="bkl")],
                                        SAT: [_s("route_projecting_gym", constraints_applied=["user_moved"])]})
        state = {"week_plans": {WS: deepcopy(plan)}, "equipment": {"gyms": deepcopy(GYMS), "home": list(HOME)}}
        snapshot = deepcopy(state)
        dry = ks.check_insertion(state, MON, plan=deepcopy(plan), events=[deepcopy(ev)], archived_weeks=[])
        real = apply_events(deepcopy(plan), [deepcopy(ev)], gyms=deepcopy(GYMS), home_equipment=list(HOME), today=MON)
        assert _day(dry["week_plan"], ev["date"]) == _day(real, ev["date"])
        assert _day(real, ev["date"]) != _day(plan, ev["date"])
        assert state == snapshot  # nothing written into the input

    def test_deterministic(self):
        plan = _plan("strength_power", {MON: [_s("limit_boulder_gym", gym="bkl")],
                                        THU: [_s("treadmill_hiit_4x4", slot="lunch", gym="work"),
                                              _s("technique_focus_gym", gym="bkl")]})
        a = _change(plan, location="home", slot=None)
        b = _change(plan, location="home", slot=None)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


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


class TestApi:
    def _seed(self) -> tuple:
        t = date.today()
        mon = (t - timedelta(days=t.weekday())).isoformat()
        thu = (date.fromisoformat(mon) + timedelta(days=3)).isoformat()
        days = [{"date": (date.fromisoformat(mon) + timedelta(days=i)).isoformat(), "sessions": []} for i in range(7)]
        days[0]["sessions"] = [_s("limit_boulder_gym", gym="bkl")]
        days[3]["sessions"] = [_s("technique_focus_gym", gym="bkl")]
        plan = {"start_date": mon, "plan_revision": 1, "weeks": [{"week_index": 1, "days": days}],
                "profile_snapshot": {"phase_id": "strength_power",
                                     "session_pool": _build_session_pool("strength_power", "lead"),
                                     "intensity_cap": "max"},
                "adaptations": []}
        state = deps.load_state(None)
        state.setdefault("week_plans", {})[mon] = deepcopy(plan)
        state.pop("macrocycle_paused", None)
        state["equipment"] = {"gyms": deepcopy(GYMS), "home": list(HOME), "home_enabled": True}
        deps.save_state(state, None)
        return mon, thu, plan

    def _post(self, plan: dict, mon: str, thu: str, dry_run: bool) -> dict:
        r = client.post("/api/replanner/events", json={
            "week_plan": plan, "today": mon, "dry_run": dry_run,
            "events": [{"event_type": "change_gym", "date": thu, "location": "home", "slot": "evening"}],
        })
        assert r.status_code == 200, r.text
        return r.json()

    @staticmethod
    def _evening(week_plan: dict, d_iso: str) -> dict:
        day = next(d for d in week_plan["weeks"][0]["days"] if d["date"] == d_iso)
        return next(s for s in day["sessions"] if s["slot"] == "evening")

    def test_dry_run_returns_the_substitution_and_writes_nothing(self, isolated_state):
        mon, thu, plan = self._seed()
        stored_before = json.dumps(deps.load_state(None)["week_plans"][mon], sort_keys=True)
        dry = self._post(deepcopy(plan), mon, thu, dry_run=True)
        assert dry["dry_run"] is True
        s = self._evening(dry["week_plan"], thu)
        assert (s["session_id"], s["location"], _why(s)) == ("strength_long", "home", "open_key=finger_max+pulling_max")
        assert json.dumps(deps.load_state(None)["week_plans"][mon], sort_keys=True) == stored_before
        body = self._post(deepcopy(plan), mon, thu, dry_run=False)
        assert self._evening(body["week_plan"], thu)["session_id"] == "strength_long"
        stored = self._evening(deps.load_state(None)["week_plans"][mon], thu)
        assert (stored["session_id"], stored["location"], stored["gym_id"]) == ("strength_long", "home", None)
        assert body["warnings"] == ["technique_focus_gym → strength_long (incompatible_location=home)"]
