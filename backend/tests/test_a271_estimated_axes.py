"""A271 — a self-declaration may not move a domain weight (framing B).

Two residuals survived A270 and were pinned by its property test: a
`cant_manage_rests` weakness moved `volume_climbing` by 3.5 pp through the
endurance axis, and for a user with no tests at all — 8 of 18 production
profiles — one self-declaration moved a deload weight by 8.3 pp, more than the
+7.5 pp technique distortion D260 called the largest in the engine.

Framing B removes the self-eval penalty from any axis with nothing measured
under it, while leaving grade-derived estimates in the weights: a grade the
athlete reported is a weak signal, a self-diagnosis is not a signal at all.
"""
import json
from pathlib import Path

import pytest

from backend.engine.assessment_v1 import (
    PROFILE_SCORING_VERSION,
    SOURCE_ESTIMATED,
    SOURCE_MEASURED,
    _AXIS_WEAKNESS_PENALTIES,
    compute_assessment_profile,
    compute_assessment_profile_with_source,
    compute_profile_source,
)
from backend.engine.migrations.m002_backfill_profile_source import migrate as m002
from backend.engine.migrations.m003_backfill_tests_source_from_values import (
    _TEST_KEYS,
    migrate as m003,
)

AXES = (
    "finger_strength",
    "pulling_strength",
    "power_endurance",
    "technique",
    "endurance",
)
_FIXTURE = Path(__file__).parent / "fixtures" / "a269_production_profiles.json"

_ALL_WEAKNESSES = sorted(
    {w for groups in _AXIS_WEAKNESS_PENALTIES.values() for g in groups for w in g[0]}
)


@pytest.fixture(scope="module")
def corpus():
    return json.loads(_FIXTURE.read_text())


def _assessment(**over):
    base = {
        "body": {"weight_kg": 76},
        "experience": {"climbing_years": 10},
        "grades": {"lead_max_rp": "8a", "lead_max_os": "7a+"},
        "tests": {},
        "tests_source": {},
        "self_eval": {},
    }
    base.update(over)
    return base


GOAL = {"target_grade": "8a+", "current_grade": "8a", "goal_type": "lead_grade"}


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("weakness", _ALL_WEAKNESSES)
def test_no_weakness_moves_an_unmeasured_axis(weakness):
    """The whole vocabulary, swept. Technique is the one legitimate exception:
    it IS the self-report (`self_reported`), and it drives nothing."""
    reference = compute_assessment_profile(_assessment(), GOAL)
    with_weakness = compute_assessment_profile(
        _assessment(self_eval={"primary_weakness": weakness}), GOAL
    )
    for axis in AXES:
        if axis == "technique":
            continue
        assert with_weakness[axis] == reference[axis], f"{weakness} moved {axis}"


def test_a_weakness_still_bites_on_a_measured_axis():
    """Framing B removes the penalty where there is nothing under it, not
    everywhere. Endurance with a measured repeater still responds."""
    measured = _assessment(
        tests={"repeater_7_3_max_sets_20mm": 24},
        tests_source={"repeater_7_3_max_sets_20mm": "measured"},
    )
    neutral = compute_assessment_profile(measured, GOAL)
    with_pump = compute_assessment_profile(
        {**measured, "self_eval": {"primary_weakness": "pump_too_early"}}, GOAL
    )
    assert with_pump["endurance"] < neutral["endurance"]
    assert with_pump["power_endurance"] < neutral["power_endurance"]


def test_the_finger_and_pulling_penalties_are_now_inert_everywhere():
    """They only ever existed in the grade-estimate branch, i.e. exactly when
    the axis was NOT measured. There is no measured branch to keep them in, so
    they are gone rather than moved — inventing one would be a fabrication.

    The mapping stays in `_AXIS_WEAKNESS_PENALTIES`: it still describes what a
    weakness means, and a session-pool rule (A258-style) is the right consumer.
    """
    assert "fingers_give_out" in _AXIS_WEAKNESS_PENALTIES["finger_strength"][0][0]
    reference = compute_assessment_profile(_assessment(), GOAL)
    for weakness in ("fingers_give_out", "weak_on_slopers", "cant_hold_hard_moves"):
        profile = compute_assessment_profile(
            _assessment(self_eval={"primary_weakness": weakness}), GOAL
        )
        assert profile["finger_strength"] == reference["finger_strength"]
        assert profile["pulling_strength"] == reference["pulling_strength"]


def test_a_grade_derived_estimate_still_drives_the_plan():
    """Framing B, not framing A. The counterfactual for A was 12 of 18 users
    left with the bare phase defaults; a grade the athlete reported is a weak
    signal, and weak is not the same as absent.
    """
    weak = compute_assessment_profile(
        _assessment(), {**GOAL, "current_grade": "6c", "target_grade": "8a+"}
    )
    strong = compute_assessment_profile(
        _assessment(), {**GOAL, "current_grade": "8a", "target_grade": "8a+"}
    )
    assert weak["finger_strength"] < strong["finger_strength"]
    assert weak["pulling_strength"] < strong["pulling_strength"]


def test_scoring_version():
    assert PROFILE_SCORING_VERSION == "profile_v3_self_report_unweighted"


# ---------------------------------------------------------------------------
# m003 — the prerequisite
# ---------------------------------------------------------------------------

def test_m003_stamps_a_typed_value_as_measured():
    state = {"assessment": {"tests": {"max_hang_20mm_7s_total_kg": 122}}}
    assert m003(state) is True
    assert state["assessment"]["tests_source"]["max_hang_20mm_7s_total_kg"] == "measured"


def test_m003_is_idempotent():
    state = {"assessment": {"tests": {"max_hang_20mm_7s_total_kg": 122}}}
    assert m003(state) is True
    before = json.dumps(state, sort_keys=True)
    assert m003(state) is False
    assert json.dumps(state, sort_keys=True) == before


def test_m003_ignores_empty_values_and_unknown_keys():
    state = {
        "assessment": {
            "tests": {
                "max_hang_20mm_7s_total_kg": None,
                "repeater_7_3_max_sets_20mm": "",
                "some_future_field": 42,
            }
        }
    }
    assert m003(state) is False
    assert not state["assessment"].get("tests_source")


def test_m003_covers_the_four_blind_production_users(corpus):
    """The reason the brief called this a blocking prerequisite.

    `f49678eb`, `d7f6083e`, `79fadc50` and `22080848` had a real finger number
    on file and an empty sidecar — they onboarded before D214. Without m003 a
    provenance-gated rule would have punished them for a bookkeeping gap.
    """
    blind = {"f49678eb", "d7f6083e", "79fadc50", "22080848"}
    seen = set()
    for user in corpus:
        if user["uid"] not in blind:
            continue
        seen.add(user["uid"])
        source = compute_profile_source(user["assessment"])
        assert source["finger_strength"] == SOURCE_MEASURED, user["uid"]
    assert seen == blind


def test_m003_never_changes_a_score(corpus):
    """It touches provenance, never a value."""
    for user in corpus:
        before = compute_assessment_profile(user["assessment"], user["goal"])
        state = {"assessment": json.loads(json.dumps(user["assessment"]))}
        m003(state)
        after = compute_assessment_profile(state["assessment"], user["goal"])
        # Scores may differ only where provenance gates the self-eval penalty,
        # which is the point of the brief — but never on an axis with no
        # weakness declared.
        if not (user["assessment"].get("self_eval") or {}).get("primary_weakness"):
            assert after == before, user["uid"]


def test_m002_recomputes_when_m003_widened_the_sidecar():
    """Ordering + the `force` flag: a `profile_source` derived from a blind
    sidecar must not survive the backfill that un-blinds it."""
    state = {
        "assessment": {
            "profile": {a: 50 for a in AXES},
            "tests": {"max_hang_20mm_7s_total_kg": 122},
        }
    }
    m002(state)  # derived from an empty tests_source
    assert state["assessment"]["profile_source"]["finger_strength"] == SOURCE_ESTIMATED

    grew = m003(state)
    assert grew is True
    assert m002(state, force=grew) is True
    assert state["assessment"]["profile_source"]["finger_strength"] == SOURCE_MEASURED


def test_migration_chain_order_in_load_state():
    """m001 -> m003 -> m002. Reversed, a measured axis reads as estimated."""
    import inspect

    from backend.api import deps

    src = inspect.getsource(deps.load_state)
    assert (
        src.index("m001_backfill_tests_source")
        < src.index("m003_backfill_tests_source_from_values")
        < src.index("m002_backfill_profile_source")
    )


def test_put_state_stamps_the_sidecar_at_write_time():
    """The live hole A271 found: the settings assessment editor patches
    `assessment.tests` through PUT /api/state and never stamped `tests_source`,
    so every manual correction produced a measured number with no provenance.
    """
    from fastapi.testclient import TestClient

    from backend.api.main import app

    client = TestClient(app)
    client.delete("/api/state")
    r = client.put(
        "/api/state",
        json={"assessment": {"tests": {"max_hang_20mm_7s_total_kg": 118}}},
    )
    assert r.status_code == 200, r.text
    source = client.get("/api/state").json()["assessment"]["tests_source"]
    assert source["max_hang_20mm_7s_total_kg"] == "measured"


def test_put_state_ignores_unknown_test_keys():
    from fastapi.testclient import TestClient

    from backend.api.main import app

    client = TestClient(app)
    client.delete("/api/state")
    client.put("/api/state", json={"assessment": {"tests": {"not_a_test": 1}}})
    source = (client.get("/api/state").json()["assessment"] or {}).get("tests_source") or {}
    assert "not_a_test" not in source
    assert set(source) <= set(_TEST_KEYS)


# ---------------------------------------------------------------------------
# Blast radius on the real profiles
# ---------------------------------------------------------------------------

def test_only_eight_users_move_and_only_on_three_axes(corpus):
    moved = {axis: 0 for axis in AXES}
    users_moved = 0
    for user in corpus:
        v2, v3 = user["expected_profile_v2"], user["expected_profile_v3"]
        deltas = [a for a in AXES if v2[a] != v3[a]]
        if deltas:
            users_moved += 1
        for axis in deltas:
            moved[axis] += 1
    # 7 distinct users, 10 axis-moves: one of them shifts on two axes.
    assert users_moved == 7
    assert moved["finger_strength"] == 3
    assert moved["pulling_strength"] == 3
    assert moved["endurance"] == 4
    # A270 already neutralised these two; A271 must not touch them again.
    assert moved["power_endurance"] == 0
    assert moved["technique"] == 0


def test_the_author_is_untouched(corpus):
    """He has both strength tests measured and no unmeasured-axis weakness that
    A271 gates, so the brief must be a no-op for him."""
    author = next(u for u in corpus if u["uid"] == "7ea9f0ee")
    assert author["expected_profile_v2"] == author["expected_profile_v3"]
    profile, source = compute_assessment_profile_with_source(
        author["assessment"], author["goal"]
    )
    assert profile == author["expected_profile_v3"]
    assert source["finger_strength"] == SOURCE_MEASURED


# ---------------------------------------------------------------------------
# The recompute policy — pinned because it was nearly reported backwards
# ---------------------------------------------------------------------------

def test_a_scoring_change_is_not_retroactive_for_existing_users(corpus):
    """A stored profile survives a scoring change until an INPUT changes.

    `_recompute_profile_if_needed` fingerprints the assessment *inputs*, not the
    scoring version, so shipping A270/A271 does not rescore anyone who was
    already on file: they keep their v1 numbers and their `profile_v1` stamp
    until they edit their body, grades, tests, self-eval or goal — or until an
    explicit `/api/assessment/compute` or `start-new-cycle`.

    This is exactly the "never retroactive" rule the versioning plan states
    (D271 §7, D272 §7), and it is why `profile_scoring_version` exists: the
    population is deliberately mixed, and the field says who is on which rules.
    It is asserted here because nothing else pins it, and because the practical
    consequence is easy to state backwards — no user sees the "your profile
    changed" banner on deploy day.
    """
    import hashlib

    from backend.api.deps import _ensure_profile_fresh

    user = corpus[0]
    assessment, goal = user["assessment"], user["goal"]
    fingerprint = hashlib.md5(
        json.dumps(
            {
                "body": assessment.get("body") or {},
                "grades": assessment.get("grades") or {},
                "tests": assessment.get("tests") or {},
                "self_eval": assessment.get("self_eval") or {},
                "experience": assessment.get("experience") or {},
                "target_grade": goal.get("target_grade"),
                "current_grade": goal.get("current_grade"),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()

    stored = dict(user["stored_profile"])
    state = {
        "assessment": {
            **assessment,
            "profile": stored,
            "_profile_fingerprint": fingerprint,
            "profile_scoring_version": "profile_v1",
        },
        "goal": goal,
    }

    _ensure_profile_fresh(state)
    assert state["assessment"]["profile"] == stored
    assert state["assessment"]["profile_scoring_version"] == "profile_v1"
    # …and the new rules ARE different, so the test is not vacuous.
    assert compute_assessment_profile(assessment, goal) != stored


def test_an_input_change_does_bring_the_new_rules(corpus):
    """The other half: once anything moves, the athlete lands on v3."""
    from backend.api.deps import _ensure_profile_fresh

    user = corpus[0]
    state = {
        "assessment": {**user["assessment"], "profile": dict(user["stored_profile"])},
        "goal": dict(user["goal"]),
    }
    _ensure_profile_fresh(state)  # no fingerprint stored -> recomputes
    assert state["assessment"]["profile"] == user["expected_profile_v3"]
    assert state["assessment"]["profile_scoring_version"] == PROFILE_SCORING_VERSION
