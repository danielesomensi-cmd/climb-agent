"""A294 (R5) — key sessions: which sessions of the week carry the phase's key
stimuli, what is owed, and how to get it back.

Why this exists: the plan placed a finger session, the athlete replaced it with
a custom session or skipped it, and nothing in the app said that the one
max-finger stimulus of the week had just gone. Five analyses each had their own
idea of a "key session"; this module is the single owner (DECISIONS 2026-10-04:
derived at read, never persisted).

Contract — everything here is pure and deterministic:

- ``compute_key_status(state, today, *, archived_weeks, outdoor_rows,
  week_start, ...)`` → a JSON-serialisable dict for ONE week (the week of
  ``today`` unless ``week_start`` is given). Nothing is written, the input is
  never mutated, there is no ``date.today()`` and no I/O except the static
  catalogs (``key_stimuli/v1`` and the exercise catalog) when not passed in.
- The status is DERIVED: ``debt = max(0, target − satisfied − valid_planned)``.
  Weeks already cached until the end of the macrocycle need no migration.
- ``check_insertion(...)`` answers "what happens to the key sessions if this
  custom / generated / catalog session goes on that day" on a deep copy, via the
  replanner's own ``apply_events`` (same path the real click takes).
- ``key_status_text(status)`` — compact block for the coach prompt and scripts.

Single definitions it reuses (never reimplemented): the stimulus families and
exposure rules (``stimulus``), finger-hard days and the outdoor-hard rule
(``stimulus.finger_hard_days``), the anchored floor of the phase
(``anchored_load``), the replanner's recovery gap / rewritable rule / reconcile
(``replanner_v1``) and the planner's slot picker (``planner_v2``).

Statuses of one requirement row (``status``):

- ``done``      — target met by full-dose sessions;
- ``planned``   — the rest of the target is planned on a valid future day;
- ``partial``   — only partial-dose sessions (e.g. a weighted pull-up below the
  phase floor): no ✓, the debt stays, severity at most ``warning``;
- ``missing``   — debt > 0;
- ``not_due``   — a max-gap requirement whose deadline is after this week;
- ``unplaceable`` — the planner itself could not place it (``unmet_stimulus``).

``resolution`` explains what to do with a debt: ``proposal`` (a validated
re-schedule is attached), ``deferred_next`` (catching up would break a key of
next week — "the next one is <date>"), ``deferred_fatigue`` (very_hard
feedback / adaptive replan in the last 72 h: no catch-up, by principle),
``let_go`` (no valid day left) or ``missed`` (the week is over).
"""

from __future__ import annotations

import copy
import json
import os
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from backend.engine import guards_v1 as _guards_mod
from backend.engine.stimulus import (
    FAMILY_FINGER_MAX,
    FAMILY_LIMIT_POWER,
    count_exposures,
    counted_entries,
    exposures,
    finger_hard_days,
    is_finger_hard_session,
    is_test_session,
    iter_plan_sessions,
    outdoor_hard_days,
    session_flag,
    session_stimuli,
    stimulus_of,
    _outdoor_entries as _stimulus_outdoor_entries,
)

DateLike = Union[date, str]
ArchivedWeeks = Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]]

VERSION = "a294.1"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEY_CATALOG_PATH = os.path.join(_REPO_ROOT, "backend", "catalog", "key_stimuli", "v1", "key_stimuli.json")
_EXERCISES_PATH = os.path.join(_REPO_ROOT, "backend", "catalog", "exercises", "v1", "exercises.json")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Minimum technique-category drills (catalog ``category == technique``) in a
#: session to count it as the technique key. ENGINEERING CONSTANT (A293).
TECHNIQUE_MIN_DRILLS = 2
#: Zero-cost warm-up drills (athlete_plan.md §3): the warm-up is not the
#: technique stimulus, so these never count towards the technique key.
WARMUP_TECHNIQUE_DRILLS = ("silent_feet_drill", "foothold_stare", "straight_arms", "hip_rotation_drill",
                           # C272: the small-foot pressure primer is a warm-up drill too.
                           "small_feet_press_hold")
#: A294 review (GOAL REFRAME: the technique key is FEET + POSITIONING, the two
#: declared limiters). Technique drills of these catalog recency groups do not
#: count: relaxation (breathing_awareness), pacing (slow_climbing,
#: tech_green_light_red_light, tech_smooth_is_fast), route reading
#: (timed_route_preview) and lead-specific (fall_practice, the try-hard drill)
#: are useful but are not that stimulus. ENGINEERING CONSTANT.
TECHNIQUE_EXCLUDED_RECENCY = ("technique_pacing_drills", "technique_relaxation_drills",
                              "technique_route_reading", "technique_lead_specific",
                              # C272: the try-hard library (comp, no-take, fall
                              # ladder, routine, commit map) is the try-hard
                              # component, not the feet / positioning stimulus.
                              "technique_tryhard",
                              # C272 review: the 4-weekly benchmark is a TEST
                              # (read on the 8-week trend), not the weekly
                              # stimulus at limit.
                              "technique_benchmark")
#: ENGINEERING CONSTANT (R5, Prilepin at 85-90 %: 6-8 total reps in sets of
#: 2-3): a heavy session needs this many effective sets of the main exercise to
#: count as a FULL dose. Unknown set count → not penalised.
MIN_FULL_SETS = 4
#: Half-kilo rounding of prescribed loads: a load this close below the floor is
#: the floor (anchored loads are rounded to 0.5 kg).
FLOOR_TOLERANCE_KG = 0.25
#: A pending max test blocks hard/finger work in the hours before it
#: (decision 2026-10-04: one definition, shared with the retest blockers).
PRE_TEST_BLOCK_H = 72
#: Very_hard feedback / adaptive replan in the last 72 h → no catch-up.
FATIGUE_LOOKBACK_D = 3
#: Re-entry: fewer than this many exposures in the window → reduced proposals
#: (no campus) and finger supporting sessions marked optional.
REENTRY_MIN_EXPOSURES = 2
REENTRY_WINDOW_D = 21
#: Severity: a p1 requirement turns critical when at least this share of the
#: phase weeks elapsed so far had no full exposure. ENGINEERING CONSTANT (R5).
CRITICAL_PHASE_SHARE = 0.5
#: Heavy pull within this many days before a limit / strength_long key
#: (decision 2026-10-04: "no ≥85 % pull or front lever within 24 h before").
PRE_LIMIT_PULL_D = 1
#: At most this many heavy (≥ 85 %) pulling sessions in any 7 days
#: (decision 2026-10-04, chin-ups included).
MAX_HEAVY_PULL_7D = 2
#: Next-week look-ahead used by the proposal validator.
NEXT_WEEK_LOOKAHEAD_D = 3

SEVERITY_ORDER = ("none", "info", "warning", "critical")
ROLE_ORDER = ("optional", "supporting", "key")

# ---------------------------------------------------------------------------
# Catalogs
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_key_catalog_file() -> Dict[str, Any]:
    with open(KEY_CATALOG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_key_catalog() -> Dict[str, Any]:
    """The key-stimuli catalog (a deep copy: callers may not mutate the cache)."""
    return copy.deepcopy(_load_key_catalog_file())


@lru_cache(maxsize=1)
def _load_exercise_catalog_file() -> Dict[str, Dict[str, Any]]:
    with open(_EXERCISES_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    items = data.get("exercises") if isinstance(data, dict) else data
    return {e["id"]: e for e in items or [] if isinstance(e, dict) and e.get("id")}


def load_exercise_catalog() -> Dict[str, Dict[str, Any]]:
    return dict(_load_exercise_catalog_file())


def phase_requirements(phase_id: Optional[str],
                       key_catalog: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
    """The key requirements of a phase, each merged with its stimulus definition.

    Row: ``{key, label, why, target_per_week, priority, max_severity,
    max_gap_days?, families, session_ids, propose, ...}``.
    """
    cat = key_catalog if key_catalog is not None else _load_key_catalog_file()
    stimuli = cat.get("stimuli") or {}
    out: List[Dict[str, Any]] = []
    for item in (cat.get("phases") or {}).get(phase_id or "", []):
        sid = item.get("stimulus")
        sdef = stimuli.get(sid) or {}
        row = {**copy.deepcopy(sdef), **copy.deepcopy(item)}
        row["key"] = sid
        row.pop("stimulus", None)
        row.setdefault("label", sid)
        row.setdefault("target_per_week", 1)
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _as_date(value: DateLike) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _parse(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return _as_date(value)
    except (TypeError, ValueError):
        return None


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _bodyweight(state: Mapping[str, Any]) -> Optional[float]:
    return _num(state.get("bodyweight_kg")) or _num((state.get("body") or {}).get("weight_kg"))


def _plan_days(state: Mapping[str, Any], archived_weeks: ArchivedWeeks) -> Dict[str, List[Dict[str, Any]]]:
    days: Dict[str, List[Dict[str, Any]]] = {}
    for d, s, _src in iter_plan_sessions(state, archived_weeks):
        days.setdefault(d, []).append(s)
    return days


def _week_plan(state: Mapping[str, Any], ws: date, archived_weeks: ArchivedWeeks) -> Optional[Dict[str, Any]]:
    key = ws.isoformat()
    plan = (state.get("week_plans") or {}).get(key)
    if isinstance(plan, dict):
        return plan
    cur = state.get("current_week_plan")
    if isinstance(cur, dict) and str(cur.get("start_date") or "") == key:
        return cur
    if isinstance(archived_weeks, Mapping):
        arch = archived_weeks.get(key)
        if isinstance(arch, dict):
            return arch
    elif archived_weeks:
        for row in archived_weeks:
            if isinstance(row, Mapping) and str(row.get("week_start") or "") == key and isinstance(row.get("plan"), dict):
                return row["plan"]
    return None


def _session_name(session_id: Optional[str]) -> str:
    sid = str(session_id or "")
    return sid.replace("_", " ").strip().capitalize() if sid else ""


def _ref(d: str, s: Mapping[str, Any], **extra: Any) -> Dict[str, Any]:
    out = {"date": d, "slot": s.get("slot"), "session_id": s.get("session_id"),
           "name": s.get("name"), "status": s.get("status") or "planned"}
    out.update(extra)
    return out


def _phase_on(state: Mapping[str, Any], on: date) -> Optional[Dict[str, Any]]:
    from backend.engine.macro_position import position_on

    return position_on(state.get("macrocycle"), on)


# ---------------------------------------------------------------------------
# Matching: which key stimuli a session delivers
# ---------------------------------------------------------------------------

def technique_hit(session: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]],
                  req: Optional[Mapping[str, Any]] = None) -> bool:
    """The technique key: the technique catalog session, or ≥ TECHNIQUE_MIN_DRILLS
    feet / positioning drills (not ``TECHNIQUE_EXCLUDED_RECENCY``) that are neither the
    try-hard drill nor warm-up drills."""
    sids = (req or {}).get("session_ids") or ["technique_focus_gym"]
    if str(session.get("session_id") or "") in sids:
        return True
    entries, _origin = counted_entries(session)
    drills = {str(e.get("exercise_id") or "") for e in entries
              if _is_technique_key_drill(catalog.get(str(e.get("exercise_id") or "")) or {})}
    drills -= {"fall_practice"} | set(WARMUP_TECHNIQUE_DRILLS)
    return len(drills) >= TECHNIQUE_MIN_DRILLS


def _is_technique_key_drill(ex: Mapping[str, Any]) -> bool:
    """A technique-category drill that trains feet / positioning (not
    relaxation, pacing or route reading)."""
    return ex.get("category") == "technique" and ex.get("recency_group") not in TECHNIQUE_EXCLUDED_RECENCY


def tryhard_hit(session: Mapping[str, Any], req: Optional[Mapping[str, Any]] = None) -> bool:
    """Try-hard: a session that actually contains a fall-practice block.

    A294 review: a limit session alone no longer counts — that made the
    try-hard row a copy of the limit row and never checked the component the
    GOAL REFRAME asked for. Outdoor attempts near the redpoint and a free
    boulder session at the limit still count (flags on the requirement)."""
    ex_ids = set((req or {}).get("exercise_ids") or ["fall_practice"])
    entries, _origin = counted_entries(session)
    return any(str(e.get("exercise_id") or "") in ex_ids for e in entries)


def _generic_hit(req: Mapping[str, Any], session: Mapping[str, Any]) -> bool:
    sid = str(session.get("session_id") or "")
    if sid in (req.get("session_ids") or []):
        return True
    fams = req.get("families") or []
    return bool(fams) and any(f in session_stimuli(session) for f in fams)


def session_delivers(req: Mapping[str, Any], session: Mapping[str, Any],
                     catalog: Mapping[str, Mapping[str, Any]]) -> bool:
    """Whether ``session`` delivers requirement ``req`` (presence, not dose).

    A test session counts only for the requirements that accept tests (a max
    test is a max stimulus); otherwise tests are never key sessions."""
    if is_test_session(session) and not req.get("tests_count"):
        return False
    key = req.get("key")
    if key == "technique":
        return technique_hit(session, catalog, req)
    if key == "try_hard":
        return tryhard_hit(session, req)
    return _generic_hit(req, session)


def session_keys(session: Mapping[str, Any], phase_id: Optional[str],
                 catalog: Optional[Mapping[str, Mapping[str, Any]]] = None,
                 key_catalog: Optional[Mapping[str, Any]] = None) -> List[str]:
    """Keys of the phase a session delivers (try-hard excluded: it rides on the
    limit key, never a session of its own)."""
    cat = catalog if catalog is not None else _load_exercise_catalog_file()
    return [r["key"] for r in phase_requirements(phase_id, key_catalog)
            if r["key"] != "try_hard" and session_delivers(r, session, cat)]


# ---------------------------------------------------------------------------
# Dose
# ---------------------------------------------------------------------------

def _entry_load_total(entry: Mapping[str, Any], bw: Optional[float]) -> Optional[float]:
    total = _num(entry.get("used_total_load_kg"))
    if total is not None:
        return total
    ext = _num(entry.get("used_external_load_kg"))
    if ext is not None and bw is not None:
        return bw + ext
    for k in ("suggested_total_load_kg",):
        v = _num(entry.get(k))
        if v is not None:
            return v
    sug = entry.get("suggested") or {}
    v = _num(sug.get("target_total_load_kg"))
    if v is not None:
        return v
    ext = _num(entry.get("load_kg"))
    if ext is not None and bw is not None:
        return bw + ext
    return None


def _entry_sets(entry: Mapping[str, Any], origin: str) -> Optional[int]:
    if origin == "actual":
        v = _num(entry.get("completed_sets"))
    else:
        v = _num(entry.get("sets")) or _num((entry.get("prescription") or {}).get("sets"))
    return int(v) if v is not None and v > 0 else None


def _limit_log_dose(state: Mapping[str, Any], session: Mapping[str, Any], d_iso: str) -> Dict[str, Any]:
    """A296 (dose ``limit_log``): the limit stimulus of a custom / adhoc session.

    A catalog session is full on presence (the engine prescribed it). A custom
    or generated session whose limit exercise was logged problem by problem is
    full only with ≥ ``limit_log.QUALIFYING_PROBLEMS`` problems at or above the
    day's target (sent or high point) — a "limit" spent on easy problems is not
    the week's limit stimulus. With no problem log it stays full on presence
    (nothing measured: no new debt for a session that was done)."""
    from backend.engine import limit_log

    custom = bool(session.get("is_custom")) or str(session.get("session_id") or "").startswith(("custom_", "generated_"))
    if not custom:
        return {"dose": "full", "reason": "presence"}
    logged = [e for e in limit_log.entries_for_session(state, d_iso, session.get("session_id")) if e.get("problems")]
    if not logged:
        return {"dose": "full", "reason": "presence"}
    best = max(logged, key=lambda e: limit_log.qualifying_count(e["problems"], e.get("target_grade")))
    n = limit_log.qualifying_count(best["problems"], best.get("target_grade"))
    if n >= limit_log.QUALIFYING_PROBLEMS:
        return {"dose": "full", "reason": "limit_log_at_target", "qualifying": n,
                "target_grade": best.get("target_grade")}
    return {"dose": "partial", "reason": "limit_log_below_target", "qualifying": n,
            "target_grade": best.get("target_grade")}


def session_dose(state: Mapping[str, Any], session: Mapping[str, Any], d_iso: str,
                 req: Mapping[str, Any]) -> Dict[str, Any]:
    """``{"dose": "full"|"partial", "reason": str, ...}`` of a session for ``req``.

    Only the anchored families (``dose: anchored`` — finger_max, pulling_max)
    are measured; everything else is full on presence. For the anchored ones,
    every main exercise of the family is compared with the anchored FLOOR of
    the phase on that day (``anchored_load(...)["floor"]``: the effective floor,
    re-entry ramp and pain already applied) and needs ≥ ``MIN_FULL_SETS`` sets:

    - a catalog session done or planned → full (the engine prescribed it);
    - a test → full;
    - a custom exercise in ``load_mode: anchored`` → full when the athlete is
      tested (its load IS the anchored prescription);
    - otherwise the load (logged, else prescribed) is compared with the floor;
      no readable load → partial (no ✓, the debt stays); no tested max →
      partial for a custom, full for a catalog session (A294 review).
    """
    if req.get("dose") == "limit_log":
        return _limit_log_dose(state, session, d_iso)
    if req.get("dose") != "anchored":
        return {"dose": "full", "reason": "presence"}
    if is_test_session(session):
        return {"dose": "full", "reason": "test"}
    from backend.engine.anchored_load import ANCHORED_EXERCISES, anchored_load, effective_load_mode

    fams = set(req.get("families") or [])
    entries, origin = counted_entries(session)
    custom = bool(session.get("is_custom")) or str(session.get("session_id") or "").startswith(("custom_", "generated_"))
    main = [e for e in entries if stimulus_of(e.get("exercise_id")) in fams]
    if not main:
        # Session id match without an exercise list (catalog fallback).
        return {"dose": "full" if not custom else "partial",
                "reason": "catalog_session" if not custom else "no_main_exercise"}
    if not custom and origin != "actual":
        return {"dose": "full", "reason": "catalog_session"}
    bw = _bodyweight(state)
    best: Optional[Dict[str, Any]] = None
    for e in main:
        eid = str(e.get("exercise_id") or "")
        sets = _entry_sets(e, origin)
        if sets is not None and sets < MIN_FULL_SETS:
            res = {"dose": "partial", "reason": "too_few_sets", "sets": sets, "exercise_id": eid}
        elif eid not in ANCHORED_EXERCISES:
            res = {"dose": "full", "reason": "not_anchored", "exercise_id": eid}
        else:
            reps = _num(e.get("reps")) or _num(e.get("completed_reps"))
            ws = _num(e.get("work_seconds"))
            anch = anchored_load(state, eid, date=d_iso, sets=sets,
                                 reps=int(reps) if reps and eid in ("weighted_pullup", "weighted_chinup") else None,
                                 work_seconds=ws if eid.startswith("max_hang") else None)
            if anch is None and not custom:
                # A294 review: an untested athlete who did the catalog session
                # did what the engine prescribed — no floor to compare with,
                # so no debt (untested users: no behaviour change).
                res = {"dose": "full", "reason": "catalog_session", "exercise_id": eid}
            elif anch is None:
                res = {"dose": "partial", "reason": "no_tested_max", "exercise_id": eid}
            elif origin != "actual" and custom and effective_load_mode(e) == "anchored":
                res = {"dose": "full", "reason": "anchored_prescription", "exercise_id": eid,
                       "floor_kg": anch.get("floor")}
            elif not custom and origin == "actual" and _entry_load_total(e, bw) is None:
                res = {"dose": "full", "reason": "catalog_session", "exercise_id": eid}
            else:
                total = _entry_load_total(e, bw)
                floor = _num(anch.get("floor"))
                if total is None or floor is None:
                    res = {"dose": "partial", "reason": "load_unknown", "exercise_id": eid}
                elif total + FLOOR_TOLERANCE_KG >= floor:
                    res = {"dose": "full", "reason": "at_or_above_floor", "exercise_id": eid,
                           "total_kg": round(total, 1), "floor_kg": floor}
                else:
                    res = {"dose": "partial", "reason": "below_floor", "exercise_id": eid,
                           "total_kg": round(total, 1), "floor_kg": floor}
        if res["dose"] == "full":
            return res
        best = best or res
    return best or {"dose": "partial", "reason": "no_main_exercise"}


# ---------------------------------------------------------------------------
# Requirement rows
# ---------------------------------------------------------------------------

def _skipped_refs(state: Mapping[str, Any], week_sessions: Sequence[Tuple[str, Dict[str, Any]]],
                  ws: date, we: date) -> List[Dict[str, Any]]:
    """Skipped sessions of the week: the stub's ``skipped_session_id`` (A294)
    first, else ``session_completion_log`` by date (the log has no slot)."""
    out: List[Dict[str, Any]] = []
    stub_dates = set()
    for d, s in week_sessions:
        if s.get("status") == "skipped" and s.get("skipped_session_id"):
            out.append({"date": d, "slot": s.get("slot"), "session_id": s["skipped_session_id"],
                        "tags": s.get("skipped_tags")})
            stub_dates.add((d, s["skipped_session_id"]))
    for row in state.get("session_completion_log") or []:
        if not isinstance(row, Mapping) or row.get("status") != "skipped":
            continue
        d = _parse(row.get("date"))
        if d is None or not (ws <= d <= we):
            continue
        sid = row.get("session_id") or None
        if (d.isoformat(), sid) in stub_dates:
            continue
        out.append({"date": d.isoformat(), "slot": None, "session_id": sid})
    return sorted(out, key=lambda r: (r["date"], str(r.get("slot") or ""), str(r.get("session_id") or "")))


def _free_limit_dates(state: Mapping[str, Any], since: date, until: date) -> List[str]:
    return sorted({r["date"] for r in exposures(state, since=since, until=until, families=[FAMILY_LIMIT_POWER])
                   if r["source"] == "free"})


def _outdoor_rows_in(state: Mapping[str, Any], outdoor_rows: Optional[Sequence[Mapping[str, Any]]],
                     since: date, until: date) -> List[Mapping[str, Any]]:
    out = []
    for e in _stimulus_outdoor_entries(state, outdoor_rows):
        d = _parse(e.get("date"))
        if d is not None and since <= d <= until:
            out.append(e)
    return out


def _outdoor_any(state: Mapping[str, Any], outdoor_rows: Optional[Sequence[Mapping[str, Any]]],
                 since: date, until: date) -> List[Dict[str, Any]]:
    """Outdoor days in range (any outdoor log, routes or not): technique evidence."""
    seen: Dict[str, Dict[str, Any]] = {}
    for row in list(outdoor_rows or []) + list(state.get("outdoor_log") or []):
        if not isinstance(row, Mapping):
            continue
        entry = row.get("entry") if isinstance(row.get("entry"), Mapping) else row
        d = _parse(entry.get("date"))
        if d is None or not (since <= d <= until):
            continue
        seen.setdefault(d.isoformat(), {"date": d.isoformat(), "spot_name": entry.get("spot_name")})
    return [seen[k] for k in sorted(seen)]


def _last_full_before(state: Mapping[str, Any], req: Mapping[str, Any], until: date,
                      archived_weeks: ArchivedWeeks, catalog: Mapping[str, Mapping[str, Any]],
                      lookback_d: int = 60) -> Optional[str]:
    """Last day ≤ ``until`` with a full-dose done session (or free/outdoor
    evidence) for ``req``."""
    since = until - timedelta(days=lookback_d)
    best: Optional[str] = None
    for d, s, _src in iter_plan_sessions(state, archived_weeks):
        if s.get("status") != "done" or not (since.isoformat() <= d <= until.isoformat()):
            continue
        if session_delivers(req, s, catalog) and session_dose(state, s, d, req)["dose"] == "full":
            best = d if best is None or d > best else best
    if req.get("free_limit_counts"):
        for d in _free_limit_dates(state, since, until):
            best = d if best is None or d > best else best
    return best


def _phase_history(state: Mapping[str, Any], req: Mapping[str, Any], ws: date,
                   pos: Optional[Mapping[str, Any]], archived_weeks: ArchivedWeeks,
                   catalog: Mapping[str, Mapping[str, Any]],
                   outdoor_rows: Optional[Sequence[Mapping[str, Any]]]) -> Tuple[int, int]:
    """(elapsed phase weeks before ``ws``, how many of them had no full exposure)."""
    if not pos:
        return 0, 0
    start = _parse(pos.get("phase_start"))
    if start is None:
        return 0, 0
    start = _monday(start)
    days = _plan_days(state, archived_weeks)
    elapsed = 0
    empty = 0
    wk = start
    while wk < ws:
        we = wk + timedelta(days=6)
        hit = False
        for k in range(7):
            d = (wk + timedelta(days=k)).isoformat()
            for s in days.get(d, []):
                if s.get("status") == "done" and session_delivers(req, s, catalog) \
                        and session_dose(state, s, d, req)["dose"] == "full":
                    hit = True
        if not hit and req.get("free_limit_counts") and _free_limit_dates(state, wk, we):
            hit = True
        if not hit and req.get("outdoor_hard_counts") and outdoor_hard_days(
                state, since=wk, until=we, outdoor_rows=outdoor_rows):
            hit = True
        if not hit and req.get("outdoor_counts") and _outdoor_any(state, outdoor_rows, wk, we):
            hit = True
        elapsed += 1
        empty += 0 if hit else 1
        wk += timedelta(days=7)
    return elapsed, empty


def _cap_severity(sev: str, cap: Optional[str]) -> str:
    if cap is None or cap not in SEVERITY_ORDER:
        return sev
    return sev if SEVERITY_ORDER.index(sev) <= SEVERITY_ORDER.index(cap) else cap


def _fatigue_recent(state: Mapping[str, Any], today: date,
                    week_plan: Optional[Mapping[str, Any]]) -> Optional[str]:
    """'very_hard' / 'adaptive_replan' when either happened in the last 72 h."""
    from backend.engine.retest_policy import very_hard_dates

    lo = (today - timedelta(days=FATIGUE_LOOKBACK_D)).isoformat()
    hi = today.isoformat()
    if any(lo <= v <= hi for v in very_hard_dates(state)):
        return "very_hard"
    for a in (week_plan or {}).get("adaptations") or []:
        if isinstance(a, Mapping) and a.get("type") == "adaptive_replan":
            d = str(a.get("date") or "")[:10]
            if d and lo <= d <= hi:
                return "adaptive_replan"
    return None


# ---------------------------------------------------------------------------
# Timeline checks (unified: plan + outdoor + free, this week and the next)
# ---------------------------------------------------------------------------

def _pending_tests(days: Mapping[str, List[Mapping[str, Any]]], d: date, n_days: int) -> List[str]:
    out = []
    for k in range(1, n_days + 1):
        dd = (d + timedelta(days=k)).isoformat()
        for s in days.get(dd, []):
            sid = str(s.get("session_id") or "")
            if sid.startswith("test_max") and s.get("status") not in ("done", "skipped"):
                out.append(f"{dd} {sid}")
    return out


def _finger_hard_map(state: Mapping[str, Any], lo: date, hi: date, archived_weeks: ArchivedWeeks,
                     outdoor_rows: Optional[Sequence[Mapping[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in finger_hard_days(state, since=lo, until=hi, archived_weeks=archived_weeks,
                              outdoor_rows=outdoor_rows, include_planned=True):
        out.setdefault(r["date"], []).append(r)
    return out


def _recovery_gap_days(plan: Optional[Mapping[str, Any]]) -> int:
    from backend.engine.replanner_v1 import _recovery_gap

    return max(1, int(_recovery_gap(dict(plan or {}))))


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------

def _slot_occupied(day: Mapping[str, Any]) -> set:
    from backend.engine.other_activity_v1 import other_activity_slots

    occ = {s.get("slot") for s in day.get("sessions") or [] if s.get("slot")}
    try:
        occ |= set(other_activity_slots(dict(day)))
    except Exception:  # pragma: no cover - defensive
        pass
    return occ


def _effective_availability(state: Mapping[str, Any], ws: date) -> Dict[str, Any]:
    from backend.engine.weekly_override import merge_override_into_availability

    override = (state.get("weekly_overrides") or {}).get(ws.isoformat())
    return merge_override_into_availability(state.get("availability"), override)


def _default_gym_id(state: Mapping[str, Any]) -> Optional[str]:
    gyms = ((state.get("equipment") or {}).get("gyms")) or []
    if not gyms:
        return None
    return sorted(gyms, key=lambda g: (g.get("priority", 999), g.get("gym_id", "")))[0].get("gym_id")


def _diff_plan(before: Mapping[str, Any], after: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Sessions that changed (session_id / tags / status) between two plans, by
    (date, slot). A session that disappeared is reported with ``to: None``."""
    def index(p: Mapping[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        out = {}
        for w in p.get("weeks") or []:
            for day in w.get("days") or []:
                for s in day.get("sessions") or []:
                    out[(str(day.get("date")), str(s.get("slot")))] = s
        return out
    a, b = index(before), index(after)
    changes = []
    for k, s in sorted(a.items()):
        t = b.get(k)
        if t is None:
            changes.append({"date": k[0], "slot": k[1], "before": s, "after": None})
        elif (s.get("session_id"), s.get("status"), dict(s.get("tags") or {})) != \
                (t.get("session_id"), t.get("status"), dict(t.get("tags") or {})):
            changes.append({"date": k[0], "slot": k[1], "before": s, "after": t})
    return changes


def _prev_days(state: Mapping[str, Any], ws: date, archived_weeks: ArchivedWeeks) -> Optional[List[Dict[str, Any]]]:
    prev = _week_plan(state, ws - timedelta(days=7), archived_weeks)
    if not prev:
        return None
    try:
        return (prev.get("weeks") or [{}])[0].get("days") or None
    except (IndexError, AttributeError):
        return None


def _simulate_add(state: Mapping[str, Any], plan: Mapping[str, Any], event: Mapping[str, Any],
                  ws: date, archived_weeks: ArchivedWeeks,
                  custom_sessions: Optional[List[Dict[str, Any]]] = None,
                  today: Optional[date] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Apply ``event`` on a deep copy through the replanner (the click's path:
    same prev_days seed, same frozen past as POST /events)."""
    from backend.engine.replanner_v1 import apply_events

    after = apply_events(copy.deepcopy(dict(plan)), [dict(event)],
                         custom_sessions=custom_sessions,
                         prev_days=_prev_days(state, ws, archived_weeks),
                         today=today.isoformat() if today else None)
    return after, _diff_plan(plan, after)


def _is_heavy_pull(state: Mapping[str, Any], s: Mapping[str, Any], d_iso: str) -> bool:
    """Heavy pulling for the 24 h / 2-per-7-days rules (decision 2026-10-04:
    "≥ 85 % pull"): a session of the max-pulling family (weighted pull-ups /
    chin-ups — strength_long, pulling_strength_gym, a custom with weighted
    pulls) that ``retest_policy.is_heavy_pulling_session`` reads as heavy (load
    ≥ 85 % of the official 1RM, or unreadable → prudent). Sessions that are
    "pulling + hard" only by label (PE intervals, limit boulders) are not
    weighted pulls and do not count here."""
    from backend.engine.retest_policy import is_heavy_pulling_session
    from backend.engine.stimulus import FAMILY_PULLING_MAX

    if s.get("status") == "skipped":
        return False
    if FAMILY_PULLING_MAX in session_stimuli(s) and is_heavy_pulling_session(state, s, d_iso):
        return True
    return _carries_bw_heavy_pull(state, s, d_iso)


def _carries_bw_heavy_pull(state: Mapping[str, Any], s: Mapping[str, Any], d_iso: str) -> bool:
    """A298 (DECISIONS: "no ≥85 % pull OR FRONT LEVER within 24 h before
    limit/strength_long"): any front lever level — and the one-arm pull-up
    levels — count as a heavy pull for a TESTED athlete, the same definition
    athlete_context uses. Untested athletes: unchanged (False)."""
    from backend.engine import bw_ladders as _bw

    if s.get("status") == "skipped" or not _bw.carries_heavy_bw_pull(s):
        return False
    return _bw.tested_gate(state, d_iso)


def _is_limit_class(s: Mapping[str, Any]) -> bool:
    return s.get("status") != "skipped" and (
        FAMILY_LIMIT_POWER in session_stimuli(s) or str(s.get("session_id") or "") == "strength_long")


def _heavy_pull_clash(state: Mapping[str, Any], days: Mapping[str, List[Mapping[str, Any]]],
                      d: date, slot: str, sid: str) -> Optional[Dict[str, Any]]:
    """A294 review: the heavy-pulling rules of the decisions, for a candidate
    ``sid`` on (``d``, ``slot``):

    - no heavy pull within 24 h BEFORE a limit / strength_long session (the
      candidate pulls and a limit session follows; or the candidate is a limit
      session and a heavy pull precedes it);
    - at most ``MAX_HEAVY_PULL_7D`` heavy pulling sessions in any 7 days.
    """
    from backend.engine.planner_v2 import _SESSION_META

    meta = _SESSION_META.get(sid) or {}
    cand = {"session_id": sid, "slot": slot,
            "tags": {"hard": bool(meta.get("hard")), "finger": bool(meta.get("finger")),
                     "pulling": bool(meta.get("pulling"))}}
    d_iso = d.isoformat()
    si = SLOT_INDEX.get(slot, 9)
    cand_pull = _is_heavy_pull(state, cand, d_iso)
    cand_limit = _is_limit_class(cand)

    def _after(x_d: str, x: Mapping[str, Any]) -> bool:  # x follows the candidate within 24 h
        if x_d == d_iso:
            return SLOT_INDEX.get(str(x.get("slot")), 9) > si
        return x_d == (d + timedelta(days=PRE_LIMIT_PULL_D)).isoformat()

    def _before(x_d: str, x: Mapping[str, Any]) -> bool:  # x precedes the candidate within 24 h
        if x_d == d_iso:
            return SLOT_INDEX.get(str(x.get("slot")), 9) < si
        return x_d == (d - timedelta(days=PRE_LIMIT_PULL_D)).isoformat()

    near = [(x_d, x) for x_d in ((d - timedelta(days=1)).isoformat(), d_iso, (d + timedelta(days=1)).isoformat())
            for x in days.get(x_d, [])]
    if cand_pull and not cand_limit:
        lim = [f"{x_d} {x.get('session_id')}" for x_d, x in near if _after(x_d, x) and _is_limit_class(x)]
        if lim:
            return {"reason": "heavy_pull_before_limit", "with": lim}
    if cand_limit:
        pulls = [f"{x_d} {x.get('session_id')}" for x_d, x in near
                 if _before(x_d, x) and not _is_limit_class(x) and _is_heavy_pull(state, x, x_d)]
        if pulls:
            return {"reason": "heavy_pull_before_limit", "with": pulls}
    if cand_pull:
        heavy_days: Dict[str, List[str]] = {}
        for k in range(-6, 7):
            x_d = (d + timedelta(days=k)).isoformat()
            for x in days.get(x_d, []):
                if _is_heavy_pull(state, x, x_d):
                    heavy_days.setdefault(x_d, []).append(f"{x_d} {x.get('session_id')}")
        for start in range(-6, 1):
            lo = (d + timedelta(days=start)).isoformat()
            hi = (d + timedelta(days=start + 6)).isoformat()
            inside = [r for x_d, rs in heavy_days.items() if lo <= x_d <= hi for r in rs]
            if len(inside) + 1 > MAX_HEAVY_PULL_7D:
                return {"reason": "heavy_pull_cap", "with": sorted(inside)}
    return None


def _guard_view(state: Mapping[str, Any], plan: Mapping[str, Any], ws: date,
                archived_weeks: ArchivedWeeks, today: Optional[date]) -> List[Dict[str, Any]]:
    """A301: the guard alerts of ``plan`` (``guards_v1``), seeded with the
    previous week like the click's path."""
    return _guards_mod.evaluate(plan, _prev_days(state, ws, archived_weeks),
                                today.isoformat() if today else None, state)


def _added_present(after: Mapping[str, Any], d_iso: str, slot: str, session_id: str) -> bool:
    for w in after.get("weeks") or []:
        for day in w.get("days") or []:
            if str(day.get("date")) != d_iso:
                continue
            for s in day.get("sessions") or []:
                if s.get("slot") == slot and s.get("session_id") == session_id:
                    return True
    return False


def _propose_for(
    state: Mapping[str, Any], reqs: Sequence[Dict[str, Any]], *, today: date, ws: date,
    plan: Mapping[str, Any], key_index: Mapping[Tuple[str, str], List[str]],
    archived_weeks: ArchivedWeeks, outdoor_rows: Optional[Sequence[Mapping[str, Any]]],
    reentry: Mapping[str, bool], next_week_keys: Mapping[str, List[Dict[str, Any]]],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """The first valid re-schedule covering ``reqs`` (greedy: catalog order of
    ``propose``, then date, then the planner's slot preference), or None with
    the reasons the candidates were rejected."""
    from backend.engine.macrocycle_v1 import _build_session_pool
    from backend.engine.planner_v2 import (
        WEEKDAYS,
        _SESSION_META,
        _find_best_slot,
        _normalize_availability,
        _pick_location,
        _primary_view,
        _select_gym_id,
        allowed_locations_for,
    )

    snapshot = plan.get("profile_snapshot") or {}
    phase_id = snapshot.get("phase_id")
    pool = list(snapshot.get("session_pool") or [])
    if not pool and phase_id:
        try:
            pool = _build_session_pool(phase_id, (state.get("goal") or {}).get("discipline") or "lead")
        except Exception:
            pool = []
    primary = reqs[0]
    candidates: List[str] = []
    # A294 review: the phase's key catalog is the authority on what the phase
    # needs, so a stimulus it requires may be proposed even when the planner's
    # session pool lacks it (PE asks for limit every 12 days, deload for
    # technique, and neither pool holds those sessions). In-pool sessions are
    # still preferred.
    ordered = [sid for sid in primary.get("propose") or [] if not pool or sid in pool] + \
              [sid for sid in primary.get("propose") or [] if pool and sid not in pool]
    for sid in ordered:
        if sid not in _SESSION_META:
            continue
        if reentry.get(primary["key"]) and sid in (primary.get("reentry_excluded") or []):
            continue
        # A candidate must cover every requirement of the group.
        if all(sid in (r.get("propose") or []) or sid in (r.get("session_ids") or []) for r in reqs):
            candidates.append(sid)
    if not candidates:
        return None, {"reason": "no_candidate"}

    equipment = state.get("equipment") or {}
    gyms = list(equipment.get("gyms") or [])
    home_eq = equipment.get("home")
    try:
        locations = list(allowed_locations_for(equipment))
    except Exception:
        locations = ["gym", "home"]
    # A300: a key session is never proposed on a complementary slot.
    norm = _primary_view(_normalize_availability(_effective_availability(state, ws), locations))
    default_gym = _default_gym_id(state)
    we = ws + timedelta(days=6)
    gap = _recovery_gap_days(plan)
    days_all = _plan_days(state, archived_weeks)
    fh = _finger_hard_map(state, ws - timedelta(days=gap + 1), we + timedelta(days=NEXT_WEEK_LOOKAHEAD_D + gap),
                          archived_weeks, outdoor_rows)
    outdoor_days = {e["date"] for e in _outdoor_any(state, outdoor_rows, ws, we)}
    plan_days = {str(day.get("date")): day for w in plan.get("weeks") or [] for day in w.get("days") or []}
    hard_cap_raw = snapshot.get("hard_cap_per_week")
    rejections: List[Dict[str, Any]] = []
    deferred_next: Optional[Dict[str, Any]] = None
    # A day on which the athlete skipped this very stimulus is not a candidate:
    # the skip says that day does not work.
    skipped_days = {str(day.get("date")) for day in plan_days.values() for s in day.get("sessions") or []
                    if s.get("status") == "skipped" and s.get("skipped_session_id")
                    and any(s["skipped_session_id"] in (r.get("propose") or []) + (r.get("session_ids") or [])
                            for r in reqs)}
    guards_before: Optional[List[Dict[str, Any]]] = None
    start = max(today, ws)
    d = start
    while d <= we:
        d_iso = d.isoformat()
        day = plan_days.get(d_iso)
        if day is None or d_iso in outdoor_days or d_iso in skipped_days \
                or day.get("outdoor_spot_name") or day.get("outdoor_spot_id"):
            d += timedelta(days=1)
            continue
        if any(c in (s.get("constraints_applied") or []) for s in day.get("sessions") or []
               for c in ("pretrip_deload", "other_activity_reduce")):
            d += timedelta(days=1)
            continue
        wd = WEEKDAYS[d.weekday()]
        occupied = _slot_occupied(day)
        for sid in candidates:
            meta = _SESSION_META[sid]
            finger = bool(meta.get("finger")) or primary.get("finger_hard")
            hard = bool(meta.get("hard"))
            # Finger gap against the unified timeline (plan + outdoor + free,
            # previous and next week included).
            if finger:
                clash = []
                for k in range(-gap, gap + 1):
                    dd = (d + timedelta(days=k)).isoformat()
                    for r in fh.get(dd, []):
                        clash.append((dd, r))
                if clash:
                    nxt = [c for c in clash if c[0] > we.isoformat()]
                    if nxt and not [c for c in clash if c[0] <= we.isoformat()]:
                        deferred_next = deferred_next or {"date": nxt[0][0], "session_id": nxt[0][1].get("session_id")}
                    rejections.append({"date": d_iso, "session_id": sid, "reason": "finger_gap",
                                       "with": sorted({c[0] for c in clash})})
                    continue
            # A294 review: a test later the SAME day counts too (a hard lunch
            # session before an evening max test measures fatigue).
            same_day_test = any(str(x.get("session_id") or "").startswith("test_max")
                                and x.get("status") not in ("done", "skipped") for x in days_all.get(d_iso, []))
            if (finger or hard) and (same_day_test or _pending_tests(days_all, d, PRE_TEST_BLOCK_H // 24)):
                rejections.append({"date": d_iso, "session_id": sid, "reason": "pre_test"})
                continue
            res = _find_best_slot(norm.get(wd, {}), meta, locations, prefer_evening=True,
                                  home_equipment=home_eq, gyms=gyms, default_gym_id=default_gym,
                                  occupied_slots=occupied)
            if not res:
                rejections.append({"date": d_iso, "session_id": sid, "reason": "no_slot"})
                continue
            slot, slot_info = res
            pull_clash = _heavy_pull_clash(state, days_all, d, slot, sid)
            if pull_clash:
                rejections.append({"date": d_iso, "session_id": sid, "reason": pull_clash["reason"],
                                   "with": pull_clash["with"]})
                continue
            location = _pick_location(meta.get("location", ("gym",)), slot_info, locations,
                                      required_equipment=meta.get("required_equipment"),
                                      home_equipment=home_eq, gyms=gyms, default_gym_id=default_gym) or "gym"
            gym_id = _select_gym_id(slot_info, default_gym, gyms) if location == "gym" else None
            event = {"event_type": "add_planned_session", "session_id": sid, "target_date": d_iso,
                     "slot": slot, "location": location, "gym_id": gym_id}
            try:
                after, changes = _simulate_add(state, plan, event, ws, archived_weeks, today=today)
            except ValueError as exc:
                rejections.append({"date": d_iso, "session_id": sid, "reason": f"invalid: {exc}"})
                continue
            if not _added_present(after, d_iso, slot, sid):
                rejections.append({"date": d_iso, "session_id": sid, "reason": "downshifted_by_reconcile"})
                continue
            # A301: applying the proposal rewrites nothing around it any more
            # (guards are alerts after a user action), so the ENGINE's
            # proposal must not need it: a candidate that would raise a guard
            # alert the week did not already have (finger gap with a finger
            # maintenance, hard cap, HIIT before it…) is rejected — it used to
            # be accepted with the neighbour declared as a side effect.
            if guards_before is None:
                guards_before = _guard_view(state, plan, ws, archived_weeks, today)
            fresh = _guards_mod.new_warnings(guards_before, _guard_view(state, after, ws, archived_weeks, today))
            if fresh:
                rejections.append({"date": d_iso, "session_id": sid, "reason": "guard_alert",
                                   "codes": sorted({w["code"] for w in fresh}),
                                   "with": sorted({f"{w['date']} {w.get('session_id')}" for w in fresh})})
                continue
            bad = []
            side = []
            for c in changes:
                b = c["before"]
                protected = (b.get("status") in ("done", "skipped") or b.get("forced") or b.get("is_custom")
                             or key_index.get((c["date"], c["slot"])))
                if protected:
                    bad.append(c)
                else:
                    side.append({"date": c["date"], "slot": c["slot"],
                                 "from": b.get("session_id"),
                                 "to": (c["after"] or {}).get("session_id"),
                                 "reason": ((c["after"] or {}).get("constraints_applied") or [None])[0]})
            if bad:
                rejections.append({"date": d_iso, "session_id": sid, "reason": "touches_protected",
                                   "sessions": [f"{c['date']} {c['before'].get('session_id')}" for c in bad]})
                continue
            hard_after = sum(
                1 for w in after.get("weeks") or [] for dd in w.get("days") or []
                if any((s.get("tags") or {}).get("hard") and s.get("status") != "done" for s in dd.get("sessions") or [])
            )
            proposal = {
                "keys": [r["key"] for r in reqs],
                "date": d_iso,
                "slot": slot,
                "session_id": sid,
                "session_name": _session_name(sid),
                "location": location,
                "gym_id": gym_id,
                "reduced_reentry_dose": bool(reentry.get(primary["key"])) and bool(primary.get("reentry_excluded")),
                "side_effects": side,
                "checks": {"finger_gap_ok": True, "pre_test_ok": True, "heavy_pulling_ok": True,
                           "hard_days_after": hard_after,
                           "hard_cap": int(hard_cap_raw) if _num(hard_cap_raw) is not None else None},
                "apply": {"endpoint": "/api/replanner/events", "event": event},
                "_after": after,  # popped by the caller (cumulative validation)
            }
            return proposal, {}
        d += timedelta(days=1)
    info: Dict[str, Any] = {"reason": "no_valid_day", "rejections": rejections}
    if deferred_next:
        info["deferred_next"] = deferred_next
    return None, info


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_key_status(
    state: Mapping[str, Any],
    today: DateLike,
    *,
    archived_weeks: ArchivedWeeks = None,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    week_start: Optional[DateLike] = None,
    exercise_catalog: Optional[Mapping[str, Mapping[str, Any]]] = None,
    key_catalog: Optional[Mapping[str, Any]] = None,
    with_proposals: bool = True,
) -> Dict[str, Any]:
    """The key status of one week. See the module docstring for the contract.

    Returns::

        {version, source: "a294", as_of, week_start, week_end, phase_id,
         is_current_week, is_past_week, reentry: {stimulus: bool},
         requirements: [{key, label, why, priority, target, status, resolution,
                         severity, debt, done[], partial[], planned[], skipped[],
                         lost[], last_full_date?, due_by?, exposures_21d,
                         next_key?, hint?}],
         sessions: [{date, slot, session_id, role, keys}],
         proposals: [...], conflicts: [...],
         summary: {required, covered, done, missing, debt, max_severity}}
    """
    st: Dict[str, Any] = copy.deepcopy(dict(state or {}))
    arch = copy.deepcopy(archived_weeks) if archived_weeks is not None else None
    rows = copy.deepcopy(list(outdoor_rows)) if outdoor_rows is not None else None
    cat = exercise_catalog if exercise_catalog is not None else _load_exercise_catalog_file()
    td = _as_date(today)
    ws = _monday(_as_date(week_start) if week_start is not None else td)
    we = ws + timedelta(days=6)
    is_past = we < td
    is_current = ws <= td <= we

    plan = _week_plan(st, ws, arch)
    pos = _phase_on(st, ws)
    phase_id = ((plan or {}).get("profile_snapshot") or {}).get("phase_id") or (pos or {}).get("phase_id")
    if pos and pos.get("phase_id") and phase_id != pos.get("phase_id") and plan is None:
        phase_id = pos.get("phase_id")
    reqs = phase_requirements(phase_id, key_catalog)

    days = _plan_days(st, arch)
    week_sessions: List[Tuple[str, Dict[str, Any]]] = []
    for k in range(7):
        d = (ws + timedelta(days=k)).isoformat()
        for s in days.get(d, []):
            week_sessions.append((d, s))
    hard_outdoor = outdoor_hard_days(st, since=ws, until=we, outdoor_rows=rows)
    any_outdoor = _outdoor_any(st, rows, ws, we)
    free_limit = _free_limit_dates(st, ws, we)
    skipped_all = _skipped_refs(st, week_sessions, ws, we)
    unmet = {str((u or {}).get("stimulus")) for u in ((plan or {}).get("unmet_stimulus") or []) if isinstance(u, Mapping)}
    lookback = td if not is_past else we
    reentry: Dict[str, bool] = {}
    for fam in (FAMILY_FINGER_MAX, FAMILY_LIMIT_POWER):
        n = count_exposures(st, fam, since=lookback - timedelta(days=REENTRY_WINDOW_D), until=lookback,
                            archived_weeks=arch)
        reentry[fam] = n < REENTRY_MIN_EXPOSURES

    out_rows: List[Dict[str, Any]] = []
    for req in reqs:
        done: List[Dict[str, Any]] = []
        partial: List[Dict[str, Any]] = []
        planned: List[Dict[str, Any]] = []
        for d, s in week_sessions:
            if not session_delivers(req, s, cat):
                continue
            status = s.get("status")
            if status == "skipped":
                continue
            dose = session_dose(st, s, d, req)
            if status == "done":
                ref = _ref(d, s, dose=dose["dose"], dose_reason=dose.get("reason"))
                (done if dose["dose"] == "full" else partial).append(ref)
            else:
                ref = _ref(d, s, dose=dose["dose"], dose_reason=dose.get("reason"))
                if d < td.isoformat():
                    ref["unmarked"] = True  # in the past, never marked done/skipped
                planned.append(ref)
        if req.get("outdoor_counts"):
            for e in any_outdoor:
                if not any(x["date"] == e["date"] for x in done):
                    done.append({"date": e["date"], "slot": None, "session_id": None,
                                 "name": f"outdoor {e.get('spot_name') or ''}".strip(), "status": "done",
                                 "dose": "full", "evidence": "outdoor (regole tecniche non verificabili)"})
        if req.get("outdoor_hard_counts"):
            for o in hard_outdoor:
                if not any(x["date"] == o["date"] for x in done):
                    done.append({"date": o["date"], "slot": None, "session_id": None, "name": "outdoor hard",
                                 "status": "done", "dose": "full",
                                 "evidence": f"outdoor ≥ soglia hard ({o.get('grade')})"})
        if req.get("free_limit_counts"):
            for d_iso in free_limit:
                if not any(x["date"] == d_iso for x in done):
                    done.append({"date": d_iso, "slot": None, "session_id": None, "name": "free boulder",
                                 "status": "done", "dose": "full", "evidence": "free session ≥ soglia"})
        skipped = [k for k in skipped_all if k.get("session_id")
                   and session_delivers(req, {"session_id": k["session_id"], "tags": {}}, cat)]
        lost = [dict(k, reason="skipped") for k in skipped]
        # A294 review: a downshift is a LOST key stimulus only while the
        # requirement is still owed (checked below, once the debt is known) —
        # otherwise a covered stimulus raised a high "key stimulus is lost".
        lost_down = []
        for d, s in week_sessions:
            prev = s.get("downshifted_from")
            if prev and session_delivers(req, {"session_id": prev}, cat):
                lost_down.append({"date": d, "slot": s.get("slot"), "session_id": prev,
                                  "reason": (s.get("constraints_applied") or ["downshift"])[0]})

        target = int(req.get("target_per_week") or 1)
        full_days = sorted({x["date"] for x in done})
        satisfied = len(full_days)
        valid_planned = sorted({p["date"] for p in planned if not p.get("unmarked") and p["dose"] == "full"
                                and p["date"] not in full_days})
        debt = max(0, target - satisfied - len(valid_planned))
        row: Dict[str, Any] = {
            "key": req["key"], "label": req.get("label"), "why": req.get("why"),
            "priority": req.get("priority"), "max_severity": req.get("max_severity"),
            "target": target, "done": sorted(done, key=lambda x: (x["date"], str(x.get("slot") or ""))),
            "partial": partial, "planned": planned, "skipped": skipped, "lost": lost,
            "debt": debt, "resolution": None, "severity": "none",
        }
        if req["key"] in ("finger_max", "limit_power", "finger_maintenance"):
            fam = FAMILY_LIMIT_POWER if req["key"] == "limit_power" else FAMILY_FINGER_MAX
            row["exposures_21d"] = count_exposures(st, fam, since=lookback - timedelta(days=REENTRY_WINDOW_D),
                                                   until=lookback, archived_weeks=arch)
        if satisfied >= target:
            row["status"] = "done"
        elif debt == 0:
            row["status"] = "planned"
        elif partial:
            row["status"] = "partial"
        else:
            row["status"] = "missing"
        if req["key"] in ("finger_max", "finger_maintenance") and "finger_strength" in unmet and debt > 0:
            row["status"] = "unplaceable"
            row["debt"] = 0
            row["hint"] = "the planner could not place a finger session this week (see the unmet-stimulus card)"
        if req.get("max_gap_days"):
            last = _last_full_before(st, req, min(td, we), arch, cat)
            last_d = _parse(last)
            due = (last_d + timedelta(days=int(req["max_gap_days"]))) if last_d else None
            row["last_full_date"] = last_d.isoformat() if last_d else None
            row["last_done"] = row["last_full_date"]  # A293 name, kept for the CLI
            row["due_by"] = due.isoformat() if due else None
            if row["status"] == "missing" and due is not None and due > we:
                row["status"] = "not_due"
                row["debt"] = 0
        if row["debt"] > 0:
            row["lost"].extend(lost_down)
        out_rows.append(row)

    # The try-hard rides on its host key (limit, or project in performance):
    # no host due in this phase/week → no try-hard owed.
    by_key = {r["key"]: r for r in out_rows}
    req_by_key = {r["key"]: r for r in reqs}
    tryhard_host = (req_by_key.get("try_hard") or {}).get("attached_to") or "limit_power"
    host_row = by_key.get(tryhard_host)
    if "try_hard" in by_key and by_key["try_hard"]["status"] in ("missing", "partial") \
            and (host_row is None or host_row.get("status") in ("not_due", "unplaceable")):
        by_key["try_hard"]["status"] = "not_due"
        by_key["try_hard"]["debt"] = 0
    if "try_hard" in by_key and by_key["try_hard"]["debt"] > 0:
        nxt = sorted([p for p in (host_row or {}).get("planned") or [] if not p.get("unmarked")],
                     key=lambda p: p["date"])
        host_name = "projecting" if tryhard_host == "project" else "limit"
        by_key["try_hard"]["hint"] = (
            f"add a fall-practice block (fall_practice) to the {host_name} session of {nxt[0]['date']}"
            if nxt else f"add a fall-practice block (fall_practice) to your next {host_name} session")

    # Roles: the minimal set of sessions that covers each target is "key".
    sessions_roles: Dict[Tuple[str, str], Dict[str, Any]] = {}
    key_index: Dict[Tuple[str, str], List[str]] = {}
    prop_order = {r["key"]: list(r.get("propose") or []) for r in reqs}
    for r, req in zip(out_rows, reqs):
        if req["key"] == "try_hard":
            continue
        cands: List[Tuple[Tuple[Any, ...], str, Dict[str, Any], bool]] = []
        for d, s in week_sessions:
            if s.get("status") == "skipped" or not session_delivers(req, s, cat):
                continue
            dose = session_dose(st, s, d, req)["dose"]
            done_full = s.get("status") == "done" and dose == "full"
            order = prop_order[req["key"]]
            sid = str(s.get("session_id") or "")
            rank = (0 if done_full else 1, 0 if dose == "full" else 1, 1 if s.get("is_custom") else 0,
                    order.index(sid) if sid in order else len(order), d, str(s.get("slot") or ""))
            cands.append((rank, d, s, dose == "full"))
        cands.sort(key=lambda c: c[0])
        n_key = 0
        target = r["target"]
        for _rank, d, s, full in cands:
            k = (d, str(s.get("slot")))
            if full and n_key < target:
                role = "key"
                n_key += 1
            else:
                fam_reentry = reentry.get(FAMILY_FINGER_MAX if req["key"] != "limit_power" else FAMILY_LIMIT_POWER)
                role = "optional" if (fam_reentry and req.get("finger_hard") and s.get("status") != "done") else "supporting"
            entry = sessions_roles.setdefault(k, {"date": d, "slot": s.get("slot"),
                                                  "session_id": s.get("session_id"),
                                                  "status": s.get("status") or "planned",
                                                  "role": role, "keys": [], "supporting": []})
            if ROLE_ORDER.index(role) > ROLE_ORDER.index(entry["role"]):
                entry["role"] = role
            if role == "key":
                entry["keys"].append(req["key"])
                key_index.setdefault(k, []).append(req["key"])
            else:
                entry["supporting"].append(req["key"])
    for k, e in sessions_roles.items():
        if e["role"] == "key" and tryhard_host in e["keys"] and "try_hard" in by_key:
            e["keys"].append("try_hard")
    for r in out_rows:
        for sk in r["skipped"]:
            k = (sk["date"], str(sk.get("slot")))
            if sk.get("slot") and k not in sessions_roles:
                sessions_roles[k] = {"date": sk["date"], "slot": sk.get("slot"), "session_id": sk["session_id"],
                                     "status": "skipped", "role": "skipped", "keys": [r["key"]], "supporting": []}
            elif sk.get("slot") and sessions_roles[k]["role"] == "skipped":
                sessions_roles[k]["keys"].append(r["key"])
        for lo in r["lost"]:
            if lo.get("reason") == "skipped" or not lo.get("slot"):
                continue
            k = (lo["date"], str(lo.get("slot")))
            entry = sessions_roles.setdefault(k, {"date": lo["date"], "slot": lo.get("slot"),
                                                  "session_id": None, "status": "planned",
                                                  "role": "downgraded", "keys": [], "supporting": []})
            entry.setdefault("downgraded_from", lo["session_id"])
            if entry["role"] not in ("key",):
                entry["role"] = "downgraded"
            if r["key"] not in entry["keys"]:
                entry["keys"].append(r["key"])

    # Next week's key sessions (planning info for deferred_next).
    next_week_keys: Dict[str, List[Dict[str, Any]]] = {}
    nws = ws + timedelta(days=7)
    for k in range(7):
        d = (nws + timedelta(days=k)).isoformat()
        for s in days.get(d, []):
            if s.get("status") in ("done", "skipped"):
                continue
            npos = _phase_on(st, nws)
            for nreq in phase_requirements((npos or {}).get("phase_id") or phase_id, key_catalog):
                if nreq["key"] != "try_hard" and session_delivers(nreq, s, cat):
                    next_week_keys.setdefault(nreq["key"], []).append(_ref(d, s))

    # Resolution, proposals and severity.
    fatigue = _fatigue_recent(st, td, plan) if is_current else None
    proposals: List[Dict[str, Any]] = []
    finger_proposal_made = False
    covered: set = set()
    # A294 review: proposals are validated CUMULATIVELY — each one against the
    # plan with the previous proposals already applied (same slot, finger gap,
    # hard cap, heavy pulling), never each alone against the original plan.
    work_st: Dict[str, Any] = st
    work_plan: Optional[Dict[str, Any]] = plan
    work_index: Dict[Tuple[str, str], List[str]] = {k: list(v) for k, v in key_index.items()}
    for r, req in sorted(zip(out_rows, reqs), key=lambda x: (x[1].get("priority") or 9, x[1]["key"])):
        if r["debt"] <= 0 or r["status"] in ("not_due", "unplaceable"):
            continue
        if is_past or plan is None:
            r["resolution"] = "missed"
        elif td > we:
            r["resolution"] = "missed"
        elif fatigue:
            r["resolution"] = "deferred_fatigue"
            r["fatigue_reason"] = fatigue
        elif req["key"] in covered:
            r["resolution"] = "proposal"
        elif not with_proposals or not req.get("propose"):
            r["resolution"] = None
        elif req.get("finger_hard") and finger_proposal_made:
            r["resolution"] = "let_go"
            r["hint"] = "one finger catch-up per week at most"
        else:
            group = [req]
            # strength_long covers finger_max + pulling_max in one session.
            reentry_arg = {"finger_max": reentry[FAMILY_FINGER_MAX], "limit_power": reentry[FAMILY_LIMIT_POWER]}
            if req["key"] == "finger_max" and (by_key.get("pulling_max") or {}).get("debt", 0) > 0:
                pull_req = next(x for x in reqs if x["key"] == "pulling_max")
                group_try = [dict(req, propose=["strength_long"]), pull_req]
                prop, info = _propose_for(work_st, group_try, today=td, ws=ws, plan=work_plan,
                                          key_index=work_index, archived_weeks=arch, outdoor_rows=rows,
                                          reentry=reentry_arg, next_week_keys=next_week_keys)
                if prop:
                    group = group_try
                else:
                    prop, info = None, {}
            else:
                prop, info = None, {}
            if prop is None:
                prop, info = _propose_for(work_st, group, today=td, ws=ws, plan=work_plan,
                                          key_index=work_index, archived_weeks=arch, outdoor_rows=rows,
                                          reentry=reentry_arg, next_week_keys=next_week_keys)
            if prop:
                after_plan = prop.pop("_after", None)
                if proposals:
                    # Validated with the earlier proposals in place.
                    prop["assumes"] = [{"date": p["date"], "slot": p["slot"], "session_id": p["session_id"]}
                                       for p in proposals]
                proposals.append(prop)
                r["resolution"] = "proposal"
                covered.update(prop["keys"])
                if req.get("finger_hard"):
                    finger_proposal_made = True
                if after_plan is not None:
                    work_st = copy.deepcopy(work_st)
                    work_st.setdefault("week_plans", {})[ws.isoformat()] = after_plan
                    if isinstance(work_st.get("current_week_plan"), dict) and \
                            str(work_st["current_week_plan"].get("start_date") or "") == ws.isoformat():
                        work_st["current_week_plan"] = after_plan
                    work_plan = after_plan
                    work_index.setdefault((prop["date"], str(prop["slot"])), []).extend(prop["keys"])
            elif info.get("deferred_next") or next_week_keys.get(req["key"]):
                nk = next_week_keys.get(req["key"]) or []
                r["resolution"] = "deferred_next"
                r["next_key"] = (nk[0] if nk else info.get("deferred_next"))
            elif info.get("reason") == "no_candidate":
                # A294 review: no catalog session can carry it with this
                # equipment — "no safe day left" would be a false reason.
                r["resolution"] = None
                r["hint"] = "no session you can do with your equipment carries it — add it from the week view"
            else:
                r["resolution"] = "let_go"
            if info.get("rejections"):
                r["rejections"] = info["rejections"][:12]
    for r, req in zip(out_rows, reqs):
        if r["debt"] <= 0 or r["status"] in ("not_due", "unplaceable"):
            r["severity"] = "none"
            continue
        if r["resolution"] in ("deferred_fatigue", "let_go", "deferred_next"):
            sev = "info" if r["resolution"] != "let_go" else "warning"
        else:
            sev = "warning"
            # A294 review: escalation follows the catalog's max_severity, not
            # the priority — the GOAL REFRAME wants a missed technique stimulus
            # (priority 2) to raise the same card as a missed finger session.
            if req.get("max_severity") == "critical" and r["status"] != "partial":
                elapsed, empty = _phase_history(st, req, ws, pos, arch, cat, rows)
                last_week = bool(pos and pos.get("is_last_week_of_phase"))
                share = (empty + 1) / (elapsed + 1)
                if (last_week and not r["done"] and (is_past or td >= we)) or share >= CRITICAL_PHASE_SHARE and elapsed >= 1:
                    sev = "critical"
        if r["status"] == "partial":
            sev = _cap_severity(sev, "warning")
        r["severity"] = _cap_severity(sev, req.get("max_severity"))

    conflicts = _conflicts(st, td, ws, we, week_sessions, sessions_roles, days, arch, rows, plan) \
        if not is_past else []

    covered_n = sum(1 for r in out_rows if r["status"] in ("done", "planned", "not_due"))
    max_sev = max((r["severity"] for r in out_rows), key=SEVERITY_ORDER.index, default="none")
    return {
        "version": VERSION,
        "source": "a294",
        "as_of": td.isoformat(),
        "week_start": ws.isoformat(),
        "week_end": we.isoformat(),
        "phase_id": phase_id,
        "is_current_week": is_current,
        "is_past_week": is_past,
        "reentry": {"finger_max": reentry[FAMILY_FINGER_MAX], "limit_power": reentry[FAMILY_LIMIT_POWER]},
        "requirements": out_rows,
        "sessions": [sessions_roles[k] for k in sorted(sessions_roles)],
        "proposals": proposals,
        "conflicts": conflicts,
        "summary": {
            "required": len(out_rows),
            "covered": covered_n,
            "done": sum(1 for r in out_rows if r["status"] == "done"),
            "missing": [r["key"] for r in out_rows if r["debt"] > 0],
            "debt": sum(r["debt"] for r in out_rows),
            "max_severity": max_sev,
        },
        "unknown_skips": [k for k in skipped_all if not k.get("session_id")],
        "removed_unknown": _removed_unknown(st, ws),
    }


def _removed_unknown(state: Mapping[str, Any], ws: date) -> int:
    n = 0
    for w in (state.get("week_plans") or {}).values():
        if not isinstance(w, Mapping) or str(w.get("start_date") or "") != ws.isoformat():
            continue
        for a in w.get("adaptations") or []:
            if not isinstance(a, Mapping):
                continue
            ev = a.get("event") if isinstance(a.get("event"), Mapping) else a
            if ev.get("event_type") == "remove_session" and not ev.get("session_ref") and not ev.get("session_id"):
                n += 1
    return n


# ---------------------------------------------------------------------------
# Conflicts (warnings, never blocks)
# ---------------------------------------------------------------------------

def _conflicts(
    state: Mapping[str, Any], today: date, ws: date, we: date,
    week_sessions: Sequence[Tuple[str, Dict[str, Any]]],
    roles: Mapping[Tuple[str, str], Mapping[str, Any]],
    days: Mapping[str, List[Mapping[str, Any]]], archived_weeks: ArchivedWeeks,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]], plan: Optional[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    from backend.engine.retest_policy import is_heavy_pulling_session

    out: List[Dict[str, Any]] = []
    t_iso = today.isoformat()
    for (d, slot), e in sorted(roles.items()):
        if e.get("role") == "downgraded" and d >= t_iso:
            out.append({"code": "key_downgraded", "severity": "high", "date": d, "slot": e.get("slot"),
                        "session_id": e.get("downgraded_from"), "keys": e.get("keys"),
                        "message": f"{_session_name(e.get('downgraded_from'))} on {d} was turned into recovery "
                                   "by the spacing rules — the key stimulus is lost unless you move it."})
    gap = _recovery_gap_days(plan)
    fh = _finger_hard_map(state, ws - timedelta(days=gap), we + timedelta(days=gap), archived_weeks, outdoor_rows)
    for d, s in week_sessions:
        if d < t_iso or s.get("status") in ("done", "skipped"):
            continue
        dd = _as_date(d)
        hard_or_finger = session_flag(s, "hard") or is_finger_hard_session(s)
        if hard_or_finger and not is_test_session(s):
            tests = _pending_tests(days, dd, PRE_TEST_BLOCK_H // 24)
            if tests:
                out.append({"code": "pre_test_fatigue", "severity": "high", "date": d, "slot": s.get("slot"),
                            "session_id": s.get("session_id"), "tests": tests,
                            "message": f"Hard session on {d} within 72 h of a max test ({tests[0]}): "
                                       "the test would measure fatigue, not strength."})
        role = (roles.get((d, str(s.get("slot")))) or {}).get("role")
        if role == "key" and is_finger_hard_session(s):
            clash = []
            for k in range(-gap, gap + 1):
                if k == 0:
                    continue
                other = (dd + timedelta(days=k)).isoformat()
                for r in fh.get(other, []):
                    if r.get("session_id") != s.get("session_id") or other != d:
                        clash.append(f"{other} {r.get('session_id') or r.get('reason')}")
            same_day = [x for x in days.get(d, []) if x is not s and x.get("status") != "skipped"
                        and is_finger_hard_session(x)]
            clash += [f"{d} {x.get('session_id')}" for x in same_day]
            if clash:
                out.append({"code": "finger_gap", "severity": "medium", "date": d, "slot": s.get("slot"),
                            "session_id": s.get("session_id"), "with": sorted(set(clash)),
                            "message": f"Another finger-hard day sits within {gap} day(s) of the key session "
                                       f"on {d}: one of them will not be at full quality."})
        if role == "key" and (FAMILY_LIMIT_POWER in session_stimuli(s) or s.get("session_id") == "strength_long"):
            for k in range(1, PRE_LIMIT_PULL_D + 1):
                prev = (dd - timedelta(days=k)).isoformat()
                same = [x for x in days.get(d, []) if x is not s and x.get("status") != "skipped"
                        and SLOT_INDEX.get(str(x.get("slot")), 9) < SLOT_INDEX.get(str(s.get("slot")), 9)]
                cands = [x for x in days.get(prev, []) if x.get("status") != "skipped"] + same
                heavy = [x for x in cands if x.get("session_id") != s.get("session_id")
                         and (is_heavy_pulling_session(state, x, prev) or _carries_bw_heavy_pull(state, x, prev))
                         and not is_finger_hard_session(x)]
                if heavy:
                    out.append({"code": "pulling_overlap", "severity": "medium", "date": d, "slot": s.get("slot"),
                                "session_id": s.get("session_id"),
                                "with": [f"{prev} {x.get('session_id')}" for x in heavy],
                                "message": f"Heavy pulling within 24 h before the key session on {d}."})
    return out


SLOT_INDEX = {"morning": 0, "lunch": 1, "evening": 2}


# ---------------------------------------------------------------------------
# Insertion check (custom collision warning, coach preview)
# ---------------------------------------------------------------------------

def _is_key_lost(before: Mapping[str, Any], after: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Requirements whose coverage got worse between two key statuses."""
    b = {r["key"]: r for r in before.get("requirements") or []}
    lost = []
    rank = {"done": 0, "planned": 1, "not_due": 1, "partial": 2, "missing": 3, "unplaceable": 3}
    for r in after.get("requirements") or []:
        prev = b.get(r["key"])
        if prev is None:
            continue
        if r["debt"] > prev["debt"] or rank.get(r["status"], 3) > rank.get(prev["status"], 3):
            lost.append({"key": r["key"], "label": r.get("label"),
                         "before": prev["status"], "after": r["status"]})
    return lost


def check_insertion(
    state: Mapping[str, Any],
    today: DateLike,
    *,
    plan: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    archived_weeks: ArchivedWeeks = None,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    custom_sessions: Optional[List[Dict[str, Any]]] = None,
    exercise_catalog: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """What ``events`` (typically one ``add_custom_session`` /
    ``add_generated_session``) would do to the key sessions of ``plan``'s week.

    Runs the events through ``apply_events`` on a deep copy (prev_days seeded),
    then compares the key status before and after. Returns::

        {week_plan, adjustments, key_status, key_conflicts: [...], added_guard_warnings: [...]}

    A301: ``apply_events`` no longer downshifts anything after a user action,
    so ``adjustments`` is empty and the ``key_removed`` / ``key_replaced`` /
    ``test_downgraded`` codes (all born from a reconcile downshift) no longer
    arise from an insertion; the clash is reported as ``finger_gap`` /
    ``pre_test_fatigue`` and in ``added_guard_warnings`` (the alerts the insertion
    ADDS to the week, ``guards_v1``).

    ``key_conflicts`` codes: ``key_removed`` (high — a key session was
    downgraded or replaced; ``replace_key: true`` when the inserted session
    delivers the same stimulus at full dose, i.e. it can take the key's place),
    ``pre_test_fatigue`` (high), ``finger_gap`` (high since the A294 review —
    the inserted session is finger-hard within the recovery gap of a
    finger-hard day the reconcile cannot move).
    Nothing is persisted.
    """
    from backend.engine.replanner_v1 import apply_events

    cat = exercise_catalog if exercise_catalog is not None else _load_exercise_catalog_file()
    st = copy.deepcopy(dict(state or {}))
    ws_iso = str(plan.get("start_date") or "")
    ws = _monday(_as_date(ws_iso)) if ws_iso else _monday(_as_date(today))
    before_plan = copy.deepcopy(dict(plan))
    st.setdefault("week_plans", {})
    st["week_plans"][ws.isoformat()] = before_plan
    before = compute_key_status(st, today, archived_weeks=archived_weeks, outdoor_rows=outdoor_rows,
                                week_start=ws, exercise_catalog=cat, with_proposals=False)
    after_plan = apply_events(copy.deepcopy(before_plan), [dict(e) for e in events],
                              custom_sessions=custom_sessions,
                              prev_days=_prev_days(st, ws, archived_weeks),
                              today=_as_date(today).isoformat())
    adjustments: List[Dict[str, Any]] = []
    for a in after_plan.get("adaptations") or []:
        if isinstance(a, Mapping) and a.get("type") == "reconcile":
            adjustments.extend(a.get("adjustments") or [])
    st_after = copy.deepcopy(st)
    st_after["week_plans"][ws.isoformat()] = after_plan
    if isinstance(st_after.get("current_week_plan"), dict) and \
            str(st_after["current_week_plan"].get("start_date") or "") == ws.isoformat():
        st_after["current_week_plan"] = after_plan
    after = compute_key_status(st_after, today, archived_weeks=archived_weeks, outdoor_rows=outdoor_rows,
                               week_start=ws, exercise_catalog=cat, with_proposals=False)

    # The inserted sessions: present after, absent before (by date + slot).
    def _idx(p: Mapping[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        return {(str(day.get("date")), str(s.get("slot"))): s
                for w in p.get("weeks") or [] for day in w.get("days") or [] for s in day.get("sessions") or []}
    bi, ai = _idx(before_plan), _idx(after_plan)
    inserted = [(k, s) for k, s in ai.items() if k not in bi or (bi[k].get("session_id") != s.get("session_id")
                                                                 and s.get("is_custom"))]
    reqs = phase_requirements(after.get("phase_id"))
    conflicts: List[Dict[str, Any]] = []
    lost = _is_key_lost(before, after)
    downgraded = [a for a in adjustments if a.get("action") == "downgraded"]
    for lk in lost:
        req = next((r for r in reqs if r["key"] == lk["key"]), None)
        replaces = False
        partial_same = False
        for (d, _slot), s in inserted:
            if req and session_delivers(req, s, cat):
                if session_dose(st_after, s, d, req)["dose"] == "full":
                    replaces = True
                else:
                    partial_same = True
        cause = [a for a in downgraded if req and session_delivers(req, {"session_id": a.get("previous_session_id")}, cat)]
        conflicts.append({
            "code": "key_removed", "severity": "high", "key": lk["key"], "label": lk.get("label"),
            "replace_key": replaces,
            "partial_replacement": partial_same and not replaces,
            "downgraded": cause,
            "message": (f"This session takes the place of your {lk.get('label') or lk['key']} key session"
                        + (f" ({cause[0]['previous_session_id']} on {cause[0]['date']} becomes recovery)" if cause else "")
                        + (": it delivers the same stimulus, so it can replace it." if replaces
                           else ": it trains the same stimulus, but below the dose of the phase." if partial_same
                           else ": the key stimulus of the week would be lost.")),
        })
    # A key session downgraded while its stimulus stays covered — by the
    # inserted session itself: the insertion REPLACES the key (decision
    # 2026-10-04: warning with confirm + replace_key when same stimulus).
    lost_keys = {lk["key"] for lk in lost}
    before_roles = {(e["date"], str(e.get("slot"))): e for e in before.get("sessions") or []}
    for a in downgraded:
        role = before_roles.get((str(a.get("date")), str(a.get("slot"))))
        if not role or role.get("role") != "key":
            continue
        for k in role.get("keys") or []:
            if k in lost_keys or k == "try_hard":
                continue
            req = next((r for r in reqs if r["key"] == k), None)
            if req is None or not any(session_delivers(req, s, cat) for _k, s in inserted):
                continue
            label = req.get("label") or k
            conflicts.append({
                "code": "key_replaced", "severity": "medium", "key": k, "label": label,
                "replace_key": True, "downgraded": [a],
                "message": (f"This session replaces your {label} key session "
                            f"({a.get('previous_session_id')} on {a.get('date')} becomes recovery): "
                            "it delivers the same stimulus."),
            })
    # A test the reconcile turned into recovery because of the insertion.
    for a in downgraded:
        if str(a.get("previous_session_id") or "").startswith("test_"):
            conflicts.append({
                "code": "test_downgraded", "severity": "high", "date": a.get("date"), "slot": a.get("slot"),
                "session_id": a.get("previous_session_id"), "downgraded": [a],
                "message": (f"The {a.get('previous_session_id')} planned on {a.get('date')} would be turned into "
                            "recovery by the spacing rules: move this session or the test."),
            })
    # Pending tests are read on the plan BEFORE the insertion (the reconcile
    # may already have removed the test the insertion collides with).
    days_before = _plan_days(st, archived_weeks)
    for (d, slot), s in inserted:
        dd = _as_date(d)
        if (session_flag(s, "hard") or is_finger_hard_session(s)) and not is_test_session(s):
            tests = _pending_tests(days_before, dd, PRE_TEST_BLOCK_H // 24)
            if tests:
                conflicts.append({"code": "pre_test_fatigue", "severity": "high", "date": d, "slot": slot,
                                  "tests": tests,
                                  "message": f"Hard work on {d} within 72 h of a max test ({tests[0]})."})
        if is_finger_hard_session(s):
            # A294 review: read on the plan AFTER the insertion (what the
            # reconcile downshifted is reported as key_removed instead), minus
            # the inserted session itself. Whatever is left is a finger-hard day
            # nobody can move — done, forced, custom, outdoor or an earlier
            # session — so it is a real clash and asks for a confirm (high).
            gap = _recovery_gap_days(after_plan)
            fh = _finger_hard_map(st_after, dd - timedelta(days=gap), dd + timedelta(days=gap),
                                  archived_weeks, outdoor_rows)
            clash = sorted({f"{x} {r.get('session_id') or r.get('reason')}" for x, rs in fh.items() for r in rs
                            if not (x == d and r.get("session_id") == s.get("session_id"))})
            if clash:
                conflicts.append({"code": "finger_gap", "severity": "high", "date": d, "slot": slot,
                                  "with": clash,
                                  "message": f"Finger-hard session on {d} within {gap} day(s) of another "
                                             f"finger-hard day ({clash[0]}): the fingers need that gap to "
                                             "recover."})
    # A301: what the insertion adds to the guard alerts of the week (finger
    # gap, 72 h before a finger test, heavy pulls, HIIT next to a max, hard
    # cap, pre-trip) — the insertion itself rewrites nothing any more.
    prev = _prev_days(st, ws, archived_weeks)
    td_iso = _as_date(today).isoformat()
    guard_warnings = _guards_mod.new_warnings(
        _guards_mod.evaluate(before_plan, prev, td_iso, st),
        _guards_mod.evaluate(after_plan, prev, td_iso, st_after),
    )
    return {"week_plan": after_plan, "adjustments": adjustments, "key_status": after,
            "key_conflicts": conflicts, "added_guard_warnings": guard_warnings}


# ---------------------------------------------------------------------------
# Text block (coach prompt, scripts)
# ---------------------------------------------------------------------------

_STATUS_TXT = {"done": "done", "planned": "planned", "partial": "partial dose", "missing": "MISSING",
               "not_due": "not due", "unplaceable": "unplaceable"}


def key_status_text(status: Optional[Mapping[str, Any]], *, max_lines: int = 12) -> str:
    """Compact English block for the coach prompt / CLI. Empty string when there
    is nothing to say (no phase requirements)."""
    if not status or not status.get("requirements"):
        return ""
    L = [f"Key sessions {status.get('week_start')} → {status.get('week_end')} ({status.get('phase_id')}):"]
    for r in status["requirements"]:
        line = f"- {r.get('label')}: {_STATUS_TXT.get(r.get('status'), r.get('status'))}"
        if r.get("done"):
            line += f" (done {', '.join(x['date'][5:] for x in r['done'])})"
        nxt = [p for p in r.get("planned") or [] if not p.get("unmarked")]
        if r.get("status") == "planned" and nxt:
            line += f" (next {nxt[0]['date'][5:]} {nxt[0].get('session_id')})"
        if r.get("resolution") == "proposal":
            p = next((p for p in status.get("proposals") or [] if r["key"] in p.get("keys", [])), None)
            if p:
                line += f" → proposed {p['date'][5:]} {p['slot']} {p['session_id']}"
        elif r.get("resolution") == "deferred_next" and r.get("next_key"):
            line += f" → next key {str(r['next_key'].get('date'))[5:]}, do not catch up this week"
        elif r.get("resolution") == "deferred_fatigue":
            line += " → no catch-up (recent very hard feedback)"
        elif r.get("resolution") == "let_go":
            line += " → let it go this week"
        if r.get("severity") == "critical":
            line += " [CRITICAL]"
        L.append(line)
    for c in (status.get("conflicts") or [])[:3]:
        L.append(f"! {c.get('code')}: {c.get('message')}")
    return "\n".join(L[: max_lines + 1])


def finger_key_guard(status: Optional[Mapping[str, Any]], target_date: DateLike,
                     plan: Optional[Mapping[str, Any]] = None,
                     state: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """For the coach composer (A259 extension, decision 2026-10-04): is
    ``target_date`` within the recovery gap of a finger KEY session (done or
    pending, the same day included), or within 72 h before a pending max test?
    Returns ``{near_finger_key: [refs],
    pre_test: [refs], keys_on_day: [keys]}`` — empty lists when free."""
    out: Dict[str, Any] = {"near_finger_key": [], "pre_test": [], "keys_on_day": []}
    if not status:
        return out
    td = _as_date(target_date)
    gap = _recovery_gap_days(plan)
    for e in status.get("sessions") or []:
        # A294 review: a DONE finger key protects the days after it exactly
        # like a pending one (the tendons do not care that it is ticked), and a
        # finger key on the target day itself is the closest clash of all.
        if e.get("role") != "key" or e.get("status") == "skipped":
            continue
        d = _as_date(e["date"])
        fingers = any(k in ("finger_max", "limit_power", "finger_maintenance", "project") for k in e.get("keys") or [])
        if d == td and e.get("status") != "done":
            out["keys_on_day"].extend(e.get("keys") or [])
        if fingers and abs((d - td).days) <= gap:
            out["near_finger_key"].append({"date": e["date"], "session_id": e.get("session_id"),
                                           "keys": e.get("keys"), "status": e.get("status")})
    if state is not None:
        days = _plan_days(state, None)
        out["pre_test"] = _pending_tests(days, td, PRE_TEST_BLOCK_H // 24)
    return out


def composer_guard(
    state: Mapping[str, Any],
    target_date: DateLike,
    *,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    archived_weeks: ArchivedWeeks = None,
) -> Dict[str, Any]:
    """A259 extension (decision 2026-10-04): what the coach composer must leave
    out of the pool for a session on ``target_date``.

    - within the recovery gap of a finger KEY session (done or pending, the
      same day included — max hangs at lunch before the limit key at night): every
      finger-hard exercise (finger_max, limit_power and the max-intensity hangs
      of ``FINGER_FATIGUE_EXTRA_IDS``) — so a "quick hang session" cannot cost
      the key session its quality;
    - within 72 h before a pending max test: finger-hard exercises before a hang
      test, heavy pulls (pulling_max) before a pull-up test.

    Returns ``{exclude_ids: [...], warnings: [{code, message, ...}]}``; empty
    when nothing applies. The composer still composes (deterministic fallback
    included) — the guard only narrows the pool and says why.
    """
    from backend.engine.stimulus import EXERCISE_FAMILY, FAMILY_PULLING_MAX, FINGER_FATIGUE_EXTRA_IDS

    out: Dict[str, Any] = {"exclude_ids": [], "warnings": []}
    try:
        status = compute_key_status(state, target_date, outdoor_rows=outdoor_rows,
                                    archived_weeks=archived_weeks, with_proposals=False)
    except Exception:  # pragma: no cover - the coach must still compose
        return out
    td = _as_date(target_date)
    plan = _week_plan(state, _monday(td), archived_weeks)
    g = finger_key_guard(status, td, plan, state)
    finger_ids = {eid for eid, fam in EXERCISE_FAMILY.items() if fam in (FAMILY_FINGER_MAX, FAMILY_LIMIT_POWER)}
    finger_ids |= set(FINGER_FATIGUE_EXTRA_IDS)
    pull_ids = {eid for eid, fam in EXERCISE_FAMILY.items() if fam == FAMILY_PULLING_MAX}
    ids: set = set()
    if g["near_finger_key"]:
        k = g["near_finger_key"][0]
        ids |= finger_ids
        out["warnings"].append({
            "code": "near_finger_key", "date": k["date"], "session_id": k.get("session_id"),
            "message": (f"Finger-hard exercises were left out: your key session "
                        f"{_session_name(k.get('session_id'))} on {k['date']} is within the recovery gap. "
                        + ("To train fingers that day instead, move or replace the key session from the week view."
                           if k.get("status") != "done" else "Your fingers need that gap to recover.")),
        })
    if g["pre_test"]:
        hang = [t for t in g["pre_test"] if "hang" in t or "lp_max" in t]
        pull = [t for t in g["pre_test"] if "pullup" in t]
        if hang:
            ids |= finger_ids
        if pull:
            ids |= pull_ids
        out["warnings"].append({
            "code": "pre_test", "tests": g["pre_test"],
            "message": f"Max test coming up ({g['pre_test'][0]}): hard finger/pulling work was left out "
                       "so the test measures strength, not fatigue.",
        })
    out["exclude_ids"] = sorted(ids)
    return out


__all__ = [
    "VERSION", "load_key_catalog", "phase_requirements", "session_keys", "session_delivers",
    "session_dose", "technique_hit", "tryhard_hit", "compute_key_status", "check_insertion",
    "key_status_text", "finger_key_guard", "composer_guard", "MIN_FULL_SETS", "PRE_TEST_BLOCK_H",
]
