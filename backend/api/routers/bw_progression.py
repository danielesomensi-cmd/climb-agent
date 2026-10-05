"""A298 — bodyweight ladder levels: view, manual level, custom promotion tap.

- ``GET /api/bw-progression?date=`` — every family with the athlete's level,
  dose of the day, pending promotion and last outcome; technique ladders.
- ``PUT /api/bw-progression/{family}`` — settings "down" / "up" (source
  ``user_edit``). More than one level above the current one needs
  ``confirm: true`` (409 otherwise). Lower-back levels are allowed here: this
  is the explicit edit R12 reserves them for.
- ``POST /api/bw-progression/{family}/promotion`` — the custom-session
  proposal card: ``accept`` moves the entry up (pending promotion) and
  rewrites the 'ladder' rows of that family below the new level in the given
  custom session and in its not-yet-played week-plan slots from ``date`` on;
  decline clears the proposal. Past / done / skipped sessions are never
  touched.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.api.deps import get_user_id, load_state, require_active_subscription, save_state
from backend.engine import bw_progression as bwp

router = APIRouter(prefix="/api/bw-progression", tags=["bw-progression"])


def _day(value: Optional[str]) -> str:
    if not value:
        return _date.today().isoformat()
    try:
        return _date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date: {value!r} — expected YYYY-MM-DD")


class LevelRequest(BaseModel):
    level_idx: int = Field(ge=0, le=20)
    confirm: bool = False
    date: Optional[str] = None


class PromotionRequest(BaseModel):
    accept: bool
    date: Optional[str] = None
    custom_session_id: Optional[str] = Field(default=None, max_length=64)


@router.get("", dependencies=[Depends(require_active_subscription)])
def get_levels(date: Optional[str] = Query(None), user_id: Optional[str] = Depends(get_user_id)):
    state = load_state(user_id)
    return bwp.ladder_view(state, _day(date))


@router.put("/{family}", dependencies=[Depends(require_active_subscription)])
def put_level(family: str, req: LevelRequest, user_id: Optional[str] = Depends(get_user_id)):
    state = load_state(user_id)
    day = _day(req.date)
    try:
        entry = bwp.set_level(state, family, req.level_idx, day, confirm=req.confirm)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    save_state(state, user_id)
    return {"family": family, "entry": {k: v for k, v in entry.items() if k != "_prev"},
            "view": bwp.ladder_view(state, day)}


@router.post("/{family}/promotion", dependencies=[Depends(require_active_subscription)])
def post_promotion(family: str, req: PromotionRequest, user_id: Optional[str] = Depends(get_user_id)):
    state = load_state(user_id)
    day = _day(req.date)
    try:
        entry = bwp.resolve_promotion(state, family, accept=req.accept, ref_date=day)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No ladder level for {family}")
    rewritten = 0
    if req.accept and req.custom_session_id:
        to = int(entry["level_idx"])
        for cs in state.get("custom_sessions") or []:
            if isinstance(cs, dict) and cs.get("id") == req.custom_session_id:
                rewritten += bwp.rewrite_ladder_rows(cs.get("exercises"), family, to, day)
        sid = f"custom_{req.custom_session_id}"
        for plan in list((state.get("week_plans") or {}).values()) + [state.get("current_week_plan")]:
            for week in (plan or {}).get("weeks") or []:
                for d in week.get("days") or []:
                    if str(d.get("date") or "") < day:
                        continue
                    for s in d.get("sessions") or []:
                        if s.get("session_id") == sid and s.get("status") not in ("done", "skipped"):
                            rewritten += bwp.rewrite_ladder_rows(s.get("exercises"), family, to, day)
    save_state(state, user_id)
    return {"family": family, "accepted": req.accept, "rows_rewritten": rewritten,
            "entry": {k: v for k, v in entry.items() if k != "_prev"}}
