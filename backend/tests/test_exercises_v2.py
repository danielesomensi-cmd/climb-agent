"""Tests for exercises.json v2.1 schema validation."""

import json
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXERCISES_PATH = os.path.join(REPO_ROOT, "backend", "catalog", "exercises", "v1", "exercises.json")


@pytest.fixture(scope="module")
def exercises():
    with open(EXERCISES_PATH) as f:
        data = json.load(f)
    return data


@pytest.fixture(scope="module")
def exercise_list(exercises):
    return exercises["exercises"]


@pytest.fixture(scope="module")
def exercise_map(exercise_list):
    return {e["id"]: e for e in exercise_list}


def test_version_is_2_1(exercises):
    assert exercises["version"] == "2.1"


def test_total_count(exercise_list):
    assert len(exercise_list) == 135


def test_all_have_canonical_prescription_fields(exercise_list):
    canonical = {"sets", "reps", "work_seconds", "rest_between_reps_seconds", "rest_between_sets_seconds"}
    for e in exercise_list:
        pd = e.get("prescription_defaults", {})
        pd_keys = {k for k in pd.keys() if k != "notes"}
        missing = canonical - pd_keys
        assert not missing, f"{e['id']} missing prescription fields: {missing}"


def test_all_have_root_fields(exercise_list):
    for e in exercise_list:
        assert "description" in e, f"{e['id']} missing description"
        assert "cues" in e, f"{e['id']} missing cues"
        assert "video_url" in e, f"{e['id']} missing video_url"
        assert "load_model" in e, f"{e['id']} missing load_model"


VALID_LOAD_MODELS = {"total_load", "external_load", "grade_relative", "bodyweight_only", None}


def test_load_model_values(exercise_list):
    for e in exercise_list:
        lm = e.get("load_model")
        assert lm in VALID_LOAD_MODELS, f"{e['id']} has invalid load_model: {lm}"


HANGBOARD_IDS = {
    "max_hang_5s", "max_hang_7s", "max_hang_ladder",
    "repeater_hang_7_3", "density_hangs",
    "min_edge_hang", "dead_hang_easy", "long_duration_hang",
    "one_arm_hang_assisted", "pinch_block_training",
    # New hangboard exercises
    "max_hang_10s", "horst_7_53", "repeater_15_15",
    "lopez_subhangs", "critical_force_test", "med_test",
}


def test_hangboard_have_attributes(exercise_map):
    for eid in HANGBOARD_IDS:
        if eid not in exercise_map:
            continue
        e = exercise_map[eid]
        attrs = e.get("attributes", {})
        assert "edge_mm" in attrs, f"{eid} missing attributes.edge_mm"
        assert "grip" in attrs, f"{eid} missing attributes.grip"


TECHNIQUE_IDS = {
    "silent_feet_drill", "no_readjust_drill", "downclimbing_drill",
    "slow_climbing", "flag_practice", "gym_technique_boulder_drills",
    "pangullich_ladders_easy",
    # New technique drills
    "sticky_feet", "foothold_stare", "tap_and_place",
    "hover_hands", "hip_rotation_drill", "straight_arms",
    "sloth_monkey", "breathing_awareness", "one_hand_climbing",
    "three_limb_drill",
}


def test_technique_have_focus(exercise_map):
    for eid in TECHNIQUE_IDS:
        if eid not in exercise_map:
            continue
        e = exercise_map[eid]
        assert "focus" in e, f"{eid} missing focus field"


NEW_EXERCISE_IDS = {
    "max_hang_10s", "horst_7_53", "repeater_15_15", "lopez_subhangs",
    "critical_force_test", "med_test",
    "campus_touches", "campus_max_ladders", "campus_switches", "campus_sprint_endurance",
    "emom_bouldering", "otm_bouldering", "linked_boulders_circuit",
    "arc_training_progressive", "threshold_long_intervals", "regeneration_climbing",
    "sticky_feet", "foothold_stare", "tap_and_place", "hover_hands",
    "hip_rotation_drill", "straight_arms", "sloth_monkey", "breathing_awareness",
    "one_hand_climbing", "three_limb_drill",
}


def test_new_exercises_exist(exercise_map):
    for eid in NEW_EXERCISE_IDS:
        assert eid in exercise_map, f"New exercise {eid} not found in catalog"


def test_no_old_prescription_fields(exercise_list):
    """Ensure no exercises still have legacy field names in prescription_defaults."""
    old_fields = {
        "hang_seconds", "hold_seconds", "hold_seconds_range",
        "duration_seconds", "duration_seconds_range", "duration_min_range",
        "total_minutes_range", "sets_range", "reps_range", "reps_per_set_range",
        "rest_seconds", "rest_seconds_range", "protocol", "steps", "rounds",
        "tempo", "intensity_pct_of_total_load", "setup_fields", "intensity_notes",
    }
    for e in exercise_list:
        pd = e.get("prescription_defaults", {})
        found = old_fields & set(pd.keys())
        assert not found, f"{e['id']} still has old fields: {found}"


def test_no_duplicate_ids(exercise_list):
    ids = [e["id"] for e in exercise_list]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {[x for x in ids if ids.count(x) > 1]}"


def test_intensity_pct_only_in_attributes(exercise_list):
    """intensity_pct must be in attributes, not in prescription_defaults."""
    for e in exercise_list:
        pd = e.get("prescription_defaults", {})
        assert "intensity_pct_of_total_load" not in pd, f"{e['id']} still has intensity_pct in prescription_defaults"
        assert "intensity_pct" not in pd, f"{e['id']} has intensity_pct in prescription_defaults"
