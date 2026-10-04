from __future__ import annotations

import logging
import math
import os
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from backend.engine.assessment_v1 import GRADE_ORDER as _LEAD_GRADE_ORDER
from backend.engine.assessment_v1 import _FINGER_BENCHMARK
from backend.engine import limit_log

FONT_GRADES: List[str] = [
    "5A", "5A+", "5B", "5B+", "5C", "5C+",
    "6A", "6A+", "6B", "6B+", "6C", "6C+",
    "7A", "7A+", "7B", "7B+", "7C", "7C+",
    "8A", "8A+", "8B", "8B+", "8C", "8C+",
]
FONT_GRADE_TO_INDEX = {grade: idx for idx, grade in enumerate(FONT_GRADES)}

# A291 (R6a): the French lead ladder in the engine's canonical UPPERCASE
# (contract B344 — the wire value is uppercase, `grade_scale` tells the client
# which casing to render). Same half-grade ladder as assessment_v1.GRADE_ORDER,
# which also covers 9A/9A+ (the Font list stops at 8C+).
FRENCH_GRADES: List[str] = [g.upper() for g in _LEAD_GRADE_ORDER]
FRENCH_GRADE_TO_INDEX = {grade: idx for idx, grade in enumerate(FRENCH_GRADES)}
_GRADE_SCALES: Dict[str, Tuple[List[str], Dict[str, int]]] = {
    "font": (FONT_GRADES, FONT_GRADE_TO_INDEX),
    "french": (FRENCH_GRADES, FRENCH_GRADE_TO_INDEX),
}

# Whole-grade scale for the LEGACY step_grade. Since A291 no engine path calls
# it any more (every prescription steps by half grades with step_grade_scaled);
# kept only for compatibility, pinned by test_grade_arithmetic.py.
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
    # C-LOADMODEL-MISTAG: forearm/wrist eccentrics are external_load (dumbbell
    # required) but light — without a fixed seed the 0.15×BW default (~10 kg)
    # is dangerously heavy for prehab.
    "elbow_wrist_extensor_eccentric": 1.5,
    "stick_pronation_supination_eccentric": 1.0,
    # B363: light isolation/prehab work that fell to 0.15×BW (~12 kg) on a
    # cold start — a rotator-cuff rotation or a wrist roller at 12 kg.
    "dumbbell_external_rotation": 1.5,
    "wrist_roller": 2.0,
    "heavy_reverse_wrist_curl": 4.0,
    "lateral_raise": 4.0,
    "dumbbell_fly": 6.0,
    "overhead_tricep_extension": 6.0,
    "weighted_hanging_leg_raise": 2.5,
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
    # B363: "squat" group removed — it prescribed a split squat at goblet/0.80
    # (61.5 kg → 77 kg on a per-leg movement). split_squat now cold-starts at
    # EXTERNAL_LOAD_FALLBACK_PCT_BW.
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
    # B363: aerobic finger protocols — midpoint of the catalog MVC range. They
    # used to fall to the 0.70 default, i.e. a max-strength load on a 35 s hang.
    "sub_max_capacity_hang": 0.45,        # 40-50% MVC
    "repeater_sub_max_endurance": 0.50,   # 45-55% MVC
    "intermittent_dead_hangs": 0.60,      # 55-65% MVC
    "long_interval_repeaters": 0.50,      # 45-55% MVC
}

# B363: total_load exercises that are NOT two-arm edge hangs and must never be
# loaded as a % of the two-arm finger max (they used to be: a weighted chin-up
# at +3 kg "3x7s", a one-arm hang at 85% of the TWO-arm max). weighted_chinup
# follows the pull-up 2RM reference; the others get a suggestion only from
# their own remembered load.
NOT_FINGER_MAX_TOTAL_LOAD: Tuple[str, ...] = (
    "weighted_chinup",
    "weighted_dip",
    "suitcase_carry",
    "pinch_block_training",
    "wide_pinch_extended_wrist_hold",
    "one_arm_hang_assisted",
)
SURFACE_PRIORITY = ("board_kilter", "board_moonboard", "board_other", "spraywall", "gym_boulder")

# B365 (R6.0) — limit-boulder grade memory per FAMILY + SURFACE.
# All values below are ENGINEERING CONSTANTS (design choices, no published
# source), documented in vocabulary §2.10.2:
# - a limit grade memory is trusted for 180 days (the global 60-day gate made
#   a Kilter grade from the summer vanish and the target jump back to the
#   outdoor RP anchor);
# - a gap of ≥14 days since the last limit session on a surface opens a
#   re-entry (same gap as the programme-wide re-entry ramp, DECISIONS
#   2026-10-04): the target is the pre-gap base minus one half grade for 2
#   sessions, then the base again (± the label delta applied to the BASE, so
#   the discount never becomes permanent);
# - boards (Kilter, Moon, spray, system) with no memory anchor 2 half grades
#   below the outdoor boulder RP — a Kilter 7A is not a gym 7A;
# - floor/ceiling: the target stays within ±2 half grades of the best grade
#   logged on that surface in the last 180 days; the band low is target − 2
#   half grades (one letter).
LIMIT_MEMORY_FRESHNESS_DAYS = 180
LIMIT_REENTRY_GAP_DAYS = 14
LIMIT_REENTRY_EXPOSURES = 2
LIMIT_REENTRY_HALF_STEPS = 1
LIMIT_BOARD_ANCHOR_HALF_STEPS = 2
LIMIT_SURFACE_BAND_HALF_STEPS = 2
LIMIT_TARGET_LOW_HALF_STEPS = 2
LIMIT_BOARD_SURFACES = frozenset({"board_kilter", "board_moonboard", "board_other", "spraywall"})
_LIMIT_REENTRY_FIELDS = (
    "reentry_base_grade",
    "reentry_exposures",
    "reentry_started_at",
    "reentry_last_at",
)
VALID_FEEDBACK = {"very_easy", "easy", "ok", "hard", "very_hard"}
LEGACY_DIFFICULTY_MAP = {
    "too_easy": "very_easy",
    "easy": "easy",
    "ok": "ok",
    "hard": "hard",
    "too_hard": "very_hard",
    "fail": "very_hard",
}

# B344: `ok` is NEUTRAL. It used to carry pct_range [0.00, 0.05], i.e. a
# +2.5% midpoint on every single session — and `ok` is not just the modal
# answer, it is the DEFAULT AT ZERO INPUT: feedback-dialog.tsx documents
# "Unrated exercises default to Ok" and buildDialogFeedbackItems ships
# `feedback_label ?? "ok"`. Closing a session without touching anything
# therefore signed a +2.5% on every load. With ~2 finger sessions/week that
# compounds to +5%/week, against a ~2%/week adaptation rate observed in the
# literature (Devise et al. 2022, 4-week RCT) — and finger tissue signals
# overload late. "Giusto così" must mean "same load next time".
#
# NOTE ON REACH: _rule_midpoint_pct prefers working_loads.rules.adjustment_policy
# over this default, so users who ever stored a policy keep the old behaviour.
# This is deliberate — a stored policy is an explicit user choice — but it means
# changing this constant does NOT retro-fix every account.
DEFAULT_ADJUSTMENT_POLICY = {
    "very_easy": {"pct_range": [0.10, 0.20]},
    "easy": {"pct_range": [0.05, 0.10]},
    "ok": {"pct_range": [0.00, 0.00]},
    "hard": {"pct_range": [-0.05, 0.00]},
    "very_hard": {"pct_range": [-0.15, -0.05]},
}

# B344: minimum quantization step for external load, in kg. Used as an additive
# floor so a positive feedback always moves the load — see _next_external_load.
MIN_EXTERNAL_LOAD_STEP_KG = 0.5


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


# ---------------------------------------------------------------------------
# B363 — test-anchored exercises and the rep-aware weighted pull-up.
#
# The pull-up max is MEASURED as a 2RM (D84) and stays a 2RM: it is the
# athlete's reference number. A 1RM is only ever an intermediate value used to
# apply PULLING_1RM_PCT, and is always derived from the 2RM — never stored as
# the reference.
#
# Before B363 the 2RM test logged its feedback under the training id
# 'weighted_pullup', and apply_feedback copied the test load into
# working_loads as the next TRAINING load: the athlete's 2RM (+45 kg) came
# back as a 4x3 prescription. max_hang_5s/7s had the same defect (100% test
# max returned as the ~90% training load).
# ---------------------------------------------------------------------------

# Exercises whose test protocol logs feedback under the training id. A test log
# for these must never become the next training load.
TEST_ANCHORED_EXERCISES: Tuple[str, ...] = ("weighted_pullup", "max_hang_5s", "max_hang_7s")

# Exercises that exist ONLY as tests (catalog category "test"): their load is
# always a fixed % of the current max, so they never keep a training memory —
# a remembered "hard → -2.5%" would under-load the next retest.
def _is_pure_test_exercise(exercise_id: str) -> bool:
    if exercise_id.startswith("test_"):
        return True
    return str(_load_catalog_cache().get(exercise_id, {}).get("category") or "") == "test"


# Feedback label → reps in reserve, used to read a training set as an
# estimate of the max. Coarse by design: the app has no RIR field.
# B364: UNTESTED athletes only — the B363 2RM re-base is kept for them bit for
# bit (DECISIONS: "untested users unchanged"). A tested athlete's feedback goes
# through anchored_load.apply_anchored_feedback and never re-bases anything.
PULLUP_RIR_BY_LABEL: Dict[str, int] = {
    "very_hard": 0,
    "hard": 1,
    "ok": 2,
    "easy": 3,
    "very_easy": 4,
}

# Default reps for a weighted pull-up set when neither the feedback item nor
# the planned instance carries them (catalog prescription_defaults.reps).
PULLUP_DEFAULT_REPS = 3


def estimate_1rm_from_reps(total_load_kg: float, reps: float) -> float:
    """Generalisation of estimate_1rm_from_2rm to N reps (Epley/Brzycki mean).

    ``estimate_1rm_from_reps(x, 2) == estimate_1rm_from_2rm(x)`` by construction.
    Reps are clamped to [1, 12]: Brzycki diverges near 37 and neither formula
    is meaningful for long sets.
    """
    r = max(1.0, min(12.0, float(reps)))
    if r <= 1.0:
        return round(float(total_load_kg), 1)
    epley = total_load_kg * (1 + r / 30)
    brzycki = total_load_kg * (36 / (37 - r))
    return round((epley + brzycki) / 2, 1)


def _two_rm_from_1rm(one_rm_total: float) -> float:
    """Inverse of estimate_1rm_from_2rm (for baselines that only carry a 1RM)."""
    factor = estimate_1rm_from_2rm(1000.0) / 1000.0
    return round(float(one_rm_total) / factor, 1)


def _pullup_baseline_2rm(user_state: Dict[str, Any]) -> Tuple[Optional[float], str]:
    """(2RM total kg, updated_at) from baselines.pulling, or (None, '')."""
    pulling = _get_pulling_baseline(user_state) or {}
    two_rm = pulling.get("weighted_pullup_2rm_total_kg")
    if not isinstance(two_rm, (int, float)) or two_rm <= 0:
        one_rm = pulling.get("weighted_pullup_1rm_total_kg") or pulling.get("weighted_pullup_1rm_estimated_kg")
        two_rm = _two_rm_from_1rm(float(one_rm)) if isinstance(one_rm, (int, float)) and one_rm > 0 else None
    return (float(two_rm) if two_rm else None), str(pulling.get("updated_at") or "")


def pullup_official_2rm(user_state: Dict[str, Any]) -> Tuple[Optional[float], str, str]:
    """(2RM total kg, date, source) of the persisted pulling baseline.

    B364: the official max changes ONLY with a test. Training logs never
    re-base it (the B363 ``e2rm_total_kg`` re-base is gone) and a remembered
    working load is never read as a max.
    """
    two_rm, base_date = _pullup_baseline_2rm(user_state)
    source = str((_get_pulling_baseline(user_state) or {}).get("source") or "")
    return two_rm, base_date, source


def pullup_reference_2rm(user_state: Dict[str, Any]) -> Optional[float]:
    """The pull-up reference of the pre-B364 path, as a 2RM total load (kg).

    Read ONLY where anchored_load does not apply — an untested athlete: no
    test, an onboarding self-report, or a test older than 90 days. There the
    B363 behaviour is kept bit for bit: the baseline 2RM, unless a training log
    written AFTER it re-based it (``e2rm_total_kg``, written only by
    ``_apply_weighted_pullup_feedback`` on the untested path). Without it the
    untested pull prescription could never progress (review B364).

    A tested athlete never reads this: the prescription comes from
    ``anchored_load`` and the official max (``pullup_official_2rm``) moves only
    with a test. The pre-B363 legacy-memory branch stays removed (decided
    2026-10-04): a remembered load is never read as a max.
    """
    base_2rm, base_date = _pullup_baseline_2rm(user_state)
    entry_2rm: Optional[float] = None
    entry_date = ""
    for e in _working_entries_ro(user_state):
        if str(e.get("exercise_id") or "") != "weighted_pullup":
            continue
        val = e.get("e2rm_total_kg")
        if isinstance(val, (int, float)) and val > 0 and str(e.get("updated_at") or "") >= entry_date:
            entry_2rm, entry_date = float(val), str(e.get("updated_at") or "")
    if entry_2rm is not None and (base_2rm is None or entry_date >= base_date):
        return entry_2rm
    return base_2rm


def weighted_pullup_target(
    user_state: Dict[str, Any], phase_id: Optional[str], intensity: str
) -> Optional[Dict[str, float]]:
    """Deterministic weighted pull-up training load from the 2RM reference.

    2RM → estimated 1RM → × PULLING_1RM_PCT[(phase, intensity)] → minus
    bodyweight. Returns {total, external, reference_2rm} or None when there is
    no reference at all.
    """
    ref_2rm = pullup_reference_2rm(user_state)
    if not ref_2rm:
        return None
    bodyweight = _get_bodyweight(user_state)
    pct = PULLING_1RM_PCT.get((phase_id or "", intensity), PULLING_1RM_PCT_DEFAULT)
    total = _round_half_step(estimate_1rm_from_2rm(ref_2rm) * pct)
    external = max(0.0, _round_half_step(total - bodyweight))
    return {"total": _round_half_step(bodyweight + external), "external": external, "reference_2rm": ref_2rm}


def _working_entries_ro(user_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Read-only view of working_loads.entries (never creates the key)."""
    entries = ((user_state.get("working_loads") or {}).get("entries")) or []
    return [e for e in entries if isinstance(e, dict)]


def _is_test_log(log_entry: Dict[str, Any]) -> bool:
    """True when the log comes from a test session (same gate as _update_test_from_log)."""
    if str(log_entry.get("session_id") or "").startswith("test_"):
        return True
    for s in log_entry.get("planned") or []:
        if str(s.get("session_id") or "").startswith("test_") or bool((s.get("tags") or {}).get("test")):
            return True
    return False


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


def _next_external_load(base: float, pct: float) -> float:
    """Next external load from the used load and a feedback percentage.

    B344: a pure multiplier makes 0.0 kg an ABSORBING STATE — `0 * (1 + pct)`
    is 0 for every label, `very_easy` included. Observed in production on
    `back_squat` (0.0 kg / very_easy / next 0.0 kg, frozen since 2026-07-30).
    The same trap bites the whole small-load regime where prehab lives: at
    1.0 kg even `easy` (+7.5%) rounds straight back to 1.0.

    So when the feedback asks for MORE load and the multiplier cannot deliver
    it, fall back to one quantization step. Deliberately asymmetric (only
    `pct > 0`, decision Daniele 2026-08-30): prehab loads are already minimal
    (elbow_eccentric_curl 1.5 kg, wrist_curl 3.0 kg) and nudging them further
    down buys nothing.

    B288 is preserved: 0.0 kg stays a legitimate *recorded* load. Only the
    NEXT load moves — `last_external_load_kg` is written by the caller and is
    untouched by this function.
    """
    scaled = _round_half_step(base * (1.0 + pct))
    if pct > 0 and scaled <= base:
        return _round_half_step(base + MIN_EXTERNAL_LOAD_STEP_KG)
    return scaled


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


def grade_scale_for_ref(grade_ref: str | None) -> str:
    """Which grade scale a `grade_ref` anchor is expressed in: french | font.

    B344 (display only); since A291 also the ladder `step_grade_scaled` steps
    on (french = assessment_v1.GRADE_ORDER, up to 9A+; font = FONT_GRADES).
    The letters are shared by Font and French — 6a/6b/6c/7a reads like
    6A/6B/6C/7A — and what B344 fixed is the CASING handed to the UI: a rope drill anchored to
    `lead_max_os` came out as "6C", and uppercase 6C reads as a Font BOULDER
    grade (~7a+ French), i.e. far harder than the 6c French actually meant.

    The engine keeps emitting its canonical uppercase value in
    `suggested_grade` — same convention as boulder grades staying Font
    internally — and ships this hint so the client can render the right scale.
    Render-only: nothing downstream branches on it.
    """
    return "french" if str(grade_ref or "").startswith("lead_") else "font"


def normalize_grade_on_scale(grade: str | None, scale: str) -> Optional[str]:
    """A291: canonical uppercase grade on `scale` (font | french), or None.

    Unknown scale names fall back to font. A grade that is not on the ladder
    (e.g. "9a" on the Font scale, "V5", "") is None — never a silent default.
    """
    if grade is None:
        return None
    ladder, index = _GRADE_SCALES.get(scale) or _GRADE_SCALES["font"]
    cleaned = str(grade).strip().upper().replace(" ", "")
    return cleaned if cleaned in index else None


def step_grade_half(grade: str | None, half_steps: int, scale: str) -> Optional[str]:
    """A291 (R6a): step `grade` by HALF grades on `scale`; the '+' survives.

    6c → +1 → 6C+, 7A+ → −1 → 7A. Clamped to the ends of the ladder
    (font 5A..8C+, french 5A..9A+). Unknown grade → None plus a warning:
    callers must not emit a prescription they cannot compute.
    """
    norm = normalize_grade_on_scale(grade, scale)
    if norm is None:
        logger.warning("step_grade_half: unknown grade %r on scale %r — no grade emitted", grade, scale)
        return None
    ladder, index = _GRADE_SCALES.get(scale) or _GRADE_SCALES["font"]
    idx = max(0, min(len(ladder) - 1, index[norm] + int(half_steps)))
    return ladder[idx]


def step_grade_scaled(grade: str | None, letter_offset: int, scale: str) -> Optional[str]:
    """A291 (R6a): apply a catalog `grade_offset` on the half-grade ladder.

    The catalog unit stays ONE LETTER (vocabulary §2.10.1): an offset of −1
    is 2 half grades, so 7a+ −1 → 6C+ (it used to strip the '+' first and
    give 6C — B-LEAD-HALF-GRADE-ROUNDING, closed). Output is canonical
    uppercase on `scale`; unknown grade → None (it used to become 6C).
    """
    return step_grade_half(grade, 2 * int(letter_offset), scale)


# A292 (R6-PE): derived grade_ref for the lead power-endurance work.
# The PE drills used to hang off `lead_max_os` alone, so a climber whose onsight
# lags the redpoint by more than a letter and a half (Daniele: OS 7a+ declared,
# RP 8a+) trained power endurance on terrain sized for a much weaker climber.
# The anchor is max(OS, RP − 3 half grades); the catalog `grade_offset` is then
# applied to it exactly as before. A climber whose OS is within 3 half grades
# of the RP gets the same anchor as before (the OS), bit for bit.
PE_ANCHOR_GRADE_REF = "lead_pe_anchor"
# Untested athletes keep the pre-A292 anchor (and report it under this ref).
PE_ANCHOR_UNTESTED_REF = "lead_max_os"
# ENGINEERING CONSTANT (no published source; DECISIONS 2026-10-04, R6-PE):
# 3 half grades below the redpoint is where the anchor stops following the OS.
PE_ANCHOR_RP_HALF_STEPS = -3


def pe_anchor_applies(user_state: Dict[str, Any], on: Any) -> bool:
    """A292 scope gate for the derived PE anchor (DECISIONS 2026-10-04, Global:
    anchor rules apply ONLY to athletes with a tested baseline). Same gate as
    A290's ``phase_anchor.is_tested_any``: a tested official max on the finger
    OR the pulling protocol on ``on``. No usable date → not tested."""
    from backend.engine import retest_policy as rp  # lazy: rp imports this module lazily too
    try:
        return bool(
            rp.is_tested(user_state, rp.PROTOCOL_HANG_7S, on)
            or rp.is_tested(user_state, rp.PROTOCOL_PULLUP_2RM, on)
        )
    except (TypeError, ValueError):
        return False


def lead_pe_anchor(grades: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """A292: the lead PE anchor and which grade produced it.

    Returns ``(grade, source)`` with ``grade`` canonical uppercase French and
    ``source`` ``"lead_max_os"`` or ``"lead_max_rp"``; ``(None, None)`` when
    neither grade is on the ladder. A tie goes to the OS (no behaviour change).
    """
    grades = grades or {}
    os_grade = normalize_grade_on_scale(grades.get("lead_max_os"), "french")
    rp_grade = normalize_grade_on_scale(grades.get("lead_max_rp"), "french")
    rp_floor = step_grade_half(rp_grade, PE_ANCHOR_RP_HALF_STEPS, "french") if rp_grade else None
    _, index = _GRADE_SCALES["french"]
    if os_grade and (rp_floor is None or index[os_grade] >= index[rp_floor]):
        return os_grade, "lead_max_os"
    if rp_floor:
        return rp_floor, "lead_max_rp"
    return None, None


def step_grade(grade: str, steps: int) -> str:
    """LEGACY whole-grade step (pre-A291 §2.10.1). No engine caller since A291.

    Input + modifiers are stripped (rounded to the base whole grade).
    Output is always a whole grade without +. Use step_grade_scaled.
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

    Returns dict: exercise_id → {"load_model", "unilateral", "pattern",
    "loading_pin"}. Used as fallback when exercise_instance doesn't carry
    load_model (e.g. in test fixtures or legacy resolved data).

    ``loading_pin`` (C-LOADMODEL-MISTAG) marks genuine finger loading-pin work
    (per-hand, independent L/R max) — the ONLY external_load exercises that must
    route through ``_loading_pin_suggested``. Previously the per-hand path was
    gated on ``unilateral`` alone, which mis-routed unilateral LEG accessories
    (split_squat, and post-brief bulgarian/cossack) into the finger baseline.
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
                # B345: additive — session_tags.derive_session_tags needs these
                # to work out a user-authored session's real intensity and
                # whether it loads the fingers. Kept on this cache rather than
                # parsing exercises.json a second time.
                "intensity_level": e.get("intensity_level"),
                "domain": e.get("domain") or [],
                # A281: the taper scales training sets only — `role` is what
                # separates warmup/cooldown/prehab/test from the work itself.
                "role": e.get("role") or [],
                # B363: category "test" marks test-only exercises (no memory).
                "category": e.get("category"),
                # A291: apply_feedback reads grade_ref from here when the
                # feedback has no planned instance (custom sessions) — before,
                # the key was absent and the fallback silently read {}.
                "prescription_defaults": dict(e.get("prescription_defaults") or {}),
                # A295: pain zones (stress_tags / contraindications) and the
                # double-progression fatigue weight.
                "stress_tags": dict(e.get("stress_tags") or {}),
                "contraindications": list(e.get("contraindications") or []),
                "loading_pin": "loading_pin" in (
                    (e.get("equipment_required") or []) + (e.get("equipment_required_any") or [])
                ),
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


def _step_font_half(grade: str | None, half_steps: int) -> Optional[str]:
    """B365: step a Font grade by HALF grades on FONT_GRADES ('+' survives).

    The limit family is always Font. Same arithmetic as A291's
    `step_grade_half(..., "font")` but silent: the limit callers already fall
    back with `or`. Unknown grade → None. Clamped to the ends of the scale.
    """
    norm = normalize_font_grade(grade)
    if norm is None:
        return None
    idx = FONT_GRADE_TO_INDEX[norm] + int(half_steps)
    idx = max(0, min(len(FONT_GRADES) - 1, idx))
    return FONT_GRADES[idx]


def _clamp_font(grade: str, low: str, high: str) -> str:
    gi, lo, hi = FONT_GRADE_TO_INDEX[grade], FONT_GRADE_TO_INDEX[low], FONT_GRADE_TO_INDEX[high]
    return FONT_GRADES[max(lo, min(hi, gi))]


def _days_between(earlier: str | None, later: str | None) -> Optional[int]:
    a, b = _parse_day(earlier), _parse_day(later)
    if a is None or b is None:
        return None
    return (b - a).days


def _limit_family_entries(user_state: Dict[str, Any], surface: str) -> List[Dict[str, Any]]:
    """Every limit-family working_loads entry on `surface`, newest first.

    Read-only (no setdefault). The family is climbing_limit_boulder:
    limit_bouldering, board_limit_boulders, spray_wall_limit,
    system_board_limit — a grade sent on the Kilter is the same signal
    whichever of those exercises the session happened to pick.
    """
    entries = (user_state.get("working_loads") or {}).get("entries") or []
    out: List[Dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        if not _is_limit_grade_exercise(str(item.get("exercise_id") or "")):
            continue
        item_surface = str(((item.get("setup") or {}).get("surface")) or item.get("surface_selected") or "").strip().lower()
        if item_surface != surface:
            continue
        if _parse_day(item.get("updated_at")) is None:
            continue
        out.append(item)
    out.sort(key=lambda e: (str(e.get("updated_at") or ""), str(e.get("key") or "")), reverse=True)
    return out


def _limit_family_entry(user_state: Dict[str, Any], surface: str, date_value: str) -> Optional[Dict[str, Any]]:
    """B365: the newest family entry on `surface` dated on/before `date_value`."""
    for item in _limit_family_entries(user_state, surface):
        delta = _days_between(item.get("updated_at"), date_value)
        if delta is not None and delta >= 0:
            return item
    return None


def _limit_anchor_target(
    user_state: Dict[str, Any],
    prescription: Dict[str, Any],
    surface: str,
    benchmark_grade: str,
) -> str:
    """Target with no usable memory: catalog grade_ref (boulder_max_rp) + offset.

    B260: anchored to the outdoor RP, the Kilter benchmark only as fallback.
    B365: on a board the RP anchor drops 2 half grades. Not applied to the
    benchmark fallback, which is already a board grade.
    """
    grades = ((user_state.get("assessment") or {}).get("grades") or {})
    anchor_ref = prescription.get("grade_ref") or "boulder_max_rp"
    offset = int(prescription.get("grade_offset") or 0)
    # A291: half-grade ladder, the '+' of the anchor survives (7B+ + 0 → 7B+,
    # it used to become 7B). An anchor that is not a Font grade falls back to
    # the benchmark instead of the old silent 6C.
    target = step_grade_scaled(grades.get(anchor_ref), offset, "font") if grades.get(anchor_ref) is not None else None
    from_assessment = target is not None
    if target is None:
        target = step_grade_scaled(benchmark_grade, offset, "font") or benchmark_grade
    if from_assessment and surface in LIMIT_BOARD_SURFACES:
        target = _step_font_half(target, -LIMIT_BOARD_ANCHOR_HALF_STEPS) or target
    return target


def _limit_surface_band(
    user_state: Dict[str, Any],
    surface: str,
    date_value: str,
    latest: Optional[Dict[str, Any]],
) -> Optional[Tuple[str, str]]:
    """B365: (floor, ceiling) for the limit target on `surface`, or None.

    Built from the best grade the athlete actually CLIMBED on the surface in
    the trusted window (`last_used_grade` only — a `next_target_grade` is a
    target not yet sent, review finding). ±2 half grades around it.

    The floor softens after a bad session: when the newest entry was
    hard/very_hard at grade X, the floor is at most X − 1 half grade. One bad
    session is absorbed, a run of them walks the target down half a grade per
    failure instead of pinning it for 180 days.
    """
    best_idx: Optional[int] = None
    for item in _limit_family_entries(user_state, surface):
        age = _days_between(item.get("updated_at"), date_value)
        if age is None or age < 0 or age > LIMIT_MEMORY_FRESHNESS_DAYS:
            continue
        g = normalize_font_grade(item.get("last_used_grade"))
        if g is not None:
            idx = FONT_GRADE_TO_INDEX[g]
            best_idx = idx if best_idx is None else max(best_idx, idx)
    if best_idx is None:
        return None
    best = FONT_GRADES[best_idx]
    floor = _step_font_half(best, -LIMIT_SURFACE_BAND_HALF_STEPS) or best
    ceiling = _step_font_half(best, LIMIT_SURFACE_BAND_HALF_STEPS) or best
    if latest is not None and str(latest.get("last_feedback_label") or "") in ("hard", "very_hard"):
        failed = normalize_font_grade(latest.get("last_used_grade"))
        if failed is not None:
            below_failed = _step_font_half(failed, -1) or failed
            if FONT_GRADE_TO_INDEX[below_failed] < FONT_GRADE_TO_INDEX[floor]:
                floor = below_failed
    return floor, ceiling


def _limit_target_state(
    user_state: Dict[str, Any],
    prescription: Dict[str, Any],
    surface: str,
    date_value: str,
    benchmark_grade: str,
) -> Dict[str, Any]:
    """B365 (R6.0): the limit target for `surface` on `date_value`.

    Shared by inject_targets (read), apply_feedback (write) and the read-only
    consumers (coach prompt, weekly report — via `limit_next_target`) so all
    of them agree on whether a re-entry is open, on its base and on the
    prescribed grade. Returns:
      target, target_low, source (anchor|memory|reentry),
      reentry: None | {base_grade, exposures_done, exposures_required, started_at}
    Re-entry opens only when the athlete HAS climbed limit on this surface
    before (any age) and the newest entry is ≥14 days old; a first-ever
    session is the plain anchor. A new gap ≥14 days restarts an open
    re-entry from zero. An entry older than 180 days is not trusted as a
    grade: the re-entry base is then min(anchor, that stale grade), so a
    longer absence never gives a harder target than a shorter one.

    Order: the per-surface floor/ceiling clamps the BASE (memory or re-entry
    base), then the re-entry discount is applied — the floor can never cancel
    the discount or lift a re-entry above its base.
    """
    anchor = _limit_anchor_target(user_state, prescription, surface, benchmark_grade)
    latest = _limit_family_entry(user_state, surface, date_value)
    band = _limit_surface_band(user_state, surface, date_value, latest)

    def _clamped(grade: str) -> str:
        norm = normalize_font_grade(grade) or grade
        if band is None or normalize_font_grade(norm) is None:
            return norm
        return _clamp_font(norm, band[0], band[1])

    reentry: Optional[Dict[str, Any]] = None
    source = "anchor"
    target = anchor

    if latest is not None:
        age = _days_between(latest.get("updated_at"), date_value) or 0
        trusted = age <= LIMIT_MEMORY_FRESHNESS_DAYS
        remembered = normalize_font_grade(latest.get("next_target_grade")) if trusted else None
        open_base = normalize_font_grade(latest.get("reentry_base_grade")) if trusted else None
        open_done = int(latest.get("reentry_exposures") or 0)
        if age >= LIMIT_REENTRY_GAP_DAYS:
            # A gap (new or during an open re-entry) restarts the ramp.
            if remembered:
                base = remembered
            else:
                stale = normalize_font_grade(latest.get("next_target_grade"))
                base = anchor
                if stale is not None and normalize_font_grade(anchor) is not None and FONT_GRADE_TO_INDEX[stale] < FONT_GRADE_TO_INDEX[normalize_font_grade(anchor)]:
                    base = stale
            reentry = {"base_grade": _clamped(base), "exposures_done": 0, "started_at": None}
        elif open_base and open_done < LIMIT_REENTRY_EXPOSURES:
            reentry = {
                "base_grade": _clamped(open_base),
                "exposures_done": open_done,
                "started_at": latest.get("reentry_started_at"),
            }
        elif remembered:
            target = _clamped(remembered)
            source = "memory"

    if reentry is not None:
        reentry["exposures_required"] = LIMIT_REENTRY_EXPOSURES
        target = _step_font_half(reentry["base_grade"], -LIMIT_REENTRY_HALF_STEPS) or reentry["base_grade"]
        source = "reentry"
    elif source == "anchor":
        target = _clamped(target)

    # B365: the band low is computed from the FINAL target. It used to be
    # derived from the anchor before the memory override, so a 7A memory
    # under a 7C anchor gave low 7B > target 7A.
    target_low = _step_font_half(target, -LIMIT_TARGET_LOW_HALF_STEPS) or target
    return {
        "target": target,
        "target_low": target_low,
        "source": source,
        "reentry": reentry,
    }


def limit_next_target(
    user_state: Dict[str, Any],
    entry: Dict[str, Any],
    date_value: str,
) -> Optional[str]:
    """B365: the limit grade the app would prescribe for `entry`'s surface.

    For read-only consumers (coach prompt, weekly report) that used to quote
    `next_target_grade` raw: during a re-entry, or when the floor/ceiling
    clamps, the stored value is the BASE, not the prescribed target. Uses the
    catalog default anchor (boulder_max_rp + 0). None when `entry` is not a
    limit-family entry with a surface.
    """
    if not _is_limit_grade_exercise(str(entry.get("exercise_id") or "")):
        return None
    surface = str(((entry.get("setup") or {}).get("surface")) or entry.get("surface_selected") or "").strip().lower()
    if not surface or _parse_day(date_value) is None:
        return None
    state = _limit_target_state(user_state, {}, surface, date_value, _extract_grade_benchmark(user_state))
    return state["target"]


def limit_target_on_surface(user_state: Dict[str, Any], surface: str, date_value: str) -> Optional[str]:
    """A296: the limit target on an explicit ``surface`` (free sessions).

    Catalog-default anchor (boulder_max_rp + 0), same function as the plan.
    None when the surface is not a limit surface or the date is invalid.
    """
    surf = str(surface or "").strip().lower()
    if surf not in SURFACE_PRIORITY or _parse_day(date_value) is None:
        return None
    return _limit_target_state(user_state, {}, surf, date_value, _extract_grade_benchmark(user_state))["target"]


def limit_grade_target(
    user_state: Dict[str, Any],
    exercise_id: str,
    date_value: str,
    *,
    gym_id: str | None = None,
    prescription: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """A296: the limit target of a limit-family exercise outside the planner.

    For custom sessions (read with ``?date=``), the custom builder proposal and
    the coach/adhoc previews — the same `_limit_target_state` the planned
    session reads, so a limit done in a custom session gets the plan's target
    and its outcome counts. Read-only. Surface: the gym's surfaces when
    ``gym_id`` is known, else the union of the athlete's gyms (first by
    SURFACE_PRIORITY). None when ``exercise_id`` is not in the limit family or
    the date is not a date.
    """
    if not _is_limit_grade_exercise(str(exercise_id or "")) or _parse_day(date_value) is None:
        return None
    options = _surface_options(user_state, gym_id) if gym_id else []
    if not options:
        equip: set = set()
        for gym in ((user_state.get("equipment") or {}).get("gyms") or []):
            equip.update(str(x).strip().lower() for x in ((gym or {}).get("equipment") or []) if str(x).strip())
        options = [surface for surface in SURFACE_PRIORITY if surface in equip]
    surface = _select_surface(preferred=None, options=options, gym_id=gym_id, user_state=user_state)
    presc = prescription
    if presc is None:
        presc = (_load_catalog_cache().get(exercise_id, {}) or {}).get("prescription_defaults") or {}
    state = _limit_target_state(user_state, presc, surface, date_value, _extract_grade_benchmark(user_state))
    out: Dict[str, Any] = {
        "schema_version": "boulder_grade_font_v0",
        "surface_options": options,
        "surface_selected": surface,
        "target_grade": state["target"],
        "target_grade_low": state["target_low"],
        "target_source": state["source"],
        "log_problems": True,
    }
    if state["reentry"]:
        out["reentry"] = dict(state["reentry"])
    return out


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
    from backend.engine.anchored_load import ANCHORED_EXERCISES, anchored_load, anchored_suggested_fields

    out = deepcopy(resolved_day)
    # B364: the official max and the tested gate are read on the PERSISTED
    # state — estimate_missing_baselines stamps source='test' with today's date
    # on estimated baselines, which would make an untested user look tested.
    persisted_state = user_state
    user_state = deepcopy(user_state)  # Work on a local copy — don't mutate caller state
    estimate_missing_baselines(user_state)  # Fill missing hangboard + pulling baselines
    out["targets_schema_version"] = "progression_targets.v1"
    benchmark_grade = _extract_grade_benchmark(user_state)
    catalog_lm = _load_catalog_load_models()  # ARCH-2: fallback for instances without load_model

    from backend.engine import measured_feedback as mf
    from backend.engine import retest_policy as _rp

    # A295: the official 7 s hang max on this date (pain cap of finger hangs).
    _om7 = _rp.official_max(persisted_state, _rp.PROTOCOL_HANG_7S, out.get("date") or "9999-12-31") if out.get("date") else None
    official_hang_7s = float(_om7["total_kg"]) if _om7 and _om7.get("tested") and _om7.get("total_kg") else None

    for session in out.get("sessions") or []:
        intensity = _intensity_label(session)
        boulder_info = _boulder_target_info(session, user_state)
        session_is_test = str(session.get("session_id") or "").startswith("test_") or bool(
            (session.get("tags") or {}).get("test")
        )
        session_ex_ids = [str(i.get("exercise_id") or "") for i in session.get("exercise_instances") or []]
        for inst in session.get("exercise_instances") or []:
            ex_id = str(inst.get("exercise_id") or "")
            prescription = inst.get("prescription") or {}
            suggested: Dict[str, Any] = dict(inst.get("suggested") or {})

            # B364: the four anchored exercises of a TESTED athlete get their
            # load from the single anchored_load (official max + working load,
            # caps, re-entry ramp, guards). None → the pre-B364 branches below,
            # bit for bit (untested athletes).
            anch: Optional[Dict[str, Any]] = None
            if ex_id in ANCHORED_EXERCISES:
                anchor_source = dict(prescription)
                anchor_source.update(inst.get("suggested") or {})
                anch_setup, _ = _progression_setup_and_key(ex_id, anchor_source)
                attrs = inst.get("attributes") or {}
                anch = anchored_load(
                    persisted_state,
                    ex_id,
                    date=out.get("date") or "",
                    intensity=intensity,
                    sets=prescription.get("sets") or (prescription.get("sets_range") or [None])[0],
                    reps=prescription.get("reps") or (prescription.get("reps_range") or [None])[0],
                    work_seconds=prescription.get("work_seconds") or prescription.get("hang_seconds"),
                    session_exercise_ids=session_ex_ids,
                    setup=anch_setup,
                    catalog_intensity=prescription.get("intensity_pct_of_total_load") or attrs.get("intensity_pct"),
                )
            if anch is not None:
                suggested.update(anchored_suggested_fields(anch))

            load_model = inst.get("load_model") or catalog_lm.get(ex_id)
            # C-LOADMODEL-MISTAG: per-hand load routing keys on genuine finger
            # loading-pin equipment, NOT raw unilaterality (leg accessories are
            # unilateral but load a single dumbbell, not independent L/R maxes).
            is_loading_pin = _load_catalog_cache().get(ex_id, {}).get("loading_pin", False)

            # --- total_load: special-case exercises with unique logic ---
            if anch is not None:
                pass
            elif ex_id in ("max_hang_5s", "max_hang_7s"):
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
                # B363: weighted_pullup is ALWAYS a % of the 2RM reference
                # (tested 2RM, or a later training re-base), never a raw
                # remembered load — the remembered load may come from a set
                # with a different rep count, or from the 2RM test itself.
                # Falls back to a legacy working load only with no reference.
                bodyweight = _get_bodyweight(user_state)
                next_external: float = 0.0
                load_source: Optional[str] = None
                phase_id = _get_current_phase_id(user_state, out.get("date") or "")
                target = weighted_pullup_target(user_state, phase_id, intensity)
                if target is not None:
                    next_external = target["external"]
                    load_source = "pullup_2rm_reference"
                    suggested["reference_2rm_total_kg"] = target["reference_2rm"]
                else:
                    entry = _best_entry(user_state, ex_id, {}, out.get("date") or "")
                    if entry and entry.get("next_external_load_kg") is not None:
                        next_external = float(entry["next_external_load_kg"])

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
                # B365 (R6.0): memory read across the whole family on the
                # selected surface (180-day trust), re-entry after a ≥14-day
                # gap, board anchor, per-surface floor/ceiling, band low from
                # the final target — see _limit_target_state.
                limit_state = _limit_target_state(
                    user_state,
                    prescription,
                    selected_surface,
                    out.get("date") or "",
                    benchmark_grade,
                )
                boulder_target: Dict[str, Any] = {
                    "schema_version": "boulder_grade_font_v0",
                    "surface_options": options,
                    "surface_selected": selected_surface,
                    "target_grade": limit_state["target"],
                    "target_grade_low": limit_state["target_low"],
                    "target_source": limit_state["source"],
                    "intensity_label": intensity,
                }
                if limit_state["reentry"]:
                    boulder_target["reentry"] = dict(limit_state["reentry"])
                # A296: the players log this exercise problem by problem.
                boulder_target["log_problems"] = True
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
                anchor_from: Optional[str] = None
                if grade_ref == PE_ANCHOR_GRADE_REF and pe_anchor_applies(user_state, out.get("date")):
                    # A292 (R6-PE): derived anchor max(OS, RP − 3 half grades),
                    # tested athletes only (DECISIONS, Global).
                    ref_grade_raw, anchor_from = lead_pe_anchor(grades)
                elif grade_ref == PE_ANCHOR_GRADE_REF:
                    # Untested athlete: exactly the pre-A292 output — the
                    # onsight anchor, reported as lead_max_os.
                    grade_ref = PE_ANCHOR_UNTESTED_REF
                    ref_grade_raw = grades.get(grade_ref)
                else:
                    ref_grade_raw = grades.get(grade_ref)
                ref_scale = grade_scale_for_ref(grade_ref)
                if ref_grade_raw is not None:
                    # A291 (R6a): half-grade ladder of the anchor's own scale
                    # (french for lead_*, font for boulder_*); the '+' of the
                    # reference survives, output canonical uppercase (B344).
                    # Unknown reference grade → no suggested_grade at all
                    # (it used to come out as a silent 6C-relative value).
                    grade_offset = int(prescription.get("grade_offset") or 0)
                    suggested_grade = step_grade_scaled(ref_grade_raw, grade_offset, ref_scale)
                    if suggested_grade is not None:
                        suggested["suggested_grade"] = suggested_grade
                        suggested["grade_ref"] = grade_ref
                        suggested["grade_offset"] = grade_offset
                        suggested["grade_scale"] = ref_scale
                        if anchor_from:
                            suggested["grade_anchor_from"] = anchor_from
                # B289 group B: a remembered endurance target (written by
                # apply_feedback after 2 concordant feedbacks) overrides the
                # static assessment anchor. 60-day freshness gate as for every
                # grade entry.
                if _grade_relative_group(ex_id) == "endurance":
                    mem_entry = _best_entry(user_state, ex_id, {}, out.get("date") or "")
                    remembered = normalize_grade_on_scale((mem_entry or {}).get("next_target_grade"), ref_scale)
                    if mem_entry and remembered:
                        suggested["suggested_grade"] = remembered
                        suggested["grade_ref"] = grade_ref
                        suggested["grade_source"] = "working_loads"
                        suggested["grade_scale"] = grade_scale_for_ref(grade_ref)
                        # The remembered grade is not the anchor's any more.
                        suggested.pop("grade_anchor_from", None)

            # External load exercises — data-driven from load_model (ARCH-2)
            if load_model == "external_load" and not is_loading_pin:
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
            if load_model == "total_load" and ex_id == "weighted_chinup" and anch is None:
                # B363: chin-up follows the pull-up 2RM reference.
                target = weighted_pullup_target(
                    user_state, _get_current_phase_id(user_state, out.get("date") or ""), intensity,
                )
                if target is not None:
                    reps = prescription.get("reps") or (prescription.get("reps_range") or [5])[0]
                    sets = prescription.get("sets") or (prescription.get("sets_range") or [4])[0]
                    suggested.update({
                        "schema_version": "progression_targets.v1",
                        "suggested_external_load_kg": target["external"],
                        "suggested_total_load_kg": target["total"],
                        "suggested_rep_scheme": f"{sets}x{reps}",
                        "load_source": "pullup_2rm_reference",
                    })
            if load_model == "total_load" and anch is None and ex_id not in ("max_hang_5s", "max_hang_7s", "weighted_pullup") and not (
                ex_id == "weighted_chinup" and suggested.get("load_source") == "pullup_2rm_reference"
            ):
                if ex_id not in NOT_FINGER_MAX_TOTAL_LOAD:
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
                    if _hang_recently_tested(persisted_state, out.get("date") or ""):
                        # B364 (R3 §8): a max tested < 30 days ago is not stale —
                        # an assisted hang is just assisted, not a re-test cue.
                        suggested["load_assist_kg"] = -float(suggested["suggested_external_load_kg"])
                    else:
                        suggested["load_warning"] = (
                            "counterweight_required — consider re-running max_hang_7s test"
                        )

            # Loading pin exercises (unilateral, external_load) — data-driven (ARCH-2)
            if load_model == "external_load" and is_loading_pin:
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

            # A295 (R4): which measure the client may ask for, the double-
            # progression target, and the read-side pain block (anchored
            # exercises already carry theirs from anchored_load).
            kind = mf.measure_kind(ex_id, is_test=session_is_test)
            if kind:
                suggested["measure"] = kind
                if kind == mf.MEASURE_DP_REPS:
                    lo = mf.prescribed_reps_of(ex_id, prescription)
                    if lo:
                        dp_entry = _best_entry(
                            user_state, ex_id, {}, out.get("date") or "",
                            freshness_days=EXTERNAL_LOAD_FRESHNESS_DAYS,
                        )
                        target = mf.dp_target_for(dp_entry, lo)
                        suggested["target_reps"] = target
                        suggested["dp_range"] = list(mf.dp_range(lo))
                        if target != lo:
                            dp_sets = prescription.get("sets") or (prescription.get("sets_range") or [3])[0]
                            suggested["suggested_rep_scheme"] = f"{dp_sets}x{target}"
            if anch is not None and anch.get("pain"):
                suggested["pain_flag"] = True
                suggested["pain"] = dict(anch["pain"])
            elif anch is None or session_is_test:
                # A295 review: a test session gets the flag (a test is a max:
                # never a cut load, but "pain reported" must show) — the retest
                # policy also blocks a test of the zone (blocked:pain).
                mf.pain_adjust_suggested(
                    suggested, persisted_state, ex_id, out.get("date") or "",
                    load_model=load_model, bodyweight=_get_bodyweight(user_state),
                    official_hang_total=official_hang_7s, flag_only=session_is_test,
                )

            if suggested:
                inst["suggested"] = suggested

    return out


def _hang_recently_tested(user_state: Dict[str, Any], date_value: str) -> bool:
    """A tested 7 s hang max younger than TESTED_NO_WARNING_D days on ``date_value``."""
    from backend.engine.anchored_load import TESTED_NO_WARNING_D, official_for, _parse

    on = _parse(date_value)
    if on is None:
        return False
    om = official_for(user_state, "max_hang_7s", on)
    return bool(om and om.get("tested") and (om.get("age_days") or 0) < TESTED_NO_WARNING_D)


def _rule_midpoint_pct(user_state: Dict[str, Any], label: str) -> float:
    rules = (((user_state.get("working_loads") or {}).get("rules") or {}).get("adjustment_policy") or {})
    policy = rules.get(label) or DEFAULT_ADJUSTMENT_POLICY.get(label) or {}
    pct_range = policy.get("pct_range") or [0.0, 0.0]
    if len(pct_range) != 2:
        return 0.0
    return float(pct_range[0] + pct_range[1]) / 2.0


def _grade_delta_for_feedback(label: str) -> int:
    """Limit-family step per feedback label, in HALF grades (A291).

    very_easy +2, easy +1, ok 0, hard −1, very_hard −2 half grades. Before
    A291 the same numbers were whole letters (easy on 7A → 7B), a full grade
    per session on a max-intensity target.
    """
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


def _prune_test_queue(user_state: Dict[str, Any]) -> None:
    """Drop queued retests that have since been performed.

    B346. Until now nothing ever removed an entry, which was harmless only
    because nothing ever read the queue either. Now that ``planner_v2`` PASS 3
    consumes it, an entry left behind would re-place the same test every single
    week. An entry is satisfied when a test with the same ``test_id`` was
    recorded on or after the day the entry was created.

    Note this is a second line of defence, not the only one: PASS 3 still
    applies the 42-day freshness gate, so a just-completed test would not be
    re-placed even if the entry survived. Both exist because the failure modes
    differ — freshness protects the plan, pruning stops the queue growing
    without bound.
    """
    queue = user_state.get("test_queue")
    if not isinstance(queue, list) or not queue:
        return

    latest_by_test: Dict[str, str] = {}
    for entries in (user_state.get("tests") or {}).values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            test_id = str(entry.get("test_id") or "")
            date_str = str(entry.get("date") or "")
            if not test_id or not date_str:
                continue
            if date_str > latest_by_test.get(test_id, ""):
                latest_by_test[test_id] = date_str

    def _satisfied(item: Dict[str, Any]) -> bool:
        test_id = str(item.get("test_id") or "")
        created = str(item.get("created_at") or "")
        done_on = latest_by_test.get(test_id)
        return bool(done_on) and bool(created) and done_on >= created

    user_state["test_queue"] = [item for item in queue if not _satisfied(item)]


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
    measurements_only = False
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
        # B364 (B156 fix): a test_* item added to a TRAINING session makes only
        # the test_* items measurements. A training max_hang_7s / weighted
        # pull-up logged in the same session is a working set — it must never
        # write the official max.
        measurements_only = not top_session_id.startswith("test_")
    date_str = str(log_entry.get("date") or "")
    assessment = updated.setdefault("assessment", {})
    at = assessment.setdefault("tests", {})
    # D214: tests_source sidecar — every scalar written below is a measured result
    at_src = assessment.setdefault("tests_source", {})

    def _mark_measured(*keys: str) -> None:
        for k in keys:
            at_src[k] = "measured"

    from backend.engine.retest_policy import test_confidence

    def _trend(history: List[Dict[str, Any]], test_id: str, value_key: str, value: float) -> Dict[str, Any]:
        """B364: delta vs the previous test of the same protocol; |Δ| < 5 % = stable."""
        prev = [h for h in history if h.get("test_id") == test_id and str(h.get("date") or "") < date_str
                and isinstance(h.get(value_key), (int, float))]
        if not prev:
            return {}
        prev.sort(key=lambda h: str(h.get("date") or ""))
        before = float(prev[-1][value_key])
        if before <= 0:
            return {}
        delta = round((value - before) / before * 100, 1)
        trend = "stable" if abs(delta) < 5.0 else ("up" if delta > 0 else "down")
        return {"delta_pct": delta, "trend": trend, "previous_date": prev[-1].get("date")}

    def _confidence(test_id: str) -> Dict[str, Any]:
        """B364: computed confidence (exposures in the 21 days before the test),
        never a constant. Engine-side it sees the hot weeks + the registry;
        the migration recomputes it with the archived weeks."""
        conf = test_confidence(updated, {"test_id": test_id, "date": date_str})
        if conf.get("confidence") is None:
            return {"confidence": "high"}
        return {
            "confidence": conf["confidence"],
            "confidence_basis": {"exposures": conf["exposures"], "window_start": conf["window_start"],
                                 "window_end": conf["window_end"], "min_required": conf["min_required"]},
        }

    for item in feedback_items:
        exercise_id = str(item.get("exercise_id") or "")
        if measurements_only and not exercise_id.startswith("test_") and not _is_pure_test_exercise(exercise_id):
            continue

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
                **_confidence("max_hang_7s_total_load"),
                **_trend(max_strength, "max_hang_7s_total_load", "total_load_kg", total),
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
                baselines[0]["bodyweight_at_test_kg"] = bodyweight
                baselines[0]["confidence"] = entry["confidence"]
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
                **_confidence("max_hang_5s_total_load"),
                **_trend(max_strength, "max_hang_5s_total_load", "total_load_kg", total),
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
                baselines[0]["bodyweight_at_test_kg"] = bodyweight
                baselines[0]["confidence"] = entry["confidence"]
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
            pull_conf = _confidence("weighted_pullup_2rm")
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
                **pull_conf,
                **_trend(pull_history, "weighted_pullup_2rm", "total_load_2rm_kg", total_2rm),
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
                "confidence": pull_conf["confidence"],
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


def _apply_weighted_pullup_feedback(
    updated: Dict[str, Any],
    item: Dict[str, Any],
    planned_prescription: Dict[str, Any],
    feedback_label: str,
    date_value: str,
    bodyweight: float,
    *,
    rating: Optional[str] = "",
    rated: Optional[bool] = None,
) -> None:
    """Weighted pull-up feedback of an UNTESTED athlete (pre-B364, bit for bit).

    B364: a tested athlete never reaches this — apply_anchored_feedback handles
    it and the official max moves only with a test. An untested athlete has no
    official max: the B363 2RM re-base below is their only progression, so it
    is kept unchanged (DECISIONS 2026-10-04, "untested users unchanged").

    The set is read as an estimate of the max: load × (reps done + reps in
    reserve, from the feedback label) → estimated 1RM → 2RM equivalent.
      * not hard: the reference only goes UP (max(reference, estimate));
      * hard / very_hard: the reference goes DOWN by the adjustment policy %.
    The stored ``next_*`` fields are a convenience for legacy readers; the
    prescription itself is always recomputed by weighted_pullup_target().

    A295 review: ``last_set_reps`` (AMRAP on the last set, stopping one short
    of failure) is the measure the client shows for this exercise: when given
    it replaces the label's reps-in-reserve guess (load × (reps + 1)). The
    stored label is the RATING (``None`` = not rated, never a fake 'ok'), and
    an active pain block on the zone never lets the reference go up.
    """
    from backend.engine import measured_feedback as mf

    if rating == "":
        rating = feedback_label  # legacy call shape (tests, old callers)
    used_total = item.get("used_total_load_kg")
    used_external = item.get("used_external_load_kg")
    if used_total is None and used_external is not None:
        used_total = float(used_external) + bodyweight
    if used_external is None and used_total is not None:
        used_external = float(used_total) - bodyweight
    if used_total is None:
        return

    reps = _first_not_none(
        item.get("reps"), item.get("prescribed_reps"), planned_prescription.get("reps"),
    )
    try:
        reps_f = float(reps) if reps is not None else float(PULLUP_DEFAULT_REPS)
    except (TypeError, ValueError):
        reps_f = float(PULLUP_DEFAULT_REPS)
    if reps_f <= 0:
        reps_f = float(PULLUP_DEFAULT_REPS)
    rir = PULLUP_RIR_BY_LABEL.get(feedback_label, 2)
    last_set = item.get("last_set_reps")
    measured_reps: Optional[float] = None
    if isinstance(last_set, (int, float)) and not isinstance(last_set, bool) and last_set > 0:
        measured_reps = float(last_set)

    existing = next(
        (e for e in _working_entries_ro(updated) if str(e.get("exercise_id") or "") == "weighted_pullup"
         and isinstance(e.get("e2rm_total_kg"), (int, float))),
        None,
    )
    if existing is not None:
        existing_date = str(existing.get("updated_at") or "")
        # A log older than the stored re-base must not move it, up or down.
        if date_value < existing_date:
            return
        # Idempotent: the same log applied twice re-bases once.
        if (
            date_value == existing_date
            and existing.get("last_total_load_kg") == _round_half_step(float(used_total))
            and existing.get("last_feedback_label") == rating
            and existing.get("last_set_reps") == (int(measured_reps) if measured_reps is not None else None)
        ):
            return
    _, base_date = _pullup_baseline_2rm(updated)
    if base_date and date_value < base_date:
        # Older than the current test: the test already supersedes it.
        return

    if measured_reps is not None:
        set_2rm = _two_rm_from_1rm(estimate_1rm_from_reps(float(used_total), measured_reps + 1))
    else:
        set_2rm = _two_rm_from_1rm(estimate_1rm_from_reps(float(used_total), reps_f + rir))
    reference = pullup_reference_2rm(updated)
    if feedback_label in {"hard", "very_hard"}:
        base = reference if reference else set_2rm
        new_2rm = _round_half_step(base * (1.0 + _rule_midpoint_pct(updated, feedback_label)))
    else:
        new_2rm = _round_half_step(max(reference or 0.0, set_2rm))
    if reference and mf.active_pain_block(updated, mf.exercise_pain_sites("weighted_pullup"), date_value):
        new_2rm = min(new_2rm, _round_half_step(reference))

    entry = _find_working_load_entry(updated, "weighted_pullup", {})
    entry.update({
        "exercise_id": "weighted_pullup",
        "key": "weighted_pullup",
        "setup": {},
        "last_completed": bool(item.get("completed", False)),
        "last_feedback_label": rating,
        "last_rated": bool(rated) if rated is not None else rating is not None,
        "last_external_load_kg": _round_half_step(float(used_external)),
        "last_total_load_kg": _round_half_step(float(used_total)),
        "last_reps": int(reps_f),
        "e2rm_total_kg": new_2rm,
        "updated_at": date_value,
    })
    if measured_reps is not None:
        entry["last_set_reps"] = int(measured_reps)
    else:
        entry.pop("last_set_reps", None)
    phase_id = _get_current_phase_id(updated, date_value)
    target = weighted_pullup_target(updated, phase_id, "hard")
    if target is not None:
        entry["next_total_load_kg"] = target["total"]
        entry["next_external_load_kg"] = target["external"]


_UNPAINED_DROP_PREFIXES = ("suggested_", "pain", "right_hand", "left_hand", "target_", "added_weight",
                           "assistance", "anchored", "load_", "reference_2rm", "dp_", "measure")


def _pain_reference_reads(
    state: Dict[str, Any],
    exercise_id: str,
    session: Dict[str, Any],
    planned_inst: Dict[str, Any],
    item: Dict[str, Any],
    date_value: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """A295 review — what the read side prescribes for this exercise on
    ``date_value`` WITHOUT and WITH the pain block: the two references the
    write side uses to undo the cut during a block (see
    ``measured_feedback.pain_hold_next``). Pure: the same inject_targets on
    the state with and without its pain blocks; stale load fields of the
    planned instance are dropped first so they cannot leak into the result."""
    from backend.engine import measured_feedback as mf

    if planned_inst:
        inst = deepcopy(planned_inst)
    else:
        presc = {}
        for src, dst in (("prescribed_sets", "sets"), ("prescribed_reps", "reps"),
                         ("prescribed_work_seconds", "work_seconds"), ("work_seconds", "work_seconds")):
            if item.get(src) is not None:
                presc[dst] = item[src]
        inst = {"exercise_id": exercise_id, "prescription": presc}
    inst["suggested"] = {k: v for k, v in (inst.get("suggested") or {}).items()
                         if not str(k).startswith(_UNPAINED_DROP_PREFIXES)}
    sess = {k: v for k, v in (session or {}).items() if k != "exercise_instances"}
    sess.setdefault("session_id", "")
    sess["exercise_instances"] = [inst]
    try:
        reads = []
        for st in (mf.state_without_pain(state), state):
            out = inject_targets({"date": date_value, "sessions": [deepcopy(sess)]}, st)
            reads.append(out["sessions"][0]["exercise_instances"][0].get("suggested") or {})
        return reads[0], reads[1]
    except Exception:  # pragma: no cover — defensive: never break a feedback write
        logger.warning("pain reference read failed for %s on %s", exercise_id, date_value, exc_info=True)
        return {}, {}


def _hang_seconds_of(planned_prescription: Dict[str, Any], item: Dict[str, Any], exercise_id: str) -> float:
    return float(
        _first_not_none(planned_prescription.get("work_seconds"), item.get("work_seconds"),
                        item.get("prescribed_work_seconds"))
        or ((_load_catalog_cache().get(exercise_id) or {}).get("prescription_defaults") or {}).get("work_seconds")
        or 7
    )


def _hang_margin_step(
    existing: Optional[Dict[str, Any]],
    item: Dict[str, Any],
    *,
    rating: Optional[str],
    used_total: float,
    date_value: str,
    planned_prescription: Dict[str, Any],
    exercise_id: str,
) -> Tuple[float, Dict[str, Any]]:
    """A295 — measured hang outside the anchored path (untested max hangs,
    max_hang_10s, horst_7_53): next total = used + the measured kg step.

    Same bands as the anchored hang (B364 ``_hang_measured_step``: >5 s +4,
    3-5 s +2, 0-2 s hold, failed −2 kg; a timed hold is read in seconds), one
    step per exposure, and the total never rises more than FINGER_MAX_RISE_PCT
    (5 %) over the rolling 7-day escalation anchor. A hard label never lets a
    measure raise the load. Returns (next total, extra entry fields).
    """
    from backend.engine.anchored_load import (
        FINGER_MAX_RISE_PCT,
        FINGER_RISE_WINDOW_D,
        _hang_measured_step,
    )

    t = _hang_seconds_of(planned_prescription, item, exercise_id)
    step = _hang_measured_step(item, t) or 0.0
    if rating in ("hard", "very_hard"):
        step = min(step, 0.0)
    if item.get("completed") is False:
        step = min(step, 0.0)
    anchor = (existing or {}).get("escalation_anchor")
    anchor_d = _parse_day((anchor or {}).get("date"))
    now_d = _parse_day(date_value)
    if not isinstance(anchor, dict) or anchor_d is None or now_d is None or (now_d - anchor_d).days >= FINGER_RISE_WINDOW_D:
        anchor = {"date": date_value, "total_kg": _round_half_step(used_total)}
    rise_cap = math.floor((float(anchor["total_kg"]) * (1 + FINGER_MAX_RISE_PCT)) * 2 + 1e-9) / 2
    next_total = min(_round_half_step(used_total + step), rise_cap)
    extra: Dict[str, Any] = {"escalation_anchor": anchor, "last_work_seconds": t}
    if item.get("hang_margin") is not None:
        extra["last_hang_margin"] = item.get("hang_margin")
    if item.get("hang_held_s") is not None:
        extra["last_hang_held_s"] = item.get("hang_held_s")
    return next_total, extra


_DP_SNAPSHOT_FIELDS = ("dp_target_reps", "dp_range")


def _dp_label_pct(user_state: Dict[str, Any], label: str) -> float:
    """Label step of a double-progression accessory WITHOUT a measure.

    A stored ``working_loads.rules.adjustment_policy`` entry still wins (an
    explicit user choice, B344). Otherwise easy +5 % / very_easy +10 %
    (DECISIONS 2026-10-04) and the default policy for ok / hard / very_hard.
    """
    from backend.engine import measured_feedback as mf

    stored = (((user_state.get("working_loads") or {}).get("rules") or {}).get("adjustment_policy") or {})
    if label in stored:
        return _rule_midpoint_pct(user_state, label)
    if label in mf.DP_LABEL_STEP_PCT:
        return mf.DP_LABEL_STEP_PCT[label]
    return _rule_midpoint_pct(user_state, label)


def _apply_dp_feedback(
    updated: Dict[str, Any],
    entry: Dict[str, Any],
    item: Dict[str, Any],
    *,
    exercise_id: str,
    rating: Optional[str],
    base: float,
    date_value: str,
    session_key: str,
    planned_prescription: Dict[str, Any],
    last_set_reps: Optional[int],
) -> Tuple[float, Dict[str, Any]]:
    """A295 (R4 §3c) — double progression of a reps accessory.

    Returns (next load, fields to merge into the entry). ``base`` is the load
    used (external for external_load, total for total_load); the caller turns
    the result into its own next_* fields.

    Measured success (last-set reps ≥ target, all prescribed sets done, label
    not hard, no pain block on the zone) → target + 1 rep; at the top of the
    range → load + 2.5 % (fingers + 1.25 %, B344 floor +0.5 kg) and target back
    to lo. Without a measure the label policy applies (easy +5 %, very_easy
    +10 %, hard / very_hard the adjustment policy); not rated → hold.

    Idempotent: the entry keeps ``applied {key, base_before}``; the same
    (date, session) recomputes from the snapshot, so a replay gives the same
    result and a pencil correction takes effect.
    """
    from backend.engine import measured_feedback as mf

    applied = entry.get("applied") if isinstance(entry.get("applied"), dict) else None
    if applied and applied.get("key") == session_key:
        before = dict(applied.get("base_before") or {})
    else:
        before = {k: deepcopy(entry.get(k)) for k in _DP_SNAPSHOT_FIELDS if entry.get(k) is not None}

    lo_raw = mf.prescribed_reps_of(exercise_id, item, planned_prescription)
    lo, hi = mf.dp_range(lo_raw or 1)
    stored_target = mf.dp_target_for(before, lo)
    shown = mf._int(item.get("target_reps"))
    target = max(lo, min(hi, shown)) if shown else stored_target

    completed = item.get("completed") is not False
    done_sets = _first_not_none(item.get("completed_sets"))
    presc_sets = _first_not_none(item.get("prescribed_sets"), planned_prescription.get("sets"))
    sets_ok = not (
        isinstance(done_sets, (int, float)) and isinstance(presc_sets, (int, float)) and done_sets < presc_sets
    )
    pain = mf.active_pain_block(updated, mf.exercise_pain_sites(exercise_id), date_value)
    step_pct = mf.DP_FINGER_LOAD_STEP_PCT if mf.is_finger_loading(exercise_id) else mf.DP_LOAD_STEP_PCT

    next_target = target
    next_load = _round_half_step(base)
    outcome = "hold"
    if not completed:
        outcome = "not_completed"
    elif last_set_reps is not None:
        success = last_set_reps >= target and sets_ok and rating not in ("hard", "very_hard") and pain is None
        if success and target < hi:
            next_target, outcome = target + 1, "reps_up"
        elif success:
            next_load, next_target, outcome = _next_external_load(base, step_pct), lo, "load_up"
        elif rating in ("hard", "very_hard"):
            next_load, outcome = _next_external_load(base, _rule_midpoint_pct(updated, rating)), "label_down"
        elif pain is not None:
            outcome = "pain_freeze"
    elif rating is not None:
        pct = _dp_label_pct(updated, rating)
        if pct > 0 and pain is not None:
            outcome = "pain_freeze"
        elif pct != 0:
            next_load = _next_external_load(base, pct)
            outcome = "label_up" if pct > 0 else "label_down"

    fields: Dict[str, Any] = {
        "dp_target_reps": next_target,
        "dp_range": [lo, hi],
        "dp_last_outcome": outcome,
        "applied": {"key": session_key, "base_before": before},
    }
    if last_set_reps is not None:
        fields["last_set_reps"] = last_set_reps
    return next_load, fields


def apply_feedback(log_entry: Dict[str, Any], user_state: Dict[str, Any]) -> Dict[str, Any]:
    from backend.engine import measured_feedback as mf

    updated = deepcopy(user_state)
    actual = log_entry.get("actual") or {}
    feedback_items = actual.get("exercise_feedback_v1") or []
    date_value = str(log_entry.get("date") or "")
    bodyweight = _get_bodyweight(updated)

    from backend.engine.anchored_load import (
        ANCHORED_EXERCISES,
        apply_anchored_feedback,
        record_exposures,
    )

    counters = updated.setdefault("progression_counters", {})
    if not isinstance(counters, dict):
        counters = {}
        updated["progression_counters"] = counters
    _ensure_test_queue(updated)
    # B364: labels never schedule a test. The max-hang label streaks that fed
    # the label enqueue are gone with it (DECISIONS 2026-10-04).
    counters.pop("max_hang_5s_hard_streak", None)
    counters.pop("max_hang_5s_easy_streak", None)
    # B364: the ONE persisted exposure registry (A288's view reads it).
    record_exposures(updated, log_entry)
    # A295: feedback contract + pain. Pain is written BEFORE the items so a
    # pain reported today already freezes today's upward steps and signals.
    contract = mf.log_contract(log_entry)
    mf.record_pain(updated, log_entry)
    session_key = f"{date_value}|{str(log_entry.get('session_id') or '')}"
    # Per-hand items of one exercise: the double progression reads the WEAKER
    # hand (min of the last-set reps) before the single step.
    min_last_set: Dict[str, int] = {}
    for _it in feedback_items:
        _eid = str(_it.get("exercise_id") or "").strip()
        _r = _it.get("last_set_reps")
        if _eid and isinstance(_r, (int, float)) and not isinstance(_r, bool):
            min_last_set[_eid] = min(int(_r), min_last_set.get(_eid, int(_r)))

    for item in feedback_items:
        exercise_id = str(item.get("exercise_id") or "").strip()
        if not exercise_id:
            continue
        # A295: None = not rated (no label, or a legacy 'ok' — the old default
        # at zero input). The load math reads it as 'ok' (hold the load used);
        # the stored label stays None and last_rated tells the two apart.
        rating = mf.feedback_rating(item, contract)
        feedback_label = rating or "ok"
        measure = mf.measure_kind(exercise_id, is_test=_is_test_log(log_entry))
        rated = rating is not None or mf.has_measure(item)

        session, planned_inst = _lookup_planned_instance(log_entry, exercise_id)
        planned_prescription = (planned_inst.get("prescription") or {}) if planned_inst else {}
        planned_target = (((planned_inst.get("suggested") or {}).get("suggested_boulder_target") or {}) if planned_inst else {})
        catalog_info = _load_catalog_cache().get(exercise_id, {})
        fb_load_model = (planned_inst.get("load_model") if planned_inst else None) or item.get("load_model") or catalog_info.get("load_model")
        # C-LOADMODEL-MISTAG: per-hand write keys on loading-pin equipment, not
        # raw unilaterality — mirror of the read-side is_loading_pin gate.
        fb_loading_pin = catalog_info.get("loading_pin", False)

        # B363: a TEST of a test-anchored exercise is a max, not a training
        # load. It updates the baseline (_update_test_from_log, below) and
        # retires the old training memory so the next prescription re-anchors
        # on the fresh max as a percentage.
        if _is_pure_test_exercise(exercise_id) or (
            exercise_id in TEST_ANCHORED_EXERCISES and _is_test_log(log_entry)
        ):
            # Retire the old memory only when the test produced a result —
            # the same fields _update_test_from_log writes the baseline from.
            # A skipped/aborted test item must not wipe a valid re-base.
            has_result = item.get("used_total_load_kg") is not None or item.get("used_external_load_kg") is not None
            if has_result:
                wl = updated.setdefault("working_loads", {})
                wl["entries"] = [
                    e for e in (wl.get("entries") or [])
                    if str(e.get("exercise_id") or "") != exercise_id
                ]
            continue

        # B364: anchored exercises of a TESTED athlete — working load moves in
        # kg steps from the load used, inside the cap; the max never moves.
        if exercise_id in ANCHORED_EXERCISES:
            setup_source = dict(planned_prescription)
            setup_source.update(item)
            if apply_anchored_feedback(
                updated,
                item,
                feedback_label=rating,
                date_value=date_value,
                planned_session=session or None,
                planned_prescription=planned_prescription,
                setup_source=setup_source,
                session_key=session_key,
            ):
                continue

        if exercise_id == "weighted_pullup":
            _apply_weighted_pullup_feedback(
                updated, item, planned_prescription, feedback_label, date_value, bodyweight,
                rating=rating, rated=rated,
            )
            continue

        if fb_load_model == "total_load":
            used_total = item.get("used_total_load_kg")
            used_external = item.get("used_external_load_kg")
            if used_total is None and used_external is not None:
                used_total = float(used_external) + bodyweight
            if used_external is None and used_total is not None:
                used_external = float(used_total) - bodyweight
            if used_total is None and used_external is None:
                continue

            setup_source = dict(planned_prescription)
            setup_source.update(item)
            setup, setup_key = _progression_setup_and_key(exercise_id, setup_source)
            existing_entry = next(
                (e for e in _working_entries_ro(updated) if str(e.get("key") or "") == setup_key), None,
            )
            extra: Dict[str, Any] = {}
            if measure == mf.MEASURE_HANG_MARGIN and mf.has_measure(item):
                # A295: a measured hang (untested max hang, 10 s, Hörst) moves
                # the working load in the same kg bands as the anchored hang
                # (B364), inside a +5 % rise per rolling 7 days.
                if existing_entry is not None and str(existing_entry.get("updated_at") or "") > date_value:
                    continue  # a newer log already moved it: never rewrite it
                next_total, extra = _hang_margin_step(
                    existing_entry, item, rating=rating, used_total=float(used_total),
                    date_value=date_value, planned_prescription=planned_prescription,
                    exercise_id=exercise_id,
                )
            elif measure == mf.MEASURE_DP_REPS:
                if existing_entry is not None and str(existing_entry.get("updated_at") or "") > date_value:
                    continue
                dp_entry = existing_entry if existing_entry is not None else {}
                next_total, extra = _apply_dp_feedback(
                    updated, dp_entry, item, exercise_id=exercise_id, rating=rating,
                    base=float(used_total), date_value=date_value, session_key=session_key,
                    planned_prescription=planned_prescription,
                    last_set_reps=min_last_set.get(exercise_id),
                )
            elif measure == mf.MEASURE_LAST_SET_REPS and min_last_set.get(exercise_id) is not None:
                # A295 review: an untested weighted chin-up with the measure
                # the client asked for — the same kg bands as the anchored
                # pull (B364), never up on a hard label or an unfinished set.
                from backend.engine.anchored_load import PULL_MAX_STEP_KG, _pull_measured_step

                if existing_entry is not None and str(existing_entry.get("updated_at") or "") > date_value:
                    continue
                pull_reps = int(_first_not_none(item.get("reps"), item.get("prescribed_reps"),
                                                planned_prescription.get("reps")) or 0) \
                    or mf.prescribed_reps_of(exercise_id) or 1
                step = _pull_measured_step({"last_set_reps": min_last_set[exercise_id]}, pull_reps, float(used_total)) or 0.0
                step = min(step, PULL_MAX_STEP_KG)
                if rating in ("hard", "very_hard"):
                    step = min(step, _round_half_step(float(used_total) * _rule_midpoint_pct(updated, rating)))
                if item.get("completed") is False:
                    step = min(step, 0.0)
                next_total = _round_half_step(float(used_total) + step)
                extra = {"last_set_reps": min_last_set[exercise_id], "last_reps": pull_reps}
            else:
                pct = _rule_midpoint_pct(updated, feedback_label)
                next_total = _round_half_step(float(used_total) * (1.0 + pct))
            if exercise_id in mf.HANG_MARGIN_EXERCISES:
                # A295 review: a finger hang outside the anchored four never
                # goes above the structural ceiling of a tested athlete.
                from backend.engine.anchored_load import hang_write_cap

                hang_cap = hang_write_cap(updated, _hang_seconds_of(planned_prescription, item, exercise_id), date_value)
                if hang_cap is not None:
                    next_total = min(next_total, hang_cap)
            pain_blk = mf.active_pain_block(updated, mf.exercise_pain_sites(exercise_id), date_value)
            if pain_blk is not None:
                # A295 review: under a pain block nothing on the zone goes up,
                # and the pain-reduced load is never stored as the new memory.
                ref, cut = _pain_reference_reads(updated, exercise_id, session, planned_inst, item, date_value)
                next_total, extra["pain_hold"] = mf.pain_hold_next(
                    existing_entry, field="next_total_load_kg", used=float(used_total),
                    computed_next=next_total, session_key=session_key, date_value=date_value,
                    reference_before=ref.get("suggested_total_load_kg"), reference_cut=cut.get("suggested_total_load_kg"),
                )
                anchor = extra.get("escalation_anchor")
                if isinstance(anchor, dict) and anchor.get("date") == date_value:
                    extra["escalation_anchor"] = {
                        "date": date_value, "total_kg": _round_half_step(max(next_total, float(used_total))),
                    }
            next_external = _round_half_step(next_total - bodyweight)

            entry = _find_working_load_entry(updated, exercise_id, setup)
            if pain_blk is None:
                entry.pop("pain_hold", None)
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": setup_key,
                    "setup": setup,
                    "last_completed": bool(item.get("completed", False)),
                    "last_feedback_label": rating,
                    "last_rated": rated,
                    "last_external_load_kg": _round_half_step(float(used_external)),
                    "last_total_load_kg": _round_half_step(float(used_total)),
                    "next_external_load_kg": next_external,
                    "next_total_load_kg": next_total,
                    "updated_at": date_value,
                    **extra,
                }
            )


        elif fb_load_model == "external_load" and not fb_loading_pin:
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
            extra = {}
            existing_entry = next(
                (e for e in _working_entries_ro(updated) if str(e.get("key") or "") == exercise_id), None,
            )
            if measure == mf.MEASURE_DP_REPS:
                if existing_entry is not None and str(existing_entry.get("updated_at") or "") > date_value:
                    continue  # out-of-order log: the newer entry is never rewritten
                next_load, extra = _apply_dp_feedback(
                    updated, existing_entry if existing_entry is not None else {}, item,
                    exercise_id=exercise_id, rating=rating, base=base, date_value=date_value,
                    session_key=session_key, planned_prescription=planned_prescription,
                    last_set_reps=min_last_set.get(exercise_id),
                )
            else:
                pct = _rule_midpoint_pct(updated, feedback_label)
                next_load = _next_external_load(base, pct)
            pain_blk = mf.active_pain_block(updated, mf.exercise_pain_sites(exercise_id), date_value)
            if pain_blk is not None:
                ref, cut = _pain_reference_reads(updated, exercise_id, session, planned_inst, item, date_value)
                next_load, extra["pain_hold"] = mf.pain_hold_next(
                    existing_entry, field="next_external_load_kg", used=base,
                    computed_next=next_load, session_key=session_key, date_value=date_value,
                    reference_before=ref.get("suggested_external_load_kg"), reference_cut=cut.get("suggested_external_load_kg"),
                )
            entry = _find_working_load_entry(updated, exercise_id, {})
            if pain_blk is None:
                entry.pop("pain_hold", None)
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": exercise_id,
                    "setup": {},
                    "last_completed": bool(item.get("completed", False)),
                    "last_feedback_label": rating,
                    "last_rated": rated,
                    "last_external_load_kg": _round_half_step(base),
                    "next_external_load_kg": next_load,
                    "updated_at": date_value,
                    **extra,
                }
            )

        elif fb_load_model == "grade_relative" and _is_limit_grade_exercise(exercise_id):
            # B289 group A: whole climbing_limit_boulder family (was
            # limit_bouldering only). Surface-keyed memory, per-feedback steps.
            # A296: with a problem log the target moves on what was climbed
            # (limit_log.classify_session); the label path stays the fallback.
            used_grade = normalize_font_grade(item.get("used_grade"))
            problems, _problem_warnings = limit_log.sanitize_problems(item.get("problems"))
            if not used_grade and not problems:
                continue
            options = list(planned_target.get("surface_options") or _surface_options(updated, session.get("gym_id")))
            surface_selected = _select_surface(
                preferred=item.get("surface_selected") or planned_target.get("surface_selected"),
                options=options,
                gym_id=session.get("gym_id"),
                user_state=updated,
            )
            # B365 (R6.0): is this session part of a re-entry? Evaluated on the
            # state BEFORE this write, with the same function the read uses.
            # Idempotent on a same-day resubmission (B197): an entry whose
            # re-entry already counted today is recomputed, not re-counted.
            prior = _limit_family_entry(updated, surface_selected, date_value)
            reentry_fields: Optional[Dict[str, Any]] = None
            if (
                prior is not None
                and normalize_font_grade(prior.get("reentry_base_grade"))
                and str(prior.get("reentry_last_at") or "") == date_value
            ):
                reentry_fields = {
                    "reentry_base_grade": normalize_font_grade(prior.get("reentry_base_grade")),
                    "reentry_exposures": int(prior.get("reentry_exposures") or 1),
                    "reentry_started_at": prior.get("reentry_started_at") or date_value,
                    "reentry_last_at": date_value,
                }
            else:
                limit_prescription = planned_prescription or (catalog_info.get("prescription_defaults") or {})
                limit_state = _limit_target_state(
                    updated,
                    limit_prescription,
                    surface_selected,
                    date_value,
                    _extract_grade_benchmark(updated),
                )
                if limit_state["reentry"]:
                    reentry = limit_state["reentry"]
                    reentry_fields = {
                        "reentry_base_grade": reentry["base_grade"],
                        "reentry_exposures": int(reentry["exposures_done"]) + 1,
                        "reentry_started_at": reentry.get("started_at") or date_value,
                        "reentry_last_at": date_value,
                    }

            # A296: the prescribed target of the day — planned instance first,
            # then the target this same session already logged (a resubmission
            # must not re-read a memory it just moved), then the read function
            # on the state before this write (custom / adhoc sessions).
            log_session_id = str(log_entry.get("session_id") or "") or None
            prior_log = limit_log.find_entry(updated, date_value, log_session_id, exercise_id)
            planned_surface = str(planned_target.get("surface_selected") or "").strip().lower()
            day_target = (
                # A planned target is for its own surface: switching from the
                # Kilter to the wall reads the wall's target instead.
                (normalize_font_grade(planned_target.get("target_grade"))
                 if planned_surface in ("", surface_selected) else None)
                or normalize_font_grade((prior_log or {}).get("target_grade"))
            )
            if day_target is None:
                day_target = _limit_target_state(
                    updated,
                    planned_prescription or (catalog_info.get("prescription_defaults") or {}),
                    surface_selected,
                    date_value,
                    _extract_grade_benchmark(updated),
                )["target"]

            delta = _grade_delta_for_feedback(feedback_label)
            classification: Optional[Dict[str, Any]] = None
            reference: Optional[str] = None
            if problems and (reentry_fields is None or reentry_fields["reentry_exposures"] >= LIMIT_REENTRY_EXPOSURES):
                # Measured: the problems decide (the label is kept for info).
                # Closing a re-entry, progression is judged against the BASE.
                reference = reentry_fields["reentry_base_grade"] if reentry_fields is not None else day_target
                classification = limit_log.classify_session(
                    problems, reference, limit_log.previous_entry(updated, surface_selected, date_value),
                )
                delta = int(classification["delta"])
            if reentry_fields is None:
                # A291: half grades, the '+' survives ('ok' on 7A+ stays 7A+;
                # step_grade used to strip it to 7A).
                # A296: with problems the step applies to the day's target.
                base_grade = reference if classification is not None else used_grade
                next_grade = _step_font_half(base_grade, delta) or base_grade
            elif reentry_fields["reentry_exposures"] < LIMIT_REENTRY_EXPOSURES:
                # Still re-entering: keep the BASE as the memory (the read
                # applies the discount), never the discounted grade.
                next_grade = reentry_fields["reentry_base_grade"]
            else:
                # Re-entry closes: progression relative to the base.
                next_grade = _step_font_half(reentry_fields["reentry_base_grade"], delta) or reentry_fields["reentry_base_grade"]
            setup, setup_key = _progression_setup_and_key(exercise_id, {"surface": surface_selected})
            entry = _find_working_load_entry(updated, exercise_id, setup)
            # The band reads last_used_grade as "the best grade CLIMBED": with
            # problems it is the hardest send, else the grade the athlete
            # typed; with neither the previous value is kept (never the target).
            climbed = (limit_log.best_sent(problems) if problems else None) or used_grade
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": setup_key,
                    "setup": setup,
                    "surface_selected": surface_selected,
                    "last_feedback_label": rating,
                    "last_rated": rated or bool(problems),
                    "next_target_grade": next_grade,
                    "updated_at": date_value,
                }
            )
            if climbed:
                entry["last_used_grade"] = climbed
            for field in _LIMIT_REENTRY_FIELDS:
                entry.pop(field, None)
            if reentry_fields is not None:
                entry.update(reentry_fields)

            # A296: the limit log entry (one per date+session+exercise).
            log_row: Dict[str, Any] = {
                "date": date_value,
                "session_id": log_session_id,
                "exercise_id": exercise_id,
                "surface": surface_selected,
                "target_grade": day_target,
                "problems": problems,
                "source": limit_log.source_for_session(log_session_id),
                "feedback_label": rating,
                "used_grade": used_grade,
                "next_target_grade": next_grade,
            }
            if classification is not None:
                log_row.update({
                    "reference_grade": reference,
                    "step": classification["delta"],
                    "step_reason": classification["reason"],
                    "hard_attempts": classification["hard_attempts"],
                })
                if classification["guard"]:
                    log_row["warning"] = "hard_attempts_guard"
            elif problems and reentry_fields is not None:
                log_row["step_reason"] = "reentry"
            if problems:
                log_row["qualifies"] = limit_log.qualifies(problems, day_target)
            # A sent above the boulder redpoint never writes the max: it is
            # only proposed. Gym boulder only — a board grade is not an RP.
            rp = normalize_font_grade(((updated.get("assessment") or {}).get("grades") or {}).get("boulder_max_rp"))
            top = limit_log.best_sent(problems) if problems else None
            if (
                top and rp and surface_selected not in LIMIT_BOARD_SURFACES
                and FONT_GRADE_TO_INDEX.get(top, -1) > FONT_GRADE_TO_INDEX[rp]
            ):
                log_row["rp_proposal"] = {"grade": top, "current": rp}
            limit_log.upsert_entry(updated, log_row)

        elif fb_load_model == "grade_relative" and _grade_relative_group(exercise_id) == "endurance":
            # B289 group B (intervals/continuous): the grade is an intensity
            # target, not a max — one easy/hard session is noise. The target
            # steps ±1 HALF grade (A291; was a whole letter) only after 2
            # CONSECUTIVE CONCORDANT
            # feedbacks (easy/very_easy up, hard/very_hard down); "ok" resets
            # the streak and re-anchors the target to the grade actually used.
            # Memory keyed on exercise_id alone (no setup: the circuit grade
            # is gym-relative, but per-surface splits would fragment the
            # little signal endurance work produces).
            # A291: the ladder follows the anchor's scale — planned grade_ref,
            # else the catalog default (custom sessions send no planned
            # instance). French covers 9A/9A+, which the Font list lacks.
            endurance_scale = grade_scale_for_ref(
                planned_prescription.get("grade_ref")
                or (catalog_info.get("prescription_defaults") or {}).get("grade_ref")
            )
            used_grade = normalize_grade_on_scale(item.get("used_grade"), endurance_scale)
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
            if rating is None:
                # A295: not rated — the target follows the grade climbed and
                # the concordance streak is left exactly as it was.
                streak_dir, streak_count = prev_dir, prev_count
                next_grade = used_grade
            elif direction == 0:
                streak_dir, streak_count = 0, 0
                next_grade = used_grade
            else:
                streak_count = prev_count + 1 if direction == prev_dir else 1
                if streak_count >= 2:
                    next_grade = step_grade_half(used_grade, direction, endurance_scale) or used_grade
                    streak_dir, streak_count = 0, 0
                else:
                    next_grade = used_grade
                    streak_dir = direction
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": exercise_id,
                    "setup": {},
                    "last_feedback_label": rating,
                    "last_rated": rated,
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

        elif fb_load_model == "external_load" and fb_loading_pin:
            # Loading-pin (finger, per-hand): feedback includes hand field
            hand = str(item.get("hand") or "right").lower()
            # B288: same falsy-0 bug as the bilateral branch above.
            used_load = _first_not_none(
                item.get("used_external_load_kg"), item.get("used_load_kg")
            )
            if used_load is None:
                continue
            base = float(used_load)
            pct = _rule_midpoint_pct(updated, feedback_label)
            next_load = _next_external_load(base, pct)
            hand_key = f"{exercise_id}:{hand}"
            entries = _working_entries(updated)
            entry = None
            for e in entries:
                if str(e.get("key") or "") == hand_key:
                    entry = e
                    break
            pain_blk = mf.active_pain_block(updated, mf.exercise_pain_sites(exercise_id), date_value)
            hold_fields: Dict[str, Any] = {}
            if pain_blk is not None:
                ref, cut = _pain_reference_reads(updated, exercise_id, session, planned_inst, item, date_value)
                next_load, hold_fields["pain_hold"] = mf.pain_hold_next(
                    entry, field="next_external_load_kg", used=base,
                    computed_next=next_load, session_key=session_key, date_value=date_value,
                    reference_before=(ref.get(f"{hand}_hand") or {}).get("suggested_external_load_kg"),
                    reference_cut=(cut.get(f"{hand}_hand") or {}).get("suggested_external_load_kg"),
                )
            if entry is None:
                entry = {"exercise_id": exercise_id, "key": hand_key, "hand": hand}
                entries.append(entry)
                entries.sort(key=lambda e: str(e.get("key") or ""))
            if pain_blk is None:
                entry.pop("pain_hold", None)
            entry.update(hold_fields)
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": hand_key,
                    "hand": hand,
                    "last_completed": bool(item.get("completed", False)),
                    "last_feedback_label": rating,
                    "last_rated": rated,
                    "last_external_load_kg": _round_half_step(base),
                    "next_external_load_kg": next_load,
                    "updated_at": date_value,
                }
            )

    _update_test_from_log(log_entry, updated, bodyweight)
    _prune_test_queue(updated)
    return updated
