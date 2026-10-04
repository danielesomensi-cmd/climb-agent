"""A288 (F0) — the single stimulus-family table and the exposure views."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.engine import stimulus as st

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"


def _catalog():
    d = json.loads(CATALOG.read_text())
    items = d if isinstance(d, list) else d.get("exercises")
    return {e["id"]: e for e in items}


def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


# ---------------------------------------------------------------------------
# Family table vs catalog
# ---------------------------------------------------------------------------

def test_every_family_exercise_exists_in_catalog():
    cat = _catalog()
    missing = sorted(eid for eid in st.EXERCISE_FAMILY if eid not in cat)
    assert missing == []


def test_family_table_matches_catalog_rule():
    """The table is the catalog rule written out. A catalog edit that moves an
    exercise in or out of a family must update the table (and be reviewed)."""
    cat = _catalog()
    expected = {}
    for eid, e in cat.items():
        pats = _as_list(e.get("pattern"))
        doms = _as_list(e.get("domain"))
        edge = (e.get("attributes") or {}).get("edge_mm")
        if "finger_max_strength" in doms and edge is not None:
            expected[eid] = st.FAMILY_FINGER_MAX
        elif eid in ("weighted_pullup", "weighted_chinup"):
            expected[eid] = st.FAMILY_PULLING_MAX
        elif ("climbing_limit_boulder" in pats and "warmup" not in _as_list(e.get("role"))
              and eid != "warmup_easy_boulders"):
            expected[eid] = st.FAMILY_LIMIT_POWER
        elif "campus_ladder" in pats and eid != "campus_sprint_endurance":
            expected[eid] = st.FAMILY_LIMIT_POWER
        elif "power_endurance" in doms:
            expected[eid] = st.FAMILY_POWER_ENDURANCE
    assert st.EXERCISE_FAMILY == expected


def test_min_edge_hang_and_10s_hangs_are_not_finger_max():
    assert st.stimulus_of("min_edge_hang") is None
    assert st.stimulus_of("max_hang_10s") is None
    assert st.stimulus_of("lp_max_lift_10s") is None
    assert st.stimulus_of("max_hang_7s") == st.FAMILY_FINGER_MAX
    assert st.stimulus_of("weighted_chinup") == st.FAMILY_PULLING_MAX
    assert st.stimulus_of(None) is None
    assert st.stimulus_of("bench_press") is None


def test_fallback_session_ids_are_real_sessions():
    from backend.engine.planner_v2 import _SESSION_META

    assert set(st.SESSION_FALLBACK_STIMULI) <= set(_SESSION_META)


# ---------------------------------------------------------------------------
# Session exercise rule
# ---------------------------------------------------------------------------

def test_actual_wins_and_is_never_merged_with_planned():
    s = {
        "session_id": "custom_cs_x",
        "is_custom": True,
        "exercises": [{"exercise_id": "max_hang_7s"}, {"exercise_id": "weighted_pullup"}],
        "actual_exercises": [{"exercise_id": "weighted_pullup", "completed_sets": 4}],
    }
    entries, origin = st.session_exercise_entries(s)
    assert origin == "actual"
    assert [e["exercise_id"] for e in entries] == ["weighted_pullup"]
    assert st.session_stimuli(s) == [st.FAMILY_PULLING_MAX]


def test_resolved_instances_used_for_catalog_sessions():
    s = {"session_id": "strength_long", "exercises": [],
         "resolved": {"resolved_session": {"exercise_instances": [{"exercise_id": "horst_7_53"}]}}}
    entries, origin = st.session_exercise_entries(s)
    assert origin == "planned" and entries[0]["exercise_id"] == "horst_7_53"
    assert st.session_stimuli(s) == [st.FAMILY_FINGER_MAX]


def test_fallback_only_without_any_exercise_list():
    assert st.session_stimuli({"session_id": "strength_long"}) == [
        st.FAMILY_FINGER_MAX, st.FAMILY_PULLING_MAX]
    # with an exercise list, the session id adds nothing
    s = {"session_id": "strength_long", "exercises": [{"exercise_id": "bench_press"}]}
    assert st.session_stimuli(s) == []


@pytest.mark.parametrize("entry,player,counts", [
    ({"exercise_id": "max_hang_7s", "completed_sets": 1}, True, True),
    ({"exercise_id": "max_hang_7s", "completed_reps": 3}, True, True),
    # player pre-fills completed + load even for skipped exercises
    ({"exercise_id": "max_hang_7s", "completed": True, "used_external_load_kg": 30}, True, False),
    ({"exercise_id": "max_hang_7s", "completed": True, "used_total_load_kg": 116}, False, True),
    ({"exercise_id": "max_hang_7s", "completed": False, "completed_sets": 5}, False, False),
    ({"exercise_id": "max_hang_7s", "feedback_label": "skipped", "completed_sets": 5}, False, False),
    ({"exercise_id": "max_hang_7s"}, False, False),
])
def test_logged_entry_counts(entry, player, counts):
    assert st.logged_entry_counts(entry, player_session=player) is counts


# ---------------------------------------------------------------------------
# Exposure view
# ---------------------------------------------------------------------------

def _week(start, days):
    return {"start_date": start, "weeks": [{"days": [
        {"date": d, "sessions": sessions} for d, sessions in days
    ]}]}


def _state():
    return {
        "bodyweight_kg": 78.0,
        "performance": {"current_level": {
            "sport": {"worked": {"grade": "8a+"}},
            "boulder": {"worked": {"grade": "7C"}},
        }},
        "goal": {"discipline": "lead", "current_grade": "8a+"},
        "week_plans": {
            "2026-09-21": _week("2026-09-21", [
                ("2026-09-24", [
                    {"session_id": "test_max_hang_7s", "status": "done",
                     "tags": {"hard": True, "finger": True},
                     "actual_exercises": [{"exercise_id": "max_hang_7s", "completed_sets": 1,
                                           "used_total_load_kg": 116}]},
                    {"session_id": "test_max_weighted_pullup", "status": "done",
                     "actual_exercises": [{"exercise_id": "weighted_pullup", "completed_sets": 4,
                                           "used_total_load_kg": 123}]},
                ]),
            ]),
            "2026-09-28": _week("2026-09-28", [
                ("2026-10-04", [
                    {"session_id": "custom_cs_ab", "is_custom": True, "status": "done",
                     "tags": {"hard": True, "finger": False},
                     "exercises": [{"exercise_id": "weighted_pullup", "sets": 4, "load_kg": 30}],
                     "actual_exercises": [{"exercise_id": "weighted_pullup", "completed_sets": 4,
                                           "prescribed_sets": 4, "used_external_load_kg": 30}]},
                ]),
                ("2026-10-02", [
                    {"session_id": "strength_long", "status": "skipped",
                     "resolved": {"resolved_session": {"exercise_instances": [
                         {"exercise_id": "max_hang_7s"}]}}},
                ]),
            ]),
        },
        "free_sessions": [],
    }


def _archive():
    return {"2026-09-07": _week("2026-09-07", [
        ("2026-09-08", [{"session_id": "strength_long", "status": "done",
                         "resolved": {"resolved_session": {"exercise_instances": [
                             {"exercise_id": "max_hang_7s", "prescription": {"sets": 5}},
                             {"exercise_id": "weighted_pullup"}]}}}]),
        ("2026-09-10", [{"session_id": "finger_strength_home", "status": "done"}]),
    ])}


def test_exposures_hot_plus_archive_and_test_flag():
    rows = st.exposures(_state(), archived_weeks=_archive())
    got = [(r["date"], r["family"], r["exercise_id"], r["source"], r["evidence"], r["is_test"])
           for r in rows]
    assert got == [
        ("2026-09-08", "finger_max", "max_hang_7s", "archive", "planned", False),
        ("2026-09-08", "pulling_max", "weighted_pullup", "archive", "planned", False),
        ("2026-09-10", "finger_max", None, "archive", "planned", False),
        ("2026-09-24", "finger_max", "max_hang_7s", "week_plan", "measured", True),
        ("2026-09-24", "pulling_max", "weighted_pullup", "week_plan", "measured", True),
        ("2026-10-04", "pulling_max", "weighted_pullup", "week_plan", "measured", False),
    ]
    planned_hang = rows[0]
    assert planned_hang["sets_prescribed"] == 5 and planned_hang["sets_done"] is None
    assert rows[-1]["sets_done"] == 4 and rows[-1]["sets_prescribed"] == 4


def test_archive_row_shape_accepted_and_hot_wins():
    arch_rows = [{"week_start": k, "plan": v} for k, v in _archive().items()]
    assert st.exposures(_state(), archived_weeks=arch_rows) == st.exposures(
        _state(), archived_weeks=_archive())
    # the same week archived AND hot: hot copy only
    state = _state()
    stale = {"2026-09-21": _week("2026-09-21", [
        ("2026-09-22", [{"session_id": "strength_long", "status": "done"}])])}
    rows = st.exposures(state, archived_weeks=stale)
    assert all(r["date"] != "2026-09-22" for r in rows)


def test_skipped_and_planned_status_never_count():
    rows = st.exposures(_state())
    assert all(r["date"] != "2026-10-02" for r in rows)


def test_window_filters_and_family_filter():
    rows = st.exposures(_state(), archived_weeks=_archive(), since="2026-09-10",
                        until="2026-09-24", families=["finger_max"])
    assert [(r["date"], r["exercise_id"]) for r in rows] == [
        ("2026-09-10", None), ("2026-09-24", "max_hang_7s")]


def test_count_exposures_counts_distinct_days():
    state = _state()
    state["week_plans"]["2026-09-21"]["weeks"][0]["days"][0]["sessions"][0][
        "actual_exercises"].append({"exercise_id": "horst_7_53", "completed_sets": 3})
    assert st.count_exposures(state, "finger_max", since="2026-09-01", until="2026-10-31") == 1


def test_current_week_plan_read_when_not_in_week_plans():
    state = _state()
    state["current_week_plan"] = _week("2026-10-05", [
        ("2026-10-05", [{"session_id": "custom_x", "is_custom": True, "status": "done",
                         "actual_exercises": [{"exercise_id": "max_hang_7s", "completed_sets": 3}]}])])
    assert "2026-10-05" in st.exposure_dates(state, "finger_max")


def test_registry_merged_without_duplicates():
    state = _state()
    state["progression_counters"] = {"stimulus_exposures": {
        "pulling_max": ["2026-10-04", {"date": "2026-10-01", "exercise_id": "weighted_chinup"}],
        "unknown_family": ["2026-10-01"],
    }}
    rows = st.exposures(state, families=["pulling_max"])
    assert [(r["date"], r["source"]) for r in rows] == [
        ("2026-09-24", "week_plan"), ("2026-10-01", "registry"), ("2026-10-04", "week_plan")]


def test_free_boulder_limit_rule():
    state = _state()
    climbs = [{"grade": "7B"}, {"grade": "7B+"}, {"grade": "6C"}]
    state["free_sessions"] = [
        {"id": "f1", "date": "2026-10-06", "surface": "board_kilter", "climbs": climbs},
        {"id": "f2", "date": "2026-10-07", "surface": "gym_boulder", "climbs": climbs[1:]},
        {"id": "f3", "date": "2026-10-08", "surface": "gym_routes", "climbs": climbs},
    ]
    rows = st.exposures(state, families=["limit_power"])
    assert [(r["date"], r["session_id"], r["sets_done"]) for r in rows] == [("2026-10-06", "f1", 2)]
    # without a boulder redpoint nothing can be judged
    del state["performance"]["current_level"]["boulder"]
    assert st.exposures(state, families=["limit_power"]) == []


def test_exposures_deterministic_and_input_untouched():
    state = _state()
    snap = copy.deepcopy(state)
    a = st.exposures(state, archived_weeks=_archive())
    b = st.exposures(state, archived_weeks=_archive())
    assert a == b
    assert state == snap


def test_empty_state():
    assert st.exposures({}) == []
    assert st.finger_hard_days({}) == []
    assert st.count_exposures({}, "finger_max", since="2026-01-01", until="2026-12-31") == 0


# ---------------------------------------------------------------------------
# OUTDOOR-HARD rule
# ---------------------------------------------------------------------------

def test_hard_climb_threshold_two_steps_below_redpoint():
    s = _state()
    assert st.hard_climb_threshold(s, "lead") == "7c+"
    assert st.hard_climb_threshold(s, "boulder") == "7B"
    assert st.is_hard_climb(s, "lead", "7c+") is True
    assert st.is_hard_climb(s, "lead", "7c") is False
    assert st.is_hard_climb(s, "lead", "8a/a+") is True
    assert st.is_hard_climb(s, "boulder", "7b") is True
    assert st.is_hard_climb(s, "boulder", "7A+") is False
    assert st.is_hard_climb(s, "lead", "banana") is False


def test_redpoint_goal_fallback_only_same_discipline():
    s = {"goal": {"discipline": "lead", "current_grade": "7b"}}
    assert st.hard_climb_threshold(s, "lead") == "7a"
    assert st.hard_climb_threshold(s, "boulder") is None
    assert st.is_hard_climb(s, "boulder", "8A") is False


def test_outdoor_hard_days_from_rows_and_state():
    s = _state()
    s["outdoor_log"] = [
        {"date": "2026-10-03", "spot_id": "b", "discipline": "lead", "load_score": 30},  # no routes
        {"date": "2026-09-27", "spot_id": "b", "discipline": "lead",
         "routes": [{"name": "Easy", "grade": "7a"}]},
    ]
    rows = [{"entry": {"date": "2026-10-03", "spot_id": "b", "discipline": "lead", "routes": [
        {"name": "warm", "grade": "6b"}, {"name": "Mike", "grade": "7b+"},
        {"name": "Jactatio", "grade": "8a", "attempts": [{"result": "fell"}]}]}}]
    got = st.outdoor_hard_days(s, outdoor_rows=rows)
    assert got == [{"date": "2026-10-03", "source": "outdoor", "discipline": "lead",
                    "grade": "8a", "route": "Jactatio"}]


# ---------------------------------------------------------------------------
# finger-hard / pulling-hard
# ---------------------------------------------------------------------------

def test_power_endurance_gym_is_pulling_hard_not_finger_hard():
    pe = {"session_id": "power_endurance_gym", "tags": {"hard": True, "finger": False}}
    assert st.is_finger_hard_session(pe) is False
    assert st.is_pulling_hard_session(pe) is True


def test_custom_with_max_hang_is_finger_hard_despite_tags():
    cs = {"session_id": "custom_cs_x", "is_custom": True, "tags": {"hard": False, "finger": False},
          "exercises": [{"exercise_id": "max_hang_7s", "load_kg": 32}]}
    assert st.is_finger_hard_session(cs) is True
    assert st.is_finger_hard_session({"session_id": "technique_focus_gym"}) is False


def test_finger_hard_days_sources_and_planned_switch():
    s = _state()
    s["week_plans"]["2026-10-05"] = _week("2026-10-05", [
        ("2026-10-07", [{"session_id": "power_contact_gym", "status": "planned",
                         "tags": {"hard": True, "finger": True}}]),
        ("2026-10-08", [{"session_id": "power_endurance_gym",
                         "tags": {"hard": True, "finger": False}}]),
    ])
    s["free_sessions"] = [{"id": "f1", "date": "2026-10-06", "surface": "gym_boulder",
                           "climbs": [{"grade": "7C"}, {"grade": "7B"}]}]
    rows_out = [{"date": "2026-10-03", "discipline": "lead", "routes": [{"grade": "8a"}]}]
    done_only = st.finger_hard_days(s, since="2026-09-20", outdoor_rows=rows_out)
    assert [(r["date"], r["reason"]) for r in done_only] == [
        ("2026-09-24", "finger_hard_session"),
        ("2026-10-03", "outdoor_hard"),
        ("2026-10-06", "free_limit"),
    ]
    with_planned = st.finger_hard_days(s, since="2026-10-05", include_planned=True)
    assert [(r["date"], r["session_id"]) for r in with_planned] == [
        ("2026-10-06", "f1"), ("2026-10-07", "power_contact_gym")]
    # skipped never counts, even with include_planned
    assert all(r["date"] != "2026-10-02" for r in st.finger_hard_days(s, include_planned=True))
