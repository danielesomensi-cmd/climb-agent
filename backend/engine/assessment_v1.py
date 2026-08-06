"""Assessment engine v1 — compute 5-axis profile from raw assessment data."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.engine.grade_mapping import BOULDER_TO_LEAD

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Grade helpers
# ---------------------------------------------------------------------------

GRADE_ORDER: List[str] = [
    # B302: 5a+/5b+/5c+ were missing while the grade picker (LEAD_GRADES) offers
    # them — a lead climber selecting one crashed grade_index → assessment failed
    # → no profile → no plan. Every consumer uses these indices RELATIVELY (gaps,
    # ranking), so inserting is safe; outdoor_log pins its own weights (see there).
    "5a", "5a+", "5b", "5b+", "5c", "5c+",
    "6a", "6a+", "6b", "6b+", "6c", "6c+",
    "7a", "7a+", "7b", "7b+", "7c", "7c+",
    "8a", "8a+", "8b", "8b+", "8c", "8c+",
    "9a", "9a+",
]

_GRADE_INDEX = {g: i for i, g in enumerate(GRADE_ORDER)}


def grade_index(grade: str) -> int:
    """Return the ordinal index for a grade string. Raises ValueError if unknown."""
    if grade not in _GRADE_INDEX:
        raise ValueError(f"Unknown grade: {grade!r}")
    return _GRADE_INDEX[grade]


def resolve_grade(grade: Optional[str]) -> Optional[str]:
    """Normalize any stored grade to the lead scale the benchmarks are built on.

    The benchmark tables below are calibrated to lowercase French lead grades,
    but the engine stores boulder grades in Fontainebleau (``"7B"``) — see the
    "Fontainebleau for boulder grades" rule in CLAUDE.md. Every caller that
    turns a grade into an index therefore has to map first, or a boulder athlete
    silently falls off the table.

    B321: before this existed, ``_compute_finger_strength`` did
    ``grade_index(g) if g in _GRADE_INDEX else 0`` — so ``"7B"`` produced index
    **0**, i.e. "beginner", and the axis scored 0 for a 7B boulderer with real
    numbers on file. Same silent-zero pattern A262 removed from the public
    assessment endpoint. Returns ``None`` for a genuinely unknown grade so the
    caller can fall back to a neutral score instead of fabricating a floor.
    """
    if not grade:
        return None
    if grade in _GRADE_INDEX:
        return grade
    mapped = BOULDER_TO_LEAD.get(grade.upper())
    if mapped in _GRADE_INDEX:
        return mapped
    return None


def grade_gap(grade_a: str, grade_b: str) -> int:
    """Return grade_a - grade_b in half-grade steps (positive = a is harder)."""
    return grade_index(grade_a) - grade_index(grade_b)


# ---------------------------------------------------------------------------
# Benchmark tables (indexed by target grade)
# ---------------------------------------------------------------------------

# Max hang 20mm 5s: total_load / bodyweight ratio
_FINGER_BENCHMARK: Dict[str, float] = {
    "7a": 1.0, "7a+": 1.08,
    "7b": 1.15, "7b+": 1.20,
    "7c": 1.25, "7c+": 1.30,
    "8a": 1.40, "8a+": 1.50,
    "8b": 1.60, "8b+": 1.70,
    "8c": 1.80, "8c+": 1.90,
    "9a": 2.00, "9a+": 2.10,
}

# Weighted pullup 1RM: total_load / bodyweight ratio
_PULLING_BENCHMARK: Dict[str, float] = {
    "7a": 1.20, "7a+": 1.25,
    "7b": 1.30, "7b+": 1.35,
    "7c": 1.40, "7c+": 1.45,
    "8a": 1.55, "8a+": 1.65,
    "8b": 1.75, "8b+": 1.85,
    "8c": 1.95, "8c+": 2.05,
    "9a": 2.15, "9a+": 2.25,
}

# A266: converting a one-hand loading-pin lift into the two-hand max-hang total
# the finger benchmark is expressed in.
#
# Not a guess, and not derivable from _FINGER_BENCHMARK alone — three
# independent sources agree on it:
#
#   * _FINGER_BENCHMARK says 8a needs a two-hand total of 1.40 x bodyweight.
#   * Lattice's published one-arm dataset (20mm, 7-10s) puts the same ability —
#     V8/V9, i.e. lead ~8a — at 0.73-0.79 x bodyweight on ONE arm.
#     => implied two-hand / one-arm ratio = 1.40 / 0.76 = 1.84
#   * The climbing bilateral-deficit literature reports a two-arm-total to
#     one-arm ratio of 1.6-2.0 (it is below 2.0 because a single limb expresses
#     more force alone than it does as half of a bilateral effort).
#
# 1.84 sits inside the literature range and falls out of our own benchmark, so
# the tables stay mutually consistent: a climber who tests on a pin and one who
# tests on a hangboard land on the same axis score. Rounded to 1.85.
LP_ONE_ARM_TO_TWO_HAND = 1.85

# Above this, a "one-hand lift" is a data-entry error, not a climber: the Lattice
# dataset puts V17 — the hardest boulder ever climbed — at 1.18 x bodyweight on
# one arm. Anything past 1.5 is someone typing the total load, the plate weight,
# or pounds into a kg field. We drop it rather than saturate the axis on it.
LP_MAX_PLAUSIBLE_BW_RATIO = 1.5

# Repeater test (7:3 duty cycle, 20mm, 60% max total load): expected reps for grade
_PE_REPEATER_BENCHMARK: Dict[str, int] = {
    "7a": 18, "7a+": 20,
    "7b": 22, "7b+": 24,
    "7c": 26, "7c+": 28,
    "8a": 30, "8a+": 32,
    "8b": 34, "8b+": 36,
    "8c": 38, "8c+": 40,
    "9a": 42, "9a+": 44,
}


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(max(lo, min(hi, round(value))))


def _benchmark_for(table: Dict[str, float], target_grade: str) -> float:
    """Get the benchmark for target_grade, falling back to nearest known grade."""
    # B321: a Font target ("7C") used to raise ValueError here and take the whole
    # profile down with it. Onboarding maps target_grade before calling, but
    # PUT /api/state and the goal editor do not always.
    # An unresolvable grade falls back to the same "7c+" the profile entry point
    # uses as its default target — never a ValueError, because a raised
    # assessment means no profile, which means no plan at all (B302).
    target_grade = resolve_grade(target_grade) or "7c+"
    if target_grade in table:
        return table[target_grade]
    # Fall back: find the closest grade in the table
    tgt_idx = grade_index(target_grade)
    best_grade = None
    best_dist = 999
    for g in table:
        dist = abs(grade_index(g) - tgt_idx)
        if dist < best_dist:
            best_dist = dist
            best_grade = g
    return table[best_grade] if best_grade else 1.0


# ---------------------------------------------------------------------------
# Utility: Brzycki 1RM estimation (D38)
# ---------------------------------------------------------------------------

def brzycki_1rm(weight: float, reps: int) -> float:
    """Estimate 1RM from submaximal reps using Brzycki formula.

    Most accurate for 1-10 reps. Returns the weight itself if reps <= 1.
    """
    if reps <= 0:
        return 0.0
    if reps == 1:
        return float(weight)
    if reps >= 37:
        return float(weight)  # formula breaks at 37 reps
    return weight * (36.0 / (37.0 - reps))


# ---------------------------------------------------------------------------
# Weakness → axis penalty mapping (R148)
# ---------------------------------------------------------------------------
# Centralized self-eval weakness → axis penalty table. Previously these were
# scattered as inline if/elif string-comparisons across every _compute_* axis.
# Each axis maps to one or more independent weakness groups; within a group the
# penalty is applied once — the larger value when the weakness is the user's
# *primary* weakness, the smaller when it is the *secondary*. Multiple groups on
# the same axis stack (e.g. endurance penalizes both pump and rest management).
# Shape: axis -> tuple of (weakness_values, primary_penalty, secondary_penalty).
# Prerequisite for R149 (weakness→resolver hints) and the LLM Coach layer.
_AXIS_WEAKNESS_PENALTIES: Dict[str, Tuple[Tuple[Tuple[str, ...], float, float], ...]] = {
    "finger_strength": ((("fingers_give_out", "weak_on_slopers"), 15.0, 8.0),),
    "pulling_strength": ((("cant_hold_hard_moves",), 10.0, 5.0),),
    "power_endurance": ((("pump_too_early", "poor_dynamic_movement"), 8.0, 4.0),),
    "technique": ((
        (
            "technique_errors", "cant_read_routes", "poor_body_tension",
            "poor_problem_reading", "poor_dynamic_movement",
        ),
        10.0, 5.0,
    ),),
    "endurance": (
        (("pump_too_early",), 10.0, 5.0),
        (("cant_manage_rests",), 10.0, 5.0),
    ),
}


def _redpoint_onsight_gap(grades: Dict[str, Any]) -> Optional[int]:
    """Return the redpoint − onsight gap in half-grade steps, or None.

    Both power_endurance and technique are driven by this gap. B321: they read
    ``lead_max_rp``/``lead_max_os`` only, so a boulder-only athlete — who fills
    in ``boulder_max_rp``/``boulder_max_os`` and leaves the lead fields empty —
    always fell through to the neutral 50 on **both** axes, no matter how their
    onsight compared to their redpoint. Boulder grades are mapped to lead via
    ``resolve_grade`` so the gap is measured on one scale, the same convention
    A262 applies in the public assessment endpoint.
    """
    for rp_key, os_key in (
        ("lead_max_rp", "lead_max_os"),
        ("boulder_max_rp", "boulder_max_os"),
    ):
        rp = resolve_grade(grades.get(rp_key))
        os_ = resolve_grade(grades.get(os_key))
        if rp and os_:
            return grade_gap(rp, os_)
    return None


def _grade_ratio_score(current_grade: str, target_grade: str, ceiling: float) -> float:
    """Estimate an axis from the current/target grade ratio (no measured test).

    B321: both call sites previously inlined
    ``grade_index(g) if g in _GRADE_INDEX else 0``, which turned any grade the
    lead table does not contain — every Fontainebleau boulder grade — into a
    hard 0 and dragged the axis to the floor. Grades are resolved through
    ``resolve_grade`` first; if either side is still unknown the score is the
    neutral 50, the same value used when the target index is 0. Unknown must
    read as "we don't know", never as "you are a beginner".
    """
    current = resolve_grade(current_grade)
    target = resolve_grade(target_grade)
    if current is None or target is None:
        return 50.0
    target_idx = grade_index(target)
    if target_idx <= 0:
        return 50.0
    return (grade_index(current) / target_idx) * ceiling


def _weakness_penalty(self_eval: Dict[str, Any], axis: str) -> float:
    """Return the (negative or zero) self-eval penalty for the given axis.

    Sums over the axis's weakness groups: each group contributes the primary
    penalty if it matches ``primary_weakness``, else the secondary penalty if it
    matches ``secondary_weakness``, else nothing.
    """
    total = 0.0
    primary = self_eval.get("primary_weakness")
    secondary = self_eval.get("secondary_weakness")
    for weaknesses, primary_pen, secondary_pen in _AXIS_WEAKNESS_PENALTIES.get(axis, ()):
        if primary in weaknesses:
            total -= primary_pen
        elif secondary in weaknesses:
            total -= secondary_pen
    return total


# ---------------------------------------------------------------------------
# Individual axis computations
# ---------------------------------------------------------------------------

def loading_pin_two_hand_equivalent(
    tests: Dict[str, Any], bodyweight_kg: float
) -> Optional[float]:
    """Two-hand max-hang total (kg) implied by a one-hand loading-pin lift.

    A266: users who train fingers on a loading pin — including the beta tester
    who cannot use a hangboard at all, for a shoulder limitation — record
    ``lp_max_lift_5s_left/right_kg`` and nothing else. `_compute_finger_strength`
    only ever read ``max_hang_*``, so their measured numbers were invisible and
    the axis silently fell back to estimating from grade. The wizard collects
    these values and the closed loop writes them; only the assessment ignored
    them.

    Both hands are averaged rather than summed: the benchmark describes one
    two-hand effort, and a left/right spread is an asymmetry to carry into
    training, not extra strength. A single hand on file is used on its own.

    Returns None when there is no usable value, so the caller keeps its existing
    grade-estimate path instead of scoring against a fabricated number.
    """
    if bodyweight_kg <= 0:
        return None
    lifts = []
    for key in ("lp_max_lift_5s_left_kg", "lp_max_lift_5s_right_kg"):
        value = tests.get(key)
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        if value / bodyweight_kg > LP_MAX_PLAUSIBLE_BW_RATIO:
            logger.warning(
                "loading_pin_two_hand_equivalent: %s=%.1fkg is %.0f%% of a %.1fkg "
                "bodyweight — beyond the hardest boulder ever climbed; ignoring "
                "as a data-entry error",
                key, value, 100 * value / bodyweight_kg, bodyweight_kg,
            )
            continue
        lifts.append(value)
    if not lifts:
        return None
    return (sum(lifts) / len(lifts)) * LP_ONE_ARM_TO_TWO_HAND


def _compute_finger_strength(
    tests: Dict[str, Any],
    body: Dict[str, Any],
    self_eval: Dict[str, Any],
    target_grade: str,
    current_grade: str,
) -> int:
    bw = body.get("weight_kg") or 70.0
    benchmark = _benchmark_for(_FINGER_BENCHMARK, target_grade)
    max_hang = tests.get("max_hang_20mm_7s_total_kg") or tests.get("max_hang_20mm_5s_total_kg")

    # A266: a hangboard number wins when both exist — it is measured directly in
    # the unit the benchmark speaks. The pin is converted only as a fallback.
    if max_hang is None:
        max_hang = loading_pin_two_hand_equivalent(tests, bw)

    if max_hang is not None:
        ratio = max_hang / bw
        score = (ratio / benchmark) * 100
    else:
        # Estimate from grades: assume current grade ~ 60-70% of target benchmark
        score = _grade_ratio_score(current_grade, target_grade, 70.0)
        # Self-eval modifier
        score += _weakness_penalty(self_eval, "finger_strength")

    return _clamp(score)


def _compute_pulling_strength(
    tests: Dict[str, Any],
    body: Dict[str, Any],
    self_eval: Dict[str, Any],
    target_grade: str,
    current_grade: str,
) -> int:
    bw = body.get("weight_kg") or 70.0
    benchmark = _benchmark_for(_PULLING_BENCHMARK, target_grade)
    wp_1rm = tests.get("weighted_pullup_1rm_total_kg")

    # D38: Brzycki estimation when direct 1RM is missing but submaximal data exists
    if wp_1rm is None:
        sub_reps = tests.get("pullup_submaximal_reps")
        sub_load = tests.get("pullup_submaximal_load_kg")
        if sub_reps is not None and sub_load is not None:
            sub_reps = int(sub_reps)
            sub_load = float(sub_load)
            wp_1rm = round(brzycki_1rm(bw + sub_load, sub_reps), 1)

    if wp_1rm is not None:
        ratio = wp_1rm / bw
        score = (ratio / benchmark) * 100
    else:
        score = _grade_ratio_score(current_grade, target_grade, 65.0)
        score += _weakness_penalty(self_eval, "pulling_strength")

    return _clamp(score)


def _compute_power_endurance(
    grades: Dict[str, Any],
    self_eval: Dict[str, Any],
    tests: Optional[Dict[str, Any]] = None,
    target_grade: str = "7c+",
) -> int:
    """Compute power endurance score.

    Weighted components:
    - Repeater test (objective): 40% when available
    - RP-OS gap: 40% (or 60% without repeater)
    - Self-eval: 20% (or 40% without repeater)
    """
    tests = tests or {}

    # --- Gap score ---
    gap = _redpoint_onsight_gap(grades)

    if gap is None:
        gap_score = 50.0
    elif gap <= 2:
        gap_score = 75.0
    elif gap <= 4:
        gap_score = 55.0
    elif gap <= 6:
        gap_score = 40.0
    else:
        gap_score = 30.0

    # --- Repeater score (objective) ---
    repeater_reps = tests.get("repeater_7_3_max_sets_20mm")
    has_repeater = repeater_reps is not None and isinstance(repeater_reps, (int, float))

    if has_repeater:
        benchmark = _benchmark_for(_PE_REPEATER_BENCHMARK, target_grade)
        repeater_score = (repeater_reps / benchmark) * 100
        repeater_score = min(100.0, max(0.0, repeater_score))
    else:
        repeater_score = 0.0

    # --- Self-eval modifier (reduced penalties to avoid double counting) ---
    eval_modifier = _weakness_penalty(self_eval, "power_endurance")

    # --- Weighted combination ---
    if has_repeater:
        # 40% repeater + 40% gap + 20% self_eval influence
        score = repeater_score * 0.4 + gap_score * 0.4 + (gap_score + eval_modifier) * 0.2
    else:
        # 60% gap + 40% self_eval influence
        score = gap_score * 0.6 + (gap_score + eval_modifier) * 0.4

    return _clamp(score)


def _compute_technique(
    grades: Dict[str, Any],
    self_eval: Dict[str, Any],
) -> int:
    gap = _redpoint_onsight_gap(grades)

    if gap is None:
        score = 50.0
    elif gap <= 2:
        score = 80.0
    elif gap <= 4:
        score = 60.0
    elif gap <= 6:
        score = 40.0
    else:
        score = 30.0

    score += _weakness_penalty(self_eval, "technique")

    return _clamp(score)


def _compute_endurance(
    pe_score: int,
    experience: Dict[str, Any],
    self_eval: Dict[str, Any],
    tests: Optional[Dict[str, Any]] = None,
) -> int:
    score = pe_score * 0.8
    climbing_years = experience.get("climbing_years") or 0
    score += min(climbing_years * 2, 10)

    score += _weakness_penalty(self_eval, "endurance")

    # Max hang duration modifier (Hörst test #3: sustained finger endurance)
    tests = tests or {}
    hang_duration = tests.get("max_hang_duration_20mm_seconds")
    if hang_duration is not None:
        hang_duration = float(hang_duration)
        if hang_duration >= 90:
            score += 8
        elif hang_duration >= 60:
            score += 4
        elif hang_duration >= 45:
            pass  # +0
        elif hang_duration >= 30:
            score -= 4
        else:
            score -= 8

    return _clamp(score)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Axis provenance (A269)
# ---------------------------------------------------------------------------
#
# D260 §3.6 called it "the 50 problem": `50` is emitted as a silent default by
# missing grades in PE/technique, by the `else` branch of finger/pulling when
# `target_idx == 0`, and by `profile.get(axis, 50)` in the macrocycle — so
# downstream a real average and "we have no data" are indistinguishable. On the
# 18 production profiles, 8 have no finger test at all, 15 have no repeater, and
# 18/18 have no dedicated endurance test. Nothing recorded any of that.
#
# This sidecar is the axis-level twin of `assessment.tests_source` (D214), which
# records the same thing one level down, for individual test scalars. The same
# absence convention applies and is load-bearing: **a missing key means
# `estimated`**, never "measured". A reader must never be able to read silence
# as a measurement.
#
# The values describe what an axis was DERIVED FROM, not how good it is.

PROFILE_SCORING_VERSION = "profile_v1"

SOURCE_MEASURED = "measured"    # every input to the axis is a measured test
SOURCE_PARTIAL = "partial"      # at least one measured input + derived/subjective terms
SOURCE_ESTIMATED = "estimated"  # no measured input at all

# The keys each axis actually READS. Deliberately not the wider set the planner
# treats as "a fresh test": `week.py` also accepts `weighted_pullup_2rm_total_kg`
# for retest freshness, but `_compute_pulling_strength` never reads it — an axis
# scored from a grade estimate is `estimated` no matter which other tests exist.
_FINGER_SOURCE_KEYS: Tuple[str, ...] = (
    "max_hang_20mm_7s_total_kg",
    "max_hang_20mm_5s_total_kg",
    "lp_max_lift_5s_left_kg",
    "lp_max_lift_5s_right_kg",
)
_PULLING_SOURCE_KEYS: Tuple[str, ...] = ("weighted_pullup_1rm_total_kg",)
_PULLING_SUBMAX_KEYS: Tuple[str, ...] = (
    "pullup_submaximal_reps",
    "pullup_submaximal_load_kg",
)


def _is_measured(tests_source: Dict[str, Any], key: str) -> bool:
    return tests_source.get(key) == SOURCE_MEASURED


def compute_profile_source(assessment: Dict[str, Any]) -> Dict[str, str]:
    """Per-axis provenance, derived from ``assessment.tests_source``.

    Reads `tests_source`, never `tests`: a value estimated during onboarding is
    *present* but not *measured*, and telling those two apart is the whole point
    of the D214 sidecar this builds on.
    """
    tests_source = assessment.get("tests_source") or {}
    if not isinstance(tests_source, dict):
        tests_source = {}

    finger = (
        SOURCE_MEASURED
        if any(_is_measured(tests_source, k) for k in _FINGER_SOURCE_KEYS)
        else SOURCE_ESTIMATED
    )
    # A266: a loading-pin number is measured but CONVERTED (LP_ONE_ARM_TO_TWO_HAND).
    # It stays `measured` — the conversion is derived from three agreeing sources
    # and `tests_source` still records which key was the origin, so nothing is lost.

    pulling_measured = any(_is_measured(tests_source, k) for k in _PULLING_SOURCE_KEYS) or all(
        _is_measured(tests_source, k) for k in _PULLING_SUBMAX_KEYS
    )
    pulling = SOURCE_MEASURED if pulling_measured else SOURCE_ESTIMATED

    # PE is at most `partial`: the repeater carries 40% of the score, the rest is
    # the RP-OS gap and self-eval (D260 §3.3).
    pe = (
        SOURCE_PARTIAL
        if _is_measured(tests_source, "repeater_7_3_max_sets_20mm")
        else SOURCE_ESTIMATED
    )

    # No test feeds technique. Not "none today" — none by construction: the axis
    # is the RP-OS gap bucket plus a self-declared weakness (D260 §3.5).
    technique = SOURCE_ESTIMATED

    # Endurance has no test of its own (D260 §3.4): it is `0.8 x PE` plus tenure
    # plus a hang-duration nudge. It is `partial` when EITHER of its two measured
    # inputs exists — the duration modifier directly, or the repeater flowing in
    # through PE. The brief's table listed only the duration; the definition
    # ("at least one measured input") covers both, and a repeater does reach this
    # axis at 32% weight, so the wider rule is the honest one.
    endurance = (
        SOURCE_PARTIAL
        if _is_measured(tests_source, "max_hang_duration_20mm_seconds") or pe == SOURCE_PARTIAL
        else SOURCE_ESTIMATED
    )

    return {
        "finger_strength": finger,
        "pulling_strength": pulling,
        "power_endurance": pe,
        "technique": technique,
        "endurance": endurance,
    }


def compute_assessment_profile_with_source(
    assessment: Dict[str, Any], goal: Dict[str, Any]
) -> Tuple[Dict[str, int], Dict[str, str]]:
    """The profile plus its per-axis provenance (A269).

    Every call site that PERSISTS a profile should use this one, so the scores
    and the record of where they came from can never drift apart. The plain
    ``compute_assessment_profile`` remains for callers that only need the
    numbers — the ~30 test files and the stateless public endpoint, which
    already reports provenance its own way (`measured_axes`, A262/A263).
    """
    return compute_assessment_profile(assessment, goal), compute_profile_source(assessment)


def compute_assessment_profile(assessment: Dict[str, Any], goal: Dict[str, Any]) -> Dict[str, int]:
    """Compute the 5-axis assessment profile (each axis 0-100).

    Args:
        assessment: The assessment dict from user_state (body, experience, grades, tests, self_eval).
        goal: The goal dict from user_state (goal_type, target_grade, current_grade, etc.).

    Returns:
        Dict with keys: finger_strength, pulling_strength, power_endurance,
        technique, endurance — each an int 0-100.
    """
    body = assessment.get("body") or {}
    experience = assessment.get("experience") or {}
    grades = assessment.get("grades") or {}
    tests = assessment.get("tests") or {}
    self_eval = assessment.get("self_eval") or {}

    target_grade = goal.get("target_grade", "7c+")
    current_grade = goal.get("current_grade", "7a")

    finger = _compute_finger_strength(tests, body, self_eval, target_grade, current_grade)
    pulling = _compute_pulling_strength(tests, body, self_eval, target_grade, current_grade)
    pe = _compute_power_endurance(grades, self_eval, tests, target_grade)
    technique = _compute_technique(grades, self_eval)
    endurance = _compute_endurance(pe, experience, self_eval, tests)

    return {
        "finger_strength": finger,
        "pulling_strength": pulling,
        "power_endurance": pe,
        "technique": technique,
        "endurance": endurance,
    }
