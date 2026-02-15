"""Assessment router — compute 6-axis profile."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.deps import load_state, save_state
from backend.api.models import AssessmentRequest
from backend.engine.assessment_v1 import compute_assessment_profile

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


@router.post("/compute")
def compute_assessment(req: AssessmentRequest):
    """Compute 6-axis assessment profile and save into state."""
    state = load_state()

    assessment = req.assessment or state.get("assessment", {})
    goal = req.goal or state.get("goal", {})

    if not goal:
        raise HTTPException(status_code=422, detail="No goal provided and none in state")

    try:
        profile = compute_assessment_profile(assessment, goal)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Assessment computation failed: {e}")

    # Save profile into state
    state.setdefault("assessment", {})["profile"] = profile
    save_state(state)

    return {"profile": profile}
