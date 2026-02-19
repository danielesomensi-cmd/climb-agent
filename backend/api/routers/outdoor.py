"""Outdoor router — spots CRUD, session logging, slot conversion."""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.api.deps import REPO_ROOT, load_state, save_state
from backend.api.models import OutdoorSpotCreate, OutdoorSessionLog, ConvertSlotRequest
from backend.engine.outdoor_log import (
    append_outdoor_session,
    compute_outdoor_stats,
    load_outdoor_sessions,
)

router = APIRouter(prefix="/api/outdoor", tags=["outdoor"])

LOG_DIR = str(REPO_ROOT / "backend" / "data" / "logs")


# ── Spots CRUD ──────────────────────────────────────────────────────────

@router.get("/spots")
def get_outdoor_spots():
    """Return all saved outdoor climbing spots."""
    state = load_state()
    return {"spots": state.get("outdoor_spots", [])}


@router.post("/spots")
def add_outdoor_spot(req: OutdoorSpotCreate):
    """Add a new outdoor spot to user state."""
    state = load_state()
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
    save_state(state)
    return {"status": "ok", "spot": spot}


@router.delete("/spots/{spot_id}")
def delete_outdoor_spot(spot_id: str):
    """Remove an outdoor spot by id."""
    state = load_state()
    spots = state.get("outdoor_spots", [])
    new_spots = [s for s in spots if s.get("id") != spot_id]

    if len(new_spots) == len(spots):
        raise HTTPException(status_code=404, detail=f"Spot '{spot_id}' not found")

    state["outdoor_spots"] = new_spots
    save_state(state)
    return {"status": "ok"}


# ── Session logging ─────────────────────────────────────────────────────

@router.post("/log")
def post_outdoor_log(req: OutdoorSessionLog):
    """Validate and append an outdoor session to the log."""
    entry = req.model_dump(exclude_none=True)
    entry["log_version"] = "outdoor.v1"

    try:
        log_path = append_outdoor_session(entry, LOG_DIR)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {"status": "ok", "log_path": os.path.basename(log_path)}


@router.get("/sessions")
def get_outdoor_sessions(since: Optional[str] = Query(None)):
    """List outdoor sessions, optionally filtered by date."""
    sessions = load_outdoor_sessions(LOG_DIR, since_date=since)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/stats")
def get_outdoor_stats(since: Optional[str] = Query(None)):
    """Get aggregated outdoor climbing statistics."""
    sessions = load_outdoor_sessions(LOG_DIR, since_date=since)
    stats = compute_outdoor_stats(sessions)
    return stats


# ── Slot conversion ─────────────────────────────────────────────────────

@router.post("/convert-slot")
def convert_outdoor_slot(req: ConvertSlotRequest):
    """Convert an outdoor day slot to gym/home and suggest a session."""
    from backend.engine.replanner_v1 import suggest_sessions

    state = load_state()
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
