"""B363 — a test max must never come back as a training load.

Production case (2026-10-04): the 2RM pull-up test of 2026-09-24 (+45 kg at
78 kg BW) logged its feedback under the training id ``weighted_pullup``;
apply_feedback copied it into working_loads and the next 4x3 was prescribed at
+45 kg — the athlete's 2RM. Same defect on max_hang_7s (100% test max returned
as the ~90% training load).

The pull-up reference stays a 2RM (it is what the athlete measures); a 1RM is
only an intermediate value to apply PULLING_1RM_PCT.
"""

from copy import deepcopy

from backend.api.routers.feedback import _attach_prescribed_reps
from backend.engine.adhoc_prescription import anchor_adhoc_load, propose_exercise_prescription
from backend.engine.progression_v1 import (
    apply_feedback,
    estimate_1rm_from_2rm,
    estimate_1rm_from_reps,
    inject_targets,
    pullup_reference_2rm,
    weighted_pullup_target,
)

BW = 78.0


def _state() -> dict:
    """Daniele's real numbers on 2026-10-04 (strength_power, week 5)."""
    return {
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
        "baselines": {
            "pulling": {
                "weighted_pullup_2rm_total_kg": 123.0,
                "weighted_pullup_1rm_estimated_kg": 128.9,
                "weighted_pullup_1rm_total_kg": 128.9,
                "bodyweight_kg": BW,
                "max_external_load_kg": 51.0,
                "source": "test_session",
                "updated_at": "2026-09-24",
            },
            "hangboard": [{"grip": "half_crimp", "edge_mm": 20, "hang_seconds": 7,
                           "max_total_load_kg": 116.0, "source": "test", "updated_at": "2026-09-24"}],
        },
        "working_loads": {"entries": [], "rules": {}},
    }


def _day(date="2026-10-04", reps=3):
    return {
        "date": date,
        "sessions": [{
            "session_id": "pulling_strength_home",
            "intent": "strength",
            "tags": {},
            "exercise_instances": [{"exercise_id": "weighted_pullup", "prescription": {"sets": 4, "reps": reps}}],
        }],
    }


def _pullup_suggested(state, date="2026-10-04"):
    out = inject_targets(_day(date), state)
    return out["sessions"][0]["exercise_instances"][0]["suggested"]


def _test_log(exercise_id, **fb):
    item = {"exercise_id": exercise_id, "completed": True, "feedback_label": "ok", **fb}
    return {
        "date": "2026-09-24",
        "session_id": f"test_{'max_weighted_pullup' if exercise_id == 'weighted_pullup' else 'max_hang_7s'}",
        "planned": [{"session_id": "test_x", "tags": {"test": True}, "exercise_instances": []}],
        "actual": {"exercise_feedback_v1": [item]},
    }


def _training_log(label, external, reps=3, date="2026-10-04"):
    return {
        "date": date,
        "session_id": "custom_cs_x",
        "actual": {"exercise_feedback_v1": [{
            "exercise_id": "weighted_pullup", "completed": True, "feedback_label": label,
            "used_external_load_kg": external, "prescribed_reps": reps,
        }]},
    }


def _entries(state, exercise_id):
    return [e for e in state["working_loads"]["entries"] if e.get("exercise_id") == exercise_id]


# --- the 2RM stays the reference --------------------------------------------

def test_reps_formula_matches_the_2rm_formula():
    assert estimate_1rm_from_reps(123.0, 2) == estimate_1rm_from_2rm(123.0)


def test_reference_is_the_tested_2rm():
    assert pullup_reference_2rm(_state()) == 123.0


def test_daniele_prescription_today_is_not_his_2rm():
    sug = _pullup_suggested(_state())
    # 2RM 123 → e1RM 128.9 → strength_power/hard 82.5% → 106.5 total → +28.5
    assert sug["suggested_external_load_kg"] == 28.5
    assert sug["suggested_total_load_kg"] < 123.0
    assert sug["reference_2rm_total_kg"] == 123.0


# --- a test never becomes the training load ---------------------------------

def test_pullup_2rm_test_does_not_write_training_load():
    state = _state()
    state["working_loads"]["entries"] = [{"exercise_id": "weighted_pullup", "key": "weighted_pullup",
                                          "next_external_load_kg": 30.0, "updated_at": "2026-09-10"}]
    updated = apply_feedback(_test_log("weighted_pullup", used_external_load_kg=45.0), state)
    assert _entries(updated, "weighted_pullup") == []
    # …but the test itself is still recorded as the new baseline.
    assert updated["baselines"]["pulling"]["weighted_pullup_2rm_total_kg"] == 123.0
    assert _pullup_suggested(updated)["suggested_external_load_kg"] < 45.0


def test_max_hang_test_does_not_write_training_load():
    state = _state()
    updated = apply_feedback(_test_log("max_hang_7s", used_total_load_kg=116.0), state)
    assert _entries(updated, "max_hang_7s") == []


def test_polluted_legacy_entry_is_ignored():
    """The exact prod entry: test load copied in as next load, no e2rm."""
    state = _state()
    state["working_loads"]["entries"] = [{
        "key": "weighted_pullup", "exercise_id": "weighted_pullup", "setup": {},
        "updated_at": "2026-09-24", "last_total_load_kg": 123.0, "next_total_load_kg": 123.0,
        "last_external_load_kg": 45.0, "next_external_load_kg": 45.0, "last_feedback_label": "ok",
    }]
    assert _pullup_suggested(state)["suggested_external_load_kg"] == 28.5


# --- training re-bases the 2RM ----------------------------------------------

def test_easy_light_set_never_lowers_the_reference():
    updated = apply_feedback(_training_log("easy", 30.0), _state())
    assert pullup_reference_2rm(updated) == 123.0


def test_strong_set_of_three_raises_the_reference():
    # 3 reps at +45 reported "ok" (≈2 in reserve) ≈ a 5RM at 123 → well above a 2RM of 123.
    updated = apply_feedback(_training_log("ok", 45.0), _state())
    assert pullup_reference_2rm(updated) > 123.0
    assert _pullup_suggested(updated)["suggested_external_load_kg"] > 28.5


def test_only_hard_lowers_the_reference():
    hard = apply_feedback(_training_log("hard", 30.0), _state())
    very_hard = apply_feedback(_training_log("very_hard", 30.0), _state())
    assert pullup_reference_2rm(hard) < 123.0
    assert pullup_reference_2rm(very_hard) < pullup_reference_2rm(hard)
    for label in ("ok", "easy", "very_easy"):
        assert pullup_reference_2rm(apply_feedback(_training_log(label, 20.0), _state())) == 123.0


def test_a_new_test_supersedes_a_training_rebase():
    state = apply_feedback(_training_log("ok", 45.0), _state())
    assert pullup_reference_2rm(state) > 123.0
    state = apply_feedback(_test_log("weighted_pullup", used_external_load_kg=42.0), state)
    assert pullup_reference_2rm(state) == 120.0


def test_rebase_is_deterministic():
    a = apply_feedback(_training_log("ok", 40.0), _state())
    b = apply_feedback(_training_log("ok", 40.0), _state())
    assert a["working_loads"] == b["working_loads"]


# --- builder / composer / adhoc ---------------------------------------------

def _catalog():
    return {"weighted_pullup": {"id": "weighted_pullup", "load_model": "total_load",
                                "prescription_defaults": {"sets": 4, "reps": 3}}}


def test_builder_never_proposes_the_2rm():
    state = _state()
    state["working_loads"]["entries"] = [{"key": "weighted_pullup", "exercise_id": "weighted_pullup",
                                          "last_external_load_kg": 45.0, "next_external_load_kg": 45.0,
                                          "updated_at": "2026-09-24"}]
    p = propose_exercise_prescription("weighted_pullup", _catalog(), state, "strength_power", today="2026-10-04")
    assert p["load_kg"] == 28.5
    assert p["last_logged"]["load_kg"] == 45.0  # the true last value is still shown


def test_adhoc_anchor_uses_the_2rm_reference():
    target = weighted_pullup_target(_state(), "strength_power", "medium")
    assert anchor_adhoc_load(_catalog()["weighted_pullup"], _state(), "strength_power") == target["external"]


# --- router attaches the prescribed reps ------------------------------------

def test_router_attaches_prescribed_reps_from_week_plan():
    state = {"week_plans": {"2026-09-28": {"weeks": [{"days": [{"date": "2026-10-04", "sessions": [{
        "session_id": "custom_cs_x",
        "exercises": [{"exercise_id": "weighted_pullup", "reps": 3, "sets": 4}],
    }]}]}]}}}
    log = {"actual": {"exercise_feedback_v1": [{"exercise_id": "weighted_pullup"}, {"exercise_id": "dip"}]}}
    _attach_prescribed_reps(log, state, "2026-10-04", "custom_cs_x")
    items = log["actual"]["exercise_feedback_v1"]
    assert items[0]["prescribed_reps"] == 3
    assert "prescribed_reps" not in items[1]


def test_router_does_not_override_client_reps():
    state = {"custom_sessions": [{"id": "cs_x", "exercises": [{"exercise_id": "weighted_pullup", "reps": 3}]}]}
    log = {"actual": {"exercise_feedback_v1": [{"exercise_id": "weighted_pullup", "reps": 5}]}}
    _attach_prescribed_reps(deepcopy(log), state, "2026-10-04", "custom_cs_x")
    _attach_prescribed_reps(log, state, "2026-10-04", "custom_cs_x")
    assert log["actual"]["exercise_feedback_v1"][0] == {"exercise_id": "weighted_pullup", "reps": 5}


# --- workflow audit findings (same bug class, other exercises) --------------

def _inject_one(state, ex_id, prescription=None, date="2026-10-04"):
    day = {"date": date, "sessions": [{"session_id": "s", "intent": "strength", "tags": {},
           "exercise_instances": [{"exercise_id": ex_id, "prescription": prescription or {}}]}]}
    return inject_targets(day, state)["sessions"][0]["exercise_instances"][0].get("suggested") or {}


def test_pure_test_exercises_keep_no_training_memory():
    for ex_id in ("test_repeater_7_3_to_failure", "lp_repeater_test"):
        log = {"date": "2026-10-04", "session_id": "test_x", "actual": {"exercise_feedback_v1": [{
            "exercise_id": ex_id, "completed": True, "feedback_label": "hard",
            "used_total_load_kg": 69.5, "used_external_load_kg": 24.0, "hand": "right"}]}}
        assert _entries(apply_feedback(log, _state()), ex_id) == []


def test_weighted_chinup_follows_the_pullup_reference_not_the_finger_max():
    sug = _inject_one(_state(), "weighted_chinup", {"sets": 4, "reps": 5})
    assert sug["load_source"] == "pullup_2rm_reference"
    assert sug["suggested_external_load_kg"] == 28.5
    assert sug["suggested_rep_scheme"] == "4x5"


def test_non_edge_total_load_gets_no_finger_max_suggestion():
    for ex_id in ("weighted_dip", "suitcase_carry", "pinch_block_training", "one_arm_hang_assisted"):
        sug = _inject_one(_state(), ex_id, {"sets": 3, "reps": 4})
        assert "suggested_total_load_kg" not in sug, ex_id


def test_aerobic_hangs_use_their_catalog_intensity():
    # 116 kg max × 45% = 52 kg total → assisted hang, not a near-max load.
    sug = _inject_one(_state(), "sub_max_capacity_hang", {"sets": 4, "work_seconds": 35})
    assert sug["suggested_total_load_kg"] == 52.0


def test_light_prehab_cold_start_is_not_twelve_kg():
    sug = _inject_one(_state(), "dumbbell_external_rotation", {"sets": 3, "reps": 15})
    assert sug["suggested_external_load_kg"] == 1.5


def test_body_part_picker_uses_reference_and_freshness_gate():
    from backend.engine.body_part_picker import apply_resolver_light
    state = _state()
    state["working_loads"]["entries"] = [
        {"key": "weighted_pullup", "exercise_id": "weighted_pullup", "next_external_load_kg": 45.0,
         "next_total_load_kg": 123.0, "updated_at": "2026-09-24"},
        {"key": "max_hang_5s", "exercise_id": "max_hang_5s", "next_external_load_kg": 46.0,
         "next_total_load_kg": 123.0, "updated_at": "2026-03-17"},
    ]
    wp = apply_resolver_light({"id": "weighted_pullup", "load_model": "total_load",
                               "prescription_defaults": {"sets": 4, "reps": 3}}, state, "2026-10-04")
    assert wp["suggested_external_load_kg"] == 28.5
    mh = apply_resolver_light({"id": "max_hang_5s", "load_model": "total_load",
                               "prescription_defaults": {"sets": 5, "work_seconds": 5}}, state, "2026-10-04")
    assert mh.get("suggested_external_load_kg") != 46.0
    assert mh["load_source"] != "working_loads"


def test_coach_prompt_never_prints_the_2rm_as_training_load():
    from backend.coach.prompt_builder import _baselines_section
    state = _state()
    state["working_loads"]["entries"] = [{"key": "weighted_pullup", "exercise_id": "weighted_pullup",
                                          "next_external_load_kg": 45.0, "next_total_load_kg": 123.0,
                                          "updated_at": "2026-09-24"}]
    text = _baselines_section(state)
    line = next(l for l in text.splitlines() if "Working load: weighted_pullup" in l)
    assert "45.0 kg" not in line and "2RM" in line


def test_composer_scales_down_for_more_reps_only():
    from backend.coach.session_composer import _scale_load_for_reps
    bench = {"id": "bench_press", "load_model": "external_load", "prescription_defaults": {"reps": 4}}
    assert _scale_load_for_reps(34.5, bench, 12) < 34.5
    assert _scale_load_for_reps(34.5, bench, 3) == 34.5
    hang = {"id": "repeater_hang_7_3", "load_model": "total_load", "prescription_defaults": {"reps": 6}}
    assert _scale_load_for_reps(10.0, hang, 12) == 10.0


# --- review findings ---------------------------------------------------------

def test_test_log_without_a_result_keeps_the_rebase():
    state = apply_feedback(_training_log("ok", 45.0), _state())
    ref = pullup_reference_2rm(state)
    log = _test_log("weighted_pullup")  # no load: skipped/aborted
    log["date"] = "2026-10-10"
    assert pullup_reference_2rm(apply_feedback(log, state)) == ref


def test_backdated_log_does_not_move_a_newer_rebase():
    state = apply_feedback(_training_log("ok", 45.0, date="2026-10-04"), _state())
    ref = pullup_reference_2rm(state)
    for label in ("ok", "hard"):
        old = apply_feedback(_training_log(label, 30.0, date="2026-10-01"), state)
        assert pullup_reference_2rm(old) == ref


def test_same_log_twice_rebases_once():
    once = apply_feedback(_training_log("hard", 30.0), _state())
    twice = apply_feedback(_training_log("hard", 30.0), once)
    assert pullup_reference_2rm(twice) == pullup_reference_2rm(once)


def test_max_hang_test_resets_the_streaks():
    state = _state()
    state["progression_counters"] = {"max_hang_5s_hard_streak": 2, "max_hang_5s_easy_streak": 0}
    updated = apply_feedback(_test_log("max_hang_7s", used_total_load_kg=118.0), state)
    assert updated["progression_counters"]["max_hang_5s_hard_streak"] == 0


def test_untested_baseline_still_trusts_legacy_memory():
    state = _state()
    state["baselines"]["pulling"]["source"] = "estimated_from_assessment"
    state["working_loads"]["entries"] = [{"key": "weighted_pullup", "exercise_id": "weighted_pullup",
                                          "next_total_load_kg": 115.0, "updated_at": "2026-10-01"}]
    assert pullup_reference_2rm(state) > 123.0


def test_remembered_chinup_load_does_not_override_the_reference():
    state = _state()
    state["working_loads"]["entries"] = [{"key": "weighted_chinup", "exercise_id": "weighted_chinup",
                                          "next_external_load_kg": 45.0, "updated_at": "2026-10-01"}]
    sug = _inject_one(state, "weighted_chinup", {"sets": 4, "reps": 5})
    assert sug["suggested_external_load_kg"] == 28.5


def test_router_reads_planned_resolved_instances():
    state = {"week_plans": {"2026-09-28": {"weeks": [{"days": [{"date": "2026-10-01", "sessions": [{
        "session_id": "pulling_strength_home",
        "resolved": {"resolved_session": {"exercise_instances": [
            {"exercise_id": "weighted_pullup", "prescription": {"sets": 4, "reps": 4}}]}},
    }]}]}]}}}
    log = {"actual": {"exercise_feedback_v1": [{"exercise_id": "weighted_pullup"}]}}
    _attach_prescribed_reps(log, state, "2026-10-01", "pulling_strength_home")
    assert log["actual"]["exercise_feedback_v1"][0]["prescribed_reps"] == 4


def test_composer_scales_pullup_on_total_load():
    from backend.coach.session_composer import _scale_load_for_reps
    wp = {"id": "weighted_pullup", "load_model": "total_load", "prescription_defaults": {"reps": 3}}
    on_total = _scale_load_for_reps(28.5, wp, 6, BW)
    on_external = _scale_load_for_reps(28.5, wp, 6, 0.0)
    assert on_total < on_external
