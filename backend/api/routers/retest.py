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

- ``POST /api/retest/extend`` — B414 (B414-2) "Postpone the expiry": one
  button for both axes. A postpone (``kind: postpone``) of every covered axis
  to the SAME day, ``weeks`` (2 | 4 | 6, default 4) after the later of the
  athlete's today and the latest ``valid_until`` of those axes (never
  shortening one). Same record path as the decline endpoint (a postpone also
  extends the max's validity to its ``until``; with no pending test the record
  carries the trigger ``expiry``; a new postpone replaces the axis' active
  ones), one save for both axes. Repeatable with no total cap. Undo: the
  DELETE below, per axis.

- ``POST /api/retest/request`` — B414 (B414-3) "Do the test", per covered
  axis (default: every covered axis): a test already in the plan → nothing
  written, the answer names its day (``planned``) — a test only projected by
  the policy is not enough (it may be weeks away: the request brings it to
  the first day the guards allow); the
  macrocycle is over → nothing written, ``cycle_ended`` (the app opens "Start
  a new cycle", whose week 1 has the tests); otherwise a ``kind: request``
  record (``rd.build_request``) — the policy then schedules the test from the
  athlete's today, in every phase but the deload, on the first day the guards
  allow — and the cached week it now belongs to is flagged stale. A request
  ends the axis' declines and postpones (the athlete's latest word).

Every real write of a postpone appends a ``retest_postponed`` event (axis,
until, previous_until, trigger, source) to the user's event log (fail-soft:
the state is already saved).

All: ``dry_run`` runs everything on a copy and writes nothing (allowed while
the plan is paused); a real write refuses a paused plan (409), takes the
per-user write lock (B371) and saves once. Neither ever touches a past or
played session: "today" is the later of the server's day and the athlete's
(``today`` — body of the POST, query of the DELETE — clamped to ±1 day by
``week._client_today``): a test dated the athlete's yesterday is past even
when the server (UTC) still calls it today.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
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
from backend.engine import storage

logger = logging.getLogger(__name__)

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


class ExtendRequest(BaseModel):
    """B414: "Postpone the expiry" — both covered axes, ``weeks`` from the
    later of today and their latest ``valid_until``."""
    weeks: int = rp.EXTENSION_DEFAULT_WEEKS
    reason: Literal["fatigue", "injury", "illness", "travel", "schedule", "not_needed", "other"] = "other"
    note: Optional[str] = Field(default=None, max_length=rd.NOTE_MAX_CHARS)
    source: Literal["app", "coach", "cli"] = "app"
    dry_run: bool = False
    today: Optional[str] = None


class RequestTestRequest(BaseModel):
    """B414: "Do the test" — the covered axes in ``axes`` (default: all)."""
    axes: Optional[list[Literal["finger", "pulling"]]] = None
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


def _apply_record(work: dict, rec: dict, *, server_today: date, local_today: date,
                  finger_device: Optional[str]) -> dict:
    """Store *rec* (``rd.upsert``), take the engine's planned tests of its axis
    out from the later of the two todays, and flag the weeks to regenerate.
    In place on *work*; returns what the response reports."""
    axis = rec["axis"]
    replaced = rd.upsert(work, rec, today=server_today, finger_device=finger_device)
    # Never a test the athlete already lived: from the later of the two todays.
    rows = rd.planned_tests(work, axis, since=max(server_today, local_today))
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
    reopen = rd.week_to_reopen(work, axis, today=server_today, finger_device=finger_device)
    if reopen is not None:
        stale.extend(_mark_stale(work, reopen))
    return {
        "replaced": replaced,
        "tests_removed": removed,
        "kept_user_owned_tests": [{k: r[k] for k in ("week_start", "date", "slot", "session_id")}
                                  for r in rows if r["user_owned"]],
        "weeks_marked_stale": stale,
    }


def _log_postpones(user_id: Optional[str], recs: list) -> None:
    """B414: the append-only audit of every postpone written (fail-soft — the
    state is already saved; the record keeps ``previous_until`` anyway)."""
    for rec in recs:
        if rec.get("kind") != rp.DECLINE_KIND_POSTPONE:
            continue
        try:
            storage.append_event(user_id, {
                "event": "retest_postponed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "axis": rec.get("axis"), "until": rec.get("until"), "previous_until": rec.get("previous_until"),
                "trigger": rec.get("trigger"), "source": rec.get("source"),
            })
        except Exception:  # pragma: no cover - the event log never fails the write
            logger.warning("B414: retest_postponed event not written", exc_info=True)


@router.post("/decline", dependencies=[Depends(require_active_subscription)])
@serialized_by_user
def decline(req: DeclineRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Decline or postpone the pending test of one axis (A320; B414: a postpone
    also extends the max's validity, and needs no pending test)."""
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
    out = _apply_record(work, rec, server_today=server_today, local_today=local_today,
                        finger_device=finger_device)
    if not req.dry_run:
        save_state(work, user_id)
        _log_postpones(user_id, [rec])
    return {
        "dry_run": req.dry_run,
        "decline": rec,
        "replaced": out["replaced"],
        "tests_removed": out["tests_removed"],
        "kept_user_owned_tests": out["kept_user_owned_tests"],
        "weeks_marked_stale": sorted(set(out["weeks_marked_stale"])),
        "retest_status": _compute_retest_status(work, user_id),
    }


@router.post("/extend", dependencies=[Depends(require_active_subscription)])
@serialized_by_user
def extend(req: ExtendRequest, user_id: Optional[str] = Depends(get_user_id)):
    """B414 (B414-2): "Postpone the expiry" of both covered axes at once."""
    if req.weeks not in rp.EXTENSION_WEEKS:
        raise _error(422, "invalid_weeks", "Postpone the expiry by "
                     + ", ".join(str(w) for w in rp.EXTENSION_WEEKS) + " weeks.")
    state = load_state(user_id)
    if not req.dry_run:
        assert_plan_not_paused(state)  # A223
    work = deepcopy(state) if req.dry_run else state
    server_today = datetime.now().date()
    local_today = date.fromisoformat(_client_today(req.today))
    status = _compute_retest_status(work, user_id) or {}
    rows = {a: r for a, r in (status.get("axes") or {}).items() if r.get("covered")}
    if not rows:
        raise _error(422, "not_covered", "No tested max to postpone the expiry of.")
    finger_device = (work.get("preferences") or {}).get("finger_training_device")
    # One day for both axes, never shortening one: from the later of today and
    # their latest validity.
    base = max([local_today] + [date.fromisoformat(str(r.get("valid_until"))[:10])
                                for r in rows.values() if r.get("valid_until")])
    until = base + timedelta(weeks=req.weeks)
    recs: list = []
    for axis in rp.RETEST_AXES:
        if axis not in rows:
            continue
        try:
            recs.append(rd.build_record(
                work, axis, status_row=rows[axis], today=server_today, today_local=local_today,
                kind=rp.DECLINE_KIND_POSTPONE, until=until, reason=req.reason, note=req.note, source=req.source,
                # B414 review: the cap counts from the common base — the axis
                # tested first (earlier validity) would refuse 6 weeks.
                cap_from=base,
            ))
        except rd.DeclineError as e:
            raise _error(409 if e.code in rd.CONFLICT_CODES else 422, e.code, e.message)
    extensions: list = []
    removed: list = []
    kept: list = []
    stale: list = []
    for rec in recs:
        out = _apply_record(work, rec, server_today=server_today, local_today=local_today,
                            finger_device=finger_device)
        extensions.append({"axis": rec["axis"], "decline": rec, "replaced": out["replaced"],
                           "previous_until": rec.get("previous_until")})
        removed.extend(out["tests_removed"])
        kept.extend(r for r in out["kept_user_owned_tests"] if r not in kept)
        stale.extend(out["weeks_marked_stale"])
    if not req.dry_run:
        save_state(work, user_id)
        _log_postpones(user_id, recs)
    return {
        "dry_run": req.dry_run,
        "weeks": req.weeks,
        "until": until.isoformat(),
        "extensions": extensions,
        "tests_removed": removed,
        "kept_user_owned_tests": kept,
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


@router.post("/request", dependencies=[Depends(require_active_subscription)])
@serialized_by_user
def request_test(req: RequestTestRequest, user_id: Optional[str] = Depends(get_user_id)):
    """B414 (B414-3): "Do the test" — the athlete asks for the test of the
    covered axes now (see the module docstring)."""
    from backend.engine.macro_position import position_on

    state = load_state(user_id)
    if not req.dry_run:
        assert_plan_not_paused(state)  # A223
    work = deepcopy(state) if req.dry_run else state
    server_today = datetime.now().date()
    local_today = date.fromisoformat(_client_today(req.today))
    status = _compute_retest_status(work, user_id) or {}
    rows = status.get("axes") or {}
    wanted = list(dict.fromkeys(req.axes or [a for a in rp.RETEST_AXES if (rows.get(a) or {}).get("covered")]))
    if not wanted:
        raise _error(422, "not_covered", "No tested axis: the retest policy cannot schedule the test.")
    for axis in wanted:
        if not (rows.get(axis) or {}).get("covered"):
            raise _error(422, "not_covered", f"The {axis} axis is not scheduled by the retest policy "
                                             "(no test of that axis, or a loading pin).")
    axes_out: dict = {}
    for axis in wanted:
        nt = rows[axis].get("next_test")
        if nt and nt.get("date") and nt.get("source") == "planned":
            axes_out[axis] = {"action": "planned", "date": nt["date"], "session_id": nt.get("session_id")}
    if len(axes_out) == len(wanted):
        return {"dry_run": req.dry_run, "action": "already_planned", "axes": axes_out, "requests": [],
                "replaced": [], "weeks_marked_stale": [],
                "go_to": min(a["date"] for a in axes_out.values()), "retest_status": status}
    pos = position_on(dict(work.get("macrocycle") or {}), local_today.isoformat()) \
        if work.get("macrocycle") else None
    if not pos or pos.get("after_end"):
        # Nothing to place a test in: the next cycle opens with the tests.
        for axis in wanted:
            axes_out.setdefault(axis, {"action": "cycle_ended", "date": None, "session_id": None})
        return {"dry_run": req.dry_run, "action": "cycle_ended", "axes": axes_out, "requests": [],
                "replaced": [], "weeks_marked_stale": [], "go_to": None, "retest_status": status}
    finger_device = (work.get("preferences") or {}).get("finger_training_device")
    recs: list = []
    replaced: list = []
    stale: list = []
    for axis in wanted:
        if axis in axes_out:
            continue
        try:
            rec = rd.build_request(work, axis, status_row=rows[axis], today=local_today, source=req.source)
        except rd.DeclineError as e:
            raise _error(409 if e.code in rd.CONFLICT_CODES else 422, e.code, e.message)
        old = rd.upsert(work, rec, today=server_today, finger_device=finger_device)
        if old is not None:
            replaced.append(old)
        recs.append(rec)
    for rec in recs:
        # The cached week the test now belongs to was generated without it.
        reopen = rd.week_to_reopen(work, rec["axis"], today=server_today, finger_device=finger_device)
        if reopen is not None:
            stale.extend(_mark_stale(work, reopen))
    if not req.dry_run:
        save_state(work, user_id)
    after = _compute_retest_status(work, user_id) or {}
    for rec in recs:
        nt = ((after.get("axes") or {}).get(rec["axis"]) or {}).get("next_test") or {}
        axes_out[rec["axis"]] = {"action": "requested", "date": nt.get("date"), "session_id": nt.get("session_id"),
                                 "next_test_reason": None if nt else
                                 ((after.get("axes") or {}).get(rec["axis"]) or {}).get("next_test_reason")}
    dates = [a["date"] for a in axes_out.values() if a.get("date")]
    return {"dry_run": req.dry_run, "action": "requested", "axes": axes_out, "requests": recs,
            "replaced": replaced, "weeks_marked_stale": sorted(set(stale)),
            "go_to": min(dates) if dates else None, "retest_status": after}
