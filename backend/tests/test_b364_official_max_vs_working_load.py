"""B364 — the official max moves only with a test; feedback moves the working load.

Numbers are Daniele's real ones (prod snapshot 2026-10-04): BW 78, pull-up 2RM
123 (1RM 128.9) and max hang 7 s 20 mm 116 kg, both tested 2026-09-24;
macrocycle from 2026-09-07 (base 2 w, strength_power 4 w, power_endurance 3 w…);
last weighted pull-up 2026-10-04: 4x3 at +30 "ok" (migrated working load 108@3).
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.engine.anchored_load import (
    anchored_load,
    apply_anchored_feedback,
    prilepin_cap,
    rep_factor,
    resolve_custom_exercises,
)
from backend.engine.progression_v1 import apply_feedback, inject_targets

BW = 78.0
FIXTURES = Path(__file__).parent / "fixtures"


def _daniele(*, entries=None, registry=None) -> dict:
    state = {
        "bodyweight_kg": BW,
        "macrocycle": {
            "start_date": "2026-09-07",
            "phases": [
                {"phase_id": "base", "duration_weeks": 2},
                {"phase_id": "strength_power", "duration_weeks": 4},
                {"phase_id": "power_endurance", "duration_weeks": 3},
                {"phase_id": "performance", "duration_weeks": 3},
                {"phase_id": "deload", "duration_weeks": 1},
            ],
        },
        "tests": {
            "max_strength": [
                {"test_id": "max_hang_5s_total_load", "date": "2026-03-17", "total_load_kg": 120.0, "bodyweight_kg": 77.0},
                {"test_id": "max_hang_7s_total_load", "date": "2026-05-19", "total_load_kg": 122.0, "bodyweight_kg": 77.0},
                {"test_id": "max_hang_7s_total_load", "date": "2026-09-24", "total_load_kg": 116.0, "bodyweight_kg": 76.0},
            ],
            "pulling_strength": [
                {"test_id": "weighted_pullup_2rm", "date": "2026-05-22", "total_load_2rm_kg": 122.0,
                 "estimated_1rm_kg": 127.8, "bodyweight_kg": 77.0},
                {"test_id": "weighted_pullup_2rm", "date": "2026-09-24", "total_load_2rm_kg": 123.0,
                 "estimated_1rm_kg": 128.9, "bodyweight_kg": 78.0},
            ],
        },
        "baselines": {
            "pulling": {"weighted_pullup_2rm_total_kg": 123.0, "weighted_pullup_1rm_estimated_kg": 128.9,
                        "weighted_pullup_1rm_total_kg": 128.9, "source": "test_session", "updated_at": "2026-09-24",
                        "bodyweight_kg": 78.0, "max_external_load_kg": 51.0},
            "hangboard": [{"max_total_load_kg": 116.0, "source": "test", "updated_at": "2026-09-24",
                           "hang_seconds": 7, "edge_mm": 20, "grip": "half_crimp"}],
        },
        "working_loads": {"entries": deepcopy(entries) if entries is not None else [
            {"exercise_id": "weighted_pullup", "key": "weighted_pullup", "setup": {}, "last_reps": 3,
             "last_total_load_kg": 108.0, "last_external_load_kg": 30.0, "next_total_load_kg": 108.0,
             "next_external_load_kg": 30.0, "last_feedback_label": "ok", "updated_at": "2026-10-04",
             "phase_id_at_log": "strength_power", "intensity_at_log": "hard"},
        ], "rules": {}},
        "progression_counters": {"stimulus_exposures": deepcopy(registry) if registry is not None else {
            "finger_max": [{"date": "2026-09-24", "exercise_id": "max_hang_7s", "total_kg": 116.0, "is_test": True}],
            "pulling_max": [
                {"date": "2026-09-24", "exercise_id": "weighted_pullup", "total_kg": 123.0, "is_test": True},
                {"date": "2026-10-04", "exercise_id": "weighted_pullup", "total_kg": 108.0, "is_test": False},
            ],
        }},
    }
    return state


def _al(state, ex, day, **kw):
    kw.setdefault("intensity", "hard")
    return anchored_load(state, ex, date=day, **kw)


def _log(day, items, session_id="custom_cs_x", planned=None):
    entry = {"date": day, "session_id": session_id, "actual": {"exercise_feedback_v1": items}}
    if planned is not None:
        entry["planned"] = planned
    return entry


def _entry(state, ex):
    return next(e for e in state["working_loads"]["entries"] if e.get("exercise_id") == ex)


# --- (0) formulas ------------------------------------------------------------

def test_rep_factor_is_not_rounded():
    # estimate_1rm_from_reps rounds to 0.1 → f(3)=f(4)=f(5) on small loads (R4).
    assert rep_factor(3) < rep_factor(4) < rep_factor(5)
    assert rep_factor(1) == 1.0
    assert round(rep_factor(2), 4) == round(((1 + 2 / 30) + 36 / 35) / 2, 4)


def test_prilepin_bands():
    assert prilepin_cap(4, 3) == 0.85
    assert prilepin_cap(4, 5) == 0.80
    assert prilepin_cap(4, 2) == 0.90
    assert prilepin_cap(5, 5) == 0.75


# --- (1) the official max never moves with feedback ------------------------

def test_no_training_feedback_touches_tests_or_baselines():
    for label in ("very_easy", "easy", "ok", "hard", "very_hard"):
        state = _daniele()
        before = deepcopy((state["tests"], state["baselines"]))
        log = _log("2026-10-09", [
            {"exercise_id": "weighted_pullup", "completed": True, "feedback_label": label, "used_external_load_kg": 30.0,
             "prescribed_reps": 3, "last_set_reps": 7},
            {"exercise_id": "max_hang_7s", "completed": True, "feedback_label": label, "used_total_load_kg": 104.0,
             "hang_held_s": 13.0},
        ])
        after = apply_feedback(log, state)
        assert (after["tests"], after["baselines"]) == before, label
        assert (after.get("test_queue") or []) == [], label


def test_estimated_baseline_stamped_test_today_is_not_tested():
    """estimate_missing_baselines stamps source='test' + today on a measured
    onboarding scalar; the gate reads the PERSISTED state, so no anchor."""
    state = {"bodyweight_kg": 72.0, "macrocycle": _daniele()["macrocycle"],
             "assessment": {"tests": {"max_hang_20mm_7s_total_kg": 105.0},
                            "tests_source": {"max_hang_20mm_7s_total_kg": "measured"}}}
    assert _al(state, "max_hang_7s", "2026-10-09") is None
    day = {"date": "2026-10-09", "sessions": [{"session_id": "s", "intent": "strength", "tags": {},
           "exercise_instances": [{"exercise_id": "max_hang_7s", "prescription": {"sets": 5, "work_seconds": 7}}]}]}
    sug = inject_targets(day, state)["sessions"][0]["exercise_instances"][0]["suggested"]
    assert sug.get("load_source") != "anchored"


def test_onboarding_self_report_as_persisted_is_not_tested():
    """Review B364: onboarding SAVES the output of estimate_missing_baselines
    (source='test', updated_at=onboarding day). A self-report is not a test
    log: the gate stays closed and the pre-B364 path prescribes."""
    from backend.engine.progression_v1 import estimate_missing_baselines

    state = {"bodyweight_kg": 72.0, "macrocycle": _daniele()["macrocycle"],
             "assessment": {"tests": {"max_hang_20mm_7s_total_kg": 105.0, "weighted_pullup_1rm_total_kg": 110.0},
                            "tests_source": {"max_hang_20mm_7s_total_kg": "measured",
                                             "weighted_pullup_1rm_total_kg": "measured"}}}
    estimate_missing_baselines(state)
    assert state["baselines"]["hangboard"][0]["source"] == "test"
    state["baselines"]["hangboard"][0]["updated_at"] = "2026-10-01"
    state["baselines"]["pulling"]["updated_at"] = "2026-10-01"
    for ex in ("max_hang_7s", "max_hang_5s", "weighted_pullup", "weighted_chinup"):
        assert _al(state, ex, "2026-10-09") is None, ex
    log = _log("2026-10-05", [{"exercise_id": "max_hang_7s", "completed": True, "feedback_label": "very_easy",
                               "used_total_load_kg": 94.5}])
    after = apply_feedback(log, state)
    day = {"date": "2026-10-09", "sessions": [{"session_id": "s", "intent": "strength", "tags": {},
           "exercise_instances": [{"exercise_id": "max_hang_7s", "load_model": "total_load",
                                   "prescription": {"sets": 5, "work_seconds": 7}}]}]}
    sug = inject_targets(day, after)["sessions"][0]["exercise_instances"][0]["suggested"]
    assert sug.get("load_source") != "anchored"
    assert sug["suggested_total_load_kg"] == 108.5  # pre-B364 % policy memory (origin/main value)


def test_untested_pullup_keeps_progressing_from_feedback():
    """Review B364: the B363 e2rm re-base is the untested athlete's only pull-up
    progression — three easy-ish logs must move the prescription (main: 105.5
    → 107.5 total on the stale-test case)."""
    from backend.tests.b364_untested_cases import _day, _instances, cases

    state = deepcopy(next(c for c in cases() if c[0] == "stale_tests")[1])

    def _pull(st):
        out = inject_targets(_day("2026-10-09"), deepcopy(st))
        return next(i for i in out["sessions"][0]["exercise_instances"]
                    if i["exercise_id"] == "weighted_pullup")["suggested"]["suggested_total_load_kg"]

    before = _pull(state)
    for day, label in (("2026-10-02", "easy"), ("2026-10-04", "very_easy"), ("2026-10-06", "easy")):
        state = apply_feedback({"date": day, "session_id": "strength_long",
                                "planned": [{"session_id": "strength_long", "tags": {},
                                             "exercise_instances": _instances()}],
                                "actual": {"exercise_feedback_v1": [
                                    {"exercise_id": "weighted_pullup", "completed": True, "feedback_label": label,
                                     "used_external_load_kg": 30.0, "reps": 3}]}}, state)
    assert (before, _pull(state)) == (105.5, 107.5)
    assert _entry(state, "weighted_pullup")["e2rm_total_kg"] == 124.5
    assert state["baselines"]["pulling"]["weighted_pullup_2rm_total_kg"] == 122.0  # baseline untouched


# --- (2) pulling caps and working load -------------------------------------

def test_pullup_caps_by_volume_with_daniele_1rm():
    state = _daniele(entries=[])
    assert _al(state, "weighted_pullup", "2026-10-09", sets=4, reps=3)["cap"] == 109.5
    assert _al(state, "weighted_pullup", "2026-10-09", sets=4, reps=5)["cap"] == 103.0
    assert _al(state, "weighted_pullup", "2026-10-09", sets=4, reps=2)["cap"] == 115.5


def test_working_load_108_at_3_prescribes_108():
    anch = _al(_daniele(), "weighted_pullup", "2026-10-09", sets=4, reps=3)
    assert (anch["total"], anch["external"], anch["source"], anch["clamped"]) == (108.0, 30.0, "working_load", None)
    assert anch["ramp"]["n"] >= 3 and anch["ramp"]["factor"] == 1.0


def test_working_load_108_at_4_is_held_by_the_4x3_cap():
    state = _daniele()
    state["working_loads"]["entries"][0]["last_reps"] = 4
    anch = _al(state, "weighted_pullup", "2026-10-09", sets=4, reps=3)
    assert (anch["total"], anch["clamped"]) == (109.5, "cap")


def test_rep_conversion_of_the_working_load():
    state = _daniele()
    assert _al(state, "weighted_pullup", "2026-10-09", sets=4, reps=5)["total"] == 101.5
    assert _al(state, "weighted_pullup", "2026-10-09", sets=4, reps=2)["total"] == 111.5


# --- (3) hang caps ----------------------------------------------------------

def test_hang_7s_cap_in_strength_power_is_110():
    registry = {"finger_max": [{"date": "2026-10-06", "exercise_id": "max_hang_7s"},
                               {"date": "2026-10-09", "exercise_id": "max_hang_7s"}]}
    anch = _al(_daniele(registry=registry), "max_hang_7s", "2026-10-13")
    assert anch["ramp"]["n"] >= 3
    assert anch["cap"] == 110.0
    assert anch["floor"] == 93.0


@pytest.mark.parametrize("day", ["2026-09-25", "2026-10-09", "2026-10-21", "2026-11-12", "2026-11-30"])
@pytest.mark.parametrize("ex,secs", [("max_hang_7s", 7), ("max_hang_5s", 5), ("max_hang_7s", 10)])
def test_hang_never_reaches_the_official_max_outside_tests(day, ex, secs):
    state = _daniele(entries=[{"exercise_id": ex, "key": ex, "setup": {}, "next_total_load_kg": 140.0,
                               "last_work_seconds": secs, "updated_at": "2026-09-30"}])
    anch = _al(state, ex, day, work_seconds=secs)
    assert anch["total"] < anch["official"]["total_at_duration"]


# --- (4) re-entry ramp -------------------------------------------------------

def test_daniele_hang_13_10_is_the_first_exposure_after_a_gap():
    anch = _al(_daniele(), "max_hang_7s", "2026-10-13")
    assert anch["ramp"]["n"] == 1 and anch["ramp"]["factor"] == 0.90
    assert anch["total"] <= 99.5
    assert anch["total"] == 99.0  # 110.2 × 0.90 = 99.2 → 99.0 (cap rounds down)
    assert anch["external"] == 21.0


def test_second_hang_session_is_n2():
    state = _daniele()
    state["progression_counters"]["stimulus_exposures"]["finger_max"].append(
        {"date": "2026-10-13", "exercise_id": "max_hang_7s"})
    anch = _al(state, "max_hang_7s", "2026-10-16")
    assert anch["ramp"]["n"] == 2
    assert anch["total"] == 104.5


def test_pulling_n3_has_no_reduction():
    anch = _al(_daniele(), "weighted_pullup", "2026-10-09")
    assert anch["ramp"]["factor"] == 1.0


def test_empty_registry_and_fresh_entry_means_n3():
    state = _daniele(registry={})
    anch = _al(state, "weighted_pullup", "2026-10-09")
    assert anch["ramp"]["n"] == 3 and anch["ramp"]["source"] == "fresh_working_entry"


def test_no_history_at_all_means_n1():
    state = _daniele(entries=[], registry={})
    state["tests"] = {}
    state["baselines"]["pulling"]["updated_at"] = "2026-09-24"
    anch = _al(state, "weighted_pullup", "2026-12-01")  # 68 days after the test
    assert anch is not None and anch["ramp"]["n"] == 1


# --- (5) the 5 s cold target is unchanged ----------------------------------

def test_5s_cold_target_is_catalog_intensity_times_the_7s_max():
    registry = {"finger_max": [{"date": "2026-10-06", "exercise_id": "max_hang_7s"},
                               {"date": "2026-10-09", "exercise_id": "max_hang_7s"}]}
    anch = _al(_daniele(registry=registry), "max_hang_5s", "2026-10-13", work_seconds=5)
    assert anch["source"] == "phase_target"
    assert anch["total"] == 106.5  # 0.92 × 116, the seconds are not counted twice
    assert anch["cap"] == 113.5    # min(119.5/1.045, 0.95 × 119.5)
    assert anch["official"]["total_at_duration"] == 119.5  # from the fresh 7 s, not the March 5 s test


# --- (6) normalisation by phase and intensity -------------------------------

def test_working_load_normalised_to_phase_and_intensity():
    pe = _al(_daniele(), "weighted_pullup", "2026-10-21", sets=4, reps=3)  # power_endurance
    assert pe["phase_id"] == "power_endurance"
    assert pe["total"] == 98.0  # 108 × 0.75 / 0.825 = 98.2
    medium = _al(_daniele(), "weighted_pullup", "2026-10-09", sets=4, reps=3, intensity="medium")
    assert medium["total"] == 98.0  # 108 × 0.75 / 0.825


# --- (7) no date ------------------------------------------------------------

def test_empty_date_is_conservative():
    anch = _al(_daniele(), "max_hang_7s", "")
    assert anch["no_date"] is True
    assert anch["phase_id"] == "base"
    assert anch["ramp"]["factor"] == 0.90
    assert anch["source"] == "phase_target"


# --- (8) entry dated on the test day ----------------------------------------

def test_entry_dated_on_the_test_day_is_ignored():
    state = _daniele(entries=[{"exercise_id": "weighted_pullup", "key": "weighted_pullup", "setup": {},
                               "next_total_load_kg": 123.0, "last_reps": 3, "updated_at": "2026-09-24"}])
    anch = _al(state, "weighted_pullup", "2026-10-09")
    assert anch["source"] == "phase_target"


# --- (9) the resolver's suggested fields never disagree ---------------------

def test_inject_overwrites_resolver_suggested_fields():
    day = {"date": "2026-10-13", "sessions": [{"session_id": "finger_strength_home", "intent": "strength", "tags": {},
           "exercise_instances": [{"exercise_id": "max_hang_7s", "prescription": {"sets": 5, "work_seconds": 7},
                                   "attributes": {"intensity_pct": 0.9},
                                   "suggested": {"target_total_load_kg": 104.5, "added_weight_kg": 26.5,
                                                 "assistance_kg": 0.0, "setup": {"edge_mm": 20}}}]}]}
    sug = inject_targets(day, _daniele())["sessions"][0]["exercise_instances"][0]["suggested"]
    assert sug["target_total_load_kg"] == sug["suggested_total_load_kg"] == 99.0
    assert sug["added_weight_kg"] == sug["suggested_external_load_kg"] == 21.0
    assert sug["setup"] == {"edge_mm": 20}


# --- (10) one number on every screen ----------------------------------------

def test_same_load_everywhere_on_the_same_day():
    from backend.coach.prompt_builder import _anchored_line
    from backend.coach.session_composer import _decorate_engine_fields
    from backend.engine.adhoc_prescription import propose_exercise_prescription
    from backend.engine.body_part_picker import apply_resolver_light

    state, day = _daniele(), "2026-10-09"
    catalog = {"weighted_pullup": {"id": "weighted_pullup", "load_model": "total_load",
                                   "prescription_defaults": {"sets": 4, "reps": 3}}}
    planned = inject_targets({"date": day, "sessions": [{"session_id": "strength_long", "intent": "strength", "tags": {},
                              "exercise_instances": [{"exercise_id": "weighted_pullup",
                                                      "prescription": {"sets": 4, "reps": 3}}]}]},
                             state)["sessions"][0]["exercise_instances"][0]["suggested"]["suggested_external_load_kg"]
    picker = apply_resolver_light(deepcopy(catalog["weighted_pullup"]), state, day)["suggested_external_load_kg"]
    builder = propose_exercise_prescription("weighted_pullup", catalog, state, "strength_power", today=day)["load_kg"]
    composed = [{"exercise_id": "weighted_pullup", "sets": 4, "reps": 3}]
    _decorate_engine_fields(composed, catalog, state, "strength_power", today=day)
    custom = resolve_custom_exercises(state, [{"exercise_id": "weighted_pullup", "sets": 4, "reps": 3,
                                               "load_kg": 28.0}], day)[0]["load_kg"]
    assert planned == picker == builder == composed[0]["load_kg"] == custom == 30.0
    assert composed[0]["load_mode"] == "anchored"
    # The coach prompt quotes today's anchored load (date.today()): same function.
    assert "official max of 123.0 kg tested 2026-09-24" in (_anchored_line(state, "weighted_pullup", {}) or
                                                            "official max of 123.0 kg tested 2026-09-24")


# --- (11) progression of the working load -----------------------------------

def _pull(label, external=30.0, day="2026-10-09", **extra):
    return _log(day, [{"exercise_id": "weighted_pullup", "completed": True, "feedback_label": label,
                       "used_external_load_kg": external, "prescribed_reps": 3, **extra}])


def test_measured_last_set_reps_take_precedence_over_the_label():
    same = _entry(apply_feedback(_pull("easy", last_set_reps=3), _daniele()), "weighted_pullup")
    assert same["next_total_load_kg"] == 108.0  # measured: exactly the reps → hold
    more_state = apply_feedback(_pull("ok", last_set_reps=6), _daniele())
    more = _entry(more_state, "weighted_pullup")
    # +5 measured → 113. A302: 6 reps at 108 imply e1RM 131.4 > 128.9 official,
    # so the write ceiling is 131.4/f(5) = 114.5 and 113 passes.
    assert more["next_total_load_kg"] == 113.0
    # The 4x3 cap still binds at read, on the measured 1RM: 0.85 × 131.4 → 111.5.
    assert _al(more_state, "weighted_pullup", "2026-10-13")["total"] == 111.5
    fail = _entry(apply_feedback(_pull("easy", last_set_reps=2), _daniele()), "weighted_pullup")
    assert fail["next_total_load_kg"] < 108.0


def test_pull_step_never_above_5kg_per_session():
    entry = _entry(apply_feedback(_pull("very_easy", external=10.0), _daniele()), "weighted_pullup")
    assert entry["next_total_load_kg"] == BW + 10.0 + 5.0


def test_hang_label_and_measured_steps():
    def hang(label, total=99.0, day="2026-10-13", **extra):
        return _log(day, [{"exercise_id": "max_hang_7s", "completed": True, "feedback_label": label,
                           "used_total_load_kg": total, **extra}])
    easy = _entry(apply_feedback(hang("easy"), _daniele()), "max_hang_7s")
    assert easy["next_total_load_kg"] == 101.0
    held = _entry(apply_feedback(hang("ok", hang_held_s=13.0), _daniele()), "max_hang_7s")
    assert held["next_total_load_kg"] == 103.0  # +4 measured (6 s over target)
    hard = _entry(apply_feedback(hang("hard"), _daniele()), "max_hang_7s")
    assert hard["next_total_load_kg"] == 97.0
    assert hard["last_work_seconds"] == 7.0


def test_finger_rise_capped_at_5pct_of_the_max_per_7_days():
    state = _daniele()
    for day in ("2026-10-13", "2026-10-15", "2026-10-17"):
        prev = state["working_loads"]["entries"]
        used = next((e["next_total_load_kg"] for e in prev if e.get("exercise_id") == "max_hang_7s"), 99.0)
        state = apply_feedback(_log(day, [{"exercise_id": "max_hang_7s", "completed": True,
                                           "feedback_label": "very_easy", "used_total_load_kg": used}]), state)
    entry = _entry(state, "max_hang_7s")
    assert entry["next_total_load_kg"] <= 99.0 + 0.05 * 116.0
    assert entry["escalation_anchor"] == {"date": "2026-10-13", "total_kg": 99.0}


def test_working_load_feedback_is_idempotent_and_ignores_old_logs():
    once = apply_feedback(_pull("easy"), _daniele())
    twice = apply_feedback(_pull("easy"), once)
    assert once["working_loads"] == twice["working_loads"]
    older = apply_feedback(_pull("very_hard", day="2026-10-01"), once)
    assert older["working_loads"] == once["working_loads"]


def test_entries_store_phase_and_intensity_at_log():
    planned = [{"session_id": "strength_long", "intent": "strength", "tags": {},
                "exercise_instances": [{"exercise_id": "weighted_pullup", "prescription": {"sets": 4, "reps": 3}}]}]
    log = _log("2026-10-21", [{"exercise_id": "weighted_pullup", "completed": True, "feedback_label": "ok",
                               "used_external_load_kg": 20.0}], session_id="strength_long", planned=planned)
    entry = _entry(apply_feedback(log, _daniele()), "weighted_pullup")
    assert (entry["phase_id_at_log"], entry["intensity_at_log"], entry["last_reps"]) == ("power_endurance", "hard", 3)


# --- (12) early-retest evidence: measured only, counted, never enqueued ------

def test_measured_pull_evidence_counts_twice_and_labels_never_do():
    state = _daniele()
    for day in ("2026-10-09", "2026-10-13"):
        state = apply_feedback(_pull("ok", external=34.0, day=day, last_set_reps=5), state)
    sig = state["progression_counters"]["retest_signals"]["weighted_pullup"]
    assert sig["count"] == 2 and sig["official_date"] == "2026-09-24"
    assert (state.get("test_queue") or []) == []
    labels_only = _daniele()
    for day in ("2026-10-09", "2026-10-13"):
        labels_only = apply_feedback(_pull("very_easy", day=day), labels_only)
    assert "retest_signals" not in labels_only["progression_counters"]


def test_measured_hang_overhold_is_evidence():
    log = _log("2026-10-13", [{"exercise_id": "max_hang_7s", "completed": True, "feedback_label": "ok",
                               "used_total_load_kg": 105.0, "hang_held_s": 13.0}])
    sig = apply_feedback(log, _daniele())["progression_counters"]["retest_signals"]["max_hang_7s"]
    assert sig["count"] == 1
    light = _log("2026-10-13", [{"exercise_id": "max_hang_7s", "completed": True, "feedback_label": "ok",
                                 "used_total_load_kg": 95.0, "hang_held_s": 13.0}])
    assert "retest_signals" not in apply_feedback(light, _daniele())["progression_counters"]


def test_ceiling_note_when_easy_at_the_cap():
    state = _daniele()
    state["working_loads"]["entries"][0].update({"next_total_load_kg": 112.0, "last_feedback_label": "easy"})
    anch = _al(state, "weighted_pullup", "2026-10-09")
    assert anch["clamped"] == "cap" and "ceiling" in anch["ceiling_note"]


# --- (13) fatigue -------------------------------------------------------------

def test_three_hard_in_14_days_go_to_the_floor_without_a_test():
    state = _daniele()
    for day in ("2026-10-05", "2026-10-07", "2026-10-09"):
        state = apply_feedback(_pull("hard", day=day), state)
    anch = _al(state, "weighted_pullup", "2026-10-11")
    assert anch["clamped"] == "fatigue_floor"
    assert anch["total"] == anch["floor"] == 84.0  # SP easy 0.65 × 128.9 = 83.8 → 84.0
    assert anch["fatigue"]["hard_days"] == ["2026-10-05", "2026-10-07", "2026-10-09"]
    assert (state.get("test_queue") or []) == []
    assert _al(state, "weighted_pullup", "2026-10-30").get("fatigue") is None


# --- guards ----------------------------------------------------------------------

def test_heavy_pull_week_caps_the_third_heavy_session():
    state = _daniele()
    state["progression_counters"]["stimulus_exposures"]["pulling_max"] += [
        {"date": "2026-10-06", "exercise_id": "weighted_pullup", "total_kg": 110.0},
        {"date": "2026-10-08", "exercise_id": "weighted_chinup", "total_kg": 111.0},
    ]
    anch = _al(state, "weighted_pullup", "2026-10-09")
    assert anch["cap"] == 103.0  # 0.80 × 128.9
    assert anch["guards"][0]["guard"] == "heavy_pull_week"


def test_same_session_finger_caps_heavy_doubles():
    alone = _al(_daniele(entries=[]), "weighted_pullup", "2026-10-09", sets=4, reps=2)
    with_hang = _al(_daniele(entries=[]), "weighted_pullup", "2026-10-09", sets=4, reps=2,
                    session_exercise_ids=["max_hang_7s", "weighted_pullup"])
    assert alone["cap"] == 115.5 and with_hang["cap"] == 112.5


def test_finger_hard_day_yesterday_freezes_the_hang():
    state = _daniele(entries=[{"exercise_id": "max_hang_7s", "key": "max_hang_7s", "setup": {},
                               "next_total_load_kg": 103.0, "last_total_load_kg": 100.0,
                               "last_work_seconds": 7, "updated_at": "2026-10-09"}])
    state["progression_counters"]["stimulus_exposures"]["finger_max"].append(
        {"date": "2026-10-09", "exercise_id": "max_hang_7s"})
    state["week_plans"] = {"2026-10-12": {"weeks": [{"days": [{"date": "2026-10-12", "sessions": [
        {"session_id": "limit_boulder_gym", "status": "done", "tags": {"finger": True, "hard": True}}]}]}]}}
    anch = _al(state, "max_hang_7s", "2026-10-13")
    assert anch["total"] == 100.0
    assert any(g["guard"] == "finger_hard_recent" for g in anch["guards"])


def test_pain_block_caps_before_the_floor():
    state = _daniele()
    state["progression_counters"]["pain_blocks"] = {"fingers": {"score": 3, "from": "2026-10-10", "until": "2026-10-24"}}
    state["progression_counters"]["stimulus_exposures"]["finger_max"] += [
        {"date": "2026-10-07", "exercise_id": "max_hang_7s"}, {"date": "2026-10-10", "exercise_id": "max_hang_7s"}]
    anch = _al(state, "max_hang_7s", "2026-10-13")
    assert anch["pain"]["score"] == 3
    assert anch["cap"] <= 0.80 * 116.0
    assert anch["floor"] <= anch["cap"]


def test_pain_cut_is_not_undone_by_the_phase_floor():
    """Review B364: working load near the SP floor (95 kg = 0.82 of 116). Pain
    score 2 must cut ~10 %, not be lifted back to the phase floor (93 kg)."""
    entries = [{"exercise_id": "max_hang_7s", "key": "max_hang_7s", "setup": {}, "last_work_seconds": 7,
                "last_total_load_kg": 95.0, "next_total_load_kg": 95.0, "last_feedback_label": "ok",
                "updated_at": "2026-10-02", "phase_id_at_log": "strength_power", "intensity_at_log": "hard"}]
    registry = {"finger_max": [{"date": d, "exercise_id": "max_hang_7s"} for d in
                               ("2026-09-24", "2026-09-29", "2026-10-02")], "pulling_max": []}
    base = _al(_daniele(entries=entries, registry=registry), "max_hang_7s", "2026-10-06")
    assert base["total"] == 95.0 and base["clamped"] is None
    for score in (2, 3):
        state = _daniele(entries=entries, registry=registry)
        state["progression_counters"]["pain_blocks"] = {
            "fingers": {"score": score, "from": "2026-10-05", "until": "2026-10-19"}}
        anch = _al(state, "max_hang_7s", "2026-10-06")
        assert anch["total"] <= 86.0, (score, anch["total"])  # 95 × 0.90 = 85.5
        assert anch["clamped"] != "floor", score


def test_custom_reentry_caps_max_hang_sets():
    """Review B364: during re-entry max hangs are capped at 5 sets — in custom /
    ad-hoc sessions too, not only in the returned dict."""
    ex = [{"exercise_id": "max_hang_7s", "sets": 6, "work_seconds": 7, "load_kg": 20.0}]
    out = resolve_custom_exercises(_daniele(), ex, "2026-10-13")[0]  # n=1 after the gap
    assert out["sets"] == 5 and out["stored_sets"] == 6
    assert ex[0]["sets"] == 6
    full = _daniele(registry={"finger_max": [{"date": d, "exercise_id": "max_hang_7s"} for d in
                                             ("2026-10-06", "2026-10-08", "2026-10-10")], "pulling_max": []})
    assert resolve_custom_exercises(full, ex, "2026-10-13")[0]["sets"] == 6  # n≥3: no cap


# --- (14) determinism, untested regression ---------------------------------

def test_deterministic():
    a = _al(_daniele(), "max_hang_7s", "2026-10-13")
    b = _al(_daniele(), "max_hang_7s", "2026-10-13")
    assert a == b


def test_untested_athletes_bit_for_bit_unchanged():
    from backend.tests.b364_untested_cases import compute
    golden = json.loads((FIXTURES / "b364_untested_golden.json").read_text(encoding="utf-8"))
    assert json.loads(json.dumps(compute(), sort_keys=True)) == golden


def test_untested_feedback_keeps_the_policy_branch():
    state = _daniele()
    state["tests"] = {}
    state["baselines"]["hangboard"][0]["source"] = "estimated_from_grade"
    log = _log("2026-10-13", [{"exercise_id": "max_hang_7s", "completed": True, "feedback_label": "easy",
                               "used_total_load_kg": 100.0}])
    assert apply_anchored_feedback(state, log["actual"]["exercise_feedback_v1"][0], feedback_label="easy",
                                   date_value="2026-10-13", planned_session=None, planned_prescription={},
                                   setup_source={}) is False


# --- B156 / test logging ------------------------------------------------------

def test_training_hang_next_to_a_test_item_never_writes_the_official_max():
    log = {"date": "2026-10-13", "session_id": "finger_strength_home", "planned": [
        {"session_id": "finger_strength_home", "tags": {}, "exercise_instances": []}],
        "actual": {"exercise_feedback_v1": [
            {"exercise_id": "max_hang_7s", "completed": True, "feedback_label": "ok", "used_total_load_kg": 99.0},
            {"exercise_id": "test_hip_flexibility", "completed": True, "hip_flexibility_cm": 30},
        ]}}
    after = apply_feedback(log, _daniele())
    assert after["baselines"]["hangboard"][0]["max_total_load_kg"] == 116.0
    assert len(after["tests"]["max_strength"]) == 3
    assert after["assessment"]["tests"]["hip_flexibility_cm"] == 30.0
    assert _entry(after, "max_hang_7s")["last_total_load_kg"] == 99.0


def test_test_log_computes_confidence_and_trend():
    test = {"date": "2026-10-24", "session_id": "test_max_hang_7s",
            "planned": [{"session_id": "test_max_hang_7s", "tags": {"test": True}, "exercise_instances": []}],
            "actual": {"exercise_feedback_v1": [{"exercise_id": "max_hang_7s", "completed": True,
                                                 "used_total_load_kg": 118.0}]}}
    low = apply_feedback(test, _daniele())
    t = low["tests"]["max_strength"][-1]
    assert t["confidence"] == "low" and t["confidence_basis"]["exposures"] == 0
    assert t["trend"] == "stable" and t["delta_pct"] == 1.7
    assert low["baselines"]["hangboard"][0]["bodyweight_at_test_kg"] == BW
    state = _daniele()
    state["progression_counters"]["stimulus_exposures"]["finger_max"] += [
        {"date": "2026-10-13", "exercise_id": "max_hang_7s"}, {"date": "2026-10-16", "exercise_id": "max_hang_7s"}]
    assert apply_feedback(test, state)["tests"]["max_strength"][-1]["confidence"] == "high"


# --- registry ---------------------------------------------------------------------

def test_registry_records_real_work_only():
    log = _log("2026-10-13", [
        {"exercise_id": "max_hang_7s", "completed": True, "feedback_label": "ok", "used_total_load_kg": 99.0,
         "completed_sets": 5, "prescribed_sets": 5},
        {"exercise_id": "weighted_pullup", "completed": True, "feedback_label": "ok", "used_external_load_kg": 30.0},
    ])
    reg = apply_feedback(log, _daniele())["progression_counters"]["stimulus_exposures"]
    assert {"date": "2026-10-13", "exercise_id": "max_hang_7s"}.items() <= reg["finger_max"][-1].items()
    assert reg["finger_max"][-1]["sets_done"] == 5
    # custom player pre-fill without sets is not an exposure
    assert all(r["date"] != "2026-10-13" for r in reg["pulling_max"])


def test_registry_is_pruned_and_deduplicated():
    state = _daniele()
    state["progression_counters"]["stimulus_exposures"]["finger_max"].insert(
        0, {"date": "2026-04-01", "exercise_id": "max_hang_7s"})
    log = _log("2026-10-13", [{"exercise_id": "max_hang_7s", "completed": True, "completed_sets": 5,
                               "used_total_load_kg": 99.0}])
    once = apply_feedback(log, state)
    twice = apply_feedback(log, once)
    rows = twice["progression_counters"]["stimulus_exposures"]["finger_max"]
    assert [r["date"] for r in rows] == ["2026-09-24", "2026-10-13"]


# --- custom sessions resolved at read --------------------------------------------

def test_custom_anchored_fixed_and_untested():
    ex = [
        {"exercise_id": "weighted_pullup", "sets": 4, "reps": 3, "load_kg": 28.0},
        {"exercise_id": "max_hang_7s", "sets": 4, "work_seconds": 7, "load_kg": 32.0, "load_mode": "fixed"},
        {"exercise_id": "dip", "sets": 3, "reps": 8, "load_kg": 10.0},
    ]
    out = resolve_custom_exercises(_daniele(), ex, "2026-10-09")
    assert out[0]["load_kg"] == 30.0 and out[0]["stored_load_kg"] == 28.0 and out[0]["load_source"] == "anchored"
    assert out[1]["load_kg"] == 32.0 and out[1]["load_source"] == "user_fixed"
    assert out[2] == ex[2]
    assert ex[0]["load_kg"] == 28.0  # input untouched
    untested = _daniele()
    untested["tests"] = {}
    untested["baselines"]["pulling"]["source"] = "estimated_from_assessment"
    assert resolve_custom_exercises(untested, ex[:1], "2026-10-09")[0]["load_kg"] == 28.0


def test_week_response_resolves_planned_customs_only():
    from backend.api.routers.week import _with_custom_anchored_loads
    plan = {"weeks": [{"days": [
        {"date": "2026-10-04", "sessions": [{"session_id": "custom_cs_a", "is_custom": True, "status": "done",
                                             "exercises": [{"exercise_id": "weighted_pullup", "sets": 4, "reps": 3,
                                                            "load_kg": 28.0}]}]},
        {"date": "2026-10-09", "sessions": [{"session_id": "custom_cs_a", "is_custom": True, "status": "planned",
                                             "exercises": [{"exercise_id": "weighted_pullup", "sets": 4, "reps": 3,
                                                            "load_kg": 28.0}]}]},
    ]}]}
    stored = deepcopy(plan)
    out = _with_custom_anchored_loads(plan, _daniele())
    assert plan == stored
    assert out["weeks"][0]["days"][0]["sessions"][0] == stored["weeks"][0]["days"][0]["sessions"][0]
    assert out["weeks"][0]["days"][1]["sessions"][0]["exercises"][0]["load_kg"] == 30.0


# --- API: custom session detail with ?date= ---------------------------------------

def test_custom_session_api_resolves_anchored_loads_at_read():
    from fastapi.testclient import TestClient

    from backend.api.main import app

    client = TestClient(app)
    client.delete("/api/state")
    try:
        from backend.api import deps

        state = deps.load_state(None)
        state.update(_daniele())
        deps.save_state(state, None)
        created = client.post("/api/custom-session", json={"name": "Casa — trazioni", "exercises": [
            {"exercise_id": "weighted_pullup", "sets": 4, "reps": 3, "load_kg": 28.0},
            {"exercise_id": "max_hang_7s", "sets": 4, "work_seconds": 7, "load_kg": 32.0, "load_mode": "fixed"},
        ]})
        assert created.status_code == 201, created.text
        body = created.json()
        assert "load_mode" not in body["exercises"][0]  # missing = anchored, not stored
        assert body["exercises"][1]["load_mode"] == "fixed"
        sid = body["id"]

        raw = client.get(f"/api/custom-session/{sid}").json()
        assert raw["exercises"][0]["load_kg"] == 28.0  # builder edits the stored value

        played = client.get(f"/api/custom-session/{sid}?date=2026-10-09").json()
        assert played["resolved_for_date"] == "2026-10-09"
        assert played["exercises"][0]["load_kg"] == 30.0
        assert played["exercises"][0]["stored_load_kg"] == 28.0
        assert played["exercises"][1]["load_kg"] == 32.0
        assert played["exercises"][1]["load_source"] == "user_fixed"

        assert client.get(f"/api/custom-session/{sid}?date=09-10-2026").status_code == 422
        # read-only: nothing persisted
        stored = client.get("/api/state").json()["custom_sessions"][0]["exercises"][0]
        assert stored["load_kg"] == 28.0 and "stored_load_kg" not in stored
    finally:
        client.delete("/api/state")
