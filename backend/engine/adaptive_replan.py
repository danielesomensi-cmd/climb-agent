"""Adaptive replanning after user feedback (B25).

Pure functions, no I/O except catalog loading. When a user reports very_hard
or fail feedback, the plan is conservatively adjusted:
  - Rule 1: single very_hard → downgrade next hard day
  - Rule 2: 2× very_hard in 3 days → insert recovery day (overrides Rule 1)
Never auto-upgrades.
"""

from __future__ import annotations

import functools
import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.engine.progression_v1 import canonical_feedback_label

_LABEL_TO_SCORE = {
    "very_easy": 1,
    "easy": 2,
    "ok": 3,
    "hard": 4,
    "very_hard": 5,
}

_SCORE_THRESHOLDS = [
    (1.5, "very_easy"),
    (2.5, "easy"),
    (3.5, "ok"),
    (4.5, "hard"),
]


def _score_to_label(score: float) -> str:
    for threshold, label in _SCORE_THRESHOLDS:
        if score <= threshold:
            return label
    return "very_hard"


@functools.lru_cache(maxsize=1)
def load_exercises_by_id() -> Dict[str, Dict[str, Any]]:
    """Load exercise catalog keyed by exercise id."""
    path = Path("backend/catalog/exercises/v1/exercises.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {e["id"]: e for e in data["exercises"]}


def _derive_session_difficulty(
    log_entry: Dict[str, Any],
    exercises_by_id: Dict[str, Dict[str, Any]],
) -> str:
    """Fatigue-cost-weighted average of exercise feedback labels."""
    actual = log_entry.get("actual") or {}
    feedback_items = actual.get("exercise_feedback_v1") or []

    if not feedback_items:
        return "ok"

    total_weighted_score = 0.0
    total_weight = 0.0

    for item in feedback_items:
        label = canonical_feedback_label(item)
        score = _LABEL_TO_SCORE.get(label, 3)
        exercise_id = str(item.get("exercise_id") or "")
        exercise = exercises_by_id.get(exercise_id, {})
        fatigue_cost = float(exercise.get("fatigue_cost", 5))
        total_weighted_score += score * fatigue_cost
        total_weight += fatigue_cost

    if total_weight == 0:
        return "ok"

    avg = total_weighted_score / total_weight
    return _score_to_label(avg)


def append_feedback_log(
    state: Dict[str, Any],
    log_entry: Dict[str, Any],
    resolved_day: Optional[Dict[str, Any]],
    exercises_by_id: Dict[str, Dict[str, Any]],
) -> None:
    """Append session feedback summary to state["feedback_log"]. Trims to 7."""
    difficulty = _derive_session_difficulty(log_entry, exercises_by_id)

    # Extract session_id
    session_id = "unknown"
    if resolved_day and resolved_day.get("sessions"):
        session_id = resolved_day["sessions"][0].get("session_id", "unknown")
    elif log_entry.get("planned"):
        planned = log_entry["planned"]
        if isinstance(planned, list) and planned:
            session_id = planned[0].get("session_id", "unknown")
        elif isinstance(planned, dict):
            session_id = planned.get("session_id", "unknown")

    date = str(log_entry.get("date") or "")

    feedback_log: List[Dict[str, Any]] = state.setdefault("feedback_log", [])
    feedback_log.append({
        "date": date,
        "session_id": session_id,
        "difficulty": difficulty,
    })

    # Trim to last 7 entries by date descending
    feedback_log.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
    del feedback_log[7:]


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def check_adaptive_replan(
    plan: Dict[str, Any],
    feedback_history: List[Dict[str, Any]],
    current_date: str,
) -> Dict[str, Any]:
    """Check if adaptive replanning is needed based on feedback history.

    Returns {"actions": [...], "warnings": [...]}.
    """
    actions: List[Dict[str, Any]] = []
    warnings: List[str] = []

    if not feedback_history:
        return {"actions": actions, "warnings": warnings}

    # Filter for very_hard / fail entries
    hard_entries = [
        e for e in feedback_history
        if e.get("difficulty") in {"very_hard", "fail"}
    ]

    if not hard_entries:
        return {"actions": actions, "warnings": warnings}

    # Filter to entries within 3 days of current_date
    try:
        current_dt = _parse_date(current_date)
    except (ValueError, TypeError):
        return {"actions": actions, "warnings": warnings}

    recent_hard = []
    for entry in hard_entries:
        try:
            entry_dt = _parse_date(str(entry.get("date") or ""))
        except (ValueError, TypeError):
            continue
        delta = (current_dt - entry_dt).days
        if 0 <= delta <= 3:
            recent_hard.append(entry)

    if not recent_hard:
        return {"actions": actions, "warnings": warnings}

    days = plan.get("weeks", [{}])[0].get("days", []) if plan.get("weeks") else []

    # Rule 2 (higher priority): 2+ very_hard/fail in 3 days → insert recovery
    if len(recent_hard) >= 2:
        for day in days:
            day_date = str(day.get("date") or "")
            try:
                day_dt = _parse_date(day_date)
            except (ValueError, TypeError):
                continue
            if day_dt <= current_dt:
                continue
            # Skip days already done/skipped
            if day.get("status") in {"done", "skipped"}:
                continue
            sessions = day.get("sessions") or []
            if all(s.get("status") in {"done", "skipped"} for s in sessions if s.get("status")):
                if any(s.get("status") in {"done", "skipped"} for s in sessions):
                    continue
            actions.append({
                "type": "insert_recovery",
                "target_date": day_date,
                "reason": f"{len(recent_hard)}x very_hard/fail in last 3 days",
                "replacement_session_id": "regeneration_easy",
            })
            return {"actions": actions, "warnings": warnings}

    # Rule 1: most recent entry is very_hard/fail → downgrade next hard day
    most_recent = max(hard_entries, key=lambda e: str(e.get("date") or ""))
    if most_recent.get("difficulty") in {"very_hard", "fail"}:
        for day in days:
            day_date = str(day.get("date") or "")
            try:
                day_dt = _parse_date(day_date)
            except (ValueError, TypeError):
                continue
            if day_dt <= current_dt:
                continue
            sessions = day.get("sessions") or []
            for session in sessions:
                if session.get("status") in {"done", "skipped"}:
                    continue
                tags = session.get("tags") or {}
                if tags.get("hard"):
                    actions.append({
                        "type": "downgrade_next_hard",
                        "target_date": day_date,
                        "reason": "very_hard/fail feedback → downgrade next hard session",
                        "original_session_id": session.get("session_id"),
                        "replacement_session_id": "complementary_conditioning",
                    })
                    return {"actions": actions, "warnings": warnings}

    return {"actions": actions, "warnings": warnings}


def apply_adaptive_replan(
    plan: Dict[str, Any],
    actions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply adaptive replan actions to the plan. Returns modified copy."""
    updated = deepcopy(plan)
    days = updated.get("weeks", [{}])[0].get("days", []) if updated.get("weeks") else []

    for action in actions:
        target_date = action.get("target_date")
        target_day = None
        for day in days:
            if day.get("date") == target_date:
                target_day = day
                break
        if target_day is None:
            continue

        action_type = action.get("type")

        if action_type == "downgrade_next_hard":
            sessions = target_day.get("sessions") or []
            for i, session in enumerate(sessions):
                tags = session.get("tags") or {}
                if tags.get("hard") and session.get("status") not in {"done", "skipped"}:
                    sessions[i] = {
                        "slot": session.get("slot", "evening"),
                        "session_id": "complementary_conditioning",
                        "location": session.get("location", "home"),
                        "gym_id": session.get("gym_id"),
                        "intensity": "medium",
                        "tags": {"hard": False, "finger": False},
                        "constraints_applied": ["adaptive_replan"],
                        "explain": [
                            "adaptive replan: downgrade hard session after very_hard feedback",
                            f"original_session={session.get('session_id')}",
                        ],
                    }
                    break

        elif action_type == "insert_recovery":
            sessions = target_day.get("sessions") or []
            if sessions:
                # Preserve slot/location/gym_id from first session
                ref = sessions[0]
                target_day["sessions"] = [{
                    "slot": ref.get("slot", "evening"),
                    "session_id": "regeneration_easy",
                    "location": ref.get("location", "home"),
                    "gym_id": ref.get("gym_id"),
                    "intensity": "low",
                    "tags": {"hard": False, "finger": False},
                    "constraints_applied": ["adaptive_replan"],
                    "explain": [
                        "adaptive replan: recovery day after repeated very_hard feedback",
                    ],
                }]
            else:
                target_day["sessions"] = [{
                    "slot": "evening",
                    "session_id": "regeneration_easy",
                    "location": "home",
                    "gym_id": None,
                    "intensity": "low",
                    "tags": {"hard": False, "finger": False},
                    "constraints_applied": ["adaptive_replan"],
                    "explain": [
                        "adaptive replan: recovery day after repeated very_hard feedback",
                    ],
                }]

    # Log adaptation
    current_date = actions[0].get("target_date", "") if actions else ""
    updated.setdefault("adaptations", []).append({
        "type": "adaptive_replan",
        "date": current_date,
        "actions": actions,
    })

    return updated
