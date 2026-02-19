"""Report engine — generates weekly and monthly training reports."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.engine.outdoor_log import load_outdoor_sessions


def _load_indoor_sessions(log_dir: str, since: str, until: str) -> List[Dict[str, Any]]:
    """Load indoor session log entries within a date range."""
    sessions: List[Dict[str, Any]] = []
    if not os.path.isdir(log_dir):
        return sessions

    for fn in sorted(os.listdir(log_dir)):
        if not fn.startswith("sessions_") or not fn.endswith(".jsonl"):
            continue
        path = os.path.join(log_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    entry_date = entry.get("date", "")
                    if since <= entry_date <= until:
                        sessions.append(entry)
        except OSError:
            continue

    return sessions


def generate_weekly_report(
    user_state: Dict[str, Any],
    log_dir: str,
    week_start: str,
) -> Dict[str, Any]:
    """Generate a weekly training report.

    Args:
        user_state: Current user state.
        log_dir: Directory containing session JSONL logs.
        week_start: YYYY-MM-DD Monday of the week.

    Returns:
        Report dict with adherence, volume, highlights.
    """
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    end = start + timedelta(days=6)
    since = start.isoformat()
    until = end.isoformat()

    indoor = _load_indoor_sessions(log_dir, since, until)
    outdoor = load_outdoor_sessions(log_dir, since_date=since)
    # Filter outdoor to this week
    outdoor = [s for s in outdoor if s.get("date", "") <= until]

    # Planned sessions from current_week_plan
    plan = user_state.get("current_week_plan") or {}
    planned_count = 0
    for week in plan.get("weeks", []):
        for day in week.get("days", []):
            if since <= day.get("date", "") <= until:
                planned_count += len(day.get("sessions", []))

    completed_count = len(indoor)
    adherence = round(completed_count / planned_count * 100, 1) if planned_count else 0.0

    # Total volume (minutes)
    indoor_minutes = sum(
        s.get("duration_minutes", 0) for s in indoor
    )
    outdoor_minutes = sum(
        s.get("duration_minutes", 0) for s in outdoor
    )

    # Session types
    session_types: Dict[str, int] = {}
    for s in indoor:
        sid = s.get("session_id", "unknown")
        session_types[sid] = session_types.get(sid, 0) + 1

    # Highlights
    highlights: List[str] = []
    if adherence >= 90:
        highlights.append("Excellent adherence this week!")
    elif adherence >= 70:
        highlights.append("Good training consistency.")

    if outdoor:
        highlights.append(f"{len(outdoor)} outdoor session(s) logged.")

    return {
        "report_type": "weekly",
        "week_start": week_start,
        "week_end": until,
        "planned_sessions": planned_count,
        "completed_sessions": completed_count,
        "adherence_pct": adherence,
        "total_indoor_minutes": indoor_minutes,
        "total_outdoor_minutes": outdoor_minutes,
        "session_types": session_types,
        "outdoor_sessions": len(outdoor),
        "highlights": highlights,
    }


def generate_monthly_report(
    user_state: Dict[str, Any],
    log_dir: str,
    month: str,
) -> Dict[str, Any]:
    """Generate a monthly training report.

    Args:
        user_state: Current user state.
        log_dir: Directory containing session JSONL logs.
        month: YYYY-MM string.

    Returns:
        Report dict with aggregated stats and suggestions.
    """
    year, mon = month.split("-")
    start = datetime.strptime(f"{month}-01", "%Y-%m-%d").date()
    # End of month
    if int(mon) == 12:
        end = datetime(int(year) + 1, 1, 1).date() - timedelta(days=1)
    else:
        end = datetime(int(year), int(mon) + 1, 1).date() - timedelta(days=1)

    since = start.isoformat()
    until = end.isoformat()

    indoor = _load_indoor_sessions(log_dir, since, until)
    outdoor = load_outdoor_sessions(log_dir, since_date=since)
    outdoor = [s for s in outdoor if s.get("date", "") <= until]

    # Weekly aggregation
    total_weeks = (end - start).days // 7 + 1
    weekly_counts: List[int] = [0] * total_weeks
    for s in indoor:
        entry_date = datetime.strptime(s.get("date", since), "%Y-%m-%d").date()
        week_idx = min((entry_date - start).days // 7, total_weeks - 1)
        weekly_counts[week_idx] += 1

    avg_sessions_per_week = round(sum(weekly_counts) / max(total_weeks, 1), 1)

    # Feedback summary
    feedback_labels: Dict[str, int] = {}
    for s in indoor:
        label = s.get("overall_feeling") or s.get("feedback_label", "ok")
        feedback_labels[label] = feedback_labels.get(label, 0) + 1

    # Total volume
    indoor_minutes = sum(s.get("duration_minutes", 0) for s in indoor)
    outdoor_minutes = sum(s.get("duration_minutes", 0) for s in outdoor)

    # Suggestions (max 3 rules)
    suggestions: List[str] = []
    overall_adherence = avg_sessions_per_week
    target = (user_state.get("planning_prefs") or {}).get("target_training_days_per_week", 4)

    if target > 0 and overall_adherence / target < 0.7:
        suggestions.append(
            "Training adherence is below 70%. Consider adjusting your availability or reducing target days."
        )

    if not outdoor:
        suggestions.append(
            "No outdoor sessions this month. Consider scheduling an outdoor day to apply gym gains."
        )

    # Check for technique sessions
    technique_count = sum(
        1 for s in indoor
        if "technique" in s.get("session_id", "")
    )
    if technique_count == 0 and len(indoor) >= 4:
        suggestions.append(
            "No technique-focused sessions detected. Adding movement quality work can accelerate progress."
        )

    return {
        "report_type": "monthly",
        "month": month,
        "period_start": since,
        "period_end": until,
        "total_indoor_sessions": len(indoor),
        "total_outdoor_sessions": len(outdoor),
        "avg_sessions_per_week": avg_sessions_per_week,
        "weekly_session_counts": weekly_counts,
        "total_indoor_minutes": indoor_minutes,
        "total_outdoor_minutes": outdoor_minutes,
        "feedback_summary": feedback_labels,
        "suggestions": suggestions[:3],
    }
