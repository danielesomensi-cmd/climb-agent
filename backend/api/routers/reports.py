"""Reports router — weekly and monthly training reports."""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api.deps import REPO_ROOT, load_state
from backend.engine.report_engine import generate_monthly_report, generate_weekly_report

router = APIRouter(prefix="/api/reports", tags=["reports"])

LOG_DIR = str(REPO_ROOT / "backend" / "data" / "logs")


@router.get("/weekly")
def get_weekly_report(week_start: str = Query(..., description="YYYY-MM-DD Monday")):
    """Generate a weekly training report."""
    state = load_state()
    report = generate_weekly_report(state, LOG_DIR, week_start)
    return report


@router.get("/monthly")
def get_monthly_report(month: str = Query(..., description="YYYY-MM")):
    """Generate a monthly training report."""
    state = load_state()
    report = generate_monthly_report(state, LOG_DIR, month)
    return report
