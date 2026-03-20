"""Outdoor router — spots CRUD, session logging, slot conversion."""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import get_user_id, load_state, save_state
from backend.api.models import OutdoorSpotCreate, OutdoorSessionLog, ConvertSlotRequest
from backend.engine.outdoor_log import (
    append_outdoor_session,
    compute_outdoor_load_score,
    compute_outdoor_stats,
    load_outdoor_sessions,
    update_outdoor_session,
)

router = APIRouter(prefix="/api/outdoor", tags=["outdoor"])


# ── Spots CRUD ──────────────────────────────────────────────────────────

@router.get("/spots")
def get_outdoor_spots(user_id: Optional[str] = Depends(get_user_id)):
    """Return all saved outdoor climbing spots."""
    state = load_state(user_id)
    return {"spots": state.get("outdoor_spots", [])}


@router.post("/spots")
def add_outdoor_spot(req: OutdoorSpotCreate, user_id: Optional[str] = Depends(get_user_id)):
    """Add a new outdoor spot to user state."""
    state = load_state(user_id)
    spots = state.setdefault("outdoor_spots", [])

    spot_id = req.id or f"spot_{uuid.uuid4().hex[:8]}"

    # Check for duplicate id
    if any(s.get("id") == spot_id for s in spots):
        raise HTTPException(status_code=409, detail=f"Spot with id '{spot_id}' already exists")

    spot: Dict[str, Any] = {
        "id": spot_id,
        "name": req.name,
        "discipline": req.discipline,
    }
    if req.typical_days:
        spot["typical_days"] = req.typical_days
    if req.notes:
        spot["notes"] = req.notes

    spots.append(spot)
    save_state(state, user_id)
    return {"status": "ok", "spot": spot}


@router.delete("/spots/{spot_id}")
def delete_outdoor_spot(spot_id: str, user_id: Optional[str] = Depends(get_user_id)):
    """Remove an outdoor spot by id."""
    state = load_state(user_id)
    spots = state.get("outdoor_spots", [])
    new_spots = [s for s in spots if s.get("id") != spot_id]

    if len(new_spots) == len(spots):
        raise HTTPException(status_code=404, detail=f"Spot '{spot_id}' not found")

    state["outdoor_spots"] = new_spots
    save_state(state, user_id)
    return {"status": "ok"}


# ── Session logging ─────────────────────────────────────────────────────

@router.post("/log")
def post_outdoor_log(req: OutdoorSessionLog, user_id: Optional[str] = Depends(get_user_id)):
    """Validate and append an outdoor session to the log."""
    entry = req.model_dump(exclude_none=True)
    entry["log_version"] = "outdoor.v1"

    try:
        log_path = append_outdoor_session(entry, user_id)
    except ValueError as e:
        # D134: distinguish auth errors (missing user_id) from validation errors
        if "authenticated user_id" in str(e):
            raise HTTPException(
                status_code=401,
                detail="Authentication required to save outdoor session",
            )
        raise HTTPException(status_code=422, detail=str(e))
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write outdoor log: {e}",
        )

    # Verify write persisted (file backend only — Supabase has read-after-write in storage layer)
    if not log_path.startswith("supabase://") and not os.path.isfile(log_path):
        raise HTTPException(
            status_code=500,
            detail=f"Outdoor log write succeeded but file not found at {log_path}",
        )

    return {"status": "ok", "log_path": os.path.basename(log_path)}


@router.get("/log/{date}")
def get_outdoor_log_by_date(date: str, user_id: Optional[str] = Depends(get_user_id)):
    """Return the outdoor session entry for a specific date."""
    sessions = load_outdoor_sessions(user_id, since_date=date)
    matching = [s for s in sessions if s.get("date") == date]
    if not matching:
        raise HTTPException(status_code=404, detail=f"No outdoor session found for date {date}")
    entry = matching[-1]
    entry["load_score"] = compute_outdoor_load_score(entry)
    return {"session": entry}


@router.put("/log")
def put_outdoor_log(req: OutdoorSessionLog, user_id: Optional[str] = Depends(get_user_id)):
    """Update an existing outdoor session (replace entry for the same date)."""
    entry = req.model_dump(exclude_none=True)
    entry["log_version"] = "outdoor.v1"

    try:
        update_outdoor_session(user_id, req.date, entry)
    except ValueError as e:
        detail = str(e)
        if "authenticated user_id" in detail:
            raise HTTPException(status_code=401, detail="Authentication required to update outdoor session")
        status = 404 if "No outdoor session found" in detail or "No outdoor log file" in detail else 422
        raise HTTPException(status_code=status, detail=detail)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to update outdoor log: {e}")

    # Update state.outdoor_log[] (B116) with recalculated load_score
    state = load_state(user_id)
    outdoor_log = state.get("outdoor_log", [])
    for ol_entry in outdoor_log:
        if ol_entry.get("date") == req.date:
            ol_entry["spot_name"] = entry.get("spot_name", ol_entry.get("spot_name", ""))
            ol_entry["discipline"] = entry.get("discipline", ol_entry.get("discipline", "both"))
            ol_entry["load_score"] = compute_outdoor_load_score(entry)
            break
    save_state(state, user_id)

    return {"status": "ok", "load_score": compute_outdoor_load_score(entry)}


@router.get("/sessions")
def get_outdoor_sessions(since: Optional[str] = Query(None), user_id: Optional[str] = Depends(get_user_id)):
    """List outdoor sessions, optionally filtered by date."""
    sessions = load_outdoor_sessions(user_id, since_date=since)
    # Enrich each session with its load score
    for s in sessions:
        s["load_score"] = compute_outdoor_load_score(s)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/stats")
def get_outdoor_stats(since: Optional[str] = Query(None), user_id: Optional[str] = Depends(get_user_id)):
    """Get aggregated outdoor climbing statistics."""
    sessions = load_outdoor_sessions(user_id, since_date=since)
    stats = compute_outdoor_stats(sessions)
    return stats


# ── Slot conversion ─────────────────────────────────────────────────────

@router.post("/convert-slot")
def convert_outdoor_slot(req: ConvertSlotRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Convert an outdoor day slot to gym/home and suggest a session."""
    from backend.engine.replanner_v1 import suggest_sessions

    state = load_state(user_id)
    macrocycle = state.get("macrocycle")
    if not macrocycle:
        raise HTTPException(status_code=400, detail="No macrocycle generated yet")

    suggestions = suggest_sessions(
        user_state=state,
        target_date=req.date,
        location=req.new_location,
    )

    return {
        "date": req.date,
        "new_location": req.new_location,
        "suggestions": suggestions,
    }
