"""Week router — generate a week plan from macrocycle context."""

from __future__ import annotations

import os
from copy import deepcopy

from fastapi import APIRouter, HTTPException

from backend.api.deps import REPO_ROOT, load_state, week_num_to_phase_context
from backend.engine.planner_v2 import generate_phase_week
from backend.engine.resolve_session import resolve_session

router = APIRouter(prefix="/api/week", tags=["week"])

SESSIONS_DIR = "backend/catalog/sessions/v1"
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"


@router.get("/{week_num}")
def get_week(week_num: int):
    """Generate the plan for a given week (1-based). week_num=0 → current week."""
    state = load_state()
    macrocycle = state.get("macrocycle")
    if not macrocycle:
        raise HTTPException(status_code=422, detail="No macrocycle — generate one first")

    try:
        ctx = week_num_to_phase_context(macrocycle, week_num)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    availability = state.get("availability")
    planning_prefs = state.get("planning_prefs", {})
    equipment = state.get("equipment", {})
    gyms = equipment.get("gyms", [])
    hard_cap = planning_prefs.get("hard_day_cap_per_week", 3)

    # Determine default gym_id (highest priority first)
    default_gym_id = None
    if gyms:
        sorted_gyms = sorted(gyms, key=lambda g: (g.get("priority", 999), g.get("gym_id", "")))
        default_gym_id = sorted_gyms[0].get("gym_id")

    try:
        week_plan = generate_phase_week(
            phase_id=ctx["phase_id"],
            domain_weights=ctx["domain_weights"],
            session_pool=ctx["session_pool"],
            start_date=ctx["start_date"],
            availability=availability,
            hard_cap_per_week=hard_cap,
            planning_prefs=planning_prefs,
            default_gym_id=default_gym_id,
            gyms=gyms,
            intensity_cap=ctx.get("intensity_cap"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Week generation failed: {e}")

    # Auto-resolve each session so the frontend gets exercises inline
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

    return {
        "week_num": ctx["week_num"],
        "phase_id": ctx["phase_id"],
        "week_plan": week_plan,
    }
