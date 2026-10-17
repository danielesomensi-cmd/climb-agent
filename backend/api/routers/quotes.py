"""Quotes router — daily motivational quotes.

B384: this GET used to load the whole state, append one id to
``quote_history`` and save the whole state back on *every* call — not under
the user write lock, so a write landing between its load and its save was
lost, and in prod each call cost ~1.3 s for a 528 KB blob.

Now the quote is a pure function of (user, day, context) and the state is
written at most once per new quote: only when the quote of the day is not
already in ``quote_history``, under ``user_write_lock`` and on a state
reloaded inside the lock. The history is kept because ``scripts/gtm_funnel.py``
reads its length as "days the app was opened"; the selection no longer
depends on it.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import get_user_id, load_state, save_state
from backend.api.plan_revision import user_write_lock
from backend.engine.quotes_engine import get_quote_of_the_day, update_quote_history

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


def _parse_date(raw: Optional[str]) -> date_cls:
    if not raw:
        return date_cls.today()
    try:
        return date_cls.fromisoformat(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date, expected YYYY-MM-DD")


@router.get("/daily")
def get_daily_quote(
    context: str = Query("general", description="Quote context tag"),
    date: Optional[str] = Query(None, description="Client-local date (YYYY-MM-DD); default server today"),
    user_id: Optional[str] = Depends(get_user_id),
):
    """Get the motivational quote of the day for the given context."""
    quote = get_quote_of_the_day(context, _parse_date(date), str(user_id or ""))

    state = load_state(user_id)
    if quote["id"] in (state.get("quote_history") or []):
        return quote  # already recorded: zero writes

    with user_write_lock(user_id):
        fresh = load_state(user_id)  # never save a state read outside the lock
        if quote["id"] not in (fresh.get("quote_history") or []):
            update_quote_history(fresh, quote["id"])
            save_state(fresh, user_id)
    return quote
