"""Admin router — user management (protected by ADMIN_SECRET)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from backend.api.rate_limit import limiter
from backend.engine import storage

router = APIRouter(prefix="/api/admin", tags=["admin"])

import os
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


def _require_admin(request: Request) -> None:
    """Raise 403 if X-Admin-Key header is missing or wrong."""
    secret = ADMIN_SECRET
    key = request.headers.get("X-Admin-Key")
    if not secret or key != secret:
        raise HTTPException(status_code=403, detail="Forbidden")


def _extract_last_access(state: Dict[str, Any], user_id: str) -> Optional[str]:
    """Best-effort last access date from feedback_log, macrocycle, or file mtime."""
    fl = state.get("feedback_log") or []
    if fl:
        return fl[0].get("date")

    mc = state.get("macrocycle") or {}
    gen = mc.get("generated_at")
    if gen:
        return gen[:10]

    assessed = (state.get("assessment") or {}).get("last_assessed")
    if assessed:
        return assessed[:10]

    # Fallback: file modification time
    mtime = storage.user_state_mtime(user_id)
    if mtime is not None:
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    return None


def _extract_grade(state: Dict[str, Any]) -> Optional[str]:
    """Current grade from goal or assessment."""
    grade = (state.get("goal") or {}).get("current_grade")
    if grade:
        return grade

    discipline = (state.get("goal") or {}).get("discipline", "boulder")
    grades = (state.get("assessment") or {}).get("grades") or {}
    return grades.get(f"{discipline}_max_rp") or grades.get("boulder_max_rp")


def _count_sessions(state: Dict[str, Any], user_id: str) -> int:
    """Count completed sessions from feedback_log + JSONL session logs."""
    count = len(state.get("feedback_log") or [])
    count += storage.count_session_log_lines(user_id)
    return count


def _extract_onboarding_date(state: Dict[str, Any]) -> Optional[str]:
    """Onboarding date from goal.created_at or macrocycle.start_date."""
    created = (state.get("goal") or {}).get("created_at")
    if created:
        return created[:10]

    mc = state.get("macrocycle") or {}
    start = mc.get("start_date")
    if start:
        return start[:10]

    return (state.get("assessment") or {}).get("last_assessed")


def _scan_users() -> List[Dict[str, Any]]:
    """Scan USERS_DIR and extract summary for each user."""
    users: List[Dict[str, Any]] = []

    for user_id in storage.list_user_ids():
        state = storage.read_state(user_id)
        if state is None:
            continue

        users.append({
            "uuid": user_id,
            "last_access": _extract_last_access(state, user_id),
            "grade": _extract_grade(state),
            "sessions_completed": _count_sessions(state, user_id),
            "onboarding_date": _extract_onboarding_date(state),
        })

    return users


@router.get("/users")
def list_users(request: Request):
    """List all users with summary info. Requires X-Admin-Key header."""
    _require_admin(request)
    users = _scan_users()
    return {"users": users, "total": len(users)}


@router.delete("/users/{uuid}")
@limiter.limit("5/minute")
def delete_user(uuid: str, request: Request):
    """Delete a user directory entirely. Requires X-Admin-Key header."""
    _require_admin(request)
    if uuid not in storage.list_user_ids():
        raise HTTPException(status_code=404, detail=f"User {uuid} not found")
    storage.delete_user_data(uuid)
    return {"status": "deleted", "uuid": uuid}
