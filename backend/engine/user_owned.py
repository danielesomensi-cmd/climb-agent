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

from typing import Any, List, Mapping, Optional, Tuple

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


def removed_refs(plan: Mapping[str, Any]) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """``(date, session_ref, slot)`` of every session the user took off a day.

    - ``remove_session``;
    - ``move_session``: the source side, and (B369 review) the session the
      move overwrote in the target slot (``replaced_session_id``);
    - ``day_override`` (B369 review): a partial override names the one session
      it replaced (``replaced_session_id`` / ``replaced_slot``); a whole-day
      indoor override names the slots the day held (``replaced_slots``) — a
      slot that did not exist at override time is not taken away.

    A reference with neither a session id nor a slot is ignored (it would
    match every session of the day).
    """
    out: List[Tuple[str, Optional[str], Optional[str]]] = []
    for a in (plan or {}).get("adaptations") or []:
        if not isinstance(a, Mapping):
            continue
        if a.get("type") == "day_override" and not a.get("outdoor") and a.get("target_date"):
            date = str(a["target_date"])
            if a.get("replaced_session_id") or a.get("replaced_slot"):
                out.append((date, a.get("replaced_session_id"), a.get("replaced_slot")))
            for slot in a.get("replaced_slots") or []:
                if slot:
                    out.append((date, None, slot))
            continue
        if a.get("type") != "event" or not isinstance(a.get("event"), Mapping):
            continue
        ev = a["event"]
        et = ev.get("event_type")
        if et == "remove_session":
            date, ref, slot = ev.get("date"), ev.get("session_ref"), ev.get("slot")
        elif et == "move_session":
            date = ev.get("from_date")
            ref = ev.get("session_ref") or ev.get("moved_session_id")
            slot = ev.get("from_slot")
            if ev.get("to_date") and ev.get("replaced_session_id"):
                out.append((str(ev["to_date"]), ev["replaced_session_id"], ev.get("to_slot")))
        else:
            continue
        if date and (ref or slot):
            out.append((str(date), ref, slot))
    return out


def whole_day_override_dates(plan: Mapping[str, Any]) -> List[str]:
    """Dates the user replaced wholesale, every slot included: an outdoor
    override, or a whole-day indoor override recorded before the B369 review
    (no ``replaced_slots`` — which slots it replaced is unknown). A newer
    whole-day override names its slots and goes through ``removed_refs``."""
    out: List[str] = []
    for a in (plan or {}).get("adaptations") or []:
        if not isinstance(a, Mapping) or a.get("type") != "day_override":
            continue
        if a.get("outdoor") or (a.get("whole_day") and "replaced_slots" not in a):
            if a.get("target_date"):
                out.append(str(a["target_date"]))
    return out


def carry_user_markers(old: Mapping[str, Any], new_constraints: List[str]) -> List[str]:
    """B369 review: the ``constraints_applied`` of a session a guard rewrites in
    place — *new_constraints* plus the ownership markers of the old one, so a
    rewritten user session stays the user's (``is_user_owned``) and the next
    regeneration keeps it instead of dropping it."""
    kept = [m for m in (old.get("constraints_applied") or []) if m in USER_MARKERS]
    return list(new_constraints) + [m for m in kept if m not in new_constraints]


def ref_matches(session: Mapping[str, Any], ref: Optional[str], slot: Optional[str]) -> bool:
    if ref and session.get("session_id") != ref:
        return False
    if slot and session.get("slot") != slot:
        return False
    return True
