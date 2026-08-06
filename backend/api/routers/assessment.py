"""Assessment router — compute 6-axis profile."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_user_id, load_state, save_state
from backend.api.models import AssessmentRequest
from backend.engine.assessment_v1 import (
    PROFILE_SCORING_VERSION,
    compute_assessment_profile_with_source,
)
from backend.engine.progression_v1 import estimate_missing_baselines

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


@router.post("/compute")
def compute_assessment(req: AssessmentRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Compute 6-axis assessment profile and save into state."""
    state = load_state(user_id)

    assessment = req.assessment or state.get("assessment", {})
    goal = req.goal or state.get("goal", {})

    if not goal:
        raise HTTPException(status_code=422, detail="No goal provided and none in state")

    try:
        profile, profile_source = compute_assessment_profile_with_source(assessment, goal)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Assessment computation failed: {e}")

    # Save profile into state
    # A269: scores and their provenance are written together, never apart.
    state.setdefault("assessment", {})["profile"] = profile
    state["assessment"]["profile_source"] = profile_source
    state["assessment"]["profile_scoring_version"] = PROFILE_SCORING_VERSION
    estimate_missing_baselines(state)  # B121: re-estimate pulling baseline from test results
    save_state(state, user_id)

    return {"profile": profile}
