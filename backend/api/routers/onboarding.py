"""Onboarding router — defaults and complete flow."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend.api.deps import REPO_ROOT, invalidate_week_cache, load_state, next_monday, save_state
from backend.api.models import OnboardingData
from backend.engine.assessment_v1 import GRADE_ORDER, compute_assessment_profile
from backend.engine.macrocycle_v1 import generate_macrocycle

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

# Boulder grades (Fontainebleau)
BOULDER_GRADE_ORDER = [
    "5A", "5B", "5C",
    "6A", "6A+", "6B", "6B+", "6C", "6C+",
    "7A", "7A+", "7B", "7B+", "7C", "7C+",
    "8A", "8A+", "8B", "8B+", "8C", "8C+",
]

WEAKNESS_OPTIONS = [
    {"id": "pump_too_early", "label": "I pump out too early", "description": "My forearms pump before my strength gives out"},
    {"id": "fingers_give_out", "label": "My fingers give out", "description": "Finger strength is my main limiter"},
    {"id": "cant_hold_hard_moves", "label": "Can't hold hard moves", "description": "I lack strength/power on single crux moves"},
    {"id": "technique_errors", "label": "Technique errors", "description": "I fall due to body position or movement mistakes"},
    {"id": "cant_read_routes", "label": "Can't read routes", "description": "I struggle to find the beta and read sequences"},
    {"id": "cant_manage_rests", "label": "Can't manage rests", "description": "I don't recover well on rest stances"},
    {"id": "lack_power", "label": "Lack explosive power", "description": "Dynamic moves and dynos are my weak point"},
    {"id": "injury_prone", "label": "Frequent injuries", "description": "Physical issues limit my training"},
]

EQUIPMENT_HOME = [
    {"id": "hangboard", "label": "Hangboard", "description": "Finger training board"},
    {"id": "pullup_bar", "label": "Pull-up bar", "description": "Fixed bar for pull-ups and hanging exercises"},
    {"id": "band", "label": "Assistance band", "description": "Elastic band for assistance or resistance"},
    {"id": "dumbbell", "label": "Dumbbells", "description": "Dumbbells for strength exercises"},
    {"id": "kettlebell", "label": "Kettlebell", "description": "Kettlebell for functional exercises"},
    {"id": "ab_wheel", "label": "Ab Wheel", "description": "Abdominal wheel"},
    {"id": "rings", "label": "Rings", "description": "Gymnastic rings for suspension exercises"},
    {"id": "foam_roller", "label": "Foam Roller", "description": "Roller for self-massage and myofascial release"},
    {"id": "resistance_band", "label": "Resistance band", "description": "Elastic band for activation and prehab exercises"},
    {"id": "pinch_block", "label": "Pinch Block", "description": "Block for pinch grip training"},
]

EQUIPMENT_GYM = [
    {"id": "gym_boulder", "label": "Bouldering area", "description": "Gym with bouldering sector and set problems"},
    {"id": "gym_routes", "label": "Lead / Top-rope walls", "description": "Wall for roped climbing"},
    {"id": "spraywall", "label": "Spraywall", "description": "Wall with fixed holds for custom boulders"},
    {"id": "board_kilter", "label": "Kilter Board", "description": "Digital board with LED problems"},
    {"id": "board_moonboard", "label": "MoonBoard", "description": "Standardized board with online problems"},
    {"id": "campus_board", "label": "Campus Board", "description": "Board with rungs for power training"},
    {"id": "hangboard", "label": "Hangboard", "description": "Hangboard at the gym"},
    {"id": "dumbbell", "label": "Dumbbells", "description": "Dumbbells for strength"},
    {"id": "barbell", "label": "Barbell", "description": "Barbell for heavy strength exercises"},
    {"id": "bench", "label": "Bench", "description": "Bench for press and support exercises"},
    {"id": "cable_machine", "label": "Cable machine", "description": "Cable pulley machine for pulling and pushing exercises"},
    {"id": "leg_press", "label": "Leg press", "description": "Machine for lower body pressing exercises"},
]

TEST_DESCRIPTIONS = {
    "max_hang_20mm_5s": {
        "label": "Max Hang 20mm — 5 seconds",
        "description": "Hang on a 20mm edge for 5 seconds with the maximum possible weight (half crimp). Include your body weight in the total.",
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
        "disciplines": ["lead", "boulder"],
        "weakness_options": WEAKNESS_OPTIONS,
        "equipment_home": EQUIPMENT_HOME,
        "equipment_gym": EQUIPMENT_GYM,
        "limitation_areas": ["elbow", "shoulder", "wrist", "knee", "back"],
        "test_descriptions": TEST_DESCRIPTIONS,
        "slots": ["morning", "lunch", "evening"],
        "weekdays": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    }


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
            "body_fat_pct": profile.get("body_fat_pct"),
        },
        "bodyweight_kg": profile.get("weight_kg"),
        "assessment": {
            "last_assessed": None,
            "body": {
                "weight_kg": profile.get("weight_kg"),
                "height_cm": profile.get("height_cm"),
                "body_fat_pct": profile.get("body_fat_pct"),
            },
            "experience": data.experience,
            "grades": data.grades,
            "tests": data.tests,
            "self_eval": data.self_eval,
            "profile": None,
        },
        "goal": data.goal,
        "planning_prefs": data.planning_prefs or {
            "hard_day_cap_per_week": 3,
            "target_training_days_per_week": 4,
        },
        "availability": data.availability,
        "equipment": data.equipment,
        "limitations": {
            "active_flags": [
                f"{lim['area']}_{lim.get('side', 'both')}"
                for lim in data.limitations
            ],
            "details": data.limitations,
        },
        "trips": data.trips,
        "macrocycle": None,
        "performance": {
            "current_level": _build_current_level(data.grades),
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


def _build_current_level(grades: Dict[str, Any]) -> Dict[str, Any]:
    """Build performance.current_level from onboarding grades."""
    level: Dict[str, Any] = {"updated_at": None}
    if grades.get("lead_max_rp") or grades.get("lead_max_os"):
        level["sport"] = {}
        if grades.get("lead_max_rp"):
            level["sport"]["worked"] = {"grade": grades["lead_max_rp"]}
        if grades.get("lead_max_os"):
            level["sport"]["onsight"] = {"grade": grades["lead_max_os"]}
    if grades.get("boulder_max_rp") or grades.get("boulder_max_os"):
        level["boulder"] = {}
        if grades.get("boulder_max_rp"):
            level["boulder"]["worked"] = {"grade": grades["boulder_max_rp"]}
        if grades.get("boulder_max_os"):
            level["boulder"]["onsight"] = {"grade": grades["boulder_max_os"]}
    return level


@router.post("/complete")
def onboarding_complete(data: OnboardingData):
    """Atomic onboarding: save state + compute assessment + generate macrocycle."""
    # 1. Build and save user state
    state = _build_user_state_from_onboarding(data)
    save_state(state)

    # 2. Compute assessment profile
    assessment = state.get("assessment", {})
    goal = state.get("goal", {})

    # Ensure goal has current_grade from grades
    if not goal.get("current_grade") and assessment.get("grades"):
        grades = assessment["grades"]
        discipline = goal.get("discipline", "lead")
        if discipline == "lead":
            goal["current_grade"] = grades.get("lead_max_rp", "7a")
        else:
            goal["current_grade"] = grades.get("boulder_max_rp", "6A")

    try:
        profile = compute_assessment_profile(assessment, goal)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Assessment computation failed: {e}")

    state["assessment"]["profile"] = profile
    state["assessment"]["last_assessed"] = next_monday().replace(
        next_monday()[:4], next_monday()[:4]  # keep as-is
    )

    # 3. Generate macrocycle
    try:
        start = next_monday()
        macrocycle = generate_macrocycle(goal, profile, state, start, 12)
    except Exception as e:
        # Save state with profile even if macrocycle fails
        save_state(state)
        raise HTTPException(status_code=422, detail=f"Macrocycle generation failed: {e}")

    state["macrocycle"] = macrocycle
    invalidate_week_cache(state)
    save_state(state)

    return {"profile": profile, "macrocycle": macrocycle}
