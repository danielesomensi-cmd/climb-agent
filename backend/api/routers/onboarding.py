"""Onboarding router — defaults and complete flow."""

from __future__ import annotations

import logging
import uuid
from copy import deepcopy
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.deps import REPO_ROOT, build_current_level, ensure_monday, get_user_id, invalidate_week_cache, load_state, next_monday, this_monday, save_state
from backend.api.rate_limit import limiter
from backend.api.models import OnboardingData, OnboardingDraftEnvelope, StartWeekRequest
from backend.engine.assessment_v1 import GRADE_ORDER, compute_assessment_profile
from backend.engine.grade_mapping import BOULDER_TO_LEAD
from backend.engine.macrocycle_v1 import generate_macrocycle
from backend.engine.progression_v1 import estimate_missing_baselines
from backend.engine.start_date_utils import (
    is_week_one_empty,
    strict_next_monday,
    this_monday as _engine_this_monday,
)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

# A233: whitelist of attribution keys the client may persist. Anything else
# is dropped server-side; values are cut to _ATTRIBUTION_MAX_LEN chars.
_ATTRIBUTION_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "referrer", "landing_page", "first_touch_at",
}
_ATTRIBUTION_MAX_LEN = 200


def _sanitize_attribution(raw: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Keep only whitelisted string keys, truncated — never trust the client."""
    if not raw or not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for key in _ATTRIBUTION_KEYS:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            out[key] = value.strip()[:_ATTRIBUTION_MAX_LEN]
    return out

# Boulder grades (Fontainebleau)
BOULDER_GRADE_ORDER = [
    "5A", "5B", "5C",
    "6A", "6A+", "6B", "6B+", "6C", "6C+",
    "7A", "7A+", "7B", "7B+", "7C", "7C+",
    "8A", "8A+", "8B", "8B+", "8C", "8C+",
]

WEAKNESS_OPTIONS_UNIVERSAL = [
    {"id": "fingers_give_out", "label": "My fingers give out", "description": "Finger strength is my main limiter"},
    {"id": "cant_hold_hard_moves", "label": "Can't hold hard moves", "description": "I lack strength/power on single crux moves"},
    {"id": "technique_errors", "label": "Technique errors", "description": "I fall due to body position or movement mistakes"},
    {"id": "lack_power", "label": "Lack explosive power", "description": "Dynamic moves and dynos are my weak point"},
    {"id": "injury_prone", "label": "Frequent injuries", "description": "Physical issues limit my training"},
]

WEAKNESS_OPTIONS_LEAD = [
    {"id": "pump_too_early", "label": "I pump out too early", "description": "My forearms pump before my strength gives out"},
    {"id": "cant_read_routes", "label": "Can't read routes", "description": "I struggle to find the beta and read sequences"},
    {"id": "cant_manage_rests", "label": "Can't manage rests", "description": "I don't recover well on rest stances"},
]

WEAKNESS_OPTIONS_BOULDER = [
    {"id": "poor_body_tension", "label": "Poor body tension", "description": "I can't maintain tension on steep terrain, feet cut"},
    {"id": "poor_dynamic_movement", "label": "Poor dynamic movement", "description": "I struggle with coordination moves and dynos"},
    {"id": "weak_on_slopers", "label": "Weak on slopers", "description": "I struggle on rounded or open-hand holds"},
    {"id": "poor_problem_reading", "label": "Poor problem reading", "description": "I can't read sequences or find beta efficiently"},
]

# Flat list for backward compatibility
WEAKNESS_OPTIONS = WEAKNESS_OPTIONS_UNIVERSAL + WEAKNESS_OPTIONS_LEAD + WEAKNESS_OPTIONS_BOULDER

EQUIPMENT_HOME = [
    {"id": "hangboard", "label": "Hangboard", "description": "Finger training board"},
    {"id": "loading_pin", "label": "Loading Pin (hangboard alternative)", "description": "Pin for one-arm weighted hangs"},
    {"id": "homewall", "label": "Homewall", "description": "Home climbing wall (any size or board type)"},
    {"id": "pullup_bar", "label": "Pull-up bar", "description": "Fixed bar for pull-ups and hanging exercises"},
    {"id": "dumbbell", "label": "Dumbbells", "description": "Dumbbells for strength exercises"},
    {"id": "kettlebell", "label": "Kettlebell", "description": "Kettlebell for functional exercises"},
    {"id": "band", "label": "Assistance band", "description": "Elastic band for assistance or resistance"},
    {"id": "resistance_band", "label": "Resistance band", "description": "Elastic band for activation and prehab exercises"},
    {"id": "rings", "label": "Rings", "description": "Gymnastic rings for suspension exercises"},
    {"id": "foam_roller", "label": "Foam Roller", "description": "Roller for self-massage and myofascial release"},
    {"id": "ab_wheel", "label": "Ab Wheel", "description": "Abdominal wheel"},
    {"id": "pinch_block", "label": "Pinch Block", "description": "Block for pinch grip training"},
]

EQUIPMENT_GYM = [
    # --- Climbing areas ---
    {"id": "gym_boulder", "label": "Bouldering area", "description": "Gym with bouldering sector and set problems"},
    {"id": "gym_routes", "label": "Lead / Top-rope walls", "description": "Wall for roped climbing"},
    {"id": "spraywall", "label": "Spraywall", "description": "Wall with fixed holds for custom boulders"},
    # --- Boards ---
    {"id": "board_kilter", "label": "Kilter Board", "description": "Digital board with LED problems"},
    {"id": "board_moonboard", "label": "MoonBoard", "description": "Standardized board with online problems"},
    {"id": "board_other", "label": "Other board", "description": "Tension, Grasshopper, or any other training board"},
    {"id": "campus_board", "label": "Campus Board", "description": "Board with rungs for power training"},
    # --- Finger training ---
    {"id": "hangboard", "label": "Hangboard", "description": "Hangboard at the gym"},
    {"id": "loading_pin", "label": "Loading Pin (hangboard alternative)", "description": "Pin for one-arm weighted hangs"},
    {"id": "pinch_block", "label": "Pinch Block", "description": "Block for pinch grip training"},
    # --- Strength equipment ---
    {"id": "pullup_bar", "label": "Pull-up bar", "description": "Fixed bar for pull-ups and hanging exercises"},
    {"id": "weight", "label": "Weight plates", "description": "Free weight plates for loading exercises"},
    {"id": "dumbbell", "label": "Dumbbells", "description": "Dumbbells for strength"},
    {"id": "barbell", "label": "Barbell", "description": "Barbell for heavy strength exercises"},
    {"id": "bench", "label": "Bench", "description": "Bench for press and support exercises"},
    {"id": "cable_machine", "label": "Cable machine", "description": "Cable pulley machine for pulling and pushing exercises"},
    {"id": "leg_press", "label": "Leg press", "description": "Machine for lower body pressing exercises"},
    # --- Accessories ---
    {"id": "resistance_band", "label": "Resistance band", "description": "Elastic band for activation and prehab exercises"},
    {"id": "rings", "label": "Rings", "description": "Gymnastic rings for suspension exercises"},
    {"id": "foam_roller", "label": "Foam Roller", "description": "Roller for self-massage and myofascial release"},
    {"id": "ab_wheel", "label": "Ab Wheel", "description": "Abdominal wheel"},
]

TEST_DESCRIPTIONS = {
    "max_hang_20mm_7s": {
        "label": "Max Hang 20mm — 7 seconds (MVC-7)",
        "description": "Hang on a 20mm edge for 7 seconds with the maximum possible weight (half crimp). Include your body weight in the total.",
        "unit": "kg (total weight = body + added)",
        "example": "E.g.: weigh 77kg + 48kg added = 125kg total",
    },
    "weighted_pullup_1rm": {
        "label": "Weighted Pull-up — 1RM",
        "description": "The maximum weight you can complete one full pull-up with (1 repetition).",
        "unit": "kg (total weight = body + added)",
        "example": "E.g.: weigh 77kg + 45kg = 122kg total",
    },
    "repeater_7_3_max_sets": {
        "label": "Repeater 7/3 — max sets",
        "description": "Hang 7 seconds, rest 3 seconds, repeat to failure. At 60% of your max hang. How many reps can you do?",
        "unit": "number of completed repetitions",
        "example": "E.g.: 24 reps before failure",
    },
}


@router.get("/defaults")
def onboarding_defaults():
    """Return all option lists for onboarding dropdowns/checklists."""
    return {
        "grades": GRADE_ORDER,
        "boulder_grades": BOULDER_GRADE_ORDER,
        "disciplines": ["lead", "boulder", "both"],
        "weakness_options": WEAKNESS_OPTIONS,
        "weakness_options_grouped": {
            "universal": WEAKNESS_OPTIONS_UNIVERSAL,
            "lead": WEAKNESS_OPTIONS_LEAD,
            "boulder": WEAKNESS_OPTIONS_BOULDER,
        },
        "equipment_home": EQUIPMENT_HOME,
        "equipment_gym": EQUIPMENT_GYM,
        "limitation_areas": ["elbow", "finger", "shoulder", "wrist", "knee", "back", "other"],
        "test_descriptions": TEST_DESCRIPTIONS,
        "slots": ["morning", "lunch", "evening"],
        "weekdays": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    }


def _ensure_gym_ids(equipment: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure every gym in equipment.gyms has a stable gym_id."""
    gyms = equipment.get("gyms")
    if gyms:
        for gym in gyms:
            if not gym.get("gym_id"):
                gym["gym_id"] = uuid.uuid4().hex[:8]
    return equipment


def _validate_equipment_keys(equipment: Dict[str, Any]) -> None:
    """Validate that all equipment IDs are known. Raises ValueError with hint on unknown keys."""
    from backend.engine.equipment_utils import KNOWN_EQUIPMENT_KEYS
    all_unknown = []
    home_eq = equipment.get("home") or []
    for key in home_eq:
        if key not in KNOWN_EQUIPMENT_KEYS:
            all_unknown.append(key)
    for gym in (equipment.get("gyms") or []):
        for key in (gym.get("equipment") or []):
            if key not in KNOWN_EQUIPMENT_KEYS:
                all_unknown.append(key)
    if all_unknown:
        # Build a hint for the most common typo
        import difflib
        hints = []
        for uk in sorted(set(all_unknown)):
            close = difflib.get_close_matches(uk, KNOWN_EQUIPMENT_KEYS, n=1, cutoff=0.6)
            hint = f" (did you mean: {close[0]!r}?)" if close else ""
            hints.append(f"{uk!r}{hint}")
        raise ValueError(f"Unknown equipment key(s): {', '.join(hints)}")


# B293 — sanity bounds for the profile. Reject outside, never clamp silently:
# weight/height feed the engine (assessment ratios, hangboard added-load =
# target_total - bodyweight), so a 0 here becomes a corrupted baseline or a
# dangerous prescription downstream.
_PROFILE_BOUNDS: Dict[str, tuple] = {
    "weight_kg": (30, 150),
    "height_cm": (120, 220),
    "age": (1, 99),
}


def _validate_profile(profile: Dict[str, Any]) -> None:
    """Validate onboarding profile fields. Raises ValueError listing every problem."""
    problems = []
    if not str(profile.get("name") or "").strip():
        problems.append("name is required")
    for key, (lo, hi) in _PROFILE_BOUNDS.items():
        raw = profile.get(key)
        try:
            val = float(raw)
        except (TypeError, ValueError):
            val = None
        if val is None or not (lo <= val <= hi):
            problems.append(f"{key} must be between {lo} and {hi}")
    if problems:
        raise ValueError("Invalid profile: " + "; ".join(problems))


def _recovery_multiplier_for_age(age: int | None) -> float:
    """B165b: compute default recovery multiplier from age.

    Thresholds: 1.0× under 50, 1.25× at 50-59, 1.5× at 60+.
    """
    if age is None or age < 50:
        return 1.0
    if age < 60:
        return 1.25
    return 1.5


def _normalize_test_keys(tests: dict) -> dict:
    """Ensure both 7s and legacy 5s keys exist for max hang (D85 compat)."""
    result = dict(tests)
    val = result.get("max_hang_20mm_7s_total_kg") or result.get("max_hang_20mm_5s_total_kg")
    if val is not None:
        result["max_hang_20mm_7s_total_kg"] = val
        result["max_hang_20mm_5s_total_kg"] = val
    return result


def _build_tests_source(tests: dict) -> dict:
    """D214: mark every user-entered test scalar as ``measured``.

    Missing keys are omitted — readers default to ``"estimated"``.
    Dual-writes the 5s/7s hang sibling because they share a single input.
    """
    source: dict = {}
    for key, value in (tests or {}).items():
        if value is None or value == "":
            continue
        source[key] = "measured"
    if (
        "max_hang_20mm_7s_total_kg" in source
        or "max_hang_20mm_5s_total_kg" in source
    ):
        source["max_hang_20mm_7s_total_kg"] = "measured"
        source["max_hang_20mm_5s_total_kg"] = "measured"
    return source


def _build_planning_prefs(
    prefs: dict | None,
    age: int | None,
) -> Dict[str, Any]:
    """Build planning_prefs with D83 recovery multiplier auto-set from age."""
    result = dict(prefs) if prefs else {
        "hard_day_cap_per_week": 3,
        "target_training_days_per_week": 4,
    }
    if "recovery_multiplier" not in result:
        result["recovery_multiplier"] = _recovery_multiplier_for_age(age)
    return result


def _build_user_state_from_onboarding(data: OnboardingData) -> Dict[str, Any]:
    """Convert onboarding form data into a valid user_state dict."""
    profile = data.profile
    state: Dict[str, Any] = {
        "schema_version": "1.5",
        "user": {
            "id": (profile.get("name") or "user").lower().replace(" ", "_"),
            "name": profile.get("name", ""),
            "preferred_name": profile.get("preferred_name", ""),
            "timezone": "Europe/Brussels",
            "units": {"distance": "km", "edge": "mm", "weight": "kg"},
        },
        "body": {
            "weight_kg": profile.get("weight_kg"),
            "height_cm": profile.get("height_cm"),
            "age": profile.get("age"),
        },
        "bodyweight_kg": profile.get("weight_kg"),
        "assessment": {
            "last_assessed": None,
            "body": {
                "weight_kg": profile.get("weight_kg"),
                "height_cm": profile.get("height_cm"),
                "age": profile.get("age"),
            },
            "experience": data.experience,
            "grades": data.grades,
            "tests": _normalize_test_keys(data.tests),
            "tests_source": _build_tests_source(_normalize_test_keys(data.tests)),
            "self_eval": data.self_eval,
            "profile": None,
        },
        "goal": data.goal,
        "planning_prefs": _build_planning_prefs(data.planning_prefs, profile.get("age")),
        "preferences": data.preferences or {
            "finger_training_device": "hangboard",
        },
        "availability": data.availability,
        "equipment": _ensure_gym_ids(data.equipment),  # validation done before this call
        "limitations": {
            "active_flags": [
                f"{lim['area']}_{lim.get('side', 'both')}"
                for lim in data.limitations
            ],
            "details": data.limitations,
        },
        "trips": data.trips,
        "outdoor_spots": [
            {
                "id": f"spot_{i}_{(s.get('name') or 'unnamed').lower().replace(' ', '_')[:12]}",
                "name": s.get("name", ""),
                "discipline": s.get("discipline", "both"),
            }
            for i, s in enumerate(data.outdoor_spots)
        ],
        "macrocycle": None,
        "performance": {
            "current_level": build_current_level(data.grades),
        },
        "baselines": {},
        "recent_sessions": [],
        "recent_sessions_window_days": 14,
        "stimulus_recency": {},
        "fatigue_proxy": {},
        "working_loads": {"entries": [], "rules": {}},
        "tests": {},
        "history_index": {
            "session_log_paths": ["data/logs/sessions_2026.jsonl"],
            "session_log_format": "jsonl",
        },
    }
    return state


# B293 — server-side wizard draft. One draft per user, stored inside
# user_state under ``onboarding_draft``. Lifecycle: written on step
# navigation / debounced edits while the wizard is in flight; wiped by a
# successful /complete (the state is rebuilt from scratch there); ignored
# once a macrocycle exists (a completed user re-visiting the wizard is
# pre-populated from real state, not from a stale draft). Size is a few KB
# per user, bounded by _DRAFT_MAX_BYTES.
_DRAFT_MAX_BYTES = 100_000


@router.get("/draft")
def get_onboarding_draft(user_id: Optional[str] = Depends(get_user_id)):
    """Return the saved wizard draft for this user, or null."""
    state = load_state(user_id)
    return {"draft": state.get("onboarding_draft")}


@router.put("/draft")
def put_onboarding_draft(body: OnboardingDraftEnvelope, user_id: Optional[str] = Depends(get_user_id)):
    """Save (replace wholesale) the wizard draft for this user."""
    import json as _json
    if len(_json.dumps(body.data)) > _DRAFT_MAX_BYTES:
        raise HTTPException(status_code=422, detail="Draft too large")
    state = load_state(user_id)
    if state.get("macrocycle"):
        # Onboarding already completed — never resurrect a wizard draft.
        return {"status": "ignored"}
    state["onboarding_draft"] = {
        "data": body.data,
        "deepest_step": body.deepest_step,
        "saved_at": body.saved_at,
    }
    save_state(state, user_id)
    return {"status": "ok"}


@router.post("/complete")
@limiter.limit("3/minute")
def onboarding_complete(request: Request, data: OnboardingData, user_id: Optional[str] = Depends(get_user_id)):
    """Atomic onboarding: save state + estimate baselines + assessment + macrocycle.

    Always generates a full macrocycle. When test_week_requested=True, sets
    initial_tests_requested flag so that test sessions are injected into week 1.
    """
    # 0. Validate profile + equipment keys before anything else
    try:
        _validate_profile(data.profile)
        _validate_equipment_keys(data.equipment)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 1. Build user state
    # B293: a failed complete must not destroy the server-side wizard draft —
    # the user is still mid-wizard and may reload. A SUCCESSFUL complete wipes
    # it implicitly: the state is rebuilt from scratch without the draft key.
    prev_draft = load_state(user_id).get("onboarding_draft")
    state = _build_user_state_from_onboarding(data)

    # 1b. A233: persist first-touch attribution (sanitized). Written before any
    # save_state so it survives even if assessment/macrocycle generation fails.
    attribution = _sanitize_attribution(data.attribution)
    if attribution:
        from datetime import datetime as _dt, timezone as _tz
        attribution["onboarded_at"] = _dt.now(_tz.utc).isoformat()
        state["attribution"] = attribution

    # 2. Estimate missing baselines from grade/pullup before assessment
    estimate_missing_baselines(state)

    # 3. Compute assessment profile
    assessment = state.get("assessment", {})
    goal = state.get("goal", {})

    discipline = goal.get("discipline", "lead")

    # Derive goal_type from discipline if not explicitly set
    if not goal.get("goal_type"):
        goal["goal_type"] = {
            "lead": "lead_grade",
            "boulder": "boulder_grade",
            "both": "all_round",
        }.get(discipline, "lead_grade")

    # Boulder grades (uppercase Font) must be mapped to lead equivalents
    # for assessment benchmarks which are calibrated to French lead grades.
    # A-NEW-MACRO: extracted into backend.engine.grade_mapping so PUT /api/state
    # can apply the same mapping on discipline switch (D232 finding).
    if not goal.get("current_grade") and assessment.get("grades"):
        grades = assessment["grades"]
        if discipline == "boulder":
            boulder_current = grades.get("boulder_max_rp", "6A")
            goal["current_grade"] = BOULDER_TO_LEAD.get(boulder_current, "6c+")
        else:
            goal["current_grade"] = grades.get("lead_max_rp", "7a")

    # For boulder-only: map target_boulder_grade to lead equivalent for assessment
    if discipline == "boulder":
        boulder_target = goal.get("target_boulder_grade") or goal.get("target_grade", "")
        if boulder_target:
            goal["target_boulder_grade"] = boulder_target  # preserve original
            goal["target_grade"] = BOULDER_TO_LEAD.get(boulder_target, "7a")

    logger.info("goal before assessment: %s", goal)

    try:
        profile = compute_assessment_profile(assessment, goal)
    except Exception as e:
        if prev_draft:
            state["onboarding_draft"] = prev_draft
        save_state(state, user_id)
        raise HTTPException(status_code=422, detail=f"Assessment computation failed: {e}")

    state["assessment"]["profile"] = profile
    state["assessment"]["last_assessed"] = next_monday()

    # 4. If user requested initial tests, set flag (tests injected into week 1)
    if data.test_week_requested:
        state["initial_tests_requested"] = True

    # 5. Generate macrocycle.
    #
    # A-ACTIVATION-TIMING: default start_date is this_monday() so the user
    # can start their first session today or later this week (instead of
    # waiting up to 7 days for next Monday). The planner's B95 guard
    # prevents past-day session placement even when start_date is before
    # today. Threshold-1 fallback: if Week 1 would have zero placeable
    # sessions (e.g. late-Sunday onboarding with only weekday availability),
    # fall back to strict_next_monday so the user gets a proper first week.
    from datetime import date as _date
    try:
        today = _date.today()
        start = ensure_monday(_engine_this_monday(today))
        default_weeks = 10 if discipline == "boulder" else 12
        total_weeks = goal.get("total_weeks", default_weeks)
        # A218: clamp to engine range. min_weeks raised to physical floor sums
        # (lead=11, boulder=8). Max capped at 16 weeks (KB consensus).
        min_weeks = 8 if discipline == "boulder" else 11
        total_weeks = max(min_weeks, min(total_weeks, 16))
        macrocycle = generate_macrocycle(goal, profile, state, start, total_weeks)

        if is_week_one_empty(state, macrocycle, today):
            logger.info(
                "Onboarding fallback: Week 1 would be empty for user_id=%s, "
                "falling back to strict next Monday.", user_id,
            )
            start = ensure_monday(strict_next_monday(today))
            macrocycle = generate_macrocycle(goal, profile, state, start, total_weeks)
    except Exception as e:
        if prev_draft:
            state["onboarding_draft"] = prev_draft
        save_state(state, user_id)
        raise HTTPException(status_code=422, detail=f"Macrocycle generation failed: {e}")

    state["macrocycle"] = macrocycle
    invalidate_week_cache(state)
    save_state(state, user_id)

    # A250: auto-start the 15-day free trial — the user lands on /today with
    # a running trial instead of a paywall. No Stripe involved yet (card only
    # when they subscribe). Never overwrites an existing row, never breaks
    # onboarding on failure (worst case: user hits /subscribe as before).
    trial_started = False
    if user_id:
        try:
            from backend.engine.subscription_guard import start_trial_if_new
            trial_started = start_trial_if_new(user_id)
        except Exception:
            logger.exception("A250 trial auto-start failed for user_id=%s", user_id)

    # Founder alert (fire-and-forget): a new user completed onboarding.
    try:
        from backend.api.notifications import notify
        grades = state.get("assessment", {}).get("grades", {}) or {}
        grade = grades.get("boulder_max_rp") if discipline == "boulder" else grades.get("lead_max_rp")
        notify(
            "🧗 Nuovo iscritto — onboarding completato\n"
            f"Disciplina: {discipline} · grado: {grade or '?'}\n"
            f"Trial auto-start: {'✅' if trial_started else '— (riga esistente o non applicabile)'}\n"
            f"User: {user_id}"
        )
    except Exception:  # never let an alert break onboarding
        pass

    return {"profile": profile, "macrocycle": macrocycle}


@router.post("/start-week")
def onboarding_start_week(body: StartWeekRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Shift macrocycle start_date back so the user begins at week N."""
    from datetime import datetime, timedelta

    state = load_state(user_id)
    mc = state.get("macrocycle")
    if not mc or not mc.get("phases"):
        raise HTTPException(status_code=422, detail="No macrocycle found — complete onboarding first")

    total_weeks = sum(p.get("duration_weeks", 1) for p in mc["phases"])
    offset = min(body.offset_weeks, total_weeks - 1)

    if offset > 0:
        old_start = datetime.strptime(mc["start_date"], "%Y-%m-%d").date()
        new_start = old_start - timedelta(weeks=offset)
        mc["start_date"] = ensure_monday(new_start.isoformat())
        # Recompute end_date from new start + total weeks
        total_weeks = sum(p.get("duration_weeks", 1) for p in mc["phases"])
        mc["end_date"] = (new_start + timedelta(weeks=total_weeks)).isoformat()
        invalidate_week_cache(state)
        save_state(state, user_id)

    return {"status": "ok", "start_date": mc["start_date"], "offset_applied": offset}


