"""A315 — automatic re-schedule of a key session the user's action lost.

A294 computes, for every key requirement of the week that still has debt, a
validated re-schedule proposal; before A315 it only waited for a tap. Now a
write that makes a key requirement owe MORE than before (a skip, a removal, a
move, an override, an outdoor day, a change of gym, a custom that took a key
session's place) applies the proposals of exactly those keys, through the same
``add_planned_session`` event the tap sends, and tells the user (toast + Undo).

Why this is not what A301 forbade: A301 stopped the engine from rewriting the
plan *in reaction to the guards* (downshifts, ripples). An automatic
re-schedule is the application of a proposal that was validated to raise NO
new guard alert and to leave no other key worse off, it is declared in the
response, and it is undone with one tap (``undo_auto_reschedule``).

Rules:
- only on writes (``/events`` without dry run, ``/override``), never on a read;
- only the keys whose debt went UP in this call — an old debt the user let go
  is not re-applied by an unrelated write;
- never a key the user already undid this week (``auto_reschedule_declined``);
- kill switch ``KEY_AUTO_RESCHEDULE``: only the literal ``0`` disables, read at
  call time;
- fail-soft: any error leaves the user's own action applied and nothing else.
"""

from __future__ import annotations

import logging
import os
from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return os.environ.get("KEY_AUTO_RESCHEDULE", "") != "0"


def state_with_plan(state: Mapping[str, Any], plan: Mapping[str, Any]) -> Dict[str, Any]:
    """*state* with *plan* in place as its week (shallow: nothing is mutated)."""
    ws = str(plan.get("start_date") or "")[:10]
    st = dict(state)
    st["week_plans"] = {**(state.get("week_plans") or {}), ws: plan}
    cur = state.get("current_week_plan")
    if isinstance(cur, Mapping) and str(cur.get("start_date") or "")[:10] == ws:
        st["current_week_plan"] = plan
    return st


def debts(key_status: Optional[Mapping[str, Any]]) -> Dict[str, int]:
    return {r["key"]: int(r.get("debt") or 0) for r in (key_status or {}).get("requirements") or []}


def declined_keys(plan: Mapping[str, Any]) -> set:
    out: set = set()
    for a in plan.get("adaptations") or []:
        if isinstance(a, Mapping) and a.get("type") == "auto_reschedule_declined":
            out.update(a.get("keys") or [])
    return out


def debts_before(state: Mapping[str, Any], user_id: Optional[str], plan: Mapping[str, Any],
                 today: Optional[str]) -> Optional[Dict[str, int]]:
    """The week's key debts before the call's events (None when unavailable
    or switched off — then nothing is applied automatically)."""
    if not enabled():
        return None
    from backend.api.key_status import build_key_status

    try:
        st = build_key_status(state_with_plan(state, plan), user_id, week_start=plan.get("start_date"),
                              today=today, with_proposals=False)
        return debts(st) if st else None
    except Exception:
        logger.warning("A315: key debts before the events unavailable", exc_info=True)
        return None


def _adaptation_id(plan: Mapping[str, Any], prop: Mapping[str, Any]) -> str:
    base = f"ar_{prop['date']}_{prop['slot']}_{prop['session_id']}"
    taken = {a.get("id") for a in plan.get("adaptations") or [] if isinstance(a, Mapping)}
    if base not in taken:
        return base
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"


def select(key_status: Optional[Mapping[str, Any]], before: Mapping[str, int],
           plan: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """The proposals to apply: those covering a key whose debt went up, none
    of a key the user declined this week."""
    if not key_status or key_status.get("is_past_week"):
        return []
    after = debts(key_status)
    grown = {k for k, v in after.items() if v > before.get(k, 0)}
    if not grown:
        return []
    declined = declined_keys(plan)
    out = []
    for p in key_status.get("proposals") or []:
        keys = set(p.get("keys") or [])
        if keys & grown and not keys & declined:
            out.append(p)
    return out


def apply(
    state: Mapping[str, Any],
    user_id: Optional[str],
    plan: Dict[str, Any],
    before: Optional[Mapping[str, int]],
    *,
    today: Optional[str],
    custom_sessions: Optional[list] = None,
    dry_run: bool = False,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """``(plan, auto_reschedules)``: *plan* with the automatic re-schedules
    applied (unchanged on dry run, when off, or on any failure)."""
    if before is None or not enabled():
        return plan, []
    from backend.api.key_status import build_key_status, resolve_today
    from backend.engine.replanner_v1 import apply_events

    try:
        ks = build_key_status(state_with_plan(state, plan), user_id, week_start=plan.get("start_date"),
                              today=today, with_proposals=True)
        chosen = select(ks, before, plan)
        if not chosen:
            return plan, []
        events: List[Dict[str, Any]] = []
        report: List[Dict[str, Any]] = []
        work = deepcopy(plan)
        for p in chosen:
            ev = dict((p.get("apply") or {}).get("event") or {})
            if ev.get("event_type") != "add_planned_session":
                continue
            aid = _adaptation_id(work, p)
            ev.update(auto=True, adaptation_id=aid, keys=list(p.get("keys") or []))
            events.append(ev)
            work.setdefault("adaptations", []).append({"id": aid})  # reserve the id
            report.append({
                "adaptation_id": aid,
                "keys": list(p.get("keys") or []),
                "date": p["date"],
                "slot": p["slot"],
                "session_id": p["session_id"],
                "session_name": p.get("session_name"),
                "replaced": p.get("replaces"),
            })
        if not events or dry_run:
            return plan, report
        updated = apply_events(plan, events, custom_sessions=custom_sessions, today=resolve_today(today))
        return updated, report
    except Exception:
        logger.warning("A315: automatic key re-schedule failed — the user's action stands alone",
                       exc_info=True)
        return plan, []
