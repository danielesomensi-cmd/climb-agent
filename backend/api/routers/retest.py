"""A320 — decline or postpone a retest of the retest policy.

- ``POST /api/retest/decline`` — "not this test" (``kind: decline``) or "not
  before ``until``" (``kind: postpone``) for the PENDING test of one axis (the
  ``next_test`` of ``retest_status``). Stores the record (``retest_declines``),
  removes the ENGINE's planned tests of the axis dated from today on — a
  combined test is both axes' test: the regeneration re-places the other axis
  alone — and marks their weeks stale, so the next GET /api/week regenerates
  them under the decline; so is the cached week the test now belongs to (the
  week of a postpone's ``until``, the next trigger of another kind) when it
  was generated without it. The athlete's own planned tests (moved, forced,
  quick-added) are never removed: ``kept_user_owned_tests`` names them (the
  coach removes them explicitly through /api/replanner/events, dry run first).
- ``DELETE /api/retest/decline/{axis}`` — undo: removes the axis' stored
  records, takes out the engine's tests placed under a postpone (trigger
  ``postponed``: nothing backs them any more) and marks stale the weeks
  generated under the records and the weeks it took a test from, so the next
  GET /api/week places the test again where the policy wants it. An implicit
  decline (the athlete removed or replaced the test in a week's plan) is not
  undone here: the test goes back with an explicit add.

Both: ``dry_run`` runs everything on a copy and writes nothing (allowed while
the plan is paused); a real write refuses a paused plan (409), takes the
per-user write lock (B371) and saves once. Neither ever touches a past or
played session: "today" is the later of the server's day and the athlete's
(``today`` — body of the POST, query of the DELETE — clamped to ±1 day by
``week._client_today``): a test dated the athlete's yesterday is past even
when the server (UTC) still calls it today.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import (
    STALE_KEY, assert_plan_not_paused, get_user_id, load_state, mark_weeks_stale, require_active_subscription,
    save_state,
)
from backend.api.plan_revision import serialized_by_user, stamp_revision, stored_plan_for
from backend.api.routers.week import _client_today, _compute_retest_status
from backend.engine import retest_declines as rd
from backend.engine import retest_policy as rp

router = APIRouter(prefix="/api/retest", tags=["retest"])


class DeclineRequest(BaseModel):
    axis: Literal["finger", "pulling"]
    kind: Literal["decline", "postpone"] = "decline"
    until: Optional[date] = None
    reason: Literal["fatigue", "injury", "illness", "travel", "schedule", "not_needed", "other"]
    note: Optional[str] = Field(default=None, max_length=rd.NOTE_MAX_CHARS)
    # The client's reading of the pending trigger (409 trigger_mismatch when
    # the plan moved on since it was shown).
    trigger: Optional[str] = Field(default=None, max_length=40)
    source: Literal["app", "coach", "cli"] = "app"
    dry_run: bool = False
    today: Optional[str] = None


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _mark_stale(state: dict, week_start: str) -> list:
    """Flag one week stale (B369, server's today); the keys flagged."""
    marked = mark_weeks_stale(state, only=week_start)
    if not marked and (stored_plan_for(state, week_start) or {}).get(STALE_KEY):
        marked = [week_start]  # a week stored only as current_week_plan
    return marked


@router.post("/decline", dependencies=[Depends(require_active_subscription)])
@serialized_by_user
def decline(req: DeclineRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Decline or postpone the pending test of one axis (A320)."""
    state = load_state(user_id)
    if not req.dry_run:
        assert_plan_not_paused(state)  # A223 — a dry run only answers "what would happen"
    work = deepcopy(state) if req.dry_run else state
    server_today = datetime.now().date()
    local_today = date.fromisoformat(_client_today(req.today))
    status = _compute_retest_status(work, user_id) or {}
    finger_device = (work.get("preferences") or {}).get("finger_training_device")
    try:
        rec = rd.build_record(
            work, req.axis, status_row=(status.get("axes") or {}).get(req.axis), today=server_today,
            today_local=local_today, kind=req.kind, until=req.until, reason=req.reason, note=req.note,
            source=req.source, trigger=req.trigger,
        )
    except rd.DeclineError as e:
        raise _error(409 if e.code in rd.CONFLICT_CODES else 422, e.code, e.message)
    replaced = rd.upsert(work, rec, today=server_today, finger_device=finger_device)
    # Never a test the athlete already lived: from the later of the two todays.
    rows = rd.planned_tests(work, req.axis, since=max(server_today, local_today))
    removed = rd.drop_engine_tests(work, rows)
    stale: list = []
    for week_start in sorted({r["week_start"] for r in removed}):
        plan = stored_plan_for(work, week_start)
        if plan is not None:
            # B371: the week changed — a client holding the old copy gets a 409,
            # also when the week was already stale (no bump from the flag then).
            stamp_revision(plan, plan)
        stale.extend(_mark_stale(work, week_start))
    # The cached week the test now belongs to (a postpone's `until`, the next
    # trigger of another kind) was generated without it: flagged too, or the
    # test would wait for the first week generated later.
    reopen = rd.week_to_reopen(work, req.axis, today=server_today, finger_device=finger_device)
    if reopen is not None:
        stale.extend(_mark_stale(work, reopen))
    if not req.dry_run:
        save_state(work, user_id)
    return {
        "dry_run": req.dry_run,
        "decline": rec,
        "replaced": replaced,
        "tests_removed": removed,
        "kept_user_owned_tests": [{k: r[k] for k in ("week_start", "date", "slot", "session_id")}
                                  for r in rows if r["user_owned"]],
        "weeks_marked_stale": sorted(set(stale)),
        "retest_status": _compute_retest_status(work, user_id),
    }


@router.delete("/decline/{axis}", dependencies=[Depends(require_active_subscription)])
@serialized_by_user
def undecline(axis: str, dry_run: bool = False, today: Optional[str] = None,
              user_id: Optional[str] = Depends(get_user_id)):
    """Undo the stored declines of one axis (A320)."""
    if axis not in rp.RETEST_AXES:
        raise _error(422, "unknown_axis", f"Unknown axis {axis!r}: expected finger or pulling.")
    state = load_state(user_id)
    if not dry_run:
        assert_plan_not_paused(state)  # A223
    work = deepcopy(state) if dry_run else state
    removed = rd.remove(work, axis)
    if not removed:
        raise _error(404, "no_decline", f"No declined or postponed {axis} test to undo.")
    server_today = datetime.now().date()
    local_today = date.fromisoformat(_client_today(today))
    # A320 review: a test placed under the postpone (trigger `postponed`) has
    # nothing behind it any more — the engine's ones go, from the later of the
    # two todays (never a past session), and their weeks are regenerated.
    rows = rd.tests_placed_under_postpone(work, axis, since=max(server_today, local_today))
    dropped = rd.drop_engine_tests(work, rows)
    stale: list = []
    for week_start in sorted({r["week_start"] for r in dropped}):
        plan = stored_plan_for(work, week_start)
        if plan is not None:
            stamp_revision(plan, plan)  # B371, as in POST
        stale.extend(_mark_stale(work, week_start))
    for week_start in rd.weeks_generated_under_decline(work, axis, since=server_today):
        stale.extend(_mark_stale(work, week_start))
    if not dry_run:
        save_state(work, user_id)
    return {
        "dry_run": dry_run,
        "removed": removed,
        "tests_removed": dropped,
        "kept_user_owned_tests": [{k: r[k] for k in ("week_start", "date", "slot", "session_id")}
                                  for r in rows if r["user_owned"]],
        "weeks_marked_stale": sorted(set(stale)),
        "retest_status": _compute_retest_status(work, user_id),
    }
