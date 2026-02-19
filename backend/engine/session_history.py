"""Cross-session exercise recency — reads completed session logs for variety."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import List


def get_recent_exercise_ids(log_dir: str, days: int = 7) -> List[str]:
    """Read recent session logs and extract exercise_ids used.

    Scans sessions_*.jsonl files in log_dir for entries within the last `days` days.
    Returns ordered list (most recent first, then chronological within day).
    """
    if not os.path.isdir(log_dir):
        return []

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    recent: List[str] = []

    paths = []
    for fn in sorted(os.listdir(log_dir)):
        if fn.startswith("sessions_") and fn.endswith(".jsonl"):
            paths.append(os.path.join(log_dir, fn))

    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Filter by date if available
                    entry_date = obj.get("date", "")
                    if entry_date and entry_date < cutoff:
                        continue

                    # Extract exercise_ids from various possible structures
                    exercise_ids = _extract_exercise_ids(obj)
                    recent.extend(exercise_ids)
        except OSError:
            continue

    return recent


def _extract_exercise_ids(obj: dict) -> List[str]:
    """Extract exercise_id values from a session log entry."""
    ids: List[str] = []

    # Structure 1: exercise_instances (from resolved session)
    instances = obj.get("exercise_instances") or []
    if not instances:
        resolved = obj.get("resolved_session") or {}
        instances = resolved.get("exercise_instances") or []

    for inst in instances:
        eid = inst.get("exercise_id")
        if eid:
            ids.append(eid.strip().lower())

    # Structure 2: exercise_outcomes (from feedback log)
    outcomes = obj.get("exercise_outcomes") or []
    for out in outcomes:
        eid = out.get("exercise_id")
        if eid:
            ids.append(eid.strip().lower())

    return ids
