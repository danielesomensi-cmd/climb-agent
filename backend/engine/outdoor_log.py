"""Outdoor session logging — append-only JSONL log for outdoor climbing sessions."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


REQUIRED_FIELDS = {"log_version", "date", "spot_name", "discipline", "duration_minutes", "routes"}
VALID_DISCIPLINES = {"lead", "boulder", "both"}


def validate_outdoor_entry(entry: Dict[str, Any]) -> List[str]:
    """Validate an outdoor session entry. Returns list of error strings (empty = valid)."""
    errors: List[str] = []

    missing = REQUIRED_FIELDS - set(entry.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")
        return errors

    if entry.get("log_version") != "outdoor.v1":
        errors.append(f"Invalid log_version: {entry.get('log_version')} (expected outdoor.v1)")

    if entry.get("discipline") not in VALID_DISCIPLINES:
        errors.append(f"Invalid discipline: {entry.get('discipline')}")

    date_str = entry.get("date", "")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        errors.append(f"Invalid date format: {date_str} (expected YYYY-MM-DD)")

    duration = entry.get("duration_minutes")
    if not isinstance(duration, int) or duration < 1:
        errors.append(f"Invalid duration_minutes: {duration}")

    routes = entry.get("routes")
    if not isinstance(routes, list):
        errors.append("routes must be a list")
    else:
        for i, route in enumerate(routes):
            if not isinstance(route, dict):
                errors.append(f"routes[{i}] must be a dict")
                continue
            if not route.get("name"):
                errors.append(f"routes[{i}].name is required")
            if not route.get("grade"):
                errors.append(f"routes[{i}].grade is required")
            attempts = route.get("attempts")
            if not isinstance(attempts, list) or len(attempts) < 1:
                errors.append(f"routes[{i}].attempts must be a non-empty list")

    return errors


def _log_path_for_date(log_dir: str, date_str: str) -> str:
    """Return the JSONL log path for a given date (yearly files)."""
    year = date_str[:4]
    return os.path.join(log_dir, f"outdoor_sessions_{year}.jsonl")


def append_outdoor_session(entry: Dict[str, Any], log_dir: str) -> str:
    """Validate and append an outdoor session entry to the yearly JSONL log.

    Returns the path of the log file written to.
    Raises ValueError if validation fails.
    """
    errors = validate_outdoor_entry(entry)
    if errors:
        raise ValueError(f"Invalid outdoor session entry: {'; '.join(errors)}")

    os.makedirs(log_dir, exist_ok=True)
    log_path = _log_path_for_date(log_dir, entry["date"])

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return log_path


def load_outdoor_sessions(
    log_dir: str,
    since_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load outdoor sessions from JSONL logs, optionally filtered by date."""
    sessions: List[Dict[str, Any]] = []

    if not os.path.isdir(log_dir):
        return sessions

    for fn in sorted(os.listdir(log_dir)):
        if not fn.startswith("outdoor_sessions_") or not fn.endswith(".jsonl"):
            continue
        path = os.path.join(log_dir, fn)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if since_date and entry.get("date", "") < since_date:
                    continue
                sessions.append(entry)

    return sessions


def compute_outdoor_stats(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregated statistics from outdoor sessions."""
    if not sessions:
        return {
            "total_sessions": 0,
            "total_routes": 0,
            "grade_histogram": {},
            "onsight_pct": 0.0,
            "flash_pct": 0.0,
            "sent_pct": 0.0,
            "top_grade_sent": None,
        }

    total_routes = 0
    onsight_count = 0
    flash_count = 0
    sent_count = 0
    grade_counts: Dict[str, int] = {}
    grades_sent: List[str] = []

    for session in sessions:
        for route in session.get("routes", []):
            total_routes += 1
            grade = route.get("grade", "unknown")
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

            attempts = route.get("attempts", [])
            any_sent = any(a.get("result") == "sent" for a in attempts)

            if any_sent:
                sent_count += 1
                grades_sent.append(grade)

                # Onsight: first attempt is sent and style is onsight (or no style but first attempt sent)
                style = route.get("style")
                if style == "onsight":
                    onsight_count += 1
                elif style == "flash":
                    flash_count += 1
                elif style is None and len(attempts) == 1 and attempts[0].get("result") == "sent":
                    # Auto-detect: single attempt sent = potential onsight
                    onsight_count += 1

    # Top grade sent (lexicographic — works for Font/French scales approximately)
    top_grade = max(grades_sent) if grades_sent else None

    return {
        "total_sessions": len(sessions),
        "total_routes": total_routes,
        "grade_histogram": dict(sorted(grade_counts.items())),
        "onsight_pct": round(onsight_count / total_routes * 100, 1) if total_routes else 0.0,
        "flash_pct": round(flash_count / total_routes * 100, 1) if total_routes else 0.0,
        "sent_pct": round(sent_count / total_routes * 100, 1) if total_routes else 0.0,
        "top_grade_sent": top_grade,
    }
