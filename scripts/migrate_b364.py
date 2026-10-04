#!/usr/bin/env python
"""B364 — prod migration: official max vs working load.

DRY-RUN BY DEFAULT. Nothing is written unless ``--apply`` is passed. It is run
by the main loop after the deploy, never by the implementing session.

What it changes, per user (all deterministic, all idempotent):

(a) working_loads: every entry carrying the B363 ``e2rm_total_kg`` re-base
    of a TESTED athlete (official max from a test log, < 90 days) gets
    ``next_total = last_total + step(last_feedback_label)`` (the B364 kg
    steps, at the entry's own ``last_reps``) and ``e2rm_total_kg`` is popped.
    Untested athletes keep it: it is their pre-B364 progression.
    Daniele 2026-10-04: 4x3 at +30 "ok" → next 108 kg total (@3).
(b) progression_counters.stimulus_exposures: the ONE exposure registry is
    seeded from the hot week plans + ``week_archive`` (A221 moved past weeks
    there) + the ``tests.*`` dates, last 120 days, families finger_max and
    pulling_max (the ones the re-entry ramp reads).
(c) tests.* (hang + pull-up 2RM): ``confidence`` recomputed with the archived
    weeks (low = < 2 exposure days in the 21 days before the test), plus
    ``confidence_basis``, ``delta_pct`` and ``trend`` (stable when |Δ| < 5 %);
    the baselines get the confidence of their test.
(d) custom_sessions: anchored exercises (weighted pull-up / chin-up, max hangs)
    without a ``load_mode`` get ``load_mode: 'anchored'`` (same as the default,
    made explicit).
(e) cs_743c5d6d (Daniele): the false "~65 %" sentence of the max hang note is
    rewritten (+32 kg = 110 kg total = 94.8 % of the 116 kg max), in the library
    and in every NOT-yet-played week-plan copy of that session.
(f) progression_counters: the dead label streaks
    (max_hang_5s_hard_streak / max_hang_5s_easy_streak) are removed.

Never touched: tests/baselines values, done/skipped sessions, feedback,
actual_exercises, timestamps of past sessions.

Safety: --apply takes a verified JSON backup per user first and re-reads the
state after the write (byte-identical check against what was written).

Usage:
  # dry-run, one user (default)
  STORAGE_BACKEND=supabase python scripts/migrate_b364.py --user-id <uuid>
  # dry-run, every user
  STORAGE_BACKEND=supabase python scripts/migrate_b364.py --all
  # dry-run on a JSON state file (no storage at all)
  python scripts/migrate_b364.py --state-file state.json [--archive-file archive.json]
  # real run
  STORAGE_BACKEND=supabase python scripts/migrate_b364.py --user-id <uuid> --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.engine import retest_policy as rp  # noqa: E402
from backend.engine.anchored_load import (  # noqa: E402
    ANCHORED_EXERCISES,
    HANG_LABEL_STEP_KG,
    PULL_EXERCISES,
    PULL_LABEL_STEP_KG,
    PULL_LABEL_STEP_PCT,
    REGISTRY_KEEP_D,
    round_half,
)
from backend.engine.stimulus import (  # noqa: E402
    FAMILY_FINGER_MAX,
    FAMILY_PULLING_MAX,
    exposures,
)

MIGRATION_ID = "B364"
DANIELE_CS = "cs_743c5d6d"
FALSE_NOTE = "INVARIATO. Sub-massimali: 32 kg contro i 48 del working load (~65%)."
TRUE_NOTE = (
    "Carico automatico (B364): il motore calcola il max hang 7\" il giorno della seduta dal "
    "massimale ufficiale (116 kg totali, test 24/09) con tetto di fase e rampa di rientro. "
    "Il vecchio +32 fisso era 110 kg totali = 94,8% del massimale, non ~65%."
)
_TEST_HISTORY = {
    "max_strength": ("total_load_kg", (rp.PROTOCOL_HANG_7S, rp.PROTOCOL_HANG_5S)),
    "pulling_strength": ("total_load_2rm_kg", (rp.PROTOCOL_PULLUP_2RM,)),
}


# ---------------------------------------------------------------------------
# Pure migration (state, archived weeks, today) → (new state, change log)
# ---------------------------------------------------------------------------

def _bw(state: Dict[str, Any]) -> float:
    return float(state.get("bodyweight_kg") or ((state.get("body") or {}).get("weight_kg") or 0.0))


def _step_e2rm_entries(state: Dict[str, Any], today: date, log: List[str]) -> None:
    bw = _bw(state)
    for e in ((state.get("working_loads") or {}).get("entries") or []):
        if not isinstance(e, dict) or "e2rm_total_kg" not in e:
            continue
        eid = str(e.get("exercise_id") or "")
        protocol = rp.EXERCISE_PROTOCOL.get(eid)
        if protocol is None or not rp.is_tested(state, protocol, today):
            # Untested athlete: the e2rm re-base IS their pull-up progression
            # (pre-B364 path, kept bit for bit) — popping it would freeze the
            # prescription back to the baseline. Left untouched.
            log.append(f"(a) working_loads[{e.get('key')}]: untested on {today.isoformat()} — "
                       f"e2rm_total_kg={e.get('e2rm_total_kg')} kept (pre-B364 path)")
            continue
        last_total = e.get("last_total_load_kg")
        if not isinstance(last_total, (int, float)) and isinstance(e.get("last_external_load_kg"), (int, float)):
            last_total = float(e["last_external_load_kg"]) + bw
        label = str(e.get("last_feedback_label") or "ok")
        before = (e.get("next_total_load_kg"), e.get("e2rm_total_kg"))
        if isinstance(last_total, (int, float)):
            if eid in PULL_EXERCISES:
                step = PULL_LABEL_STEP_KG.get(label)
                if step is None:
                    step = round_half(float(last_total) * PULL_LABEL_STEP_PCT.get(label, 0.0))
            else:
                step = HANG_LABEL_STEP_KG.get(label, 0.0)
            nxt = round_half(float(last_total) + step)
            e["next_total_load_kg"] = nxt
            e["next_external_load_kg"] = round_half(nxt - bw)
        e.pop("e2rm_total_kg", None)
        log.append(f"(a) working_loads[{e.get('key')}]: next_total {before[0]} → {e.get('next_total_load_kg')} "
                   f"(@{e.get('last_reps')} reps, label {label}); popped e2rm_total_kg={before[1]}")


def _seed_registry(state: Dict[str, Any], archived: Any, today: date, log: List[str]) -> None:
    since = today - timedelta(days=REGISTRY_KEEP_D)
    counters = state.setdefault("progression_counters", {})
    reg = counters.get("stimulus_exposures") if isinstance(counters.get("stimulus_exposures"), dict) else {}
    seeded: Dict[str, List[Dict[str, Any]]] = {}
    for fam in (FAMILY_FINGER_MAX, FAMILY_PULLING_MAX):
        rows: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for r in exposures(state, since=since, until=today, archived_weeks=archived, families=[fam]):
            if r["source"] == "registry":
                continue
            key = (r["date"], str(r.get("exercise_id") or ""))
            rows[key] = {
                "date": r["date"], "exercise_id": r.get("exercise_id"), "session_id": r.get("session_id"),
                "total_kg": r.get("used_total_load_kg"), "sets_done": r.get("sets_done"),
                "sets_prescribed": r.get("sets_prescribed"), "is_test": bool(r.get("is_test")),
                "evidence": r.get("evidence"), "seeded_by": MIGRATION_ID,
            }
        from backend.engine.anchored_load import _test_dates  # same rule the ramp uses
        for d in _test_dates(state, fam):
            if since.isoformat() <= d <= today.isoformat() and not any(k[0] == d for k in rows):
                rows[(d, "test")] = {"date": d, "exercise_id": None, "is_test": True,
                                     "evidence": "measured", "seeded_by": MIGRATION_ID}
        for r in (reg.get(fam) or []):  # keep rows already written by apply_feedback
            if isinstance(r, dict) and r.get("date"):
                rows[(str(r["date"])[:10], str(r.get("exercise_id") or ""))] = r
        seeded[fam] = sorted(rows.values(), key=lambda r: (str(r["date"]), str(r.get("exercise_id") or "")))
    for fam, rows in reg.items():
        if fam not in seeded:
            seeded[fam] = rows
    if seeded != reg:
        counters["stimulus_exposures"] = seeded
        for fam in (FAMILY_FINGER_MAX, FAMILY_PULLING_MAX):
            log.append(f"(b) stimulus_exposures.{fam}: {[r['date'] for r in seeded.get(fam, [])]}")


def _recompute_tests(state: Dict[str, Any], archived: Any, log: List[str]) -> None:
    tests = state.get("tests") or {}
    for cat, (value_key, protocols) in _TEST_HISTORY.items():
        history = [t for t in (tests.get(cat) or []) if isinstance(t, dict)]
        for t in history:
            if t.get("test_id") not in protocols or not t.get("date"):
                continue
            before = (t.get("confidence"), t.get("trend"))
            conf = rp.test_confidence(state, t, archived_weeks=archived)
            if conf.get("confidence") is None:
                continue
            t["confidence"] = conf["confidence"]
            t["confidence_basis"] = {"exposures": conf["exposures"], "window_start": conf["window_start"],
                                     "window_end": conf["window_end"], "min_required": conf["min_required"],
                                     "computed_by": MIGRATION_ID}
            prev = sorted((h for h in history if h.get("test_id") == t["test_id"]
                           and str(h.get("date") or "") < str(t["date"])
                           and isinstance(h.get(value_key), (int, float))),
                          key=lambda h: str(h.get("date")))
            if prev and isinstance(t.get(value_key), (int, float)) and float(prev[-1][value_key]) > 0:
                delta = round((float(t[value_key]) - float(prev[-1][value_key])) / float(prev[-1][value_key]) * 100, 1)
                t["delta_pct"] = delta
                t["trend"] = "stable" if abs(delta) < 5.0 else ("up" if delta > 0 else "down")
                t["previous_date"] = prev[-1].get("date")
            if (t.get("confidence"), t.get("trend")) != before:
                log.append(f"(c) tests.{cat}[{t['test_id']} {t['date']}]: confidence {before[0]} → "
                           f"{t['confidence']} ({conf['exposures']} exposures {conf['window_start']}..{conf['window_end']}), "
                           f"trend {t.get('trend')} {t.get('delta_pct')}%")
    baselines = state.get("baselines") or {}
    hb = baselines.get("hangboard") or []
    om = rp.official_max(state, rp.PROTOCOL_HANG_7S, "9999-12-31")
    if hb and isinstance(hb[0], dict) and om:
        t = next((x for x in (tests.get("max_strength") or []) if str(x.get("date")) == om["date"]
                  and x.get("confidence")), None)
        if t and hb[0].get("confidence") != t["confidence"]:
            hb[0]["confidence"] = t["confidence"]
            log.append(f"(c) baselines.hangboard[0].confidence → {t['confidence']}")
    pb = baselines.get("pulling")
    om = rp.official_max(state, rp.PROTOCOL_PULLUP_2RM, "9999-12-31")
    if isinstance(pb, dict) and om:
        t = next((x for x in (tests.get("pulling_strength") or []) if str(x.get("date")) == om["date"]
                  and x.get("confidence")), None)
        if t and pb.get("confidence") != t["confidence"]:
            pb["confidence"] = t["confidence"]
            log.append(f"(c) baselines.pulling.confidence → {t['confidence']}")


def _fix_custom(ex: Dict[str, Any], where: str, cs_id: Optional[str], log: List[str]) -> None:
    eid = str(ex.get("exercise_id") or "")
    if eid in ANCHORED_EXERCISES and ex.get("load_mode") not in ("anchored", "fixed"):
        ex["load_mode"] = "anchored"
        log.append(f"(d) {where} {eid}: load_mode → anchored (stored kg {ex.get('load_kg')} kept as reference)")
    if cs_id == DANIELE_CS and eid == "max_hang_7s" and FALSE_NOTE in str(ex.get("notes") or ""):
        ex["notes"] = str(ex["notes"]).replace(FALSE_NOTE, TRUE_NOTE)
        log.append(f"(e) {where} max_hang_7s: false '~65%' note rewritten")


def _fix_customs(state: Dict[str, Any], today: date, log: List[str]) -> None:
    for cs in state.get("custom_sessions") or []:
        if not isinstance(cs, dict):
            continue
        for ex in cs.get("exercises") or []:
            if isinstance(ex, dict):
                _fix_custom(ex, f"custom_sessions[{cs.get('id')}]", cs.get("id"), log)
    plans = list((state.get("week_plans") or {}).items())
    if isinstance(state.get("current_week_plan"), dict):
        plans.append(("current_week_plan", state["current_week_plan"]))
    for key, plan in plans:
        for week in (plan or {}).get("weeks") or []:
            for day in week.get("days") or []:
                d = str(day.get("date") or "")
                if not d or d < today.isoformat():
                    continue  # past days are immutable
                for s in day.get("sessions") or []:
                    if not s.get("custom_session_id") or s.get("status") in ("done", "skipped"):
                        continue
                    for ex in s.get("exercises") or []:
                        if isinstance(ex, dict):
                            _fix_custom(ex, f"week_plans[{key}] {d} {s.get('session_id')}",
                                        s.get("custom_session_id"), log)


def migrate_state(state: Dict[str, Any], archived: Any, today: date) -> Tuple[Dict[str, Any], List[str]]:
    """Pure: returns (migrated copy, human-readable change log). Idempotent."""
    out = deepcopy(state)
    log: List[str] = []
    _step_e2rm_entries(out, today, log)
    _seed_registry(out, archived, today, log)
    _recompute_tests(out, archived, log)
    _fix_customs(out, today, log)
    counters = out.get("progression_counters") or {}
    for k in ("max_hang_5s_hard_streak", "max_hang_5s_easy_streak"):
        if k in counters:
            counters.pop(k)
            log.append(f"(f) progression_counters.{k} removed")
    return out, log


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

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
    archived = _archived_weeks(storage, uid)
    new_state, log = migrate_state(state, archived, today)
    name = ((state.get("user") or {}).get("name") or "").strip()
    print(f"-- {uid} ({name or '?'}): {len(log)} change(s), {len(archived)} archived week(s) read")
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
    ap = argparse.ArgumentParser(description="B364 migration (dry-run by default)")
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--user-id")
    who.add_argument("--all", action="store_true")
    who.add_argument("--state-file", help="migrate a JSON state file offline (prints, never writes)")
    ap.add_argument("--archive-file", help="with --state-file: JSON {week_start: plan} of archived weeks")
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
        archived = json.loads(Path(args.archive_file).read_text(encoding="utf-8")) if args.archive_file else None
        _new, log = migrate_state(state, archived, today)
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
