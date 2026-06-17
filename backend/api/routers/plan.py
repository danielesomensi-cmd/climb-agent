"""Plan pause / resume router (A223).

Implements Option B from the D246 audit:
- ``macrocycle.start_date`` is IMMUTABLE.
- A cumulative, whole-week (Monday-to-Monday) ``pause.offset_days`` shifts the
  *effective* anchor read only by the two forward consumers in ``deps.py``.
- ``end_date`` is extended by N on each resume.
- Completed / archived sessions are never mutated; the paused-week remnant is
  classified "paused" (neutral) at read time, not "missed".

State shape (on ``state["macrocycle"]["pause"]``)::

    {
      "active_since": ISO_date | null,   # set on pause, cleared on resume
      "offset_days": int,                # cumulative, multiple of 7, default 0
      "log": [ {"from": ISO_date, "to": ISO_date} ]  # closed intervals (display)
    }

The pause object is scoped inside the macrocycle, so ``start-new-cycle``
(fresh macrocycle dict) resets it and the log is archived with the old cycle.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import (
    compute_pause_offset,
    get_user_id,
    load_state,
    require_active_subscription,
    save_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plan", tags=["plan"])


def _get_macrocycle(state: Dict[str, Any]) -> Dict[str, Any]:
    mc = state.get("macrocycle")
    if not mc:
        raise HTTPException(status_code=422, detail="No macrocycle to pause/resume")
    return mc


def _week_has_user_edits(plan: Dict[str, Any]) -> bool:
    """True if any session in the plan was user-edited (B153b ``_user_edited``)
    or quick-added/completed — i.e. content the user would lose on a plain
    regenerate. Future weeks beyond the pause-start week have no real completed
    sessions, so this is effectively "did the user customize this week"."""
    for week in (plan.get("weeks") or []):
        for day in (week.get("days") or []):
            for s in (day.get("sessions") or []):
                if s.get("_user_edited") or s.get("status") in ("done", "skipped"):
                    return True
    return False


def _shift_plan_dates(plan: Dict[str, Any], n_days: int) -> Dict[str, Any]:
    """Return *plan* with its ``start_date`` and every ``days[].date`` shifted
    forward by ``n_days``. Mutates in place and returns it."""
    def _add(iso: str) -> str:
        return (datetime.strptime(iso, "%Y-%m-%d").date() + timedelta(days=n_days)).isoformat()

    if isinstance(plan.get("start_date"), str):
        try:
            plan["start_date"] = _add(plan["start_date"])
        except ValueError:
            pass
    for week in (plan.get("weeks") or []):
        for day in (week.get("days") or []):
            if isinstance(day.get("date"), str):
                try:
                    day["date"] = _add(day["date"])
                except ValueError:
                    pass
    return plan


def _shift_future_weeks(state: Dict[str, Any], active_since: str, n_days: int) -> Dict[str, Any]:
    """On resume with N>0: shift only weeks strictly AFTER the pause-start week.

    - keys <= Monday(active_since): immutable (completed/past + the paused-week
      remnant) → left untouched. The remnant's undone sessions are classified
      "paused" at read time (macrocycle_archive), never rewritten.
    - keys > Monday(active_since): genuinely-future cached weeks (no real
      completed sessions). User-edited → shift dates +N and rekey (preserve
      edits, stays phase-consistent because +N matches the anchor shift).
      Otherwise → drop (regenerated lazily at the new effective anchor).

    Returns a small report dict for the resume response.
    """
    p = datetime.strptime(active_since, "%Y-%m-%d").date()
    freeze_monday = (p - timedelta(days=p.weekday())).isoformat()
    week_plans = state.get("week_plans") or {}
    new_plans: Dict[str, Any] = {}
    shifted, dropped = 0, 0
    for k, plan in week_plans.items():
        if not isinstance(k, str) or k <= freeze_monday:
            new_plans[k] = plan
            continue
        if _week_has_user_edits(plan):
            new_key = (datetime.strptime(k, "%Y-%m-%d").date() + timedelta(days=n_days)).isoformat()
            new_plans[new_key] = _shift_plan_dates(plan, n_days)
            shifted += 1
        else:
            dropped += 1  # not carried over → regenerated on demand
    state["week_plans"] = new_plans

    # Legacy single-pointer: if it pointed at a now-shifted/dropped future week,
    # clear it so the next read regenerates against the new anchor.
    cwp = state.get("current_week_plan")
    if cwp and isinstance(cwp.get("start_date"), str) and cwp["start_date"] > freeze_monday:
        state["current_week_plan"] = None
        state.pop("_prev_week_plan", None)
    return {"weeks_shifted": shifted, "weeks_dropped": dropped}


@router.post("/pause", dependencies=[Depends(require_active_subscription)])
def pause_plan(user_id: Optional[str] = Depends(get_user_id)):
    """Pause the active plan. Records ``pause.active_since = today``.
    Idempotent: a second call while already paused is a no-op."""
    state = load_state(user_id)
    mc = _get_macrocycle(state)
    pause = mc.setdefault("pause", {"active_since": None, "offset_days": 0, "log": []})
    pause.setdefault("offset_days", 0)
    pause.setdefault("log", [])

    if pause.get("active_since"):
        return {
            "paused": True,
            "active_since": pause["active_since"],
            "offset_days": pause["offset_days"],
        }

    today = date.today().isoformat()
    pause["active_since"] = today
    save_state(state, user_id)
    logger.info("A223: plan paused user=%s since=%s", user_id, today)
    return {"paused": True, "active_since": today, "offset_days": pause["offset_days"]}


@router.post("/resume", dependencies=[Depends(require_active_subscription)])
def resume_plan(user_id: Optional[str] = Depends(get_user_id)):
    """Resume a paused plan. Computes the whole-week offset, extends ``end_date``,
    appends the closed interval to ``pause.log``, clears ``active_since`` and
    shifts future cached weeks. Idempotent: a no-op if not paused."""
    state = load_state(user_id)
    mc = _get_macrocycle(state)
    pause = mc.get("pause") or {}
    active_since = pause.get("active_since")
    if not active_since:
        return {"paused": False, "offset_days": int(pause.get("offset_days") or 0)}

    today = date.today().isoformat()
    n = compute_pause_offset(active_since, today)
    report = {"weeks_shifted": 0, "weeks_dropped": 0}

    if n > 0:
        pause["offset_days"] = int(pause.get("offset_days") or 0) + n
        end = mc.get("end_date")
        if end:
            try:
                mc["end_date"] = (
                    datetime.strptime(end, "%Y-%m-%d").date() + timedelta(days=n)
                ).isoformat()
            except ValueError:
                pass
        report = _shift_future_weeks(state, active_since, n)

    pause.setdefault("log", []).append({"from": active_since, "to": today})
    pause["active_since"] = None
    save_state(state, user_id)
    logger.info(
        "A223: plan resumed user=%s N=%dd offset=%dd %s",
        user_id, n, pause["offset_days"], report,
    )
    return {
        "paused": False,
        "offset_days": pause["offset_days"],
        "shifted_days": n,
        "end_date": mc.get("end_date"),
        **report,
    }
