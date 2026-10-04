"""A288 (F0) — where a date falls in the macrocycle, as a pure function.

Before A288 the position in the macrocycle had one pause-aware definition,
``backend.api.deps.current_phase_and_week`` (A223), which reads
``date.today()`` internally — so engine code that needed the position *on a
given date* (a future session, a past test) either reimplemented it or called
into the API layer. Three train-harder analyses (R2 ``phase_context``, R3
``phase_position``, R7 ``phase_and_week_on``) were about to add three more
copies. This module is the single one; ``deps`` delegates to it.

Rules (identical to deps.py before A288 — parity is pinned by
``test_a288_macro_position.py``):

- ``effective_start = start_date + pause.offset_days`` (completed pauses).
- While a pause is open (``pause.active_since``), the position is frozen at
  ``active_since``: ``effective_on = min(active_since, on_date)``.
- Before the start → phase 0, week 0. Past the end → last phase, last week.

Pure: no ``date.today()``, no I/O, no ``backend.api`` import, so engine
modules (athlete context, retest policy, resolver) can use it without
FastAPI or storage.

Known divergence, documented and NOT fixed here (high-risk module, out of
F0 scope): ``progression_v1._get_current_phase_id`` ignores the A223 pause.
B364 replaces it on the anchored-load paths.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple, Union

DateLike = Union[date, str]


def _as_date(value: DateLike) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def effective_anchor(macrocycle: Dict[str, Any], today: DateLike) -> Tuple[date, date]:
    """Return ``(effective_start, effective_today)`` accounting for the A223 pause.

    Same contract as ``deps._effective_anchor`` with the date passed in.
    No pause → ``(start_date, today)`` exactly.
    """
    mc_start = datetime.strptime(macrocycle["start_date"], "%Y-%m-%d").date()
    pause = macrocycle.get("pause") or {}
    offset_days = int(pause.get("offset_days") or 0)
    effective_start = mc_start + timedelta(days=offset_days)
    eff_today = _as_date(today)
    active_since = pause.get("active_since")
    if active_since:
        try:
            frozen = datetime.strptime(active_since, "%Y-%m-%d").date()
            eff_today = min(frozen, eff_today)
        except ValueError:
            pass
    return effective_start, eff_today


def phase_and_week_on(macrocycle: Dict[str, Any], on_date: DateLike) -> Tuple[int, int]:
    """``(phase_index, week_within_phase)``, both 0-based, on ``on_date``.

    Same contract as ``deps.current_phase_and_week`` with the date passed in:
    before the start → ``(0, 0)``; past the end → last phase, last week;
    no phases → ``(0, 0)``.
    """
    phases = macrocycle.get("phases") or []
    if not phases:
        return (0, 0)

    mc_start, today = effective_anchor(macrocycle, on_date)
    cumulative_week = 0

    for pi, phase in enumerate(phases):
        duration = phase.get("duration_weeks", 1)
        phase_start = mc_start + timedelta(weeks=cumulative_week)
        phase_end = phase_start + timedelta(weeks=duration)
        if today < phase_end:
            weeks_into = max(0, (today - phase_start).days // 7)
            return (pi, min(weeks_into, duration - 1))
        cumulative_week += duration

    last = phases[-1]
    return (len(phases) - 1, last.get("duration_weeks", 1) - 1)


def position_on(macrocycle: Optional[Dict[str, Any]], on_date: DateLike) -> Optional[Dict[str, Any]]:
    """Rich, read-only description of the position on ``on_date``.

    Returns ``None`` when there is no usable macrocycle (no phases or no
    ``start_date``). Otherwise::

        {
          "phase_index": int,          # 0-based, == phase_and_week_on()[0]
          "phase_id": str,
          "week_in_phase": int,        # 0-based, == phase_and_week_on()[1]
          "phase_weeks": int,          # duration of that phase
          "abs_week": int,             # 1-based week of the macrocycle
          "total_weeks": int,
          "phase_start": "YYYY-MM-DD", # effective (pause-shifted) dates
          "phase_end": "YYYY-MM-DD",   # exclusive: first day after the phase
          "is_last_week_of_phase": bool,
          "next_phase_id": str | None,
          "before_start": bool,
          "after_end": bool,
          "paused": bool,              # an A223 pause is open
        }
    """
    if not macrocycle:
        return None
    phases = macrocycle.get("phases") or []
    if not phases or not macrocycle.get("start_date"):
        return None

    pi, wi = phase_and_week_on(macrocycle, on_date)
    mc_start, eff_on = effective_anchor(macrocycle, on_date)
    weeks_before = sum(int(p.get("duration_weeks", 1)) for p in phases[:pi])
    phase = phases[pi]
    duration = int(phase.get("duration_weeks", 1))
    phase_start = mc_start + timedelta(weeks=weeks_before)
    phase_end = phase_start + timedelta(weeks=duration)
    total_weeks = sum(int(p.get("duration_weeks", 1)) for p in phases)
    cycle_end = mc_start + timedelta(weeks=total_weeks)
    return {
        "phase_index": pi,
        "phase_id": phase.get("phase_id"),
        "week_in_phase": wi,
        "phase_weeks": duration,
        "abs_week": weeks_before + wi + 1,
        "total_weeks": total_weeks,
        "phase_start": phase_start.isoformat(),
        "phase_end": phase_end.isoformat(),
        "is_last_week_of_phase": wi == duration - 1,
        "next_phase_id": phases[pi + 1].get("phase_id") if pi + 1 < len(phases) else None,
        "before_start": eff_on < mc_start,
        "after_end": eff_on >= cycle_end,
        "paused": bool((macrocycle.get("pause") or {}).get("active_since")),
    }
