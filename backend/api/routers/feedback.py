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
from backend.engine.progression_v1 import apply_feedback, canonical_feedback_label
from backend.engine.resolve_session import normalize_limitations, _check_exercise_limitation

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

    # 3b. A139: Persist raw actual exercise data in session slot
    _fb_items = (req.log_entry.get("actual") or {}).get("exercise_feedback_v1") or []
    if _fb_items:
        _target_date = req.log_entry.get("date")
        _target_sid = req.log_entry.get("session_id")
        # Write to current_week_plan
        _wp = state.get("current_week_plan") or {}
        for _week_block in _wp.get("weeks", []):
            for _day_entry in _week_block.get("days", []):
                if _day_entry.get("date") != _target_date:
                    continue
                for _sess in _day_entry.get("sessions", []):
                    if _sess.get("session_id") == _target_sid:
                        _sess["actual_exercises"] = _fb_items
                        break
        # B136b: Also sync to week_plans cache so GET /api/week/0 sees it
        _wp_start = _wp.get("start_date", "")
        if _wp_start:
            _cached = (state.get("week_plans") or {}).get(_wp_start)
            if _cached and _cached.get("weeks"):
                for _week_block_c in _cached["weeks"]:
                    for _day_c in _week_block_c.get("days", []):
                        if _day_c.get("date") != _target_date:
                            continue
                        for _sess_c in _day_c.get("sessions", []):
                            if _sess_c.get("session_id") == _target_sid:
                                _sess_c["actual_exercises"] = _fb_items
                                break

    # 4. Check adaptive replanning (B25)
    plan = state.get("current_week_plan")
    if plan and plan.get("weeks"):
        current_date = req.log_entry.get("date") or date_type.today().isoformat()
        feedback_history = state.get("feedback_log", [])
        result = check_adaptive_replan(plan, feedback_history, current_date)
        if result["actions"]:
            updated_plan = apply_adaptive_replan(plan, result["actions"])
            state["current_week_plan"] = updated_plan
            # Sync to per-week cache so navigation doesn't lose the change
            start_key = updated_plan.get("start_date", "")
            if start_key:
                if "week_plans" not in state:
                    state["week_plans"] = {}
                state["week_plans"][start_key] = updated_plan

    # 5. Limitation severity suggestions (B38)
    limitation_suggestions = []
    limitation_map = normalize_limitations(state)
    if limitation_map:
        exercise_feedback = (req.log_entry.get("actual") or {}).get("exercise_feedback_v1") or []
        for item in exercise_feedback:
            label = canonical_feedback_label(item)
            if label not in ("hard", "very_hard"):
                continue
            ex_id = str(item.get("exercise_id") or "").strip()
            ex_data = exercises_by_id.get(ex_id, {})
            lim = _check_exercise_limitation(ex_data, limitation_map)
            if lim and lim["severity"] == "monitor":
                limitation_suggestions.append({
                    "exercise_id": ex_id,
                    "zone": lim["zone"],
                    "current_severity": "monitor",
                    "suggested_severity": "active",
                    "reason": f"{label} feedback on exercise with {lim['zone']} contraindication",
                })

    # 6. Attach feedback to session completion log (B117)
    log_entry_date = req.log_entry.get("date")
    log_entry_session = req.log_entry.get("session_id")
    if log_entry_date and log_entry_session:
        for entry in reversed(state.get("session_completion_log", [])):
            if entry.get("date") == log_entry_date and entry.get("session_id") == log_entry_session:
                # Compute overall difficulty from exercise feedback
                fb_items = (req.log_entry.get("actual") or {}).get("exercise_feedback_v1") or []
                labels = [canonical_feedback_label(f) for f in fb_items]
                labels = [l for l in labels if l]
                if labels:
                    entry["difficulty"] = labels[-1] if len(set(labels)) > 1 else labels[0]
                entry["exercise_count"] = len(fb_items)
                duration = req.log_entry.get("session_duration_seconds")
                if duration is not None:
                    entry["session_duration_seconds"] = duration
                break

    save_state(state, user_id)
    response = {"status": "ok", "state": state}
    if limitation_suggestions:
        response["limitation_suggestions"] = limitation_suggestions
    return response
