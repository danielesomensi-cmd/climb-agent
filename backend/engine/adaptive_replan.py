"""Adaptive replanning after user feedback (B25) — suggestion only since B369.

Pure functions, no I/O except catalog loading. When a user reports very_hard
or fail feedback, the detection below finds what a conservative coach would
lighten:
  - Rule 1: single very_hard → the next hard session
  - Rule 2: 2× very_hard in 3 days → a recovery day (overrides Rule 1)

B369 (Daniele, 2026-10-05: "non facciamo cose automatiche"): the plan is NEVER
changed. ``build_adaptive_suggestion`` turns the detection into an alert the
/api/feedback response carries; lightening a session is the athlete's call
(a custom session). ``apply_adaptive_replan`` — the old automatic rewrite —
is gone.
"""

from __future__ import annotations

import functools
import json
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
    include_protected: bool = False,
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

    # B369: with *include_protected* (the suggestion path — nothing is
    # rewritten) a forced / custom / user-owned session is a valid target too:
    # it is exactly what the athlete may want to lighten. Done/skipped never.
    def _candidate(session: Dict[str, Any]) -> bool:
        if include_protected:
            return session.get("status") not in ("done", "skipped")
        return _rewritable(session)

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
            if sessions and not any(_candidate(s) for s in sessions):
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
                if not _candidate(session):
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


def build_adaptive_suggestion(
    result: Dict[str, Any], plan: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """B369: the alert /api/feedback returns after a very_hard / fail — never
    a plan change. ``None`` when the detection found nothing.

    ``kind`` is ``lighten_next_hard`` (Rule 1) or ``recovery_day`` (Rule 2);
    ``session_id`` / ``session_name`` name the session concerned when there is
    one (Rule 1, or the first not-done session of the Rule-2 day).
    """
    actions = (result or {}).get("actions") or []
    if not actions:
        return None
    action = actions[0]
    target_date = action.get("target_date")
    kind = "recovery_day" if action.get("type") == "insert_recovery" else "lighten_next_hard"
    session: Optional[Dict[str, Any]] = None
    for day in ((plan or {}).get("weeks") or [{}])[0].get("days", []) if plan else []:
        if day.get("date") != target_date:
            continue
        for s in day.get("sessions") or []:
            if s.get("status") in ("done", "skipped"):
                continue
            if kind == "recovery_day" or s.get("session_id") == action.get("original_session_id"):
                session = s
                break
    suggestion: Dict[str, Any] = {
        "kind": kind,
        "target_date": target_date,
        "reason": action.get("reason"),
        "plan_changed": False,
    }
    if session is not None:
        suggestion["session_id"] = session.get("session_id")
        if session.get("name"):
            suggestion["session_name"] = session.get("name")
        suggestion["user_owned"] = _user_owned(session)
    elif action.get("original_session_id"):
        suggestion["session_id"] = action.get("original_session_id")
    if kind == "recovery_day":
        suggestion["message"] = (
            f"Repeated very hard sessions: consider making {target_date} a recovery day. "
            "Nothing was changed in your plan."
        )
    else:
        suggestion["message"] = (
            f"That felt very hard: consider lightening your next hard session ({target_date}). "
            "Nothing was changed in your plan."
        )
    return suggestion


def _user_owned(session: Dict[str, Any]) -> bool:
    from backend.engine.user_owned import is_user_owned

    return is_user_owned(session)
