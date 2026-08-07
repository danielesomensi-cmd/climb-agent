"""Session router — resolve abstract session to concrete exercises."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import REPO_ROOT, get_user_id, load_state, require_active_subscription, save_state
from backend.api.models import (
    AddExerciseRequest,
    RemoveExerciseRequest,
    SessionResolveRequest,
    SurfaceOverrideRequest,
)
from backend.engine.load_score import fatigue_map_by_id, load_score_from_ids
from backend.engine.resolve_session import resolve_session

import logging

logger = logging.getLogger(__name__)

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
    from backend.api.routers.replanner import persist_week_plan as _replanner_persist
    _replanner_persist(updated, state, user_id)


@router.post("/resolve", dependencies=[Depends(require_active_subscription)])
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
            equipment_override=req.equipment_override,
        )
    except Exception as e:
        logger.error("Session resolution failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Session resolution failed. Please try again.")

    return {"resolved": resolved}


@router.post("/add-exercise", dependencies=[Depends(require_active_subscription)])
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

    # B324: mirror the fields resolve_session puts on an instance. This dict used
    # to carry a subset, so a hand-added exercise reached the guided player without
    # `alt_sides` (no RIGHT/LEFT alternation on Copenhagen plank, Pallof press…),
    # without cues/video, and under `exercise_name` — a key no client reads, so
    # the card fell back to the de-underscored id.
    new_instance = {
        "exercise_id": req.exercise_id,
        "name": exercise.get("name", req.exercise_id),
        # Legacy key kept for instances persisted before B324 (and fixtures).
        "exercise_name": exercise.get("name", req.exercise_id),
        "prescription": prescription,
        "source": "user_added",
        "category": exercise.get("category", ""),
        "video_url": exercise.get("video_url") or None,
        "cues": exercise.get("cues") or [],
        "attributes": exercise.get("attributes") or {},
        "equipment_required": list(exercise.get("equipment_required") or []),
        "load_model": exercise.get("load_model"),
        "unilateral": bool(exercise.get("unilateral")),
        "alt_sides": bool(exercise.get("alt_sides")),
    }

    exercise_instances.append(new_instance)
    resolved_session["exercise_instances"] = exercise_instances

    # Recalculate session_load_score (D151: rescaled ×1.5, cap 85 — B312: shared helper)
    resolved["session_load_score"] = load_score_from_ids(
        (inst.get("exercise_id") for inst in exercise_instances),
        fatigue_map_by_id(catalog),
    )

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
    resolved["session_load_score"] = load_score_from_ids(
        (inst.get("exercise_id") for inst in exercise_instances),
        fatigue_map_by_id(_load_exercises_catalog()),
    )


@router.post("/remove-exercise", dependencies=[Depends(require_active_subscription)])
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


# --------------------------------------------------------------------------- #
# B313 — surface override ("Boulder only, today")
# --------------------------------------------------------------------------- #


def _resolve_for_slot(
    session_id: str,
    slot: dict,
    day_date: str,
    state: dict,
    user_id,
    equipment_override: Optional[list] = None,
) -> dict:
    """Resolve `session_id` as if the week router had resolved it for this slot.

    Mirrors the context `_auto_resolve` builds (location, gym, date), so a
    session resolved here is indistinguishable from one resolved by
    GET /api/week — which is what lets both the apply and the revert path go
    through this single function.
    """
    session_path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if not (REPO_ROOT / session_path).exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    resolve_state = deepcopy(state)
    resolve_state["context"] = {
        **resolve_state.get("context", {}),
        "location": slot.get("location", "home"),
        "gym_id": slot.get("gym_id"),
        "target_date": day_date,
        "date": day_date,
    }
    try:
        return resolve_session(
            repo_root=str(REPO_ROOT),
            session_path=session_path,
            templates_dir=TEMPLATES_DIR,
            exercises_path=EXERCISES_PATH,
            out_path="",
            user_state_override=resolve_state,
            write_output=False,
            user_id=user_id,
            phase=slot.get("phase_id"),
            equipment_override=equipment_override,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Surface override resolution failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Session resolution failed. Please try again.")


def _apply_slot_meta(slot: dict, session_id: str) -> None:
    """Realign the planner-owned fields of a slot after a session_id swap.

    A slot carries `intensity`, `estimated_load_score` and `tags` alongside the
    session_id; leaving them pointing at the replaced session would give a
    boulder session the rope session's hard/finger flags — which drive the 48h
    finger gap and the report's hard-day count. Same realignment the replanner
    does when it substitutes a session.
    """
    from backend.engine.planner_v2 import _INTENSITY_TO_LOAD, _SESSION_META

    meta = _SESSION_META.get(session_id)
    if not meta:
        return
    slot["intensity"] = meta["intensity"]
    slot["estimated_load_score"] = _INTENSITY_TO_LOAD.get(meta["intensity"], 40)
    tags = {"hard": meta["hard"], "finger": meta["finger"]}
    if meta.get("test"):
        tags["test"] = True
    slot["tags"] = tags


def _boulder_equipment_override(slot: dict, state: dict, session_id: str) -> list:
    """Available equipment for this slot minus the rope wall.

    Server-side twin of what the A210 client used to compute: it asks the
    resolver's own `get_location_equipment` instead of re-deriving equipment in
    TypeScript, so there is one definition of "what this user has at this gym".
    """
    from backend.engine.resolve_session import get_location_equipment, norm_str

    resolve_state = deepcopy(state)
    resolve_state["context"] = {
        **resolve_state.get("context", {}),
        "location": slot.get("location", "home"),
        "gym_id": slot.get("gym_id"),
    }
    _, equipment = get_location_equipment(resolve_state, {"id": session_id})
    return [e for e in equipment if norm_str(e) != "gym_routes"]


def _has_boulder_wall(slot: dict, state: dict, session_id: str) -> bool:
    """Does this location actually have a boulder wall?

    Checked up front rather than inferred from the resolved output: without it
    the resolver quietly falls back to whatever else is around (hangboard moving
    hangs, for one) and returns a perfectly valid session that is not bouldering.
    """
    from backend.engine.equipment_utils import expand_equipment
    from backend.engine.resolve_session import get_location_equipment

    resolve_state = deepcopy(state)
    resolve_state["context"] = {
        **resolve_state.get("context", {}),
        "location": slot.get("location", "home"),
        "gym_id": slot.get("gym_id"),
    }
    _, equipment = get_location_equipment(resolve_state, {"id": session_id})
    return "gym_boulder" in set(expand_equipment(equipment))


def _rope_free(resolved: dict) -> bool:
    """No exercise in the adapted session still needs the rope wall.

    Removing the rope from the available equipment normally guarantees this, but
    explicitly pinned exercises bypass the P0 filters — so the promise made to
    the user ("boulder only") is verified rather than assumed.
    """
    rs = resolved.get("resolved_session") or {}
    return not any(
        "gym_routes" in (inst.get("equipment_required") or [])
        for inst in rs.get("exercise_instances") or []
    )


def _primary_block_survived(resolved: dict) -> bool:
    """The adapted session still trains what it was there to train.

    Warm-up, core and cool-down resolve almost anywhere, so "has exercises" is
    not enough: without a boulder wall the session would come back as a
    stretching routine wearing the name of a climbing session.
    """
    blocks = (resolved.get("resolved_session") or {}).get("blocks") or []
    primaries = [b for b in blocks if b.get("type") == "primary"]
    if not primaries:
        return True  # nothing declared primary — no promise to keep
    return any(b.get("status") == "selected" for b in primaries)


@router.post("/surface-override", dependencies=[Depends(require_active_subscription)])
def surface_override(req: SurfaceOverrideRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Adapt a rope-dependent session to the boulder wall for this day only (B313).

    A210 shipped this as React state that never left the card: the preview
    switched to boulder while the guided player, the feedback payload and the
    load all kept reading the planned rope session. The override now lands on
    the slot itself, so every consumer sees one session — the one the user is
    actually going to do.

    Two ways to get there, chosen here and not in the client:
      - **swap**: the session declares a `boulder_fallback` in the catalog →
        resolve that session instead, and move the slot onto it.
      - **equipment**: no declared fallback → re-resolve the same session with
        the rope wall removed from the available equipment.

    `surface: null` reverts: the slot goes back to its planned session_id and is
    re-resolved through the same path, so the response is immediately renderable
    instead of leaving the card empty until the next week fetch.
    """
    state = load_state(user_id)
    week_plan = req.week_plan
    if not week_plan:
        raise HTTPException(status_code=422, detail="week_plan is required")

    day, session, resolved, _ = _find_session(week_plan, req.date, req.session_index)
    _assert_session_mutable(session, req.date)

    if session.get("is_custom"):
        raise HTTPException(
            status_code=422,
            detail="Custom sessions have no planned surface to override — edit the session instead",
        )

    if req.surface is None:
        planned_id = session.get("surface_override_from")
        if not planned_id:
            # Nothing to revert — idempotent, mirrors mark_planned's no-op.
            return {"week_plan": week_plan}
        session["session_id"] = planned_id
        session["resolved"] = _resolve_for_slot(
            planned_id, session, req.date, state, user_id
        )
        _apply_slot_meta(session, planned_id)
        for key in ("surface_override", "surface_override_from", "_user_edited"):
            session.pop(key, None)
        _persist_week_plan(week_plan, state, user_id)
        return {"week_plan": week_plan}

    if session.get("surface_override"):
        # Already adapted — applying twice must not lose the planned session_id.
        return {"week_plan": week_plan}

    planned_id = session.get("session_id")
    fallback_id = ((resolved or {}).get("session") or {}).get("boulder_fallback")
    target_id = fallback_id or planned_id

    if not _has_boulder_wall(session, state, target_id):
        raise HTTPException(
            status_code=422,
            detail="No boulder wall available at this location",
        )

    # One resolve, one guarantee. The catalog's `boulder_fallback` chooses WHICH
    # session; taking the rope out of the available equipment is what makes it
    # boulder — and it is applied in both cases.
    #
    # Not applying it to the swap was the first version of this endpoint, and it
    # was wrong: at a gym with both walls, `boulder_circuit_gym` happily selects
    # `route_on_the_minute` (a rope exercise) for its primary block, so the user
    # asked for boulder and got routes under a different session name.
    new_resolved = _resolve_for_slot(
        target_id,
        session,
        req.date,
        state,
        user_id,
        equipment_override=_boulder_equipment_override(session, state, target_id),
    )

    instances = (new_resolved.get("resolved_session") or {}).get("exercise_instances") or []
    if not instances or not _primary_block_survived(new_resolved) or not _rope_free(new_resolved):
        # Better an honest failure than a session that is boulder in name only:
        # the user keeps the rope session and can pick something else.
        raise HTTPException(
            status_code=422,
            detail="No boulder alternative available for this session at this location",
        )

    if fallback_id:
        session["session_id"] = fallback_id
        _apply_slot_meta(session, fallback_id)

    session["resolved"] = new_resolved
    session["surface_override"] = "boulder"
    session["surface_override_from"] = planned_id
    # B153b: keep _auto_resolve from resolving the rope session back on top.
    session["_user_edited"] = True
    _persist_week_plan(week_plan, state, user_id)

    return {"week_plan": week_plan}


