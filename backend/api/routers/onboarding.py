"""Onboarding router — defaults and complete flow."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend.api.deps import REPO_ROOT, load_state, next_monday, save_state
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
    {"id": "pump_too_early", "label": "Pompo troppo presto", "description": "I miei avambracci si gonfiano prima che la forza ceda"},
    {"id": "fingers_give_out", "label": "Le dita cedono", "description": "La forza delle dita è il mio limite principale"},
    {"id": "cant_hold_hard_moves", "label": "Non tengo i movimenti duri", "description": "Mi manca forza/potenza sui singoli movimenti crux"},
    {"id": "technique_errors", "label": "Errori di tecnica", "description": "Cado per posizione del corpo o movimenti sbagliati"},
    {"id": "cant_read_routes", "label": "Non leggo le vie", "description": "Fatico a trovare la beta e leggere le sequenze"},
    {"id": "cant_manage_rests", "label": "Non gestisco i riposi", "description": "Non recupero bene sulle soste"},
    {"id": "lack_power", "label": "Manca potenza esplosiva", "description": "Movimenti dinamici e lanci sono il mio punto debole"},
    {"id": "injury_prone", "label": "Infortuni frequenti", "description": "Problemi fisici limitano il mio allenamento"},
]

EQUIPMENT_HOME = [
    {"id": "hangboard", "label": "Hangboard / Trave", "description": "Trave da allenamento per le dita"},
    {"id": "pullup_bar", "label": "Sbarra trazioni", "description": "Barra fissa per trazioni e esercizi sospesi"},
    {"id": "band", "label": "Elastico assistenza", "description": "Banda elastica per assistenza o resistenza"},
    {"id": "dumbbell", "label": "Manubri", "description": "Manubri per esercizi di forza"},
    {"id": "kettlebell", "label": "Kettlebell", "description": "Peso a sfera per esercizi funzionali"},
    {"id": "ab_wheel", "label": "Ab Wheel", "description": "Ruota per addominali"},
    {"id": "rings", "label": "Anelli", "description": "Anelli da ginnastica per esercizi sospesi"},
    {"id": "foam_roller", "label": "Foam Roller", "description": "Rullo per automassaggio e rilascio miofasciale"},
    {"id": "resistance_band", "label": "Banda elastica", "description": "Banda elastica per esercizi di attivazione e prehab"},
    {"id": "pinch_block", "label": "Pinch Block", "description": "Blocco per allenamento presa pinch"},
]

EQUIPMENT_GYM = [
    {"id": "gym_boulder", "label": "Area boulder", "description": "Palestra con settore boulder e problemi settati"},
    {"id": "gym_routes", "label": "Vie con corda", "description": "Muro per arrampicata con corda"},
    {"id": "spraywall", "label": "Spraywall", "description": "Muro con prese fisse per boulder personalizzati"},
    {"id": "board_kilter", "label": "Kilter Board", "description": "Board digitale con problemi LED"},
    {"id": "board_moonboard", "label": "MoonBoard", "description": "Board standardizzato con problemi online"},
    {"id": "campus_board", "label": "Campus Board", "description": "Pannello con listelli per power training"},
    {"id": "hangboard", "label": "Hangboard", "description": "Trave nella palestra"},
    {"id": "dumbbell", "label": "Manubri", "description": "Manubri per forza"},
    {"id": "barbell", "label": "Bilanciere", "description": "Bilanciere per esercizi di forza pesante"},
    {"id": "bench", "label": "Panca", "description": "Panca per esercizi di spinta e supporto"},
]

TEST_DESCRIPTIONS = {
    "max_hang_20mm_5s": {
        "label": "Max Hang 20mm — 5 secondi",
        "description": "Appendi a un listello da 20mm per 5 secondi con il massimo peso possibile (half crimp). Includi il tuo peso corporeo nel totale.",
        "unit": "kg (peso totale = corpo + zavorra)",
        "example": "Es: pesi 77kg + 48kg zavorra = 125kg totale",
    },
    "weighted_pullup_1rm": {
        "label": "Weighted Pull-up — 1RM",
        "description": "Il massimo peso con cui riesci a fare una trazione completa (1 ripetizione).",
        "unit": "kg (peso totale = corpo + zavorra)",
        "example": "Es: pesi 77kg + 45kg = 122kg totale",
    },
    "repeater_7_3_max_sets": {
        "label": "Repeater 7/3 — serie massime",
        "description": "Appendi 7 secondi, riposa 3 secondi, ripeti fino a cedimento. Al 60% del tuo max hang. Quante ripetizioni riesci a fare?",
        "unit": "numero di ripetizioni completate",
        "example": "Es: 24 ripetizioni prima di cedimento",
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
    save_state(state)

    return {"profile": profile, "macrocycle": macrocycle}
