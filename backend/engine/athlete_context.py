"""A293 (R7a) — the athlete context Claude Code reads before composing a session.

Why this exists: custom sessions composed "from memory" went wrong three
times in a week (a 2RM used as a working load, a bodyweight drill too easy for
the athlete, key sessions of the phase silently skipped). Everything a
session-composer needs to know is already computed by the engine — position in
the macrocycle (A288), official maxima and their confidence (A288/B364), the
anchored loads (B364), the retest policy (A289), the finger-hard days (A288) —
but scattered over a dozen modules. This module assembles it in ONE read-only
snapshot, and ``scripts/athlete_context.py`` prints it.

Contract:

- ``build_athlete_context(state, today, *, archived_weeks, outdoor_rows,
  catalog)`` → a JSON-serialisable dict with stable keys (``version``).
- Pure and deterministic: the input is never mutated, no ``date.today()``, no
  network/database I/O. Archived weeks (A221 ``week_archive``) and outdoor rows
  (``outdoor_logs``) are passed in by the caller. The only file read is the
  static exercise catalog, and only when ``catalog`` is not given.
- It reuses the engine's single definitions and NEVER reimplements a load
  formula: loads come only from ``anchored_load`` (B364), maxima only from
  ``retest_policy.official_max``, finger-hard days only from
  ``stimulus.finger_hard_days``, retest decisions only from
  ``retest_policy.retest_status``. When a contract does not exist yet the
  section says so and is labelled ``source: "fallback"``.
- ``render_text(ctx)`` renders it in Italian for the CLI (Claude Code reads the
  output). ``render_coach_block`` / ``render_composer_block`` (A297, R7b) render
  it in English for the in-app coach chat and ad-hoc composer — the single
  prompt integration point, wired by ``backend.coach.athlete_block`` behind
  ``COACH_ATHLETE_CONTEXT``. ``composer_guard_view`` / ``drop_heavy_pulls``
  turn the day's guards into deterministic pool exclusions.

Key sessions: A294 owns their definition (derived at read, never persisted).
``key_sessions`` / ``key_sessions_next_week`` are
``key_sessions_v1.compute_key_status`` for the current and the next week (the
A293 fallback is gone). A failure is reported as ``source: "error"`` and the
warning ``KEY_SESSIONS_ERROR`` — never an empty section.

Read-only by construction: nothing here writes tests, baselines, working loads
or week plans. Past sessions are only read.
"""

from __future__ import annotations

import copy
import json
import os
import re
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from backend.engine import bw_ladders as _bw
from backend.engine import retest_policy as rp
from backend.engine import limit_log as _limit_log
from backend.engine.anchored_load import (
    ANCHORED_EXERCISES,
    AXIS_FINGER,
    AXIS_PULLING,
    HEAVY_PULL_WEEKLY_MAX,
    WORKING_ENTRY_MAX_AGE_D,
    anchored_load,
    fatigue_for,
    pain_for,
)
from backend.engine.macro_position import position_on
from backend.engine.stimulus import (
    FAMILY_LIMIT_POWER,
    counted_entries,
    finger_hard_days,
    is_finger_hard_session,
    is_test_session,
    iter_plan_sessions,
    outdoor_hard_days,
    session_flag,
    session_stimuli,
)

DateLike = Union[date, str]
ArchivedWeeks = Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]]

VERSION = "c272.1"

# ---------------------------------------------------------------------------
# Constants. Shared with the engine, never copied: the command and the docs
# read them from here.
# ---------------------------------------------------------------------------

#: 48 h between finger-hard days (planner ``_enforce_no_consecutive_finger``).
FINGER_GAP_H = rp.FINGER_GAP_H
#: A hang test is blocked 72 h after a finger-hard day (retest only).
RETEST_BLOCK_H = rp.RETEST_BLOCK_H
#: A pull-up test is blocked 48 h after a heavy pulling session.
PULL_TEST_BLOCK_H = rp.PULL_TEST_BLOCK_H
#: Max heavy (≥ 85 % 1RM) pulling sessions per 7 days (decision 2026-10-04).
HEAVY_PULL_MAX_PER_7D = HEAVY_PULL_WEEKLY_MAX
#: ENGINEERING CONSTANT: an accessory group used this many times in the variety
#: window is "overused" (rotate it out).
OVERUSED_MIN = 3
#: Variety window: the resolver's recency look-back (3 Monday-indexed weeks).
VARIETY_WEEKS = 3
#: Look-ahead of the upcoming / guards sections.
UPCOMING_DAYS = 14
GUARD_DAYS = 8
#: Try-hard outcome window (TECH logging decision: 4 weeks).
TRYHARD_WINDOW_D = 28
#: PE phase: max gap between two limit sessions (decision 2026-10-04).
PE_LIMIT_MAX_GAP_D = 12
#: Coach notes are truncated to this length in the context.
COACH_NOTES_MAX = 500

#: Where the general improvement plan lives (A293). The CLI extracts the block
#: between these markers and prints it (ladder levels, pocket notes, ...).
ATHLETE_PLAN_PATH = "docs/training/athlete_plan.md"
NOTES_BEGIN = "<!-- athlete-context:notes -->"
NOTES_END = "<!-- /athlete-context:notes -->"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_EXERCISES_PATH = os.path.join(_REPO_ROOT, "backend", "catalog", "exercises", "v1", "exercises.json")

# ---------------------------------------------------------------------------
# Key sessions — owned by A294 (``key_sessions_v1``). The names below are kept
# as thin aliases for the CLI and the custom-session command.
# ---------------------------------------------------------------------------

from backend.engine import key_sessions_v1 as ks1  # noqa: E402

TECHNIQUE_MIN_DRILLS = ks1.TECHNIQUE_MIN_DRILLS
WARMUP_TECHNIQUE_DRILLS = ks1.WARMUP_TECHNIQUE_DRILLS
#: Exercises that make a session a try-hard practice.
TRYHARD_EXERCISE_IDS = ("fall_practice", "fall_ladder", "three_attempt_comp", "no_take_lead_onsight", "commit_map")
#: Custom sessions whose name starts with this are Daniele's recurring "Work"
#: lunch sessions: re-checked against the day guards and at each phase change.
_WORK_RE = re.compile(r"^\s*Work\b", re.IGNORECASE)

_HIIT_RE = re.compile(r"\b(HIIT|VO2)", re.IGNORECASE)
_TRYHARD_TOKEN_RE = re.compile(r"\b(SEND|FALL|TAKE|LET_GO)\b")


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


@lru_cache(maxsize=1)
def _load_catalog_file() -> Dict[str, Dict[str, Any]]:
    with open(_EXERCISES_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    items = data.get("exercises") if isinstance(data, dict) else data
    return {e["id"]: e for e in items or [] if isinstance(e, dict) and e.get("id")}


def load_exercise_catalog() -> Dict[str, Dict[str, Any]]:
    """The static exercise catalog by id (cached; a copy is returned)."""
    return dict(_load_catalog_file())


def _bodyweight(state: Mapping[str, Any]) -> Optional[float]:
    return _num(state.get("bodyweight_kg")) or _num((state.get("body") or {}).get("weight_kg"))


def _session_ref(d: str, s: Mapping[str, Any]) -> Dict[str, Any]:
    return {"date": d, "slot": s.get("slot"), "session_id": s.get("session_id"),
            "name": s.get("name"), "status": s.get("status") or "planned"}


def _outdoor_entries(
    state: Mapping[str, Any], outdoor_rows: Optional[Sequence[Mapping[str, Any]]]
) -> List[Mapping[str, Any]]:
    """Outdoor log entries (``outdoor_logs`` rows, raw or ``{"entry": ...}``)."""
    out: List[Mapping[str, Any]] = []
    for row in outdoor_rows or []:
        if not isinstance(row, Mapping):
            continue
        entry = row.get("entry") if isinstance(row.get("entry"), Mapping) else row
        if entry.get("date"):
            out.append(entry)
    return sorted(out, key=lambda e: str(e.get("date")))


def _plan_days(state: Mapping[str, Any], archived_weeks: ArchivedWeeks) -> Dict[str, List[Dict[str, Any]]]:
    """``{date: [session, ...]}`` over hot + archived week plans."""
    days: Dict[str, List[Dict[str, Any]]] = {}
    for d, s, _src in iter_plan_sessions(state, archived_weeks):
        days.setdefault(d, []).append(s)
    return days


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _position(state: Mapping[str, Any], today: date) -> Dict[str, Any]:
    mc = state.get("macrocycle")
    pos = position_on(mc, today)
    goal = state.get("goal") or {}
    out: Dict[str, Any] = {
        "available": pos is not None,
        "goal": {k: goal.get(k) for k in ("goal_type", "discipline", "target_grade", "target_style",
                                          "current_grade", "deadline") if goal.get(k) is not None},
    }
    if pos is None:
        return out
    out.update(pos)
    out["week_in_phase_1based"] = pos["week_in_phase"] + 1
    phases = (mc or {}).get("phases") or []
    phase = phases[pos["phase_index"]] if pos["phase_index"] < len(phases) else {}
    out["phase_notes"] = phase.get("notes")
    out["intensity_cap"] = phase.get("intensity_cap")
    return out


def _maxima(state: Mapping[str, Any], today: date, archived_weeks: ArchivedWeeks) -> Dict[str, Any]:
    """Official maxima per PROTOCOL (never per axis), with computed confidence."""
    out: Dict[str, Any] = {}
    for protocol in (rp.PROTOCOL_HANG_7S, rp.PROTOCOL_HANG_5S, rp.PROTOCOL_PULLUP_2RM):
        om = rp.official_max(state, protocol, today)
        if om is None:
            out[protocol] = None
            continue
        conf = rp.axis_confidence(state, om, archived_weeks=archived_weeks)
        trend = rp.axis_trend(state, om)
        row = {
            "total_kg": om.get("total_kg"),
            "one_rm_kg": om.get("one_rm_kg"),
            "date": om.get("date"),
            "age_days": om.get("age_days"),
            "tested": bool(om.get("tested")),
            "fresh": bool(om.get("fresh")),
            "source": om.get("source"),
            "converted": bool(om.get("converted")),
            "source_seconds": om.get("source_seconds"),
            "bodyweight_kg": om.get("bodyweight_kg"),
            "edge_mm": om.get("edge_mm"),
            "grip": om.get("grip"),
            "confidence": conf.get("confidence"),
            "confidence_exposures": conf.get("exposures"),
            "confidence_basis": conf.get("basis"),
            "stored_confidence": om.get("stored_confidence"),
            "trend": trend.get("trend"),
            "delta_pct": trend.get("delta_pct"),
        }
        out[protocol] = row
    return out


def _anchors(state: Mapping[str, Any], today: date) -> Dict[str, Any]:
    """Anchored loads on ``today`` (custom-session intensity), from B364 only."""
    rows: Dict[str, Any] = {}
    for ex in ANCHORED_EXERCISES:
        anch = anchored_load(state, ex, date=today)
        if anch is None:
            rows[ex] = None
            continue
        rows[ex] = {
            "total": anch["total"],
            "external": anch["external"],
            "sets": anch["sets"],
            "reps": anch.get("reps"),
            "work_seconds": anch.get("work_seconds"),
            "rep_scheme": anch["rep_scheme"],
            "pct_of_official": anch.get("pct_of_official"),
            "official_total": (anch.get("official") or {}).get("total"),
            "official_one_rm": (anch.get("official") or {}).get("one_rm"),
            "official_date": (anch.get("official") or {}).get("date"),
            "cap": anch.get("cap"),
            "floor": anch.get("floor"),
            "clamped": anch.get("clamped"),
            "source": anch.get("source"),
            "phase_id": anch.get("phase_id"),
            "intensity": anch.get("intensity"),
            "ramp": anch.get("ramp"),
            "guards": [g.get("guard") for g in anch.get("guards") or []],
            "pain": bool(anch.get("pain")),
            "fatigue": bool(anch.get("fatigue")),
            "ceiling_note": anch.get("ceiling_note"),
        }
    return {
        "bodyweight_kg": _bodyweight(state),
        "available": any(v is not None for v in rows.values()),
        "exercises": rows,
    }


def _retest(state: Mapping[str, Any], today: date, archived_weeks: ArchivedWeeks,
            outdoor_rows: Optional[Sequence[Mapping[str, Any]]]) -> Dict[str, Any]:
    device = (state.get("preferences") or {}).get("finger_training_device")
    try:
        status = rp.retest_status(state, today, finger_device=device,
                                  archived_weeks=archived_weeks, outdoor_rows=outdoor_rows)
    except Exception as exc:  # pragma: no cover - defensive: the context must render
        return {"available": False, "error": str(exc)}
    status = dict(status)
    status["available"] = bool(status.get("axes"))
    return status


def _technique_hit(session: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]]) -> bool:
    """The technique key (A294 definition)."""
    return ks1.technique_hit(session, catalog)


def key_requirements_for(phase_id: Optional[str]) -> List[Dict[str, Any]]:
    """The key requirements of a phase (A294 catalog ``key_stimuli/v1``)."""
    return ks1.phase_requirements(phase_id)


def key_matches(session: Mapping[str, Any], phase_id: Optional[str],
                catalog: Optional[Mapping[str, Mapping[str, Any]]] = None) -> List[str]:
    """Keys of the phase a (planned) session delivers — used by the CLI to flag
    a key session that a simulated insertion would downgrade or replace."""
    cat = catalog if catalog is not None else load_exercise_catalog()
    return ks1.session_keys(session, phase_id, cat)


def _key_sessions(
    state: Mapping[str, Any], today: date, archived_weeks: ArchivedWeeks,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]],
    catalog: Mapping[str, Mapping[str, Any]], *, week_of: Optional[date] = None,
    with_proposals: bool = True,
) -> Dict[str, Any]:
    """A294's ``compute_key_status`` for the week of ``week_of`` (default: the
    current week). A failure is reported (``source: "error"``), never hidden
    behind an empty section."""
    try:
        return ks1.compute_key_status(state, today, archived_weeks=archived_weeks, outdoor_rows=outdoor_rows,
                                      week_start=week_of, exercise_catalog=catalog,
                                      with_proposals=with_proposals)
    except Exception as exc:  # pragma: no cover - defensive: the context must render
        ws = _monday(week_of or today)
        return {"source": "error", "error": f"{type(exc).__name__}: {exc}", "week_start": ws.isoformat(),
                "week_end": (ws + timedelta(days=6)).isoformat(), "requirements": [], "sessions": [],
                "proposals": [], "conflicts": [], "summary": {}, "unknown_skips": [], "removed_unknown": 0}


def _session_view(d: str, s: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        **_session_ref(d, s),
        "hard": session_flag(s, "hard"),
        "finger": session_flag(s, "finger"),
        "pulling": session_flag(s, "pulling"),
        "finger_hard": is_finger_hard_session(s),
        "intensity": s.get("intensity"),
        "is_custom": bool(s.get("is_custom")),
        "is_test": is_test_session(s),
        "stimuli": session_stimuli(s),
        "hiit": bool(_HIIT_RE.search(str(s.get("name") or ""))),
    }


def _upcoming(state: Mapping[str, Any], today: date, archived_weeks: ArchivedWeeks) -> List[Dict[str, Any]]:
    days = _plan_days(state, archived_weeks)
    out: List[Dict[str, Any]] = []
    for k in range(UPCOMING_DAYS + 1):
        d = (today + timedelta(days=k)).isoformat()
        for s in days.get(d, []):
            out.append(_session_view(d, s))
    return out


def _recent(state: Mapping[str, Any], today: date, archived_weeks: ArchivedWeeks,
            outdoor_rows: Optional[Sequence[Mapping[str, Any]]]) -> Dict[str, Any]:
    days = _plan_days(state, archived_weeks)
    sessions: List[Dict[str, Any]] = []
    for k in range(7, 0, -1):
        d = (today - timedelta(days=k)).isoformat()
        for s in days.get(d, []):
            if s.get("status") in ("done", "skipped"):
                sessions.append(_session_view(d, s))
    since = today - timedelta(days=14)
    outdoor: List[Dict[str, Any]] = []
    hard = {o["date"]: o for o in outdoor_hard_days(state, since=since, until=today, outdoor_rows=outdoor_rows)}
    for e in _outdoor_entries(state, outdoor_rows):
        d = str(e["date"])[:10]
        if not (since.isoformat() <= d <= today.isoformat()):
            continue
        routes = [r for r in e.get("routes") or [] if isinstance(r, Mapping)]
        outdoor.append({
            "date": d, "spot": e.get("spot_name"), "discipline": e.get("discipline"),
            "routes": len(routes),
            "sent": sum(1 for r in routes if any((a or {}).get("result") == "sent" for a in r.get("attempts") or [])),
            "hard_day": d in hard,
            "hardest_hard_route": (hard.get(d) or {}).get("route"),
            "hardest_hard_grade": (hard.get(d) or {}).get("grade"),
        })
    return {"sessions": sessions, "outdoor": outdoor}


def _hard_cap_of_week(state: Mapping[str, Any], week_start: date) -> Optional[int]:
    """The hard-day cap of a week: the plan snapshot's ``hard_cap_per_week``
    (0 is a legitimate deload cap, so ``is None`` — never truthiness — decides
    the fallback, as the replanner's ``_safe_hard_cap`` does), else the user's
    ``planning_prefs.hard_day_cap_per_week``."""
    plan = (state.get("week_plans") or {}).get(week_start.isoformat()) or {}
    raw = (plan.get("profile_snapshot") or {}).get("hard_cap_per_week")
    if _num(raw) is None:
        raw = (state.get("planning_prefs") or {}).get("hard_day_cap_per_week")
    return int(_num(raw)) if _num(raw) is not None else None


def _finger_spacing_gap(state: Mapping[str, Any], d: date) -> int:
    """Days of finger spacing the replanner enforces around ``d``: its own
    ``_recovery_gap`` (``ceil(recovery_multiplier)`` of the week's snapshot)."""
    from backend.engine.replanner_v1 import _recovery_gap

    plan = (state.get("week_plans") or {}).get(_monday(d).isoformat()) or {}
    return max(1, int(_recovery_gap(plan)))


def _guards(
    state: Mapping[str, Any], today: date, archived_weeks: ArchivedWeeks,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]],
) -> Dict[str, Any]:
    """Per-day guards for the next ``GUARD_DAYS`` days, from session PROPERTIES
    (tags, stimuli, tests, outdoor-hard rule) — never from a load score.

    Finger: 48 h from finger-hard days, the 72 h hang-test block, AND the
    replanner's own spacing (``_enforce_no_consecutive_finger``): any session
    tagged ``finger`` within ``ceil(recovery_multiplier)`` days — a max-hang
    custom next to a finger_maintenance would downgrade it. Heavy pulling: every
    rolling 7-day window that contains the day, past AND planned days. Both also
    respect the week's hard cap (0 in deload) and the deload phase."""
    lo = today - timedelta(days=8)
    hi = today + timedelta(days=GUARD_DAYS + 7)
    fh_rows = finger_hard_days(state, since=lo, until=hi, archived_weeks=archived_weeks,
                               outdoor_rows=outdoor_rows, include_planned=True)
    fh: Dict[str, List[str]] = {}
    for r in fh_rows:
        fh.setdefault(r["date"], []).append(str(r.get("session_id") or r["reason"]))
    days = _plan_days(state, archived_weeks)

    def sessions_on(d: date) -> List[Dict[str, Any]]:
        return [s for s in days.get(d.isoformat(), []) if s.get("status") != "skipped"]

    heavy: Dict[str, List[str]] = {}
    finger_tagged: Dict[str, List[str]] = {}
    for k in range(-7, GUARD_DAYS + 7):
        d = today + timedelta(days=k)
        for s in sessions_on(d):
            if rp.is_heavy_pulling_session(state, s, d):
                heavy.setdefault(d.isoformat(), []).append(str(s.get("session_id")))
            if session_flag(s, "finger"):
                finger_tagged.setdefault(d.isoformat(), []).append(str(s.get("session_id")))

    def max_day(d: date) -> bool:
        return any(is_finger_hard_session(s) or (session_flag(s, "pulling") and session_flag(s, "hard"))
                   for s in sessions_on(d))

    def pre_limit(d: date) -> List[str]:
        out = []
        for s in sessions_on(d + timedelta(days=1)):
            if FAMILY_LIMIT_POWER in session_stimuli(s) or str(s.get("session_id")) == "strength_long":
                out.append(str(s.get("session_id")))
        return out

    def tests_within(d: date, n_days: int, prefix: str) -> List[str]:
        out = []
        for k in range(1, n_days + 1):
            for s in sessions_on(d + timedelta(days=k)):
                if str(s.get("session_id") or "").startswith(prefix):
                    out.append(f"{(d + timedelta(days=k)).isoformat()} {s.get('session_id')}")
        return out

    def hard_days_of_week(ws_: date) -> List[str]:
        return sorted({(ws_ + timedelta(days=j)).isoformat() for j in range(7)
                       if any(session_flag(s, "hard") for s in sessions_on(ws_ + timedelta(days=j)))})

    def heavy_window(d: date) -> List[str]:
        """The fullest rolling 7-day window containing ``d`` (``d`` excluded)
        that already holds the weekly maximum of heavy pulling days."""
        worst: List[str] = []
        for off in range(-6, 1):
            w0 = d + timedelta(days=off)
            inwin = sorted(x for x in heavy if w0.isoformat() <= x <= (w0 + timedelta(days=6)).isoformat()
                           and x != d.isoformat())
            if len(inwin) >= HEAVY_PULL_MAX_PER_7D and len(inwin) > len(worst):
                worst = inwin
        return worst

    mc = state.get("macrocycle")
    rows: List[Dict[str, Any]] = []
    for k in range(GUARD_DAYS):
        d = today + timedelta(days=k)
        d_iso = d.isoformat()
        prev_d, next_d = (d - timedelta(days=1)).isoformat(), (d + timedelta(days=1)).isoformat()
        reasons_finger: List[str] = []
        # A297: every reason also carries a language-neutral code + detail, so
        # the English coach/composer renderers never parse the Italian text.
        codes_finger: List[Dict[str, str]] = []
        if prev_d in fh:
            reasons_finger.append(f"dita hard il {prev_d} ({', '.join(fh[prev_d])})")
            codes_finger.append({"code": "finger_hard_adjacent", "detail": f"{prev_d} {', '.join(fh[prev_d])}"})
        if next_d in fh:
            reasons_finger.append(f"dita hard il {next_d} ({', '.join(fh[next_d])})")
            codes_finger.append({"code": "finger_hard_adjacent", "detail": f"{next_d} {', '.join(fh[next_d])}"})
        gap = _finger_spacing_gap(state, d)
        for j in range(1, gap + 1):
            before, after = (d - timedelta(days=j)).isoformat(), (d + timedelta(days=j)).isoformat()
            if before in finger_tagged and not (j == 1 and before in fh):
                reasons_finger.append(
                    f"sessione con tag dita il {before} ({', '.join(finger_tagged[before])}): giorni dita "
                    f"entro lo spacing del replanner ({gap} gg)")
                codes_finger.append({"code": "finger_spacing",
                                     "detail": f"{before} {', '.join(finger_tagged[before])} ({gap} d)"})
            if after in finger_tagged and not (j == 1 and after in fh):
                reasons_finger.append(
                    f"sessione con tag dita il {after} ({', '.join(finger_tagged[after])}): spacing del "
                    f"replanner {gap} gg, la declasserebbe a regeneration_easy")
                codes_finger.append({"code": "finger_spacing",
                                     "detail": f"{after} {', '.join(finger_tagged[after])} ({gap} d)"})
        hang_tests = tests_within(d, RETEST_BLOCK_H // 24, "test_max_hang")
        if hang_tests:
            reasons_finger.append(f"test dita entro {RETEST_BLOCK_H} h: {', '.join(hang_tests)}")
            codes_finger.append({"code": "hang_test_soon", "detail": ", ".join(hang_tests)})
        heavy_7d = heavy_window(d)
        reasons_pull: List[str] = []
        codes_pull: List[Dict[str, str]] = []
        if heavy_7d:
            reasons_pull.append(f"già {len(heavy_7d)} sedute di tirata pesante in una finestra di 7 gg "
                                f"che contiene questo giorno ({', '.join(heavy_7d)})")
            codes_pull.append({"code": "heavy_pull_week", "detail": ", ".join(heavy_7d)})
        pl = pre_limit(d)
        if pl:
            reasons_pull.append(f"il giorno dopo c'è {', '.join(pl)}: niente trazione ≥85% né front lever")
            codes_pull.append({"code": "pre_limit", "detail": f"{next_d} {', '.join(pl)}"})
        pull_tests = tests_within(d, PULL_TEST_BLOCK_H // 24, "test_max_weighted_pullup")
        if pull_tests:
            reasons_pull.append(f"test trazione entro {PULL_TEST_BLOCK_H} h: {', '.join(pull_tests)}")
            codes_pull.append({"code": "pull_test_soon", "detail": ", ".join(pull_tests)})
        # Both a max-finger and a heavy-pull insertion make the day hard.
        common: List[str] = []
        codes_common: List[Dict[str, str]] = []
        pos_d = position_on(mc, d) or {}
        if pos_d.get("phase_id") == "deload":
            common.append("fase deload: niente massimali")
            codes_common.append({"code": "deload", "detail": ""})
        wk = _monday(d)
        cap_d = _hard_cap_of_week(state, wk)
        hd = hard_days_of_week(wk)
        if cap_d is not None and d_iso not in hd and len(hd) >= cap_d:
            common.append(f"cap giorni hard della settimana raggiunto ({len(hd)}/{cap_d})")
            codes_common.append({"code": "hard_cap", "detail": f"{len(hd)}/{cap_d}"})
        reasons_finger.extend(common)
        reasons_pull.extend(common)
        codes_finger.extend(codes_common)
        codes_pull.extend(codes_common)
        reasons_hiit: List[str] = []
        codes_hiit: List[Dict[str, str]] = []
        if max_day(d) or max_day(d + timedelta(days=1)):
            reasons_hiit.append("sessione max lo stesso giorno o il giorno dopo")
            codes_hiit.append({"code": "max_session_adjacent", "detail": ""})
        rows.append({
            "date": d_iso,
            "weekday": d.strftime("%a").lower(),
            "finger_hard_today": d_iso in fh,
            "finger_hard_today_sessions": fh.get(d_iso, []),
            "finger_max_ok": not reasons_finger,
            "finger_reasons": reasons_finger,
            "finger_codes": codes_finger,
            "finger_spacing_gap_d": gap,
            "heavy_pull_ok": not reasons_pull,
            # Front lever counts as heavy pulling (decision 2026-10-04): same
            # 2-per-7-days window, same 24 h before limit, same caps.
            "front_lever_ok": not reasons_pull,
            "pull_reasons": reasons_pull,
            "pull_codes": codes_pull,
            "hiit_ok": not reasons_hiit,
            "hiit_reasons": reasons_hiit,
            "hiit_codes": codes_hiit,
        })

    # Weekly hard cap: hard days of the current week vs the plan snapshot cap.
    ws = _monday(today)
    cap = _hard_cap_of_week(state, ws)
    hard_days = hard_days_of_week(ws)
    return {
        "finger_gap_h": FINGER_GAP_H,
        "retest_block_h": RETEST_BLOCK_H,
        "heavy_pull_max_per_7d": HEAVY_PULL_MAX_PER_7D,
        "days": rows,
        "heavy_pull_days": {d: v for d, v in sorted(heavy.items())},
        "hard_cap": {"week_start": ws.isoformat(), "cap": cap, "hard_days": hard_days,
                     "count": len(hard_days), "at_cap": cap is not None and len(hard_days) >= cap},
    }


def _work_checks(state: Mapping[str, Any], today: date, position: Mapping[str, Any],
                 guards: Mapping[str, Any], archived_weeks: ArchivedWeeks) -> List[Dict[str, Any]]:
    """Daniele's recurring "Work —" sessions (DECISIONS R7): a planned HIIT on a
    NO-HIIT guard day, and — when the phase changes within ``UPCOMING_DAYS`` —
    the "Work" sessions already planned in the next phase, to be reviewed."""
    out: List[Dict[str, Any]] = []
    days = _plan_days(state, archived_weeks)
    no_hiit = {g["date"]: g for g in guards.get("days") or [] if not g.get("hiit_ok")}
    for d_iso in sorted(no_hiit):
        for s in days.get(d_iso, []):
            if s.get("status") in ("done", "skipped") or not _HIIT_RE.search(str(s.get("name") or "")):
                continue
            out.append({"code": "HIIT_ON_GUARD_DAY", "date": d_iso, "session_id": s.get("session_id"),
                        "message": f"«{s.get('name')}» pianificata il {d_iso} ({s.get('slot')}) in un giorno NO HIIT "
                                   f"({'; '.join(no_hiit[d_iso].get('hiit_reasons') or [])}): spostala o rendila Z2"})
    change = _parse(position.get("phase_end")) if position.get("available") else None
    if change is not None and today < change <= today + timedelta(days=UPCOMING_DAYS):
        work: Dict[str, List[str]] = {}
        for d_iso, sessions in days.items():
            if d_iso < change.isoformat():
                continue
            for s in sessions:
                if s.get("status") in ("done", "skipped") or not _WORK_RE.search(str(s.get("name") or "")):
                    continue
                work.setdefault(str(s.get("name")), []).append(d_iso)
        if work:
            names = "; ".join(f"«{n}» dal {min(v)} ({len(v)}×)" for n, v in sorted(work.items()))
            out.append({"code": "WORK_RECURRENCE_PHASE_CHANGE", "date": change.isoformat(),
                        "message": f"cambio fase il {change.isoformat()} → {position.get('next_phase_id') or 'fine ciclo'}: "
                                   f"rivedi le ricorrenze Work già pianificate ({names}) contro la nuova fase e le guardie"})
    return out


def _variety(state: Mapping[str, Any], today: date, archived_weeks: ArchivedWeeks,
             catalog: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """Recency groups used by DONE sessions in the resolver's window (3 weeks
    indexed on Monday). Custom sessions read ``actual_exercises`` when present,
    else ``exercises`` — never the union. Tests excluded."""
    start = _monday(today) - timedelta(days=7 * (VARIETY_WEEKS - 1))
    groups: Dict[str, Dict[str, Any]] = {}
    exercises: Dict[str, int] = {}
    last_date: Dict[str, str] = {}
    for d, s, _src in iter_plan_sessions(state, archived_weeks):
        dd = _as_date(d)
        if not (start <= dd <= today) or s.get("status") != "done" or is_test_session(s):
            continue
        entries, _origin = counted_entries(s)
        seen_here = set()
        for e in entries:
            ex = str(e.get("exercise_id") or "")
            if not ex or ex in seen_here:
                continue
            seen_here.add(ex)
            meta = catalog.get(ex) or {}
            grp = meta.get("recency_group") or ex
            g = groups.setdefault(grp, {"group": grp, "count": 0, "last_date": None,
                                        "exercises": set(), "intensity_level": meta.get("intensity_level"),
                                        "category": meta.get("category")})
            g["count"] += 1
            g["last_date"] = max(filter(None, [g["last_date"], d]))
            g["exercises"].add(ex)
            exercises[ex] = exercises.get(ex, 0) + 1
            last_date[ex] = max(last_date.get(ex, ""), d)
    rows = []
    for g in groups.values():
        g = dict(g)
        g["exercises"] = sorted(g["exercises"])
        g["overused"] = g["count"] >= OVERUSED_MIN
        rows.append(g)
    rows.sort(key=lambda r: (-r["count"], r["group"]))
    return {
        "window_start": start.isoformat(),
        "window_end": today.isoformat(),
        "groups": rows,
        "overused": [r["group"] for r in rows if r["overused"]
                     and r.get("category") not in ("warmup_general", "warmup_specific", "flexibility", "mobility")],
        "exercise_counts": dict(sorted(exercises.items(), key=lambda kv: (-kv[1], kv[0]))),
        # A297: per-exercise last DONE date in the window — the recency the
        # ad-hoc builder ranks on (never the resolver's custom-blind list).
        "exercise_last_date": dict(sorted(last_date.items())),
    }


def _working_loads(state: Mapping[str, Any], today: date) -> List[Dict[str, Any]]:
    """Working-load memory of the anchored exercises — informative, never a
    load source (loads come from ``anchors``). Flags: STALE, TEST_COPY."""
    test_ext: Dict[str, List[float]] = {}
    for t in (state.get("tests") or {}).get("pulling_strength") or []:
        if isinstance(t, Mapping) and _num(t.get("external_load_2rm_kg")) is not None:
            test_ext.setdefault(str(t.get("exercise_id") or "weighted_pullup"), []).append(float(t["external_load_2rm_kg"]))
    for t in (state.get("tests") or {}).get("max_strength") or []:
        if isinstance(t, Mapping) and _num(t.get("external_load_kg")) is not None:
            test_ext.setdefault(str(t.get("exercise_id") or ""), []).append(float(t["external_load_kg"]))
    out: List[Dict[str, Any]] = []
    for e in ((state.get("working_loads") or {}).get("entries") or []):
        if not isinstance(e, Mapping) or e.get("exercise_id") not in ANCHORED_EXERCISES:
            continue
        flags: List[str] = []
        upd = _parse(e.get("updated_at"))
        if upd is None or (today - upd).days > WORKING_ENTRY_MAX_AGE_D:
            flags.append("STALE")
        last_ext = _num(e.get("last_external_load_kg"))
        if last_ext is not None and any(abs(last_ext - x) <= 0.5 for x in test_ext.get(str(e["exercise_id"]), [])):
            flags.append("TEST_COPY")
        out.append({
            "exercise_id": e.get("exercise_id"),
            "updated_at": e.get("updated_at"),
            "last_external_load_kg": last_ext,
            "last_reps": e.get("last_reps"),
            "last_work_seconds": e.get("last_work_seconds"),
            "next_external_load_kg": _num(e.get("next_external_load_kg")),
            "last_feedback_label": e.get("last_feedback_label"),
            "flags": flags,
        })
    return sorted(out, key=lambda r: str(r["exercise_id"]))


def _tryhard(state: Mapping[str, Any], today: date,
             outdoor_rows: Optional[Sequence[Mapping[str, Any]]]) -> Dict[str, Any]:
    """Try-hard outcomes over 4 weeks, read from the outdoor notes written in
    the agreed format (``T1 M7 FALL +1``). A296 will replace this with the
    structured limit log; until then a missing note is "not logged", never a
    missing key session."""
    since = (today - timedelta(days=TRYHARD_WINDOW_D)).isoformat()
    counts = {"SEND": 0, "FALL": 0, "TAKE": 0, "LET_GO": 0}
    for e in _outdoor_entries(state, outdoor_rows):
        d = str(e["date"])[:10]
        if not (since <= d <= today.isoformat()):
            continue
        texts = [str(e.get("notes") or "")]
        for r in e.get("routes") or []:
            if not isinstance(r, Mapping):
                continue
            texts.append(str(r.get("notes") or ""))
            for a in r.get("attempts") or []:
                if isinstance(a, Mapping):
                    texts.append(str(a.get("notes") or ""))
        for t in texts:
            for tok in _TRYHARD_TOKEN_RE.findall(t):
                counts[tok] += 1
    non_send = counts["FALL"] + counts["TAKE"] + counts["LET_GO"]
    return {
        "source": "outdoor_notes",
        "window_start": since,
        "counts": counts,
        "logged_attempts": sum(counts.values()),
        "fall_pct_of_non_send": round(100.0 * counts["FALL"] / non_send, 1) if non_send else None,
    }


def _load_flags(state: Mapping[str, Any], today: date) -> Dict[str, Any]:
    """A295 pain blocks and the B364 fatigue rule, per axis, on ``today`` —
    read with the same helpers ``anchored_load`` applies, never recomputed."""
    out: Dict[str, Any] = {"pain": {}, "fatigue": {}}
    for axis in (AXIS_FINGER, AXIS_PULLING):
        p = pain_for(state, axis, today)
        if p is not None:
            out["pain"][axis] = p
        f = fatigue_for(state, axis, today)
        if f is not None:
            out["fatigue"][axis] = f
    return out


#: Limit-log entries carried in the context (A296).
LIMIT_LOG_RECENT = 4


def _limit_log_view(state: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """The newest A296 limit-log entries, summarised (problems counted, never
    copied whole)."""
    out: List[Dict[str, Any]] = []
    for e in _limit_log.recent(state, LIMIT_LOG_RECENT):
        problems = [p for p in e.get("problems") or [] if isinstance(p, Mapping)]
        out.append({
            "date": e.get("date"),
            "source": e.get("source"),
            "surface": e.get("surface"),
            "exercise_id": e.get("exercise_id"),
            "target_grade": e.get("target_grade"),
            "problems": len(problems),
            "sent": sum(1 for p in problems if p.get("outcome") == _limit_log.OUTCOME_SENT),
            "best_sent": _limit_log.best_sent(problems) if problems else None,
            "step": e.get("step"),
            "step_reason": e.get("step_reason"),
            "next_target_grade": e.get("next_target_grade"),
            "qualifies": e.get("qualifies"),
            "warning": e.get("warning"),
        })
    return out


def _limits(state: Mapping[str, Any]) -> Dict[str, Any]:
    lim = state.get("limitations") or {}
    notes = str((state.get("preferences") or {}).get("coach_notes") or "")
    return {
        "active_flags": list(lim.get("active_flags") or []),
        "details": list(lim.get("details") or []),
        "coach_notes": notes[:COACH_NOTES_MAX] if notes else None,
        "finger_training_device": (state.get("preferences") or {}).get("finger_training_device"),
    }


def _trips(state: Mapping[str, Any], today: date) -> List[Dict[str, Any]]:
    out = []
    for t in state.get("trips") or []:
        if not isinstance(t, Mapping):
            continue
        end = _parse(t.get("end_date")) or _parse(t.get("start_date"))
        start = _parse(t.get("start_date"))
        if start is None or end is None or end < today:
            continue
        out.append({"name": t.get("name"), "start_date": start.isoformat(), "end_date": end.isoformat(),
                    "days_to_start": (start - today).days, "discipline": t.get("discipline")})
    return sorted(out, key=lambda r: r["start_date"])


def _equipment_keys(state: Mapping[str, Any]) -> List[str]:
    """Every equipment key the athlete has anywhere (home + gyms) — used only to
    skip a ladder test seed that needs equipment (the dragon flag needs a bench)."""
    eq = state.get("equipment") or {}
    keys = set(eq.get("home") or []) | set(eq.get("available") or [])
    for g in eq.get("gyms") or []:
        if isinstance(g, Mapping):
            keys |= set(g.get("equipment") or [])
    return sorted(str(k) for k in keys)


def _bw_ladders(state: Mapping[str, Any], today: date, archived_weeks: ArchivedWeeks) -> Dict[str, Any]:
    """C272: current level per bodyweight family — a READ-ONLY seed
    (``bw_ladders.seed_levels``: history, else the L-sit test). Never written."""
    try:
        return _bw.seed_levels(state, today, archived_weeks=archived_weeks, equipment=_equipment_keys(state))
    except Exception as exc:  # pragma: no cover - a broken ladder file must not kill the context
        return {"source": "error", "error": f"{type(exc).__name__}: {exc}", "families": []}


def _technique_library(catalog: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """C272: the technique / positioning / try-hard / pocket drill library and
    the technique ladders (levels per athlete live in the athlete plan notes)."""
    try:
        return _bw.technique_library(catalog)
    except Exception as exc:  # pragma: no cover
        return {"source": "error", "error": f"{type(exc).__name__}: {exc}", "drills": []}


def _warnings(ctx: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    ks = ctx.get("key_sessions") or {}
    if ks.get("source") == "error":
        out.append({"code": "KEY_SESSIONS_ERROR",
                    "message": f"stato delle sessioni chiave non calcolabile ({ks.get('error')})"})
    for k in ks.get("unknown_skips") or []:
        out.append({"code": "SKIP_WITHOUT_ID", "message": f"sessione saltata il {k['date']} senza id"})
    if ks.get("removed_unknown"):
        out.append({"code": "REMOVED_UNKNOWN",
                    "message": f"{ks['removed_unknown']} remove_session senza id nella settimana"})
    for row in ks.get("requirements") or []:
        if row.get("status") in ("missing", "partial"):
            out.append({"code": "KEY_MISSING", "key": row["key"], "severity": row.get("severity"),
                        "resolution": row.get("resolution"),
                        "message": f"stimolo chiave mancante questa settimana: {row['label']}"
                                   + (" (solo dose parziale)" if row.get("status") == "partial" else "")})
    for c in ks.get("conflicts") or []:
        out.append({"code": "KEY_CONFLICT", "conflict": c.get("code"), "date": c.get("date"),
                    "message": c.get("message")})
    for w in ctx.get("working_loads") or []:
        for f in w.get("flags") or []:
            out.append({"code": f, "exercise_id": w["exercise_id"],
                        "message": f"working load {w['exercise_id']}: {f}"})
    for proto, m in (ctx.get("maxima") or {}).items():
        if m and m.get("confidence") == "low":
            out.append({"code": "LOW_CONFIDENCE_TEST", "protocol": proto,
                        "message": f"test {proto} del {m['date']} a bassa confidenza "
                                   f"({m.get('confidence_exposures')} esposizioni nei 21 gg prima)"})
        if m and not m.get("tested"):
            out.append({"code": "MAX_NOT_TESTED", "protocol": proto,
                        "message": f"{proto}: massimale non testato di recente (anchor non disponibile)"})
    for ex, a in ((ctx.get("anchors") or {}).get("exercises") or {}).items():
        if a and a.get("ceiling_note"):
            out.append({"code": "AT_CEILING", "exercise_id": ex, "message": a["ceiling_note"]})
    out.extend(ctx.get("work_checks") or [])
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_athlete_context(
    state: Mapping[str, Any],
    today: DateLike,
    *,
    archived_weeks: ArchivedWeeks = None,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    catalog: Optional[Mapping[str, Mapping[str, Any]]] = None,
    with_proposals: bool = True,
    include_next_week: bool = True,
) -> Dict[str, Any]:
    """The read-only athlete context on ``today``. See the module docstring.

    ``with_proposals`` / ``include_next_week`` (A297): the in-app composer
    needs neither the catch-up proposals (each one is a replanner simulation)
    nor next week's key view, so it turns them off to stay fast."""
    st: Dict[str, Any] = copy.deepcopy(dict(state or {}))
    arch = copy.deepcopy(archived_weeks) if archived_weeks is not None else None
    rows = copy.deepcopy(list(outdoor_rows)) if outdoor_rows is not None else None
    cat = catalog if catalog is not None else load_exercise_catalog()
    td = _as_date(today)

    position = _position(st, td)
    phase_id = position.get("phase_id") if position.get("available") else None
    ctx: Dict[str, Any] = {
        "version": VERSION,
        "as_of": td.isoformat(),
        "constants": {
            "finger_gap_h": FINGER_GAP_H,
            "retest_block_h": RETEST_BLOCK_H,
            "pull_test_block_h": PULL_TEST_BLOCK_H,
            "heavy_pull_max_per_7d": HEAVY_PULL_MAX_PER_7D,
            "low_conf_min_exposures": rp.LOW_CONF_MIN_EXPOSURES,
            "low_conf_window_d": rp.LOW_CONF_WINDOW_D,
            "overused_min": OVERUSED_MIN,
        },
        "athlete_plan": ATHLETE_PLAN_PATH,
        "position": position,
        "maxima": _maxima(st, td, arch),
        "anchors": _anchors(st, td),
        "retest": _retest(st, td, arch, rows),
        "key_sessions": _key_sessions(st, td, arch, rows, cat, with_proposals=with_proposals),
        "key_sessions_next_week": None,
        "upcoming": _upcoming(st, td, arch),
        "recent": _recent(st, td, arch, rows),
        "guards": _guards(st, td, arch, rows),
        "variety": _variety(st, td, arch, cat),
        "working_loads": _working_loads(st, td),
        "try_hard": _tryhard(st, td, rows),
        "load_flags": _load_flags(st, td),
        "limit_log": _limit_log_view(st),
        "limits": _limits(st),
        "trips": _trips(st, td),
        "bw_ladders": _bw_ladders(st, td, arch),
        "technique_library": _technique_library(cat),
    }
    if position.get("available") and include_next_week:
        # Planning view: the next week too (no proposals: they are only made
        # for the current week).
        next_monday = _monday(td) + timedelta(days=7)
        ctx["key_sessions_next_week"] = _key_sessions(st, td, arch, rows, cat, week_of=next_monday,
                                                      with_proposals=False)
    ctx["work_checks"] = _work_checks(st, td, position, ctx["guards"], arch)
    ctx["warnings"] = _warnings(ctx)
    return ctx


def extract_plan_notes(markdown: str) -> Optional[str]:
    """The block between ``NOTES_BEGIN`` / ``NOTES_END`` in the athlete plan."""
    if not markdown or NOTES_BEGIN not in markdown or NOTES_END not in markdown:
        return None
    start = markdown.index(NOTES_BEGIN) + len(NOTES_BEGIN)
    end = markdown.index(NOTES_END, start)
    return markdown[start:end].strip() or None


# ---------------------------------------------------------------------------
# Italian text renderer (CLI)
# ---------------------------------------------------------------------------

def _fmt_kg(v: Any) -> str:
    n = _num(v)
    return "—" if n is None else (f"{n:.1f}".rstrip("0").rstrip("."))


def _anchor_line(ex: str, a: Mapping[str, Any]) -> str:
    ext = _num(a.get("external")) or 0.0
    ext_s = f"+{_fmt_kg(ext)}" if ext >= 0 else f"−{_fmt_kg(-ext)} (assistito)"
    pct = a.get("pct_of_official")
    ref = a.get("official_one_rm") or a.get("official_total")
    ref_lbl = "1RM" if a.get("official_one_rm") else "massimale"
    ramp = a.get("ramp") or {}
    ramp_s = f"rientro n={ramp.get('n')} ×{ramp.get('factor')}" if ramp.get("factor", 1.0) < 1.0 else "rampa piena"
    parts = [f"  {ex}: {a.get('rep_scheme')} a {ext_s} kg (totale {_fmt_kg(a.get('total'))})",
             f"= {round(pct * 100) if pct else '—'}% di {_fmt_kg(ref)} kg {ref_lbl} (test {a.get('official_date')})",
             f"| tetto {_fmt_kg(a.get('cap'))} / pavimento {_fmt_kg(a.get('floor'))} | {ramp_s}"]
    if a.get("clamped"):
        parts.append(f"| clamp: {a['clamped']}")
    if a.get("guards"):
        parts.append(f"| guardie: {', '.join(a['guards'])}")
    if a.get("pain"):
        parts.append("| dolore attivo")
    if a.get("fatigue"):
        parts.append("| fatica → pavimento")
    return " ".join(parts)


_RESOLUTION_IT = {
    "proposal": "proposta", "deferred_next": "rimandata alla prossima chiave",
    "deferred_fatigue": "niente recupero (fatica recente)", "let_go": "lasciala andare",
    "missed": "persa",
}


def _render_keys(L: List[str], ks: Mapping[str, Any], label: str) -> None:
    src = ks.get("source")
    src_lbl = f"ERRORE: {ks.get('error')}" if src == "error" else f"A294 {ks.get('version') or ''}".strip()
    L.append(f"## Sessioni chiave, {label} — {ks.get('week_start')} → {ks.get('week_end')} "
             f"({ks.get('phase_id')}) [{src_lbl}]")

    def _refs(items: Iterable[Mapping[str, Any]]) -> str:
        return ", ".join(f"{x['date'][5:]} {x.get('session_id') or x.get('name')}"
                         + (" (passata, non segnata)" if x.get("unmarked") else "")
                         + (" (dose parziale)" if x.get("dose") == "partial" else "") for x in items) or "—"

    for r in ks.get("requirements") or []:
        line = (f"  [{str(r.get('status', '')).upper():7}] {r.get('label')}: fatte {_refs(r.get('done') or [])} | "
                f"pianificate {_refs(r.get('planned') or [])}")
        if r.get("partial"):
            line += f" | parziali {_refs(r['partial'])}"
        if r.get("skipped"):
            line += f" | saltate {_refs(r['skipped'])}"
        if r.get("due_by"):
            line += f" | ultimo {r.get('last_full_date')}, entro {r['due_by']}"
        if r.get("status") == "not_due":
            line += " | non dovuto questa settimana (dentro il gap): NON aggiungerlo"
        if r.get("debt"):
            line += f" | debito {r['debt']}"
            if r.get("resolution"):
                line += f", {_RESOLUTION_IT.get(r['resolution'], r['resolution'])}"
            if r.get("resolution") == "deferred_next" and r.get("next_key"):
                line += f" ({str(r['next_key'].get('date'))[5:]} {r['next_key'].get('session_id')})"
            if r.get("severity") == "critical":
                line += " [CRITICA]"
        if r.get("hint") and r.get("debt"):
            line += f" — {r['hint']}"
        L.append(line)
    for p in ks.get("proposals") or []:
        side = "; ".join(f"{x['date'][5:]} {x['from']} → {x['to']}" for x in p.get("side_effects") or [])
        L.append(f"  PROPOSTA ({', '.join(p.get('keys') or [])}): {p['date']} {p['slot']} {p['session_id']} "
                 f"[{p.get('location')}]" + (f" | effetti: {side}" if side else " | nessun effetto collaterale")
                 + (" | dose di rientro (niente campus)" if p.get("reduced_reentry_dose") else ""))
    for c in ks.get("conflicts") or []:
        L.append(f"  ! {c.get('code')}: {c.get('message')}")
    sm = ks.get("summary") or {}
    if sm:
        L.append(f"  Requisiti {sm.get('required')}: coperti {sm.get('covered')}, fatti {sm.get('done')}. "
                 "Uno stimolo saltato in una settimana passata è perso, non è debito.")


_BW_SOURCE_IT = {"history": "storico", "test": "test", "state": "stato", "none": "nessun dato",
                 "catalog": "catalogo", "not_applicable": "non applicabile"}


def _render_bw_ladders(L: List[str], bw: Mapping[str, Any]) -> None:
    """C272: current level per bodyweight family (read-only seed)."""
    L.append("")
    L.append("## Scale corpo libero (livello attuale, seed in sola lettura — C272)")
    if bw.get("source") == "error":
        L.append(f"  non calcolabile ({bw.get('error')})")
        return
    if not bw.get("tested_gate"):
        L.append("  atleta non testato: nessun seed, valgono le dosi del catalogo")
        return
    lsit = bw.get("l_sit_test")
    if lsit:
        L.append(f"  L-sit {lsit['value']:g} s (log test del {lsit['log_date']})")
    for r in bw.get("families") or []:
        src = _BW_SOURCE_IT.get(r.get("source"), r.get("source"))
        if r.get("level_idx") is None:
            why = f" — {r['why']}" if r.get("why") else ""
            L.append(f"  {r['family']}: {src}{why}")
            continue
        unit = " s" if r.get("axis") == "seconds" else ""
        band = r.get("band") or {}
        bits = [f"L{r['level_idx']}/{r['n_levels'] - 1} {r['exercise_id']} {r['sets']}×{r['target']}{unit} "
                f"(banda {band.get('lo')}-{band.get('hi')}{unit}, passo {band.get('step')})"]
        ev = r.get("evidence") or {}
        if r.get("source") == "history" and ev:
            bits.append(f"[storico: {ev.get('exercise_id')} {ev.get('sets') or '?'}×{ev.get('dose') or '?'} "
                        f"il {ev.get('date')}, {ev.get('label') or 'non valutato'} → −1 passo]")
        elif r.get("source") == "test":
            sf = r.get("seeded_from") or {}
            bits.append(f"[test {sf.get('test')} {sf.get('value'):g} del {sf.get('log_date')}]")
        else:
            bits.append(f"[{src}]")
        if r.get("at_top_of_band"):
            bits.append("IN CIMA ALLA BANDA: prossimo passo terminale o livello successivo")
        if r.get("ramp"):
            rp_ = r["ramp"]
            bits.append(f"rampa: {rp_.get('sessions')} sedute qui, poi L{rp_.get('then_level')} a {rp_.get('then_target')}{unit}")
        if r.get("gate"):
            bits.append(f"richiede {r['gate']} nel blocco")
        if r.get("manual_only"):
            bits.append("SOLO MANUALE (rischio lombare)")
        if r.get("heavy_pull"):
            bits.append("conta come tirata pesante")
        if r.get("hanging"):
            bits.append("appeso: mai nelle 24 h prima di limit/strength_long")
        if r.get("next_exercise_id"):
            bits.append(f"poi {r['next_exercise_id']}")
        L.append(f"  {r['family']}: " + " · ".join(bits))
    L.append("  Il seed non scrive niente: le promozioni le decidi tu con Daniele finché non arriva il brief A "
             "della progressione (scale in backend/catalog/progressions/v1/bw_ladders.json).")


def _render_technique_library(L: List[str], lib: Mapping[str, Any]) -> None:
    """C272: the technique / try-hard drill library and the technique ladders."""
    L.append("")
    L.append("## Libreria tecnica / try-hard (id con role 'library' — solo composizione a mano)")
    if lib.get("source") == "error":
        L.append(f"  non disponibile ({lib.get('error')})")
        return
    for t in lib.get("technique_ladders") or []:
        lv = " · ".join(f"{x['level']} [{', '.join(x['drills'])}]" for x in t.get("levels") or [])
        L.append(f"  Scala {t.get('ladder')}: {lv}")
    for d in lib.get("drills") or []:
        tag = " (dita-hard)" if d.get("finger_hard") else ""
        L.append(f"  {d['exercise_id']}{tag} — misura: {d.get('measure') or '—'}")
    if lib.get("protocols"):
        L.append(f"  Protocolli (bw_ladders.json → protocols): {', '.join(lib['protocols'])}")
    L.append("  Il livello corrente di PIEDI / POSIZIONI / CADUTE sta nelle «Note atleta» qui sotto.")


def render_text(ctx: Mapping[str, Any], *, plan_notes: Optional[str] = None,
                source_line: Optional[str] = None) -> str:
    """Italian rendering for Claude Code."""
    L: List[str] = []
    L.append(f"=== Contesto atleta — {ctx.get('as_of')} (versione {ctx.get('version')}) ===")
    if source_line:
        L.append(source_line)
    pos = ctx.get("position") or {}
    goal = pos.get("goal") or {}
    if goal:
        L.append(f"Obiettivo: {goal.get('target_grade')} {goal.get('target_style') or ''} "
                 f"entro {goal.get('deadline')} (attuale {goal.get('current_grade')}, {goal.get('discipline')})")
    L.append("")
    L.append("## Posizione")
    if pos.get("available"):
        L.append(f"  {pos['phase_id']} settimana {pos['week_in_phase_1based']}/{pos['phase_weeks']} "
                 f"(settimana {pos['abs_week']}/{pos['total_weeks']} del macrociclo; fase {pos['phase_start']} → "
                 f"{pos['phase_end']} escluso; poi {pos.get('next_phase_id') or 'fine ciclo'})"
                 + (" — PAUSA ATTIVA" if pos.get("paused") else ""))
        if pos.get("intensity_cap"):
            L.append(f"  Tetto di intensità della fase: {pos['intensity_cap']}")
    else:
        L.append("  nessun macrociclo")

    L.append("")
    L.append("## Massimali ufficiali (solo test, per protocollo)")
    for proto, m in (ctx.get("maxima") or {}).items():
        if not m:
            L.append(f"  {proto}: nessun test")
            continue
        extra = f", 1RM {_fmt_kg(m.get('one_rm_kg'))}" if m.get("one_rm_kg") else ""
        conv = f", convertito da {m.get('source_seconds')}s" if m.get("converted") else ""
        L.append(f"  {proto}: {_fmt_kg(m.get('total_kg'))} kg totali{extra} — test {m.get('date')} "
                 f"({m.get('age_days')} gg{conv}); confidenza {m.get('confidence')} "
                 f"[{m.get('confidence_basis')}, {m.get('confidence_exposures')} esposizioni]; "
                 f"{'testato' if m.get('tested') else 'NON valido per gli anchor'}"
                 + (f"; trend {m.get('trend')} {m.get('delta_pct')}%" if m.get("trend") else ""))

    L.append("")
    an = ctx.get("anchors") or {}
    L.append(f"## Carichi ancorati oggi (anchored_load B364, peso corporeo {_fmt_kg(an.get('bodyweight_kg'))} kg)")
    for ex, a in (an.get("exercises") or {}).items():
        L.append(_anchor_line(ex, a) if a else f"  {ex}: carico non disponibile (massimale non testato)")
    L.append("  Questi sono gli UNICI numeri di carico per gli esercizi ancorati: mai working_loads grezzi.")
    L.append("  Valgono SOLO per lo schema indicato (serie×ripetizioni del catalogo). Con un altro schema il "
             "carico cambia: usa la riga «carico al play» di --simulate, che lo ricalcola sullo schema della bozza.")

    L.append("")
    _render_keys(L, ctx.get("key_sessions") or {}, "questa settimana")
    if ctx.get("key_sessions_next_week"):
        L.append("")
        _render_keys(L, ctx["key_sessions_next_week"], "settimana prossima")

    L.append("")
    rt = ctx.get("retest") or {}
    L.append("## Retest (retest_policy A289)")
    if not rt.get("available"):
        L.append("  nessun asse testato")
    for axis, row in (rt.get("axes") or {}).items():
        nt = row.get("next_test")
        nxt = (f"prossimo {nt['date']} ({nt.get('source')}, {nt.get('trigger')})"
               + (f" BLOCCHI: {', '.join(b.get('code', '') for b in nt.get('blockers') or [])}" if nt and nt.get("blockers") else "")
               if nt else f"nessun test in vista ({row.get('next_test_reason')})")
        L.append(f"  {axis}: ufficiale {_fmt_kg(row.get('official_total_kg'))} kg ({row.get('test_date')}), "
                 f"confidenza {row.get('confidence')}, non prima del {row.get('earliest_retest')}; {nxt}; "
                 f"segnali {row.get('signals', {}).get('count')}/{row.get('signals', {}).get('needed')}")

    L.append("")
    g = ctx.get("guards") or {}
    hc = g.get("hard_cap") or {}
    L.append(f"## Guardie (gap dita {g.get('finger_gap_h')} h, test dita {g.get('retest_block_h')} h, "
             f"tirata pesante max {g.get('heavy_pull_max_per_7d')}/7 gg)")
    L.append(f"  Giorni hard settimana: {hc.get('count')}/{hc.get('cap')} ({', '.join(d[5:] for d in hc.get('hard_days') or []) or '—'})"
             + (" — AL CAP" if hc.get("at_cap") else ""))
    for d in g.get("days") or []:
        bits = []
        bits.append("dita max OK" if d["finger_max_ok"] else "NO dita max (" + "; ".join(d["finger_reasons"]) + ")")
        if d["finger_hard_today"]:
            bits.append("già giorno dita hard: " + ", ".join(d["finger_hard_today_sessions"]))
        bits.append("tirata pesante OK" if d["heavy_pull_ok"] else "NO tirata ≥85% (" + "; ".join(d["pull_reasons"]) + ")")
        if not d["hiit_ok"]:
            bits.append("NO HIIT")
        L.append(f"  {d['date']} {d['weekday']}: " + " | ".join(bits))

    L.append("")
    L.append(f"## Prossimi {UPCOMING_DAYS} giorni")
    for s in ctx.get("upcoming") or []:
        flags = [f for f, on in (("hard", s["hard"]), ("dita", s["finger"]), ("tirata", s["pulling"]),
                                 ("dita-hard", s["finger_hard"]), ("test", s["is_test"]),
                                 ("custom", s["is_custom"]), ("HIIT?", s["hiit"])) if on]
        L.append(f"  {s['date']} {s.get('slot') or '-':8} {s.get('session_id')} "
                 f"{('«' + s['name'] + '»') if s.get('name') else ''} [{s['status']}] "
                 f"{'/'.join(flags) or 'leggera'} {('stimoli: ' + ','.join(s['stimuli'])) if s['stimuli'] else ''}".rstrip())

    L.append("")
    rc = ctx.get("recent") or {}
    L.append("## Ultimi 7 giorni (outdoor: 14)")
    for s in rc.get("sessions") or []:
        L.append(f"  {s['date']} {s.get('slot') or '-':8} {s.get('session_id')} [{s['status']}] "
                 f"{('stimoli: ' + ','.join(s['stimuli'])) if s['stimuli'] else ''}".rstrip())
    for o in rc.get("outdoor") or []:
        L.append(f"  {o['date']} outdoor {o.get('spot')}: {o['routes']} vie, {o['sent']} chiuse"
                 + (f" — giorno dita HARD ({o.get('hardest_hard_route')} {o.get('hardest_hard_grade')})" if o["hard_day"] else ""))

    L.append("")
    v = ctx.get("variety") or {}
    L.append(f"## Varietà ({v.get('window_start')} → {v.get('window_end')}, soglia {OVERUSED_MIN}×)")
    over = v.get("overused") or []
    L.append("  Usati troppo (ruotare): " + (", ".join(over) if over else "nessuno"))
    top = [f"{g2['group']} {g2['count']}×" for g2 in (v.get("groups") or [])[:12]]
    if top:
        L.append("  Gruppi più usati: " + ", ".join(top))

    wl = ctx.get("working_loads") or []
    if wl:
        L.append("")
        L.append("## Working load degli esercizi ancorati (informativo, NON fonte di carico)")
        for w in wl:
            L.append(f"  {w['exercise_id']}: ultimo {_fmt_kg(w.get('last_external_load_kg'))} kg "
                     f"× {w.get('last_reps') or w.get('last_work_seconds') or '—'} ({w.get('updated_at')}, "
                     f"{w.get('last_feedback_label') or 'non valutato'}) {' '.join(w['flags'])}".rstrip())

    th = ctx.get("try_hard") or {}
    L.append("")
    L.append(f"## Try-hard (note outdoor dal {th.get('window_start')}, formato «T1 M7 FALL +1»)")
    if th.get("logged_attempts"):
        c = th["counts"]
        L.append(f"  SEND {c['SEND']} · FALL {c['FALL']} · TAKE {c['TAKE']} · LET_GO {c['LET_GO']} → "
                 f"FALL sul totale dei non-send: {th.get('fall_pct_of_non_send')}%")
    else:
        L.append("  nessun tentativo loggato nel formato (non è una sessione chiave mancante)")

    _render_bw_ladders(L, ctx.get("bw_ladders") or {})
    _render_technique_library(L, ctx.get("technique_library") or {})

    lim = ctx.get("limits") or {}
    trips = ctx.get("trips") or []
    L.append("")
    L.append("## Limiti e viaggi")
    L.append(f"  Limitazioni: {', '.join(lim.get('active_flags') or []) or 'nessuna'}"
             + (f"; note coach: {lim['coach_notes']}" if lim.get("coach_notes") else ""))
    for t in trips:
        L.append(f"  Viaggio {t['name']} {t['start_date']} → {t['end_date']} (tra {t['days_to_start']} gg)")

    if plan_notes:
        L.append("")
        L.append(f"## Note atleta ({ctx.get('athlete_plan')})")
        for line in plan_notes.splitlines():
            L.append(f"  {line}" if line.strip() else "")

    warns = ctx.get("warnings") or []
    L.append("")
    L.append("## Avvisi")
    if not warns:
        L.append("  nessuno")
    for w in warns:
        L.append(f"  [{w['code']}] {w['message']}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# A297 (R7b) — English renderers for the in-app coach and composer prompts.
#
# The single integration point of the engine's athlete data (B364 maxima and
# anchored loads, A295 pain / fatigue / retest signals, A294 key sessions, A296
# limit log) into an LLM prompt. Neutral for any user: no internal brief ids,
# no "fallback" labels, no Italian, nothing that is not computed. A section
# whose source failed is left out, never guessed.
# ---------------------------------------------------------------------------

#: Default character budgets (≈ 4 chars/token).
COACH_BLOCK_MAX_CHARS = 3500
COMPOSER_BLOCK_MAX_CHARS = 2500

_PROTOCOL_EN = {
    rp.PROTOCOL_HANG_7S: "max hang 7s",
    rp.PROTOCOL_HANG_5S: "max hang 5s",
    rp.PROTOCOL_PULLUP_2RM: "weighted pull-up 2RM",
}

_GUARD_EN = {
    "finger_hard_adjacent": "finger-hard day {detail}",
    "finger_spacing": "finger session {detail} inside the plan's finger spacing",
    "hang_test_soon": "hang test within " + str(RETEST_BLOCK_H) + " h ({detail})",
    "heavy_pull_week": "heavy pulling already on {detail} (max " + str(HEAVY_PULL_MAX_PER_7D) + " per 7 days)",
    "pre_limit": "{detail} the next day",
    "pull_test_soon": "pull-up test within " + str(PULL_TEST_BLOCK_H) + " h ({detail})",
    "deload": "deload phase",
    "hard_cap": "weekly hard-day cap reached ({detail})",
    "max_session_adjacent": "max session the same day or the next",
}

_AXIS_EN = {AXIS_FINGER: "fingers", AXIS_PULLING: "pulling"}


def _codes_en(codes: Iterable[Mapping[str, Any]]) -> str:
    seen: List[str] = []
    for c in codes or []:
        tpl = _GUARD_EN.get(str(c.get("code")))
        if not tpl:
            continue
        txt = tpl.format(detail=str(c.get("detail") or "").strip()).replace(" ()", "")
        if txt not in seen:
            seen.append(txt)
    return "; ".join(seen)


def _position_en(pos: Mapping[str, Any]) -> str:
    if not pos.get("available"):
        return "No active macrocycle."
    out = (f"Phase {pos.get('phase_id')} week {pos.get('week_in_phase_1based')}/{pos.get('phase_weeks')} "
           f"(macrocycle week {pos.get('abs_week')}/{pos.get('total_weeks')}); next: "
           f"{pos.get('next_phase_id') or 'end of cycle'} from {pos.get('phase_end')}")
    if pos.get("paused"):
        out += " — PLAN PAUSED"
    return out + "."


def _maxima_lines_en(ctx: Mapping[str, Any]) -> List[str]:
    out: List[str] = []
    for proto, m in (ctx.get("maxima") or {}).items():
        if not m:
            continue
        if not m.get("tested"):
            # A297 review: a stale test (> TEST_FRESH_DAYS) or a baseline-only
            # self-report stays visible — flagged as such — exactly like the
            # pre-A297 B364 line, so the coach never reads the leftover raw
            # baseline numbers as a current tested max.
            out.append(f"- {_PROTOCOL_EN.get(proto, proto)}: {_fmt_kg(m.get('total_kg'))} kg total, from "
                       f"{m.get('date')} (stale or not a test — not a current tested max; it changes ONLY "
                       "with a test)")
            continue
        bits = [f"{_fmt_kg(m.get('total_kg'))} kg total"]
        if m.get("one_rm_kg"):
            bits.append(f"1RM {_fmt_kg(m.get('one_rm_kg'))} kg")
        bits.append(f"tested {m.get('date')} ({m.get('age_days')} d ago"
                    + (f", converted from the {m.get('source_seconds')}s test" if m.get("converted") else "") + ")")
        if m.get("confidence"):
            bits.append(f"confidence {m['confidence']} ({m.get('confidence_exposures')} exposures "
                        f"in the {rp.LOW_CONF_WINDOW_D} days before the test)")
        if m.get("trend"):
            bits.append(f"trend {m['trend']} {m.get('delta_pct')}%")
        out.append(f"- {_PROTOCOL_EN.get(proto, proto)}: " + ", ".join(bits))
    return out


def _anchor_line_en(ex: str, a: Mapping[str, Any]) -> str:
    ext = _num(a.get("external")) or 0.0
    ext_s = f"+{_fmt_kg(ext)} kg" if ext >= 0 else f"-{_fmt_kg(-ext)} kg (assisted)"
    pct = a.get("pct_of_official")
    ref = a.get("official_one_rm") or a.get("official_total")
    ref_lbl = "1RM" if a.get("official_one_rm") else "max"
    line = (f"- {ex}: {a.get('rep_scheme')} at {ext_s} ({_fmt_kg(a.get('total'))} kg total"
            + (f", {round(pct * 100)}% of the {_fmt_kg(ref)} kg {ref_lbl}" if pct else "") + ")")
    ramp = a.get("ramp") or {}
    if (ramp.get("factor") or 1.0) < 1.0:
        line += f"; re-entry after a break (exposure {ramp.get('n')}), capped lower"
    if a.get("guards"):
        line += f"; capped by {', '.join(str(g) for g in a['guards'])}"
    if a.get("pain"):
        line += "; pain flag → reduced"
    if a.get("fatigue"):
        line += "; fatigue flag → at the phase floor"
    if a.get("ceiling_note"):
        line += "; at the ceiling of the tested max (the next retest raises it)"
    return line


def _load_flags_lines_en(ctx: Mapping[str, Any]) -> List[str]:
    lf = ctx.get("load_flags") or {}
    out: List[str] = []
    for axis, p in sorted((lf.get("pain") or {}).items()):
        out.append(f"- Pain ({p.get('site')}, score {p.get('score')}/3) active {p.get('from')} → {p.get('until')}: "
                   f"{_AXIS_EN.get(axis, axis)} loads are reduced and no max {_AXIS_EN.get(axis, axis)} efforts "
                   "while it lasts (the engine removes them from ad-hoc sessions); keep that work submaximal "
                   "and ask how it feels.")
    for axis, f in sorted((lf.get("fatigue") or {}).items()):
        out.append(f"- Fatigue: {len(f.get('hard_days') or [])} hard/very hard {_AXIS_EN.get(axis, axis)} sessions in "
                   "14 days → loads held at the phase floor.")
    return out


def _limit_lines_en(ctx: Mapping[str, Any]) -> List[str]:
    out: List[str] = []
    for e in ctx.get("limit_log") or []:
        line = (f"- {e.get('date')} {str(e.get('surface') or '?').replace('_', ' ')}"
                f" ({e.get('source')}), target {e.get('target_grade') or '?'}: ")
        if e.get("problems"):
            line += f"{e['problems']} problems, {e.get('sent')} sent"
            if e.get("best_sent"):
                line += f" (best {e['best_sent']})"
        else:
            line += "no problems logged"
        if e.get("next_target_grade"):
            line += f" → next target {e['next_target_grade']}"
        if e.get("warning") == "hard_attempts_guard":
            line += " [too many hard attempts]"
        out.append(line)
    return out


def _retest_lines_en(ctx: Mapping[str, Any]) -> List[str]:
    out: List[str] = []
    for axis, row in ((ctx.get("retest") or {}).get("axes") or {}).items():
        if not row.get("covered"):
            continue
        nt = row.get("next_test")
        if nt:
            nxt = f"next test {nt.get('date')} ({nt.get('source')})"
            if nt.get("blockers"):
                nxt += " — currently blocked: " + ", ".join(str(b.get("code")) for b in nt["blockers"])
        else:
            nxt = f"no test due yet ({str(row.get('next_test_reason') or '').replace('_', ' ')})"
        sig = row.get("signals") or {}
        out.append(f"- {_AXIS_EN.get(axis, axis)}: {nxt}; not before {row.get('earliest_retest')}; "
                   f"measured retest signals {sig.get('count')}/{sig.get('needed')}")
    return out


def _key_text(ctx: Mapping[str, Any]) -> str:
    ks = ctx.get("key_sessions") or {}
    if ks.get("source") == "error":
        return ""
    try:
        return ks1.key_status_text(ks)
    except Exception:  # pragma: no cover - defensive: never break the prompt
        return ""


def _restricted_days_en(ctx: Mapping[str, Any], limit: int) -> List[str]:
    out: List[str] = []
    for d in (ctx.get("guards") or {}).get("days") or []:
        bits: List[str] = []
        if not d.get("finger_max_ok"):
            bits.append("no max finger work (" + _codes_en(d.get("finger_codes") or []) + ")")
        if not d.get("heavy_pull_ok"):
            bits.append("no pulling ≥85% 1RM or front lever (" + _codes_en(d.get("pull_codes") or []) + ")")
        if not d.get("hiit_ok"):
            bits.append("no HIIT")
        if bits:
            out.append(f"- {d['date']} {d.get('weekday')}: " + "; ".join(bits))
        if len(out) >= limit:
            break
    return out


def _clip(lines: List[str], max_chars: int) -> str:
    """Join, dropping whole lines from the end (never cutting mid-line) until
    the block fits the budget; the header lines are always kept."""
    text = "\n".join(lines)
    while len(text) > max_chars and len(lines) > 2:
        lines = lines[:-1]
        text = "\n".join(lines)
    return text


def render_coach_block(ctx: Mapping[str, Any], *, max_chars: int = COACH_BLOCK_MAX_CHARS) -> str:
    """English athlete-context block for the coach CHAT prompt (dynamic,
    never cached). Sections are ordered by importance so a budget cut drops the
    least important (variety, limit log) first."""
    L: List[str] = [
        f"## Athlete context (computed by the engine for {ctx.get('as_of')})",
        "(Deterministic engine facts — never contradict them and never invent numbers outside them. "
        "An official max changes ONLY with a test, never with feedback; training loads are set by the "
        "engine from it.)",
        "- Position: " + _position_en(ctx.get("position") or {}),
    ]
    maxima = _maxima_lines_en(ctx)
    if maxima:
        L.append("Official maxima (tests only):")
        L.extend(maxima)
    anchors = [(ex, a) for ex, a in ((ctx.get("anchors") or {}).get("exercises") or {}).items() if a]
    if anchors:
        L.append("Training loads today (engine, valid only for the stated sets x reps):")
        L.extend(_anchor_line_en(ex, a) for ex, a in anchors)
    flags = _load_flags_lines_en(ctx)
    if flags:
        L.extend(flags)
    keys = _key_text(ctx)
    if keys:
        L.append("Key sessions this week — never suggest dropping or replacing one without saying which "
                 "stimulus is lost; a missed key stimulus of a past week is gone, not owed:")
        L.extend(keys.splitlines())
    hc = (ctx.get("guards") or {}).get("hard_cap") or {}
    restricted = _restricted_days_en(ctx, limit=5)
    if restricted or hc.get("cap") is not None:
        L.append("Recovery guards for the next days"
                 + (f" (hard days this week {hc.get('count')}/{hc.get('cap')})" if hc.get("cap") is not None else "")
                 + ":")
        L.extend(restricted or ["- no finger / pulling restrictions in the next days"])
    retest = _retest_lines_en(ctx)
    if retest:
        L.append("Retest policy (only the policy schedules tests):")
        L.extend(retest)
    limit = _limit_lines_en(ctx)
    if limit:
        L.append("Limit-boulder log (newest first):")
        L.extend(limit)
    over = (ctx.get("variety") or {}).get("overused") or []
    if over:
        L.append(f"- Used {OVERUSED_MIN}+ times in the last {VARIETY_WEEKS} weeks (rotate): " + ", ".join(over[:10]))
    return _clip(L, max_chars)


def day_guard(ctx: Mapping[str, Any], day: Optional[DateLike] = None) -> Optional[Dict[str, Any]]:
    """The guard row of ``day`` (default: ``as_of``), or None when outside the
    guard horizon."""
    d_iso = _as_date(day).isoformat() if day is not None else str(ctx.get("as_of"))
    for row in (ctx.get("guards") or {}).get("days") or []:
        if row.get("date") == d_iso:
            return row
    return None


def _grades_en(state: Mapping[str, Any]) -> str:
    g = ((state.get("assessment") or {}).get("grades") or {})
    bits = [f"{lbl} {g[k]}" for k, lbl in (("lead_max_rp", "lead RP"), ("lead_max_os", "lead OS"),
                                            ("boulder_max_rp", "boulder RP (Font)")) if g.get(k)]
    return ", ".join(bits)


def render_composer_block(
    ctx: Mapping[str, Any],
    *,
    state: Optional[Mapping[str, Any]] = None,
    day: Optional[DateLike] = None,
    max_chars: int = COMPOSER_BLOCK_MAX_CHARS,
) -> str:
    """English ``ATHLETE CONTEXT`` for the ad-hoc composer, placed AFTER the
    athlete's literal request: the request decides what is trained, this
    constrains how. Only certain data; ≤ ``max_chars``."""
    d_iso = _as_date(day).isoformat() if day is not None else str(ctx.get("as_of"))
    L: List[str] = [
        f"ATHLETE CONTEXT (engine-computed for the session day {d_iso}; the request decides WHAT is "
        "trained, this context constrains HOW):",
        "- " + _position_en(ctx.get("position") or {}),
    ]
    if state is not None and _grades_en(state):
        L.append(f"- Level: {_grades_en(state)}.")
    g = day_guard(ctx, d_iso)
    if g is not None:
        if g.get("finger_max_ok") and g.get("heavy_pull_ok"):
            L.append("- Guards on this day: no finger / pulling restriction.")
        else:
            if not g.get("finger_max_ok"):
                L.append("- Guard: NO max finger work this day (max hangs, limit boulders, campus) — "
                         + _codes_en(g.get("finger_codes") or []) + ". The engine removes such lines.")
            if not g.get("heavy_pull_ok"):
                L.append("- Guard: NO pulling at ≥85% 1RM and NO front lever this day — "
                         + _codes_en(g.get("pull_codes") or []) + ". Moderate pulling is fine.")
        if not g.get("hiit_ok"):
            L.append("- Avoid HIIT / VO2 intervals: a max session is the same day or the next.")
    for line in _load_flags_lines_en(ctx):
        L.append(line)
    ks = ctx.get("key_sessions") or {}
    if ks.get("source") != "error" and ks.get("requirements"):
        parts = []
        for r in ks["requirements"]:
            st = str(r.get("status"))
            nxt = [p for p in r.get("planned") or [] if not p.get("unmarked")]
            txt = f"{r.get('label')} {st}"
            if st == "planned" and nxt:
                txt += f" ({str(nxt[0].get('date'))[5:]})"
            parts.append(txt)
        L.append("- Key sessions this week: " + "; ".join(parts)
                 + ". Do not duplicate a key stimulus that is planned this week; never replace a key session.")
    anchored = [ex for ex, a in ((ctx.get("anchors") or {}).get("exercises") or {}).items() if a]
    if anchored:
        L.append("- Exercises marked [ANCHOR] get their load from the athlete's tested max (engine-set): pick "
                 "them for the stimulus, never swap them for a variant to change the load.")
    for e in (ctx.get("limit_log") or [])[:1]:
        if e.get("next_target_grade"):
            L.append(f"- Limit target on {str(e.get('surface') or '?').replace('_', ' ')}: "
                     f"{e['next_target_grade']} (last limit session {e.get('date')}).")
    over = (ctx.get("variety") or {}).get("overused") or []
    if over:
        L.append(f"- Overused in the last {VARIETY_WEEKS} weeks (prefer alternatives, marked [OVERUSED]): "
                 + ", ".join(over[:10]) + ".")
    return _clip(L, max_chars)


# ---------------------------------------------------------------------------
# A297 — the composer guard derived from the context (deterministic)
# ---------------------------------------------------------------------------

def _finger_hard_ids() -> set:
    from backend.engine.stimulus import EXERCISE_FAMILY, FAMILY_FINGER_MAX, FINGER_FATIGUE_EXTRA_IDS

    ids = {eid for eid, fam in EXERCISE_FAMILY.items() if fam in (FAMILY_FINGER_MAX, FAMILY_LIMIT_POWER)}
    return ids | set(FINGER_FATIGUE_EXTRA_IDS)


def _pulling_max_ids() -> set:
    from backend.engine.stimulus import EXERCISE_FAMILY, FAMILY_PULLING_MAX

    return {eid for eid, fam in EXERCISE_FAMILY.items() if fam == FAMILY_PULLING_MAX}


def front_lever_ids(catalog: Mapping[str, Mapping[str, Any]]) -> set:
    """Front-lever variants (counted as heavy pulling, decision 2026-10-04)."""
    return {str(eid) for eid, ex in catalog.items()
            if str(eid).startswith("front_lever") or (ex or {}).get("recency_group") == "core_front_lever"}


def heavy_pull_pct(state: Mapping[str, Any], exercise_id: str, day: DateLike, *,
                   sets: Optional[int] = None, reps: Optional[int] = None,
                   session_exercise_ids: Optional[Iterable[str]] = None) -> Optional[float]:
    """% of 1RM of a weighted pull prescribed by ``anchored_load`` on ``day``,
    or None when the athlete has no tested max (not verifiable)."""
    anch = anchored_load(state, exercise_id, date=_as_date(day).isoformat(), sets=sets, reps=reps,
                         session_exercise_ids=session_exercise_ids)
    if anch is None:
        return None
    return _num(anch.get("pct_of_official"))


def athlete_is_tested(ctx: Optional[Mapping[str, Any]]) -> bool:
    """True when the athlete has at least one TESTED official max (source test
    and < TEST_FRESH_DAYS old). DECISIONS (global): higher intensities and the
    anchor rules apply only to tested athletes; an untested athlete's ad-hoc
    selection stays the pre-A297 one (guards still remove, never add)."""
    return any(bool(m and m.get("tested")) for m in ((ctx or {}).get("maxima") or {}).values())


#: ENGINEERING CONSTANT (design choice, no published source): finger-hard /
#: campus exercises allowed in ONE ad-hoc session — 2 normally, 1 on a
#: low-energy day. Without it the intensity ranking stacks four campus drills
#: or three max-hang protocols in one preview.
MAX_FINGER_HARD_PER_SESSION = 2
MAX_FINGER_HARD_PER_SESSION_LOW_ENERGY = 1


def finger_hard_session_ids(catalog: Mapping[str, Mapping[str, Any]]) -> set:
    """Exercises that count against ``MAX_FINGER_HARD_PER_SESSION``: the
    finger-max / limit-power families, the finger-fatigue hangs and every
    campus drill (campus_sprint_endurance included)."""
    ids = {i for i in _finger_hard_ids() if i in catalog}
    ids |= {str(eid) for eid in catalog if str(eid).startswith("campus_")}
    return ids


def _max_intensity_ids(catalog: Mapping[str, Mapping[str, Any]], domains: Iterable[str]) -> set:
    """Catalog exercises at ``intensity_level == "max"`` in any of ``domains``
    (bodyweight max pulls such as one_arm_pullup_assisted are not in the
    pulling_max family, but they are a max pulling effort all the same)."""
    want = set(domains)
    out = set()
    for eid, ex in catalog.items():
        ex = ex or {}
        if ex.get("intensity_level") != "max":
            continue
        dom = ex.get("domain") or []
        if isinstance(dom, str):
            dom = [dom]
        if want & set(dom):
            out.add(str(eid))
    return out


def cap_finger_hard(
    exercises: List[Dict[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
    energy: Optional[str],
) -> List[str]:
    """Remove, in place, the finger-hard / campus lines beyond the per-session
    cap (LLM path, after validation; first ones kept). Returns ``dropped``."""
    ids = finger_hard_session_ids(catalog)
    cap = MAX_FINGER_HARD_PER_SESSION_LOW_ENERGY if energy == "low" else MAX_FINGER_HARD_PER_SESSION
    n = 0
    keep: List[Dict[str, Any]] = []
    dropped: List[str] = []
    for e in exercises:
        eid = str(e.get("exercise_id"))
        if eid in ids:
            if n >= cap:
                dropped.append(f"{eid}: more than {cap} finger-hard / campus exercises in one session")
                continue
            n += 1
        keep.append(e)
    exercises[:] = keep
    return dropped


_FINGER_DOMAINS = ("finger_strength", "finger_max_strength", "contact_strength")
_PULLING_DOMAINS = ("strength_pulling",)


def composer_guard_view(
    state: Mapping[str, Any],
    ctx: Mapping[str, Any],
    day: Optional[DateLike],
    catalog: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """What the guards of ``day`` take out of an ad-hoc session, from session
    PROPERTIES (never a load score):

    - ``exclude_ids``: removed from the pool before anyone picks — finger-hard
      exercises on a NO-finger-max day; front-lever variants on a NO-heavy-pull
      day; and, for the deterministic builder only (``builder_exclude_ids``),
      the weighted pulls whose catalog scheme would land ≥ 85 % 1RM;
    - ``heavy_pull_check``: the LLM path re-checks every composed weighted pull
      at ITS reps after validation (``drop_heavy_pulls``);
    - ``dropped``: one human-readable line per family removed, with the reason,
      for the preview's audit trail.
    """
    g = day_guard(ctx, day) if ctx else None
    out: Dict[str, Any] = {"day": None, "finger_max_ok": True, "heavy_pull_ok": True, "hiit_ok": True,
                           "exclude_ids": [], "builder_exclude_ids": [], "heavy_pull_check": False,
                           "dropped": [], "reasons": {}, "pain_axes": []}
    day_d: Optional[date] = None
    if day is not None:
        day_d = _as_date(day)
    elif ctx and ctx.get("as_of"):
        day_d = _as_date(ctx["as_of"])
    # A297 review: an active A295 pain block (score ≥ 2) on an axis makes the
    # day a NO-max day on that axis, guard horizon or not — the anchored-load
    # reduction alone never stopped the builder from picking campus / max
    # hangs, whose loads are not anchored.
    pain = {axis: pain_for(state, axis, day_d) for axis in (AXIS_FINGER, AXIS_PULLING)} if day_d else {}
    pain = {a: p for a, p in pain.items() if p is not None}
    if g is None and not pain:
        return out
    out["day"] = g["date"] if g is not None else day_d.isoformat()
    out["finger_max_ok"] = bool(g.get("finger_max_ok")) if g is not None else True
    out["heavy_pull_ok"] = bool(g.get("heavy_pull_ok")) if g is not None else True
    out["hiit_ok"] = bool(g.get("hiit_ok")) if g is not None else True
    finger_why = _codes_en(g.get("finger_codes") or []) if g is not None else ""
    pull_why = _codes_en(g.get("pull_codes") or []) if g is not None else ""
    for axis, p in sorted(pain.items()):
        txt = f"pain {p.get('site')} {p.get('score')}/3 until {p.get('until')}"
        out["pain_axes"].append(axis)
        if axis == AXIS_FINGER:
            out["finger_max_ok"] = False
            finger_why = "; ".join(x for x in (finger_why, txt) if x)
        else:
            out["heavy_pull_ok"] = False
            pull_why = "; ".join(x for x in (pull_why, txt) if x)
    excl: set = set()
    if not out["finger_max_ok"]:
        out["reasons"]["finger"] = finger_why
        ids = {i for i in _finger_hard_ids() if i in catalog}
        ids |= _max_intensity_ids(catalog, _FINGER_DOMAINS)
        excl |= ids
        if ids:
            out["dropped"].append(f"guard: max finger work left out — {finger_why}")
    builder_extra: set = set()
    if not out["heavy_pull_ok"]:
        out["reasons"]["pull"] = pull_why
        fl = front_lever_ids(catalog)
        # A297 review: a max-intensity bodyweight pull (one-arm pull-up) is a
        # ≥85% pulling effort too, even without an anchored load to check.
        max_pulls = _max_intensity_ids(catalog, _PULLING_DOMAINS)
        excl |= fl | max_pulls
        if fl:
            out["dropped"].append(f"guard: front lever left out — {pull_why}")
        if max_pulls:
            out["dropped"].append(f"guard: max-intensity pulls left out ({', '.join(sorted(max_pulls))}) — "
                                  f"{pull_why}")
        out["heavy_pull_check"] = True
        for eid in sorted(_pulling_max_ids()):
            if eid not in catalog:
                continue
            pct = heavy_pull_pct(state, eid, out["day"])
            if pct is not None and pct >= rp.HEAVY_PULL_PCT_1RM:
                builder_extra.add(eid)
    out["exclude_ids"] = sorted(excl)
    out["builder_exclude_ids"] = sorted(excl | builder_extra)
    return out


def drop_heavy_pulls(
    state: Mapping[str, Any],
    exercises: List[Dict[str, Any]],
    view: Mapping[str, Any],
) -> List[str]:
    """Remove, in place, the composed weighted pulls that land ≥ 85 % 1RM at
    their own sets/reps on a NO-heavy-pull day. Returns the ``dropped`` lines.
    Untested athletes are not verifiable and keep the line (their load is the
    remembered working load, unchanged by A297)."""
    if not view.get("heavy_pull_check") or not view.get("day"):
        return []
    pulls = _pulling_max_ids()
    ids = [str(e.get("exercise_id")) for e in exercises]
    dropped: List[str] = []
    keep: List[Dict[str, Any]] = []
    for e in exercises:
        eid = str(e.get("exercise_id"))
        if eid in pulls:
            pct = heavy_pull_pct(state, eid, view["day"], sets=e.get("sets"), reps=e.get("reps"),
                                 session_exercise_ids=ids)
            if pct is not None and pct >= rp.HEAVY_PULL_PCT_1RM:
                dropped.append(f"{eid}: guard — {round(pct * 100)}% of 1RM on a no-heavy-pull day "
                               f"({(view.get('reasons') or {}).get('pull') or 'recovery guard'})")
                continue
        keep.append(e)
    exercises[:] = keep
    return dropped


__all__ = [
    "VERSION", "FINGER_GAP_H", "RETEST_BLOCK_H", "PULL_TEST_BLOCK_H", "HEAVY_PULL_MAX_PER_7D",
    "OVERUSED_MIN", "VARIETY_WEEKS",
    "ATHLETE_PLAN_PATH", "NOTES_BEGIN", "NOTES_END",
    "build_athlete_context", "render_text", "extract_plan_notes", "load_exercise_catalog",
    "key_requirements_for", "key_matches", "WARMUP_TECHNIQUE_DRILLS",
    "render_coach_block", "render_composer_block", "day_guard", "composer_guard_view",
    "drop_heavy_pulls", "front_lever_ids", "COACH_BLOCK_MAX_CHARS", "COMPOSER_BLOCK_MAX_CHARS",
    "athlete_is_tested", "finger_hard_session_ids", "cap_finger_hard", "MAX_FINGER_HARD_PER_SESSION",
    "MAX_FINGER_HARD_PER_SESSION_LOW_ENERGY",
]
