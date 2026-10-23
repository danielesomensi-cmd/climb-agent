"""A320 — decline or postpone a retest of the retest policy (A289).

Daniele (or his coach, with his OK) says "not this test" or "not before date
X" for one axis, and no regeneration puts the test back until something new
justifies it. The policy reads the records (``retest_policy._axis_week_decision``:
a declined axis is ``skipped``, never uncovered); this module owns them.

State: top-level ``retest_declines`` (list), endpoint-owned like
``milestones`` / ``custom_sessions`` — written only by POST/DELETE
/api/retest/decline (``PUT /api/state`` refuses the key), read with
``state.get("retest_declines") or []``. An absent key = no declines (no
migration, ``schema_version`` unchanged). Record::

    {axis: finger|pulling, kind: decline|postpone,
     trigger,           # the pending trigger (legacy end_of_phase_slipped → end_of_phase)
     official_date,     # the official max the record applies to (a new test makes it inert)
     macrocycle_start,  # end_of_phase / cycle_start match only in this macrocycle
     until,             # postpone only: no test before this date (else None)
     reason,            # fatigue | injury | illness | travel | schedule | not_needed | other
     note,              # optional free text, ≤ 200 chars — stored only, never shown to the coach LLM
     declined_at,       # server ISO date
     source}            # app | coach | cli

Functions (pure, no I/O, deterministic — the caller passes every date):

- ``build_record`` — validate the request against the axis' live
  ``retest_status`` row; ``DeclineError`` (a ValueError) carries the code;
- ``upsert`` / ``remove`` — the stored list (``upsert`` prunes the records
  a newer test made inert, and a decline ends the axis' postpones);
- ``planned_tests`` / ``drop_engine_tests`` — the planned tests of an axis in
  the hot plans, and the removal of the engine's ones from ``week_plans[K]``
  AND the separate ``current_week_plan`` copy. No adaptation event is logged:
  a ``remove_session`` record would empty the slot for the regeneration
  (B382) and would itself read as the athlete's plan-edit decline;
- ``weeks_generated_under_decline`` — the weeks whose snapshot skipped the
  axis because of a stored decline (DELETE marks them stale);
- ``tests_placed_under_postpone`` — the planned tests PASS 3a placed with the
  trigger ``postponed`` (DELETE takes the engine's ones out: once the postpone
  is undone nothing backs them);
- ``week_to_reopen`` — the cached week the test now belongs to (a postpone's
  ``until``, the next trigger of another kind) when it was generated without
  it (POST marks it stale too).

The implicit plan-edit decline (a policy test the athlete removed or replaced
in a week) is derived from the plan by ``retest_policy.plan_edit_removal`` —
never stored here, and not undone by DELETE: the athlete puts the test back
with an explicit add (which lifts it).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from backend.engine import retest_policy as rp

DateLike = Union[date, str]

#: Closed set of the decline reasons (the code is all the coach prompt sees).
REASONS = rp.DECLINE_REASONS
#: Who asked: the app's button, the coach (with the athlete's OK), a script.
SOURCES = rp.DECLINE_SOURCES
NOTE_MAX_CHARS = 200

#: Codes of the requests that conflict with the state (409); every other
#: ``DeclineError`` is an invalid request (422).
CONFLICT_CODES = frozenset({"no_pending_retest", "trigger_mismatch"})


class DeclineError(ValueError):
    """An invalid decline request. ``code`` is the API's ``detail.code``."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _as_date(value: DateLike) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _record_key(rec: Mapping[str, Any]) -> Tuple[Any, ...]:
    """axis + official_date + trigger, + macrocycle_start for the week-bound
    kinds (the next cycle's end of phase / cycle start is another test)."""
    trigger = rp.normalize_trigger(rec.get("trigger"))
    mc = rec.get("macrocycle_start") if trigger in (rp.TRIGGER_END_OF_PHASE, rp.TRIGGER_CYCLE_START) else None
    return rec.get("axis"), str(rec.get("official_date") or "")[:10], trigger, mc


def active_postpone(state: Mapping[str, Any], axis: str, official_date: Optional[str]) -> Optional[Mapping[str, Any]]:
    """The postpone behind a pending ``postponed`` trigger: the active one with
    the latest ``until`` (the policy's own reading)."""
    return rp._active_postpone(rp.axis_declines(state, axis, {"date": official_date}))


def build_record(
    state: Mapping[str, Any],
    axis: str,
    *,
    status_row: Optional[Mapping[str, Any]],
    today: DateLike,
    reason: str,
    kind: str = rp.DECLINE_KIND_DECLINE,
    until: Optional[DateLike] = None,
    note: Optional[str] = None,
    source: str = "app",
    trigger: Optional[str] = None,
    today_local: Optional[DateLike] = None,
) -> Dict[str, Any]:
    """The record declining / postponing the PENDING test of ``axis``.

    ``status_row`` is ``retest_status(...)["axes"][axis]`` on the server's
    ``today`` (None when the axis has no row). ``today`` stamps
    ``declined_at``; ``today_local`` (the athlete's day, clamped by the
    caller; default ``today``) is the day ``until`` must come after.
    ``trigger`` is the client's assertion of the pending trigger.

    The pending trigger is the one of ``status_row.next_test`` (planned: the
    trigger PASS 3a stored; projected: the decision's). A pending
    ``postponed`` test is keyed on the postpone behind it (its trigger and
    macrocycle), so declining or postponing it again REPLACES that record.

    Raises :class:`DeclineError`: ``unknown_axis`` | ``invalid_kind`` |
    ``invalid_reason`` | ``invalid_source`` | ``note_too_long`` |
    ``invalid_until`` (postpone without ``until``, ``until`` with a decline,
    ``until`` not after today, or not after the pending test's own day — a
    postpone never brings a test forward) | ``not_covered`` (no tested
    official max the policy reads: untested, older than 90 days, loading pin) |
    ``until_after_expiry`` (after the axis' ``tested_until``) |
    ``no_pending_retest`` (no planned nor projected policy test) |
    ``trigger_mismatch``.
    """
    if axis not in rp.RETEST_AXES:
        raise DeclineError("unknown_axis", f"Unknown axis {axis!r}: expected finger or pulling.")
    if kind not in rp.DECLINE_KINDS:
        raise DeclineError("invalid_kind", f"Unknown kind {kind!r}: expected decline or postpone.")
    if reason not in REASONS:
        raise DeclineError("invalid_reason", f"Unknown reason {reason!r}: expected one of {', '.join(REASONS)}.")
    if source not in SOURCES:
        raise DeclineError("invalid_source", f"Unknown source {source!r}: expected one of {', '.join(SOURCES)}.")
    note = (str(note).strip() or None) if note is not None else None
    if note is not None and len(note) > NOTE_MAX_CHARS:
        raise DeclineError("note_too_long", f"The note is limited to {NOTE_MAX_CHARS} characters.")
    day = _as_date(today)
    local = _as_date(today_local) if today_local else day
    until_d: Optional[date] = None
    if kind == rp.DECLINE_KIND_POSTPONE:
        if until is None:
            raise DeclineError("invalid_until", "A postponed test needs the date it is postponed to (until).")
        try:
            until_d = _as_date(until)
        except (TypeError, ValueError):
            raise DeclineError("invalid_until", f"Invalid date {until!r}: expected YYYY-MM-DD.")
        if until_d <= local:
            raise DeclineError("invalid_until", "A test can only be postponed to a day after today.")
    elif until is not None:
        raise DeclineError("invalid_until", "A declined test takes no date: postpone it instead.")
    if not status_row or not status_row.get("covered"):
        raise DeclineError("not_covered", f"The {axis} axis is not scheduled by the retest policy "
                                          "(no tested max in the last 90 days).")
    tested_until = status_row.get("tested_until")
    if until_d is not None and tested_until and until_d.isoformat() > str(tested_until)[:10]:
        raise DeclineError("until_after_expiry", f"The tested max stops counting after {tested_until}: "
                                                 "postpone the test to that day at the latest.")
    nt = status_row.get("next_test") or {}
    pending = rp.normalize_trigger(nt.get("trigger"))
    if not nt or pending is None:
        raise DeclineError("no_pending_retest", f"No {axis} test of the retest policy is planned or due.")
    if trigger is not None and rp.normalize_trigger(trigger) != pending:
        raise DeclineError("trigger_mismatch", f"The pending {axis} test is the {pending} one, not {trigger}.")
    pending_day = str(nt.get("date") or "")[:10]
    if until_d is not None and pending_day and until_d.isoformat() <= pending_day:
        # A320 review: "not before X" with X on or before the test's own day
        # would bring a later test FORWARD (the postponed test is due from X).
        raise DeclineError("invalid_until", f"The pending {axis} test is on {pending_day}: "
                                            "postpone it to a later day.")
    official_date = str(status_row.get("test_date") or "")[:10]
    mc_start = (state.get("macrocycle") or {}).get("start_date")
    if pending == rp.TRIGGER_POSTPONED:
        prev = active_postpone(state, axis, official_date)
        if prev is not None and prev.get("trigger"):
            pending, mc_start = rp.normalize_trigger(prev["trigger"]), prev.get("macrocycle_start")
    return {
        "axis": axis,
        "kind": kind,
        "trigger": pending,
        "official_date": official_date,
        "macrocycle_start": mc_start,
        "until": until_d.isoformat() if until_d else None,
        "reason": reason,
        "note": note,
        "declined_at": day.isoformat(),
        "source": source,
    }


def upsert(
    state: Dict[str, Any],
    rec: Mapping[str, Any],
    *,
    today: DateLike,
    finger_device: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Store *rec*, replacing the record with the same key (axis +
    official_date + trigger, + macrocycle_start for end_of_phase /
    cycle_start). Records whose ``official_date`` is no longer their axis'
    official max on ``today`` (a newer test) are pruned.

    A320 review: a ``decline`` also ends the axis' active postpones — the
    athlete's latest word wins. The pending test is never before a postpone's
    ``until`` (the weeks before it have no test), so declining it declines the
    test the postpone had put off; kept, the postpone brought it back as
    ``postponed`` the moment the decline suppressed the natural trigger.

    Returns the record *rec* replaced — the one with the same key, else the
    postpone a decline ended — or None."""
    current = {}
    for axis in rp.RETEST_AXES:
        om = rp.axis_official(state, axis, today, finger_device=finger_device)
        current[axis] = om["date"] if om else None
    key = _record_key(rec)
    ends_postpones = rec.get("kind") == rp.DECLINE_KIND_DECLINE
    kept: List[Any] = []
    replaced: Optional[Dict[str, Any]] = None
    ended: Optional[Dict[str, Any]] = None
    for old in state.get(rp.DECLINES_KEY) or []:
        if not isinstance(old, Mapping) or str(old.get("official_date") or "")[:10] != current.get(old.get("axis")):
            continue  # inert: a newer test (or no max at all) on that axis
        if _record_key(old) == key:
            replaced = dict(old)
            continue
        if ends_postpones and old.get("axis") == rec.get("axis") and old.get("kind") == rp.DECLINE_KIND_POSTPONE:
            ended = dict(old)
            continue
        kept.append(old)
    kept.append(dict(rec))
    state[rp.DECLINES_KEY] = kept
    return replaced or ended


def remove(state: Dict[str, Any], axis: str) -> List[Dict[str, Any]]:
    """Remove every stored record of ``axis``; returns them. The key goes away
    with the last record (the state is then the one before any decline)."""
    recs = state.get(rp.DECLINES_KEY) or []
    removed = [dict(r) for r in recs if isinstance(r, Mapping) and r.get("axis") == axis]
    if removed:
        kept = [r for r in recs if not (isinstance(r, Mapping) and r.get("axis") == axis)]
        if kept:
            state[rp.DECLINES_KEY] = kept
        else:
            state.pop(rp.DECLINES_KEY, None)
    return removed


def _hot_plans(state: Mapping[str, Any]) -> List[Tuple[str, Mapping[str, Any]]]:
    """``(week_start, plan)`` of the hot week plans; ``current_week_plan`` only
    when its week is not in ``week_plans`` (as ``stimulus.iter_plan_days``)."""
    plans: Dict[str, Mapping[str, Any]] = {}
    for key, plan in (state.get("week_plans") or {}).items():
        if isinstance(plan, Mapping):
            plans[str(key)] = plan
    cur = state.get("current_week_plan")
    if isinstance(cur, Mapping) and cur.get("start_date") and str(cur["start_date"]) not in plans:
        plans[str(cur["start_date"])] = cur
    return sorted(plans.items())


def _days(plan: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [d for wk in plan.get("weeks") or [] if isinstance(wk, Mapping)
            for d in wk.get("days") or [] if isinstance(d, dict)]


def planned_tests(state: Mapping[str, Any], axis: str, *, since: DateLike) -> List[Dict[str, Any]]:
    """The planned tests of ``axis`` dated ≥ ``since`` in the hot week plans
    and the ``current_week_plan`` copy (one row per test):
    ``{week_start, date, slot, session_id, user_owned}``. A session of
    ``AXIS_TEST_SESSIONS_ALL[axis]`` (the combined test included), not done
    nor skipped. ``user_owned`` = ``user_owned.is_user_owned`` (moved, forced,
    quick-added…): those survive any regeneration and are never removed here."""
    from backend.engine.user_owned import is_user_owned

    sids = rp.AXIS_TEST_SESSIONS_ALL[axis]
    floor = _as_date(since).isoformat()
    rows: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    plans = list(_hot_plans(state))
    cur = state.get("current_week_plan")
    if isinstance(cur, Mapping) and cur.get("start_date"):
        # A copy of a hot week that diverged from it (legacy): its tests too.
        plans.append((str(cur["start_date"]), cur))
    for ws_key, plan in plans:
        for day in _days(plan):
            d = str(day.get("date") or "")[:10]
            if not d or d < floor:
                continue
            for s in day.get("sessions") or []:
                if not isinstance(s, Mapping) or s.get("session_id") not in sids:
                    continue
                if s.get("status") in ("done", "skipped"):
                    continue
                key = (ws_key, d, s.get("slot"), s.get("session_id"))
                rows.setdefault(key, {"week_start": ws_key, "date": d, "slot": s.get("slot"),
                                      "session_id": s.get("session_id"), "user_owned": is_user_owned(s)})
    return sorted(rows.values(), key=lambda r: (r["date"], str(r["slot"] or ""), str(r["session_id"])))


def _copies(state: Mapping[str, Any], week_start: str) -> List[Dict[str, Any]]:
    """Every stored copy of the week: ``week_plans[K]`` and the legacy
    ``current_week_plan`` when it is that week (``state_codec.unpack`` makes it
    an independent deep copy)."""
    out: List[Dict[str, Any]] = []
    plan = (state.get("week_plans") or {}).get(week_start)
    if isinstance(plan, dict):
        out.append(plan)
    cur = state.get("current_week_plan")
    if isinstance(cur, dict) and cur.get("start_date") == week_start and not any(cur is p for p in out):
        out.append(cur)
    return out


def _drop_from(plan: Dict[str, Any], row: Mapping[str, Any]) -> bool:
    from backend.engine.user_owned import is_user_owned

    for day in _days(plan):
        if str(day.get("date") or "")[:10] != row["date"]:
            continue
        sessions = day.get("sessions") or []
        for i, s in enumerate(sessions):
            if (isinstance(s, Mapping) and s.get("session_id") == row["session_id"] and s.get("slot") == row["slot"]
                    and s.get("status") not in ("done", "skipped") and not is_user_owned(s)):
                del sessions[i]
                if not sessions:
                    # As replanner's remove_session: no session left → no day status.
                    day.pop("status", None)
                return True
    return False


def drop_engine_tests(state: Dict[str, Any], rows: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Remove the ENGINE-owned rows of :func:`planned_tests` from every copy of
    their week (``week_plans[K]`` and ``current_week_plan``), in place. Returns
    the removed rows (without ``user_owned``). Never logs an adaptation event
    (see the module docstring); the caller stamps the revision and marks the
    weeks stale so the next GET /api/week regenerates them under the decline.
    A removed combined test was both axes' test: the regeneration places the
    other axis alone."""
    removed: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("user_owned"):
            continue
        hit = False
        for plan in _copies(state, row["week_start"]):
            hit = _drop_from(plan, row) or hit
        if hit:
            removed.append({k: row[k] for k in ("week_start", "date", "slot", "session_id")})
    return removed


def tests_placed_under_postpone(state: Mapping[str, Any], axis: str, *, since: DateLike) -> List[Dict[str, Any]]:
    """A320 review: the rows of :func:`planned_tests` that PASS 3a placed under
    a postpone — the week's snapshot holds the axis' ``placed`` row with
    trigger ``postponed`` on that day and slot. Such a test exists only because
    of the postpone: once it is undone (DELETE) nothing backs it — the original
    week sees it "already scheduled" while the next regeneration of its own week
    drops it, and the test is lost. DELETE takes the engine's ones out."""
    out: List[Dict[str, Any]] = []
    for row in planned_tests(state, axis, since=since):
        snap = ((rp._hot_plan(state, row["week_start"]) or {}).get("profile_snapshot") or {}) \
            .get("retest_decisions") or {}
        for req in snap.get("required_sessions") or []:
            if (isinstance(req, Mapping) and req.get("axis") == axis and req.get("status") == "placed"
                    and req.get("trigger") == rp.TRIGGER_POSTPONED
                    and str(req.get("placed_date") or "")[:10] == row["date"]
                    and req.get("placed_slot") == row["slot"]):
                out.append(row)
                break
    return out


def weeks_generated_under_decline(state: Mapping[str, Any], axis: str, *, since: DateLike) -> List[str]:
    """Hot weeks from the Monday of ``since`` on whose snapshot skipped ``axis``
    because of a STORED decline (``skip_reason`` declined / postponed, not a
    plan edit): undoing the decline must regenerate them."""
    lower = _monday(_as_date(since)).isoformat()
    out: List[str] = []
    for key, plan in _hot_plans(state):
        if key < lower:
            continue
        snap = (plan.get("profile_snapshot") or {}).get("retest_decisions") or {}
        for row in snap.get("skipped") or []:
            if not isinstance(row, Mapping) or row.get("axis") != axis:
                continue
            view = row.get("declined") if isinstance(row.get("declined"), Mapping) else {}
            if row.get("skip_reason") in (rp.SKIP_DECLINED, rp.SKIP_POSTPONED) \
                    and view.get("source") != rp.DECLINE_SOURCE_PLAN_EDIT:
                out.append(key)
                break
    return out


def week_to_reopen(
    state: Mapping[str, Any],
    axis: str,
    *,
    today: DateLike,
    finger_device: Optional[str] = None,
) -> Optional[str]:
    """The cached week the test now belongs to, when it was generated without
    it: the first week from the Monday of ``today`` on where the policy calls
    the axis due (the week holding a postpone's ``until``, the next trigger of
    another kind) — when that week is hot, not stale and no test of the axis
    is planned anywhere. A cached week is never regenerated on its own: without
    the flag the test would wait for the first week generated later (a week
    or more after the athlete's ``until``).

    None when a test of the axis is still planned (the athlete's own, kept),
    when that first due week is not generated yet or already stale (the next
    GET /api/week generates it), or when nothing is due before the max
    expires within ``STATUS_HORIZON_WEEKS``. The same week walk as
    ``retest_status``'s projection; dates only (the archived weeks feed the
    confidence, which moves no date since A319)."""
    day = _as_date(today)
    if planned_tests(state, axis, since=day):
        return None
    ws = _monday(day)
    for k in range(rp.STATUS_HORIZON_WEEKS):
        wk = ws + timedelta(days=7 * k)
        dec = rp._axis_week_decision(state, axis, wk, today=day, finger_device=finger_device,
                                     archived_weeks=None, check_already_scheduled=False)
        if dec is None:
            return None  # the max expires first: the legacy rules take over
        if dec["status"] != "due":
            continue
        hot = rp._hot_plan(state, wk.isoformat())
        if hot is None or hot.get(rp._STALE_KEY):
            return None
        return wk.isoformat()
    return None


__all__ = [
    "REASONS", "SOURCES", "NOTE_MAX_CHARS", "CONFLICT_CODES", "DeclineError", "active_postpone",
    "build_record", "upsert", "remove", "planned_tests", "drop_engine_tests", "tests_placed_under_postpone",
    "weeks_generated_under_decline", "week_to_reopen",
]
