"""Replanner router — day overrides and event-based adaptation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.deps import load_state
from backend.api.models import EventsRequest, OverrideRequest
from backend.engine.replanner_v1 import apply_day_override, apply_events

router = APIRouter(prefix="/api/replanner", tags=["replanner"])


@router.post("/override")
def override(req: OverrideRequest):
    """Apply a day override (change tomorrow's session by intent)."""
    state = load_state()

    week_plan = req.week_plan
    if not week_plan:
        raise HTTPException(
            status_code=422,
            detail="week_plan is required — generate one from GET /api/week/{week_num} first",
        )

    try:
        updated = apply_day_override(
            week_plan,
            intent=req.intent,
            location=req.location,
            reference_date=req.reference_date,
            slot=req.slot,
            phase_id=req.phase_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Override failed: {e}")

    return {"week_plan": updated}


@router.post("/events")
def events(req: EventsRequest):
    """Apply a list of events (move, mark_done, mark_skipped, etc.) to a week plan."""
    state = load_state()

    week_plan = req.week_plan
    if not week_plan:
        raise HTTPException(
            status_code=422,
            detail="week_plan is required — generate one from GET /api/week/{week_num} first",
        )

    availability = state.get("availability")
    planning_prefs = state.get("planning_prefs")
    gyms = (state.get("equipment") or {}).get("gyms")

    try:
        updated = apply_events(
            week_plan,
            req.events,
            availability=availability,
            planning_prefs=planning_prefs,
            gyms=gyms,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Events application failed: {e}")

    return {"week_plan": updated}
