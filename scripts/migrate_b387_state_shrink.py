#!/usr/bin/env python3
"""B387 — one-off migration: lean custom exercises + current_week_plan pointer.

For every user row in Supabase ``users``:

1. custom sessions → every exercise in ``custom_session.storage_form`` (catalog
   display fields dropped only where the read path re-derives them exactly);
2. the blob is written through ``state_codec.pack`` (``current_week_plan``
   becomes ``current_week_key`` when it duplicates the hot week).

Nothing else changes: week plans (past or future), logs, loads, feedback are
untouched — the gate below fails the user if any other key differs.

**Lossless gate, per user** (a user that fails is skipped and reported):
- every key other than ``custom_sessions`` is identical after the change;
- every custom session keeps its non-exercise fields, and each exercise plays
  identically through the real read path — the B283 enrichment and, for
  ``--date``, the full GET-detail pipeline (anchored loads, ladder rows,
  technique measures, measure fields, limit targets);
- ``unpack(json(pack(new)))`` == ``new`` (the codec round trip).

Default is a dry run (prints sizes, writes nothing). ``--apply``:
- writes the full original rows to ``--backup-dir`` first (personal data: the
  default lives under ~/backups, never in the repo) and re-reads the backup;
- PATCHes each row filtered on its ``updated_at`` (optimistic lock: a row the
  app wrote in the meantime is left alone and reported);
- re-reads the row and checks ``unpack(row) == new``.
``--rollback`` restores every row from the backup directory.

Usage::

    python scripts/migrate_b387_state_shrink.py                  # dry run, all users
    python scripts/migrate_b387_state_shrink.py --apply
    python scripts/migrate_b387_state_shrink.py --rollback --backup-dir ~/backups/b387-2026-10-17
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.athlete_context import load_credentials  # noqa: E402
from backend.api.routers import custom_session as cs  # noqa: E402
from backend.engine import state_codec  # noqa: E402
from backend.engine.anchored_load import resolve_custom_exercises  # noqa: E402
from backend.engine.bw_progression import attach_technique_measures, resolve_custom_ladder_rows  # noqa: E402
from backend.engine.measured_feedback import attach_measure_fields  # noqa: E402


def _req(method: str, path: str, body: Any = None, prefer: Optional[str] = None) -> Any:
    base, key = load_credentials()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{base}/rest/v1/{path}", data=data, method=method, headers=headers)
    with urllib.request.urlopen(r, timeout=120) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else None


def fetch_rows(user: Optional[str]) -> List[Dict[str, Any]]:
    q = [("select", "user_id,state,updated_at"), ("order", "user_id.asc")]
    if user:
        q.append(("user_id", f"eq.{user}"))
    return _req("GET", "users?" + urllib.parse.urlencode(q)) or []


def _detail_views(state: dict, session: dict, day: str) -> List[dict]:
    """What GET /api/custom-session/{id} serves, without and with ``?date=``."""
    plain = cs.enrich_custom_sessions_for_play([session])[0]
    plain["exercises"] = attach_measure_fields(state, plain.get("exercises") or [], None)
    dated = cs.enrich_custom_sessions_for_play([session])[0]
    ex = resolve_custom_exercises(state, dated.get("exercises") or [], day)
    ex = resolve_custom_ladder_rows(state, ex, day)
    ex = attach_technique_measures(state, ex, day)
    ex = attach_measure_fields(state, ex, day)
    ex = cs.attach_limit_targets(state, ex, day)
    dated["exercises"] = ex
    return [plain, dated]


_DISPLAY = set(cs.STORED_DISPLAY_KEYS)


def _refresh_form(ex: dict) -> dict:
    """``--refresh-display``: drop the display fields unconditionally, so the read
    path shows the CURRENT catalog (fixed cues, renamed exercises, B380 unit).
    User input is untouched; the gate still checks it field by field."""
    lean = {k: v for k, v in ex.items() if k not in _DISPLAY}
    cat_ex = cs._load_exercises_catalog().get(ex.get("exercise_id") or "") or {}
    default_notes = (cat_ex.get("prescription_defaults") or {}).get("notes")
    if default_notes and lean.get("notes") == default_notes:
        lean.pop("notes")
    return lean


def _strip_display(views: List[dict]) -> List[dict]:
    out = []
    for v in views:
        v = dict(v)
        v["exercises"] = [{k: x for k, x in e.items() if k not in _DISPLAY} for e in v.get("exercises") or []]
        out.append(v)
    return out


def _display_changes(old_views: List[dict], new_views: List[dict]) -> List[str]:
    keys = []
    for ov, nv in zip(old_views[:1], new_views[:1]):
        for oe, ne in zip(ov.get("exercises") or [], nv.get("exercises") or []):
            keys += [k for k in _DISPLAY if oe.get(k) != ne.get(k)]
    return keys


DISPLAY_CHANGES: Dict[str, int] = {}


def migrate_state(state: dict, day: str, refresh_display: bool = False) -> Tuple[dict, List[str]]:
    """``(new_state, problems)`` — problems empty means the gate passed.

    Strict (default): an exercise is made lean only if it plays identically
    (``custom_session.storage_form``). ``refresh_display``: the display fields
    are re-derived from the current catalog; the gate then checks everything
    BUT the display fields, and the display changes are counted for the report."""
    problems: List[str] = []
    new = deepcopy(state)
    customs = state.get("custom_sessions")
    if isinstance(customs, list):
        if refresh_display:
            new["custom_sessions"] = [
                dict(c, exercises=[_refresh_form(dict(e)) for e in c.get("exercises") or []]) if isinstance(c, dict) else c
                for c in customs]
        else:
            new["custom_sessions"] = [cs.stored_session(c) if isinstance(c, dict) else c for c in customs]
    for k in set(state) | set(new):
        if k != "custom_sessions" and state.get(k) != new.get(k):
            problems.append(f"key {k} changed")
    for old_cs, new_cs in zip(customs or [], new.get("custom_sessions") or []):
        if not isinstance(old_cs, dict):
            continue
        sid = old_cs.get("id")
        if {k: v for k, v in old_cs.items() if k != "exercises"} != {k: v for k, v in new_cs.items() if k != "exercises"}:
            problems.append(f"{sid}: session fields changed")
        if len(old_cs.get("exercises") or []) != len(new_cs.get("exercises") or []):
            problems.append(f"{sid}: exercise count changed")
        try:
            ov, nv = _detail_views(state, old_cs, day), _detail_views(new, new_cs, day)
            if refresh_display:
                if _strip_display(ov) != _strip_display(nv):
                    problems.append(f"{sid}: user fields differ in the detail view")
                for k in _display_changes(ov, nv):
                    DISPLAY_CHANGES[k] = DISPLAY_CHANGES.get(k, 0) + 1
            elif ov != nv:
                problems.append(f"{sid}: detail view differs")
        except Exception as exc:  # a session the read path cannot serve stays as it is
            problems.append(f"{sid}: read path raised {exc!r}")
    back = state_codec.unpack(json.loads(json.dumps(state_codec.pack(new))))
    if back != new:
        problems.append("codec round trip differs")
    return new, problems


def _size(obj: Any) -> int:
    return len(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--user")
    ap.add_argument("--refresh-display", action="store_true",
                    help="re-derive name/cues/unit from the current catalog (needs Daniele's OK)")
    ap.add_argument("--date", default=date.today().isoformat(), help="day for the dated detail view check")
    ap.add_argument("--backup-dir", default=str(Path.home() / "backups" / f"b387-{date.today().isoformat()}"))
    args = ap.parse_args()
    bdir = Path(args.backup_dir).expanduser()

    if args.rollback:
        files = sorted(bdir.glob("*.json"))
        for f in files:
            row = json.loads(f.read_text(encoding="utf-8"))
            if args.user and row["user_id"] != args.user:
                continue
            _req("PATCH", f"users?user_id=eq.{row['user_id']}", {"state": row["state"]}, prefer="return=minimal")
            print(f"restored {row['user_id']}")
        return 0

    if args.apply and not state_codec.pack_enabled():
        print("STATE_CODEC_PACK=0 in the environment: refusing to apply (nothing would be packed)")
        return 1

    rows = fetch_rows(args.user)
    total_before = total_after = 0
    plan: List[Tuple[dict, dict]] = []
    skipped: List[Tuple[str, List[str]]] = []
    for row in rows:
        uid, raw = row["user_id"], row.get("state")
        if not isinstance(raw, dict):
            continue
        state = state_codec.unpack(deepcopy(raw))
        new, problems = migrate_state(state, args.date, refresh_display=args.refresh_display)
        stored = state_codec.pack(new)
        b, a = _size(raw), _size(stored)
        if problems:
            skipped.append((uid, problems))
            print(f"SKIP {uid[:8]}  {b/1024:7.1f} KB  — {'; '.join(problems[:3])}")
            continue
        if stored == raw:
            print(f"same {uid[:8]}  {b/1024:7.1f} KB")
            continue
        total_before += b
        total_after += a
        plan.append((row, new))
        print(f"ok   {uid[:8]}  {b/1024:7.1f} → {a/1024:7.1f} KB")
    if DISPLAY_CHANGES:
        print(f"display fields re-derived (exercise count per field): {dict(sorted(DISPLAY_CHANGES.items()))}")
    print(f"\n{len(plan)} to write, {len(skipped)} skipped; "
          f"{total_before/1024:.1f} → {total_after/1024:.1f} KB on the rows that change")
    if not args.apply:
        print("dry run: nothing written")
        return 0 if not skipped else 2

    bdir.mkdir(parents=True, exist_ok=True)
    for row, _new in plan:
        f = bdir / f"{row['user_id']}.json"
        f.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
        if json.loads(f.read_text(encoding="utf-8")) != row:
            print(f"backup verify failed for {row['user_id']}: aborting before any write")
            return 1
    print(f"backups: {bdir}")

    failed = 0
    for row, new in plan:
        uid = row["user_id"]
        ts = urllib.parse.quote(row["updated_at"], safe="")
        out = _req("PATCH", f"users?user_id=eq.{uid}&updated_at=eq.{ts}",
                   {"state": state_codec.pack(new)}, prefer="return=representation")
        if not out:
            failed += 1
            print(f"LOCK {uid[:8]}: the row changed since the read — left alone")
            continue
        persisted = fetch_rows(uid)[0]["state"]
        if state_codec.unpack(deepcopy(persisted)) != new:
            failed += 1
            print(f"VERIFY FAILED {uid[:8]}: restore with --rollback --user {uid}")
            continue
        print(f"written {uid[:8]}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
