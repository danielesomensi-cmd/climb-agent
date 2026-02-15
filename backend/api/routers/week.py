"""Week router — generate a week plan from macrocycle context."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.deps import load_state, week_num_to_phase_context
from backend.engine.planner_v2 import generate_phase_week

router = APIRouter(prefix="/api/week", tags=["week"])


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

    # Determine default gym_id
    default_gym_id = None
    if gyms:
        default_gym_id = gyms[0].get("gym_id")

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

    return {
        "week_num": ctx["week_num"],
        "phase_id": ctx["phase_id"],
        "week_plan": week_plan,
    }
