"""A270 — the redpoint − onsight gap is demoted from weight driver to hint.

Research decision D266, analysis D272. The gap is a tactics/style/mental
composite, not a physiological measure, and through Technique & Tactics it was
the largest single plan-shaping lever in the engine (D260 §5: +7.5 pp of
technique weight in EVERY phase, for the author).
"""
import itertools
import json
from pathlib import Path

import pytest

from backend.engine.assessment_v1 import (
    PROFILE_SCORING_VERSION,
    SOURCE_ESTIMATED,
    SOURCE_PARTIAL,
    SOURCE_SELF_REPORTED,
    _AXIS_WEAKNESS_PENALTIES,
    _redpoint_onsight_gap,
    compute_assessment_profile,
    compute_assessment_profile_with_source,
)
from backend.engine.macrocycle_v1 import (
    _BASE_WEIGHTS,
    _BASE_WEIGHTS_BOULDER,
    _adjust_domain_weights,
    _compute_phase_durations,
    _find_weakest_axis,
)
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
    return json.loads(_FIXTURE.read_text())


def _assessment(**over):
    base = {
        "body": {"weight_kg": 76},
        "experience": {"climbing_years": 10},
        "grades": {"lead_max_rp": "8a", "lead_max_os": "7a+"},
        "tests": {},
        "self_eval": {},
    }
    base.update(over)
    return base


GOAL = {"target_grade": "8a+", "current_grade": "8a", "goal_type": "lead_grade"}


# ---------------------------------------------------------------------------
# The gap is gone from scoring
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("onsight", ["8a", "7c", "7b", "7a+", "6c", "5c"])
def test_the_gap_moves_neither_technique_nor_pe(onsight):
    """Sweep the whole gap range: no axis may respond to it."""
    reference = compute_assessment_profile(_assessment(), GOAL)
    varied = compute_assessment_profile(
        _assessment(grades={"lead_max_rp": "8a", "lead_max_os": onsight}), GOAL
    )
    assert varied == reference


def test_missing_grades_no_longer_change_anything():
    """The old `gap is None -> 50` default was one of D260's four silent 50s."""
    assert compute_assessment_profile(_assessment(grades={}), GOAL) == (
        compute_assessment_profile(_assessment(), GOAL)
    )


def test_the_gap_helper_survives_for_the_coach_hint():
    """Demoted, not deleted: it is the source of the coach's tactical line."""
    assert _redpoint_onsight_gap({"lead_max_rp": "8a", "lead_max_os": "7a+"}) == 5
    assert _redpoint_onsight_gap({"boulder_max_rp": "7B", "boulder_max_os": "7A"}) == 2
    assert _redpoint_onsight_gap({}) is None


# ---------------------------------------------------------------------------
# Technique
# ---------------------------------------------------------------------------

def test_technique_is_self_report_only_and_has_three_values():
    seen = set()
    for primary, secondary in itertools.product(
        [None, "technique_errors", "cant_hold_hard_moves"],
        [None, "cant_read_routes", "pump_too_early"],
    ):
        profile, source = compute_assessment_profile_with_source(
            _assessment(
                self_eval={"primary_weakness": primary, "secondary_weakness": secondary}
            ),
            GOAL,
        )
        seen.add(profile["technique"])
        assert source["technique"] == SOURCE_SELF_REPORTED
    assert seen == {40, 45, 50}


def test_technique_is_out_of_the_domain_weight_map():
    """The largest distortion D260 found, removed."""
    weak = {a: 60 for a in AXES} | {"technique": 30}
    strong = {a: 60 for a in AXES} | {"technique": 100}
    for weights in (_BASE_WEIGHTS, _BASE_WEIGHTS_BOULDER):
        for phase in weights:
            assert _adjust_domain_weights(weights[phase], weak) == _adjust_domain_weights(
                weights[phase], strong
            )


def test_technique_is_out_of_the_weakest_axis_tuple():
    """The phantom-50 trap: removing the key is NOT enough.

    `_find_weakest_axis` does `profile.get(axis, 50)`, so an absent axis becomes
    a phantom 50 — and on the real profiles that phantom won the weakest-axis
    title for two users. It has to be out of the tuple.
    """
    # With technique absent, the phantom 50 would beat four axes at 80.
    everything_strong = {a: 80 for a in AXES if a != "technique"}
    assert _find_weakest_axis(everything_strong)[1] == 80
    assert _find_weakest_axis(everything_strong)[0] != "technique"
    # And an explicit, very low technique must still not win.
    assert _find_weakest_axis({**everything_strong, "technique": 10})[0] != "technique"
    # An empty profile is the only case that returns "no weakness".
    assert _find_weakest_axis({}) == ("power_endurance", 50)


def test_a_technique_weakness_no_longer_shifts_a_phase_duration():
    """It used to extend Base at Performance's expense — a no-op for lead
    (floor == cap == 4) but real for boulder."""
    profile = {a: 60 for a in AXES} | {"technique": 30}
    for discipline in ("lead", "boulder"):
        with_weakness = _compute_phase_durations(profile, 12, discipline=discipline)
        without = _compute_phase_durations(
            {**profile, "technique": 80}, 12, discipline=discipline
        )
        assert with_weakness == without


# ---------------------------------------------------------------------------
# Power endurance
# ---------------------------------------------------------------------------

def test_pe_without_a_repeater_is_exactly_fifty_and_estimated():
    for primary in [None] + [
        w for group in _AXIS_WEAKNESS_PENALTIES["power_endurance"] for w in group[0]
    ]:
        profile, source = compute_assessment_profile_with_source(
            _assessment(self_eval={"primary_weakness": primary}), GOAL
        )
        assert profile["power_endurance"] == 50, primary
        assert source["power_endurance"] == SOURCE_ESTIMATED


def test_a_neutral_pe_cannot_move_a_weight():
    """Why the flat 50 matters: 50 sits in the dead band, 42 would not.

    `50 + eval` with a -8 penalty lands at 42, below the `< 50` cliff — a
    self-declaration steering the plan, which is what this brief removes.
    """
    neutral = {a: 60 for a in AXES} | {"power_endurance": 50}
    baseline = {a: 60 for a in AXES}
    for phase in _BASE_WEIGHTS:
        assert _adjust_domain_weights(_BASE_WEIGHTS[phase], neutral) == (
            _adjust_domain_weights(_BASE_WEIGHTS[phase], baseline)
        )


def test_pe_with_a_repeater_is_the_undiluted_repeater():
    """D260 §3.3: a repeater worth 78/100 was dragged to 54 by the gap."""
    assessment = _assessment(
        tests={"repeater_7_3_max_sets_20mm": 25},
        tests_source={"repeater_7_3_max_sets_20mm": "measured"},
    )
    profile, source = compute_assessment_profile_with_source(assessment, GOAL)
    # 25 / 32 (8a+ benchmark) * 100 = 78.1
    assert profile["power_endurance"] == 78
    assert source["power_endurance"] == SOURCE_PARTIAL


# ---------------------------------------------------------------------------
# The property test that would have caught the original distortion
# ---------------------------------------------------------------------------

_ALL_WEAKNESSES = sorted(
    {w for groups in _AXIS_WEAKNESS_PENALTIES.values() for g in groups for w in g[0]}
)


# Weaknesses that reach the ENDURANCE axis. They are excluded from the strict
# bound below and pinned separately in
# `test_known_residual_a_self_reported_endurance_weakness_still_moves_a_weight`:
# endurance is `estimated` for 15 of 18 production users, so for them it is a
# self-report too, and A270 deliberately scopes out the general rule "an
# estimated axis does not drive weights" (it would also touch finger, pulling
# and endurance for the 8 users with no tests — see A270 brief §6).
_ENDURANCE_WEAKNESSES = {
    w for group in _AXIS_WEAKNESS_PENALTIES["endurance"] for w in group[0]
}


def test_known_residual_a_self_reported_endurance_weakness_still_moves_a_weight():
    """FINDING, not a passing grade — surfaced by the property test below.

    `cant_manage_rests` is a pure self-declaration, and through the endurance
    axis it still moves `volume_climbing` by ~3.5 pp: endurance drops 10 points
    and crosses the `< 50` cliff. It is structurally the same defect A270 just
    removed from technique, on a different axis.

    Out of scope here by decision (A270 brief §6) because the fix — an
    `estimated` axis does not participate in the weight machinery — also changes
    finger, pulling and endurance for the 8 users with no tests at all, and
    deserves its own counterfactual. Pinned so it stays visible and so the
    follow-up has a number to beat.
    """
    measured = {
        "max_hang_20mm_7s_total_kg": 122,
        "weighted_pullup_1rm_total_kg": 127.8,
    }
    reference = compute_assessment_profile(
        _assessment(tests=dict(measured), self_eval={}), GOAL
    )
    with_weakness = compute_assessment_profile(
        _assessment(
            tests=dict(measured),
            self_eval={"primary_weakness": "cant_manage_rests"},
        ),
        GOAL,
    )
    a = _adjust_domain_weights(_BASE_WEIGHTS["base"], reference)
    b = _adjust_domain_weights(_BASE_WEIGHTS["base"], with_weakness)
    delta = max(abs(b[k] - a[k]) for k in a)
    assert 0.03 <= delta <= 0.04, f"residual moved: {delta * 100:.1f}pp"


def test_no_self_reported_input_moves_a_weight_by_more_than_two_points():
    """The guard D260 wished existed.

    For every weakness combination, every phase and both disciplines — holding
    the measured axes fixed — no domain weight may move by more than 2 pp. The
    +7.5 pp technique distortion would have failed this on the day it shipped.

    Scoped to the weaknesses A270 addresses: the endurance-mapped ones are a
    known, deliberately deferred residual (see the test above).
    """
    measured_tests = {
        "max_hang_20mm_7s_total_kg": 122,
        "weighted_pullup_1rm_total_kg": 127.8,
    }
    reference = compute_assessment_profile(
        _assessment(tests=dict(measured_tests), self_eval={}), GOAL
    )
    worst = 0.0
    candidates = [None] + [w for w in _ALL_WEAKNESSES if w not in _ENDURANCE_WEAKNESSES]
    for primary, secondary in itertools.product(candidates, repeat=2):
        if primary == secondary and primary is not None:
            continue
        profile = compute_assessment_profile(
            _assessment(
                tests=dict(measured_tests),
                self_eval={"primary_weakness": primary, "secondary_weakness": secondary},
            ),
            GOAL,
        )
        for weights in (_BASE_WEIGHTS, _BASE_WEIGHTS_BOULDER):
            for phase in weights:
                a = _adjust_domain_weights(weights[phase], reference)
                b = _adjust_domain_weights(weights[phase], profile)
                delta = max(abs(b[k] - a[k]) for k in a)
                worst = max(worst, delta)
                assert delta <= 0.02, (
                    f"{primary}/{secondary} moved a {phase} weight by "
                    f"{delta * 100:.1f}pp"
                )
    # In scope, the true figure is not "under 2 pp" — it is **zero**. With both
    # strength axes measured, technique out of the weight map and PE neutral, no
    # self-declaration reaches a domain weight at all.
    assert worst == 0.0


def test_weights_stay_normalised_on_the_production_corpus(corpus):
    for user in corpus:
        profile = compute_assessment_profile(user["assessment"], user["goal"])
        boulder = user["goal"].get("goal_type") == "boulder_grade"
        weights = _BASE_WEIGHTS_BOULDER if boulder else _BASE_WEIGHTS
        for phase in weights:
            adjusted = _adjust_domain_weights(weights[phase], profile)
            # `_adjust_domain_weights` rounds each key to 3 decimals AFTER
            # normalising, so the sum lands within a few thousandths of 1.0.
            assert abs(sum(adjusted.values()) - 1.0) < 0.005, user["uid"]
            assert all(v >= 0.02 for v in adjusted.values()), user["uid"]


# ---------------------------------------------------------------------------
# What actually moved, on the 18 real profiles
# ---------------------------------------------------------------------------

def test_only_three_axes_move_and_the_strength_axes_never_do(corpus):
    """The blast radius, pinned. Finger and pulling are measured ratios and
    were never touched by the gap — if they move, something else broke."""
    moved = {axis: 0 for axis in AXES}
    for user in corpus:
        v1, v2 = user["expected_profile"], user["expected_profile_v2"]
        for axis in AXES:
            if v1[axis] != v2[axis]:
                moved[axis] += 1
    assert moved["finger_strength"] == 0
    assert moved["pulling_strength"] == 0
    assert moved["technique"] == 18
    assert moved["power_endurance"] == 18
    assert moved["endurance"] == 18


def test_the_author_regression(corpus):
    """The case D260 documented end to end."""
    author = next(u for u in corpus if u["uid"] == "7ea9f0ee")
    profile, source = compute_assessment_profile_with_source(
        author["assessment"], author["goal"]
    )
    assert author["expected_profile"]["technique"] == 30  # before
    assert profile["technique"] == 40
    assert profile["power_endurance"] == 70  # was 53 — the repeater, undiluted
    assert profile["endurance"] == 65  # was 51 — follows PE at 0.8x
    assert source["technique"] == SOURCE_SELF_REPORTED
    assert source["power_endurance"] == SOURCE_PARTIAL


def test_the_author_technique_weight_returns_to_baseline(corpus):
    """D260 §5's headline number, reversed: .275 -> .202 in Base."""
    author = next(u for u in corpus if u["uid"] == "7ea9f0ee")
    profile = compute_assessment_profile(author["assessment"], author["goal"])
    adjusted = _adjust_domain_weights(_BASE_WEIGHTS["base"], profile)
    assert adjusted["technique"] == pytest.approx(0.202, abs=0.001)
    assert _BASE_WEIGHTS["base"]["technique"] == 0.20  # base weight untouched


def test_every_user_becomes_stale_and_that_is_correct(corpus):
    """A270 changes scores, so `is_macrocycle_stale` MUST fire.

    That is the banner offering the user a regeneration — the intended
    behaviour, not a side effect. Pinned so it cannot regress silently, and so
    the size of the product event is visible: this is every user with a plan.
    """
    stale = 0
    for user in corpus:
        state = {
            "assessment": {**user["assessment"], "profile": user["expected_profile_v2"]},
            "macrocycle": {"assessment_snapshot": dict(user["expected_profile"])},
        }
        if is_macrocycle_stale(state):
            stale += 1
    assert stale == 18


def test_known_residual_self_report_leaks_through_the_grade_estimate_fallback():
    """SECOND FINDING from the property sweep, larger than the one A270 removes.

    When an axis has no test, `_compute_finger_strength` and
    `_compute_pulling_strength` fall back to a grade estimate **plus the
    self-eval penalty**, and endurance carries its own. For a user with no tests
    at all — 8 of the 18 production profiles — a single self-declaration
    (`cant_manage_rests`) moves a deload weight by **8.3 pp**: more than the
    +7.5 pp technique distortion D260 called the largest in the engine.

    Deliberately out of A270's scope (brief §6): the fix is the general rule
    that an `estimated` axis does not participate in the weight machinery, which
    changes the plan for those 8 users and needs its own counterfactual. A269
    shipped the field that makes that rule expressible; this test pins the size
    of the problem it will have to solve.
    """
    reference = compute_assessment_profile(_assessment(self_eval={}), GOAL)
    assert reference["power_endurance"] == 50 and reference["technique"] == 50
    with_weakness = compute_assessment_profile(
        _assessment(self_eval={"primary_weakness": "cant_manage_rests"}), GOAL
    )
    a = _adjust_domain_weights(_BASE_WEIGHTS["deload"], reference)
    b = _adjust_domain_weights(_BASE_WEIGHTS["deload"], with_weakness)
    delta = max(abs(b[k] - a[k]) for k in a)
    assert 0.08 <= delta <= 0.09, f"residual moved: {delta * 100:.1f}pp"


def test_the_coach_gets_the_gap_as_a_hint_with_its_guardrail():
    """The gap is demoted, not deleted — it moves into the coach context.

    The guardrail sentence is load-bearing: without it the model reads a number
    labelled "gap" and diagnoses technique, the failure mode B305 closed when
    the coach imitated a format string and fabricated a build.
    """
    from backend.coach.prompt_builder import _profile_section

    section = _profile_section(
        {
            "goal": {"target_style": "redpoint"},
            "assessment": {
                "grades": {"lead_max_rp": "8a", "lead_max_os": "7a+"},
                "profile": {a: 50 for a in AXES},
                "profile_source": {"technique": SOURCE_SELF_REPORTED},
            },
        }
    )
    assert "Onsight gap: 5 half-grades" in section
    assert "NOT a technique measurement" in section
    assert "the plan does not weight it" in section
    assert "target style: redpoint" in section


def test_the_coach_is_never_told_a_self_reported_axis_is_the_weakness():
    from backend.coach.prompt_builder import _profile_section

    section = _profile_section(
        {
            "assessment": {
                "profile": {
                    "technique": 10,  # lowest by far
                    "finger_strength": 90,
                    "pulling_strength": 91,
                    "power_endurance": 92,
                    "endurance": 93,
                },
                "profile_source": {"technique": SOURCE_SELF_REPORTED},
            }
        }
    )
    weakest = [line for line in section.splitlines() if line.startswith("- Weakest")][0]
    assert "technique" not in weakest
    assert "finger_strength" in weakest


def test_scoring_version_is_bumped():
    assert PROFILE_SCORING_VERSION == "profile_v2_gap_demoted"
