"""Quotes router — daily motivational quotes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from backend.api.deps import load_state, save_state
from backend.engine.quotes_engine import get_quote_for_session, update_quote_history

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


@router.get("/daily")
def get_daily_quote(context: str = Query("general", description="Quote context tag")):
    """Get a motivational quote for the given context."""
    state = load_state()
    recent_ids = state.get("quote_history", [])

    quote = get_quote_for_session(
        context=context,
        recent_quote_ids=recent_ids,
    )

    # Update history
    update_quote_history(state, quote["id"])
    save_state(state)

    return quote
