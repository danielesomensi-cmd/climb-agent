"""Free climbing session router — surfaces, presets, start/log/finish, history."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import get_user_id, load_state, require_active_subscription, save_state, REPO_ROOT
from backend.api.models import (
    FreeSessionFinishRequest,
    FreeSessionLogClimbRequest,
    FreeSessionStartRequest,
)
from backend.engine.free_session import (
    SURFACES,
    SURFACE_IDS,
    VALID_CLIMB_STYLES,
    VALID_CONTEXTS,
    VALID_FEELS,
    VALID_SESSION_MODES,
    compute_free_session_load,
    compute_summary,
    get_phase_for_date,
    get_user_gyms,
    get_user_max_grade,
    is_lead_surface,
    normalize_grade,
    offset_grade,
    validate_climb,
)

router = APIRouter(prefix="/api/free-session", tags=["free-session"])

# ── Catalog loaders ──────────────────────────────────────────────────────

_PRESETS_CACHE: Optional[Dict[str, Any]] = None
_TIPS_CACHE: Optional[Dict[str, Any]] = None


def _load_presets() -> Dict[str, Any]:
    global _PRESETS_CACHE
    if _PRESETS_CACHE is None:
        path = REPO_ROOT / "backend" / "catalog" / "free_session_presets" / "v1" / "presets.json"
        with open(path) as f:
            _PRESETS_CACHE = json.load(f)
    return _PRESETS_CACHE


def _load_tips() -> Dict[str, Any]:
    global _TIPS_CACHE
    if _TIPS_CACHE is None:
        path = REPO_ROOT / "backend" / "catalog" / "free_session_presets" / "v1" / "phase_tips.json"
        with open(path) as f:
            _TIPS_CACHE = json.load(f)
    return _TIPS_CACHE


def _get_presets_for_surface(surface: str) -> List[Dict[str, Any]]:
    """Return preset list for a surface (boulder presets for boulder surfaces, lead for lead)."""
    presets = _load_presets()
    if is_lead_surface(surface):
        return presets.get("lead", [])
    return presets.get("boulder", [])


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/surfaces")
def get_surfaces(user_id: Optional[str] = Depends(get_user_id)):
    """Return all available surfaces + user's saved gyms for the picker."""
    state = load_state(user_id)
    gyms = get_user_gyms(state)
    return {"surfaces": SURFACES, "gyms": gyms}


@router.get("/presets")
def get_presets(
    surface: str = Query(..., description="Surface id"),
    user_id: Optional[str] = Depends(get_user_id),
):
    """Return presets for a surface, personalized with user's grades and current phase."""
    if surface not in SURFACE_IDS:
        raise HTTPException(status_code=400, detail=f"Invalid surface: {surface}")

    state = load_state(user_id)
    today_str = datetime.now().strftime("%Y-%m-%d")
    phase_id = get_phase_for_date(state, today_str)
    user_max = get_user_max_grade(state, surface)

    presets_raw = _get_presets_for_surface(surface)
    tips = _load_tips()

    result = []
    for p in presets_raw:
        # Compute target grade from user max + offset
        target_grade = None
        if user_max:
            target_grade = offset_grade(user_max, p.get("grade_offset", 0))

        # Phase compatibility for current phase
        compat = p.get("phase_compatibility", {}).get(phase_id, "caution")

        # Phase tip
        template_tips = tips.get("template_tips", {}).get(phase_id, {})
        tip = template_tips.get(p["id"], "")

        result.append({
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "icon": p["icon"],
            "target_grade": target_grade,
            "rest_seconds": p["rest_seconds"],
            "target_climbs": f"{p['target_climbs_min']}-{p['target_climbs_max']}",
            "duration": f"{p['duration_min']}-{p['duration_max']} min",
            "phase_compatibility": compat,
            "phase_tip": tip,
        })

    # Free mode tip
    free_tip = tips.get("free_mode_tips", {}).get(phase_id, "")

    return {"presets": result, "free_mode_tip": free_tip, "phase_id": phase_id}


@router.post("/start", dependencies=[Depends(require_active_subscription)])
def start_session(
    req: FreeSessionStartRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Create a new free climbing session."""
    # Validate enums
    if req.surface not in SURFACE_IDS:
        raise HTTPException(status_code=400, detail=f"Invalid surface: {req.surface}")
    if req.context not in VALID_CONTEXTS:
        raise HTTPException(status_code=400, detail=f"Invalid context: {req.context}")
    if req.session_mode not in VALID_SESSION_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid session_mode: {req.session_mode}")
    if req.session_mode == "template" and not req.preset_id:
        raise HTTPException(status_code=400, detail="preset_id required for template mode")
    if req.session_mode == "circuit" and req.surface != "circuit_core":
        raise HTTPException(status_code=400, detail="circuit mode requires circuit_core surface")

    state = load_state(user_id)
    free_sessions = state.setdefault("free_sessions", [])

    # Generate session ID
    existing_today = [s for s in free_sessions if s.get("date") == req.date]
    seq = len(existing_today) + 1
    session_id = f"free_{req.date.replace('-', '')}_{seq}"

    # Phase
    phase_id = get_phase_for_date(state, req.date)

    # Get tip + target grade
    tips = _load_tips()
    tip = None
    target_grade = None
    rest_seconds = None

    if req.session_mode == "circuit":
        # Circuit sessions don't need presets, grades, or rest
        pass
    elif req.session_mode == "template" and req.preset_id:
        template_tips = tips.get("template_tips", {}).get(phase_id, {})
        tip = template_tips.get(req.preset_id, "")

        # Find preset to get grade offset and rest
        presets = _get_presets_for_surface(req.surface)
        preset = next((p for p in presets if p["id"] == req.preset_id), None)
        if preset:
            user_max = get_user_max_grade(state, req.surface)
            if user_max:
                target_grade = offset_grade(user_max, preset.get("grade_offset", 0))
            rest_seconds = preset.get("rest_seconds")
    else:
        free_tips = tips.get("free_mode_tips", {})
        tip = free_tips.get(phase_id, "")

    now = datetime.now(timezone.utc).isoformat()

    session: Dict[str, Any] = {
        "id": session_id,
        "date": req.date,
        "context": req.context,
        "session_mode": req.session_mode,
        "preset_id": req.preset_id,
        "surface": req.surface,
        "gym_name": req.gym_name,
        "phase_at_time": phase_id,
        "started_at": now,
        "finished_at": None,
        "duration_minutes": None,
        "climbs": [],
        "summary": None,
        "overall_feel": None,
        "notes": None,
        "load_score": None,
    }

    free_sessions.append(session)

    # If replacement context, mark planned session as skipped
    if req.context == "replacement":
        _mark_planned_session_skipped(state, req.date)

    save_state(state, user_id)

    return {
        "session_id": session_id,
        "phase_at_time": phase_id,
        "tip": tip,
        "target_grade": target_grade,
        "rest_seconds": rest_seconds,
    }


@router.post("/{session_id}/log-climb", dependencies=[Depends(require_active_subscription)])
def log_climb(
    session_id: str,
    req: FreeSessionLogClimbRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Add a climb to an active free session."""
    state = load_state(user_id)
    session = _find_session(state, session_id)

    if session.get("finished_at") is not None:
        raise HTTPException(status_code=400, detail="Session already finished")

    climb: Dict[str, Any] = {
        "grade": req.grade,
        "status": req.status,
        "attempts": req.attempts,
        "style": req.style,
        "topped": req.topped,
        "notes": req.notes,
    }

    error = validate_climb(climb, session["surface"])
    if error:
        raise HTTPException(status_code=422, detail=error)

    # Normalize grade to uppercase
    climb["grade"] = normalize_grade(req.grade) or req.grade

    now = datetime.now(timezone.utc).isoformat()
    index = len(session.get("climbs", [])) + 1
    climb["index"] = index
    climb["logged_at"] = now

    session.setdefault("climbs", []).append(climb)
    save_state(state, user_id)

    return {"index": index, "logged_at": now}


@router.post("/{session_id}/finish", dependencies=[Depends(require_active_subscription)])
def finish_session(
    session_id: str,
    req: FreeSessionFinishRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Close a free session, compute summary and load."""
    if req.overall_feel is not None and req.overall_feel not in VALID_FEELS:
        raise HTTPException(status_code=400, detail=f"Invalid overall_feel: {req.overall_feel}")

    state = load_state(user_id)
    session = _find_session(state, session_id)

    if session.get("finished_at") is not None:
        raise HTTPException(status_code=400, detail="Session already finished")

    now = datetime.now(timezone.utc)
    session["finished_at"] = now.isoformat()

    # Duration
    try:
        started = datetime.fromisoformat(session["started_at"])
        session["duration_minutes"] = round((now - started).total_seconds() / 60)
    except (ValueError, TypeError):
        session["duration_minutes"] = None

    session["overall_feel"] = req.overall_feel
    session["notes"] = req.notes

    # Circuit sessions: simple load formula
    if session.get("session_mode") == "circuit":
        circuit = req.circuit
        if circuit:
            session["circuit"] = circuit
            completed = circuit.get("completed_exercises", 0)
            load = round(completed * 0.5, 1)
        else:
            load = 0.0
        session["load_score"] = load
        session["summary"] = compute_summary([])
    else:
        # Summary
        climbs = session.get("climbs", [])
        session["summary"] = compute_summary(climbs)

        # Load
        user_max = get_user_max_grade(state, session["surface"])
        if user_max and climbs:
            session["load_score"] = compute_free_session_load(climbs, user_max)
        else:
            session["load_score"] = 0.0

    save_state(state, user_id)

    return {
        "summary": session["summary"],
        "duration_minutes": session["duration_minutes"],
        "load_score": session["load_score"],
    }


@router.get("/history")
def get_history(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    user_id: Optional[str] = Depends(get_user_id),
):
    """Return free sessions for a given date."""
    state = load_state(user_id)
    free_sessions = state.get("free_sessions", [])
    matching = [s for s in free_sessions if s.get("date") == date]

    # Return a lightweight view for history
    result = []
    for s in matching:
        result.append({
            "id": s["id"],
            "surface": s.get("surface"),
            "gym_name": s.get("gym_name"),
            "context": s.get("context"),
            "session_mode": s.get("session_mode"),
            "preset_id": s.get("preset_id"),
            "duration_minutes": s.get("duration_minutes"),
            "summary": s.get("summary"),
            "overall_feel": s.get("overall_feel"),
            "started_at": s.get("started_at"),
            "finished_at": s.get("finished_at"),
            "load_score": s.get("load_score"),
        })

    return {"sessions": result}


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Delete a free session by ID."""
    state = load_state(user_id)
    free_sessions = state.get("free_sessions", [])
    new_sessions = [s for s in free_sessions if s.get("id") != session_id]

    if len(new_sessions) == len(free_sessions):
        raise HTTPException(status_code=404, detail=f"Free session '{session_id}' not found")

    state["free_sessions"] = new_sessions
    save_state(state, user_id)
    return {"status": "ok"}


# ── Helpers ──────────────────────────────────────────────────────────────

def _find_session(state: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    """Find a free session by ID. Raises 404 if not found."""
    free_sessions = state.get("free_sessions", [])
    for s in free_sessions:
        if s.get("id") == session_id:
            return s
    raise HTTPException(status_code=404, detail=f"Free session '{session_id}' not found")


def _mark_planned_session_skipped(state: Dict[str, Any], date: str) -> None:
    """Mark the first non-done planned session on this date as skipped."""
    week_plan = state.get("current_week_plan")
    if not week_plan:
        return

    for week in week_plan.get("weeks", []):
        for day in week.get("days", []):
            if day.get("date") == date:
                for sess in day.get("sessions", []):
                    if sess.get("status") == "planned":
                        sess["status"] = "skipped"
                        return
