from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

from backend.engine.planner_v2 import _SESSION_META, generate_phase_week

# Phase-aware intent → session_id mapping (uses planner_v2 session catalog)
INTENT_TO_SESSION = {
    "rest": "regeneration_easy",
    "recovery": "yoga_recovery",
    "technique": "technique_focus_gym",
    "strength": "strength_long",
    "power": "power_contact_gym",
    "power_endurance": "power_endurance_gym",
    "aerobic_endurance": "endurance_aerobic_gym",
    "core": "complementary_conditioning",
    "prehab": "prehab_maintenance",
    "flexibility": "flexibility_full",
    "finger_maintenance": "finger_maintenance_home",
    "finger_max": "finger_strength_home",
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


def _meta_for(session_id: str) -> Dict[str, Any]:
    """Get session metadata from planner_v2's _SESSION_META."""
    return _SESSION_META.get(session_id, {
        "hard": False, "finger": False, "intensity": "low",
        "climbing": False, "location": ("home", "gym"),
    })


def _build_fill_session(plan: Dict[str, Any], day: Dict[str, Any], slot: str, *, kind: str) -> Dict[str, Any]:
    # deterministic conservative fill using planner_v2 sessions
    session_id = "regeneration_easy" if kind == "recovery" else "complementary_conditioning"
    meta = _meta_for(session_id)
    location = "home"
    gym_id = None
    if any(s.get("location") == "gym" for s in day.get("sessions") or []):
        location = "gym"
        gym_id = _default_gym_id_from_plan(plan)
    return {
        "slot": slot,
        "session_id": session_id,
        "location": location,
        "gym_id": gym_id,
        "intensity": meta["intensity"],
        "constraints_applied": ["replanner_fill"],
        "tags": {"hard": meta["hard"], "finger": meta["finger"]},
        "explain": ["deterministic refill", f"fill_kind={kind}"],
    }


def _enforce_caps(plan: Dict[str, Any]) -> None:
    hard_cap = int(((plan.get("profile_snapshot") or {}).get("hard_cap_per_week") or 3))
    days = plan["weeks"][0]["days"]
    hard_days = [d for d in days if any((s.get("tags") or {}).get("hard") and s.get("status") != "done" for s in d.get("sessions") or [])]
    if len(hard_days) > hard_cap:
        for day in reversed(hard_days[hard_cap:]):
            for session in day.get("sessions") or []:
                tags = session.get("tags") or {}
                if tags.get("hard"):
                    recovery_meta = _meta_for("regeneration_easy")
                    session.update(
                        {
                            "session_id": "regeneration_easy",
                            "intensity": recovery_meta["intensity"],
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
        has_finger = any((s.get("tags") or {}).get("finger") and s.get("status") != "done" for s in day.get("sessions") or [])
        if has_finger and last_finger_date and (cur - last_finger_date).days <= 1:
            for session in day.get("sessions") or []:
                if (session.get("tags") or {}).get("finger"):
                    recovery_meta = _meta_for("regeneration_easy")
                    session.update(
                        {
                            "session_id": "regeneration_easy",
                            "intensity": recovery_meta["intensity"],
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
            recovery = _build_fill_session(updated, day, slot, kind="recovery")
            recovery["status"] = "skipped"
            day.setdefault("sessions", []).append(recovery)
            day["status"] = "skipped"

        elif event_type == "mark_done":
            day = _find_day(updated, event["date"])
            for s in day.get("sessions") or []:
                if _session_matches(s, session_ref=event.get("session_ref"), slot=event.get("slot")):
                    s["status"] = "done"
                    break
            if all(s.get("status") == "done" for s in day.get("sessions") or []):
                day["status"] = "done"

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
                snapshot = updated.get("profile_snapshot") or {}
                phase_id = snapshot.get("phase_id", "base")
                from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _build_session_pool, _adjust_domain_weights
                base_weights = _BASE_WEIGHTS.get(phase_id, _BASE_WEIGHTS["base"])
                domain_weights = snapshot.get("domain_weights", base_weights)
                session_pool = _build_session_pool(phase_id)
                regenerated = generate_phase_week(
                    phase_id=phase_id,
                    domain_weights=domain_weights,
                    session_pool=session_pool,
                    start_date=updated["start_date"],
                    availability=availability,
                    allowed_locations=snapshot.get("allowed_locations", ["home", "gym"]),
                    hard_cap_per_week=int(snapshot.get("hard_cap_per_week", 3)),
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
    phase_id: Optional[str] = None,
    target_date: Optional[str] = None,
    gym_id: Optional[str] = None,
) -> Dict[str, Any]:
    updated = deepcopy(plan)

    # Resolve target day: explicit target_date or reference_date + 1
    if target_date:
        target = _parse_date(target_date)
    else:
        target = _parse_date(reference_date) + timedelta(days=1)
    target_key = target.isoformat()

    session_id = INTENT_TO_SESSION.get(intent)
    if session_id is None:
        raise ValueError(f"Unsupported override intent: {intent}")

    meta = _meta_for(session_id)
    effective_phase = phase_id or (updated.get("profile_snapshot") or {}).get("phase_id", "base")
    target_day = _find_day(updated, target_key)
    effective_gym_id = gym_id or (_default_gym_id_from_plan(updated) if location == "gym" else None)
    target_day["sessions"] = [
        {
            "slot": slot,
            "session_id": session_id,
            "location": location,
            "gym_id": effective_gym_id,
            "phase_id": effective_phase,
            "intensity": meta["intensity"],
            "constraints_applied": ["manual_override"],
            "tags": {"hard": meta["hard"], "finger": meta["finger"]},
            "explain": ["user day override applied", f"override_intent={intent}"],
        }
    ]

    if meta["hard"] or meta["finger"]:
        recovery_meta = _meta_for("regeneration_easy")
        for delta in (1, 2):
            ripple_key = (target + timedelta(days=delta)).isoformat()
            try:
                ripple_day = _find_day(updated, ripple_key)
            except ValueError:
                continue
            next_sessions = []
            for session in ripple_day.get("sessions", []):
                if session.get("tags", {}).get("hard"):
                    next_sessions.append(
                        {
                            "slot": session.get("slot", "evening"),
                            "session_id": "regeneration_easy",
                            "location": session.get("location", location),
                            "gym_id": session.get("gym_id", effective_gym_id),
                            "phase_id": effective_phase,
                            "intensity": recovery_meta["intensity"],
                            "constraints_applied": ["recovery_ripple"],
                            "tags": {"hard": False, "finger": False},
                            "explain": ["downgraded after hard override", f"source_day={target_key}"],
                        }
                    )
                else:
                    next_sessions.append(session)
            ripple_day["sessions"] = next_sessions

    _reconcile(updated)

    updated.setdefault("adaptations", []).append(
        {
            "type": "day_override",
            "reference_date": reference_date,
            "target_date": target_key,
            "ripple_days": [
                (target + timedelta(days=1)).isoformat(),
                (target + timedelta(days=2)).isoformat(),
            ],
        }
    )
    return updated
