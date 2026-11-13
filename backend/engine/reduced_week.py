"""A328 (b) — D288 R3-b: the reduced week on a trigger, as an ALERT only.

Inside an 11–14 week cycle there is no calendar unload (D288 §Q3: the 4–6
week cadence is practice, not evidence; one week of cessation costs strength).
One optional reduced week is SUGGESTED, only on a trigger:

- ``very_hard_7d`` — at least ``VERY_HARD_MIN`` sessions rated ``very_hard``
  (``session_completion_log[].difficulty``) in the ``VERY_HARD_WINDOW_D`` days
  up to today;
- ``pain_block`` — a pain block (``progression_counters.pain_blocks``, written
  by R4) active today with score ≥ 2, on any site — the reading of
  ``anchored_load.pain_for``;
- ``athlete_request`` — the athlete asked for it (the caller says so:
  ``requested=True``; only the coach does, there is no app path — R3-c is out
  of scope, decided 2026-11-13).

It stays silent (``skipped``) when:

- ``recent_taper`` — an A281 trip taper window [T−14, T−1] fell in the
  ``TAPER_LOOKBACK_D`` days up to today (or runs today): the athlete has just
  had a reduced block;
- ``deload_soon`` — the suggested week, or the current one, is the terminal
  deload (it already is the reduced week, A328).

The shape it proposes is the deload form (``macrocycle_v1.DELOAD_*``): same
climbing days, sets × 0.5, the phase's finger key as one exposure at the
working load −10 %, the limit short or technique, power endurance easy, no
test. Nothing here writes or applies anything (A301 / B369: after a user
action the engine only alerts). Pure and deterministic: no clock, ``today`` is
an argument.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional

#: ENGINEERING CONSTANTS (D288 §Q3 R3, no climbing evidence).
VERY_HARD_MIN = 2
VERY_HARD_WINDOW_D = 7
PAIN_MIN_SCORE = 2
#: "a trip taper fell within the previous 5 weeks".
TAPER_LOOKBACK_D = 35

REASON_VERY_HARD = "very_hard_7d"
REASON_PAIN = "pain_block"
REASON_REQUEST = "athlete_request"
SKIP_TAPER = "recent_taper"
SKIP_DELOAD = "deload_soon"

#: The shape of the reduced week (data for the coach / a future card).
FORM: Dict[str, Any] = {
    "same_climbing_days": True,
    "sets_factor": 0.5,
    "finger": "one exposure, 2-3 sets at the phase working load -10 %, >= 3 s in reserve",
    "limit": "short, or a flash-level technique session",
    "power_endurance": "none (easy climbing)",
    "tests": "none",
    "to_failure": "none",
}


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def very_hard_sessions(state: Mapping[str, Any], today: date) -> List[Dict[str, Any]]:
    """The sessions rated ``very_hard`` in the window up to ``today`` (one row
    per date + session; a skipped row never counts)."""
    lo = today - timedelta(days=VERY_HARD_WINDOW_D - 1)
    seen: Dict[tuple, Dict[str, Any]] = {}
    for row in state.get("session_completion_log") or []:
        if not isinstance(row, Mapping) or row.get("difficulty") != "very_hard" or row.get("status") == "skipped":
            continue
        d = _as_date(row.get("date"))
        if d is None or not (lo <= d <= today):
            continue
        key = (d.isoformat(), str(row.get("session_id") or ""))
        seen.setdefault(key, {"date": key[0], "session_id": row.get("session_id")})
    return [seen[k] for k in sorted(seen)]


def active_pain_blocks(state: Mapping[str, Any], today: date) -> List[Dict[str, Any]]:
    """Pain blocks active on ``today`` with score ≥ PAIN_MIN_SCORE, any site."""
    blocks = (state.get("progression_counters") or {}).get("pain_blocks") or {}
    if not isinstance(blocks, Mapping):
        return []
    out = []
    for site in sorted(blocks):
        b = blocks[site]
        if not isinstance(b, Mapping):
            continue
        start, until = _as_date(b.get("from")), _as_date(b.get("until"))
        try:
            score = int(float(b.get("score") or 0))
        except (TypeError, ValueError):
            score = 0
        if start is None or until is None or not (start <= today <= until) or score < PAIN_MIN_SCORE:
            continue
        out.append({"site": site, "score": score, "from": start.isoformat(), "until": until.isoformat()})
    return out


def recent_tapers(state: Mapping[str, Any], today: date) -> List[Dict[str, Any]]:
    """Trips whose A281 taper window [T−14, T−1] touches the last
    TAPER_LOOKBACK_D days up to today (a taper running today included)."""
    from backend.engine.macrocycle_v1 import TAPER_TOTAL_DAYS

    lo = today - timedelta(days=TAPER_LOOKBACK_D)
    out = []
    for trip in state.get("trips") or []:
        if not isinstance(trip, Mapping):
            continue
        t = _as_date(trip.get("start_date"))
        if t is None:
            continue
        w_start, w_end = t - timedelta(days=TAPER_TOTAL_DAYS), t - timedelta(days=1)
        if w_start <= today and w_end >= lo:
            out.append({"trip": trip.get("name"), "start_date": t.isoformat(),
                        "taper_from": w_start.isoformat(), "taper_to": w_end.isoformat()})
    return out


def _phase_of_week(state: Mapping[str, Any], monday: date) -> Optional[str]:
    from backend.engine.macro_position import position_on

    pos = position_on(state.get("macrocycle"), monday)
    return (pos or {}).get("phase_id")


def suggestion(state: Mapping[str, Any], today: Any, *, requested: bool = False) -> Dict[str, Any]:
    """Whether a reduced week should be SUGGESTED to the athlete, and why.

    Returns ``{suggested, week_start, reasons[], skipped, detail, form}``:
    ``reasons`` lists the triggers met (``very_hard_7d`` | ``pain_block`` |
    ``athlete_request``), ``skipped`` the reason a met trigger is not
    suggested (``recent_taper`` | ``deload_soon``) or None. ``week_start`` is
    the first Monday on or after ``today``. Never writes.
    """
    td = _as_date(today)
    if td is None:
        raise ValueError(f"reduced_week.suggestion: invalid today {today!r}")
    week_start = td + timedelta(days=(7 - td.weekday()) % 7)
    vh = very_hard_sessions(state, td)
    pain = active_pain_blocks(state, td)
    reasons: List[str] = []
    if len(vh) >= VERY_HARD_MIN:
        reasons.append(REASON_VERY_HARD)
    if pain:
        reasons.append(REASON_PAIN)
    if requested:
        reasons.append(REASON_REQUEST)
    tapers = recent_tapers(state, td)
    this_monday = td - timedelta(days=td.weekday())
    deload = any(_phase_of_week(state, m) == "deload" for m in sorted({this_monday, week_start}))
    skipped: Optional[str] = None
    if reasons:
        if deload:
            skipped = SKIP_DELOAD
        elif tapers:
            skipped = SKIP_TAPER
    return {
        "version": 1,
        "source": "a328",
        "as_of": td.isoformat(),
        "suggested": bool(reasons) and skipped is None,
        "week_start": week_start.isoformat(),
        "reasons": reasons,
        "skipped": skipped,
        "detail": {"very_hard": vh, "pain_blocks": pain, "tapers": tapers},
        "form": dict(FORM),
    }


#: The athlete-facing sentence of each reason (English, the app's language;
#: the coach renders its own).
REASON_TEXT: Dict[str, str] = {
    REASON_VERY_HARD: "two sessions rated very hard in the last 7 days",
    REASON_PAIN: "an active pain block",
    REASON_REQUEST: "you asked for it",
}


def alert_text(s: Optional[Mapping[str, Any]]) -> Optional[str]:
    """One sentence for a future card / the coach, or None when not suggested."""
    if not s or not s.get("suggested"):
        return None
    why = " and ".join(REASON_TEXT.get(r, r) for r in s.get("reasons") or [])
    return (f"Consider a reduced week from {s.get('week_start')} ({why}): same climbing days, half the sets, "
            "one finger exposure at your working load minus 10 %, no intervals, no tests. Nothing changes "
            "in your plan unless you decide it.")
