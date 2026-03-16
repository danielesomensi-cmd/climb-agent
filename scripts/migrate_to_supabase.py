#!/usr/bin/env python3
"""One-shot migration: Railway volume → Supabase.

Reads user data from the filesystem (DATA_DIR / Railway volume) and inserts
it into Supabase tables.

Usage:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/migrate_to_supabase.py [user_id ...]

If no user_ids are specified, migrates ALL users found in the volume.

Environment:
    DATA_DIR            Path to data directory (default: backend/data)
    SUPABASE_URL        Supabase project URL
    SUPABASE_SERVICE_KEY Supabase service role key
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("DATA_DIR", str(REPO_ROOT / "backend" / "data")))
USERS_DIR = DATA_DIR / "users"

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

from supabase import create_client  # noqa: E402

_url = os.environ.get("SUPABASE_URL", "")
_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
if not _url or not _key:
    print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars")
    sys.exit(1)

sb = create_client(_url, _key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file and return list of parsed dicts."""
    entries = []
    if not path.exists():
        return entries
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def migrate_user(user_id: str) -> dict:
    """Migrate a single user. Returns summary dict."""
    user_dir = USERS_DIR / user_id
    summary = {"user_id": user_id, "state": False, "sessions": 0, "outdoor": 0, "events": 0}

    # 1. user_state.json → users table
    state_path = user_dir / "user_state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            sb.table("users").upsert({"user_id": user_id, "state": state}).execute()
            summary["state"] = True
        except Exception as e:
            print(f"  WARN: state failed for {user_id}: {e}")

    # 2. sessions_*.jsonl → session_logs table
    logs_dir = user_dir / "logs"
    if logs_dir.is_dir():
        session_entries = []
        for fn in sorted(logs_dir.iterdir()):
            if fn.name.startswith("sessions_") and fn.suffix == ".jsonl":
                for entry in _read_jsonl(fn):
                    log_date = entry.get("date", "2026-01-01")
                    session_entries.append({
                        "user_id": user_id,
                        "log_date": log_date,
                        "entry": entry,
                    })

        if session_entries:
            # Bulk insert in batches of 100
            for i in range(0, len(session_entries), 100):
                batch = session_entries[i:i+100]
                sb.table("session_logs").insert(batch).execute()
            summary["sessions"] = len(session_entries)

        # 3. outdoor_sessions_*.jsonl → outdoor_logs table
        outdoor_entries = []
        for fn in sorted(logs_dir.iterdir()):
            if fn.name.startswith("outdoor_sessions_") and fn.suffix == ".jsonl":
                for entry in _read_jsonl(fn):
                    session_date = entry.get("date", "2026-01-01")
                    outdoor_entries.append({
                        "user_id": user_id,
                        "session_date": session_date,
                        "entry": entry,
                    })

        if outdoor_entries:
            # Deduplicate by date (keep last, matching file-based behaviour)
            by_date = {}
            for e in outdoor_entries:
                by_date[e["session_date"]] = e
            deduped = list(by_date.values())

            for i in range(0, len(deduped), 100):
                batch = deduped[i:i+100]
                sb.table("outdoor_logs").upsert(batch).execute()
            summary["outdoor"] = len(deduped)

        # 4. events.jsonl → event_logs table
        events_path = logs_dir / "events.jsonl"
        event_entries = []
        for entry in _read_jsonl(events_path):
            event_entries.append({
                "user_id": user_id,
                "entry": entry,
            })

        if event_entries:
            for i in range(0, len(event_entries), 100):
                batch = event_entries[i:i+100]
                sb.table("event_logs").insert(batch).execute()
            summary["events"] = len(event_entries)

    return summary


def migrate_recovery_codes() -> int:
    """Migrate recovery_codes.json → recovery_codes table."""
    codes_path = DATA_DIR / "recovery_codes.json"
    if not codes_path.exists():
        return 0

    codes = json.loads(codes_path.read_text(encoding="utf-8"))
    if not codes:
        return 0

    rows = [
        {
            "code": code,
            "user_id": info.get("uuid", ""),
            "created_at": info.get("created_at"),
        }
        for code, info in codes.items()
    ]

    # Upsert to avoid conflicts on re-run
    sb.table("recovery_codes").upsert(rows).execute()
    return len(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Determine which users to migrate
    if len(sys.argv) > 1:
        user_ids = sys.argv[1:]
    else:
        # Discover all users in the volume
        if not USERS_DIR.is_dir():
            print(f"No users directory at {USERS_DIR}")
            sys.exit(1)
        user_ids = sorted(
            d.name for d in USERS_DIR.iterdir()
            if d.is_dir() and (d / "user_state.json").exists()
        )

    if not user_ids:
        print("No users found to migrate.")
        sys.exit(0)

    print(f"Migrating {len(user_ids)} user(s) from {DATA_DIR} → Supabase")
    print(f"Supabase URL: {_url}")
    print()

    results = []
    for uid in user_ids:
        print(f"  Migrating {uid} ...")
        try:
            summary = migrate_user(uid)
            results.append(summary)
            status = "✓" if summary["state"] else "✗"
            print(f"    {status} state={summary['state']}, sessions={summary['sessions']}, "
                  f"outdoor={summary['outdoor']}, events={summary['events']}")
        except Exception as e:
            print(f"    ✗ FAILED: {e}")
            results.append({"user_id": uid, "error": str(e)})

    # Recovery codes
    print()
    n_codes = migrate_recovery_codes()
    print(f"  Recovery codes: {n_codes}")

    # Summary
    print()
    print("=" * 60)
    print(f"Migrated: {sum(1 for r in results if r.get('state'))} / {len(results)} users")
    total_sessions = sum(r.get("sessions", 0) for r in results)
    total_outdoor = sum(r.get("outdoor", 0) for r in results)
    print(f"Total session logs: {total_sessions}")
    print(f"Total outdoor logs: {total_outdoor}")
    print(f"Recovery codes: {n_codes}")


if __name__ == "__main__":
    main()
