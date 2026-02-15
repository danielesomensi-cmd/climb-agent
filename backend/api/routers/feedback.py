"""Feedback router — session feedback and closed-loop state updates."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.deps import load_state, save_state
from backend.api.models import FeedbackRequest
from backend.engine.closed_loop_v1 import apply_day_result_to_user_state
from backend.engine.progression_v1 import apply_feedback

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("")
def post_feedback(req: FeedbackRequest):
    """Apply session feedback: progression updates + closed-loop state changes."""
    state = load_state()

    # 1. Apply progression feedback (updates working loads)
    try:
        state = apply_feedback(req.log_entry, state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feedback application failed: {e}")

    # 2. Apply closed-loop state update (stimulus recency, fatigue proxy)
    if req.resolved_day:
        try:
            state = apply_day_result_to_user_state(
                state,
                resolved_day=req.resolved_day,
                status=req.status,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Closed-loop update failed: {e}")

    save_state(state)
    return {"status": "ok", "state": state}
