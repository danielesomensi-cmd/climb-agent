"""Macrocycle router — generate periodized macrocycle."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from backend.api.deps import invalidate_week_cache, load_state, this_monday, save_state
from backend.api.models import MacrocycleRequest
from backend.engine.macrocycle_v1 import generate_macrocycle

router = APIRouter(prefix="/api/macrocycle", tags=["macrocycle"])


@router.post("/generate")
def generate(req: MacrocycleRequest):
    """Generate a macrocycle and save it into state."""
    state = load_state()

    goal = state.get("goal")
    if not goal:
        raise HTTPException(status_code=422, detail="No goal in state — complete onboarding first")

    profile = (state.get("assessment") or {}).get("profile")
    if not profile:
        raise HTTPException(status_code=422, detail="No assessment profile — run assessment first")

    # Validate goal deadline is not in the past
    deadline = goal.get("deadline")
    if deadline:
        try:
            dl = datetime.strptime(deadline, "%Y-%m-%d").date()
            if dl < date.today():
                raise HTTPException(
                    status_code=400,
                    detail="Goal deadline is in the past. Please update your goal with a future date.",
                )
        except ValueError:
            pass  # Non-standard format, let macrocycle generator handle it

    start_date = req.start_date or this_monday()

    try:
        macrocycle = generate_macrocycle(goal, profile, state, start_date, req.total_weeks)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Macrocycle generation failed: {e}")

    state["macrocycle"] = macrocycle
    invalidate_week_cache(state)
    save_state(state)

    return {"macrocycle": macrocycle}
