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
) -> Optional[str]:
    """Fatigue-cost-weighted average of the RATED exercise labels.

    A295 (R4 §3e): ``None`` when nothing was rated or the rated exercises
    cover less than half of the session's fatigue cost — an untouched dialog
    is not an "ok" session, and one very_hard tapped on a warm-up is not a
    very_hard session. See measured_feedback.derive_session_difficulty.
    """
    from backend.engine.measured_feedback import derive_session_difficulty

    return derive_session_difficulty(log_entry, exercises_by_id)


def append_feedback_log(
    state: Dict[str, Any],
    log_entry: Dict[str, Any],
    resolved_day: Optional[Dict[str, Any]],
    exercises_by_id: Dict[str, Dict[str, Any]],
) -> None:
    """Append session feedback summary to state["feedback_log"]. Trims to 7."""
    difficulty = _derive_session_difficulty(log_entry, exercises_by_id)

    # Extract session_id — prefer direct field from log_entry (frontend sends this)
    session_id = log_entry.get("session_id") or "unknown"
    if session_id == "unknown" and resolved_day and resolved_day.get("sessions"):
        session_id = resolved_day["sessions"][0].get("session_id", "unknown")
    if session_id == "unknown" and log_entry.get("planned"):
        planned = log_entry["planned"]
        if isinstance(planned, list) and planned:
            session_id = planned[0].get("session_id", "unknown")
        elif isinstance(planned, dict):
            session_id = planned.get("session_id", "unknown")

    date = str(log_entry.get("date") or "")

    # Build per-exercise feedback map for UI display (B35 / FR-3)
    actual = log_entry.get("actual") or {}
    feedback_items = actual.get("exercise_feedback_v1") or []
    # A295: only what the athlete actually rated (no fake 'ok').
    from backend.engine.measured_feedback import rated_exercise_feedback, sanitize_pain

    exercise_feedback: Dict[str, str] = rated_exercise_feedback(log_entry)
    pain = sanitize_pain(log_entry.get("pain"))

    feedback_log: List[Dict[str, Any]] = state.setdefault("feedback_log", [])
    duration = log_entry.get("session_duration_seconds")

    # B197 Bug 1: dedup by (date, session_id). On resubmit, merge the new
    # payload into the existing entry instead of appending. Duration is kept
    # as max() so a short re-submit (e.g. fresh `startedAt` after a /today
    # render race) cannot clobber the real training duration.
    existing = None
    for candidate in feedback_log:
        if str(candidate.get("date") or "") == date and candidate.get("session_id") == session_id:
            existing = candidate
            break

    if existing is not None:
        # A295: a resubmit without a rating never erases a rated difficulty.
        if difficulty is not None:
            existing["difficulty"] = difficulty
        if pain is not None:
            existing["pain"] = pain
        if exercise_feedback:
            existing["exercise_feedback"] = exercise_feedback
        if duration is not None:
            prev = existing.get("session_duration_seconds")
            existing["session_duration_seconds"] = (
                max(prev, duration) if isinstance(prev, (int, float)) else duration
            )
    else:
        entry: Dict[str, Any] = {
            "date": date,
            "session_id": session_id,
        }
        if difficulty is not None:
            entry["difficulty"] = difficulty
        if pain is not None:
            entry["pain"] = pain
        if exercise_feedback:
            entry["exercise_feedback"] = exercise_feedback
        if duration is not None:
            entry["session_duration_seconds"] = duration
        feedback_log.append(entry)

    # Trim to last 7 entries by date descending
    feedback_log.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
    del feedback_log[7:]


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _rewritable(session: Dict[str, Any]) -> bool:
    """B367: the replanner's single exemption list (done/skipped, forced, custom)."""
    from backend.engine.replanner_v1 import _is_rewritable

    return _is_rewritable(session)


def _past(day_date: str, today: Optional[str]) -> bool:
    """B367: a day before the athlete's today is immutable even when unmarked."""
    return bool(today) and day_date < str(today)


def check_adaptive_replan(
    plan: Dict[str, Any],
    feedback_history: List[Dict[str, Any]],
    current_date: str,
    today: Optional[str] = None,
) -> Dict[str, Any]:
    """Check if adaptive replanning is needed based on feedback history.

    Returns {"actions": [...], "warnings": [...]}.

    B367: a target day/session must be something the engine may rewrite —
    never a done/skipped, forced (A254) or user-authored custom (B345)
    session, and never a day before *today* (ISO; ``None`` = no frozen past).
    Rule 2 used to pick the first day that was not ENTIRELY done/skipped, so a
    day holding a done session plus a planned one — or any custom session —
    was then wiped wholesale by ``apply_adaptive_replan``.
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
            if day_dt <= current_dt or _past(day_date, today):
                continue
            # Skip days already done/skipped
            if day.get("status") in {"done", "skipped"}:
                continue
            sessions = day.get("sessions") or []
            # B367: a day with sessions but none the engine may rewrite is not
            # a target (the recovery would have to delete the user's work).
            # An empty day keeps the pre-B367 behaviour.
            if sessions and not any(_rewritable(s) for s in sessions):
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
            if day_dt <= current_dt or _past(day_date, today):
                continue
            sessions = day.get("sessions") or []
            for session in sessions:
                # B367: done/skipped, forced and custom sessions are never
                # downgraded (it used to check done/skipped only).
                if not _rewritable(session):
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
    """Apply adaptive replan actions to the plan. Returns modified copy.

    B367: only sessions ``_is_rewritable`` allows are touched — a done/skipped,
    forced or custom session on the target day is kept byte-identical (the
    recovery used to replace the whole day).
    """
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
                if tags.get("hard") and _rewritable(session):
                    sessions[i] = {
                        "slot": session.get("slot", "evening"),
                        "session_id": "complementary_conditioning",
                        "downshifted_from": session.get("session_id"),  # A294
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
            rewritable = [s for s in sessions if _rewritable(s)]
            if sessions and not rewritable:
                continue  # B367: nothing the engine may touch on this day
            recovery = {
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
            }
            if rewritable:
                # Preserve slot/location/gym_id from the first rewritable
                # session; the rewritable ones collapse into the one recovery
                # session, the protected ones stay exactly as they are.
                ref = rewritable[0]
                recovery["slot"] = ref.get("slot", "evening")
                recovery["location"] = ref.get("location", "home")
                recovery["gym_id"] = ref.get("gym_id")
                lost = next(
                    (s for s in rewritable if (s.get("tags") or {}).get("hard") or (s.get("tags") or {}).get("finger")),
                    ref,
                )
                if lost.get("session_id") != "regeneration_easy":
                    recovery["downshifted_from"] = lost.get("session_id")  # A294
                first = sessions.index(ref)
                kept = [s for s in sessions if not _rewritable(s)]
                kept_before = [s for s in sessions[:first] if not _rewritable(s)]
                target_day["sessions"] = kept_before + [recovery] + kept[len(kept_before):]
            else:
                target_day["sessions"] = [recovery]

    # Log adaptation
    current_date = actions[0].get("target_date", "") if actions else ""
    updated.setdefault("adaptations", []).append({
        "type": "adaptive_replan",
        "date": current_date,
        "actions": actions,
    })

    return updated
