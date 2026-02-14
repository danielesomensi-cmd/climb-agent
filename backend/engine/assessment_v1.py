"""Assessment engine v1 — compute 6-axis profile from raw assessment data."""

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
    max_hang = tests.get("max_hang_20mm_5s_total_kg")

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
        if self_eval.get("primary_weakness") == "fingers_give_out":
            score -= 15
        elif self_eval.get("secondary_weakness") == "fingers_give_out":
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
) -> int:
    lead_rp = grades.get("lead_max_rp")
    lead_os = grades.get("lead_max_os")

    if lead_rp and lead_os and lead_rp in _GRADE_INDEX and lead_os in _GRADE_INDEX:
        gap = grade_gap(lead_rp, lead_os)
        if gap <= 2:
            score = 75.0
        elif gap <= 4:
            score = 55.0
        elif gap <= 6:
            score = 40.0
        else:
            score = 30.0
    else:
        score = 50.0

    if self_eval.get("primary_weakness") == "pump_too_early":
        score -= 15
    elif self_eval.get("secondary_weakness") == "pump_too_early":
        score -= 8

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

    if self_eval.get("primary_weakness") in ("technique_errors", "cant_read_routes"):
        score -= 10
    elif self_eval.get("secondary_weakness") in ("technique_errors", "cant_read_routes"):
        score -= 5

    return _clamp(score)


def _compute_endurance(
    pe_score: int,
    experience: Dict[str, Any],
    self_eval: Dict[str, Any],
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

    return _clamp(score)


def _compute_body_composition(
    body: Dict[str, Any],
    finger_score: int,
) -> int:
    bf = body.get("body_fat_pct")
    if bf is not None:
        if bf <= 10:
            score = 95.0
        elif bf <= 12:
            score = 85.0
        elif bf <= 14:
            score = 78.0
        elif bf <= 16:
            score = 70.0
        elif bf <= 18:
            score = 60.0
        elif bf <= 20:
            score = 50.0
        elif bf <= 25:
            score = 35.0
        else:
            score = 20.0
    else:
        # Estimate from finger strength score — if strong for weight, good composition
        score = min(70.0, finger_score * 0.9)

    return _clamp(score)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_assessment_profile(assessment: Dict[str, Any], goal: Dict[str, Any]) -> Dict[str, int]:
    """Compute the 6-axis assessment profile (each axis 0-100).

    Args:
        assessment: The assessment dict from user_state (body, experience, grades, tests, self_eval).
        goal: The goal dict from user_state (goal_type, target_grade, current_grade, etc.).

    Returns:
        Dict with keys: finger_strength, pulling_strength, power_endurance,
        technique, endurance, body_composition — each an int 0-100.
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
    pe = _compute_power_endurance(grades, self_eval)
    technique = _compute_technique(grades, self_eval)
    endurance = _compute_endurance(pe, experience, self_eval)
    body_comp = _compute_body_composition(body, finger)

    return {
        "finger_strength": finger,
        "pulling_strength": pulling,
        "power_endurance": pe,
        "technique": technique,
        "endurance": endurance,
        "body_composition": body_comp,
    }
