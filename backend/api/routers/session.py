"""Session router — resolve abstract session to concrete exercises."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import REPO_ROOT, get_user_id, load_state, save_state
from backend.api.models import (
    AddExerciseRequest,
    RemoveExerciseRequest,
    SessionResolveRequest,
)
from backend.engine.resolve_session import resolve_session

router = APIRouter(prefix="/api/session", tags=["session"])

SESSIONS_DIR = "backend/catalog/sessions/v1"
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"


def _assert_session_mutable(session: dict, date: str) -> None:
    """Raise 409 if session is completed/skipped (immutability invariant B120)."""
    status = session.get("status")
    if status in ("done", "skipped"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot modify session with status '{status}' on {date}",
        )


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
            user_id=user_id,
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

    # Find the target day (B157: search all weeks, not just weeks[0])
    target_day = None
    for week_block in week_plan.get("weeks", []):
        for day in week_block.get("days", []):
            if day.get("date") == req.date:
                target_day = day
                break
        if target_day:
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
    _assert_session_mutable(session, req.date)

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
    default_prescription = exercise.get("prescription_defaults", {})
    prescription = {**default_prescription, **(req.prescription_override or {})}

    new_instance = {
        "exercise_id": req.exercise_id,
        "exercise_name": exercise.get("name", req.exercise_id),
        "prescription": prescription,
        "source": "user_added",
        "category": exercise.get("category", ""),
        "attributes": exercise.get("attributes") or {},
        "load_model": exercise.get("load_model"),
        "unilateral": bool(exercise.get("unilateral")),
    }

    exercise_instances.append(new_instance)
    resolved_session["exercise_instances"] = exercise_instances

    # Recalculate session_load_score (D151: rescaled ×1.5, cap 85)
    fatigue_map = {e_id: catalog[e_id].get("fatigue_cost", 0) for e_id in catalog}
    raw_fatigue = sum(
        fatigue_map.get(inst.get("exercise_id"), 0)
        for inst in exercise_instances
    )
    resolved["session_load_score"] = round(min(85, raw_fatigue * 1.5))

    # B153b: mark session so _auto_resolve skips re-resolution
    session["_user_edited"] = True
    _persist_week_plan(week_plan, state, user_id)

    return {"week_plan": week_plan}


def _find_session(week_plan: dict, date: str, session_index: int):
    """Locate day, session, resolved data in week_plan. Returns (day, session, resolved, exercise_instances)."""
    # B157: search all weeks, not just weeks[0]
    target_day = None
    for week_block in week_plan.get("weeks", []):
        for day in week_block.get("days", []):
            if day.get("date") == date:
                target_day = day
                break
        if target_day:
            break
    if target_day is None:
        raise HTTPException(status_code=404, detail=f"Date not found in plan: {date}")

    sessions = target_day.get("sessions", [])
    if session_index < 0 or session_index >= len(sessions):
        raise HTTPException(
            status_code=422,
            detail=f"session_index {session_index} out of range (day has {len(sessions)} sessions)",
        )

    session = sessions[session_index]
    resolved = session.get("resolved")
    if not resolved:
        raise HTTPException(status_code=422, detail="Session not yet resolved")

    exercise_instances = resolved.get("resolved_session", {}).get("exercise_instances", [])
    return target_day, session, resolved, exercise_instances


def _recalc_load_score(resolved: dict, exercise_instances: list) -> None:
    """Recalculate session_load_score after exercise list changes."""
    catalog = _load_exercises_catalog()
    fatigue_map = {e_id: catalog[e_id].get("fatigue_cost", 0) for e_id in catalog}
    raw_fatigue = sum(
        fatigue_map.get(inst.get("exercise_id"), 0)
        for inst in exercise_instances
    )
    resolved["session_load_score"] = round(min(85, raw_fatigue * 1.5))


@router.post("/remove-exercise")
def remove_exercise(req: RemoveExerciseRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Remove an exercise from a resolved session."""
    state = load_state(user_id)
    week_plan = req.week_plan
    if not week_plan:
        raise HTTPException(status_code=422, detail="week_plan is required")

    _, session, resolved, exercise_instances = _find_session(week_plan, req.date, req.session_index)
    _assert_session_mutable(session, req.date)

    if req.exercise_index < 0 or req.exercise_index >= len(exercise_instances):
        raise HTTPException(
            status_code=422,
            detail=f"exercise_index {req.exercise_index} out of range (session has {len(exercise_instances)} exercises)",
        )

    if len(exercise_instances) <= 1:
        raise HTTPException(
            status_code=422,
            detail="Cannot remove the last exercise — session must have at least one exercise",
        )

    exercise_instances.pop(req.exercise_index)
    _recalc_load_score(resolved, exercise_instances)
    # B153b: mark session so _auto_resolve skips re-resolution
    session["_user_edited"] = True
    _persist_week_plan(week_plan, state, user_id)

    return {"week_plan": week_plan}


