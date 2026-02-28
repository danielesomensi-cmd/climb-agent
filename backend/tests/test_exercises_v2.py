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
    assert len(exercise_list) == 148


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


# --- grade_ref / grade_offset validation ---

VALID_GRADE_REFS = {"boulder_max_rp", "boulder_max_os", "lead_max_os", "lead_max_rp"}

CAMPUS_IDS = {
    "pangullich_ladders_easy", "campus_laddering_feet_off",
    "campus_laddering_feet_on", "campus_bumps", "campus_double_dyno",
}


def test_grade_relative_non_campus_have_grade_ref(exercise_list):
    """All grade_relative exercises except campus board must have grade_ref."""
    for e in exercise_list:
        if e.get("load_model") != "grade_relative":
            continue
        if e["id"] in CAMPUS_IDS:
            continue
        pd = e.get("prescription_defaults", {})
        assert pd.get("grade_ref") is not None, (
            f"{e['id']} is grade_relative but missing grade_ref"
        )


def test_grade_ref_canonical_values(exercise_list):
    """grade_ref must be one of the 4 canonical values when present."""
    for e in exercise_list:
        pd = e.get("prescription_defaults", {})
        gr = pd.get("grade_ref")
        if gr is None:
            continue
        assert gr in VALID_GRADE_REFS, (
            f"{e['id']} has invalid grade_ref: {gr}"
        )


def test_grade_offset_range(exercise_list):
    """grade_offset must be int in [-6, 1] when present."""
    for e in exercise_list:
        pd = e.get("prescription_defaults", {})
        go = pd.get("grade_offset")
        if go is None:
            continue
        assert isinstance(go, int), f"{e['id']} grade_offset is not int: {type(go)}"
        assert -6 <= go <= 1, f"{e['id']} grade_offset out of range: {go}"


def test_grade_ref_implies_grade_offset(exercise_list):
    """If grade_ref is set, grade_offset must also be set (and vice versa)."""
    for e in exercise_list:
        pd = e.get("prescription_defaults", {})
        gr = pd.get("grade_ref")
        go = pd.get("grade_offset")
        if gr is not None:
            assert go is not None, f"{e['id']} has grade_ref but no grade_offset"
        if go is not None:
            assert gr is not None, f"{e['id']} has grade_offset but no grade_ref"


def test_timed_rep_exercises_have_correct_volume(exercise_list):
    """Exercises with reps > 1 AND work_seconds > 0 must have numeric reps and sets.

    The guided session timer loops sets × reps work intervals.
    This test verifies the data contract: sets and reps are both positive integers
    so the timer can compute total_work_intervals = sets × reps.
    """
    timed_rep_exercises = []
    for e in exercise_list:
        pd = e.get("prescription_defaults", {})
        reps = pd.get("reps")
        work_s = pd.get("work_seconds")
        if reps is not None and isinstance(reps, int) and reps > 1 and work_s and work_s > 0:
            timed_rep_exercises.append(e)

    # At least density_hangs, repeater_hang_7_3, repeater_15_15 must be in this set
    ids = {e["id"] for e in timed_rep_exercises}
    assert "density_hangs" in ids
    assert "repeater_hang_7_3" in ids
    assert "repeater_15_15" in ids

    for e in timed_rep_exercises:
        pd = e["prescription_defaults"]
        sets = pd.get("sets")
        reps = pd.get("reps")
        work_s = pd.get("work_seconds")
        rest_sets = pd.get("rest_between_sets_seconds")

        assert isinstance(sets, int) and sets >= 1, f"{e['id']} sets must be positive int"
        assert isinstance(reps, int) and reps >= 2, f"{e['id']} reps must be >= 2"
        assert isinstance(work_s, (int, float)) and work_s > 0, f"{e['id']} work_seconds must be > 0"
        assert rest_sets is not None and rest_sets > 0, f"{e['id']} must have rest_between_sets_seconds"

        total_intervals = sets * reps
        assert total_intervals >= 4, (
            f"{e['id']}: sets={sets} × reps={reps} = {total_intervals} intervals — "
            "seems too low for a timed-rep protocol"
        )


def test_density_hangs_protocol(exercise_map):
    """density_hangs must match Tyler Nelson protocol: 3 grips × 3 hangs, 90s rep rest."""
    dh = exercise_map["density_hangs"]
    pd = dh["prescription_defaults"]
    assert pd["sets"] == 3
    assert pd["reps"] == 3
    assert pd["work_seconds"] == 30
    assert pd["rest_between_reps_seconds"] == 90, "Nelson protocol: 90s rest between hangs"
    assert pd["rest_between_sets_seconds"] == 180


# --- B56: heavy conditioning muscle group expansion ---

B56_EXERCISE_IDS = {"dumbbell_bench_press", "bicep_curl", "lateral_raise"}


def test_b56_exercises_exist(exercise_map):
    """B56 exercises must be present in the catalog."""
    for eid in B56_EXERCISE_IDS:
        assert eid in exercise_map, f"B56 exercise {eid} not found in catalog"


def test_b56_exercises_patterns(exercise_map):
    """B56 exercises must have the correct new patterns."""
    assert exercise_map["bicep_curl"]["pattern"] == "elbow_flexion"
    assert exercise_map["lateral_raise"]["pattern"] == "shoulder_isolation"
    assert exercise_map["dumbbell_bench_press"]["pattern"] == "push"
