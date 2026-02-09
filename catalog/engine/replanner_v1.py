from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

from catalog.engine.planner_v1 import SESSION_LIBRARY, generate_week_plan

INTENT_TO_SESSION = {
    "rest": "deload_recovery",
    "recovery": "deload_recovery",
    "technique": "gym_technique_boulder",
    "strength": "strength_long",
    "power": "gym_power_bouldering",
    "power_endurance": "gym_power_endurance",
    "aerobic_endurance": "gym_aerobic_endurance",
}
SLOTS = ("morning", "lunch", "evening")


def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _find_day(plan: Dict[str, Any], target_date: str) -> Dict[str, Any]:
    for day in plan["weeks"][0]["days"]:
        if day.get("date") == target_date:
            return day
    raise ValueError(f"Date not present in plan: {target_date}")


def _default_gym_id_from_plan(plan: Dict[str, Any]) -> Optional[str]:
    profile = plan.get("profile_snapshot") or {}
    prefs = profile.get("planning_prefs") or {}
    gym_id = prefs.get("default_gym_id")
    return gym_id if isinstance(gym_id, str) and gym_id else None


def _session_matches(session: Dict[str, Any], *, session_ref: Optional[str], slot: Optional[str]) -> bool:
    if session_ref and session.get("session_id") != session_ref:
        return False
    if slot and session.get("slot") != slot:
        return False
    return True


def _extract_session(day: Dict[str, Any], *, session_ref: Optional[str], slot: Optional[str]) -> Dict[str, Any]:
    sessions = day.get("sessions") or []
    for idx, session in enumerate(sessions):
        if _session_matches(session, session_ref=session_ref, slot=slot):
            return sessions.pop(idx)
    raise ValueError(f"Session not found for day={day.get('date')} session_ref={session_ref} slot={slot}")


def _insert_or_replace(day: Dict[str, Any], moved: Dict[str, Any], to_slot: str) -> None:
    moved["slot"] = to_slot
    sessions = day.setdefault("sessions", [])
    for idx, existing in enumerate(sessions):
        if existing.get("slot") == to_slot:
            sessions[idx] = moved
            break
    else:
        sessions.append(moved)
    sessions.sort(key=lambda s: (SLOTS.index(s.get("slot", "evening")), s.get("priority", 99), s.get("session_id", "")))


def _slots_from_day(day: Dict[str, Any]) -> set[str]:
    return {s.get("slot") for s in (day.get("sessions") or []) if s.get("slot") in SLOTS}


def _build_fill_session(plan: Dict[str, Any], day: Dict[str, Any], slot: str, *, kind: str) -> Dict[str, Any]:
    # deterministic conservative fill
    session_key = "deload_recovery" if kind == "recovery" else "general_strength_short"
    spec = SESSION_LIBRARY[session_key]
    location = "home"
    gym_id = None
    if any(s.get("location") == "gym" for s in day.get("sessions") or []):
        location = "gym"
        gym_id = _default_gym_id_from_plan(plan)
    return {
        "slot": slot,
        "session_id": spec.session_id,
        "location": location,
        "gym_id": gym_id,
        "intent": spec.intent,
        "priority": spec.priority,
        "constraints_applied": ["replanner_fill"],
        "tags": {"hard": spec.hard, "finger": spec.finger},
        "explain": ["deterministic refill", f"fill_kind={kind}"],
    }


def _enforce_caps(plan: Dict[str, Any]) -> None:
    hard_cap = int(((plan.get("profile_snapshot") or {}).get("hard_cap_per_week") or 3))
    days = plan["weeks"][0]["days"]
    hard_days = [d for d in days if any((s.get("tags") or {}).get("hard") for s in d.get("sessions") or [])]
    if len(hard_days) > hard_cap:
        for day in reversed(hard_days[hard_cap:]):
            for session in day.get("sessions") or []:
                tags = session.get("tags") or {}
                if tags.get("hard"):
                    recovery_spec = SESSION_LIBRARY["deload_recovery"]
                    session.update(
                        {
                            "session_id": recovery_spec.session_id,
                            "intent": recovery_spec.intent,
                            "priority": recovery_spec.priority,
                            "tags": {"hard": False, "finger": False},
                            "constraints_applied": ["hard_cap_downshift"],
                            "explain": ["hard cap exceeded after replanning", "deterministic downshift"],
                        }
                    )


def _enforce_no_consecutive_finger(plan: Dict[str, Any]) -> None:
    days = plan["weeks"][0]["days"]
    last_finger_date = None
    for day in days:
        cur = _parse_date(day["date"])
        has_finger = any((s.get("tags") or {}).get("finger") for s in day.get("sessions") or [])
        if has_finger and last_finger_date and (cur - last_finger_date).days <= 1:
            for session in day.get("sessions") or []:
                if (session.get("tags") or {}).get("finger"):
                    recovery_spec = SESSION_LIBRARY["deload_recovery"]
                    session.update(
                        {
                            "session_id": recovery_spec.session_id,
                            "intent": recovery_spec.intent,
                            "priority": recovery_spec.priority,
                            "tags": {"hard": False, "finger": False},
                            "constraints_applied": ["finger_spacing_downshift"],
                            "explain": ["no consecutive finger days", "deterministic downshift"],
                        }
                    )
            has_finger = False
        if has_finger:
            last_finger_date = cur


def _reconcile(plan: Dict[str, Any]) -> None:
    _enforce_no_consecutive_finger(plan)
    _enforce_caps(plan)


def apply_events(
    plan: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    *,
    availability: Optional[Dict[str, Any]] = None,
    planning_prefs: Optional[Dict[str, Any]] = None,
    gyms: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    updated = deepcopy(plan)
    updated.setdefault("adaptations", [])

    for event in events:
        event_type = event.get("event_type")
        if event_type == "move_session":
            from_day = _find_day(updated, event["from_date"])
            to_day = _find_day(updated, event["to_date"])
            moved = _extract_session(from_day, session_ref=event.get("session_ref"), slot=event.get("from_slot"))
            _insert_or_replace(to_day, moved, event["to_slot"])

            if event.get("from_slot") not in _slots_from_day(from_day):
                fill_kind = "accessory" if any((s.get("tags") or {}).get("hard") for s in from_day.get("sessions") or []) else "recovery"
                from_day.setdefault("sessions", []).append(_build_fill_session(updated, from_day, event["from_slot"], kind=fill_kind))

        elif event_type == "mark_skipped":
            day = _find_day(updated, event["date"])
            removed = _extract_session(day, session_ref=event.get("session_ref"), slot=event.get("slot"))
            slot = removed.get("slot") or event.get("slot") or "evening"
            day.setdefault("sessions", []).append(_build_fill_session(updated, day, slot, kind="recovery"))

        elif event_type == "mark_done":
            day = _find_day(updated, event["date"])
            try:
                _extract_session(day, session_ref=event.get("session_ref"), slot=event.get("slot"))
            except ValueError:
                pass

        elif event_type == "set_availability":
            if availability is not None and event.get("availability"):
                av = event["availability"]
                if event.get("date"):
                    date_key = _parse_date(event["date"]).weekday()
                    weekday = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[date_key]
                else:
                    weekday = av.get("weekday")
                slot = av.get("slot")
                if weekday and slot and weekday in availability and slot in availability[weekday]:
                    for key in ("available", "locations", "preferred_location", "gym_id"):
                        if key in av:
                            availability[weekday][slot][key] = av[key]
                regenerated = generate_week_plan(
                    start_date=updated["start_date"],
                    mode=((updated.get("profile_snapshot") or {}).get("mode") or "balanced"),
                    availability=availability,
                    allowed_locations=((updated.get("profile_snapshot") or {}).get("allowed_locations") or ["home", "gym", "outdoor"]),
                    hard_cap_per_week=int(((updated.get("profile_snapshot") or {}).get("hard_cap_per_week") or 3)),
                    planning_prefs=planning_prefs,
                    default_gym_id=((planning_prefs or {}).get("default_gym_id")),
                    gyms=gyms,
                )
                updated["weeks"] = regenerated["weeks"]
                updated["profile_snapshot"] = regenerated["profile_snapshot"]

        updated["adaptations"].append({"type": "event", "event": event})

    _reconcile(updated)
    updated["plan_revision"] = int(updated.get("plan_revision") or 1) + 1
    return updated


def apply_day_override(
    plan: Dict[str, Any],
    *,
    intent: str,
    location: str,
    reference_date: str,
    slot: str = "evening",
) -> Dict[str, Any]:
    updated = deepcopy(plan)
    ref = _parse_date(reference_date)
    tomorrow = ref + timedelta(days=1)
    tomorrow_key = tomorrow.isoformat()

    session_key = INTENT_TO_SESSION.get(intent)
    if session_key is None:
        raise ValueError(f"Unsupported override intent: {intent}")

    spec = SESSION_LIBRARY[session_key]
    tomorrow_day = _find_day(updated, tomorrow_key)
    gym_id = _default_gym_id_from_plan(updated) if location == "gym" else None
    tomorrow_day["sessions"] = [
        {
            "slot": slot,
            "session_id": spec.session_id,
            "location": location,
            "gym_id": gym_id,
            "intent": spec.intent,
            "priority": 1,
            "constraints_applied": ["manual_override"],
            "tags": {"hard": spec.hard, "finger": spec.finger},
            "explain": ["user day override applied", f"override_intent={intent}"],
        }
    ]

    if spec.hard or spec.finger:
        for delta in (2, 3):
            ripple_day = _find_day(updated, (ref + timedelta(days=delta)).isoformat())
            next_sessions = []
            for session in ripple_day.get("sessions", []):
                if session.get("tags", {}).get("hard"):
                    recovery_spec = SESSION_LIBRARY["deload_recovery"]
                    next_sessions.append(
                        {
                            "slot": session.get("slot", "evening"),
                            "session_id": recovery_spec.session_id,
                            "location": session.get("location", location),
                            "gym_id": session.get("gym_id", gym_id),
                            "intent": recovery_spec.intent,
                            "priority": 5,
                            "constraints_applied": ["recovery_ripple"],
                            "tags": {"hard": False, "finger": False},
                            "explain": ["downgraded after hard override", f"source_day={tomorrow_key}"],
                        }
                    )
                else:
                    next_sessions.append(session)
            ripple_day["sessions"] = next_sessions

    updated.setdefault("adaptations", []).append(
        {
            "type": "day_override",
            "reference_date": reference_date,
            "updated_day": tomorrow_key,
            "ripple_days": [(ref + timedelta(days=2)).isoformat(), (ref + timedelta(days=3)).isoformat()],
        }
    )
    return updated
