"""Replanner router — day overrides and event-based adaptation."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import DATA_DIR, REPO_ROOT, USERS_DIR, current_phase_and_week, get_user_id, load_state, save_state
from backend.api.models import EventsRequest, OverrideRequest, QuickAddRequest
from backend.engine.outdoor_log import compute_outdoor_load_score, load_outdoor_sessions, remove_outdoor_session
from backend.engine.replanner_v1 import apply_day_add, apply_day_override, apply_events, suggest_sessions
from backend.engine.resolve_session import resolve_session

router = APIRouter(prefix="/api/replanner", tags=["replanner"])

SESSIONS_DIR = "backend/catalog/sessions/v1"
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"


def _session_display_name(session_id: str) -> str:
    """Return the human-readable name for a session, reading from its JSON file."""
    path = REPO_ROOT / SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            name = data.get("session_name") or data.get("name")
            if name:
                return name
        except Exception:
            pass
    # Fallback: format session_id as title
    return session_id.replace("_", " ").title()


def _persist_week_plan(updated: dict, state: dict, user_id) -> None:
    """Save modified plan to per-week cache and (if current) to legacy cache."""
    start_key = updated.get("start_date", "")
    if not start_key:
        return

    if "week_plans" not in state:
        state["week_plans"] = {}
    state["week_plans"][start_key] = updated

    # Also update legacy current_week_plan if this IS the current week
    macrocycle = state.get("macrocycle")
    if macrocycle and macrocycle.get("phases"):
        from datetime import datetime, timedelta

        mc_start = datetime.strptime(macrocycle["start_date"], "%Y-%m-%d").date()
        pi, wi = current_phase_and_week(macrocycle)
        cumulative = sum(p.get("duration_weeks", 1) for p in macrocycle["phases"][:pi])
        current_start = (mc_start + timedelta(weeks=cumulative + wi)).isoformat()
        if start_key == current_start:
            state["current_week_plan"] = updated
    else:
        state["current_week_plan"] = updated

    save_state(state, user_id)


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
def override(req: OverrideRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Apply a day override (change a day's session by intent)."""
    state = load_state(user_id)

    week_plan = req.week_plan
    if not week_plan:
        raise HTTPException(
            status_code=422,
            detail="week_plan is required — generate one from GET /api/week/{week_num} first",
        )

    # B96: pass gyms so override can check equipment compatibility
    equipment = state.get("equipment", {})
    gyms = equipment.get("gyms", [])

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
            gyms=gyms,
            session_index=req.session_index,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Override failed: {e}")

    _persist_week_plan(updated, state, user_id)

    # Auto-resolve all sessions so the frontend gets exercises inline
    _auto_resolve(updated, state)

    return {"week_plan": updated}


@router.get("/suggest-sessions")
def get_suggestions(target_date: str, location: str = "gym", user_id: Optional[str] = Depends(get_user_id)):
    """Suggest sessions to quick-add on a given date."""
    state = load_state(user_id)
    week_plan = state.get("current_week_plan")
    if not week_plan:
        raise HTTPException(
            status_code=422,
            detail="No current week plan — generate one from GET /api/week/0 first",
        )

    # Build session pool from macrocycle context if available
    session_pool = None
    macrocycle = state.get("macrocycle")
    if macrocycle:
        snapshot = week_plan.get("profile_snapshot") or {}
        phase_id = snapshot.get("phase_id", "base")
        from backend.engine.macrocycle_v1 import _build_session_pool
        session_pool = _build_session_pool(phase_id)

    try:
        suggestions = suggest_sessions(
            week_plan,
            target_date,
            location,
            session_pool=session_pool,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suggestion failed: {e}")

    # Enrich suggestions with human-readable names and equipment info
    for s in suggestions:
        s["session_name"] = _session_display_name(s["session_id"])
        path = REPO_ROOT / SESSIONS_DIR / f"{s['session_id']}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                s["required_equipment"] = data.get("required_equipment", [])
            except Exception:
                s["required_equipment"] = []
        else:
            s["required_equipment"] = []

    return {"suggestions": suggestions}


@router.post("/quick-add")
def quick_add(req: QuickAddRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Add an extra session to a day without replacing existing ones."""
    state = load_state(user_id)

    week_plan = req.week_plan
    if not week_plan:
        raise HTTPException(
            status_code=422,
            detail="week_plan is required — generate one from GET /api/week/{week_num} first",
        )

    try:
        updated, warnings = apply_day_add(
            week_plan,
            session_id=req.session_id,
            target_date=req.target_date,
            slot=req.slot,
            location=req.location,
            phase_id=req.phase_id,
            gym_id=req.gym_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quick-add failed: {e}")

    _persist_week_plan(updated, state, user_id)

    _auto_resolve(updated, state)

    return {"week_plan": updated, "warnings": warnings}


@router.post("/events")
def events(req: EventsRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Apply a list of events (move, mark_done, mark_skipped, etc.) to a week plan."""
    state = load_state(user_id)

    week_plan = req.week_plan
    if not week_plan:
        raise HTTPException(
            status_code=422,
            detail="week_plan is required — generate one from GET /api/week/{week_num} first",
        )

    availability = state.get("availability")
    planning_prefs = state.get("planning_prefs")
    gyms = (state.get("equipment") or {}).get("gyms")

    # For complete_outdoor events, compute outdoor load score from JSONL log
    log_dir = str(USERS_DIR / user_id / "logs") if user_id else str(DATA_DIR / "logs")
    for ev in req.events:
        if ev.get("event_type") == "complete_outdoor" and ev.get("date"):
            outdoor_sessions = load_outdoor_sessions(log_dir, since_date=ev["date"])
            matching = [s for s in outdoor_sessions if s.get("date") == ev["date"]]
            if matching:
                ev["outdoor_load_score"] = compute_outdoor_load_score(matching[-1])

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

    # Remove outdoor log entries for any undo_outdoor events so re-logging
    # doesn't produce duplicates.
    log_dir = str(USERS_DIR / user_id / "logs") if user_id else str(DATA_DIR / "logs")
    for ev in req.events:
        if ev.get("event_type") == "undo_outdoor" and ev.get("date"):
            remove_outdoor_session(log_dir, ev["date"])

    _persist_week_plan(updated, state, user_id)

    # Auto-resolve all sessions so the frontend gets exercises inline
    _auto_resolve(updated, state)

    return {"week_plan": updated}
