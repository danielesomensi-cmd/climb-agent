#!/usr/bin/env python
"""A293 (R7a) — print the athlete context before composing a custom session.

READ-ONLY, ALWAYS. This script never writes anywhere: no Supabase write, no
API call, no ``deps.load_state`` (which saves migrations and bootstraps
missing users). Live data is read with explicit ``curl -X GET`` calls on the
Supabase REST API, every run (decision 2026-10-04: no mirror, read live).

What it prints (Italian, for Claude Code): position in the macrocycle,
official maxima with computed confidence, the anchored loads of the day
(B364 ``anchored_load`` — the only load numbers to use), key-session status
of the week (A293 fallback until A294), retest status (A289), per-day guards
(48 h finger gap, heavy pulling, HIIT), upcoming sessions, variety, try-hard
outcomes, limits, and the athlete notes block of docs/training/athlete_plan.md.

Usage:
  python scripts/athlete_context.py                       # live, Daniele, today
  python scripts/athlete_context.py --date 2026-10-06     # context on another day
  python scripts/athlete_context.py --json                # machine-readable
  python scripts/athlete_context.py --state-file s.json [--archive-file a.json] [--outdoor-file o.json]
  # what-if: insert a custom-session draft and show what the replanner would do
  python scripts/athlete_context.py --simulate draft.json --target-date 2026-10-06 --slot evening [--replace]

``draft.json`` has the shape of a POST /api/custom-session body
(``{"name": ..., "exercises": [{"exercise_id": ..., "sets": ..., ...}]}``).
The simulation runs ``replanner_v1.apply_events`` on a COPY of the week plan,
exactly like POST /api/replanner/events (same availability / planning_prefs /
gyms kwargs), and diffs before/after, because ``apply_events`` does not report
what ``_reconcile`` downgraded. Nothing is written.

Exit codes: 0 ok, 1 bad arguments / fetch error, 3 no state for the user.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.engine import athlete_context as ac  # noqa: E402

#: Daniele's internal user id (memory reference_prod_user_debug).
DEFAULT_USER_ID = "7ea9f0ee-e629-4ce9-8f4f-f8e6e3dc771e"
#: Archived weeks read for the confidence window of a test up to 90 days old
#: (21 days before it) + a week of look-back (same as GET /api/week, A289).
ARCHIVE_LOOKBACK_D = 90 + 21 + 7
#: Outdoor days read: try-hard window (28 d) + the week.
OUTDOOR_LOOKBACK_D = 35

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NO_STATE = 3


# ---------------------------------------------------------------------------
# Live read (Supabase REST, GET only)
# ---------------------------------------------------------------------------

def _env_files() -> List[Path]:
    """``.env`` candidates: this checkout, then the primary worktree (a brief
    worktree has no ``.env``, it is gitignored)."""
    out = [REPO_ROOT / ".env"]
    try:
        common = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=10, check=False,
        ).stdout.strip()
        if common:
            out.append(Path(common).parent / ".env")
    except Exception:
        pass
    return out


def load_credentials() -> Tuple[str, str]:
    """``(SUPABASE_URL, SUPABASE_SERVICE_KEY)`` from the environment or ``.env``."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    for path in _env_files():
        if url and key:
            break
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k == "SUPABASE_URL" and not url:
                url = v
            elif k == "SUPABASE_SERVICE_KEY" and not key:
                key = v
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY non trovati (env o .env)")
    return url.rstrip("/"), key


def build_get_command(base_url: str, key: str, table: str, params: List[Tuple[str, str]]) -> List[str]:
    """The curl argv for ONE read. Explicit ``-X GET``, no body flag ever."""
    url = f"{base_url}/rest/v1/{table}?{urlencode(params)}"
    return [
        "curl", "-sS", "--fail-with-body", "-X", "GET", url,
        "-H", f"apikey: {key}",
        "-H", f"Authorization: Bearer {key}",
        "-H", "Accept: application/json",
    ]


_FORBIDDEN_CURL_FLAGS = {"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode",
                         "-F", "--form", "-T", "--upload-file", "--json"}


def rest_get(base_url: str, key: str, table: str, params: List[Tuple[str, str]]) -> Any:
    cmd = build_get_command(base_url, key, table, params)
    # Belt and braces: this script must never be able to send a write.
    if cmd[cmd.index("-X") + 1] != "GET" or _FORBIDDEN_CURL_FLAGS.intersection(cmd):
        raise RuntimeError("refusing a non-GET request")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"GET {table} fallita (curl {proc.returncode}): {proc.stdout[:300]} {proc.stderr[:300]}")
    return json.loads(proc.stdout or "null")


def fetch_live(user_id: str, today: date) -> Dict[str, Any]:
    """State + archived weeks + outdoor rows for ``user_id``, read live."""
    base, key = load_credentials()
    users = rest_get(base, key, "users", [("select", "state,updated_at"), ("user_id", f"eq.{user_id}")])
    if not users:
        return {"state": None, "updated_at": None, "archived_weeks": None, "outdoor_rows": None}
    arch_since = (today - timedelta(days=ARCHIVE_LOOKBACK_D)).isoformat()
    archive = rest_get(base, key, "week_archive", [
        ("select", "week_start,plan"), ("user_id", f"eq.{user_id}"),
        ("week_start", f"gte.{arch_since}"), ("week_start", f"lte.{today.isoformat()}"),
    ])
    out_since = (today - timedelta(days=OUTDOOR_LOOKBACK_D)).isoformat()
    outdoor = rest_get(base, key, "outdoor_logs", [
        ("select", "session_date,entry"), ("user_id", f"eq.{user_id}"),
        ("session_date", f"gte.{out_since}"), ("order", "session_date.asc"),
    ])
    return {
        "state": users[0].get("state"),
        "updated_at": users[0].get("updated_at"),
        "archived_weeks": archive or [],
        "outdoor_rows": outdoor or [],
    }


# ---------------------------------------------------------------------------
# File read
# ---------------------------------------------------------------------------

def _read_json(path: Optional[str]) -> Any:
    if not path:
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_from_files(state_file: str, archive_file: Optional[str], outdoor_file: Optional[str]) -> Dict[str, Any]:
    raw = _read_json(state_file)
    # Accept a bare state, {"state": ...} or a Supabase row list [{"state": ...}].
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "state" in raw[0]:
        raw = raw[0]
    state = raw.get("state") if isinstance(raw, dict) and isinstance(raw.get("state"), dict) else raw
    return {
        "state": state if isinstance(state, dict) and state else None,
        "updated_at": None,
        "archived_weeks": _read_json(archive_file),
        "outdoor_rows": _read_json(outdoor_file),
    }


def plan_notes() -> Optional[str]:
    path = REPO_ROOT / ac.ATHLETE_PLAN_PATH
    if not path.is_file():
        return None
    return ac.extract_plan_notes(path.read_text(encoding="utf-8"))


def _age_line(updated_at: Optional[str], now: Optional[datetime] = None) -> str:
    if not updated_at:
        return "Fonte: file locale"
    try:
        ts = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        now = now or datetime.now(timezone.utc)
        mins = int((now - ts).total_seconds() // 60)
        age = f"{mins} min fa" if mins < 120 else f"{mins // 60} h fa"
    except ValueError:
        age = "età sconosciuta"
    return f"Fonte: Supabase live (sola lettura), stato salvato {updated_at} ({age})"


# ---------------------------------------------------------------------------
# --simulate
# ---------------------------------------------------------------------------

def _week_plan_for(state: Dict[str, Any], target: date) -> Optional[Dict[str, Any]]:
    monday = (target - timedelta(days=target.weekday())).isoformat()
    plan = (state.get("week_plans") or {}).get(monday)
    if isinstance(plan, dict):
        return plan
    cur = state.get("current_week_plan")
    if isinstance(cur, dict) and cur.get("start_date") == monday:
        return cur
    return None


def _day_sessions(plan: Dict[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for wk in plan.get("weeks") or []:
        for day in wk.get("days") or []:
            for s in day.get("sessions") or []:
                out[(str(day.get("date")), str(s.get("slot") or ""))] = s
    return out


def _enrich(sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        from backend.api.routers.custom_session import enrich_custom_sessions_for_play
    except Exception:  # pragma: no cover - API deps missing: raw exercises still simulate
        return sessions
    return enrich_custom_sessions_for_play(sessions)


SIM_SESSION_ID = "cs_simulated_a293"


def simulate(state: Dict[str, Any], draft: Dict[str, Any], target_date: str, slot: str,
             *, replace: bool = False, location: Optional[str] = None,
             gym_id: Optional[str] = None) -> Dict[str, Any]:
    """What POST /api/replanner/events would do with this draft. Read-only."""
    from backend.engine.anchored_load import resolve_custom_exercises
    from backend.engine.macro_position import position_on
    from backend.engine.replanner_v1 import apply_events
    from backend.engine.session_tags import derive_session_tags

    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    plan = _week_plan_for(state, target)
    result: Dict[str, Any] = {"target_date": target_date, "slot": slot, "ok": False,
                              "downgrades": [], "removed": [], "warnings": []}
    if plan is None:
        result["error"] = "settimana non generata: nessun week_plan per quella data"
        return result
    pos = position_on(state.get("macrocycle"), target) or {}
    phase_id = pos.get("phase_id")

    cs = {"id": SIM_SESSION_ID, "name": draft.get("name") or "Simulated custom",
          "exercises": deepcopy(draft.get("exercises") or [])}
    tags, intensity = derive_session_tags(cs["exercises"])
    result["custom_tags"] = tags
    result["custom_intensity"] = intensity
    pool = _enrich([dict(c) for c in state.get("custom_sessions") or []] + [cs])

    before = _day_sessions(plan)
    events: List[Dict[str, Any]] = []
    occupied = before.get((target_date, slot))
    if occupied is not None:
        if not replace:
            result["error"] = (f"slot {slot} del {target_date} occupato da {occupied.get('session_id')} "
                               "(usa --replace per simulare remove_session + add_custom_session)")
            result["warnings"].append("collisione di slot")
            return result
        events.append({"event_type": "remove_session", "date": target_date, "slot": slot})
        result["removed"].append({"date": target_date, "slot": slot, "session_id": occupied.get("session_id"),
                                  "key": ac.key_matches(occupied, phase_id)})
    add = {"event_type": "add_custom_session", "custom_session_id": SIM_SESSION_ID,
           "target_date": target_date, "slot": slot, "location": location or "home"}
    if gym_id:
        add["gym_id"] = gym_id
    events.append(add)
    try:
        updated = apply_events(
            deepcopy(plan), events,
            availability=deepcopy(state.get("availability")),
            planning_prefs=deepcopy(state.get("planning_prefs")),
            gyms=deepcopy((state.get("equipment") or {}).get("gyms")),
            custom_sessions=pool,
        )
    except ValueError as exc:
        result["error"] = f"il replanner rifiuterebbe gli eventi: {exc}"
        return result

    after = _day_sessions(updated)
    for (d, sl), s in sorted(before.items()):
        if (d, sl) == (target_date, slot) and replace:
            continue
        new = after.get((d, sl))
        if new is not None and new.get("session_id") == s.get("session_id"):
            continue
        keys = ac.key_matches(s, phase_id)
        result["downgrades"].append({
            "date": d, "slot": sl, "from": s.get("session_id"),
            "to": (new or {}).get("session_id"), "key": keys,
        })
    placed = after.get((target_date, slot))
    result["ok"] = placed is not None and placed.get("session_id") == f"custom_{SIM_SESSION_ID}"
    result["placed_tags"] = (placed or {}).get("tags")
    result["resolved_exercises"] = [
        {k: e.get(k) for k in ("exercise_id", "sets", "reps", "work_seconds", "load_kg", "load_source",
                               "suggested_external_load_kg", "suggested_total_load_kg", "stored_load_kg",
                               "anchored")}
        for e in resolve_custom_exercises(state, cs["exercises"], target_date)
    ]
    if any(dg["key"] for dg in result["downgrades"]):
        result["warnings"].append("una sessione CHIAVE verrebbe declassata: cambia giorno o contenuto")
    if any(r["key"] for r in result["removed"]):
        result["warnings"].append("--replace toglierebbe una sessione CHIAVE")
    result["warnings"].append(
        "la simulazione riproduce /api/replanner/events; quick-add e override seguono percorsi diversi "
        "(prev_days della settimana precedente) e il lunedì dopo una domenica dita non è visto da /events"
    )
    return result


def _play_line(e: Dict[str, Any]) -> str:
    """The load the player will prescribe for THIS draft's scheme, with the
    calculation note the command asks to copy into the line's ``notes``."""
    scheme = f"{e.get('sets')}×{e.get('reps') or (str(e.get('work_seconds')) + 's')}"
    line = f"  carico al play: {e['exercise_id']} {scheme} load_kg {e.get('load_kg')} ({e['load_source']})"
    an = e.get("anchored") or {}
    if e.get("load_source") == "anchored" and an:
        off = an.get("official") or {}
        ref = off.get("one_rm") or off.get("total")
        ref_lbl = "1RM" if off.get("one_rm") else "massimale"
        pct = an.get("pct_of_official")
        ext = e.get("suggested_external_load_kg")
        ramp = an.get("ramp") or {}
        ramp_s = (f", rientro n={ramp.get('n')}" if (ramp.get("factor") or 1.0) < 1.0 else "")
        line += (f" → nota: «{'+' if (ext or 0) >= 0 else ''}{ext} kg (totale {e.get('suggested_total_load_kg')}) "
                 f"= {round(pct * 100) if pct else '—'}% di {ref} kg {ref_lbl}, test {off.get('date')}{ramp_s}»")
    return line


def render_simulation(sim: Dict[str, Any]) -> str:
    L = [f"=== Simulazione: custom il {sim['target_date']} ({sim['slot']}) — nessuna scrittura ==="]
    if sim.get("error"):
        L.append(f"  ERRORE: {sim['error']}")
    else:
        L.append(f"  inserita: {'sì' if sim.get('ok') else 'NO'}; tag derivati {sim.get('custom_tags')} "
                 f"intensità {sim.get('custom_intensity')}")
        for r in sim.get("removed") or []:
            L.append(f"  rimossa (--replace): {r['date']} {r['slot']} {r['session_id']}"
                     + (f" — CHIAVE {','.join(r['key'])}" if r["key"] else ""))
        if not sim.get("downgrades"):
            L.append("  nessuna altra sessione cambiata dal reconcile")
        for dg in sim.get("downgrades") or []:
            L.append(f"  {dg['date']} {dg['slot']}: {dg['from']} → {dg['to'] or 'rimossa'}"
                     + (f" — CHIAVE {','.join(dg['key'])}" if dg["key"] else ""))
        for e in sim.get("resolved_exercises") or []:
            if e.get("load_source"):
                L.append(_play_line(e))
    for w in sim.get("warnings") or []:
        L.append(f"  avviso: {w}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def _parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Contesto atleta in sola lettura (A293).")
    p.add_argument("--user-id", default=DEFAULT_USER_ID)
    p.add_argument("--date", help="giorno del contesto (YYYY-MM-DD, default oggi)")
    p.add_argument("--state-file", help="leggi lo stato da un file JSON invece che live")
    p.add_argument("--archive-file", help="settimane archiviate (con --state-file)")
    p.add_argument("--outdoor-file", help="righe outdoor_logs (con --state-file)")
    p.add_argument("--json", action="store_true", help="stampa il contesto in JSON")
    p.add_argument("--simulate", help="bozza di custom session (JSON) da simulare")
    p.add_argument("--target-date", help="giorno dell'inserimento simulato")
    p.add_argument("--slot", default="evening", help="slot dell'inserimento simulato")
    p.add_argument("--replace", action="store_true", help="simula remove_session dello slot occupato")
    p.add_argument("--location", help="location della custom simulata (default home)")
    p.add_argument("--gym-id", help="gym_id della custom simulata")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        today = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    except ValueError:
        print("--date deve essere YYYY-MM-DD", file=sys.stderr)
        return EXIT_ERROR
    if args.simulate and not args.target_date:
        print("--simulate richiede --target-date", file=sys.stderr)
        return EXIT_ERROR

    try:
        data = (load_from_files(args.state_file, args.archive_file, args.outdoor_file)
                if args.state_file else fetch_live(args.user_id, today))
    except Exception as exc:
        print(f"Lettura fallita: {exc}", file=sys.stderr)
        return EXIT_ERROR
    state = data.get("state")
    if not state:
        print(f"Nessuno stato per l'utente {args.user_id}", file=sys.stderr)
        return EXIT_NO_STATE

    ctx = ac.build_athlete_context(state, today, archived_weeks=data.get("archived_weeks"),
                                   outdoor_rows=data.get("outdoor_rows"))
    sim = None
    if args.simulate:
        sim = simulate(state, _read_json(args.simulate) or {}, args.target_date, args.slot,
                       replace=args.replace, location=args.location, gym_id=args.gym_id)
    if args.json:
        payload: Dict[str, Any] = {"context": ctx, "source": {"updated_at": data.get("updated_at"),
                                                               "file": args.state_file}}
        if sim is not None:
            payload["simulation"] = sim
        print(json.dumps(payload, ensure_ascii=False, indent=1, default=str))
    else:
        sys.stdout.write(ac.render_text(ctx, plan_notes=plan_notes(),
                                        source_line=_age_line(data.get("updated_at"))))
        if sim is not None:
            sys.stdout.write("\n" + render_simulation(sim))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
