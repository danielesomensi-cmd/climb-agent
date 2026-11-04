"""B413 (D1) — the archived weeks the bodyweight ladders read, ONE read per request.

The ladder seed (``bw_ladders.seed_levels``: the level of a family with no
persisted entry) reads the done sessions of the last 120 days. A221 moves a
past week to the cold store (``week_archive``) once it is older than the
previous Monday, so an engine call without the archive saw ~2 weeks of
history: feedback on a family that existed only in the archive found no base
and was lost (T2B 2026-10-26, back extension 2026-10-28), and the dose the
resolver showed was not the dose the feedback stepped from.

The engine stays pure — every ladder reader takes an optional
``archived_weeks`` (None = hot weeks only, the pre-B413 behaviour) — and this
module is the single place that loads it:

- :func:`load` / :func:`for_plan` — the weeks of the window for the dates a
  request works on. **No read** for an athlete the tested gate keeps out of
  the ladders, nor when every week of the window that could be archived is
  still hot. The window is Monday-aligned and the same for every reader
  (``bw_ladders.archive_window_start``), with an open end: the store only
  holds past weeks, so the open end costs nothing and every other consumer of
  the request (retest policy, key status) filters its own range out of it.
- :func:`read_range` — an archive range read served from a wider range
  already read in this request (B376 memo) when there is one: at most one
  archive range round-trip per request for a tested athlete.

Failure semantics: a read that does not need to persist anything gets the
recent-weeks view (``failed=True``; the caller must persist nothing derived
from it in that request — GET /week skips the B375 cache of played sessions).
A write that would freeze or consume a ladder dose (``write=True``) answers
503 before anything is written: a dose computed on half the history is never
stored for good. The client retries (feedback is idempotent).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, Mapping, Optional

from fastapi import HTTPException

from backend.engine import bw_ladders as _bl
from backend.engine import storage_memo

logger = logging.getLogger(__name__)

#: Open end of the ladder archive read (see the module docstring).
OPEN_END = "9999-12-31"
#: The storage read every archive range goes through (memo key name).
_RANGE_READ = "read_archived_weeks_in_range"
#: 503 body of a write that needs the archive while it cannot be read.
UNAVAILABLE_DETAIL = {
    "error": "archive_unavailable",
    "message": "Training history is temporarily unavailable — nothing was saved, please retry.",
}


@dataclass(frozen=True)
class LadderArchive:
    """``weeks``: the archived weeks to pass the engine (None = not needed,
    or not readable). ``failed``: the read was needed and failed — nothing
    derived from this request's ladder doses may be persisted."""

    weeks: Optional[Dict[str, Any]] = None
    failed: bool = False


NOT_NEEDED = LadderArchive()


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def read_range(user_id: Optional[str], start: str, end: str) -> Dict[str, Any]:
    """``storage.read_archived_weeks_in_range(user_id, start, end)``, served
    from a wider range already read in this request when there is one — the
    same weeks, without a second round-trip. Raises on a storage failure."""
    from backend.api import deps as _deps

    def _covers(args: Mapping[str, Any]) -> bool:
        return (args.get("user_id") == user_id
                and str(args.get("start")) <= start and str(args.get("end")) >= end)

    hit = storage_memo.find(_RANGE_READ, _covers)
    if hit is not storage_memo.MISSING:
        return {k: v for k, v in (hit or {}).items() if start <= str(k) <= end}
    return _deps._storage.read_archived_weeks_in_range(user_id, start, end)


def _hot_mondays(state: Mapping[str, Any]) -> set:
    hot = {str(k) for k in (state.get("week_plans") or {}).keys()}
    cur = state.get("current_week_plan")
    if isinstance(cur, Mapping) and cur.get("start_date"):
        hot.add(str(cur["start_date"])[:10])
    return hot


def needs_archive(state: Mapping[str, Any], refs: Iterable[Any], today: Optional[date] = None) -> bool:
    """True when a ladder read on ``refs`` (dates) can see the cold store: the
    tested gate is open on one of them and a week of the window that A221 may
    have archived (older than the previous Monday) is not hot."""
    days = sorted(d for d in (_as_date(r) for r in refs or ()) if d is not None)
    if not days or not state:
        return False
    lo_ref, hi_ref = days[0], days[-1]
    if not (_bl.tested_gate(state, lo_ref) or _bl.tested_gate(state, hi_ref)):
        return False
    today = today or date.today()
    # A221: only weeks before the previous Monday are ever archived.
    last = min(_monday(hi_ref), _monday(today) - timedelta(days=14))
    hot = _hot_mondays(state)
    wk = _bl.archive_window_start(lo_ref)
    while wk <= last:
        if wk.isoformat() not in hot:
            return True
        wk += timedelta(days=7)
    return False


def load(
    state: Optional[Mapping[str, Any]],
    user_id: Optional[str],
    refs: Iterable[Any],
    *,
    write: bool = False,
    today: Optional[date] = None,
) -> LadderArchive:
    """The archived weeks the ladders need on ``refs`` (the dates the request
    resolves, shows or logs). ``write``: the request freezes or consumes a
    ladder dose — a failed read raises 503 instead of falling back."""
    if not state:
        return NOT_NEEDED
    refs = [d for d in (_as_date(r) for r in refs or ()) if d is not None]
    today = today or date.today()
    try:
        need = needs_archive(state, refs, today)
    except Exception:  # a malformed state is read like an untested one
        logger.warning("B413: ladder archive check failed — hot weeks only", exc_info=True)
        need = False
    if not need:
        return NOT_NEEDED
    lo = _bl.archive_window_start(min(min(refs), today))
    try:
        weeks = read_range(user_id, lo.isoformat(), OPEN_END)
    except Exception:
        logger.warning("B413: archived weeks unavailable for the ladders (user=%s, write=%s)",
                       user_id, write, exc_info=True)
        if write:
            raise HTTPException(status_code=503, detail=dict(UNAVAILABLE_DETAIL))
        return LadderArchive(weeks=None, failed=True)
    return LadderArchive(weeks=weeks or {}, failed=False)


def plan_dates(plan: Optional[Mapping[str, Any]]) -> list:
    """Monday and Sunday of ``plan`` (the span its sessions resolve on)."""
    start = _as_date((plan or {}).get("start_date")) if isinstance(plan, Mapping) else None
    if start is None:
        return []
    return [start, start + timedelta(days=6)]


def for_plan(
    state: Optional[Mapping[str, Any]],
    user_id: Optional[str],
    plan: Optional[Mapping[str, Any]],
    *,
    write: bool = False,
    extra_refs: Iterable[Any] = (),
) -> LadderArchive:
    """:func:`load` for the week of ``plan`` (+ ``extra_refs``)."""
    refs = plan_dates(plan) + list(extra_refs or ())
    if not refs:
        return NOT_NEEDED
    return load(state, user_id, refs, write=write)


__all__ = ["LadderArchive", "NOT_NEEDED", "OPEN_END", "UNAVAILABLE_DETAIL", "read_range",
           "needs_archive", "load", "plan_dates", "for_plan"]
