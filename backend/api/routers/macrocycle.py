"""Macrocycle router — generate periodized macrocycle."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.deps import load_state, next_monday, save_state
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

    start_date = req.start_date or next_monday()

    try:
        macrocycle = generate_macrocycle(goal, profile, state, start_date, req.total_weeks)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Macrocycle generation failed: {e}")

    state["macrocycle"] = macrocycle
    save_state(state)

    return {"macrocycle": macrocycle}
