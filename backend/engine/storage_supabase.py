"""Supabase JSONB persistence backend.

Selected when STORAGE_BACKEND=supabase (production on Railway).
Tables: users, session_logs, outdoor_logs, event_logs, recovery_codes,
week_archive, coach_messages.
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
    """Resolve the row key for a request, fail-closed on anonymous access.

    B285/SEC-5: this used to map ``None → '__legacy__'``, so an unauthenticated
    request read a shared bucket instead of being rejected. Writes were already
    guarded (``_require_user_id``); reads were not. Verified before the change:
    zero ``__legacy__`` rows exist in production across users, subscriptions,
    coach_messages and session_logs, so nothing depends on the old mapping.

    ``deps.get_user_id`` now 401s before any handler runs — this raise is the
    backstop for non-HTTP callers (scripts, migrations, jobs).
    """
    if not user_id or user_id == "__legacy__":
        raise ValueError(
            "Cannot read from Supabase without an authenticated user_id. "
            f"Received: {user_id!r}"
        )
    return user_id


def _require_user_id(user_id: Optional[str]) -> str:
    """Validate user_id for write operations — prevent data landing under '__legacy__'.

    In the Supabase backend (production), every write MUST have a real user_id
    from Clerk auth.  If user_id is None or '__legacy__', the Clerk token was
    missing/expired at request time and the write would go to the wrong bucket,
    causing data loss on subsequent reads under the real user_id.
    """
    if user_id is None or user_id == "__legacy__":
        raise ValueError(
            "Cannot write to Supabase without authenticated user_id. "
            f"Received: {user_id!r}"
        )
    return user_id


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
    uid = _require_user_id(user_id)
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
# Archived week plans (cold store) — A221
#
# Past week_plans live in a separate `week_archive` table, read on demand
# only (never loaded by read_state). One row per archived week.
# ---------------------------------------------------------------------------

def archive_week(user_id: Optional[str], week_start: str, plan: Dict[str, Any]) -> None:
    """Upsert a single week plan into the cold store, with read-after-write verify.

    Pure move: the caller passes the unmodified plan dict. Raises OSError if the
    upsert or the verifying read fails — the caller MUST NOT prune the hot copy
    unless this returns cleanly (A221 safety crux: archive-write before hot-prune).
    """
    uid = _require_user_id(user_id)
    # on_conflict targets the (user_id, week_start) unique constraint (not the
    # serial PK) so re-archiving the same week UPDATEs instead of violating the
    # unique key — same class of bug as outdoor_logs (B266).
    result = _sb().table("week_archive").upsert({
        "user_id": uid,
        "week_start": week_start,
        "plan": plan,
    }, on_conflict="user_id,week_start").execute()
    if not result.data:
        raise OSError(
            f"Supabase week_archive upsert returned empty data "
            f"for user={uid}, week_start={week_start}"
        )
    verify = (
        _sb()
        .table("week_archive")
        .select("week_start")
        .eq("user_id", uid)
        .eq("week_start", week_start)
        .limit(1)
        .execute()
    )
    if not verify.data:
        raise OSError(
            f"Supabase week_archive read-after-write failed for "
            f"user={uid}, week_start={week_start}"
        )


def read_archived_week(user_id: Optional[str], week_start: str) -> Optional[Dict[str, Any]]:
    """Read a single archived week plan, or None if absent."""
    uid = _effective_uid(user_id)
    r = (
        _sb()
        .table("week_archive")
        .select("plan")
        .eq("user_id", uid)
        .eq("week_start", week_start)
        .limit(1)
        .execute()
    )
    if r.data:
        return r.data[0]["plan"]
    return None


def list_archived_keys(user_id: Optional[str]) -> List[str]:
    """Return sorted list of archived week_start keys for a user."""
    uid = _effective_uid(user_id)
    r = (
        _sb()
        .table("week_archive")
        .select("week_start")
        .eq("user_id", uid)
        .order("week_start")
        .execute()
    )
    return [row["week_start"] for row in r.data]


def read_archived_weeks_in_range(
    user_id: Optional[str], start: str, end: str
) -> Dict[str, Dict[str, Any]]:
    """Read all archived weeks whose key falls in [start, end] (inclusive)."""
    uid = _effective_uid(user_id)
    r = (
        _sb()
        .table("week_archive")
        .select("week_start, plan")
        .eq("user_id", uid)
        .gte("week_start", start)
        .lte("week_start", end)
        .execute()
    )
    return {row["week_start"]: row["plan"] for row in r.data}


def delete_archived_week(user_id: Optional[str], week_start: str) -> bool:
    """Delete a single archived week. Returns True if a row was removed."""
    uid = _require_user_id(user_id)
    r = (
        _sb()
        .table("week_archive")
        .delete()
        .eq("user_id", uid)
        .eq("week_start", week_start)
        .execute()
    )
    return len(r.data) > 0


def delete_all_archived(user_id: Optional[str]) -> int:
    """Delete the entire cold store for a user. Returns count removed."""
    uid = _require_user_id(user_id)
    r = _sb().table("week_archive").delete().eq("user_id", uid).execute()
    return len(r.data)


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
    """Insert an outdoor session. Returns a synthetic path for compat.

    Raises ValueError if user_id is missing (D134 auth guard).
    Raises OSError if the Supabase upsert returns empty data or read-after-write fails.
    """
    uid = _require_user_id(user_id)
    session_date = entry.get("date", "")

    # on_conflict MUST target the (user_id, session_date) unique constraint, not
    # the table's serial PK. Without it postgrest defaults to the PK and the
    # write degrades to a plain INSERT → a second finish for the same date hits
    # `outdoor_logs_user_id_session_date_key` (23505) and 500s (B266). With it,
    # re-finishing a day idempotently UPDATES that day's log.
    result = _sb().table("outdoor_logs").upsert({
        "user_id": uid,
        "session_date": session_date,
        "entry": entry,
    }, on_conflict="user_id,session_date").execute()

    # D134 Fix A: verify upsert returned data
    if not result.data:
        raise OSError(
            f"Supabase outdoor_log upsert returned empty data "
            f"for user={uid}, date={session_date}"
        )

    # D134 Fix A: read-after-write verification
    verify = (
        _sb()
        .table("outdoor_logs")
        .select("session_date")
        .eq("user_id", uid)
        .eq("session_date", session_date)
        .limit(1)
        .execute()
    )
    if not verify.data:
        raise OSError(
            f"Supabase outdoor_log read-after-write failed: "
            f"data not found after upsert for user={uid}, date={session_date}"
        )

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
    uid = _require_user_id(user_id)
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
    uid = _require_user_id(user_id)
    r = _sb().table("outdoor_logs").delete().eq("user_id", uid).execute()
    return len(r.data)


# ---------------------------------------------------------------------------
# Coach messages (A-COACH-V1a)
# ---------------------------------------------------------------------------

def append_coach_message(
    user_id: Optional[str], role: str, content: str,
    adhoc_session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Insert a coach chat message. Returns the stored row.

    ``adhoc_session`` (B306): the composed adhoc-session preview payload for
    assistant turns that built one — persisted so the history can re-render
    the card (with its CTA) after a reload instead of only the text summary.
    """
    uid = _require_user_id(user_id)
    row: Dict[str, Any] = {"user_id": uid, "role": role, "content": content}
    if adhoc_session is not None:
        row["adhoc_session"] = adhoc_session
    r = _sb().table("coach_messages").insert(row).execute()
    if r.data:
        return r.data[0]
    return {"role": role, "content": content}


def read_coach_messages(
    user_id: Optional[str],
    limit: int = 50,
    before: Optional[str] = None,
    since: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Read coach messages, newest first (paginate with ``before``)."""
    uid = _effective_uid(user_id)
    q = (
        _sb()
        .table("coach_messages")
        .select("id, role, content, created_at, adhoc_session")
        .eq("user_id", uid)
    )
    if since:
        q = q.gte("created_at", since)
    if before:
        q = q.lt("created_at", before)
    r = q.order("created_at", desc=True).limit(max(0, limit)).execute()
    return r.data or []


def count_coach_user_messages_since(user_id: Optional[str], since: str) -> int:
    """Count user-role coach messages with created_at >= since (rate limit)."""
    uid = _effective_uid(user_id)
    r = (
        _sb()
        .table("coach_messages")
        .select("id")
        .eq("user_id", uid)
        .eq("role", "user")
        .gte("created_at", since)
        .execute()
    )
    return len(r.data or [])


# ---------------------------------------------------------------------------
# Event log
# ---------------------------------------------------------------------------

def append_event(user_id: Optional[str], entry: Dict[str, Any]) -> None:
    """Append an event entry."""
    uid = _require_user_id(user_id)
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
    uid = _require_user_id(user_id)
    _sb().table("session_logs").delete().eq("user_id", uid).execute()
    _sb().table("coach_messages").delete().eq("user_id", uid).execute()
    _sb().table("outdoor_logs").delete().eq("user_id", uid).execute()
    _sb().table("event_logs").delete().eq("user_id", uid).execute()
    _sb().table("recovery_codes").delete().eq("user_id", uid).execute()
    _sb().table("week_archive").delete().eq("user_id", uid).execute()
    _sb().table("users").delete().eq("user_id", uid).execute()
