"""Reports router — weekly and monthly training reports."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.api.deps import DATA_DIR, USERS_DIR, get_user_id, load_state
from backend.engine.report_engine import generate_monthly_report, generate_weekly_report

router = APIRouter(prefix="/api/reports", tags=["reports"])

_FALLBACK_LOG_DIR = str(DATA_DIR / "logs")


def _log_dir(user_id: Optional[str]) -> str:
    """Return user-scoped log directory, or fallback for legacy/test."""
    if user_id:
        d = str(USERS_DIR / user_id / "logs")
        os.makedirs(d, exist_ok=True)
        return d
    return _FALLBACK_LOG_DIR


@router.get("/weekly")
def get_weekly_report(week_start: str = Query(..., description="YYYY-MM-DD Monday"), user_id: Optional[str] = Depends(get_user_id)):
    """Generate a weekly training report."""
    state = load_state(user_id)
    report = generate_weekly_report(state, _log_dir(user_id), week_start)
    return report


@router.get("/monthly")
def get_monthly_report(month: str = Query(..., description="YYYY-MM"), user_id: Optional[str] = Depends(get_user_id)):
    """Generate a monthly training report."""
    state = load_state(user_id)
    report = generate_monthly_report(state, _log_dir(user_id), month)
    return report
