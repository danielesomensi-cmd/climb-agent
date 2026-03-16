"""Supabase JSONB persistence backend.

Selected when STORAGE_BACKEND=supabase (production on Railway).
Tables: users, session_logs, outdoor_logs, event_logs, recovery_codes.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from supabase import create_client

# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_url = os.environ.get("SUPABASE_URL", "")
_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
_client = create_client(_url, _key) if _url and _key else None


def _sb():
    """Return the Supabase client, raising if not configured."""
    if _client is None:
        raise RuntimeError(
            "Supabase not configured: set SUPABASE_URL and SUPABASE_SERVICE_KEY"
        )
    return _client


# ---------------------------------------------------------------------------
# Constants re-exported for backwards compat (deps.py, main.py health check)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("DATA_DIR", str(REPO_ROOT / "backend" / "data")))
STATE_PATH = DATA_DIR / "user_state.json"
USERS_DIR = DATA_DIR / "users"


def _user_state_path(user_id: Optional[str]) -> Path:
    """Backwards compat — still needed by deps._user_state_path."""
    if user_id:
        return USERS_DIR / user_id / "user_state.json"
    return STATE_PATH


def _effective_uid(user_id: Optional[str]) -> str:
    """Map None → '__legacy__' for Supabase (every row needs a user_id)."""
    return user_id or "__legacy__"


# ---------------------------------------------------------------------------
# User state
# ---------------------------------------------------------------------------

def read_state(user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read user state from Supabase. Returns None if not found."""
    uid = _effective_uid(user_id)
    r = _sb().table("users").select("state").eq("user_id", uid).execute()
    if r.data:
        return r.data[0]["state"]
    return None


def write_state(state: Dict[str, Any], user_id: Optional[str] = None) -> None:
    """Upsert user state into Supabase."""
    uid = _effective_uid(user_id)
    _sb().table("users").upsert({"user_id": uid, "state": state}).execute()


def user_state_mtime(user_id: str) -> Optional[float]:
    """Return updated_at as a POSIX timestamp, or None if missing."""
    uid = _effective_uid(user_id)
    r = _sb().table("users").select("updated_at").eq("user_id", uid).execute()
    if r.data:
        ts = r.data[0]["updated_at"]
        dt = datetime.fromisoformat(ts)
        return dt.timestamp()
    return None


# ---------------------------------------------------------------------------
# Session logs
# ---------------------------------------------------------------------------

def read_session_logs(
    user_id: Optional[str],
    since: str = "",
    until: str = "",
) -> List[Dict[str, Any]]:
    """Read indoor session log entries, optionally filtered by date range."""
    uid = _effective_uid(user_id)
    q = _sb().table("session_logs").select("entry").eq("user_id", uid)
    if since:
        q = q.gte("log_date", since)
    if until:
        q = q.lte("log_date", until)
    q = q.order("log_date")
    r = q.execute()
    return [row["entry"] for row in r.data]


def read_recent_session_log_lines(
    user_id: Optional[str],
    max_lines: int = 200,
) -> List[Dict[str, Any]]:
    """Read the last N session log entries (most recent last)."""
    uid = _effective_uid(user_id)
    r = (
        _sb()
        .table("session_logs")
        .select("entry")
        .eq("user_id", uid)
        .order("id", desc=True)
        .limit(max_lines)
        .execute()
    )
    # Reverse so most recent is last (matches file-based behaviour)
    return [row["entry"] for row in reversed(r.data)]


def count_session_log_lines(user_id: Optional[str]) -> int:
    """Count session log entries for a user."""
    uid = _effective_uid(user_id)
    r = (
        _sb()
        .table("session_logs")
        .select("id", count="exact")
        .eq("user_id", uid)
        .execute()
    )
    return r.count or 0


# ---------------------------------------------------------------------------
# Outdoor logs
# ---------------------------------------------------------------------------

def append_outdoor_log_line(user_id: Optional[str], entry: Dict[str, Any]) -> str:
    """Insert an outdoor session. Returns a synthetic path for compat."""
    uid = _effective_uid(user_id)
    session_date = entry.get("date", "")
    _sb().table("outdoor_logs").upsert({
        "user_id": uid,
        "session_date": session_date,
        "entry": entry,
    }).execute()
    # Return a synthetic path so callers that check os.path.isfile don't crash.
    # The outdoor router verifies file existence — we return a token that passes.
    return f"supabase://outdoor_logs/{uid}/{session_date}"


def read_outdoor_logs(
    user_id: Optional[str],
    since_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Read outdoor sessions, sorted by date ascending. No dedup needed (UNIQUE constraint)."""
    uid = _effective_uid(user_id)
    q = _sb().table("outdoor_logs").select("entry").eq("user_id", uid)
    if since_date:
        q = q.gte("session_date", since_date)
    q = q.order("session_date")
    r = q.execute()
    return [row["entry"] for row in r.data]


def outdoor_log_date_exists(user_id: Optional[str], date: str) -> bool:
    """Check if an outdoor log entry exists for a given date."""
    uid = _effective_uid(user_id)
    r = (
        _sb()
        .table("outdoor_logs")
        .select("id")
        .eq("user_id", uid)
        .eq("session_date", date)
        .limit(1)
        .execute()
    )
    return len(r.data) > 0


def remove_outdoor_log_by_date(user_id: Optional[str], date: str) -> int:
    """Delete outdoor entries for a given date. Returns count removed."""
    uid = _effective_uid(user_id)
    r = (
        _sb()
        .table("outdoor_logs")
        .delete()
        .eq("user_id", uid)
        .eq("session_date", date)
        .execute()
    )
    return len(r.data)


def delete_all_outdoor_logs(user_id: Optional[str]) -> int:
    """Delete all outdoor logs for a user. Returns count removed."""
    uid = _effective_uid(user_id)
    r = _sb().table("outdoor_logs").delete().eq("user_id", uid).execute()
    return len(r.data)


# ---------------------------------------------------------------------------
# Event log
# ---------------------------------------------------------------------------

def append_event(user_id: Optional[str], entry: Dict[str, Any]) -> None:
    """Append an event entry."""
    uid = _effective_uid(user_id)
    _sb().table("event_logs").insert({"user_id": uid, "entry": entry}).execute()


# ---------------------------------------------------------------------------
# Recovery codes (global)
# ---------------------------------------------------------------------------

def load_recovery_codes() -> Dict[str, Any]:
    """Read all recovery codes. Returns dict {code: {uuid, created_at}}."""
    r = _sb().table("recovery_codes").select("code, user_id, created_at").execute()
    codes: Dict[str, Any] = {}
    for row in r.data:
        codes[row["code"]] = {
            "uuid": row["user_id"],
            "created_at": row["created_at"][:10] if row.get("created_at") else None,
        }
    return codes


def save_recovery_codes(codes: Dict[str, Any]) -> None:
    """Sync recovery codes to Supabase (truncate + bulk insert)."""
    # Delete all existing codes
    # PostgREST requires a filter for DELETE — use a true-for-all condition
    _sb().table("recovery_codes").delete().neq("code", "").execute()
    # Bulk insert
    if codes:
        rows = [
            {
                "code": code,
                "user_id": info.get("uuid", ""),
                "created_at": info.get("created_at"),
            }
            for code, info in codes.items()
        ]
        _sb().table("recovery_codes").insert(rows).execute()


# ---------------------------------------------------------------------------
# Admin helpers
# ---------------------------------------------------------------------------

def list_user_ids() -> List[str]:
    """Return sorted list of user_ids."""
    r = _sb().table("users").select("user_id").order("user_id").execute()
    return [row["user_id"] for row in r.data if row["user_id"] != "__legacy__"]


def delete_user_data(user_id: str) -> None:
    """Remove all data for a user across all tables."""
    uid = _effective_uid(user_id)
    _sb().table("session_logs").delete().eq("user_id", uid).execute()
    _sb().table("outdoor_logs").delete().eq("user_id", uid).execute()
    _sb().table("event_logs").delete().eq("user_id", uid).execute()
    _sb().table("recovery_codes").delete().eq("user_id", uid).execute()
    _sb().table("users").delete().eq("user_id", uid).execute()
