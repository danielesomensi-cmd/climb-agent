"""Reports router — weekly and monthly training reports."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import get_user_id, load_state
from backend.engine.report_engine import (
    generate_monthly_heatmap,
    generate_monthly_report,
    generate_weekly_report,
)

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/weekly")
def get_weekly_report(week_start: str = Query(..., description="YYYY-MM-DD Monday"), user_id: Optional[str] = Depends(get_user_id)):
    """Generate a weekly training report."""
    state = load_state(user_id)
    report = generate_weekly_report(state, user_id, week_start)
    return report


@router.get("/monthly")
def get_monthly_report(month: str = Query(..., description="YYYY-MM"), user_id: Optional[str] = Depends(get_user_id)):
    """Generate a monthly training report."""
    state = load_state(user_id)
    report = generate_monthly_report(state, user_id, month)
    return report


@router.get("/heatmap")
def get_monthly_heatmap(month: str = Query(..., description="YYYY-MM"), user_id: Optional[str] = Depends(get_user_id)):
    """Per-day activity/rest heatmap cells for a month (A236 / A-GAMIFY-03)."""
    if not _MONTH_RE.match(month):
        raise HTTPException(status_code=422, detail="Invalid month, expected YYYY-MM")
    state = load_state(user_id)
    return generate_monthly_heatmap(state, user_id, month)
