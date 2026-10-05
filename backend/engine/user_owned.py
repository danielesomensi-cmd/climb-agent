"""B369: what in a week plan belongs to the user, and what the user took out.

One predicate, ``is_user_owned``, read by every path that rebuilds a week
(``replanner_v1.merge_prev_week_sessions`` / ``regenerate_preserving_completed``,
the retest policy's view of what the merge will put back, the pause/resume
handling). Before B369 each path kept its own list — done/skipped here,
done/skipped/quick-add there, ``_user_edited`` somewhere else — and a
regeneration silently dropped custom sessions, forced sessions, overrides,
moved sessions and key re-schedules.

``removed_refs`` reads the plan's own ``adaptations`` log (every ``apply_events``
call appends ``{"type": "event", "event": …}``) so a merge can honour what the
user took out: a catalog session the user removed (or moved away) must not come
back on the next regeneration.

Pure, no I/O, no imports from the engine: both the replanner and the retest
policy import it.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Mapping, Optional, Tuple

#: ``constraints_applied`` markers stamped by the paths where the user puts a
#: session on the plan. Keep in sync with replanner_v1 (apply_day_add,
#: apply_events, apply_day_override).
USER_MARKERS = frozenset({
    "quick_add",        # apply_day_add (quick-add)
    "user_forced",      # apply_day_add with force (A254)
    "manual_override",  # apply_day_override
    "key_reschedule",   # add_planned_session (A294 key-session re-schedule)
    "custom_add",       # add_custom_session (A207)
    "generated_add",    # add_generated_session (A213, body-part picker, coach)
    "user_moved",       # move_session (B369)
})


def is_user_owned(session: Mapping[str, Any]) -> bool:
    """True when the user put, forced, moved or edited this session.

    A user-owned session is never dropped or rewritten by a regeneration: it is
    carried over byte-identical. Done/skipped sessions are preserved too, but
    for a different reason (history) — see ``is_preservable``.
    """
    if not isinstance(session, Mapping):
        return False
    if session.get("forced") or session.get("is_custom") or session.get("_user_edited"):
        return True
    markers = session.get("constraints_applied") or []
    if isinstance(markers, (list, tuple)):
        return any(m in USER_MARKERS for m in markers)
    return False


def is_preservable(session: Mapping[str, Any]) -> bool:
    """Should *session* survive a regeneration of its week? Done/skipped
    (history) or user-owned."""
    if not isinstance(session, Mapping):
        return False
    if session.get("status") in ("done", "skipped"):
        return True
    return is_user_owned(session)


def _events(plan: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for a in (plan or {}).get("adaptations") or []:
        if isinstance(a, Mapping) and a.get("type") == "event" and isinstance(a.get("event"), Mapping):
            yield a["event"]


def removed_refs(plan: Mapping[str, Any]) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """``(date, session_ref, slot)`` of every session the user took off a day.

    ``remove_session`` and the source side of ``move_session``. A reference
    with neither a session id nor a slot is ignored (it would match every
    session of the day).
    """
    out: List[Tuple[str, Optional[str], Optional[str]]] = []
    for ev in _events(plan):
        et = ev.get("event_type")
        if et == "remove_session":
            date, ref, slot = ev.get("date"), ev.get("session_ref"), ev.get("slot")
        elif et == "move_session":
            date = ev.get("from_date")
            ref = ev.get("session_ref") or ev.get("moved_session_id")
            slot = ev.get("from_slot")
        else:
            continue
        if date and (ref or slot):
            out.append((str(date), ref, slot))
    return out


def whole_day_override_dates(plan: Mapping[str, Any]) -> List[str]:
    """Dates the user replaced wholesale with an override (outdoor or a
    whole-day indoor override): the engine's other sessions on that day are
    gone on purpose."""
    out: List[str] = []
    for a in (plan or {}).get("adaptations") or []:
        if not isinstance(a, Mapping) or a.get("type") != "day_override":
            continue
        if a.get("outdoor") or a.get("whole_day"):
            if a.get("target_date"):
                out.append(str(a["target_date"]))
    return out


def ref_matches(session: Mapping[str, Any], ref: Optional[str], slot: Optional[str]) -> bool:
    if ref and session.get("session_id") != ref:
        return False
    if slot and session.get("slot") != slot:
        return False
    return True
