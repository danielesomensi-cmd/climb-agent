"""Feedback router — session feedback and closed-loop state updates."""

from __future__ import annotations

from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_user_id, load_state, save_state
from backend.api.models import FeedbackRequest
from backend.engine.adaptive_replan import (
    append_feedback_log,
    apply_adaptive_replan,
    check_adaptive_replan,
    load_exercises_by_id,
)
from backend.engine.closed_loop_v1 import apply_day_result_to_user_state
from backend.engine.progression_v1 import apply_feedback

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("")
def post_feedback(req: FeedbackRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Apply session feedback: progression updates + closed-loop state changes."""
    state = load_state(user_id)

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

    # 3. Append to feedback log (B25)
    exercises_by_id = load_exercises_by_id()
    append_feedback_log(state, req.log_entry, req.resolved_day, exercises_by_id)

    # 4. Check adaptive replanning (B25)
    plan = state.get("current_week_plan")
    if plan and plan.get("weeks"):
        current_date = req.log_entry.get("date") or date_type.today().isoformat()
        feedback_history = state.get("feedback_log", [])
        result = check_adaptive_replan(plan, feedback_history, current_date)
        if result["actions"]:
            state["current_week_plan"] = apply_adaptive_replan(
                plan, result["actions"]
            )

    save_state(state, user_id)
    return {"status": "ok", "state": state}
