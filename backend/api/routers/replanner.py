"""Replanner router — day overrides and event-based adaptation."""

from __future__ import annotations

import os
from copy import deepcopy

from fastapi import APIRouter, HTTPException

from backend.api.deps import REPO_ROOT, load_state
from backend.api.models import EventsRequest, OverrideRequest
from backend.engine.replanner_v1 import apply_day_override, apply_events
from backend.engine.resolve_session import resolve_session

router = APIRouter(prefix="/api/replanner", tags=["replanner"])

SESSIONS_DIR = "backend/catalog/sessions/v1"
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"


def _auto_resolve(week_plan: dict, state: dict) -> None:
    """Resolve all sessions in a week plan inline (same logic as week router)."""
    for week_block in week_plan.get("weeks", []):
        for day_entry in week_block.get("days", []):
            for session_entry in day_entry.get("sessions", []):
                session_id = session_entry.get("session_id", "")
                session_path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
                full_path = REPO_ROOT / session_path
                if not full_path.exists():
                    session_entry["resolved"] = None
                    continue
                try:
                    resolve_state = deepcopy(state)
                    resolve_state["context"] = {
                        **resolve_state.get("context", {}),
                        "location": session_entry.get("location", "home"),
                        "gym_id": session_entry.get("gym_id"),
                    }
                    resolved = resolve_session(
                        repo_root=str(REPO_ROOT),
                        session_path=session_path,
                        templates_dir=TEMPLATES_DIR,
                        exercises_path=EXERCISES_PATH,
                        out_path="",
                        user_state_override=resolve_state,
                        write_output=False,
                    )
                    session_entry["resolved"] = resolved
                except Exception:
                    session_entry["resolved"] = None


@router.post("/override")
def override(req: OverrideRequest):
    """Apply a day override (change a day's session by intent)."""
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
            target_date=req.target_date,
            gym_id=req.gym_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Override failed: {e}")

    # Auto-resolve all sessions so the frontend gets exercises inline
    _auto_resolve(updated, state)

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

    # Auto-resolve all sessions so the frontend gets exercises inline
    _auto_resolve(updated, state)

    return {"week_plan": updated}
