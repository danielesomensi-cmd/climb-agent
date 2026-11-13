"""A328 (D288 R3, decided by Daniele 2026-11-13) — the terminal deload keeps a
reduced dose of each key stimulus instead of removing all hard work.

The form (``macrocycle_v1.DELOAD_FORM``): the same climbing days as a normal
week; sets x 0.5; ONE technique session; ONE finger exposure (3 x 7 s max hang
at the previous phase's working load -10 %, >= 3 s in reserve) for an athlete
with a tested hang max; every other climbing day easy; no power-endurance
intervals, no tests, no work to failure, no weighted pull-ups.

The "mirror" tests reproduce Daniele's deload week of 2026-11-30 from the shapes
of the production mirror of 2026-11-13 (availability, gyms, prefs, the deload
phase saved with the OLD pool and ``intensity_cap: low``, the previous week's
Saturday project, his custom lunch of Tuesday and the lunch he removed), run
through the planner and the B369 merge the way ``GET /api/week`` does.
"""
from __future__ import annotations

import copy
import json
from datetime import date, timedelta

import pytest

from backend.engine import anchored_load as al
from backend.engine.macrocycle_v1 import (
    DELOAD_ABOVE_CAP,
    DELOAD_FILLERS,
    DELOAD_FINGER_SESSION,
    DELOAD_LOAD_FACTOR,
    DELOAD_TECHNIQUE_SESSION,
    DELOAD_TOUCH_LAST_DAYS,
    _BASE_WEIGHTS,
    _adjust_domain_weights,
    _build_session_pool,
    apply_deload_week,
)
from backend.engine.planner_v2 import _SESSION_META, allowed_locations_for, generate_phase_week
from backend.engine.replanner_v1 import regenerate_preserving_completed

# ---------------------------------------------------------------------------
# Daniele's shapes (production mirror 2026-11-13)
# ---------------------------------------------------------------------------

COCQUE, WORK, BKL = "16710e5a", "3c7f08e0", "3cd991ce"
GYMS = [
    {"name": "Cocque", "gym_id": COCQUE,
     "equipment": ["spraywall", "board_kilter", "gym_routes", "hangboard", "campus_board", "pullup_bar"]},
    {"name": "Work", "gym_id": WORK,
     "equipment": ["ab_wheel", "barbell", "bench", "cable_machine", "dumbbell", "foam_roller", "leg_press",
                   "pullup_bar", "resistance_band", "rings", "treadmill", "weight"]},
    {"name": "Bkl", "gym_id": BKL,
     "equipment": ["hangboard", "board_moonboard", "spraywall", "gym_boulder", "campus_board", "pullup_bar",
                   "dumbbell", "rings"]},
]
HOME = ["hangboard", "pullup_bar", "dumbbell", "band", "resistance_band", "loading_pin"]
EQUIPMENT = {"gyms": GYMS, "home": HOME, "home_enabled": True}


def _slot(available: bool, gym=None, role=None, loc="gym", **kw):
    s = {"gym_id": gym, "available": available, "preferred_location": loc}
    if role:
        s["role"] = role
    s.update(kw)
    return s


def _avail():
    lunch = _slot(True, WORK, "complementary", max_minutes=55)
    off = _slot(False, None, loc="home")
    out = {}
    for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        evening = _slot(True, BKL if wd == "mon" else COCQUE, "primary")
        if wd == "fri":
            evening = _slot(False, None)
        out[wd] = {"morning": dict(off), "lunch": dict(lunch) if wd not in ("sat", "sun") else dict(off),
                   "evening": evening, "_day_meta": None}
    return out


PREFS = {"phase_weeks": {"base": 2}, "hard_day_cap_per_week": 5,
         "complementary_rotation": ["arms_shoulders", "legs", "hiit", "z2", "upper_push_arms"],
         "target_training_days_per_week": 6}
#: The deload phase as saved in Daniele's macrocycle (generated before A328).
SAVED_POOL = ["flexibility_full", "prehab_maintenance", "regeneration_easy", "yoga_recovery",
              "deload_recovery", "easy_climbing_deload", "finger_aerobic_base"]
SAVED_WEIGHTS = {"technique": 0.147, "core_prehab": 0.294, "finger_strength": 0.059,
                 "power_endurance": 0.147, "volume_climbing": 0.294, "pulling_strength": 0.059}
WS = "2026-11-30"
DAYS = [(date.fromisoformat(WS) + timedelta(days=i)).isoformat() for i in range(7)]
MON, TUE, WED, THU, FRI, SAT, SUN = DAYS


def _s(sid, slot="evening", gym=COCQUE, **kw):
    m = _SESSION_META[sid]
    out = {"slot": slot, "session_id": sid, "location": "gym" if gym else "home", "gym_id": gym,
           "intensity": m["intensity"], "tags": {"hard": m["hard"], "finger": m["finger"]}}
    out.update(kw)
    return out


def _week(start, sessions_by_day, **extra):
    d0 = date.fromisoformat(start)
    days = []
    for i in range(7):
        d = (d0 + timedelta(days=i)).isoformat()
        days.append({"date": d, "weekday": ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[i],
                     "sessions": copy.deepcopy(sessions_by_day.get(d, []))})
    plan = {"start_date": start, "plan_version": "planner.v2", "weeks": [{"week_index": 1, "days": days}],
            "adaptations": []}
    plan.update(extra)
    return plan


def _prev_week():
    """2026-11-23 (performance) as cached: limit Wed, project Sat (finger + hard)."""
    s = "2026-11-23"
    d = lambda k: (date.fromisoformat(s) + timedelta(days=k)).isoformat()  # noqa: E731
    return _week(s, {
        d(0): [_s("technique_focus_gym", gym=BKL)],
        d(1): [_s("boulder_circuit_gym")],
        d(2): [_s("limit_boulder_gym")],
        d(3): [_s("route_endurance_gym")],
        d(5): [_s("route_projecting_gym")],
        d(6): [_s("boulder_circuit_gym")],
    })


CUSTOM_LUNCH = {
    "name": "Work — gambe con back squat + piedi (scarico)", "slot": "lunch", "tags": {"hard": False, "finger": False},
    "gym_id": WORK, "status": "planned", "explain": ["user-added custom session", "custom_session_id=cs_5853e508"],
    "location": "gym", "intensity": "medium", "is_custom": True, "session_id": "custom_cs_5853e508",
    "session_mode": "custom_build", "custom_session_id": "cs_5853e508", "constraints_applied": ["custom_add"],
    "target_duration_min": 42, "estimated_load_score": 38,
    "exercises": [{"exercise_id": "back_squat", "sets": 4, "reps": 6, "load_kg": 70.0}],
}


def _cached_deload_week():
    """The cached plan of 2026-11-30 (rev. 6, generated 2026-11-04 by the pre-A328 code)."""
    return _week(WS, {
        MON: [_s("arms_shoulders_handstand_lunch", slot="lunch", gym=WORK), _s("easy_climbing_deload", gym=BKL)],
        TUE: [copy.deepcopy(CUSTOM_LUNCH), _s("flexibility_full")],
        WED: [_s("treadmill_zone2_cardio", slot="lunch", gym=WORK), _s("prehab_maintenance")],
        THU: [_s("treadmill_zone2_cardio", slot="lunch", gym=WORK), _s("regeneration_easy")],
        FRI: [_s("upper_push_arms_lunch", slot="lunch", gym=WORK)],
        SAT: [_s("deload_recovery")],
    }, plan_revision=6, profile_snapshot={"phase_id": "deload", "session_pool": list(SAVED_POOL),
                                         "intensity_cap": "low"},
        adaptations=[
            {"type": "event", "event": {"date": TUE, "slot": "lunch", "event_type": "remove_session",
                                        "session_ref": "legs_maintenance_lunch", "removed_slot": "lunch",
                                        "removed_owned": False}},
            {"type": "event", "event": {"slot": "lunch", "gym_id": WORK, "location": "gym",
                                        "event_type": "add_custom_session", "target_date": TUE,
                                        "custom_session_id": "cs_5853e508"}},
        ])


def _router_kwargs(**over):
    """generate_phase_week as GET /api/week calls it for Daniele's week 13."""
    kw = dict(
        phase_id="deload", domain_weights=dict(SAVED_WEIGHTS), session_pool=list(SAVED_POOL), start_date=WS,
        availability=_avail(), hard_cap_per_week=5, planning_prefs=copy.deepcopy(PREFS),
        default_gym_id=COCQUE, gyms=copy.deepcopy(GYMS), intensity_cap="low", pretrip_dates=None,
        is_last_week_of_phase=True, allowed_locations=allowed_locations_for(EQUIPMENT),
        home_equipment=list(HOME), today=None, prev_week_plan=_prev_week(),
        existing_week_plan=_cached_deload_week(), trip_start_dates=[], next_week_plan=None,
        deload_finger_exposure=True,
    )
    kw.update(over)
    return kw


def _regenerate(**over):
    kw = _router_kwargs(**over)
    fresh = generate_phase_week(**kw)
    return regenerate_preserving_completed(copy.deepcopy(kw["existing_week_plan"]), fresh, preserve_before=kw["today"])


def _day(plan, d_iso):
    return next(d for d in plan["weeks"][0]["days"] if d["date"] == d_iso)


def _evening(plan, d_iso):
    return next((s for s in _day(plan, d_iso)["sessions"] if s.get("slot") == "evening"), None)


def _all(plan):
    return [(d["date"], s) for d in plan["weeks"][0]["days"] for s in d["sessions"]]


def _training_days(plan):
    return {d for d, s in _all(plan) if s.get("slot") != "lunch"}


def _climbing_days(plan):
    """Days with a climbing session of the engine (a deload filler included)."""
    out = set()
    for d, s in _all(plan):
        sid = s.get("session_id")
        if (_SESSION_META.get(sid) or {}).get("climbing") or sid == "regeneration_easy":
            out.add(d)
    return out


# ---------------------------------------------------------------------------
# 1. Daniele's week of 2026-11-30 (mirror shapes)
# ---------------------------------------------------------------------------

class TestDanieleMirrorWeek:
    def test_the_shape_of_the_week(self):
        plan = _regenerate()
        ev = {d: (_evening(plan, d) or {}).get("session_id") for d in DAYS}
        # Six climbing evenings, as in his performance weeks (Friday has none).
        assert ev[FRI] is None
        assert all(ev[d] for d in DAYS if d != FRI)
        # The finger exposure on the first valid day (>= 48 h after Saturday's
        # project), at Bkl (hangboard); the technique session where the boulder is.
        assert ev[MON] == DELOAD_FINGER_SESSION and _evening(plan, MON)["gym_id"] == BKL
        assert ev[TUE] == DELOAD_TECHNIQUE_SESSION
        assert {ev[d] for d in (WED, THU, SAT, SUN)} <= {sid for sid, _n in DELOAD_FILLERS}
        assert sum(1 for v in ev.values() if v == DELOAD_FINGER_SESSION) == 1
        assert sum(1 for v in ev.values() if v == DELOAD_TECHNIQUE_SESSION) == 1

    def test_his_custom_lunch_and_his_removal_survive(self):
        plan = _regenerate()
        tue = _day(plan, TUE)["sessions"]
        assert [s for s in tue if s.get("session_id") == "custom_cs_5853e508"] == [CUSTOM_LUNCH]
        assert not any(s.get("session_id") == "legs_maintenance_lunch" for s in tue)
        lunches = [s for _d, s in _all(plan) if s.get("slot") == "lunch"]
        assert lunches and all(not (s.get("tags") or {}).get("hard") for s in lunches)

    def test_no_hard_no_pe_no_test_no_pull(self):
        plan = _regenerate()
        for _d, s in _all(plan):
            sid = s["session_id"]
            assert not (s.get("tags") or {}).get("hard"), sid
            assert sid not in ("power_endurance_gym", "limit_boulder_gym", "power_contact_gym",
                               "strength_long", "finger_strength_home", "pulling_strength_gym"), sid
            assert not sid.startswith("test_"), sid
            assert not (_SESSION_META.get(sid) or {}).get("pulling"), sid
        assert plan["weeks"][0]["targets"] == {"hard_days": 0, "finger_days": 1}
        assert plan["weekly_load_summary"]["hard_days_count"] == 0
        assert plan["unmet_stimulus"] == []

    def test_the_saved_old_pool_and_low_cap_are_reached(self):
        """The macrocycle keeps its pre-A328 pool and cap: the form comes from code."""
        plan = generate_phase_week(**_router_kwargs())
        snap = plan["profile_snapshot"]
        assert snap["intensity_cap"] == "low"
        assert snap["session_pool"][:4] == [DELOAD_FINGER_SESSION, DELOAD_TECHNIQUE_SESSION,
                                            "easy_climbing_deload", "regeneration_easy"]
        assert set(SAVED_POOL) <= set(snap["session_pool"])
        # finger_aerobic_base leaves the fillers when the finger exposure is there.
        assert not any(s["session_id"] == "finger_aerobic_base" for _d, s in _all(plan))

    def test_deterministic(self):
        a = generate_phase_week(**_router_kwargs())
        b = generate_phase_week(**_router_kwargs())
        a.pop("generated_at"), b.pop("generated_at")
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ---------------------------------------------------------------------------
# 2. The finger exposure: who, where, when
# ---------------------------------------------------------------------------

class TestFingerExposure:
    def test_untested_athlete_gets_none(self):
        plan = generate_phase_week(**_router_kwargs(deload_finger_exposure=False))
        assert not any(s["session_id"] == DELOAD_FINGER_SESSION for _d, s in _all(plan))
        assert not any((s.get("tags") or {}).get("finger") for _d, s in _all(plan)
                       if s["session_id"] != "finger_aerobic_base")
        assert plan["weeks"][0]["targets"]["finger_days"] in (0, 1)  # finger_aerobic_base may stay
        assert plan["unmet_stimulus"] == []
        # Same climbing days anyway: the technique session and the fillers.
        assert _climbing_days(plan) == set(DAYS) - {FRI}

    def test_never_hard_never_max(self):
        meta = _SESSION_META[DELOAD_FINGER_SESSION]
        assert (meta["hard"], meta["finger"], meta["intensity"]) == (False, True, "medium")
        assert set(DELOAD_ABOVE_CAP) == {DELOAD_FINGER_SESSION, DELOAD_TECHNIQUE_SESSION}

    def test_48h_after_a_finger_day_of_the_previous_week(self):
        prev = _prev_week()
        _day(prev, "2026-11-29")["sessions"] = [_s("limit_boulder_gym")]  # Sunday finger-hard
        plan = generate_phase_week(**_router_kwargs(prev_week_plan=prev))
        touch = [d for d, s in _all(plan) if s["session_id"] == DELOAD_FINGER_SESSION]
        assert touch == [TUE]

    def test_never_in_the_last_days_of_the_week(self):
        av = _avail()
        for wd in ("mon", "tue", "wed", "thu"):
            av[wd]["evening"]["available"] = False
        plan = generate_phase_week(**_router_kwargs(availability=av))
        assert not any(s["session_id"] == DELOAD_FINGER_SESSION for _d, s in _all(plan))
        assert DELOAD_TOUCH_LAST_DAYS == 3
        # A tested athlete whose exposure fits nowhere is told so (never silent).
        rows = [u for u in plan["unmet_stimulus"] if u["phase_id"] == "deload"]
        assert [u["stimulus"] for u in rows] == ["finger_strength"]

    def test_not_next_to_a_finger_session_of_the_user(self):
        existing = _cached_deload_week()
        _day(existing, MON)["sessions"].append(dict(_s("finger_strength_home", slot="morning", gym=None),
                                                    is_custom=True, status="planned"))
        plan = generate_phase_week(**_router_kwargs(existing_week_plan=existing))
        touch = [d for d, s in _all(plan) if s["session_id"] == DELOAD_FINGER_SESSION]
        assert touch == [WED]

    def test_at_home_on_a_home_evening(self):
        av = _avail()
        av["mon"]["evening"].update({"available": False})
        av["tue"]["evening"] = _slot(True, None, "primary", loc="home")
        plan = generate_phase_week(**_router_kwargs(availability=av, existing_week_plan=None))
        touch = [(d, s["location"], s["gym_id"]) for d, s in _all(plan) if s["session_id"] == DELOAD_FINGER_SESSION]
        assert touch == [(TUE, "home", None)]


# ---------------------------------------------------------------------------
# 3. Same climbing days as a normal week; technique; fillers
# ---------------------------------------------------------------------------

def _generic_kwargs(phase, **over):
    profile = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45, "technique": 50, "endurance": 40}
    kw = dict(
        phase_id=phase, domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[phase], profile),
        session_pool=_build_session_pool(phase), start_date="2026-03-02",
        availability={d: {"evening": {"available": True, "locations": ["gym", "home"]}}
                      for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        allowed_locations=["home", "gym"], hard_cap_per_week=3, default_gym_id="blocx",
        gyms=[{"gym_id": "blocx", "equipment": ["spraywall", "board_kilter", "hangboard", "gym_boulder",
                                                "gym_routes", "dumbbell", "pullup_bar"]}],
        home_equipment=["hangboard", "pullup_bar"],
    )
    kw.update(over)
    return kw


class TestSameClimbingDays:
    @pytest.mark.parametrize("target", [3, 4, 5, 6, 7])
    @pytest.mark.parametrize("exposure", [False, True])
    def test_climbing_days_as_a_normal_week(self, target, exposure):
        prefs = {"target_training_days_per_week": target, "hard_day_cap_per_week": 3}
        normal = generate_phase_week(**_generic_kwargs("performance", planning_prefs=dict(prefs)))
        deload = generate_phase_week(**_generic_kwargs("deload", planning_prefs=dict(prefs)),
                                     deload_finger_exposure=exposure)
        # The deload trains on the very days of the normal week, and climbs on
        # every one of them (the normal week may hang at home on one).
        assert _training_days(deload) == _training_days(normal)
        assert len(_training_days(deload)) == target
        assert _climbing_days(deload) == _training_days(deload)
        sids = [s["session_id"] for _d, s in _all(deload)]
        assert sids.count(DELOAD_TECHNIQUE_SESSION) == 1
        assert sids.count(DELOAD_FINGER_SESSION) == (1 if exposure else 0)
        for sid, limit in DELOAD_FILLERS:
            assert sids.count(sid) <= limit
        assert deload["weeks"][0]["targets"] == {"hard_days": 0, "finger_days": 1 if exposure else 0}

    def test_other_phases_untouched_by_the_flag(self):
        for phase in ("base", "strength_power", "power_endurance", "performance"):
            a = generate_phase_week(**_generic_kwargs(phase, planning_prefs={"target_training_days_per_week": 5}))
            b = generate_phase_week(**_generic_kwargs(phase, planning_prefs={"target_training_days_per_week": 5}),
                                    deload_finger_exposure=True)
            a.pop("generated_at"), b.pop("generated_at")
            assert a == b, phase

    def test_apply_deload_week_has_no_session_cap(self):
        plan = _week(WS, {d: [_s("easy_climbing_deload")] for d in DAYS})
        plan["weeks"][0]["days"][0]["sessions"].append(_s("limit_boulder_gym", slot="lunch"))
        plan["weeks"][0]["days"][1]["sessions"].append(_s(DELOAD_FINGER_SESSION, slot="lunch"))
        out = apply_deload_week(plan)
        sids = [s["session_id"] for _d, s in _all(out)]
        assert sids.count("easy_climbing_deload") == 7 and "limit_boulder_gym" not in sids
        assert out["weeks"][0]["targets"] == {"hard_days": 0, "finger_days": 1}


# ---------------------------------------------------------------------------
# 4. The load: the previous phase's working load -10 %, >= 3 s in reserve
# ---------------------------------------------------------------------------

MC = {"start_date": "2026-09-07", "end_date": "2026-12-06", "phases": [
    {"phase_id": "base", "start_week": 1, "end_week": 2, "duration_weeks": 2},
    {"phase_id": "strength_power", "start_week": 3, "end_week": 6, "duration_weeks": 4},
    {"phase_id": "power_endurance", "start_week": 7, "end_week": 9, "duration_weeks": 3},
    {"phase_id": "performance", "start_week": 10, "end_week": 12, "duration_weeks": 3},
    {"phase_id": "deload", "start_week": 13, "end_week": 13, "duration_weeks": 1}]}


def _tested_state():
    """Daniele's numbers: max hang 7" 116 kg (test 24/09), bw 78, working load
    107 kg written in power endurance on 02/11."""
    return {
        "bodyweight_kg": 78, "body": {"weight_kg": 78}, "macrocycle": copy.deepcopy(MC),
        "tests": {"max_strength": [{"date": "2026-09-24", "setup": {"hang_seconds": 7},
                                    "test_id": "max_hang_7s_total_load", "exercise_id": "max_hang_7s",
                                    "bodyweight_kg": 76.0, "total_load_kg": 116.0, "external_load_kg": 40.0}]},
        "baselines": {"hangboard": [{"grip": "half_crimp", "source": "test", "edge_mm": 20,
                                     "updated_at": "2026-09-24", "hang_seconds": 7, "max_total_load_kg": 116.0}]},
        "assessment": {"tests_source": {"max_hang_20mm_7s_total_kg": "measured"}},
        "working_loads": {"entries": [{
            "key": "max_hang_7s", "setup": {"grip": None, "edge_mm": None, "load_method": None}, "anchored": True,
            "updated_at": "2026-11-02", "exercise_id": "max_hang_7s", "phase_id_at_log": "power_endurance",
            "intensity_at_log": "hard", "last_work_seconds": 7.0, "last_total_load_kg": 103.0,
            "next_total_load_kg": 107.0, "next_external_load_kg": 29.0,
            "escalation_anchor": {"date": "2026-11-02", "total_kg": 103.0}}]},
    }


class TestDeloadLoad:
    def test_daniele_99_kg(self):
        st = _tested_state()
        perf = al.anchored_load(st, "max_hang_7s", date="2026-12-01", phase_id="performance", intensity="hard", sets=3)
        dl = al.anchored_load(st, "max_hang_7s", date="2026-12-01", sets=3)
        assert perf["total"] == 110.0  # the performance cap (0.95 x 116)
        assert (dl["total"], dl["external"], dl["phase_id"]) == (99.0, 21.0, "deload")
        assert dl["total"] == al.round_half(perf["total"] * DELOAD_LOAD_FACTOR)
        assert dl["pct_of_official"] == 0.853
        assert dl["deload"] == {"factor": 0.9, "from_phase": "performance", "from_total": 110.0, "from_clamped": "cap"}
        assert dl["clamped"] is None and "ceiling_note" not in dl
        assert al.anchor_summary(dl)["deload"]["from_phase"] == "performance"

    def test_within_the_three_second_reserve(self):
        st = _tested_state()
        dl = al.anchored_load(st, "max_hang_7s", date="2026-12-01", sets=3)
        hold_cap = al.floor_half(116.0 / (1 + al.rp.HANG_PCT_PER_S * al.RESERVE_S))
        assert dl["total"] <= dl["cap"] <= hold_cap
        # The old deload cap (0.70 x max = 81 kg) no longer applies to hangs.
        assert dl["total"] > al.HANG_PHASE_CAP["deload"] * 116.0

    def test_cold_target_without_working_load(self):
        st = _tested_state()
        st["working_loads"]["entries"] = []
        perf = al.anchored_load(st, "max_hang_7s", date="2026-12-01", phase_id="performance", intensity="hard", sets=3)
        dl = al.anchored_load(st, "max_hang_7s", date="2026-12-01", sets=3)
        assert perf["source"] == "phase_target" and dl["source"] == "phase_target"
        assert dl["total"] == al.round_half(perf["total"] * DELOAD_LOAD_FACTOR)

    def test_pain_cut_is_kept(self):
        st = _tested_state()
        st["progression_counters"] = {"pain_blocks": {"fingers": {"from": "2026-11-29", "until": "2026-12-06",
                                                                  "score": 2}}}
        dl = al.anchored_load(st, "max_hang_7s", date="2026-12-01", sets=3)
        clean = al.anchored_load(_tested_state(), "max_hang_7s", date="2026-12-01", sets=3)
        assert dl["pain"]["score"] == 2 and dl["total"] < clean["total"]

    def test_untested_none(self):
        st = _tested_state()
        st["tests"] = {}
        st["baselines"] = {}
        assert al.anchored_load(st, "max_hang_7s", date="2026-12-01", sets=3) is None

    def test_pulls_unchanged_in_the_deload(self):
        """Weighted pull-ups stay out of the deload form (Daniele, 2026-11-13);
        their read path in a deload is the pre-A328 one."""
        st = _tested_state()
        st["tests"]["pulling_strength"] = [{"date": "2026-09-24", "test_id": "weighted_pullup_2rm",
                                            "exercise_id": "weighted_pullup", "bodyweight_kg": 78.0,
                                            "estimated_1rm_kg": 128.9, "total_load_2rm_kg": 123.0}]
        a = al.anchored_load(st, "weighted_pullup", date="2026-12-01", sets=4, reps=3)
        assert a is not None and a["phase_id"] == "deload" and "deload" not in a
        assert a["total"] <= al.floor_half(al._pulling_pct("deload", "hard") * a["official"]["one_rm"]) + 0.5

    def test_write_cap_of_other_hangs_ignores_the_old_deload_cap(self):
        st = _tested_state()
        assert al.hang_write_cap(st, 7, "2026-12-01") == al.hang_write_cap(st, 7, "2026-11-24") == 110.0

    def test_athlete_context_renders_the_deload_dose(self):
        from backend.engine import athlete_context as ac

        row = ac._anchors(_tested_state(), date(2026, 12, 1))["exercises"]["max_hang_7s"]
        assert (row["total"], row["phase_id"], row["deload"]["from_phase"]) == (99.0, "deload", "performance")
        line = ac._anchor_line("max_hang_7s", row)
        assert "deload: 110 kg di performance −10 %, feedback congelato" in line

    def test_source_phase(self):
        assert al.deload_source_phase(_tested_state()) == "performance"
        assert al.deload_source_phase({}) == "performance"
        st = _tested_state()
        st["macrocycle"]["phases"] = [p for p in st["macrocycle"]["phases"] if p["phase_id"] != "performance"]
        assert al.deload_source_phase(st) == "power_endurance"


class TestDeloadFeedbackFrozen:
    def _apply(self, st, d, label, used=99.0):
        item = {"exercise_id": "max_hang_7s", "completed": True, "completed_sets": 3, "prescribed_sets": 3,
                "used_total_load_kg": used, "feedback_label": label, "hang_held_s": 12.0}
        return al.apply_anchored_feedback(st, item, feedback_label=label, date_value=d,
                                          planned_session={"session_id": DELOAD_FINGER_SESSION,
                                                           "intensity": "medium"},
                                          planned_prescription={"sets": 3, "work_seconds": 7}, setup_source={})

    def test_the_working_load_never_moves_in_the_deload(self):
        for label in ("very_easy", "easy", "ok", None, "hard", "very_hard"):
            st = _tested_state()
            before = copy.deepcopy(st["working_loads"])
            assert self._apply(st, "2026-12-01", label) is True
            assert st["working_loads"] == before, label
            hard = ((st.get("progression_counters") or {}).get("hard_labels") or {}).get("finger") or []
            assert (hard == ["2026-12-01"]) is (label in ("hard", "very_hard")), label
            assert not ((st.get("progression_counters") or {}).get("retest_signals"))

    def test_outside_the_deload_it_moves(self):
        st = _tested_state()
        self._apply(st, "2026-11-24", "easy", used=105.0)
        entry = st["working_loads"]["entries"][0]
        assert entry["updated_at"] == "2026-11-24" and entry["phase_id_at_log"] == "performance"


# ---------------------------------------------------------------------------
# 5. Sets x 0.5 (A312 factor form) and the order of the exercises
# ---------------------------------------------------------------------------

class TestHalfSets:
    @pytest.mark.parametrize("sets,expected", [(1, 1), (2, 1), (3, 2), (4, 2), (6, 3)])
    def test_factor(self, sets, expected):
        from backend.engine.resolve_session import _apply_deload_sets

        out = _apply_deload_sets({"sets": sets, "deload_sets": 0.5}, user_state=_tested_state(),
                                 target_date="2026-12-01")
        assert out["sets"] == expected and "deload_sets" not in out
        if expected != sets:
            assert out["stored_sets"] == sets and out["deload_sets_applied"] is True
        same = _apply_deload_sets({"sets": sets, "deload_sets": 0.5}, user_state=_tested_state(),
                                  target_date="2026-11-24")
        assert same == {"sets": sets}

    def test_integer_keeps_its_a312_meaning(self):
        from backend.engine.resolve_session import _apply_deload_sets

        out = _apply_deload_sets({"sets": 3, "deload_sets": 2}, user_state=_tested_state(), target_date="2026-12-01")
        assert out["sets"] == 2

    def test_technique_drills_declare_the_factor(self):
        path = "backend/catalog/sessions/v1/technique_focus_gym.json"
        from pathlib import Path

        cat = json.loads((Path(__file__).resolve().parents[2] / path).read_text())
        drills = [m for m in cat["modules"] if str(m.get("block_id", "")).startswith("technique_drill_")]
        assert len(drills) == 3
        assert all(m["selection"]["primary"]["prescription_overrides"] == {"deload_sets": 0.5} for m in drills)

    def test_max_hangs_right_after_the_warm_up(self):
        from backend.engine.exercise_ordering import enforce_ordering_constraints, sort_exercises_by_phase

        exercises = [
            {"exercise_id": "regeneration_climbing", "role": "main", "domain": "regeneration"},
            {"exercise_id": "reverse_wrist_curl", "role": "prehab", "domain": "prehab_wrist"},
            {"exercise_id": "max_hang_7s", "role": "main", "domain": "finger_max_strength"},
            {"exercise_id": "finger_recruitment_pulls", "role": "warmup", "domain": "finger_strength"},
        ]
        out = enforce_ordering_constraints(sort_exercises_by_phase(exercises, "deload"), "deload")
        assert [e["exercise_id"] for e in out][:2] == ["finger_recruitment_pulls", "max_hang_7s"]


# ---------------------------------------------------------------------------
# 6. Past and user-owned sessions through a regeneration (CLAUDE.md invariant)
# ---------------------------------------------------------------------------

class TestPastAndUserSessionsIntact:
    def test_mid_week_regeneration_keeps_lived_days_and_user_sessions(self):
        existing = _cached_deload_week()
        done = dict(_s("easy_climbing_deload", gym=BKL), status="done",
                    feedback={"label": "ok"}, completed_at="2026-11-30T20:00:00")
        _day(existing, MON)["sessions"][1] = done
        skipped = dict(_s("flexibility_full"), status="skipped")
        _day(existing, TUE)["sessions"][1] = skipped
        before = copy.deepcopy(existing)
        kw = _router_kwargs(existing_week_plan=existing, today=WED)
        fresh = generate_phase_week(**kw)
        merged = regenerate_preserving_completed(copy.deepcopy(existing), fresh, preserve_before=WED)
        assert _day(merged, MON) == _day(before, MON)
        assert _day(merged, TUE) == _day(before, TUE)
        assert existing == before  # the input is never written
        # The finger exposure lands from today on, never on a lived day.
        touch = [d for d, s in _all(merged) if s["session_id"] == DELOAD_FINGER_SESSION]
        assert touch and all(d >= WED for d in touch)

    def test_custom_lunch_byte_identical_through_force(self):
        merged = _regenerate()
        assert _day(merged, TUE)["sessions"][0] == CUSTOM_LUNCH


# ---------------------------------------------------------------------------
# 7. Catalog and key rows
# ---------------------------------------------------------------------------

class TestCatalog:
    def test_session_catalog(self):
        from pathlib import Path

        cat = json.loads((Path(__file__).resolve().parents[2]
                          / "backend/catalog/sessions/v1/deload_finger_touch.json").read_text())
        main = next(m for m in cat["modules"] if m.get("block_id") == "deload_max_hang")
        rx = main["selection"]["primary"]["prescription_overrides"]
        assert main["selection"]["primary"]["exercise_id"] == "max_hang_7s"
        assert (rx["sets"], rx["work_seconds"]) == (3, 7)
        assert cat["required_equipment"] == _SESSION_META[DELOAD_FINGER_SESSION]["required_equipment"]
        # No pulling block: weighted pull-ups stay out of the deload (Daniele, 2026-11-13).
        assert not any("pull" in str(m.get("block_id", "")) for m in cat["modules"])

    def test_stimulus_and_key_row(self):
        from backend.engine import key_sessions_v1 as ks
        from backend.engine.stimulus import FAMILY_FINGER_MAX, session_stimuli

        assert session_stimuli({"session_id": DELOAD_FINGER_SESSION}) == [FAMILY_FINGER_MAX]
        rows = {r["key"]: r for r in ks.phase_requirements("deload")}
        assert set(rows) == {"finger_maintenance", "technique"}
        assert all(r["max_severity"] == "info" for r in rows.values())
        assert ks.session_delivers(rows["finger_maintenance"], {"session_id": DELOAD_FINGER_SESSION},
                                   ks.load_exercise_catalog())
