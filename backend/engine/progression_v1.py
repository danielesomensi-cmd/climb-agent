from __future__ import annotations

import logging
import os
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from backend.engine.assessment_v1 import _FINGER_BENCHMARK

FONT_GRADES: List[str] = [
    "5A", "5A+", "5B", "5B+", "5C", "5C+",
    "6A", "6A+", "6B", "6B+", "6C", "6C+",
    "7A", "7A+", "7B", "7B+", "7C", "7C+",
    "8A", "8A+", "8B", "8B+", "8C", "8C+",
]
FONT_GRADE_TO_INDEX = {grade: idx for idx, grade in enumerate(FONT_GRADES)}

# Whole-grade scale for step_grade (vocabulary §2.10.1: no half-grades).
WHOLE_FONT_GRADES: List[str] = [
    "5A", "5B", "5C",
    "6A", "6B", "6C",
    "7A", "7B", "7C",
    "8A", "8B", "8C",
]
_WHOLE_GRADE_TO_INDEX = {g: i for i, g in enumerate(WHOLE_FONT_GRADES)}

# ARCH-2: load_model dispatch is now data-driven from exercise JSON.
# These sets are ONLY used for exercise-specific data (fallback loads, intensity %),
# NOT for deciding which branch of logic to use.
# The load_model field in each exercise_instance drives the dispatch.
EXTERNAL_LOAD_FALLBACK_PCT_BW = {
    "barbell_row": 0.30,
    "bench_press": 0.40,
    "dumbbell_bench_press": 0.34,
    "face_pull": 0.08,
    "farmers_carry": 0.30,
    "goblet_squat": 0.12,
    "overhead_press": 0.25,
    "romanian_deadlift": 0.40,
    "split_squat": 0.15,
    "turkish_getup": 0.15,
}

# B288: freshness window for external_load load memory (accessory/prehab work).
# Not unlimited — a date must still exist and not be in the future — but long
# enough that an exercise programmed every 2-3 months keeps its remembered load
# instead of decaying back to the cold-start fallback below.
EXTERNAL_LOAD_FRESHNESS_DAYS = 3650

# Fixed fallback in kg for prehab exercises — bodyweight-% makes no sense here (A123).
EXTERNAL_LOAD_FALLBACK_FIXED_KG: dict[str, float] = {
    "elbow_eccentric_curl": 1.5,         # Tyler Twist — light dumbbell
    "forearm_pronation_supination": 1.0,  # hammer / light dumbbell
    "wrist_curl": 3.0,                   # wrist flexion
    "reverse_wrist_curl": 2.0,           # wrist extension
    "pallof_press": 10.0,                # A229: cable/band anti-rotation cold-start
}

# Similarity groups for cross-exercise load transfer (B90).
# Each group maps exercise_id → coefficient relative to group anchor (1.0).
# When exercise A has no working_loads but similar exercise B does,
# A's load is estimated as B's load × (coeff_A / coeff_B).
_SIMILARITY_GROUPS: Dict[str, Dict[str, float]] = {
    "push": {
        "bench_press": 1.0,
        "dumbbell_bench_press": 0.85,
    },
    "squat": {
        "split_squat": 1.0,
        "goblet_squat": 0.80,
    },
    "pull": {
        "barbell_row": 1.0,
        "face_pull": 0.25,
    },
}

# Pulling baseline: % of 1RM by (phase, session_intensity) for weighted_pullup.
# Session intensity comes from _intensity_label(): "easy" / "medium" / "hard".
PULLING_1RM_PCT: Dict[Tuple[str, str], float] = {
    ("base", "easy"): 0.55,
    ("base", "medium"): 0.625,
    ("base", "hard"): 0.70,
    ("strength_power", "easy"): 0.65,
    ("strength_power", "medium"): 0.75,
    ("strength_power", "hard"): 0.825,
    ("power_endurance", "easy"): 0.55,
    ("power_endurance", "medium"): 0.675,
    ("power_endurance", "hard"): 0.75,
    ("performance", "easy"): 0.60,
    ("performance", "medium"): 0.75,
    ("performance", "hard"): 0.845,
    ("deload", "easy"): 0.525,
    ("deload", "medium"): 0.525,
    ("deload", "hard"): 0.525,
}
PULLING_1RM_PCT_DEFAULT = 0.70

# Scaling factors for external_load pulling exercises relative to max_external_load_kg.
PULLING_EXTERNAL_SCALING: Dict[str, float] = {
    "barbell_row": 0.60,
    "face_pull": 0.15,
}

# Inverted index: exercise_id → (group_name, coefficient)
_EXERCISE_TO_GROUP: Dict[str, Tuple[str, float]] = {}
for _grp_name, _members in _SIMILARITY_GROUPS.items():
    for _ex_id, _coeff in _members.items():
        _EXERCISE_TO_GROUP[_ex_id] = (_grp_name, _coeff)



LOADING_PIN_DEFAULT_INTENSITY_PCT = {
    "lp_max_lift_5s": 0.92,
    "lp_max_lift_7s": 0.90,
    "lp_max_lift_10s": 0.88,
    "lp_short_lifts": 0.95,
    "lp_density_lifts": 0.75,
    "lp_repeater_lifts": 0.70,
}



# Grade → estimated max-hang total load offset from bodyweight (French sport grades, lead_max_rp).
# Source: climbing physiology literature / Lattice Training benchmarks (conservative).
GRADE_TO_HANG_OFFSET: Dict[str, float] = {
    "6b": -10, "6c": 0,
    "7a": 5,   "7a+": 10,
    "7b": 15,  "7b+": 20,
    "7c": 27,
    "8a": 35,  "8a+": 40,
    "8b": 45,
}

HANGBOARD_DEFAULT_INTENSITY_PCT: Dict[str, float] = {
    "density_hangs": 0.75,
    "hangboard_moving_hangs": 0.55,
    "horst_7_53": 0.90,  # Max strength protocol, 90% MVC (Hörst, López). Catalog notes: "90-95% intensity".
    "long_duration_hang": 0.55,
    "lopez_subhangs": 0.75,
    # max_hang_10s removed (TD-HORST-3): exercise deactivated, no session catalog file.
    # max_hang_7s removed (TD-HORST-2): excluded from _hangboard_suggested call path (line 933).
    "max_hang_ladder": 0.80,
    "one_arm_hang_assisted": 0.85,
    "repeater_15_15": 0.65,
    "repeater_hang_7_3": 0.70,
}
SURFACE_PRIORITY = ("board_kilter", "board_moonboard", "board_other", "spraywall", "gym_boulder")
VALID_FEEDBACK = {"very_easy", "easy", "ok", "hard", "very_hard"}
LEGACY_DIFFICULTY_MAP = {
    "too_easy": "very_easy",
    "easy": "easy",
    "ok": "ok",
    "hard": "hard",
    "too_hard": "very_hard",
    "fail": "very_hard",
}

DEFAULT_ADJUSTMENT_POLICY = {
    "very_easy": {"pct_range": [0.10, 0.20]},
    "easy": {"pct_range": [0.05, 0.10]},
    "ok": {"pct_range": [0.00, 0.05]},
    "hard": {"pct_range": [-0.05, 0.00]},
    "very_hard": {"pct_range": [-0.15, -0.05]},
}


# B214: central registry of assessment.tests.* scalar keys written by each
# exercise_id branch in _update_test_from_log. Exists so every branch can call
# _mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id]) instead of hand-listing
# keys — closes the D214 drift risk where a branch grows a new scalar write
# without adding the matching _mark_measured call.
#
# Per-hand exercises (lp_duration_test, lp_max_test_5s) keep an inline
# _mark_measured call because the key embeds the hand suffix dynamically.
_TEST_EXERCISE_SCALARS: Dict[str, Tuple[str, ...]] = {
    "max_hang_7s": (
        "max_hang_20mm_7s_total_kg",
        "max_hang_20mm_5s_total_kg",
    ),
    "max_hang_5s": (
        "max_hang_20mm_5s_total_kg",
        "max_hang_20mm_7s_total_kg",
    ),
    "repeater_hang_7_3": ("repeater_7_3_max_sets_20mm",),
    "test_repeater_7_3_to_failure": ("repeater_7_3_max_sets_20mm",),
    "test_max_hang_duration_20mm": ("max_hang_duration_20mm_seconds",),
    "test_l_sit_hold": ("l_sit_hold_seconds",),
    "test_hip_flexibility": ("hip_flexibility_cm",),
    "weighted_pullup": (
        "weighted_pullup_2rm_total_kg",
        "weighted_pullup_1rm_estimated_kg",
        "pulling_ratio_pct",
        "weighted_pullup_1rm_total_kg",
    ),
    "test_max_pullup_bw": ("max_pullups_bw",),
}

# exercise_ids in _update_test_from_log that mark scalars inline (dynamic key
# per hand). Listed here only so the B214 introspection test can assert
# completeness of _TEST_EXERCISE_SCALARS ∪ _TEST_EXERCISE_PER_HAND.
_TEST_EXERCISE_PER_HAND: Tuple[str, ...] = (
    "lp_duration_test",
    "lp_max_test_5s",
)


def estimate_1rm_from_2rm(total_load_kg: float) -> float:
    """Estimate 1RM from 2RM using average of Epley and Brzycki formulas (D84)."""
    epley = total_load_kg * (1 + 2 / 30)
    brzycki = total_load_kg * (36 / (37 - 2))
    return round((epley + brzycki) / 2, 1)


def canonical_feedback_label(item: Dict[str, Any]) -> str:
    feedback = str(item.get("feedback_label") or "").strip().lower()
    if feedback in VALID_FEEDBACK:
        return feedback

    legacy = str(item.get("difficulty") or item.get("difficulty_label") or "").strip().lower()
    if legacy in LEGACY_DIFFICULTY_MAP:
        return LEGACY_DIFFICULTY_MAP[legacy]

    if bool(item.get("too_hard")) or bool(item.get("fail")):
        return "very_hard"

    return "ok"


def _first_not_none(*values: Any) -> Any:
    """First value that is not None — unlike `a or b`, keeps a legitimate 0."""
    for value in values:
        if value is not None:
            return value
    return None


def _round_half_step(value: float) -> float:
    return round(value / 0.5) * 0.5


def _get_bodyweight(user_state: Dict[str, Any]) -> float:
    return float(user_state.get("bodyweight_kg") or ((user_state.get("body") or {}).get("weight_kg") or 0.0))


def _parse_day(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _get_current_phase_id(user_state: Dict[str, Any], date_str: str) -> str:
    """Extract phase_id from macrocycle for a given date."""
    mc = user_state.get("macrocycle") or {}
    phases = mc.get("phases") or []
    if not phases:
        return "base"
    start = _parse_day(mc.get("start_date"))
    target = _parse_day(date_str)
    if not start or not target:
        return str(phases[0].get("phase_id", "base"))
    elapsed_weeks = max(0, (target - start).days // 7)
    cumulative = 0
    for phase in phases:
        cumulative += phase.get("duration_weeks", 1)
        if elapsed_weeks < cumulative:
            return str(phase.get("phase_id", "base"))
    return str(phases[-1].get("phase_id", "base"))


def _get_pulling_baseline(user_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return baselines.pulling dict or None."""
    return (user_state.get("baselines") or {}).get("pulling")


def _is_fresh(updated_at: str | None, target_date: str | None, freshness_days: int) -> bool:
    updated = _parse_day(updated_at)
    target = _parse_day(target_date)
    if updated is None or target is None:
        return False
    delta = (target - updated).days
    return 0 <= delta <= freshness_days


def _relevant_setup(exercise_id: str, source: Dict[str, Any]) -> Dict[str, Any]:
    if exercise_id in ("max_hang_5s", "max_hang_7s"):
        return {
            "edge_mm": source.get("edge_mm"),
            "grip": source.get("grip"),
            "load_method": source.get("load_method"),
        }
    if _is_limit_grade_exercise(exercise_id):
        return {"surface": source.get("surface_selected") or source.get("surface")}
    return {}


def _progression_setup_and_key(exercise_id: str, source: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    setup = _relevant_setup(exercise_id, source)
    return setup, _setup_key(exercise_id, setup)


def _setup_key(exercise_id: str, setup: Dict[str, Any]) -> str:
    if exercise_id in ("max_hang_5s", "max_hang_7s"):
        pairs = [
            ("edge_mm", setup.get("edge_mm")),
            ("grip", setup.get("grip")),
            ("load_method", setup.get("load_method")),
        ]
    elif _is_limit_grade_exercise(exercise_id):
        pairs = [("surface", setup.get("surface"))]
    else:
        pairs = []
    serialized = "|".join(f"{k}={str(v)}" for k, v in pairs if v not in (None, ""))
    return f"{exercise_id}|{serialized}" if serialized else exercise_id


def normalize_font_grade(grade: str | None) -> Optional[str]:
    if grade is None:
        return None
    cleaned = str(grade).strip().upper().replace(" ", "")
    return cleaned if cleaned in FONT_GRADE_TO_INDEX else None


def step_grade(grade: str, steps: int) -> str:
    """Apply an integer offset on the whole-grade scale (vocabulary 2.10.1).

    Input + modifiers are stripped (rounded to the base whole grade).
    Output is always a whole grade without +.
    """
    cleaned = str(grade).strip().upper().replace(' ', '').replace('+', '')
    if cleaned not in _WHOLE_GRADE_TO_INDEX:
        cleaned = '6C'
    idx = _WHOLE_GRADE_TO_INDEX[cleaned] + int(steps)
    idx = max(0, min(len(WHOLE_FONT_GRADES) - 1, idx))
    return WHOLE_FONT_GRADES[idx]


_CATALOG_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _load_catalog_cache() -> Dict[str, Dict[str, Any]]:
    """Load exercise catalog keyed by id (cached, ARCH-2).

    Returns dict: exercise_id → {"load_model": str, "unilateral": bool}.
    Used as fallback when exercise_instance doesn't carry load_model
    (e.g. in test fixtures or legacy resolved data).
    """
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE
    import json as _json
    catalog_path = os.path.join(
        os.path.dirname(__file__), "..", "catalog", "exercises", "v1", "exercises.json"
    )
    try:
        with open(catalog_path) as f:
            data = _json.load(f)
        _CATALOG_CACHE = {
            e["id"]: {
                "load_model": e.get("load_model"),
                "unilateral": bool(e.get("unilateral")),
                "pattern": e.get("pattern"),
            }
            for e in data.get("exercises", [])
        }
    except FileNotFoundError:
        logger.error(
            "_load_catalog_cache: exercises.json not found at %s — exercise targets will be unavailable",
            catalog_path,
        )
        _CATALOG_CACHE = {}
    except KeyError as e:
        logger.error("_load_catalog_cache: unexpected catalog structure: %s", e)
        _CATALOG_CACHE = {}
    return _CATALOG_CACHE


def _load_catalog_load_models() -> Dict[str, Optional[str]]:
    """Return exercise_id → load_model mapping from catalog."""
    return {eid: info["load_model"] for eid, info in _load_catalog_cache().items()}


def _grade_relative_group(exercise_id: str) -> Optional[str]:
    """B289: classify a grade_relative exercise by progression semantics.

    - ``"limit"`` (pattern climbing_limit_boulder): max-grade work — memory
      keyed on surface, per-feedback grade steps (±1/±2), boulder_max_rp anchor.
    - ``"endurance"`` (climbing_intervals / climbing_continuous): the grade is
      an intensity target — memory keyed on exercise_id alone, and the target
      steps only after 2 consecutive concordant feedbacks (endurance grades
      move slowly; a single easy/hard session is noise).
    - ``"technique"`` (pattern technique_drill): the grade is comfort terrain
      for the drill, NOT a progression lever — used_grade is deliberately
      never stored.

    Returns None when the exercise is unknown or not grade_relative.
    """
    info = _load_catalog_cache().get(exercise_id) or {}
    if info.get("load_model") != "grade_relative":
        return None
    pattern = info.get("pattern")
    if pattern == "climbing_limit_boulder":
        return "limit"
    if pattern == "technique_drill":
        return "technique"
    return "endurance"


def _is_limit_grade_exercise(exercise_id: str) -> bool:
    """True for the limit-boulder family (surface-keyed grade memory).

    Falls back on the historical hardcoded id so limit_bouldering keeps its
    behaviour even if the catalog cache is unavailable (test fixtures).
    """
    return exercise_id == "limit_bouldering" or _grade_relative_group(exercise_id) == "limit"


def _extract_grade_benchmark(user_state: Dict[str, Any]) -> str:
    performance = user_state.get("performance") or {}
    preferred = (((performance.get("gym_reference") or {}).get("kilter") or {}).get("benchmark") or {}).get("grade")
    if normalize_font_grade(preferred):
        return normalize_font_grade(preferred) or "6C"

    current_level = performance.get("current_level") or {}
    nested = ((((current_level.get("gym_reference") or {}).get("kilter") or {}).get("benchmark") or {}).get("grade"))
    if normalize_font_grade(nested):
        return normalize_font_grade(nested) or "6C"

    worked = (((current_level.get("boulder") or {}).get("worked") or {}).get("grade"))
    if normalize_font_grade(worked):
        return normalize_font_grade(worked) or "6C"
    return "6C"


def _gym_equipment(user_state: Dict[str, Any], gym_id: str | None) -> List[str]:
    gyms = ((user_state.get("equipment") or {}).get("gyms") or [])
    for gym in gyms:
        if str((gym or {}).get("gym_id") or "").strip().lower() == str(gym_id or "").strip().lower():
            return [str(x).strip().lower() for x in (gym.get("equipment") or []) if str(x).strip()]
    return []


def _surface_options(user_state: Dict[str, Any], gym_id: str | None) -> List[str]:
    equip = set(_gym_equipment(user_state, gym_id))
    return [surface for surface in SURFACE_PRIORITY if surface in equip]


def _select_surface(*, preferred: str | None, options: List[str], gym_id: str | None, user_state: Dict[str, Any]) -> str:
    normalized = str(preferred or "").strip().lower()
    if normalized in SURFACE_PRIORITY:
        return normalized
    if options:
        return options[0]
    gym_equip = set(_gym_equipment(user_state, gym_id))
    for surface in SURFACE_PRIORITY:
        if surface in gym_equip:
            return surface
    return "gym_boulder"


def _intensity_label(session: Dict[str, Any]) -> str:
    intent = str(session.get("intent") or "").strip().lower()
    tags = session.get("tags") or {}
    if intent in {"warmup", "technique", "recovery", "accessory"} or tags.get("technique"):
        return "easy"
    if intent in {"power_endurance", "aerobic_endurance", "endurance", "volume"} or tags.get("volume"):
        return "medium"
    return "hard"


def _boulder_offset(session: Dict[str, Any], user_state: Dict[str, Any]) -> int:
    """Return the single primary offset for grade calculation."""
    return _boulder_target_info(session, user_state)["offset_high"]


def _boulder_target_info(session: Dict[str, Any], user_state: Dict[str, Any]) -> Dict[str, Any]:
    """Return boulder target info: offset range + attempt/rest guidance."""
    intent = str(session.get("intent") or "").strip().lower()
    tags = session.get("tags") or {}
    cfg = (((user_state.get("progression_config") or {}).get("boulder_targets") or {}).get("offsets") or {})

    if intent in {"warmup", "technique", "recovery", "accessory"} or tags.get("technique"):
        return {
            "offset_high": int(cfg.get("warmup_tech", -2)),
            "offset_low": int(cfg.get("warmup_tech", -2)) - 1,
            "attempt_guidance": None,
            "rest_guidance": None,
        }
    if intent in {"power", "limit"} or tags.get("hard"):
        return {
            "offset_high": int(cfg.get("limit_power", 0)),
            "offset_low": -1,
            "attempt_guidance": "1 serious attempt per problem, full rest between",
            "rest_guidance": "3-5 min between problems",
        }
    if intent in {"power_endurance", "aerobic_endurance", "endurance"} or tags.get("pe"):
        return {
            "offset_high": -1,
            "offset_low": -2,
            "attempt_guidance": "Multiple attempts per problem, controlled pump",
            "rest_guidance": "1-2 min between problems",
        }
    if intent == "volume" or tags.get("volume"):
        return {
            "offset_high": -2,
            "offset_low": -3,
            "attempt_guidance": "Many attempts, focus on movement quality",
            "rest_guidance": "1-2 min between problems",
        }
    return {
        "offset_high": int(cfg.get("default", -1)),
        "offset_low": int(cfg.get("default", -1)) - 1,
        "attempt_guidance": None,
        "rest_guidance": None,
    }


def _working_entries(user_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    working = user_state.setdefault("working_loads", {})
    return working.setdefault("entries", [])


def _find_working_load_entry(user_state: Dict[str, Any], exercise_id: str, setup: Dict[str, Any]) -> Dict[str, Any]:
    _, key = _progression_setup_and_key(exercise_id, setup)
    entries = _working_entries(user_state)
    for item in entries:
        if str(item.get("key") or "") == key:
            return item
    new_item = {"exercise_id": exercise_id, "key": key, "setup": setup}
    entries.append(new_item)
    entries.sort(key=lambda e: str(e.get("key") or ""))
    return new_item


def _best_entry(user_state: Dict[str, Any], exercise_id: str, setup: Dict[str, Any], date_value: str, freshness_days: Optional[int] = 60) -> Optional[Dict[str, Any]]:
    _, key = _progression_setup_and_key(exercise_id, setup)
    fresh_matching: List[Dict[str, Any]] = []
    fresh_by_exercise: List[Dict[str, Any]] = []
    # A242: non-mutating read (no setdefault) so read-only GET callers never
    # touch user_state; freshness_days=None disables the recency filter — the
    # builder proposal surfaces remembered loads regardless of age (dated, for a
    # human to review), while progression callers keep the default 60-day gate.
    entries = (user_state.get("working_loads") or {}).get("entries") or []
    for item in entries:
        if str(item.get("exercise_id") or "") != exercise_id:
            continue
        if freshness_days is not None and not _is_fresh(item.get("updated_at"), date_value, freshness_days):
            continue
        fresh_by_exercise.append(item)
        if str(item.get("key") or "") == key:
            fresh_matching.append(item)

    if fresh_matching:
        fresh_matching.sort(key=lambda e: (str(e.get("updated_at") or ""), str(e.get("key") or "")), reverse=True)
        return fresh_matching[0]

    meaningful_setup = any(v not in (None, "") for v in setup.values())
    if not meaningful_setup and len(fresh_by_exercise) == 1:
        return fresh_by_exercise[0]
    return None


def _transfer_load(
    user_state: Dict[str, Any],
    exercise_id: str,
    date_value: str,
    freshness_days: int = 60,
) -> Optional[float]:
    """Try to estimate load for *exercise_id* from a similar exercise's working_loads.

    Returns the transferred external load in kg, or None if no transfer is possible.
    """
    group_info = _EXERCISE_TO_GROUP.get(exercise_id)
    if not group_info:
        return None
    group_name, target_coeff = group_info
    group = _SIMILARITY_GROUPS[group_name]

    for donor_id, donor_coeff in group.items():
        if donor_id == exercise_id:
            continue
        entry = _best_entry(user_state, donor_id, {}, date_value, freshness_days)
        if entry and entry.get("next_external_load_kg") is not None:
            donor_load = float(entry["next_external_load_kg"])
            return _round_half_step(donor_load * (target_coeff / donor_coeff))
    return None


def check_load_coherence(
    user_state: Dict[str, Any],
    date_value: str = "",
    freshness_days: int = 60,
) -> List[Dict[str, Any]]:
    """Check for outlier load ratios within similarity groups.

    Returns a list of warnings for groups where the actual ratio between
    exercises deviates more than 2× from the expected coefficient ratio.
    """
    warnings: List[Dict[str, Any]] = []
    for group_name, members in _SIMILARITY_GROUPS.items():
        loads: Dict[str, float] = {}
        coeffs: Dict[str, float] = {}
        for ex_id, coeff in members.items():
            entry = _best_entry(user_state, ex_id, {}, date_value, freshness_days)
            if entry and entry.get("next_external_load_kg") is not None:
                loads[ex_id] = float(entry["next_external_load_kg"])
                coeffs[ex_id] = coeff
        if len(loads) < 2:
            continue
        ids = list(loads.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                expected_ratio = coeffs[a] / coeffs[b]
                actual_ratio = loads[a] / loads[b] if loads[b] > 0 else float("inf")
                deviation = actual_ratio / expected_ratio if expected_ratio > 0 else float("inf")
                if deviation > 2.0 or deviation < 0.5:
                    warnings.append({
                        "group": group_name,
                        "exercise_a": a,
                        "exercise_b": b,
                        "load_a": loads[a],
                        "load_b": loads[b],
                        "expected_ratio": round(expected_ratio, 2),
                        "actual_ratio": round(actual_ratio, 2),
                    })
    return warnings


def _max_hang_suggested(user_state: Dict[str, Any], prescription: Dict[str, Any], exercise_attrs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    bodyweight = _get_bodyweight(user_state)
    attrs = exercise_attrs or {}
    intensity = float(prescription.get("intensity_pct_of_total_load") or attrs.get("intensity_pct") or 0.9)
    baselines = ((user_state.get("baselines") or {}).get("hangboard") or [])
    if baselines:
        baseline = baselines[0]
    else:
        logger.warning("_max_hang_suggested: no hangboard baselines found — using bodyweight as fallback")
        baseline = {}
    max_total = float(baseline.get("max_total_load_kg") or bodyweight)
    target_total = _round_half_step(max_total * intensity)
    suggested_external = _round_half_step(target_total - bodyweight)
    work_s = prescription.get('work_seconds') or prescription.get('hang_seconds', 5)
    return {
        "schema_version": "progression_targets.v1",
        "suggested_total_load_kg": target_total,
        "suggested_external_load_kg": suggested_external,
        "suggested_rep_scheme": f"{prescription.get('sets', 6)}x{work_s}s",
    }


def _hangboard_suggested(user_state: Dict[str, Any], exercise_id: str, prescription: Dict[str, Any], exercise_attrs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compute suggested load for hangboard total_load exercises (not max_hang_5s)."""
    bodyweight = _get_bodyweight(user_state)
    attrs = exercise_attrs or {}
    intensity = prescription.get("intensity_pct_of_total_load")
    if intensity is None:
        intensity = attrs.get("intensity_pct")
    if intensity is None:
        intensity = HANGBOARD_DEFAULT_INTENSITY_PCT.get(exercise_id, 0.70)
    intensity = float(intensity)
    baselines = ((user_state.get("baselines") or {}).get("hangboard") or [])
    if baselines:
        baseline = baselines[0]
    else:
        logger.warning("_hangboard_suggested: no hangboard baselines for exercise %s — using bodyweight as fallback", exercise_id)
        baseline = {}
    baseline_source = ""
    if baseline.get("max_total_load_kg"):
        max_total = float(baseline["max_total_load_kg"])
        baseline_source = baseline.get("source") or ""
    else:
        # No hangboard baseline: estimate from current grade via _FINGER_BENCHMARK.
        # Fallback to 1.10× BW if grade is unknown (conservative intermediate estimate).
        current_grade = (
            ((user_state.get("assessment") or {}).get("grades") or {})
            .get("redpoint_french", "")
        )
        ratio = _FINGER_BENCHMARK.get(current_grade, 1.10)
        max_total = bodyweight * ratio
        baseline_source = "grade_fallback"
    target_total = _round_half_step(max_total * intensity)
    suggested_external = _round_half_step(target_total - bodyweight)
    work_s = prescription.get('work_seconds') or prescription.get('hang_seconds', 7)
    sets = prescription.get('sets') or (prescription.get('sets_range') or [4])[0]
    result: Dict[str, Any] = {
        "schema_version": "progression_targets.v1",
        "suggested_total_load_kg": target_total,
        "suggested_external_load_kg": suggested_external,
        "suggested_rep_scheme": f"{sets}x{work_s}s",
    }
    if "estimated" in baseline_source or baseline_source == "grade_fallback":
        result["load_source"] = "estimated"
    return result


def _loading_pin_suggested(
    user_state: Dict[str, Any],
    exercise_id: str,
    prescription: Dict[str, Any],
    exercise_attrs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute suggested loads for a loading pin exercise (unilateral, external_load).

    Returns a dict with right_hand and left_hand suggested loads.
    """
    attrs = exercise_attrs or {}
    intensity = float(
        prescription.get("intensity_pct_of_total_load")
        or attrs.get("intensity_pct")
        or LOADING_PIN_DEFAULT_INTENSITY_PCT.get(exercise_id, 0.85)
    )
    lp_baselines = (user_state.get("baselines") or {}).get("loading_pin") or []
    right_max = 0.0
    left_max = 0.0
    for bl in lp_baselines:
        hand = str(bl.get("hand") or "").lower()
        load = float(bl.get("max_load_kg") or 0)
        if hand == "right" and load > right_max:
            right_max = load
        elif hand == "left" and load > left_max:
            left_max = load

    # Fallback: estimate from hangboard baseline via conversion
    if right_max == 0.0 and left_max == 0.0:
        hb_baselines = (user_state.get("baselines") or {}).get("hangboard") or []
        if hb_baselines:
            hb_total = float(hb_baselines[0].get("max_total_load_kg") or 0)
            if hb_total > 0:
                from backend.engine.conversions import hangboard_to_loading_pin
                est = hangboard_to_loading_pin(hb_total)
                right_max = est["right"]
                left_max = est["left"]

    work_s = prescription.get("work_seconds") or 5
    sets = prescription.get("sets") or 5
    return {
        "schema_version": "progression_targets.v1",
        "right_hand": {
            "suggested_external_load_kg": _round_half_step(right_max * intensity),
        },
        "left_hand": {
            "suggested_external_load_kg": _round_half_step(left_max * intensity),
        },
        "suggested_rep_scheme": f"{sets}x{work_s}s",
    }


def estimate_missing_baselines(user_state: Dict[str, Any]) -> None:
    """Fill missing hangboard and pulling baselines from grade/pullup test.

    Modifies user_state in-place. Never overwrites a baseline whose source == "test".
    """
    _estimate_hangboard_baseline(user_state)
    _estimate_pulling_baseline(user_state)


def _estimate_hangboard_baseline(user_state: Dict[str, Any]) -> None:
    """Fill missing hangboard baseline from grade or pullup test (NEW-F11).

    Triggers when max_total_load_kg is absent, null, or <= (bodyweight - 10).
    """
    bodyweight = _get_bodyweight(user_state)
    baselines = ((user_state.get("baselines") or {}).get("hangboard") or [])
    baseline = baselines[0] if baselines else {}

    # Never overwrite a real test baseline
    if baseline.get("source") == "test":
        return

    existing = baseline.get("max_total_load_kg")
    if existing and float(existing) > bodyweight - 10:
        return  # Valid baseline present — skip estimation

    tests_data = ((user_state.get("assessment") or {}).get("tests") or {})
    tests_src = ((user_state.get("assessment") or {}).get("tests_source") or {})

    estimated: Optional[float] = None
    grade_used: Optional[str] = None
    source: Optional[str] = None

    # D214 F1: Priority 0 — user-measured max hang scalar wins over grade estimate.
    # Gated on tests_source == "measured" so fallback paths still fire when the
    # scalar was only estimated at onboarding.
    direct_hang = (
        tests_data.get("max_hang_20mm_7s_total_kg")
        or tests_data.get("max_hang_20mm_5s_total_kg")
    )
    direct_hang_src = (
        tests_src.get("max_hang_20mm_7s_total_kg")
        or tests_src.get("max_hang_20mm_5s_total_kg")
    )
    if direct_hang is not None and direct_hang_src == "measured":
        estimated = float(direct_hang)
        source = "test"

    # Priority 1: estimate from lead_max_rp grade
    lead_rp = (
        ((user_state.get("assessment") or {}).get("grades") or {})
        .get("lead_max_rp", "")
    )
    if lead_rp:
        lead_rp = lead_rp.lower()

    if estimated is None and lead_rp and lead_rp in GRADE_TO_HANG_OFFSET:
        estimated = bodyweight + GRADE_TO_HANG_OFFSET[lead_rp]
        grade_used = lead_rp
        source = "estimated_from_grade"
    elif estimated is None:
        # Priority 2: estimate from max weighted pullup test (B121 key fix)
        # D84: prefer estimated 1RM from 2RM, fall back to legacy direct 1RM
        pullup_1rm_total = (
            tests_data.get("weighted_pullup_1rm_estimated_kg")
            or tests_data.get("weighted_pullup_1rm_total_kg")
        )
        if pullup_1rm_total is not None:
            estimated = float(pullup_1rm_total) * 0.85
            source = "estimated_from_pullup"

    if estimated is None:
        return  # Cannot estimate — leave unchanged

    estimated = _round_half_step(estimated)
    today = datetime.now().strftime("%Y-%m-%d")

    # B-HORST-INTENSITY: populate protocol fields so downstream
    # _pick_hangboard_baseline can match without fallback. Defaults match
    # primary test protocol (max_hang_7s on 20mm half_crimp).
    new_entry: Dict[str, Any] = {
        "max_total_load_kg": estimated,
        "source": source,
        "hang_seconds": 7,
        "edge_mm": 20,
        "grip": "half_crimp",
    }
    # D214 F1: when the baseline is seeded from a user-measured scalar we stamp
    # updated_at (real test timestamp). Estimates keep estimated_at so week.py
    # freshness gate does not treat them as real tests.
    if source == "test":
        new_entry["updated_at"] = today
    else:
        new_entry["estimated_at"] = today
    if grade_used:
        new_entry["grade_used"] = grade_used

    # Write into baselines.hangboard[0]
    if not user_state.get("baselines"):
        user_state["baselines"] = {}
    hb = user_state["baselines"].get("hangboard") or []
    if hb:
        hb[0] = {**hb[0], **new_entry}
    else:
        user_state["baselines"]["hangboard"] = [new_entry]


def _estimate_pulling_baseline(user_state: Dict[str, Any]) -> None:
    """Fill baselines.pulling from assessment.tests.weighted_pullup_1rm_total_kg (B121).

    B215: source-gated on tests_source to mirror _estimate_hangboard_baseline
    Priority 0. When the scalar is user-measured, stamp source="test" +
    updated_at (real test semantics). When estimated or unmarked (legacy
    default), stamp source="estimated_from_assessment" + estimated_at so
    downstream readers can gate on baseline source alone.

    Never overwrites a baseline whose source == "test" or "test_session".
    """
    pulling = (user_state.get("baselines") or {}).get("pulling") or {}
    if pulling.get("source") in ("test", "test_session"):
        return

    bodyweight = _get_bodyweight(user_state)
    if bodyweight <= 0:
        return

    tests_data = ((user_state.get("assessment") or {}).get("tests") or {})
    tests_src = ((user_state.get("assessment") or {}).get("tests_source") or {})
    # D84: prefer estimated 1RM from 2RM, fall back to legacy direct 1RM
    pullup_1rm_total = (
        tests_data.get("weighted_pullup_1rm_estimated_kg")
        or tests_data.get("weighted_pullup_1rm_total_kg")
    )
    if pullup_1rm_total is None:
        return

    pullup_1rm_total = float(pullup_1rm_total)
    max_external = _round_half_step(pullup_1rm_total - bodyweight)
    today = datetime.now().strftime("%Y-%m-%d")

    # B215: mirror hangboard Priority 0 — measured 1RM at onboarding promotes
    # the baseline to source="test" so future readers can gate on source alone.
    measured_1rm = (
        tests_src.get("weighted_pullup_1rm_estimated_kg") == "measured"
        or tests_src.get("weighted_pullup_1rm_total_kg") == "measured"
        or tests_src.get("weighted_pullup_2rm_total_kg") == "measured"
    )

    new_pulling: Dict[str, Any] = {
        "weighted_pullup_1rm_total_kg": _round_half_step(pullup_1rm_total),
        "bodyweight_kg": bodyweight,
        "max_external_load_kg": max_external,
    }
    if measured_1rm:
        new_pulling["source"] = "test"
        new_pulling["updated_at"] = today
    else:
        new_pulling["source"] = "estimated_from_assessment"
        new_pulling["estimated_at"] = today

    if not user_state.get("baselines"):
        user_state["baselines"] = {}
    user_state["baselines"]["pulling"] = new_pulling


def inject_targets(resolved_day: Dict[str, Any], user_state: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(resolved_day)
    user_state = deepcopy(user_state)  # Work on a local copy — don't mutate caller state
    estimate_missing_baselines(user_state)  # Fill missing hangboard + pulling baselines
    out["targets_schema_version"] = "progression_targets.v1"
    benchmark_grade = _extract_grade_benchmark(user_state)
    catalog_lm = _load_catalog_load_models()  # ARCH-2: fallback for instances without load_model

    for session in out.get("sessions") or []:
        intensity = _intensity_label(session)
        boulder_info = _boulder_target_info(session, user_state)
        for inst in session.get("exercise_instances") or []:
            ex_id = str(inst.get("exercise_id") or "")
            prescription = inst.get("prescription") or {}
            suggested: Dict[str, Any] = dict(inst.get("suggested") or {})

            load_model = inst.get("load_model") or catalog_lm.get(ex_id)
            is_unilateral = inst.get("unilateral") if "unilateral" in inst else (_load_catalog_cache().get(ex_id, {}).get("unilateral", False))

            # --- total_load: special-case exercises with unique logic ---
            if ex_id in ("max_hang_5s", "max_hang_7s"):
                suggested.update(_max_hang_suggested(user_state, prescription, exercise_attrs=inst.get("attributes")))
                inject_source = dict(prescription)
                inject_source.update(inst.get("suggested") or {})
                setup, _ = _progression_setup_and_key(ex_id, inject_source)
                entry = _best_entry(user_state, ex_id, setup, out.get("date") or "")
                bodyweight = _get_bodyweight(user_state)

                if entry and entry.get("next_external_load_kg") is not None:
                    external = _round_half_step(float(entry["next_external_load_kg"]))
                    suggested["suggested_external_load_kg"] = external
                    suggested["suggested_total_load_kg"] = _round_half_step(bodyweight + external)
                elif entry and entry.get("next_total_load_kg") is not None:
                    total = _round_half_step(float(entry["next_total_load_kg"]))
                    suggested["suggested_total_load_kg"] = total
                    suggested["suggested_external_load_kg"] = _round_half_step(total - bodyweight)
                elif entry and str(entry.get("last_feedback_label") or "") in {"hard", "very_hard"}:
                    pct = _rule_midpoint_pct(user_state, str(entry.get("last_feedback_label") or "ok"))
                    next_external = _round_half_step(float(suggested.get("suggested_external_load_kg") or 0.0) * (1.0 + pct))
                    suggested["suggested_external_load_kg"] = next_external
                    suggested["suggested_total_load_kg"] = _round_half_step(bodyweight + next_external)
                    write_entry = _find_working_load_entry(user_state, ex_id, setup)
                    write_entry["next_external_load_kg"] = next_external
                    write_entry["updated_at"] = out.get("date")
            elif ex_id == "weighted_pullup":
                # weighted_pullup: working_loads → baselines.pulling → bodyweight (B121)
                entry = _best_entry(user_state, ex_id, {}, out.get("date") or "")
                bodyweight = _get_bodyweight(user_state)
                next_external: float = 0.0
                load_source: Optional[str] = None

                if entry and entry.get("next_external_load_kg") is not None:
                    next_external = float(entry["next_external_load_kg"])
                else:
                    pulling = _get_pulling_baseline(user_state)
                    if pulling and pulling.get("weighted_pullup_1rm_total_kg"):
                        rm_total = float(pulling["weighted_pullup_1rm_total_kg"])
                        phase_id = _get_current_phase_id(user_state, out.get("date") or "")
                        pct = PULLING_1RM_PCT.get((phase_id, intensity), PULLING_1RM_PCT_DEFAULT)
                        target_total = _round_half_step(rm_total * pct)
                        next_external = max(0.0, _round_half_step(target_total - bodyweight))
                        load_source = "baselines.pulling"

                reps = prescription.get("reps") or (prescription.get("reps_range") or [5])[0]
                sets = prescription.get("sets") or (prescription.get("sets_range") or [4])[0]
                suggested.update({
                    "schema_version": "progression_targets.v1",
                    "suggested_external_load_kg": _round_half_step(next_external),
                    "suggested_total_load_kg": _round_half_step(bodyweight + next_external),
                    "suggested_rep_scheme": f"{sets}x{reps}",
                })
                if load_source:
                    suggested["load_source"] = load_source

            # B289 group A: the whole limit-boulder family (limit_bouldering,
            # board_limit_boulders, spray_wall_limit, system_board_limit)
            # shares the surface-keyed grade memory below.
            if _is_limit_grade_exercise(ex_id):
                options = _surface_options(user_state, session.get("gym_id"))
                selected_surface = _select_surface(preferred=None, options=options, gym_id=session.get("gym_id"), user_state=user_state)
                # B260: anchor to the catalog grade_ref (boulder_max_rp) from
                # assessment.grades, NOT the board benchmark. Limit bouldering must
                # anchor to redpoint (band RP-1 -> RP), per Hörst et al. The board
                # benchmark (~onsight level) is only a fallback when the assessment
                # grade is missing. boulder_info still drives attempt/rest guidance.
                grades = ((user_state.get("assessment") or {}).get("grades") or {})
                anchor_ref = prescription.get("grade_ref") or "boulder_max_rp"
                anchor_raw = grades.get(anchor_ref)
                anchor_grade = (
                    str(anchor_raw).strip().upper().replace(" ", "")
                    if anchor_raw is not None
                    else benchmark_grade
                )
                anchor_offset = int(prescription.get("grade_offset") or 0)
                target_grade = step_grade(anchor_grade, anchor_offset)
                target_grade_low = step_grade(anchor_grade, anchor_offset - 1)
                grade_entry = _best_entry(
                    user_state,
                    ex_id,
                    {"surface": selected_surface},
                    out.get("date") or "",
                )
                if grade_entry and normalize_font_grade(grade_entry.get("next_target_grade")):
                    target_grade = grade_entry["next_target_grade"]
                boulder_target: Dict[str, Any] = {
                    "schema_version": "boulder_grade_font_v0",
                    "surface_options": options,
                    "surface_selected": selected_surface,
                    "target_grade": target_grade,
                    "target_grade_low": target_grade_low,
                    "intensity_label": intensity,
                }
                if boulder_info.get("attempt_guidance"):
                    boulder_target["attempt_guidance"] = boulder_info["attempt_guidance"]
                if boulder_info.get("rest_guidance"):
                    boulder_target["rest_guidance"] = boulder_info["rest_guidance"]
                suggested["suggested_boulder_target"] = boulder_target

            # Grade-relative exercises with grade_ref (excludes the limit-boulder
            # family, which has its own logic above)
            grade_ref = prescription.get("grade_ref")
            if grade_ref and not _is_limit_grade_exercise(ex_id):
                grades = ((user_state.get("assessment") or {}).get("grades") or {})
                ref_grade_raw = grades.get(grade_ref)
                if ref_grade_raw is not None:
                    # Normalize: lead grades are lowercase French (e.g. "7a+"), convert to uppercase Font
                    ref_grade_str = str(ref_grade_raw).strip().upper().replace(" ", "")
                    grade_offset = int(prescription.get("grade_offset") or 0)
                    suggested_grade = step_grade(ref_grade_str, grade_offset)
                    suggested["suggested_grade"] = suggested_grade
                    suggested["grade_ref"] = grade_ref
                    suggested["grade_offset"] = grade_offset
                # B289 group B: a remembered endurance target (written by
                # apply_feedback after 2 concordant feedbacks) overrides the
                # static assessment anchor. 60-day freshness gate as for every
                # grade entry.
                if _grade_relative_group(ex_id) == "endurance":
                    mem_entry = _best_entry(user_state, ex_id, {}, out.get("date") or "")
                    if mem_entry and normalize_font_grade(mem_entry.get("next_target_grade")):
                        suggested["suggested_grade"] = mem_entry["next_target_grade"]
                        suggested["grade_ref"] = grade_ref
                        suggested["grade_source"] = "working_loads"

            # External load exercises — data-driven from load_model (ARCH-2)
            if load_model == "external_load" and not is_unilateral:
                # B288: widened freshness window for external_load. For
                # prehab/accessory work the remembered load is "which dumbbell
                # did I pick up", not a physiological test — a real observation
                # from 4 months ago beats EXTERNAL_LOAD_FALLBACK_FIXED_KG every
                # time. Prehab recurs every 2-3 months, so the 60-day default
                # guaranteed a permanent reset to the cold-start default
                # (reverse_wrist_curl pinned at 2.0kg from 2026-03-30 to
                # 2026-07-20 despite being logged in between).
                #
                # Deliberately a WIDE WINDOW, not freshness_days=None: _is_fresh
                # is also the guard that rejects a missing/unparseable target
                # date (B-fix-CORE) and future-dated entries. Disabling it
                # outright resurrected the exact bug those guard rails pin.
                # The 60-day gate stays for max-hang / hangboard / loading-pin /
                # grade entries, where a stale max IS dangerous.
                entry = _best_entry(
                    user_state, ex_id, {}, out.get("date") or "",
                    freshness_days=EXTERNAL_LOAD_FRESHNESS_DAYS,
                )
                if entry and entry.get("next_external_load_kg") is not None:
                    next_load = _round_half_step(float(entry["next_external_load_kg"]))
                else:
                    transferred = _transfer_load(user_state, ex_id, out.get("date") or "")
                    if transferred is not None:
                        next_load = transferred
                        suggested["load_source"] = "transferred"
                    elif ex_id in EXTERNAL_LOAD_FALLBACK_FIXED_KG:
                        # A123: prehab — fixed fallback in kg (not bodyweight-%)
                        next_load = EXTERNAL_LOAD_FALLBACK_FIXED_KG[ex_id]
                    elif ex_id in PULLING_EXTERNAL_SCALING:
                        # B121: use baselines.pulling as anchor for pulling exercises
                        pulling = _get_pulling_baseline(user_state)
                        if pulling and pulling.get("max_external_load_kg"):
                            max_ext = float(pulling["max_external_load_kg"])
                            scaling = PULLING_EXTERNAL_SCALING[ex_id]
                            next_load = _round_half_step(max_ext * scaling)
                            suggested["load_source"] = "baselines.pulling"
                        else:
                            bw = _get_bodyweight(user_state)
                            pct = EXTERNAL_LOAD_FALLBACK_PCT_BW.get(ex_id, 0.15)
                            next_load = _round_half_step(bw * pct)
                    else:
                        bw = _get_bodyweight(user_state)
                        pct = EXTERNAL_LOAD_FALLBACK_PCT_BW.get(ex_id, 0.15)
                        next_load = _round_half_step(bw * pct)
                reps = prescription.get("reps") or (prescription.get("reps_range") or [8])[0]
                sets = prescription.get("sets") or (prescription.get("sets_range") or [3])[0]
                suggested.update({
                    "schema_version": "progression_targets.v1",
                    "suggested_external_load_kg": next_load,
                    "suggested_rep_scheme": f"{sets}x{reps}",
                })

            # Hangboard total_load exercises (repeaters, density hangs, etc.) — data-driven (ARCH-2)
            if load_model == "total_load" and ex_id not in ("max_hang_5s", "max_hang_7s", "weighted_pullup"):
                hb_suggested = _hangboard_suggested(user_state, ex_id, prescription, exercise_attrs=inst.get("attributes"))
                suggested.update(hb_suggested)
                entry = _best_entry(user_state, ex_id, {}, out.get("date") or "")
                if entry and entry.get("next_external_load_kg") is not None:
                    bodyweight = _get_bodyweight(user_state)
                    external = _round_half_step(float(entry["next_external_load_kg"]))
                    suggested["suggested_external_load_kg"] = external
                    suggested["suggested_total_load_kg"] = _round_half_step(bodyweight + external)
                    suggested.pop("load_source", None)  # Overridden by working_loads
                elif entry and entry.get("next_total_load_kg") is not None:
                    total = _round_half_step(float(entry["next_total_load_kg"]))
                    suggested["suggested_total_load_kg"] = total
                    suggested["suggested_external_load_kg"] = _round_half_step(total - _get_bodyweight(user_state))
                    suggested.pop("load_source", None)  # Overridden by working_loads
                # Warn if counterweight is required (external load is negative)
                if (suggested.get("suggested_external_load_kg") or 0) < 0:
                    suggested["load_warning"] = (
                        "counterweight_required — consider re-running max_hang_7s test"
                    )

            # Loading pin exercises (unilateral, external_load) — data-driven (ARCH-2)
            if load_model == "external_load" and is_unilateral:
                lp_sug = _loading_pin_suggested(user_state, ex_id, prescription, exercise_attrs=inst.get("attributes"))
                suggested.update(lp_sug)
                # Override from working_loads per-hand
                for hand in ("right", "left"):
                    hand_key = f"{ex_id}:{hand}"
                    hand_entry = None
                    for wl in _working_entries(user_state):
                        if str(wl.get("key") or "") == hand_key:
                            if _is_fresh(wl.get("updated_at"), out.get("date") or "", 60):
                                hand_entry = wl
                            break
                    if hand_entry and hand_entry.get("next_external_load_kg") is not None:
                        suggested[f"{hand}_hand"]["suggested_external_load_kg"] = _round_half_step(
                            float(hand_entry["next_external_load_kg"])
                        )

            if suggested:
                inst["suggested"] = suggested

    return out


def _rule_midpoint_pct(user_state: Dict[str, Any], label: str) -> float:
    rules = (((user_state.get("working_loads") or {}).get("rules") or {}).get("adjustment_policy") or {})
    policy = rules.get(label) or DEFAULT_ADJUSTMENT_POLICY.get(label) or {}
    pct_range = policy.get("pct_range") or [0.0, 0.0]
    if len(pct_range) != 2:
        return 0.0
    return float(pct_range[0] + pct_range[1]) / 2.0


def _grade_delta_for_feedback(label: str) -> int:
    return {
        "very_easy": 2,
        "easy": 1,
        "ok": 0,
        "hard": -1,
        "very_hard": -2,
    }.get(label, 0)


def _flatten_planned_instances(log_entry: Dict[str, Any]) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for session in log_entry.get("planned") or []:
        for inst in session.get("exercise_instances") or []:
            pairs.append((session, inst))
    return pairs


def _lookup_planned_instance(log_entry: Dict[str, Any], exercise_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    for session, inst in _flatten_planned_instances(log_entry):
        if str(inst.get("exercise_id") or "") == exercise_id:
            return session, inst
    return {}, {}


def _ensure_test_queue(user_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    queue = user_state.setdefault("test_queue", [])
    if not isinstance(queue, list):
        queue = []
        user_state["test_queue"] = queue
    return queue


def _enqueue_test(user_state: Dict[str, Any], *, test_id: str, date_value: str, offset_days: int, reason: str) -> None:
    queue = _ensure_test_queue(user_state)
    created = _parse_day(date_value)
    by_date = (created + timedelta(days=offset_days)).date().isoformat() if created else date_value

    dedupe_window_days = 21
    for item in queue:
        if str(item.get("test_id") or "") != test_id:
            continue
        existing_created = _parse_day(str(item.get("created_at") or ""))
        if created is None or existing_created is None:
            if str(item.get("created_at") or "") == date_value:
                return
            continue
        if abs((created - existing_created).days) <= dedupe_window_days:
            return
    queue.append(
        {
            "test_id": test_id,
            "recommended_by_date": by_date,
            "reason": reason,
            "created_at": date_value,
        }
    )
    queue.sort(key=lambda x: (str(x.get("recommended_by_date") or ""), str(x.get("test_id") or ""), str(x.get("created_at") or "")))


def _update_test_from_log(log_entry: Dict[str, Any], updated: Dict[str, Any], bodyweight: float) -> None:
    """Extract test results from a session log and persist them to user_state.

    Two-tier storage design (NOT a double-write — verified B200 / TD-HORST-1):

    1. ``updated["assessment"]["tests"]`` — flat dict of LATEST SCALARS
       (e.g. ``max_hang_20mm_7s_total_kg: 100.0``). Overwritten on every new
       test result. Consumed by ``assessment_v1.compute_assessment_profile``
       to recompute the 5-axis profile, and by baseline fillers
       (``_get_pulling_baseline``, B121).

    2. ``updated["tests"]`` (top-level) — append-only HISTORY LOG keyed by
       category (``max_strength``, ``repeater_strength_endurance``,
       ``pulling_strength``). Each entry carries metadata: date, bodyweight,
       freshness_policy, confidence, setup. Used for progression tracking
       over time (e.g. ``week.py`` reads ``repeater_strength_endurance``
       history for hangboard protocol decisions).

    The two tiers are complementary, not redundant:
    ``assessment.tests`` answers "what is the athlete's current level?",
    ``tests`` answers "how has the athlete progressed?". Only tests with
    rich metadata needs (max_hang, repeater, weighted_pullup) write to both
    tiers; simple measurements (hip_flexibility, l_sit_hold, etc.) write
    only the scalar — intentional, do not uniform without a dedicated brief.
    """
    planned_sessions = log_entry.get("planned") or []
    feedback_items = ((log_entry.get("actual") or {}).get("exercise_feedback_v1") or [])
    test_sessions = [s for s in planned_sessions if str(s.get("session_id") or "").startswith("test_") or bool((s.get("tags") or {}).get("test"))]
    if not test_sessions:
        top_session_id = str(log_entry.get("session_id") or "")
        # B156: also process if any feedback item is a test_measurement exercise
        # (covers test exercises added via Add Exercise to non-test sessions)
        has_test_measurement = any(
            str(fb.get("exercise_id") or "").startswith("test_")
            for fb in feedback_items
        )
        if not top_session_id.startswith("test_") and not has_test_measurement:
            return
    date_str = str(log_entry.get("date") or "")
    assessment = updated.setdefault("assessment", {})
    at = assessment.setdefault("tests", {})
    # D214: tests_source sidecar — every scalar written below is a measured result
    at_src = assessment.setdefault("tests_source", {})

    def _mark_measured(*keys: str) -> None:
        for k in keys:
            at_src[k] = "measured"

    for item in feedback_items:
        exercise_id = str(item.get("exercise_id") or "")

        # --- Max hang 7s (D85 — primary test) ---
        if exercise_id == "max_hang_7s":
            used_total = item.get("used_total_load_kg")
            if used_total is None:
                continue
            total = _round_half_step(float(used_total))
            external = _round_half_step(total - bodyweight)
            tests = updated.setdefault("tests", {})
            max_strength = tests.setdefault("max_strength", [])
            entry = {
                "test_id": "max_hang_7s_total_load",
                "date": date_str,
                "exercise_id": "max_hang_7s",
                "bodyweight_kg": bodyweight,
                "total_load_kg": total,
                "external_load_kg": external,
                "setup": {"hang_seconds": 7},
                "freshness_policy": {"stale_after_days": 90},
                "confidence": "high",
            }
            max_strength.append(entry)
            max_strength.sort(key=lambda x: (str(x.get("date") or ""), str(x.get("test_id") or "")))
            # B-HORST-INTENSITY: write full protocol fields so _pick_hangboard_baseline
            # can match without falling back + warning. Catalog max_hang_7s.attributes:
            # edge_mm=20, grip=half_crimp.
            baselines = updated.setdefault("baselines", {}).setdefault("hangboard", [{"max_total_load_kg": total}])
            if baselines:
                baselines[0]["max_total_load_kg"] = total
                baselines[0]["source"] = "test"
                baselines[0]["updated_at"] = date_str
                baselines[0]["hang_seconds"] = 7
                baselines[0]["edge_mm"] = 20
                baselines[0]["grip"] = "half_crimp"
            # Write scalar to assessment.tests (both keys for compat)
            at["max_hang_20mm_7s_total_kg"] = total
            at["max_hang_20mm_5s_total_kg"] = total  # legacy compat: assessment_v1 reads this key
            _mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id])

        # --- Max hang 5s (legacy — still accepted for backward compat) ---
        elif exercise_id == "max_hang_5s":
            used_total = item.get("used_total_load_kg")
            if used_total is None:
                continue
            total = _round_half_step(float(used_total))
            external = _round_half_step(total - bodyweight)
            tests = updated.setdefault("tests", {})
            max_strength = tests.setdefault("max_strength", [])
            entry = {
                "test_id": "max_hang_5s_total_load",
                "date": date_str,
                "exercise_id": "max_hang_5s",
                "bodyweight_kg": bodyweight,
                "total_load_kg": total,
                "external_load_kg": external,
                "setup": {"hang_seconds": 5},
                "freshness_policy": {"stale_after_days": 90},
                "confidence": "high",
            }
            max_strength.append(entry)
            max_strength.sort(key=lambda x: (str(x.get("date") or ""), str(x.get("test_id") or "")))
            # B-HORST-INTENSITY: write full protocol fields (legacy 5s branch
            # previously omitted even hang_seconds). Catalog max_hang_5s.attributes:
            # edge_mm=20, grip=half_crimp.
            baselines = updated.setdefault("baselines", {}).setdefault("hangboard", [{"max_total_load_kg": total}])
            if baselines:
                baselines[0]["max_total_load_kg"] = total
                baselines[0]["source"] = "test"
                baselines[0]["updated_at"] = date_str
                baselines[0]["hang_seconds"] = 5
                baselines[0]["edge_mm"] = 20
                baselines[0]["grip"] = "half_crimp"
            # Write scalar to assessment.tests (legacy key)
            at["max_hang_20mm_5s_total_kg"] = total
            _mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id])

        # --- Repeater 7/3 (legacy: sets-based, new: reps to failure) ---
        elif exercise_id in ("repeater_hang_7_3", "test_repeater_7_3_to_failure"):
            # B133: new test exercise reports completed_reps; legacy reports completed_sets
            completed = item.get("completed_reps") or item.get("completed_sets")
            if completed is None:
                continue
            completed = int(completed)
            tests = updated.setdefault("tests", {})
            rep_history = tests.setdefault("repeater_strength_endurance", [])
            rep_history.append({
                "test_id": "repeater_7_3_max_reps",
                "date": date_str,
                "exercise_id": exercise_id,
                "bodyweight_kg": bodyweight,
                "completed_reps": completed,
                "freshness_policy": {"stale_after_days": 90},
                "confidence": "high",
            })
            rep_history.sort(key=lambda x: (str(x.get("date") or ""), str(x.get("test_id") or "")))
            # Write scalar to assessment.tests (same key for backward compat)
            at["repeater_7_3_max_sets_20mm"] = completed
            _mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id])

        # --- Max hang duration (BW, 20mm) ---
        elif exercise_id == "test_max_hang_duration_20mm":
            value = item.get("max_hang_duration_20mm_seconds")
            if value is None:
                continue
            at["max_hang_duration_20mm_seconds"] = float(value)
            _mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id])

        # --- L-sit hold ---
        elif exercise_id == "test_l_sit_hold":
            value = item.get("l_sit_hold_seconds")
            if value is None:
                continue
            at["l_sit_hold_seconds"] = float(value)
            _mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id])

        # --- Hip flexibility ---
        elif exercise_id == "test_hip_flexibility":
            value = item.get("hip_flexibility_cm")
            if value is None:
                continue
            at["hip_flexibility_cm"] = float(value)
            _mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id])

        # --- Weighted pull-up (D84: now 2RM protocol, derive 1RM) ---
        elif exercise_id == "weighted_pullup":
            used_total = item.get("used_total_load_kg")
            used_external = item.get("used_external_load_kg")
            if used_total is None and used_external is not None:
                used_total = float(used_external) + bodyweight
            if used_total is None:
                continue
            total_2rm = _round_half_step(float(used_total))
            external_2rm = _round_half_step(total_2rm - bodyweight)
            estimated_1rm = estimate_1rm_from_2rm(total_2rm)
            pulling_ratio = round((total_2rm / bodyweight) * 100, 1) if bodyweight > 0 else 0.0
            tests = updated.setdefault("tests", {})
            pull_history = tests.setdefault("pulling_strength", [])
            pull_history.append({
                "test_id": "weighted_pullup_2rm",
                "date": date_str,
                "exercise_id": "weighted_pullup",
                "bodyweight_kg": bodyweight,
                "total_load_2rm_kg": total_2rm,
                "external_load_2rm_kg": external_2rm,
                "estimated_1rm_kg": estimated_1rm,
                "pulling_ratio_pct": pulling_ratio,
                "freshness_policy": {"stale_after_days": 90},
                "confidence": "high",
            })
            pull_history.sort(key=lambda x: (str(x.get("date") or ""), str(x.get("test_id") or "")))
            # Write scalars to assessment.tests
            at["weighted_pullup_2rm_total_kg"] = total_2rm
            at["weighted_pullup_1rm_estimated_kg"] = estimated_1rm
            at["pulling_ratio_pct"] = pulling_ratio
            # Legacy compat: keep 1rm field pointing to estimated value
            at["weighted_pullup_1rm_total_kg"] = estimated_1rm
            _mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id])
            # B121: update baselines.pulling from test
            pulling_baselines = updated.setdefault("baselines", {})
            pulling_baselines["pulling"] = {
                "weighted_pullup_2rm_total_kg": total_2rm,
                "weighted_pullup_1rm_estimated_kg": estimated_1rm,
                "weighted_pullup_1rm_total_kg": estimated_1rm,  # legacy compat
                "bodyweight_kg": bodyweight,
                "bodyweight_at_test_kg": bodyweight,
                "max_external_load_kg": _round_half_step(estimated_1rm - bodyweight),
                "pulling_ratio_pct": pulling_ratio,
                "source": "test_session",
                "updated_at": date_str,
            }

        # --- Bodyweight pull-up max reps test (D84b) ---
        elif exercise_id == "test_max_pullup_bw":
            value = item.get("max_pullups_bw")
            if value is None:
                continue
            at["max_pullups_bw"] = int(value)
            _mark_measured(*_TEST_EXERCISE_SCALARS[exercise_id])

        # --- Loading pin duration test (seconds per hand) ---
        elif exercise_id == "lp_duration_test":
            value = item.get("lp_duration_test_seconds")
            hand = str(item.get("hand") or "").lower()
            if value is None or hand not in ("right", "left"):
                continue
            at[f"lp_duration_test_{hand}_seconds"] = float(value)
            _mark_measured(f"lp_duration_test_{hand}_seconds")

        # --- Loading pin max test 5s ---
        elif exercise_id == "lp_max_test_5s":
            hand = str(item.get("hand") or "").lower()
            used_load = item.get("used_external_load_kg")
            if used_load is None or hand not in ("right", "left"):
                continue
            load_kg = _round_half_step(float(used_load))
            # Update baselines.loading_pin
            lp_baselines = updated.setdefault("baselines", {}).setdefault("loading_pin", [])
            existing = next((b for b in lp_baselines if str(b.get("hand") or "").lower() == hand), None)
            if existing:
                existing["max_load_kg"] = load_kg
                existing["source"] = "test"
                existing["updated_at"] = date_str
            else:
                lp_baselines.append({
                    "max_load_kg": load_kg,
                    "hand": hand,
                    "edge_mm": 20,
                    "grip": "half_crimp",
                    "lift_seconds": 5,
                    "source": "test",
                    "updated_at": date_str,
                })
            # Write scalar to assessment.tests
            at[f"lp_max_lift_5s_{hand}_kg"] = load_kg
            _mark_measured(f"lp_max_lift_5s_{hand}_kg")


def apply_feedback(log_entry: Dict[str, Any], user_state: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(user_state)
    actual = log_entry.get("actual") or {}
    feedback_items = actual.get("exercise_feedback_v1") or []
    date_value = str(log_entry.get("date") or "")
    bodyweight = _get_bodyweight(updated)

    counters = updated.setdefault("progression_counters", {})
    if not isinstance(counters, dict):
        counters = {}
        updated["progression_counters"] = counters
    _ensure_test_queue(updated)
    max_hang_hard = int(counters.get("max_hang_5s_hard_streak") or 0)
    max_hang_easy = int(counters.get("max_hang_5s_easy_streak") or 0)

    for item in feedback_items:
        exercise_id = str(item.get("exercise_id") or "").strip()
        if not exercise_id:
            continue
        feedback_label = canonical_feedback_label(item)

        session, planned_inst = _lookup_planned_instance(log_entry, exercise_id)
        planned_prescription = (planned_inst.get("prescription") or {}) if planned_inst else {}
        planned_target = (((planned_inst.get("suggested") or {}).get("suggested_boulder_target") or {}) if planned_inst else {})
        catalog_info = _load_catalog_cache().get(exercise_id, {})
        fb_load_model = (planned_inst.get("load_model") if planned_inst else None) or item.get("load_model") or catalog_info.get("load_model")
        fb_unilateral = (planned_inst.get("unilateral") if planned_inst and "unilateral" in planned_inst else None)
        if fb_unilateral is None:
            fb_unilateral = item.get("unilateral") if "unilateral" in item else catalog_info.get("unilateral", False)

        if fb_load_model == "total_load":
            used_total = item.get("used_total_load_kg")
            used_external = item.get("used_external_load_kg")
            if used_total is None and used_external is not None:
                used_total = float(used_external) + bodyweight
            if used_external is None and used_total is not None:
                used_external = float(used_total) - bodyweight
            if used_total is None and used_external is None:
                continue

            pct = _rule_midpoint_pct(updated, feedback_label)
            next_total = _round_half_step(float(used_total) * (1.0 + pct))
            next_external = _round_half_step(next_total - bodyweight)
            setup_source = dict(planned_prescription)
            setup_source.update(item)
            setup, setup_key = _progression_setup_and_key(exercise_id, setup_source)

            entry = _find_working_load_entry(updated, exercise_id, setup)
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": setup_key,
                    "setup": setup,
                    "last_completed": bool(item.get("completed", False)),
                    "last_feedback_label": feedback_label,
                    "last_external_load_kg": _round_half_step(float(used_external)),
                    "last_total_load_kg": _round_half_step(float(used_total)),
                    "next_external_load_kg": next_external,
                    "next_total_load_kg": next_total,
                    "updated_at": date_value,
                }
            )

            if exercise_id in ("max_hang_5s", "max_hang_7s"):
                if feedback_label in {"hard", "very_hard"}:
                    max_hang_hard += 1
                    max_hang_easy = 0
                elif feedback_label in {"easy", "very_easy"}:
                    max_hang_easy += 1
                    max_hang_hard = 0
                else:
                    max_hang_hard = 0
                    max_hang_easy = 0

        elif fb_load_model == "external_load" and not fb_unilateral:
            # B288: `a or b` treated a legitimate 0kg as missing and dropped the
            # whole item — "I did it with no added weight" is a real answer
            # (band-only Pallof press, bodyweight variant of a loaded exercise),
            # and silently discarding it left the memory on the previous load.
            used_load = _first_not_none(
                item.get("used_external_load_kg"), item.get("used_load_kg")
            )
            if used_load is None:
                continue
            base = float(used_load)
            pct = _rule_midpoint_pct(updated, feedback_label)
            next_load = _round_half_step(base * (1.0 + pct))
            entry = _find_working_load_entry(updated, exercise_id, {})
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": exercise_id,
                    "setup": {},
                    "last_completed": bool(item.get("completed", False)),
                    "last_feedback_label": feedback_label,
                    "last_external_load_kg": _round_half_step(base),
                    "next_external_load_kg": next_load,
                    "updated_at": date_value,
                }
            )

        elif fb_load_model == "grade_relative" and _is_limit_grade_exercise(exercise_id):
            # B289 group A: whole climbing_limit_boulder family (was
            # limit_bouldering only). Surface-keyed memory, per-feedback steps.
            used_grade = normalize_font_grade(item.get("used_grade"))
            if not used_grade:
                continue
            options = list(planned_target.get("surface_options") or _surface_options(updated, session.get("gym_id")))
            surface_selected = _select_surface(
                preferred=item.get("surface_selected") or planned_target.get("surface_selected"),
                options=options,
                gym_id=session.get("gym_id"),
                user_state=updated,
            )
            next_grade = step_grade(used_grade, _grade_delta_for_feedback(feedback_label))
            setup, setup_key = _progression_setup_and_key(exercise_id, {"surface": surface_selected})
            entry = _find_working_load_entry(updated, exercise_id, setup)
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": setup_key,
                    "setup": setup,
                    "surface_selected": surface_selected,
                    "last_feedback_label": feedback_label,
                    "last_used_grade": used_grade,
                    "next_target_grade": next_grade,
                    "updated_at": date_value,
                }
            )

        elif fb_load_model == "grade_relative" and _grade_relative_group(exercise_id) == "endurance":
            # B289 group B (intervals/continuous): the grade is an intensity
            # target, not a max — one easy/hard session is noise. The target
            # steps ±1 whole grade only after 2 CONSECUTIVE CONCORDANT
            # feedbacks (easy/very_easy up, hard/very_hard down); "ok" resets
            # the streak and re-anchors the target to the grade actually used.
            # Memory keyed on exercise_id alone (no setup: the circuit grade
            # is gym-relative, but per-surface splits would fragment the
            # little signal endurance work produces).
            used_grade = normalize_font_grade(item.get("used_grade"))
            if not used_grade:
                continue
            if feedback_label in {"easy", "very_easy"}:
                direction = 1
            elif feedback_label in {"hard", "very_hard"}:
                direction = -1
            else:
                direction = 0
            entry = _find_working_load_entry(updated, exercise_id, {})
            prev_dir = int(entry.get("grade_streak_direction") or 0)
            prev_count = int(entry.get("grade_streak_count") or 0)
            if direction == 0:
                streak_dir, streak_count = 0, 0
                next_grade = used_grade
            else:
                streak_count = prev_count + 1 if direction == prev_dir else 1
                if streak_count >= 2:
                    next_grade = step_grade(used_grade, direction)
                    streak_dir, streak_count = 0, 0
                else:
                    next_grade = used_grade
                    streak_dir = direction
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": exercise_id,
                    "setup": {},
                    "last_feedback_label": feedback_label,
                    "last_used_grade": used_grade,
                    "next_target_grade": next_grade,
                    "grade_streak_direction": streak_dir,
                    "grade_streak_count": streak_count,
                    "updated_at": date_value,
                }
            )

        # B289 group C (technique_drill): used_grade is DELIBERATELY not
        # stored. On a drill the grade is the comfort terrain the drill runs
        # on, not a progression lever — progressing it would push users to
        # "harder drills" instead of better movement (decision Daniele,
        # 2026-07-21). No branch here is intentional, not an oversight.

        elif fb_load_model == "external_load" and fb_unilateral:
            # Unilateral: feedback includes hand field
            hand = str(item.get("hand") or "right").lower()
            # B288: same falsy-0 bug as the bilateral branch above.
            used_load = _first_not_none(
                item.get("used_external_load_kg"), item.get("used_load_kg")
            )
            if used_load is None:
                continue
            base = float(used_load)
            pct = _rule_midpoint_pct(updated, feedback_label)
            next_load = _round_half_step(base * (1.0 + pct))
            hand_key = f"{exercise_id}:{hand}"
            entries = _working_entries(updated)
            entry = None
            for e in entries:
                if str(e.get("key") or "") == hand_key:
                    entry = e
                    break
            if entry is None:
                entry = {"exercise_id": exercise_id, "key": hand_key, "hand": hand}
                entries.append(entry)
                entries.sort(key=lambda e: str(e.get("key") or ""))
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": hand_key,
                    "hand": hand,
                    "last_completed": bool(item.get("completed", False)),
                    "last_feedback_label": feedback_label,
                    "last_external_load_kg": _round_half_step(base),
                    "next_external_load_kg": next_load,
                    "updated_at": date_value,
                }
            )

    counters["max_hang_5s_hard_streak"] = max_hang_hard
    counters["max_hang_5s_easy_streak"] = max_hang_easy

    # Determine which test to enqueue based on finger device preference
    finger_device = ((updated.get("preferences") or {}).get("finger_training_device"))
    test_id_for_retest = "lp_max_test_5s" if finger_device == "loading_pin" else "max_hang_7s_total_load"

    if max_hang_hard >= 2:
        _enqueue_test(
            updated,
            test_id=test_id_for_retest,
            date_value=date_value,
            offset_days=7,
            reason="two_recent_hard_feedback_on_max_hang",
        )
    elif max_hang_easy >= 2:
        _enqueue_test(
            updated,
            test_id=test_id_for_retest,
            date_value=date_value,
            offset_days=14,
            reason="two_recent_easy_feedback_on_max_hang",
        )

    _update_test_from_log(log_entry, updated, bodyweight)
    return updated
