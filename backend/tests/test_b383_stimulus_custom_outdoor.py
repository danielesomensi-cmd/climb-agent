"""B383 — custom sessions and crag days count in the weekly stimulus balance.

Daniele's decision (2026-10-17): most of his training is custom, and the A240
exclusion made the report say "No Endurance training in 124 days" for an
athlete who climbs routes at the crag every weekend. Custom / generated
sessions are now categorised from their exercises; a crag day the athlete
climbed counts (lead → endurance, boulder → boulder_power). Report-only and
read-only: the closed-loop writers are untouched.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

import pytest

from backend.engine import report_engine
from backend.engine.report_engine import (
    _build_stimulus_balance,
    _content_categories,
    _derived_last_done,
    exercise_stimulus_categories,
    generate_weekly_report,
)

WEEK_START = "2026-10-12"  # a Monday


def _cs(cs_id: str, name: str, exercise_ids: List[str]) -> Dict[str, Any]:
    return {"id": cs_id, "name": name, "tags": [],
            "exercises": [{"exercise_id": e, "sets": 3, "reps": 5} for e in exercise_ids]}


# Synthetic, Daniele-like: the custom sessions he really trains with.
CUSTOMS = [
    _cs("cs_finger", "Dita max — trave", ["finger_warmup_generic", "hang_rampup_progressive", "max_hang_7s",
                                           "reverse_wrist_curl", "cooldown_forearm_wrist_stretch"]),
    _cs("cs_limit", "Limit boulder", ["warmup_easy_boulders", "no_readjust_drill", "limit_bouldering",
                                      "cooldown_forearm_wrist_stretch"]),
    _cs("cs_4x4", "4x4 norvegese", ["easy_run_zone2", "treadmill_hiit_4x4", "treadmill_incline_walk",
                                    "cooldown_hamstring_fold"]),
    _cs("cs_z2core", "Z2 + core", ["treadmill_incline_walk", "pallof_press", "copenhagen_plank"]),
    _cs("cs_rope", "Corda — soglia", ["threshold_climbing", "fall_practice"]),
    _cs("cs_push", "Spinta", ["general_pulse_raise", "dumbbell_bench_press", "pike_pushup"]),
    _cs("cs_warm", "Solo riscaldamento", ["general_pulse_raise", "finger_warmup_generic"]),
]


def _row(date: str, sid: str, status: str = "done") -> Dict[str, Any]:
    return {"date": date, "session_id": sid, "status": status}


def _state(scl=None, **overrides) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "planning_prefs": {"target_training_days_per_week": 4},
        "current_week_plan": {"weeks": [{"days": []}]},
        "week_plans": {},
        "feedback_log": [],
        "session_completion_log": scl or [],
        "custom_sessions": copy.deepcopy(CUSTOMS),
        "working_loads": {"entries": [], "rules": {}},
        "macrocycle": None,
        "goal": {"discipline": "lead"},
        "assessment": {},
        "outdoor_log": [],
    }
    base.update(overrides)
    return base


def _crag(date: str, routes: List[Dict[str, Any]], discipline: str = "lead") -> Dict[str, Any]:
    return {"date": date, "spot_name": "Berdorf", "discipline": discipline,
            "log_version": "outdoor.v2", "routes": routes}


def _route(grade: str, results=("sent",), discipline=None) -> Dict[str, Any]:
    r = {"name": "x", "grade": grade, "attempts": [{"result": x} for x in results]}
    if discipline:
        r["discipline"] = discipline
    return r


@pytest.fixture
def no_outdoor_store(tmp_path, monkeypatch):
    from backend.engine import storage
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    yield


# --------------------------------------------------------------------------- #
# exercise → category
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("eid, expected", [
    ("max_hang_7s", ("finger_strength",)),
    ("limit_bouldering", ("boulder_power", "finger_strength")),
    ("threshold_climbing", ("endurance",)),
    ("arc_training", ("endurance",)),
    ("weighted_pullup", ("complementaries",)),
    ("treadmill_hiit_4x4", ("complementaries",)),   # conditioning, like the catalog session
    ("treadmill_incline_walk", ("complementaries",)),
    ("dumbbell_bench_press", ("complementaries",)),
    ("general_pulse_raise", ()),                    # warm-up adds nothing
    ("finger_warmup_generic", ()),
    ("hang_rampup_progressive", ()),
    ("cooldown_forearm_wrist_stretch", ()),
    ("max_hang_10s", ("finger_strength",)),         # generic finger domain on loaded work
    ("active_finger_curls", ("complementaries",)),  # …but not on prehab curls
    ("not_an_exercise", ()),
])
def test_exercise_categories(eid, expected):
    assert exercise_stimulus_categories(eid) == expected


def test_session_takes_climbing_categories_over_accessories():
    assert _content_categories(["max_hang_7s", "reverse_wrist_curl", "pallof_press"]) == ["finger_strength"]
    assert _content_categories(["pallof_press", "dead_bug"]) == ["complementaries"]
    assert _content_categories(["general_pulse_raise"]) == []
    assert _content_categories([]) == []


# --------------------------------------------------------------------------- #
# completion log → last done
# --------------------------------------------------------------------------- #

def test_custom_rows_count_from_their_definition():
    last = _derived_last_done([
        _row("2026-10-05", "custom_cs_finger"),
        _row("2026-10-08", "custom_cs_limit"),
        _row("2026-10-06", "custom_cs_rope"),
        _row("2026-10-09", "custom_cs_z2core"),
    ], WEEK_START, state=_state())
    assert last == {"finger_strength": "2026-10-08", "boulder_power": "2026-10-08",
                    "endurance": "2026-10-06", "complementaries": "2026-10-09"}


def test_custom_4x4_is_complementaries_not_endurance():
    last = _derived_last_done([_row("2026-10-09", "custom_cs_4x4")], WEEK_START, state=_state())
    assert last == {"complementaries": "2026-10-09"}


def test_warmup_only_or_unknown_custom_counts_nowhere():
    last = _derived_last_done([
        _row("2026-10-09", "custom_cs_warm"),
        _row("2026-10-09", "custom_cs_deleted"),
        _row("2026-10-09", "generated_hiit_2026-10-09_lunch"),
    ], WEEK_START, state=_state())
    assert last == {}


def test_plan_copy_beats_definition():
    """What was logged on the day wins over a definition edited later."""
    plan = {"start_date": "2026-10-05", "weeks": [{"days": [{"date": "2026-10-07", "sessions": [{
        "session_id": "custom_cs_push", "is_custom": True, "status": "done",
        "exercises": [{"exercise_id": "max_hang_7s"}],
        "actual_exercises": [{"exercise_id": "max_hang_7s", "completed_sets": 3}],
    }]}]}]}
    st = _state(week_plans={"2026-10-05": plan})
    last = _derived_last_done([_row("2026-10-07", "custom_cs_push")], WEEK_START, state=st)
    assert last == {"finger_strength": "2026-10-07"}


def test_generated_session_counts_from_plan_exercises():
    plan = {"start_date": "2026-10-05", "weeks": [{"days": [{"date": "2026-10-07", "sessions": [{
        "session_id": "generated_adhoc_2026-10-07_evening", "status": "done",
        "exercises": [{"exercise_id": "limit_bouldering"}],
    }]}]}]}
    st = _state(week_plans={"2026-10-05": plan})
    last = _derived_last_done([_row("2026-10-07", "generated_adhoc_2026-10-07_evening")], WEEK_START, state=st)
    assert last["boulder_power"] == "2026-10-07"


def test_skipped_custom_does_not_count():
    last = _derived_last_done([_row("2026-10-08", "custom_cs_limit", "skipped")], WEEK_START, state=_state())
    assert last == {}


# --------------------------------------------------------------------------- #
# crag days
# --------------------------------------------------------------------------- #

def test_lead_crag_day_counts_as_endurance_not_finger_strength():
    rows = [_crag("2026-10-11", [_route("6b+"), _route("7c+", ("topped_out", "fell"))])]
    last = _derived_last_done([], WEEK_START, state=_state(), outdoor_rows=rows)
    assert last == {"endurance": "2026-10-11"}


def test_boulder_crag_day_counts_as_boulder_power():
    rows = [_crag("2026-10-04", [_route("7A", ("fell",))], discipline="boulder")]
    last = _derived_last_done([], WEEK_START, state=_state(), outdoor_rows=rows)
    assert last == {"boulder_power": "2026-10-04"}


def test_mixed_crag_day_uses_route_discipline():
    rows = [_crag("2026-10-04", [_route("6c"), _route("7A", discipline="boulder")], discipline="both")]
    last = _derived_last_done([], WEEK_START, state=_state(), outdoor_rows=rows)
    assert last == {"endurance": "2026-10-04", "boulder_power": "2026-10-04"}


def test_route_with_empty_attempts_does_not_count():
    rows = [_crag("2026-10-04", [{"name": "x", "grade": "7a", "attempts": []}])]
    assert _derived_last_done([], WEEK_START, state=_state(), outdoor_rows=rows) == {}


def test_legacy_state_outdoor_log_counts():
    st = _state(outdoor_log=[_crag("2026-09-30", [_route("7a")])])
    assert _derived_last_done([], WEEK_START, state=st) == {"endurance": "2026-09-30"}


def test_done_plan_crag_day_without_log_counts_planned_does_not():
    plan = {"start_date": "2026-10-05", "weeks": [{"days": [
        {"date": "2026-10-10", "sessions": [], "outdoor_spot_name": "Berdorf", "outdoor_session_status": "done"},
        {"date": "2026-10-11", "sessions": [], "outdoor_spot_name": "Berdorf", "outdoor_session_status": "planned",
         "outdoor_plan": {"discipline": "boulder"}},
    ]}]}
    st = _state(week_plans={"2026-10-05": plan})
    assert _derived_last_done([], WEEK_START, state=st) == {"endurance": "2026-10-10"}


def test_crag_day_inside_or_after_week_is_not_before_it():
    rows = [_crag("2026-10-12", [_route("7a")]), _crag("2026-10-20", [_route("7a")])]
    assert _derived_last_done([], WEEK_START, state=_state(), outdoor_rows=rows) == {}


# --------------------------------------------------------------------------- #
# sessions this week
# --------------------------------------------------------------------------- #

def test_this_week_counts_customs_and_crag_days():
    plan = {"weeks": [{"days": [
        {"date": "2026-10-13", "sessions": [
            {"session_id": "custom_cs_z2core", "is_custom": True, "status": "done", "custom_session_id": "cs_z2core"},
        ]},
        {"date": "2026-10-14", "sessions": [
            {"session_id": "custom_cs_limit", "is_custom": True, "status": "done"},
            {"session_id": "strength_long", "status": "done"},
        ]},
        {"date": "2026-10-15", "sessions": [
            {"session_id": "custom_cs_finger", "is_custom": True, "status": "skipped"},
        ]},
        {"date": "2026-10-17", "sessions": [], "outdoor_session_status": "done", "outdoor_spot_name": "Berdorf"},
    ]}]}
    rows = [_crag("2026-10-18", [_route("7a")])]
    sb = _build_stimulus_balance(plan, [], WEEK_START, state=_state(), outdoor_rows=rows)
    assert sb["complementaries"]["sessions_this_week"] == 1
    assert sb["boulder_power"]["sessions_this_week"] == 1
    assert sb["finger_strength"]["sessions_this_week"] == 2   # limit custom + strength_long
    assert sb["endurance"]["sessions_this_week"] == 2         # two crag days (plan done + log)


def test_same_crag_day_logged_and_done_on_plan_counts_once():
    plan = {"weeks": [{"days": [
        {"date": "2026-10-17", "sessions": [], "outdoor_session_status": "done", "outdoor_spot_name": "Berdorf"},
    ]}]}
    rows = [_crag("2026-10-17", [_route("7a"), _route("6b")])]
    sb = _build_stimulus_balance(plan, [], WEEK_START, state=_state(), outdoor_rows=rows)
    assert sb["endurance"]["sessions_this_week"] == 1


# --------------------------------------------------------------------------- #
# end to end — the report Daniele reads
# --------------------------------------------------------------------------- #

def _daniele_like() -> Dict[str, Any]:
    scl = [
        _row("2026-06-10", "route_endurance_gym"),   # last catalog endurance session
        _row("2026-07-30", "limit_boulder_gym"),
        _row("2026-09-24", "strength_long"),
        _row("2026-10-05", "custom_cs_finger"),
        _row("2026-10-08", "custom_cs_limit"),
        _row("2026-10-09", "custom_cs_z2core"),
    ]
    st = _state(scl)
    st["outdoor_log"] = [_crag("2026-10-10", [_route("6b"), _route("7c+", ("topped_out",))]),
                         _crag("2026-10-11", [_route("7c+", ("fell",))])]
    return st


def test_report_no_longer_claims_months_without_endurance(no_outdoor_store):
    rep = generate_weekly_report(_daniele_like(), None, WEEK_START)
    sb = rep["stimulus_balance"]
    assert sb["endurance"]["last_done_date"] == "2026-10-11"
    assert sb["endurance"]["days_since_last"] == 1
    assert sb["boulder_power"]["last_done_date"] == "2026-10-08"
    assert sb["finger_strength"]["last_done_date"] == "2026-10-08"
    assert not [h for h in rep["highlights"] if h["key"].startswith("stimulus_gap_")]


def test_report_reads_outdoor_logs_before_the_week(no_outdoor_store, monkeypatch):
    rows = [_crag("2026-10-03", [_route("7a")]), _crag("2026-10-14", [_route("7b")])]
    monkeypatch.setattr(report_engine, "load_outdoor_sessions", lambda user_id, since_date=None: rows)
    st = _state([])
    rep = generate_weekly_report(st, None, WEEK_START)
    assert rep["stimulus_balance"]["endurance"]["last_done_date"] == "2026-10-03"
    assert rep["stimulus_balance"]["endurance"]["sessions_this_week"] == 1
    # The week's own outdoor section still reads only the week.
    assert rep["outdoor"]["sessions"] == 1


def test_deterministic_and_read_only(no_outdoor_store):
    st = _daniele_like()
    before = copy.deepcopy(st)
    a = generate_weekly_report(st, None, WEEK_START)["stimulus_balance"]
    b = generate_weekly_report(st, None, WEEK_START)["stimulus_balance"]
    assert a == b
    assert st == before
