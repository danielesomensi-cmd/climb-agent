"""Session router — resolve abstract session to concrete exercises."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import DATA_DIR, REPO_ROOT, USERS_DIR, get_user_id, load_state, save_state
from backend.api.models import AddExerciseRequest, SessionResolveRequest
from backend.engine.resolve_session import resolve_session

router = APIRouter(prefix="/api/session", tags=["session"])

SESSIONS_DIR = "backend/catalog/sessions/v1"
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"


def _load_exercises_catalog() -> dict:
    """Load the full exercises catalog and return {id: exercise_dict}."""
    path = REPO_ROOT / EXERCISES_PATH
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {e["id"]: e for e in data.get("exercises", [])}


def _persist_week_plan(updated: dict, state: dict, user_id) -> None:
    """Save modified plan to per-week cache and (if current) to legacy cache."""
    from backend.api.routers.replanner import _persist_week_plan as _replanner_persist
    _replanner_persist(updated, state, user_id)


@router.post("/resolve")
def resolve(req: SessionResolveRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Resolve a session_id into concrete exercises."""
    session_path = os.path.join(SESSIONS_DIR, f"{req.session_id}.json")
    full_path = REPO_ROOT / session_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {req.session_id}")

    state = load_state(user_id)
    if req.context:
        state["context"] = {**state.get("context", {}), **req.context}

    try:
        resolved = resolve_session(
            repo_root=str(REPO_ROOT),
            session_path=session_path,
            templates_dir=TEMPLATES_DIR,
            exercises_path=EXERCISES_PATH,
            out_path="",  # not writing to disk
            user_state_override=state,
            write_output=False,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session resolution failed: {e}")

    return {"resolved": resolved}


@router.post("/add-exercise")
def add_exercise(req: AddExerciseRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Add an exercise to an already-resolved session in the week plan."""
    state = load_state(user_id)
    week_plan = req.week_plan
    if not week_plan:
        raise HTTPException(status_code=422, detail="week_plan is required")

    # Find the target day
    target_day = None
    for day in week_plan.get("weeks", [{}])[0].get("days", []):
        if day.get("date") == req.date:
            target_day = day
            break
    if target_day is None:
        raise HTTPException(status_code=404, detail=f"Date not found in plan: {req.date}")

    sessions = target_day.get("sessions", [])
    if req.session_index < 0 or req.session_index >= len(sessions):
        raise HTTPException(
            status_code=422,
            detail=f"session_index {req.session_index} out of range (day has {len(sessions)} sessions)",
        )

    session = sessions[req.session_index]
    resolved = session.get("resolved")
    if not resolved:
        raise HTTPException(status_code=422, detail="Session not yet resolved")

    resolved_session = resolved.get("resolved_session", {})
    exercise_instances = resolved_session.get("exercise_instances", [])

    # Load exercise from catalog
    catalog = _load_exercises_catalog()
    exercise = catalog.get(req.exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail=f"Exercise not found: {req.exercise_id}")

    # Build exercise instance with defaults from catalog or override
    default_prescription = exercise.get("default_prescription", {})
    prescription = {**default_prescription, **(req.prescription_override or {})}

    new_instance = {
        "exercise_id": req.exercise_id,
        "exercise_name": exercise.get("name", req.exercise_id),
        "prescription": prescription,
        "source": "user_added",
    }

    exercise_instances.append(new_instance)
    resolved_session["exercise_instances"] = exercise_instances

    # Recalculate session_load_score
    fatigue_map = {e_id: catalog[e_id].get("fatigue_cost", 0) for e_id in catalog}
    resolved["session_load_score"] = sum(
        fatigue_map.get(inst.get("exercise_id"), 0)
        for inst in exercise_instances
    )

    _persist_week_plan(week_plan, state, user_id)

    return {"week_plan": week_plan}
