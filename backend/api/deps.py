"""Shared dependencies for the climb-agent API."""

from __future__ import annotations

import json
import uuid as _uuid
from uuid import uuid4
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fastapi import Depends, HTTPException, Request

from backend.engine import storage as _storage

REPO_ROOT = Path(__file__).resolve().parents[2]

# Re-export from storage for backwards compatibility with existing imports.
DATA_DIR = _storage.DATA_DIR
STATE_PATH = _storage.STATE_PATH
USERS_DIR = _storage.USERS_DIR

EMPTY_TEMPLATE: Dict[str, Any] = {
    "schema_version": "1.5",
    "user": {},
    "assessment": {},
    "goal": {},
    "availability": {},
    "equipment": {"home": [], "gyms": []},
    "planning_prefs": {},
    "preferences": {"finger_training_device": "hangboard"},
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
    "week_plans": {},
    "outdoor_spots": [],
    "free_sessions": [],
    "quote_history": [],
    "history_index": {"outdoor_log_paths": []},
}


def invalidate_week_cache(state: Dict[str, Any]) -> None:
    """Clear cached week plans for current/future weeks only.

    Past weeks (start_date < today) are preserved — they contain
    completed session data that must not be lost.
    """
    old = state.get("current_week_plan")
    if old:
        state["_prev_week_plan"] = old
    state["current_week_plan"] = None

    today_str = datetime.now().strftime("%Y-%m-%d")
    old_plans = state.get("week_plans") or {}
    state["week_plans"] = {
        k: v for k, v in old_plans.items() if k < today_str
    }


def invalidate_future_week_cache(state: Dict[str, Any]) -> None:
    """Clear cached week plans for future weeks only (start_date > this Monday).

    The current week is left intact — the frontend handles its
    regeneration via ``GET /api/week/0?force=true``.
    Past weeks are always preserved (completed session data).
    """
    current_monday = this_monday()
    old_plans = state.get("week_plans") or {}
    state["week_plans"] = {
        k: v for k, v in old_plans.items() if k <= current_monday
    }


def get_user_id(request: Request) -> Optional[str]:
    """Extract user_id from request, trying Clerk JWT first, then X-User-ID.

    Priority:
    1. Authorization: Bearer <clerk_jwt> → verify → lookup/create user_id
    2. X-User-ID header (dev/test fallback)
    3. None (legacy local dev without header)
    """
    # 1. Try Clerk JWT
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        from backend.api.auth import get_clerk_user_id, is_clerk_configured, lookup_or_create_user
        if is_clerk_configured():
            try:
                token = auth_header.split(" ", 1)[1]
                clerk_id = get_clerk_user_id(token)
                return lookup_or_create_user(clerk_id)
            except Exception as e:
                raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    # 2. Fallback: X-User-ID (dev/test)
    header = request.headers.get("X-User-ID")
    if header is None:
        return None
    try:
        _uuid.UUID(header, version=4)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-ID: must be a valid UUID v4")
    return header


def _user_state_path(user_id: Optional[str]) -> Path:
    """Return the state file path for a given user_id, or the legacy path."""
    return _storage._user_state_path(user_id)


def _migrate_gym_ids(state: Dict[str, Any]) -> bool:
    """Ensure every gym has a stable gym_id (B88 migration). Returns True if state was modified."""
    gyms = state.get("equipment", {}).get("gyms")
    if not gyms:
        return False
    changed = False
    for gym in gyms:
        if not gym.get("gym_id"):
            gym["gym_id"] = uuid4().hex[:8]
            changed = True
    return changed


def load_state(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Load user state from disk. Returns empty template if file missing.

    If user_id is provided, reads from the per-user directory.
    If the per-user file doesn't exist, copies the template and returns it.
    """
    state = _storage.read_state(user_id)
    if state is not None:
        if _migrate_gym_ids(state):
            save_state(state, user_id)
        return state
    if user_id:
        # New user: bootstrap from template
        state = deepcopy(EMPTY_TEMPLATE)
        _storage.write_state(state, user_id)
        return state
    return deepcopy(EMPTY_TEMPLATE)


def _ensure_profile_fresh(state: Dict[str, Any]) -> None:
    """Recompute assessment profile if assessment inputs changed since last computation.

    B127: ensures profile always reflects current assessment.tests, grades,
    self_eval, and body data — regardless of which endpoint modified them.
    """
    assessment = state.get("assessment") or {}
    goal = state.get("goal") or {}

    # Need minimum data to compute a profile
    if not goal.get("target_grade"):
        return
    if not assessment.get("grades") and not assessment.get("tests"):
        return

    # Build a fingerprint of the inputs that affect the profile
    import hashlib
    inputs = json.dumps({
        "body": assessment.get("body") or {},
        "grades": assessment.get("grades") or {},
        "tests": assessment.get("tests") or {},
        "self_eval": assessment.get("self_eval") or {},
        "experience": assessment.get("experience") or {},
        "target_grade": goal.get("target_grade"),
        "current_grade": goal.get("current_grade"),
    }, sort_keys=True)
    fingerprint = hashlib.md5(inputs.encode()).hexdigest()

    # Skip recomputation if inputs haven't changed
    if assessment.get("_profile_fingerprint") == fingerprint:
        return

    try:
        from backend.engine.assessment_v1 import compute_assessment_profile
        profile = compute_assessment_profile(assessment, goal)
        assessment["profile"] = profile
        assessment["_profile_fingerprint"] = fingerprint
        state["assessment"] = assessment
    except Exception:
        pass  # Don't break save if recomputation fails


def save_state(state: Dict[str, Any], user_id: Optional[str] = None) -> None:
    """Write user state to disk.

    If user_id is provided, writes to the per-user directory.
    Automatically recomputes assessment profile if inputs changed (B127).
    """
    _ensure_profile_fresh(state)
    _storage.write_state(state, user_id)


def ensure_monday(d: str) -> str:
    """If *d* (YYYY-MM-DD) is not a Monday, round DOWN to the previous Monday."""
    try:
        dt = datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date format: expected YYYY-MM-DD, got {d!r}")
    return (dt - timedelta(days=dt.weekday())).isoformat()


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
                "is_first_week_of_phase": (week_in_phase == 0),
                "is_last_week_of_phase": (week_in_phase == duration - 1),
            }
        cumulative += duration

    raise ValueError(f"week_num {week_num} exceeds macrocycle total weeks ({cumulative})")


# ---------------------------------------------------------------------------
# Subscription guard dependency
# ---------------------------------------------------------------------------

def require_active_subscription(user_id: Optional[str] = Depends(get_user_id)) -> None:
    """FastAPI dependency: raise 402 if subscription is expired or canceled.

    No-op when:
    - STRIPE_SECRET_KEY is not set (dev/test)
    - STORAGE_BACKEND != 'supabase' (pytest uses file backend)
    - user_id is None (unauthenticated dev request)
    - No subscription row exists (user hasn't completed checkout = still onboarding)
    """
    from backend.engine.subscription_guard import check_subscription
    result = check_subscription(user_id)
    if not result["can_interact"]:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "subscription_required",
                "status": result["status"],
                "message": "Your trial has ended. Subscribe to continue training.",
            },
        )
