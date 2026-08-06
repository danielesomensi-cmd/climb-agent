"""A269 — per-axis provenance (`profile_source`) and `profile_scoring_version`.

The brief's hard guarantee is that A269 changes **no score**: it only records
where each score came from. `test_scoring_is_unchanged_on_production_corpus` is
what makes that a fact rather than an intention.
"""
import json
from pathlib import Path

import pytest

from backend.engine.assessment_v1 import (
    PROFILE_SCORING_VERSION,
    SOURCE_ESTIMATED,
    SOURCE_MEASURED,
    SOURCE_PARTIAL,
    compute_assessment_profile,
    compute_assessment_profile_with_source,
    compute_profile_source,
)
from backend.engine.migrations.m002_backfill_profile_source import migrate
from backend.engine.state_checks import is_macrocycle_stale

AXES = (
    "finger_strength",
    "pulling_strength",
    "power_endurance",
    "technique",
    "endurance",
)

_FIXTURE = Path(__file__).parent / "fixtures" / "a269_production_profiles.json"


@pytest.fixture(scope="module")
def corpus():
    """The 18 real production assessments, scoring inputs only."""
    return json.loads(_FIXTURE.read_text())


# ---------------------------------------------------------------------------
# The guarantee
# ---------------------------------------------------------------------------

def test_scoring_is_unchanged_on_production_corpus(corpus):
    """Every one of the 18 real profiles scores exactly as before A269.

    B321's lesson: pin the actual production payload, not a synthetic one.
    """
    assert len(corpus) == 18
    for user in corpus:
        got = compute_assessment_profile(user["assessment"], user["goal"])
        assert got == user["expected_profile"], f"scoring moved for {user['uid']}"


def test_with_source_returns_the_same_profile(corpus):
    """The new entry point cannot drift from the old one."""
    for user in corpus:
        profile, source = compute_assessment_profile_with_source(
            user["assessment"], user["goal"]
        )
        assert profile == compute_assessment_profile(user["assessment"], user["goal"])
        assert set(source) == set(AXES)


def test_no_user_becomes_stale_from_provenance_alone(corpus):
    """A269 must not raise the "your profile changed" banner for anyone.

    `is_macrocycle_stale` compares axis scores against the snapshot; provenance
    is not an axis, so adding it must leave every user non-stale.
    """
    for user in corpus:
        profile = compute_assessment_profile(user["assessment"], user["goal"])
        state = {
            "assessment": {
                **user["assessment"],
                "profile": profile,
                "profile_source": compute_profile_source(user["assessment"]),
                "profile_scoring_version": PROFILE_SCORING_VERSION,
            },
            "macrocycle": {"assessment_snapshot": dict(profile)},
        }
        assert is_macrocycle_stale(state) is False, user["uid"]


def test_three_loading_pin_profiles_are_already_drifted_from_A266(corpus):
    """Documents a PRE-EXISTING drift A269 deliberately does not disturb.

    Three profiles were stored before A266 taught the finger axis to read
    `lp_max_lift_*`, so their stored score differs from what today's code would
    compute (51→100, 51→69, 54→71). A269 does **not** force a recompute — the
    brief proposed adding `tests_source` to the profile fingerprint and that was
    dropped precisely here, because it would have silently applied A266 to
    `e60d7a0c`, whose recompute Daniele explicitly withheld (A266-P1).

    This test exists so the drift stays visible and cannot be "fixed" by
    accident: the next legitimate recompute (the user editing any assessment
    input) will apply A266 to them, and that is a product decision, not a bug.
    """
    drifted = {
        u["uid"] for u in corpus if u["stored_profile"] != u["expected_profile"]
    }
    assert drifted == {"e60d7a0c", "d7f6083e", "79fadc50"}
    for user in corpus:
        if user["uid"] in drifted:
            # The drift is confined to the finger axis.
            for axis in AXES:
                if axis == "finger_strength":
                    continue
                assert user["stored_profile"][axis] == user["expected_profile"][axis]


# ---------------------------------------------------------------------------
# Provenance rules
# ---------------------------------------------------------------------------

def test_every_axis_always_has_a_value():
    source = compute_profile_source({})
    assert set(source) == set(AXES)
    assert all(v == SOURCE_ESTIMATED for v in source.values())


def test_values_present_but_not_measured_read_as_estimated():
    """The distinction D214 exists for: present != measured.

    An onboarding grade-estimate populates `tests` and leaves `tests_source`
    empty. Reading `tests` would call that a measurement.
    """
    source = compute_profile_source(
        {
            "tests": {
                "max_hang_20mm_7s_total_kg": 122,
                "weighted_pullup_1rm_total_kg": 127.8,
                "repeater_7_3_max_sets_20mm": 25,
            },
            "tests_source": {},
        }
    )
    assert source["finger_strength"] == SOURCE_ESTIMATED
    assert source["pulling_strength"] == SOURCE_ESTIMATED
    assert source["power_endurance"] == SOURCE_ESTIMATED


@pytest.mark.parametrize(
    "key",
    [
        "max_hang_20mm_7s_total_kg",
        "max_hang_20mm_5s_total_kg",
        "lp_max_lift_5s_left_kg",
        "lp_max_lift_5s_right_kg",
    ],
)
def test_any_finger_test_makes_the_axis_measured(key):
    """A266: a loading-pin user is measured, even though the value is converted."""
    source = compute_profile_source({"tests_source": {key: "measured"}})
    assert source["finger_strength"] == SOURCE_MEASURED


def test_pulling_measured_from_a_direct_1rm():
    source = compute_profile_source(
        {"tests_source": {"weighted_pullup_1rm_total_kg": "measured"}}
    )
    assert source["pulling_strength"] == SOURCE_MEASURED


def test_pulling_measured_from_the_brzycki_pair():
    """D38: a submaximal pair is a real measurement the axis actually reads."""
    source = compute_profile_source(
        {
            "tests_source": {
                "pullup_submaximal_reps": "measured",
                "pullup_submaximal_load_kg": "measured",
            }
        }
    )
    assert source["pulling_strength"] == SOURCE_MEASURED


def test_half_a_brzycki_pair_is_not_a_measurement():
    source = compute_profile_source(
        {"tests_source": {"pullup_submaximal_reps": "measured"}}
    )
    assert source["pulling_strength"] == SOURCE_ESTIMATED


def test_a_2rm_does_not_make_pulling_measured():
    """`week.py` accepts a 2RM for retest freshness; the axis never reads it.

    Provenance follows what the scoring function consumes, not what the planner
    considers a fresh test — otherwise an axis scored from a grade estimate
    would claim to be measured.
    """
    source = compute_profile_source(
        {"tests_source": {"weighted_pullup_2rm_total_kg": "measured"}}
    )
    assert source["pulling_strength"] == SOURCE_ESTIMATED


def test_repeater_makes_pe_partial_never_measured():
    """The repeater carries 40% of PE; the rest is the gap and self-eval."""
    source = compute_profile_source(
        {"tests_source": {"repeater_7_3_max_sets_20mm": "measured"}}
    )
    assert source["power_endurance"] == SOURCE_PARTIAL


def test_technique_is_always_estimated():
    """No test feeds it — not "none today", none by construction."""
    everything_measured = {
        "tests_source": {
            "max_hang_20mm_7s_total_kg": "measured",
            "weighted_pullup_1rm_total_kg": "measured",
            "repeater_7_3_max_sets_20mm": "measured",
            "max_hang_duration_20mm_seconds": "measured",
        }
    }
    assert compute_profile_source(everything_measured)["technique"] == SOURCE_ESTIMATED


def test_endurance_is_partial_through_either_measured_input():
    """Duration directly, or the repeater flowing in through PE (0.8x)."""
    via_duration = compute_profile_source(
        {"tests_source": {"max_hang_duration_20mm_seconds": "measured"}}
    )
    assert via_duration["endurance"] == SOURCE_PARTIAL

    via_repeater = compute_profile_source(
        {"tests_source": {"repeater_7_3_max_sets_20mm": "measured"}}
    )
    assert via_repeater["endurance"] == SOURCE_PARTIAL

    assert compute_profile_source({})["endurance"] == SOURCE_ESTIMATED


def test_a_malformed_tests_source_does_not_crash():
    assert compute_profile_source({"tests_source": None})["technique"] == SOURCE_ESTIMATED
    assert compute_profile_source({"tests_source": []})["technique"] == SOURCE_ESTIMATED


def test_production_corpus_provenance_distribution(corpus):
    """The number that justifies the field: most axes are not measurements."""
    counts = {axis: {} for axis in AXES}
    for user in corpus:
        for axis, value in compute_profile_source(user["assessment"]).items():
            counts[axis][value] = counts[axis].get(value, 0) + 1

    assert counts["technique"] == {SOURCE_ESTIMATED: 18}
    assert counts["finger_strength"][SOURCE_ESTIMATED] == 12
    assert counts["pulling_strength"][SOURCE_ESTIMATED] == 13
    assert counts["power_endurance"][SOURCE_PARTIAL] == 1
    assert SOURCE_MEASURED not in counts["power_endurance"]
    assert SOURCE_MEASURED not in counts["endurance"]


# ---------------------------------------------------------------------------
# Migration m002
# ---------------------------------------------------------------------------

def _legacy_state():
    return {
        "assessment": {
            "profile": {a: 50 for a in AXES},
            "tests": {"max_hang_20mm_7s_total_kg": 122},
            "tests_source": {"max_hang_20mm_7s_total_kg": "measured"},
        }
    }


def test_migration_fills_both_fields():
    state = _legacy_state()
    assert migrate(state) is True
    assessment = state["assessment"]
    assert assessment["profile_source"]["finger_strength"] == SOURCE_MEASURED
    assert assessment["profile_scoring_version"] == PROFILE_SCORING_VERSION


def test_migration_is_idempotent():
    state = _legacy_state()
    assert migrate(state) is True
    before = json.dumps(state, sort_keys=True)
    assert migrate(state) is False
    assert json.dumps(state, sort_keys=True) == before


def test_migration_never_downgrades_an_existing_entry():
    state = _legacy_state()
    state["assessment"]["profile_source"] = {"finger_strength": SOURCE_MEASURED}
    state["assessment"]["profile_scoring_version"] = "profile_v99"
    assert migrate(state) is False
    assert state["assessment"]["profile_source"] == {"finger_strength": SOURCE_MEASURED}
    assert state["assessment"]["profile_scoring_version"] == "profile_v99"


def test_migration_skips_a_state_with_no_profile():
    for state in ({}, {"assessment": {}}, {"assessment": {"profile": {}}}, None, "nope"):
        assert migrate(state) is False


def test_migration_reads_the_sidecar_m001_populates():
    """Ordering guard: m002 must run AFTER m001.

    A legacy user has `tests` but no `tests_source` until m001 infers it. Run in
    that state, m002 would mark a genuinely measured axis `estimated`.
    """
    pre_m001 = {
        "assessment": {
            "profile": {a: 50 for a in AXES},
            "tests": {"max_hang_20mm_7s_total_kg": 122},
        }
    }
    migrate(pre_m001)
    assert pre_m001["assessment"]["profile_source"]["finger_strength"] == SOURCE_ESTIMATED

    post_m001 = _legacy_state()
    migrate(post_m001)
    assert post_m001["assessment"]["profile_source"]["finger_strength"] == SOURCE_MEASURED


def test_migration_runs_after_m001_in_load_state():
    """The order is enforced by source position, so pin it."""
    import inspect

    from backend.api import deps

    src = inspect.getsource(deps.load_state)
    assert src.index("m001_backfill_tests_source") < src.index("m002_backfill_profile_source")


# ---------------------------------------------------------------------------
# End to end — the field has to survive an actual write, not just a unit call
# ---------------------------------------------------------------------------

def _onboarding_payload():
    return {
        "profile": {"name": "A269", "age": 30, "weight_kg": 76, "height_cm": 178},
        "experience": {"climbing_years": 10, "structured_training_years": 3},
        "grades": {"lead_max_rp": "8a", "lead_max_os": "7a+"},
        "goal": {
            "goal_type": "lead_grade",
            "discipline": "lead",
            "target_grade": "8a+",
            "target_style": "redpoint",
            "current_grade": "8a",
            "deadline": "2026-12-01",
        },
        "self_eval": {
            "primary_weakness": "technique_errors",
            "secondary_weakness": "pump_too_early",
        },
        "tests": {"max_hang_20mm_7s_total_kg": 122},
        "limitations": [],
        "equipment": {"home_enabled": True, "home": ["hangboard_20mm"], "gyms": []},
        "availability": {
            "mon": {"evening": {"available": True, "preferred_location": "home"}},
            "wed": {"evening": {"available": True, "preferred_location": "home"}},
            "fri": {"evening": {"available": True, "preferred_location": "home"}},
        },
        "planning_prefs": {"target_training_days_per_week": 3, "hard_day_cap_per_week": 2},
        "preferences": {"finger_training_device": "hangboard"},
        "trips": [],
        "outdoor_spots": [],
    }


def test_onboarding_complete_persists_provenance():
    from fastapi.testclient import TestClient

    from backend.api.main import app

    client = TestClient(app)
    assert client.post("/api/onboarding/complete", json=_onboarding_payload()).status_code == 200

    assessment = client.get("/api/state").json()["assessment"]
    assert assessment["profile_scoring_version"] == PROFILE_SCORING_VERSION
    source = assessment["profile_source"]
    # The one test entered is a max hang, so exactly one axis is measured.
    assert source["finger_strength"] == SOURCE_MEASURED
    assert source["pulling_strength"] == SOURCE_ESTIMATED
    assert source["technique"] == SOURCE_ESTIMATED


def test_assessment_compute_persists_provenance():
    from fastapi.testclient import TestClient

    from backend.api.main import app

    client = TestClient(app)
    assert client.post("/api/onboarding/complete", json=_onboarding_payload()).status_code == 200

    before = client.get("/api/state").json()["assessment"]["profile"]
    assert client.post("/api/assessment/compute", json={}).status_code == 200

    assessment = client.get("/api/state").json()["assessment"]
    assert assessment["profile"] == before, "recompute must not move a score"
    assert assessment["profile_source"]["finger_strength"] == SOURCE_MEASURED
    assert assessment["profile_scoring_version"] == PROFILE_SCORING_VERSION
