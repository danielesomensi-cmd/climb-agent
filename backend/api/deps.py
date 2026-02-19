"""Shared dependencies for the climb-agent API."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = REPO_ROOT / "backend" / "data" / "user_state.json"

EMPTY_TEMPLATE: Dict[str, Any] = {
    "schema_version": "1.5",
    "user": {},
    "assessment": {},
    "goal": {},
    "availability": {},
    "equipment": {"home": [], "gyms": []},
    "planning_prefs": {},
    "limitations": {"active_flags": [], "details": []},
    "trips": [],
    "macrocycle": None,
    "performance": {},
    "baselines": {},
    "recent_sessions": [],
    "stimulus_recency": {},
    "fatigue_proxy": {},
    "working_loads": {"entries": [], "rules": {}},
    "tests": {},
    "body": {},
    "current_week_plan": None,
}


def invalidate_week_cache(state: Dict[str, Any]) -> None:
    """Clear the cached week plan. Call after any action that changes plan inputs."""
    state["current_week_plan"] = None


def load_state() -> Dict[str, Any]:
    """Load user state from disk. Returns empty template if file missing."""
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return deepcopy(EMPTY_TEMPLATE)


def save_state(state: Dict[str, Any]) -> None:
    """Write user state to disk."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def next_monday(from_date: Optional[date] = None) -> str:
    """Return the next Monday as 'YYYY-MM-DD'. If from_date is already Monday, return it."""
    d = from_date or date.today()
    days_ahead = (7 - d.weekday()) % 7  # 0 = Monday
    if days_ahead == 0:
        return d.isoformat()
    return (d + timedelta(days=days_ahead)).isoformat()


def this_monday(from_date: Optional[date] = None) -> str:
    """Return the Monday of the current week as 'YYYY-MM-DD'.

    Unlike next_monday(), this goes backwards to find the Monday
    so that a macrocycle can start immediately (partial first week).
    """
    d = from_date or date.today()
    # weekday() returns 0 for Monday
    return (d - timedelta(days=d.weekday())).isoformat()


def current_phase_and_week(macrocycle: Dict[str, Any]) -> Tuple[int, int]:
    """Given a macrocycle dict, find which phase and week-within-phase today falls in.

    Returns (phase_index, week_within_phase) both 0-based.
    If today is before the macrocycle start, returns (0, 0).
    If today is past the end, returns last phase and its last week.
    """
    phases = macrocycle.get("phases") or []
    if not phases:
        return (0, 0)

    today = date.today()
    cumulative_week = 0
    mc_start = datetime.strptime(macrocycle["start_date"], "%Y-%m-%d").date()

    for pi, phase in enumerate(phases):
        duration = phase.get("duration_weeks", 1)
        phase_start = mc_start + timedelta(weeks=cumulative_week)
        phase_end = phase_start + timedelta(weeks=duration)
        if today < phase_end:
            weeks_into = max(0, (today - phase_start).days // 7)
            return (pi, min(weeks_into, duration - 1))
        cumulative_week += duration

    # Past end — return last phase, last week
    last = phases[-1]
    return (len(phases) - 1, last.get("duration_weeks", 1) - 1)


def week_num_to_phase_context(macrocycle: Dict[str, Any], week_num: int) -> Dict[str, Any]:
    """Convert a 1-based absolute week_num to phase context needed by generate_phase_week.

    week_num=0 means 'current week' (resolved from today's date).

    Returns dict with: phase_id, domain_weights, session_pool, start_date,
    intensity_cap, and the original phase dict.
    """
    phases = macrocycle.get("phases") or []
    if not phases:
        raise ValueError("Macrocycle has no phases")

    mc_start = datetime.strptime(macrocycle["start_date"], "%Y-%m-%d").date()

    if week_num == 0:
        pi, wi = current_phase_and_week(macrocycle)
        cumulative = sum(p.get("duration_weeks", 1) for p in phases[:pi])
        week_num = cumulative + wi + 1  # convert to 1-based

    # Find phase for this week_num
    cumulative = 0
    for phase in phases:
        duration = phase.get("duration_weeks", 1)
        if week_num <= cumulative + duration:
            week_in_phase = week_num - cumulative - 1  # 0-based
            week_start = mc_start + timedelta(weeks=cumulative + week_in_phase)
            return {
                "phase_id": phase["phase_id"],
                "domain_weights": phase.get("domain_weights", {}),
                "session_pool": phase.get("session_pool", []),
                "start_date": week_start.isoformat(),
                "intensity_cap": phase.get("intensity_cap"),
                "phase": phase,
                "week_num": week_num,
                "is_last_week_of_phase": (week_in_phase == duration - 1),
            }
        cumulative += duration

    raise ValueError(f"week_num {week_num} exceeds macrocycle total weeks ({cumulative})")
