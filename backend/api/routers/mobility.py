"""Mobility & Stretching pool router (A230).

Endpoints:
  GET /api/mobility/pool — full pool: regions in picker order, entries sorted
      (releases first, then holds by priority), GATE-2 soft warnings.

Session lifecycle (start/finish/history) goes through the free-session router
with ``surface="mobility_stretching"`` and ``session_mode="mobility"``.
"""

from __future__ import annotations

from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import get_user_id, load_state, require_active_subscription
from backend.engine.mobility import build_pool_payload

router = APIRouter(prefix="/api/mobility", tags=["mobility"])


@router.get("/pool", dependencies=[Depends(require_active_subscription)])
def get_pool(
    date: Optional[str] = Query(
        None,
        description="ISO date used for the GATE-2 check (planned session that day). Omit to skip the check.",
    ),
    user_id: Optional[str] = Depends(get_user_id),
):
    """Return the full mobility pool grouped by region, with GATE-2 warnings."""
    if date is not None:
        try:
            date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid date: {date!r} — expected YYYY-MM-DD",
            )
    state = load_state(user_id)
    return build_pool_payload(state, date)
