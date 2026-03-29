"""Assessment engine v1 — compute 5-axis profile from raw assessment data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Grade helpers
# ---------------------------------------------------------------------------

GRADE_ORDER: List[str] = [
    "5a", "5b", "5c",
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
# Individual axis computations
# ---------------------------------------------------------------------------

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

    if max_hang is not None:
        ratio = max_hang / bw
        score = (ratio / benchmark) * 100
    else:
        # Estimate from grades: assume current grade ~ 60-70% of target benchmark
        current_idx = grade_index(current_grade) if current_grade in _GRADE_INDEX else 0
        target_idx = grade_index(target_grade)
        if target_idx > 0:
            score = (current_idx / target_idx) * 70
        else:
            score = 50.0
        # Self-eval modifier
        if self_eval.get("primary_weakness") in ("fingers_give_out", "weak_on_slopers"):
            score -= 15
        elif self_eval.get("secondary_weakness") in ("fingers_give_out", "weak_on_slopers"):
            score -= 8

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
        current_idx = grade_index(current_grade) if current_grade in _GRADE_INDEX else 0
        target_idx = grade_index(target_grade)
        if target_idx > 0:
            score = (current_idx / target_idx) * 65
        else:
            score = 50.0
        if self_eval.get("primary_weakness") == "cant_hold_hard_moves":
            score -= 10
        elif self_eval.get("secondary_weakness") == "cant_hold_hard_moves":
            score -= 5

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
    lead_rp = grades.get("lead_max_rp")
    lead_os = grades.get("lead_max_os")

    if lead_rp and lead_os and lead_rp in _GRADE_INDEX and lead_os in _GRADE_INDEX:
        gap = grade_gap(lead_rp, lead_os)
        if gap <= 2:
            gap_score = 75.0
        elif gap <= 4:
            gap_score = 55.0
        elif gap <= 6:
            gap_score = 40.0
        else:
            gap_score = 30.0
    else:
        gap_score = 50.0

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
    eval_modifier = 0.0
    if self_eval.get("primary_weakness") in ("pump_too_early", "poor_dynamic_movement"):
        eval_modifier = -8.0
    elif self_eval.get("secondary_weakness") in ("pump_too_early", "poor_dynamic_movement"):
        eval_modifier = -4.0

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
    lead_rp = grades.get("lead_max_rp")
    lead_os = grades.get("lead_max_os")

    if lead_rp and lead_os and lead_rp in _GRADE_INDEX and lead_os in _GRADE_INDEX:
        gap = grade_gap(lead_rp, lead_os)
        if gap <= 2:
            score = 80.0
        elif gap <= 4:
            score = 60.0
        elif gap <= 6:
            score = 40.0
        else:
            score = 30.0
    else:
        score = 50.0

    technique_weaknesses = (
        "technique_errors", "cant_read_routes",
        "poor_body_tension", "poor_problem_reading", "poor_dynamic_movement",
    )
    if self_eval.get("primary_weakness") in technique_weaknesses:
        score -= 10
    elif self_eval.get("secondary_weakness") in technique_weaknesses:
        score -= 5

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

    if self_eval.get("primary_weakness") == "pump_too_early":
        score -= 10
    elif self_eval.get("secondary_weakness") == "pump_too_early":
        score -= 5
    if self_eval.get("primary_weakness") == "cant_manage_rests":
        score -= 10
    elif self_eval.get("secondary_weakness") == "cant_manage_rests":
        score -= 5

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
