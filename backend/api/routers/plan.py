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
    mark_weeks_stale,
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


def _shift_future_weeks(state: Dict[str, Any], active_since: str, n_days: int) -> Dict[str, Any]:
    """On resume with N>0: the cached weeks from the current one on go stale.

    - keys <= Monday(active_since): immutable (completed/past + the paused-week
      remnant) → left untouched. The remnant's undone sessions are classified
      "paused" at read time (macrocycle_archive), never rewritten.
    - keys between the pause week and this Monday are past now → untouched.
    - keys >= this Monday: marked stale (B369). The next GET /api/week
      regenerates each one at the new effective anchor THROUGH the merge that
      keeps the user's sessions on the calendar date they were put on, and the
      user's removals. They used to be dropped (losing any custom / forced
      session the old edit check did not see) or, when edited, shifted +N
      days — moving the user's sessions to dates they never chose.

    Returns a small report dict for the resume response (``weeks_shifted`` /
    ``weeks_dropped`` stay, always 0, for older clients).
    """
    p = datetime.strptime(active_since, "%Y-%m-%d").date()
    freeze_monday = (p - timedelta(days=p.weekday())).isoformat()
    marked = mark_weeks_stale(state, from_monday=freeze_monday)
    marked = [k for k in marked if k > freeze_monday]
    state.pop("_prev_week_plan", None)
    return {"weeks_shifted": 0, "weeks_dropped": 0, "weeks_marked_stale": len(marked)}


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
    report = {"weeks_shifted": 0, "weeks_dropped": 0, "weeks_marked_stale": 0}

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
