"""Admin router — user management (protected by ADMIN_SECRET)."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from backend.api import deps as _deps

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


def _require_admin(request: Request) -> None:
    """Raise 403 if X-Admin-Key header is missing or wrong."""
    secret = ADMIN_SECRET
    key = request.headers.get("X-Admin-Key")
    if not secret or key != secret:
        raise HTTPException(status_code=403, detail="Forbidden")


def _extract_last_access(state: Dict[str, Any], state_path: Path) -> Optional[str]:
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
    try:
        mtime = state_path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return None


def _extract_grade(state: Dict[str, Any]) -> Optional[str]:
    """Current grade from goal or assessment."""
    grade = (state.get("goal") or {}).get("current_grade")
    if grade:
        return grade

    discipline = (state.get("goal") or {}).get("discipline", "boulder")
    grades = (state.get("assessment") or {}).get("grades") or {}
    return grades.get(f"{discipline}_max_rp") or grades.get("boulder_max_rp")


def _count_sessions(state: Dict[str, Any], user_dir: Path) -> int:
    """Count completed sessions from feedback_log + JSONL session logs."""
    count = len(state.get("feedback_log") or [])

    logs_dir = user_dir / "logs"
    if not logs_dir.is_dir():
        return count

    for f in logs_dir.iterdir():
        if f.name.startswith("sessions_") and f.suffix == ".jsonl":
            try:
                count += sum(1 for line in f.read_text(encoding="utf-8").splitlines() if line.strip())
            except OSError:
                pass
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
    users_dir = Path(_deps.USERS_DIR)
    if not users_dir.is_dir():
        return users

    for entry in sorted(users_dir.iterdir()):
        if not entry.is_dir():
            continue
        state_path = entry / "user_state.json"
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        users.append({
            "uuid": entry.name,
            "last_access": _extract_last_access(state, state_path),
            "grade": _extract_grade(state),
            "sessions_completed": _count_sessions(state, entry),
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
def delete_user(uuid: str, request: Request):
    """Delete a user directory entirely. Requires X-Admin-Key header."""
    _require_admin(request)
    user_dir = Path(_deps.USERS_DIR) / uuid
    if not user_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"User {uuid} not found")
    shutil.rmtree(user_dir)
    return {"status": "deleted", "uuid": uuid}
