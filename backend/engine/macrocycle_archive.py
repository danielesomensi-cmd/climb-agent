"""Macrocycle archival helpers (A-NEW-MACRO).

Snapshots the current macrocycle into ``state["macrocycle_history"]`` before
the next ``POST /api/macrocycle/start-new-cycle`` overwrites it. The list is
append-only from the caller's perspective (this helper does not enforce that
itself — calling ``archive_current_macrocycle`` twice on the same state writes
two entries).

The completion summary is computed by inspecting ``state["session_completion_log"]``
filtered by ``macrocycle.start_date <= log.date <= macrocycle.end_date``.
``feedback_log`` is read-only — never mutated here.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _within_cycle(date_str: str, start: str, end: str) -> bool:
    """Inclusive date-string comparison. ``YYYY-MM-DD`` lexicographic ordering
    matches calendar order, so plain string compare suffices."""
    return start <= date_str <= end


def _count_phases(macrocycle: Dict[str, Any]) -> List[str]:
    """List of phase IDs covered by the macrocycle."""
    return [p.get("phase_id") for p in (macrocycle.get("phases") or []) if p.get("phase_id")]


def _planned_session_count(macrocycle: Dict[str, Any], state: Dict[str, Any]) -> int:
    """Best-effort count of planned sessions over the macrocycle's window.

    Reads ``state["week_plans"]`` and counts every session in every cached
    week whose start_date falls inside the cycle. Fresh week generations may
    not yet be cached for unreached weeks — the count therefore represents
    "sessions the user actually saw" more than "sessions the algorithm would
    eventually produce." That's the right semantic for completion %.
    """
    start = macrocycle.get("start_date")
    end = macrocycle.get("end_date")
    if not start or not end:
        return 0
    week_plans = state.get("week_plans") or {}
    total = 0
    for week_key, plan in week_plans.items():
        if not isinstance(week_key, str):
            continue
        # Cache key is the Monday of the week. Include weeks that begin within
        # the cycle window — partial last week is included by the lexicographic
        # comparison.
        if not (start <= week_key <= end):
            continue
        for week in (plan.get("weeks") or []):
            for day in (week.get("days") or []):
                total += len(day.get("sessions") or [])
    return total


def _tests_completed_in_window(state: Dict[str, Any], start: str, end: str) -> List[Dict[str, str]]:
    """Tests session_ids completed inside the cycle window, with dates."""
    completion_log = state.get("session_completion_log") or []
    out: List[Dict[str, str]] = []
    for entry in completion_log:
        date_str = entry.get("date")
        sid = entry.get("session_id") or ""
        if not date_str or not sid:
            continue
        if entry.get("status") != "done":
            continue
        if not _within_cycle(date_str, start, end):
            continue
        # Convention: any session whose id starts with "test_" is an assessment.
        if sid.startswith("test_"):
            out.append({"session_id": sid, "date": date_str})
    return out


def _build_completion_summary(
    macrocycle: Dict[str, Any],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    start = macrocycle.get("start_date") or ""
    end = macrocycle.get("end_date") or ""
    completion_log = state.get("session_completion_log") or []

    sessions_done = 0
    sessions_skipped = 0
    if start and end:
        for entry in completion_log:
            date_str = entry.get("date")
            if not date_str or not _within_cycle(date_str, start, end):
                continue
            status = entry.get("status")
            if status == "done":
                sessions_done += 1
            elif status == "skipped":
                sessions_skipped += 1

    return {
        "sessions_done": sessions_done,
        "sessions_skipped": sessions_skipped,
        "sessions_planned": _planned_session_count(macrocycle, state),
        "tests_completed": _tests_completed_in_window(state, start, end) if start and end else [],
        "phases_completed": _count_phases(macrocycle),
    }


def _weeks_completed(macrocycle: Dict[str, Any], today_iso: str) -> int:
    """Whole weeks elapsed between macrocycle start_date and today (capped at total_weeks)."""
    start_str = macrocycle.get("start_date")
    total_weeks = int(macrocycle.get("total_weeks") or 0)
    if not start_str or total_weeks <= 0:
        return 0
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        today = datetime.strptime(today_iso, "%Y-%m-%d").date()
    except ValueError:
        return 0
    if today <= start:
        return 0
    delta_days = (today - start).days
    return min(delta_days // 7, total_weeks)


def archive_current_macrocycle(state: Dict[str, Any]) -> Dict[str, Any]:
    """Snapshot ``state["macrocycle"]`` into ``state["macrocycle_history"]``.

    No-op if the state has no current macrocycle (returns the state unchanged
    apart from defensively initializing the history list).

    Mutates *state* in place AND returns it for chaining.

    Idempotency: NOT enforced. Two consecutive calls on the same macrocycle
    produce two history entries — the caller is responsible for calling exactly
    once per cycle replacement.

    The new history entry:

    .. code-block:: json

        {
            "archived_at": "2026-05-05T15:30:00+00:00",
            "macrocycle": { ... full snapshot ... },
            "goal_at_archive": { ... goal at archive time ... },
            "weeks_completed": 11,
            "total_weeks": 12,
            "completion_summary": {
                "sessions_done": int,
                "sessions_skipped": int,
                "sessions_planned": int,
                "tests_completed": [{"session_id": "test_max_hang_7s", "date": "..."}],
                "phases_completed": ["base", "strength_power", ...]
            }
        }
    """
    history = state.setdefault("macrocycle_history", [])

    macrocycle = state.get("macrocycle")
    if not macrocycle:
        # Nothing to archive — defensively initialize and return.
        return state

    today_iso = datetime.now().strftime("%Y-%m-%d")
    total_weeks = int(macrocycle.get("total_weeks") or 0)

    entry = {
        "archived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "macrocycle": deepcopy(macrocycle),
        "goal_at_archive": deepcopy(state.get("goal") or {}),
        "weeks_completed": _weeks_completed(macrocycle, today_iso),
        "total_weeks": total_weeks,
        "completion_summary": _build_completion_summary(macrocycle, state),
    }
    history.append(entry)
    return state
