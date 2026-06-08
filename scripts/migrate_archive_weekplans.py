#!/usr/bin/env python
"""A221 — controlled migration: move past week_plans into the cold store.

This is the explicit, observed "controlled run" (flag OFF). It does NOT rely on
the lazy WEEKPLAN_ARCHIVE_LAZY trigger — it archives a single user's past weeks
deterministically, with a verified backup taken first and a byte-identical
read-back check afterwards.

Backend is chosen by STORAGE_BACKEND (file | supabase), exactly like the app:
  - Local proof on a copy:   STORAGE_BACKEND=file  DATA_DIR=/tmp/...
  - Real production run:      STORAGE_BACKEND=supabase (+ prod SUPABASE_* creds)

Safety model (A221 RULE #1 — Daniele's macrocycle must not be lost):
  1. Backup the FULL state to a timestamped JSON file and re-read it to verify
     it is restorable BEFORE touching anything.
  2. Optional name/uid asserts (--expect-name, --expect-uid) — hard gate.
  3. archive_past_weeks is a pure move with write-verify-before-prune.
  4. After the move: every archived week must read back byte-identical to the
     backup, the hot copy must no longer contain it, and the recency exercise
     list must be unchanged. Any mismatch → abort with non-zero exit (the
     archive layer never deletes the hot copy unless its own write verified, so
     no data is lost even on abort).

Dry-run (default) prints the plan and writes nothing.

Rollback:
  STORAGE_BACKEND=... python scripts/migrate_archive_weekplans.py \
      --user-id <uid> --rollback --backup <path-to-backup.json>
  → restores the backed-up state verbatim and deletes the user's archive rows.

Usage:
  # dry-run (no writes)
  STORAGE_BACKEND=file DATA_DIR=/tmp/proof python scripts/migrate_archive_weekplans.py \
      --user-id 7ea9f0ee-... --expect-name daniele

  # real run (writes)
  STORAGE_BACKEND=supabase python scripts/migrate_archive_weekplans.py \
      --user-id 7ea9f0ee-... --expect-name daniele --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root on path when run as a script
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.api import deps  # noqa: E402
from backend.engine import storage  # noqa: E402
from backend.engine.resolve_session import load_recent_exercise_ids  # noqa: E402


def _state_bytes(state: dict) -> int:
    return len(json.dumps(state.get("week_plans") or {}))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _backup(state: dict, user_id: str, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"backup_{user_id}_{_ts()}.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    # Verify the backup is restorable before touching anything.
    reread = json.loads(path.read_text(encoding="utf-8"))
    if reread != state:
        raise SystemExit(f"FATAL: backup verify failed — {path} does not match live state")
    return path


def _do_rollback(user_id: str, backup_path: Path) -> int:
    if not backup_path.exists():
        raise SystemExit(f"FATAL: backup file not found: {backup_path}")
    backup_state = json.loads(backup_path.read_text(encoding="utf-8"))
    print(f"↩  Rollback: restoring state for {user_id} from {backup_path}")
    storage.write_state(backup_state, user_id)
    removed = storage.delete_all_archived(user_id)
    print(f"   restored hot state ({len(backup_state.get('week_plans') or {})} weeks), "
          f"deleted {removed} archive rows")
    after = storage.read_state(user_id)
    if after != backup_state:
        raise SystemExit("FATAL: rollback verify failed — restored state != backup")
    print("✅ Rollback verified (state == backup).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="A221 controlled archive migration")
    ap.add_argument("--user-id", required=True)
    ap.add_argument("--expect-name", default=None,
                    help="assert state.user.name (case-insensitive) starts with this")
    ap.add_argument("--expect-uid", default=None, help="assert user_id == this")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry-run)")
    ap.add_argument("--backup-dir", default=str(REPO_ROOT / "_backups"))
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--backup", default=None, help="backup file path (for --rollback)")
    args = ap.parse_args()

    uid = args.user_id
    backend = storage.__name__
    print(f"== A221 migration ==  backend={backend}  user={uid}  "
          f"mode={'APPLY' if args.apply else 'DRY-RUN'}")

    if args.rollback:
        if not args.backup:
            raise SystemExit("--rollback requires --backup <path>")
        return _do_rollback(uid, Path(args.backup))

    # ── load + guard ────────────────────────────────────────────────────────
    state = storage.read_state(uid)
    if state is None:
        raise SystemExit(f"FATAL: no state found for user {uid}")

    name = ((state.get("user") or {}).get("name") or "").strip().lower()
    if args.expect_uid and uid != args.expect_uid:
        raise SystemExit(f"FATAL: uid guard failed: {uid} != {args.expect_uid}")
    if args.expect_name and not name.startswith(args.expect_name.strip().lower()):
        raise SystemExit(f"FATAL: name guard failed: state name={name!r} "
                         f"does not start with {args.expect_name!r}")
    print(f"   guard OK (name={name!r})")

    week_plans = state.get("week_plans") or {}
    floor = deps.hot_floor()
    to_archive = sorted(k for k in week_plans if isinstance(k, str) and k < floor)
    keep_hot = sorted(k for k in week_plans if k not in to_archive)
    size_before = _state_bytes(state)
    recency_before = load_recent_exercise_ids(uid, user_state=state)

    print(f"   hot_floor (boundary) = {floor}")
    print(f"   week_plans total     = {len(week_plans)}  ({size_before/1024:.1f} KB)")
    print(f"   to archive (< N-1)   = {len(to_archive)}: {to_archive}")
    print(f"   keep hot ({{N-1,N,+}}) = {len(keep_hot)}: {keep_hot}")

    if not args.apply:
        print("\nDRY-RUN: no writes performed. Re-run with --apply to execute.")
        return 0

    # ── backup-first ────────────────────────────────────────────────────────
    backup_path = _backup(state, uid, Path(args.backup_dir))
    print(f"   ✅ backup written + verified: {backup_path}")

    # ── pure move (write-verify-prune inside archive_past_weeks) ─────────────
    moved = deps.archive_past_weeks(state, uid)
    storage.write_state(state, uid)
    print(f"   archived {moved} week(s); hot now {len(state.get('week_plans') or {})} weeks")

    # ── verification ────────────────────────────────────────────────────────
    backup_state = json.loads(backup_path.read_text(encoding="utf-8"))
    backup_weeks = backup_state.get("week_plans") or {}
    persisted = storage.read_state(uid)
    errors = []

    # 1. every archived week reads back byte-identical to the backup
    for k in to_archive:
        got = storage.read_archived_week(uid, k)
        if got != backup_weeks.get(k):
            errors.append(f"archived week {k} != backup (byte mismatch)")
        if k in (persisted.get("week_plans") or {}):
            errors.append(f"archived week {k} still present in hot state")

    # 2. kept-hot weeks unchanged
    for k in keep_hot:
        if (persisted.get("week_plans") or {}).get(k) != backup_weeks.get(k):
            errors.append(f"kept-hot week {k} changed during migration")

    # 3. recency determinism
    recency_after = load_recent_exercise_ids(uid, user_state=persisted)
    if recency_after != recency_before:
        errors.append("recency exercise list changed (determinism broken)")

    size_after = _state_bytes(persisted)
    if errors:
        print("\n❌ VERIFICATION FAILED:")
        for e in errors:
            print(f"   - {e}")
        print(f"\nBackup is at {backup_path}. Rollback with:")
        print(f"   STORAGE_BACKEND=... python scripts/migrate_archive_weekplans.py "
              f"--user-id {uid} --rollback --backup {backup_path}")
        return 2

    print("\n✅ VERIFICATION PASSED")
    print(f"   archived weeks read back byte-identical: {len(to_archive)}")
    print(f"   recency unchanged: {len(recency_before)} ids")
    print(f"   hot week_plans: {size_before/1024:.1f} KB → {size_after/1024:.1f} KB "
          f"({(1 - size_after/size_before)*100:.0f}% smaller)" if size_before else "")
    print(f"   backup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
