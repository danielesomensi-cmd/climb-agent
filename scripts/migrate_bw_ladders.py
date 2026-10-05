#!/usr/bin/env python
"""A298 — prod migration: bodyweight ladders on the existing custom sessions.

DRY-RUN BY DEFAULT. Nothing is written unless ``--apply`` is passed. It is run
by the main loop after the deploy (with Daniele's OK on the dry-run output),
never by the implementing session.

What it does, per TESTED user (official max from a test log < 90 days — the
same gate as the engine; untested users are reported and left untouched):

(a) prints the level of every bodyweight family on ``--today`` — persisted
    ``bw_progression`` entry, else the read-time seed (history: last clean dose
    − 1 step; else the L-sit test). The seed is NOT written: the engine derives
    it at read time and persists an entry only on the first feedback that
    moves it;
(b) custom_sessions: every row that is a level of a bodyweight ladder and has
    no ``progress_mode`` gets ``progress_mode: 'ladder'`` (rows saved before
    A298 are 'fixed' by default), in the library and in every NOT-yet-played
    week-plan copy of that session (date ≥ today, status not done/skipped).
    A row the user set to 'fixed' stays 'fixed'.

Never touched: done / skipped / past sessions, feedback, tests, baselines,
working_loads.

Usage (same flags as migrate_b364.py):
  STORAGE_BACKEND=supabase python scripts/migrate_bw_ladders.py --user-id <uuid>
  python scripts/migrate_bw_ladders.py --state-file state.json --today 2026-10-06
  STORAGE_BACKEND=supabase python scripts/migrate_bw_ladders.py --user-id <uuid> --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.engine import bw_ladders as bl  # noqa: E402
from backend.engine import bw_progression as bp  # noqa: E402

MIGRATION_ID = "A298"


def _mark_rows(rows: Any, where: str, today: date, log: List[str]) -> None:
    for i, r in enumerate(rows or []):
        if not isinstance(r, dict) or r.get("progress_mode") is not None:
            continue
        if bl.family_of(str(r.get("exercise_id") or ""), today):
            r["progress_mode"] = "ladder"
            log.append(f"{where}[{i}] {r.get('exercise_id')}: progress_mode → ladder")


def migrate_state(state: Dict[str, Any], archived: Any, today: date) -> Tuple[Dict[str, Any], List[str]]:
    new = deepcopy(state)
    log: List[str] = []
    if not bp.tested(new, today):
        return new, []
    for name, e in sorted(bp.entries_for(new, today, archived_weeks=archived).items()):
        dose = bp.dose_for(bp.effective_entry(e, bp.family_doc(name), today), bp.family_doc(name),
                           phase=bp.phase_on(new, today))
        print(f"   level {name}: L{e['level_idx']} {e['exercise_id']} {dose['summary']} [{e.get('source')}]")
    ids = set()
    for cs in new.get("custom_sessions") or []:
        if isinstance(cs, dict):
            ids.add(str(cs.get("id")))
            _mark_rows(cs.get("exercises"), f"custom {cs.get('id')}", today, log)
    for key, plan in sorted((new.get("week_plans") or {}).items()):
        for week in (plan or {}).get("weeks") or []:
            for d in week.get("days") or []:
                if str(d.get("date") or "") < today.isoformat():
                    continue
                for s in d.get("sessions") or []:
                    sid = str(s.get("session_id") or "")
                    if not sid.startswith("custom_") or sid[len("custom_"):] not in ids:
                        continue
                    if s.get("status") in ("done", "skipped"):
                        continue
                    _mark_rows(s.get("exercises"), f"week {key} {d.get('date')} {sid}", today, log)
    return new, log


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _archived_weeks(storage: Any, uid: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in storage.list_archived_keys(uid):
        plan = storage.read_archived_week(uid, key)
        if isinstance(plan, dict):
            out[key] = plan
    return out


def _run_one(storage: Any, uid: str, today: date, apply: bool, backup_dir: Path) -> int:
    state = storage.read_state(uid)
    if not state:
        print(f"-- {uid}: no state, skipped")
        return 0
    name = ((state.get("user") or {}).get("name") or "").strip()
    print(f"-- {uid} ({name or '?'}): tested={bp.tested(state, today)}")
    archived = _archived_weeks(storage, uid)
    new_state, log = migrate_state(state, archived, today)
    print(f"   {len(log)} change(s)")
    for line in log:
        print(f"   {line}")
    if not log or not apply:
        return 0
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"backup_{MIGRATION_ID}_{uid}_{_ts()}.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if json.loads(path.read_text(encoding="utf-8")) != state:
        raise SystemExit(f"FATAL: backup verify failed for {uid} ({path})")
    storage.write_state(new_state, uid)
    if storage.read_state(uid) != new_state:
        raise SystemExit(f"FATAL: read-back mismatch for {uid} — restore from {path}")
    print(f"   APPLIED (backup {path})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="A298 migration (dry-run by default)")
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--user-id")
    who.add_argument("--all", action="store_true")
    who.add_argument("--state-file", help="migrate a JSON state file offline (prints, never writes)")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD (default: today, UTC)")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="explicit dry-run (the default)")
    ap.add_argument("--backup-dir", default=str(REPO_ROOT / "_backups"))
    args = ap.parse_args()
    if args.apply and args.dry_run:
        raise SystemExit("--apply and --dry-run are mutually exclusive")
    today = (datetime.strptime(args.today, "%Y-%m-%d").date() if args.today
             else datetime.now(timezone.utc).date())
    print(f"== {MIGRATION_ID} migration == mode={'APPLY' if args.apply else 'DRY-RUN'} today={today}")
    if args.state_file:
        if args.apply:
            raise SystemExit("--state-file is offline only: no --apply")
        raw = json.loads(Path(args.state_file).read_text(encoding="utf-8"))
        state = raw[0]["state"] if isinstance(raw, list) else raw.get("state", raw)
        _new, log = migrate_state(state, None, today)
        print(f"-- state file: {len(log)} change(s)")
        for line in log:
            print(f"   {line}")
        return 0
    from backend.engine import storage

    uids = storage.list_user_ids() if args.all else [args.user_id]
    for uid in uids:
        _run_one(storage, uid, today, args.apply, Path(args.backup_dir))
    if not args.apply:
        print("\nDRY-RUN: nothing written. Re-run with --apply to execute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
