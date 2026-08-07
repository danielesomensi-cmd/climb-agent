#!/usr/bin/env python3
"""Export a climb-agent user_state into health-vault's training_log.csv.

Turns one climb-agent backup (the JSON from GET /api/user/export, i.e. the
"Download backup" button) into the append-only row-per-session CSV the
health-vault repo joins against daily_log.md for HRV/sleep correlation.

    python scripts/export_training_log.py backup.json > training_log.csv
    python scripts/export_training_log.py backup.json --days 14 -o training_log.csv

Design contract (mirrors the health-vault mini-brief, 2026-08):

  columns:
    data          YYYY-MM-DD (join key)
    ora_inizio    HH:MM local (Europe/Luxembourg) — BLANK when not real
    ora_fine      HH:MM local (Europe/Luxembourg)
    orari_fonte   timer_reale | tap_stimato | manuale — the fidelity of the times
                  timer_reale = real start AND end from a running timer
                  tap_stimato = real end, start reconstructed from the duration
                                (or start blank when no duration was recorded)
                  manuale     = NO reliable times on this row (outdoor logs,
                                skipped sessions) — both time columns are blank
    tipo          boulder_indoor|corda_indoor|falesia_outdoor|hangboard|pesi|cardio
    load          0-85 engine load (comparable indoor/outdoor by design, D151)
    load_fonte    actual | prescribed | free_session | outdoor_grade | unavailable
    rpe_stimato   0-10, ESTIMATED from load (+difficulty). Not a measured RPE.
    carico_dita   basso|medio|alto — heuristic from session type (optional)
    stato         done | skipped
    descrizione   generated 1-liner (name + feedback + notes)

Honesty rules baked in (health-vault requirement #1: a faked timestamp is worse
than an empty field):
  - ora_inizio is emitted ONLY when a real start exists (guided/free/outdoor
    timer). For a quick "mark done" it stays blank; orari_fonte says why.
  - rpe_stimato is labelled an estimate, never presented as an independent
    measurement — climb-agent has no 0-10 RPE field today.
  - a skipped session carries NO times: its completed_at is when the skip was
    tapped, not the end of a workout (see rows_from_completion_log).
  - outdoor logs double-submitted within seconds are collapsed to one session,
    and each dropped copy is reported on stderr (see dedupe_outdoor).

All timestamps in the state are UTC; the athlete's TZ is Europe/Luxembourg
(same offset as the stored Europe/Brussels), converted here.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Europe/Luxembourg")
except Exception:  # pragma: no cover - zoneinfo always present on 3.9+
    LOCAL_TZ = timezone(timedelta(hours=1))

REPO_ROOT = Path(__file__).resolve().parents[1]
SESSIONS_DIR = REPO_ROOT / "backend" / "catalog" / "sessions" / "v1"

LOAD_CAP = 85.0

COLUMNS = [
    "data", "ora_inizio", "ora_fine", "orari_fonte", "tipo",
    "load", "load_fonte", "rpe_stimato", "carico_dita", "stato", "descrizione",
]

DIFFICULTY_IT = {
    "very_easy": "molto facile", "easy": "facile", "ok": "giusta",
    "hard": "dura", "very_hard": "molto dura",
}
# Difficulty as a 0-10 anchor, blended 50/50 with the load-derived RPE.
DIFFICULTY_RPE = {"very_easy": 2, "easy": 4, "ok": 5, "hard": 7, "very_hard": 9}

SURFACE_TIPO = {
    "gym_boulder": "boulder_indoor",
    "gym_routes": "corda_indoor",
    "home_board": "boulder_indoor",
    "kilterboard": "boulder_indoor",
    "moonboard": "boulder_indoor",
    "spray_wall": "boulder_indoor",
}
SURFACE_IT = {
    "gym_boulder": "Boulder palestra", "gym_routes": "Vie palestra",
    "home_board": "Board di casa", "kilterboard": "Kilterboard",
    "moonboard": "MoonBoard", "spray_wall": "Spray wall",
}

# Session-id / name keywords → pesi (conditioning/weights, not climbing).
PESI_KEYWORDS = (
    "weights", "conditioning", "upper_body", "lower_body", "legs_strength",
    "pulling_strength", "antagonist", "core_training", "handstand",
)
CARDIO_KEYWORDS = ("cardio", "run", "aerobic_run", "bike")


# ── catalog ────────────────────────────────────────────────────────────────
def load_session_catalog() -> Dict[str, Dict[str, Any]]:
    """{session_id: {name, required_equipment}} from the JSON catalog."""
    out: Dict[str, Dict[str, Any]] = {}
    if not SESSIONS_DIR.exists():
        return out
    for f in sorted(SESSIONS_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        sid = d.get("session_id") or d.get("id") or f.stem
        out[sid] = {
            "name": d.get("name") or d.get("display_name") or f.stem,
            "required_equipment": d.get("required_equipment") or [],
            "stem": f.stem,
        }
    return out


# ── time helpers ─────────────────────────────────────────────────────────────
def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts or not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _hhmm_local(ts: Optional[str]) -> str:
    dt = _parse_iso(ts)
    return dt.astimezone(LOCAL_TZ).strftime("%H:%M") if dt else ""


def _minus_seconds_local(end_ts: Optional[str], seconds: Optional[float]) -> str:
    dt = _parse_iso(end_ts)
    if not dt or not seconds or seconds <= 0:
        return ""
    return (dt - timedelta(seconds=seconds)).astimezone(LOCAL_TZ).strftime("%H:%M")


# ── load / rpe ───────────────────────────────────────────────────────────────
def effective_slot_load(slot: Dict[str, Any]) -> Tuple[Optional[float], str]:
    """Reproduces engine.load_score.effective_session_load cascade.

    Returns (load, fonte). fonte is 'actual' when the completed-exercise score
    is present (0 counts), else 'prescribed'.
    """
    resolved = slot.get("resolved") or {}
    if not isinstance(resolved, dict):
        resolved = {}
    for key, zero_ok, fonte in (
        ("session_load_actual", True, "actual"),
        ("session_load_score", False, "prescribed"),
        ("estimated_load_score", False, "prescribed"),
    ):
        for holder in (slot, resolved):
            v = holder.get(key)
            if isinstance(v, (int, float)) and (zero_ok or v):
                return float(v), fonte
    return None, "unavailable"


def estimate_rpe(load: Optional[float], difficulty: Optional[str]) -> str:
    """0-10 RPE estimate. Load-driven, nudged 50/50 by the difficulty label
    when one exists. Returns '' when there is no signal at all."""
    load_rpe = None
    if isinstance(load, (int, float)):
        load_rpe = max(0.0, min(10.0, load / LOAD_CAP * 10.0))
    diff_rpe = DIFFICULTY_RPE.get(difficulty) if difficulty else None
    if load_rpe is not None and diff_rpe is not None:
        val = 0.5 * load_rpe + 0.5 * diff_rpe
    elif load_rpe is not None:
        val = load_rpe
    elif diff_rpe is not None:
        val = float(diff_rpe)
    else:
        return ""
    return str(int(max(1, min(10, round(val)))))


# ── type / finger-load classification ────────────────────────────────────────
def classify_planned_tipo(sid: str, meta: Dict[str, Any]) -> str:
    stem = (meta.get("stem") or sid or "").lower()
    equip = set(meta.get("required_equipment") or [])
    if "hangboard" in equip or "finger" in stem or "hang" in stem:
        return "hangboard"
    if "gym_routes" in equip:
        return "corda_indoor"
    if "gym_boulder" in equip:
        return "boulder_indoor"
    if any(k in stem for k in CARDIO_KEYWORDS):
        return "cardio"
    if any(k in stem for k in PESI_KEYWORDS):
        return "pesi"
    return "boulder_indoor"  # generic indoor climbing fallback


def carico_dita_for(tipo: str, sid: str) -> str:
    stem = (sid or "").lower()
    if tipo == "hangboard":
        return "alto"
    if "limit" in stem or "power_contact" in stem or "max" in stem:
        return "alto"
    if tipo == "boulder_indoor":
        return "medio"
    if tipo == "falesia_outdoor":
        return "medio"
    if tipo == "corda_indoor":
        return "basso"
    return ""  # pesi / cardio / unknown → optional, left blank


# ── row builders ─────────────────────────────────────────────────────────────
def rows_from_completion_log(state: Dict[str, Any], catalog: Dict[str, Dict[str, Any]]) -> List[dict]:
    log = state.get("session_completion_log") or []
    slot_index = _index_week_plan_slots(state)
    rows: List[dict] = []
    for e in log:
        date = e.get("date")
        sid = str(e.get("session_id") or "")
        if not date:
            continue
        meta = catalog.get(sid, {"name": sid, "required_equipment": [], "stem": sid})
        status = e.get("status") or "done"
        difficulty = e.get("difficulty")

        started_at = e.get("started_at")
        finished_at = e.get("finished_at") or e.get("completed_at")
        duration_s = e.get("session_duration_seconds")

        if started_at:
            ora_inizio = _hhmm_local(started_at)
            ora_fine = _hhmm_local(finished_at)
            orari_fonte = "timer_reale"
        elif finished_at and isinstance(duration_s, (int, float)) and duration_s > 0:
            # start reconstructed from the measured duration off the real finish.
            ora_inizio = _minus_seconds_local(finished_at, duration_s)
            ora_fine = _hhmm_local(finished_at)
            orari_fonte = "tap_stimato"
        else:
            ora_inizio = ""
            ora_fine = _hhmm_local(finished_at)
            orari_fonte = "tap_stimato"

        # A skipped session has no training time to report. Its ``completed_at``
        # is the moment the skip was tapped, which is NOT the end of a workout —
        # in the real data three separate days were all skipped in one sitting
        # and came out carrying the same 19:37. Emitting that as ora_fine states
        # a training time that never happened, so it goes blank and orari_fonte
        # says the row has no reliable times.
        if status == "skipped":
            ora_inizio, ora_fine, orari_fonte = "", "", "manuale"

        slot = slot_index.get((date, sid))
        load: Optional[float] = None
        load_fonte = "unavailable"
        if slot:
            load, load_fonte = effective_slot_load(slot)

        tipo = classify_planned_tipo(sid, meta)
        if status == "skipped":
            load, load_fonte = None, "unavailable"

        rows.append({
            "data": date,
            "ora_inizio": ora_inizio,
            "ora_fine": ora_fine,
            "orari_fonte": orari_fonte,
            "tipo": tipo,
            "load": "" if load is None else round(load),
            "load_fonte": load_fonte,
            "rpe_stimato": "" if status == "skipped" else estimate_rpe(load, difficulty),
            "carico_dita": carico_dita_for(tipo, sid),
            "stato": status,
            "descrizione": _desc_planned(meta, e, difficulty),
            "_sort": finished_at or (date + "T00:00"),
        })
    return rows


def rows_from_free_sessions(state: Dict[str, Any]) -> List[dict]:
    rows: List[dict] = []
    for s in state.get("free_sessions") or []:
        if not s.get("finished_at"):
            continue  # only completed sessions
        date = s.get("date")
        surface = s.get("surface") or ""
        mode = s.get("session_mode")
        tipo = "cardio" if mode == "cardio" else SURFACE_TIPO.get(surface, "boulder_indoor")
        load = s.get("load_score")
        rows.append({
            "data": date,
            "ora_inizio": _hhmm_local(s.get("started_at")),
            "ora_fine": _hhmm_local(s.get("finished_at")),
            "orari_fonte": "timer_reale",
            "tipo": tipo,
            "load": "" if load is None else round(float(load)),
            "load_fonte": "free_session",
            "rpe_stimato": estimate_rpe(float(load) if load is not None else None, None),
            "carico_dita": carico_dita_for(tipo, surface),
            "stato": "done",
            "descrizione": _desc_free(s, surface),
            "_sort": s.get("finished_at") or (str(date) + "T00:00"),
        })
    return rows


DOUBLE_SUBMIT_WINDOW_S = 120


def dedupe_outdoor(entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Collapse double-submitted outdoor logs. Returns (kept, dropped).

    The outdoor log has no session id, so an accidental double tap on "save"
    writes the row twice. In the real data (4 cases over 34 entries) the two
    copies are identical in EVERY field except ``completed_at``, which differs
    by 4-10 seconds — nobody logs two separate crag sessions five seconds apart.

    The window is what keeps this conservative: two genuine sessions at the same
    spot on the same day with the same load would be saved minutes or hours
    apart, and survive. Only a near-simultaneous exact copy is dropped, and the
    caller reports how many.
    """
    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for entry in entries:
        signature = {k: v for k, v in entry.items() if k != "completed_at"}
        stamp = _parse_iso(entry.get("completed_at"))
        twin = None
        for seen in kept:
            if {k: v for k, v in seen.items() if k != "completed_at"} != signature:
                continue
            seen_stamp = _parse_iso(seen.get("completed_at"))
            if stamp is None or seen_stamp is None:
                twin = seen  # no timestamps to compare: an exact copy is a copy
                break
            if abs((stamp - seen_stamp).total_seconds()) <= DOUBLE_SUBMIT_WINDOW_S:
                twin = seen
                break
        if twin is None:
            kept.append(entry)
        else:
            dropped.append(entry)
    return kept, dropped


def rows_from_outdoor(state: Dict[str, Any]) -> List[dict]:
    rows: List[dict] = []
    entries, dropped = dedupe_outdoor(state.get("outdoor_log") or [])
    if dropped:
        for d in dropped:
            print(
                f"# dedup: scartata copia outdoor {d.get('date')} {d.get('spot_name')} "
                f"(salvata a {d.get('completed_at')})",
                file=sys.stderr,
            )
    for o in entries:
        date = o.get("date")
        if not date:
            continue
        load = o.get("load_score")
        started_at = o.get("started_at")
        finished_at = o.get("finished_at")
        if started_at and finished_at:
            ora_inizio, ora_fine, fonte = _hhmm_local(started_at), _hhmm_local(finished_at), "timer_reale"
        else:
            ora_inizio, ora_fine, fonte = "", "", "manuale"
        rows.append({
            "data": date,
            "ora_inizio": ora_inizio,
            "ora_fine": ora_fine,
            "orari_fonte": fonte,
            "tipo": "falesia_outdoor",
            "load": "" if load is None else round(float(load)),
            "load_fonte": "outdoor_grade",
            "rpe_stimato": estimate_rpe(float(load) if load is not None else None, None),
            "carico_dita": "medio",
            "stato": "done",
            "descrizione": _desc_outdoor(o),
            "_sort": (started_at or (str(date) + "T00:00")),
        })
    return rows


# ── description generation ("commenti che fai tu") ───────────────────────────
def _desc_planned(meta: Dict[str, Any], entry: Dict[str, Any], difficulty: Optional[str]) -> str:
    bits = [str(meta.get("name") or entry.get("session_id") or "")]
    n = entry.get("exercise_count")
    if isinstance(n, int) and n > 0:
        bits.append(f"{n} esercizi")
    if difficulty in DIFFICULTY_IT:
        bits.append(f"percepita {DIFFICULTY_IT[difficulty]}")
    return " · ".join(b for b in bits if b)


def _desc_free(s: Dict[str, Any], surface: str) -> str:
    head = SURFACE_IT.get(surface, "Sessione libera")
    summary = s.get("summary") or {}
    n = summary.get("total_climbs") if isinstance(summary, dict) else None
    best = summary.get("hardest_grade") if isinstance(summary, dict) else None
    tail = []
    if isinstance(n, int) and n > 0:
        tail.append(f"{n} salite")
    if best:
        tail.append(f"max {best}")
    notes = (s.get("notes") or "").strip()
    line = head + (": " + ", ".join(tail) if tail else "")
    if notes:
        line += f" — {notes}"
    return line


def _desc_outdoor(o: Dict[str, Any]) -> str:
    spot = o.get("spot_name") or "Falesia"
    routes = o.get("routes") or []
    grades = [r.get("grade") for r in routes if r.get("grade")]
    tail = []
    if routes:
        tail.append(f"{len(routes)} vie")
    if grades:
        tail.append(f"fino a {max(grades)}")
    notes = (o.get("notes") or "").strip()
    line = spot + (": " + ", ".join(tail) if tail else "")
    if notes:
        line += f" — {notes}"
    return line


# ── week-plan slot index (for planned-session load) ──────────────────────────
def _index_week_plan_slots(state: Dict[str, Any]) -> Dict[Tuple[str, str], dict]:
    index: Dict[Tuple[str, str], dict] = {}

    def _ingest(plan: Any) -> None:
        if not isinstance(plan, dict):
            return
        for wk in plan.get("weeks", []):
            for dy in wk.get("days", []):
                d = dy.get("date")
                for ss in dy.get("sessions", []):
                    sid = str(ss.get("session_id") or "")
                    if d and sid:
                        index.setdefault((d, sid), ss)  # first (freshest) wins

    _ingest(state.get("current_week_plan"))
    for plan in (state.get("week_plans") or {}).values():
        _ingest(plan)
    # archived macrocycles may carry historical plans
    for arch in state.get("archived_macrocycles") or []:
        for plan in (arch.get("week_plans") or {}).values() if isinstance(arch, dict) else []:
            _ingest(plan)
    return index


# ── main ─────────────────────────────────────────────────────────────────────
def build_rows(state: Dict[str, Any], since: Optional[str] = None) -> List[dict]:
    catalog = load_session_catalog()
    rows = (
        rows_from_completion_log(state, catalog)
        + rows_from_free_sessions(state)
        + rows_from_outdoor(state)
    )
    if since:
        rows = [r for r in rows if r["data"] >= since]
    rows.sort(key=lambda r: (r["data"], r.pop("_sort", "")))
    for r in rows:
        r.pop("_sort", None)
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="climb-agent → health-vault training_log.csv")
    ap.add_argument("backup", help="Path to user_state export JSON (GET /api/user/export)")
    ap.add_argument("-o", "--out", help="Output CSV path (default: stdout)")
    ap.add_argument("--days", type=int, help="Only sessions from the last N days")
    ap.add_argument("--since", help="Only sessions on/after YYYY-MM-DD")
    args = ap.parse_args(argv)

    state = json.loads(Path(args.backup).read_text())

    since = args.since
    if args.days and not since:
        anchor = None
        for e in state.get("session_completion_log") or []:
            if e.get("date"):
                anchor = max(anchor, e["date"]) if anchor else e["date"]
        base = anchor or datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
        since = (datetime.strptime(base, "%Y-%m-%d") - timedelta(days=args.days)).strftime("%Y-%m-%d")

    rows = build_rows(state, since=since)

    fh = open(args.out, "w", newline="") if args.out else sys.stdout
    try:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    finally:
        if args.out:
            fh.close()
    print(f"# {len(rows)} sessions exported", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
