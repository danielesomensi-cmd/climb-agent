"""Macrocycle router — generate periodized macrocycle."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import (
    current_phase_and_week,
    get_user_id,
    invalidate_week_cache,
    load_state,
    this_monday,
    save_state,
)
from backend.api.models import MacrocycleRequest
from backend.engine.macrocycle_v1 import generate_macrocycle

router = APIRouter(prefix="/api/macrocycle", tags=["macrocycle"])


@router.post("/generate")
def generate(req: MacrocycleRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Generate a macrocycle and save it into state.

    When *from_phase* is set, performs incremental regeneration:
    earlier phases are kept intact, remaining phases are regenerated
    with the current assessment profile.
    """
    state = load_state(user_id)

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

    # --- resolve incremental vs full regen --------------------------------
    from_phase = req.from_phase
    if from_phase:
        old_mc = state.get("macrocycle")
        if not old_mc:
            raise HTTPException(
                status_code=422,
                detail="No existing macrocycle for incremental regen",
            )
        if from_phase == "current":
            pi, _ = current_phase_and_week(old_mc)
            from_phase = old_mc["phases"][pi]["phase_id"]

        start_date = old_mc["start_date"]
        total_weeks = old_mc.get("total_weeks", 12)
    else:
        start_date = req.start_date or this_monday()
        total_weeks = req.total_weeks

    try:
        macrocycle = generate_macrocycle(
            goal, profile, state, start_date, total_weeks,
            from_phase=from_phase,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Macrocycle generation failed: {e}")

    state["macrocycle"] = macrocycle
    state.pop("initial_tests_requested", None)
    invalidate_week_cache(state)
    save_state(state, user_id)

    return {"macrocycle": macrocycle}
