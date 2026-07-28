"""File-based persistence backend (JSON/JSONL on disk).

Used for local development and testing.
Selected when STORAGE_BACKEND != 'supabase' (default).
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _atomic_write_text(path: Path, content: str) -> None:
    """Write *content* to *path* atomically (write to temp, then rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("DATA_DIR", str(REPO_ROOT / "backend" / "data")))
STATE_PATH = DATA_DIR / "user_state.json"
USERS_DIR = DATA_DIR / "users"


def _user_state_path(user_id: Optional[str]) -> Path:
    """Return the state file path for a given user_id, or the legacy path."""
    if user_id:
        return USERS_DIR / user_id / "user_state.json"
    return STATE_PATH


def _log_dir(user_id: Optional[str]) -> str:
    """Return the log directory for a given user_id, or the legacy path."""
    if user_id:
        return str(USERS_DIR / user_id / "logs")
    return str(DATA_DIR / "logs")


# ---------------------------------------------------------------------------
# User state
# ---------------------------------------------------------------------------

def read_state(user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read user_state.json from disk.

    Returns the parsed dict, or None if the file does not exist or is corrupt.
    """
    path = _user_state_path(user_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_state(state: Dict[str, Any], user_id: Optional[str] = None) -> None:
    """Write user_state.json to disk (atomic)."""
    path = _user_state_path(user_id)
    _atomic_write_text(path, json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def user_state_mtime(user_id: str) -> Optional[float]:
    """Return the mtime of user_state.json, or None if missing."""
    path = _user_state_path(user_id)
    try:
        return path.stat().st_mtime
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Archived week plans (cold store) — A221
#
# Past week_plans are moved out of the hot user_state blob into a per-week
# cold store, read on demand only. One file per archived week.
# ---------------------------------------------------------------------------

def _week_archive_dir(user_id: Optional[str]) -> Path:
    """Directory holding archived week-plan files for a user."""
    if user_id:
        return USERS_DIR / user_id / "week_archive"
    return DATA_DIR / "week_archive"


def archive_week(user_id: Optional[str], week_start: str, plan: Dict[str, Any]) -> None:
    """Write a single week plan into the cold store (atomic, write-once-style).

    Pure move: the caller passes the unmodified plan dict. No resolution or
    regeneration ever happens here.
    """
    path = _week_archive_dir(user_id) / f"{week_start}.json"
    _atomic_write_text(path, json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def read_archived_week(user_id: Optional[str], week_start: str) -> Optional[Dict[str, Any]]:
    """Read a single archived week plan, or None if absent/corrupt."""
    path = _week_archive_dir(user_id) / f"{week_start}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_archived_keys(user_id: Optional[str]) -> List[str]:
    """Return sorted list of archived week_start keys for a user."""
    d = _week_archive_dir(user_id)
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def read_archived_weeks_in_range(
    user_id: Optional[str], start: str, end: str
) -> Dict[str, Dict[str, Any]]:
    """Read all archived weeks whose key falls in [start, end] (inclusive)."""
    out: Dict[str, Dict[str, Any]] = {}
    for key in list_archived_keys(user_id):
        if start <= key <= end:
            plan = read_archived_week(user_id, key)
            if plan is not None:
                out[key] = plan
    return out


def delete_archived_week(user_id: Optional[str], week_start: str) -> bool:
    """Delete a single archived week. Returns True if a file was removed."""
    path = _week_archive_dir(user_id) / f"{week_start}.json"
    try:
        path.unlink()
        return True
    except OSError:
        return False


def delete_all_archived(user_id: Optional[str]) -> int:
    """Delete the entire cold store for a user. Returns count removed."""
    d = _week_archive_dir(user_id)
    if not d.is_dir():
        return 0
    n = 0
    for p in d.glob("*.json"):
        try:
            p.unlink()
            n += 1
        except OSError:
            pass
    return n


# ---------------------------------------------------------------------------
# Session logs (JSONL)
# ---------------------------------------------------------------------------

def _session_log_paths(user_id: Optional[str]) -> List[str]:
    """Return sorted list of sessions_*.jsonl paths for a user."""
    log_dir = _log_dir(user_id)
    if not os.path.isdir(log_dir):
        return []
    return sorted(
        os.path.join(log_dir, fn)
        for fn in os.listdir(log_dir)
        if fn.startswith("sessions_") and fn.endswith(".jsonl")
    )


def read_session_logs(
    user_id: Optional[str],
    since: str = "",
    until: str = "",
) -> List[Dict[str, Any]]:
    """Read indoor session log entries, optionally filtered by date range."""
    sessions: List[Dict[str, Any]] = []
    for path in _session_log_paths(user_id):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    entry_date = entry.get("date", "")
                    if since and entry_date < since:
                        continue
                    if until and entry_date > until:
                        continue
                    sessions.append(entry)
        except OSError:
            continue
    return sessions


def read_recent_session_log_lines(
    user_id: Optional[str],
    max_lines: int = 200,
) -> List[Dict[str, Any]]:
    """Read the last *max_lines* entries from the most recent session JSONL files.

    Returns parsed dicts (most recent last).
    """
    entries: List[Dict[str, Any]] = []
    for path in _session_log_paths(user_id):
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-max_lines:]
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            continue
    return entries[-max_lines:]


def count_session_log_lines(user_id: Optional[str]) -> int:
    """Count total non-empty lines across all session JSONL files for a user."""
    count = 0
    for path in _session_log_paths(user_id):
        try:
            with open(path, "r", encoding="utf-8") as f:
                count += sum(1 for line in f if line.strip())
        except OSError:
            pass
    return count


# ---------------------------------------------------------------------------
# Outdoor logs (JSONL)
# ---------------------------------------------------------------------------

def _outdoor_log_path_for_date(user_id: Optional[str], date_str: str) -> str:
    """Return the outdoor JSONL path for a given date (yearly files)."""
    year = date_str[:4]
    return os.path.join(_log_dir(user_id), f"outdoor_sessions_{year}.jsonl")


def append_outdoor_log_line(user_id: Optional[str], entry: Dict[str, Any]) -> str:
    """Append a single outdoor session entry to the yearly JSONL log.

    Returns the basename of the log file written to.
    Does NOT validate — callers are responsible for validation.
    """
    log_dir = _log_dir(user_id)
    os.makedirs(log_dir, exist_ok=True)
    log_path = _outdoor_log_path_for_date(user_id, entry["date"])
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return log_path


def read_outdoor_logs(
    user_id: Optional[str],
    since_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Read outdoor sessions from JSONL logs.

    When multiple entries exist for the same date (e.g. after an update),
    only the last entry per date is returned.  Sorted by date ascending.
    """
    by_date: Dict[str, Dict[str, Any]] = {}
    log_dir = _log_dir(user_id)
    if not os.path.isdir(log_dir):
        return []

    for fn in sorted(os.listdir(log_dir)):
        if not fn.startswith("outdoor_sessions_") or not fn.endswith(".jsonl"):
            continue
        path = os.path.join(log_dir, fn)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                date = entry.get("date", "")
                if since_date and date < since_date:
                    continue
                by_date[date] = entry  # last entry wins

    return [by_date[d] for d in sorted(by_date)]


def outdoor_log_date_exists(user_id: Optional[str], date: str) -> bool:
    """Check whether an outdoor log entry exists for a given date."""
    log_path = _outdoor_log_path_for_date(user_id, date)
    if not os.path.isfile(log_path):
        return False
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if entry.get("date") == date:
                return True
    return False


def remove_outdoor_log_by_date(user_id: Optional[str], date: str) -> int:
    """Remove all outdoor entries for a given date.  Returns count removed."""
    log_path = _outdoor_log_path_for_date(user_id, date)
    if not os.path.isfile(log_path):
        return 0

    kept: List[str] = []
    removed = 0
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                kept.append(stripped)
                continue
            if entry.get("date") == date:
                removed += 1
            else:
                kept.append(stripped)

    if removed > 0:
        with open(log_path, "w", encoding="utf-8") as f:
            for line in kept:
                f.write(line + "\n")

    return removed


def delete_all_outdoor_logs(user_id: Optional[str]) -> int:
    """Delete all outdoor JSONL files for a user.  Returns count removed."""
    log_dir = _log_dir(user_id)
    removed = 0
    for path in glob.glob(os.path.join(log_dir, "outdoor_sessions_*.jsonl")):
        os.remove(path)
        removed += 1
    return removed


# ---------------------------------------------------------------------------
# Coach messages (A-COACH-V1a) — JSONL, one file per user
# ---------------------------------------------------------------------------

def _coach_messages_path(user_id: Optional[str]) -> str:
    return os.path.join(_log_dir(user_id), "coach_messages.jsonl")


def _read_all_coach_messages(user_id: Optional[str]) -> List[Dict[str, Any]]:
    """Read every coach message row, sorted by created_at ascending."""
    path = _coach_messages_path(user_id)
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    rows.sort(key=lambda r: r.get("created_at", ""))
    return rows


def append_coach_message(
    user_id: Optional[str], role: str, content: str,
    adhoc_session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append a coach chat message. Returns the stored row.

    ``adhoc_session`` (B306): composed adhoc-session payload — persisted so the
    history can re-render the card with its CTA after a reload.
    """
    row: Dict[str, Any] = {
        "id": uuid4().hex,
        "role": role,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if adhoc_session is not None:
        row["adhoc_session"] = adhoc_session
    log_dir = _log_dir(user_id)
    os.makedirs(log_dir, exist_ok=True)
    with open(_coach_messages_path(user_id), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def read_coach_messages(
    user_id: Optional[str],
    limit: int = 50,
    before: Optional[str] = None,
    since: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Read coach messages, newest first.

    ``before``/``since`` filter on the ISO ``created_at`` timestamp
    (exclusive / inclusive respectively).
    """
    rows = _read_all_coach_messages(user_id)
    if since:
        rows = [r for r in rows if r.get("created_at", "") >= since]
    if before:
        rows = [r for r in rows if r.get("created_at", "") < before]
    rows.reverse()
    return rows[: max(0, limit)]


def count_coach_user_messages_since(user_id: Optional[str], since: str) -> int:
    """Count user-role coach messages with created_at >= since (rate limit)."""
    return sum(
        1
        for r in _read_all_coach_messages(user_id)
        if r.get("role") == "user" and r.get("created_at", "") >= since
    )


# ---------------------------------------------------------------------------
# Event log (JSONL)
# ---------------------------------------------------------------------------

def append_event(user_id: Optional[str], entry: Dict[str, Any]) -> None:
    """Append an event entry to events.jsonl."""
    log_dir = _log_dir(user_id)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "events.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Recovery codes (global, not per-user)
# ---------------------------------------------------------------------------

_CODES_PATH = DATA_DIR / "recovery_codes.json"


def load_recovery_codes() -> Dict[str, Any]:
    """Read recovery_codes.json.  Returns empty dict if missing."""
    if _CODES_PATH.exists():
        return json.loads(_CODES_PATH.read_text(encoding="utf-8"))
    return {}


def save_recovery_codes(codes: Dict[str, Any]) -> None:
    """Write recovery_codes.json (atomic)."""
    _atomic_write_text(_CODES_PATH, json.dumps(codes, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Admin helpers
# ---------------------------------------------------------------------------

def list_user_ids() -> List[str]:
    """Return sorted list of user_id strings that have a user_state.json."""
    if not USERS_DIR.is_dir():
        return []
    ids: List[str] = []
    for entry in sorted(USERS_DIR.iterdir()):
        if entry.is_dir() and (entry / "user_state.json").exists():
            ids.append(entry.name)
    return ids


def delete_user_data(user_id: str) -> None:
    """Remove the entire user directory (state + logs + everything)."""
    user_dir = USERS_DIR / user_id
    if user_dir.is_dir():
        shutil.rmtree(user_dir)
