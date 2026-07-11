"""LLM Coach router (A-COACH-V1a).

Endpoints:
  POST /api/coach/chat     — one chat turn (subscription-gated, 30 msg/day)
  GET  /api/coach/history  — paginated full history for the UI

The coach is a read-only conversational layer: it never mutates plan, state,
or logs. Access is fail-closed (B202 pattern) via require_active_subscription.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.api.deps import get_user_id, require_active_subscription
from backend.coach import service
from backend.coach.llm_client import APIError, CoachConfigError
from backend.engine import storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/coach", tags=["coach"])

MAX_MESSAGE_CHARS = 4000


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)


@router.post("/chat", dependencies=[Depends(require_active_subscription)])
def coach_chat(
    req: ChatRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """One coach chat turn: {message} → {reply}."""
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message is empty")

    if service.messages_sent_today(user_id) >= service.DAILY_MESSAGE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_limit",
                "message": "You've reached today's coach limit — back tomorrow!",
            },
        )

    try:
        reply = service.handle_chat(user_id, message)
    except CoachConfigError as exc:
        # Fail loud (fixed decision): 500 + explicit log, never silent.
        logger.error("Coach misconfigured: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={"error": "coach_not_configured", "message": str(exc)},
        )
    except APIError as exc:
        logger.exception("Coach LLM call failed")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "llm_unavailable",
                "message": "The coach is temporarily unavailable — try again in a minute.",
            },
        )

    return {"reply": reply}


@router.get("/history", dependencies=[Depends(require_active_subscription)])
def coach_history(
    limit: int = Query(50, ge=1, le=100),
    before: Optional[str] = Query(
        None, description="ISO created_at cursor — return messages older than this"
    ),
    user_id: Optional[str] = Depends(get_user_id),
):
    """Paginated chat history (full, permanent). Messages oldest-first."""
    rows = storage.read_coach_messages(user_id, limit=limit + 1, before=before)
    has_more = len(rows) > limit
    page = rows[:limit]  # newest-first from storage
    page.reverse()  # oldest-first for straightforward rendering
    return {"messages": page, "has_more": has_more}
