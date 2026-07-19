"""Tips router — daily feature-discovery tips (A234).

GET is read-only (selection is stateless — see tips_engine); only an explicit
dismiss writes to user_state. The client passes its local date so "today"
matches the user's timezone, mirroring the today page.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import get_user_id, load_state, save_state
from backend.engine.tips_engine import (
    get_daily_tip,
    is_dismissed,
    record_dismissal,
    tip_exists,
)

router = APIRouter(prefix="/api/tips", tags=["tips"])


def _parse_date(raw: Optional[str]) -> date_cls:
    if not raw:
        return date_cls.today()
    try:
        return date_cls.fromisoformat(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date, expected YYYY-MM-DD")


@router.get("/daily")
def daily_tip(
    date: Optional[str] = Query(None, description="Client-local date (YYYY-MM-DD)"),
    user_id: Optional[str] = Depends(get_user_id),
):
    """Get the deterministic tip of the day + whether it was dismissed today."""
    target = _parse_date(date)
    tip = get_daily_tip(user_id or "anonymous", target)
    if tip is None:
        return {"tip": None, "dismissed_today": False}
    state = load_state(user_id)
    return {"tip": tip, "dismissed_today": is_dismissed(state, tip["id"], target)}


@router.post("/{tip_id}/dismiss")
def dismiss_tip(
    tip_id: str,
    date: Optional[str] = Query(None, description="Client-local date (YYYY-MM-DD)"),
    user_id: Optional[str] = Depends(get_user_id),
):
    """Record a per-day dismissal for this tip (idempotent)."""
    if not tip_exists(tip_id):
        raise HTTPException(status_code=404, detail="Unknown tip id")
    target = _parse_date(date)
    state = load_state(user_id)
    record_dismissal(state, tip_id, target)
    save_state(state, user_id)
    return {"ok": True, "tip_id": tip_id, "date": target.isoformat()}
