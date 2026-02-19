from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

from backend.engine.macrocycle_v1 import _build_session_pool
from backend.engine.planner_v2 import _INTENSITY_TO_LOAD, _SESSION_META, generate_phase_week

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
    "projecting": "power_contact_gym",
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
        "estimated_load_score": _INTENSITY_TO_LOAD.get(meta["intensity"], 40),
        "constraints_applied": ["replanner_fill"],
        "tags": {"hard": meta["hard"], "finger": meta["finger"]},
        "explain": ["deterministic refill", f"fill_kind={kind}"],
    }


def suggest_sessions(
    plan: Dict[str, Any],
    target_date: str,
    location: str,
    *,
    session_pool: Optional[List[str]] = None,
    max_suggestions: int = 3,
) -> List[Dict[str, Any]]:
    """Return up to *max_suggestions* candidate sessions for quick-add.

    Scoring is deterministic — same inputs always yield the same output.
    """
    phase_id = (plan.get("profile_snapshot") or {}).get("phase_id", "base")
    candidates = session_pool if session_pool is not None else _build_session_pool(phase_id)

    # Filter by location compatibility
    candidates = [
        sid for sid in candidates
        if location in _meta_for(sid).get("location", ("home", "gym"))
    ]

    # Collect already-scheduled session IDs (skip done/skipped)
    scheduled: set[str] = set()
    for day in (plan.get("weeks") or [{}])[0].get("days", []):
        for s in day.get("sessions", []):
            if s.get("status") not in ("done", "skipped"):
                scheduled.add(s.get("session_id", ""))

    # Determine hard cap
    hard_cap = int((plan.get("profile_snapshot") or {}).get("hard_cap_per_week", 3))
    hard_count = 0
    finger_adjacent = False
    for day in (plan.get("weeks") or [{}])[0].get("days", []):
        if any((s.get("tags") or {}).get("hard") and s.get("status") != "done" for s in day.get("sessions", [])):
            hard_count += 1
        # Check if adjacent day has finger session
        try:
            target_d = _parse_date(target_date)
            day_d = _parse_date(day["date"])
            if abs((target_d - day_d).days) <= 1 and day["date"] != target_date:
                if any((s.get("tags") or {}).get("finger") for s in day.get("sessions", [])):
                    finger_adjacent = True
        except (KeyError, ValueError):
            pass

    # Check if target_date follows a hard day
    follows_hard = False
    try:
        target_d = _parse_date(target_date)
        prev_date = (target_d - timedelta(days=1)).isoformat()
        for day in (plan.get("weeks") or [{}])[0].get("days", []):
            if day.get("date") == prev_date:
                if any((s.get("tags") or {}).get("hard") for s in day.get("sessions", [])):
                    follows_hard = True
                break
    except (KeyError, ValueError):
        pass

    # Score each candidate
    scored: List[tuple] = []
    for sid in candidates:
        meta = _meta_for(sid)
        score = 0

        # +10 if not already in week
        if sid not in scheduled:
            score += 10

        # +5 if recovery/complementary after hard day
        if follows_hard and not meta.get("hard") and meta.get("intensity") in ("low", "medium"):
            score += 5

        # -1000 if hard and hard cap reached
        if meta.get("hard") and hard_count >= hard_cap:
            score -= 1000

        # -1000 if finger and adjacent day has finger
        if meta.get("finger") and finger_adjacent:
            score -= 1000

        # Reason string for UX
        reason_parts = []
        if sid not in scheduled:
            reason_parts.append("adds variety")
        if follows_hard and not meta.get("hard"):
            reason_parts.append("good after a hard day")
        if meta.get("hard"):
            reason_parts.append("high intensity")
        reason = "; ".join(reason_parts) if reason_parts else "available"

        scored.append((score, sid, meta, reason))

    # Sort: highest score first, then alphabetical by session_id for determinism
    scored.sort(key=lambda t: (-t[0], t[1]))

    results: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for _score, sid, meta, reason in scored:
        if sid in seen:
            continue
        seen.add(sid)
        results.append({
            "session_id": sid,
            "intensity": meta.get("intensity", "medium"),
            "estimated_load_score": _INTENSITY_TO_LOAD.get(meta.get("intensity", "medium"), 40),
            "reason": reason,
        })
        if len(results) >= max_suggestions:
            break

    return results


def apply_day_add(
    plan: Dict[str, Any],
    *,
    session_id: str,
    target_date: str,
    slot: str = "evening",
    location: str,
    phase_id: Optional[str] = None,
    gym_id: Optional[str] = None,
) -> tuple:
    """Append a session to an existing day (quick-add). Returns (updated_plan, warnings)."""
    updated = deepcopy(plan)
    updated.setdefault("adaptations", [])
    target_day = _find_day(updated, target_date)

    # Slot conflict check
    for s in target_day.get("sessions", []):
        if s.get("slot") == slot:
            raise ValueError(f"Slot '{slot}' already occupied on {target_date}")

    meta = _meta_for(session_id)
    effective_phase = phase_id or (updated.get("profile_snapshot") or {}).get("phase_id", "base")
    effective_gym_id = gym_id or (_default_gym_id_from_plan(updated) if location == "gym" else None)

    new_session = {
        "slot": slot,
        "session_id": session_id,
        "location": location,
        "gym_id": effective_gym_id,
        "phase_id": effective_phase,
        "intensity": meta["intensity"],
        "estimated_load_score": _INTENSITY_TO_LOAD.get(meta["intensity"], 40),
        "constraints_applied": ["quick_add"],
        "tags": {"hard": meta["hard"], "finger": meta["finger"]},
        "explain": ["user quick-add session", f"added_session={session_id}"],
    }

    target_day.setdefault("sessions", []).append(new_session)
    target_day["sessions"].sort(
        key=lambda s: (SLOTS.index(s.get("slot", "evening")), s.get("priority", 99), s.get("session_id", ""))
    )

    # Ripple day+1 only (lighter than override's day+1+2)
    if meta["hard"] or meta["finger"]:
        target_d = _parse_date(target_date)
        ripple_key = (target_d + timedelta(days=1)).isoformat()
        try:
            ripple_day = _find_day(updated, ripple_key)
        except ValueError:
            ripple_day = None

        if ripple_day and ripple_day.get("sessions"):
            recovery_meta = _meta_for("regeneration_easy")
            comp_meta = _meta_for("complementary_conditioning")
            next_sessions = []
            for session in ripple_day["sessions"]:
                is_hard = (session.get("tags") or {}).get("hard")
                is_low = session.get("intensity") == "low"
                if is_hard:
                    next_sessions.append({
                        "slot": session.get("slot", "evening"),
                        "session_id": "complementary_conditioning",
                        "location": session.get("location", location),
                        "gym_id": session.get("gym_id", effective_gym_id),
                        "phase_id": effective_phase,
                        "intensity": comp_meta["intensity"],
                        "constraints_applied": ["quick_add_ripple"],
                        "tags": {"hard": False, "finger": False},
                        "explain": ["hard→medium after quick-add", f"source_day={target_date}"],
                    })
                elif not is_low:
                    next_sessions.append({
                        "slot": session.get("slot", "evening"),
                        "session_id": "regeneration_easy",
                        "location": session.get("location", location),
                        "gym_id": session.get("gym_id", effective_gym_id),
                        "phase_id": effective_phase,
                        "intensity": recovery_meta["intensity"],
                        "constraints_applied": ["quick_add_ripple"],
                        "tags": {"hard": False, "finger": False},
                        "explain": ["medium→low after quick-add", f"source_day={target_date}"],
                    })
                else:
                    next_sessions.append(session)
            ripple_day["sessions"] = next_sessions

    # Warnings (don't block)
    warnings: List[str] = []
    hard_cap = int((updated.get("profile_snapshot") or {}).get("hard_cap_per_week", 3))
    hard_count = sum(
        1 for d in updated["weeks"][0]["days"]
        if any((s.get("tags") or {}).get("hard") and s.get("status") != "done" for s in d.get("sessions", []))
    )
    if hard_count > hard_cap:
        warnings.append(f"Hard session count ({hard_count}) exceeds weekly cap ({hard_cap})")

    updated["adaptations"].append({
        "type": "quick_add",
        "target_date": target_date,
        "session_id": session_id,
        "slot": slot,
    })

    return (updated, warnings)


def regenerate_preserving_completed(
    old_plan: Dict[str, Any],
    new_plan: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge completed/skipped sessions from *old_plan* into *new_plan*."""
    result = deepcopy(new_plan)

    # Build map of completed sessions from old plan
    completed_map: Dict[str, List[Dict[str, Any]]] = {}
    for day in (old_plan.get("weeks") or [{}])[0].get("days", []):
        done_sessions = [
            s for s in day.get("sessions", [])
            if s.get("status") in ("done", "skipped")
        ]
        if done_sessions:
            completed_map[day["date"]] = done_sessions

    # Merge into new plan
    for date_key, completed_sessions in completed_map.items():
        target_day = None
        for day in (result.get("weeks") or [{}])[0].get("days", []):
            if day.get("date") == date_key:
                target_day = day
                break
        if target_day is None:
            continue

        occupied_slots = {s.get("slot") for s in target_day.get("sessions", [])}
        for cs in completed_sessions:
            cs_slot = cs.get("slot")
            if cs_slot in occupied_slots:
                # Replace the auto-generated session in this slot
                target_day["sessions"] = [
                    cs if s.get("slot") == cs_slot else s
                    for s in target_day["sessions"]
                ]
            else:
                target_day.setdefault("sessions", []).append(cs)
            occupied_slots.add(cs_slot)

        # Re-sort by slot order
        target_day["sessions"].sort(
            key=lambda s: (SLOTS.index(s.get("slot", "evening")), s.get("priority", 99), s.get("session_id", ""))
        )

    result["plan_revision"] = int(result.get("plan_revision") or 1) + 1
    return result


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


def _compensate_finger(
    plan: Dict[str, Any],
    excluded_date: str,
    phase_id: str,
    location: str,
    gym_id: Optional[str],
) -> None:
    """Try to place a finger_maintenance session on a suitable day after losing one to override.

    Looks for future days (excluded_date+2 onwards) that have no finger session,
    have >= 48h gap from the nearest existing finger day, and have a replaceable
    complementary/recovery session. Mutates *plan* in place.
    """
    days = plan["weeks"][0]["days"]
    excluded_d = _parse_date(excluded_date)

    # Collect existing finger dates (after override has been applied)
    finger_dates: set = set()
    for day in days:
        if any((s.get("tags") or {}).get("finger") for s in day.get("sessions", [])):
            finger_dates.add(_parse_date(day["date"]))

    # Search from excluded_date+2 onwards (48h gap)
    comp_session_id = "finger_maintenance_home"
    comp_meta = _meta_for(comp_session_id)

    for day in days:
        day_d = _parse_date(day["date"])
        if (day_d - excluded_d).days < 2:
            continue

        # Check 48h gap from ALL existing finger days
        too_close = False
        for fd in finger_dates:
            if abs((day_d - fd).days) <= 1:
                too_close = True
                break
        if too_close:
            continue

        # Already has finger — skip
        if any((s.get("tags") or {}).get("finger") for s in day.get("sessions", [])):
            continue

        # Find a replaceable session (complementary/recovery, non-hard, non-done)
        replaceable_idx = None
        for idx, s in enumerate(day.get("sessions", [])):
            if s.get("status") in ("done", "skipped"):
                continue
            if (s.get("tags") or {}).get("hard"):
                continue
            sid = s.get("session_id", "")
            if sid in ("complementary_conditioning", "regeneration_easy", "yoga_recovery",
                       "flexibility_full", "prehab_maintenance"):
                replaceable_idx = idx
                break

        if replaceable_idx is None:
            continue

        # Replace with finger_maintenance_home
        old = day["sessions"][replaceable_idx]
        day["sessions"][replaceable_idx] = {
            "slot": old.get("slot", "evening"),
            "session_id": comp_session_id,
            "location": "home",
            "gym_id": None,
            "phase_id": phase_id,
            "intensity": comp_meta["intensity"],
            "constraints_applied": ["finger_compensation"],
            "tags": {"hard": comp_meta["hard"], "finger": comp_meta["finger"]},
            "explain": ["finger compensation after override", f"lost_date={excluded_date}"],
        }

        plan.setdefault("adaptations", []).append({
            "type": "finger_compensation",
            "compensated_date": day["date"],
            "lost_date": excluded_date,
        })
        return  # compensated — done

    # No suitable day found — emit warning
    plan.setdefault("adaptations", []).append({
        "type": "finger_compensation_warning",
        "lost_date": excluded_date,
        "message": "Could not find a suitable day to compensate lost finger session",
    })


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

    # NEW-F6: detect phase mismatch
    current_phase = (updated.get("profile_snapshot") or {}).get("phase_id", "base")
    phase_mismatch_warning = None
    if effective_phase != current_phase:
        phase_mismatch_warning = {
            "type": "phase_mismatch_warning",
            "requested_phase": effective_phase,
            "current_phase": current_phase,
            "message": f"Override session uses phase '{effective_phase}' but current plan phase is '{current_phase}'",
        }

    target_day = _find_day(updated, target_key)
    effective_gym_id = gym_id or (_default_gym_id_from_plan(updated) if location == "gym" else None)

    # NEW-F7: save original sessions before overwriting
    original_sessions = list(target_day.get("sessions") or [])

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
        comp_meta = _meta_for("complementary_conditioning")
        for delta in (1, 2):
            ripple_key = (target + timedelta(days=delta)).isoformat()
            try:
                ripple_day = _find_day(updated, ripple_key)
            except ValueError:
                continue
            if not ripple_day.get("sessions"):
                continue
            next_sessions = []
            for session in ripple_day.get("sessions", []):
                is_hard = session.get("tags", {}).get("hard")
                is_low = session.get("intensity") == "low"

                if delta == 1:
                    # Proportional: hard→medium, medium→low, low→keep
                    if is_hard:
                        next_sessions.append(
                            {
                                "slot": session.get("slot", "evening"),
                                "session_id": "complementary_conditioning",
                                "location": session.get("location", location),
                                "gym_id": session.get("gym_id", effective_gym_id),
                                "phase_id": effective_phase,
                                "intensity": comp_meta["intensity"],
                                "constraints_applied": ["recovery_ripple_proportional"],
                                "tags": {"hard": False, "finger": False},
                                "explain": ["hard→medium after hard override", f"source_day={target_key}"],
                            }
                        )
                    elif not is_low:
                        next_sessions.append(
                            {
                                "slot": session.get("slot", "evening"),
                                "session_id": "regeneration_easy",
                                "location": session.get("location", location),
                                "gym_id": session.get("gym_id", effective_gym_id),
                                "phase_id": effective_phase,
                                "intensity": recovery_meta["intensity"],
                                "constraints_applied": ["recovery_ripple_proportional"],
                                "tags": {"hard": False, "finger": False},
                                "explain": ["medium→low after hard override", f"source_day={target_key}"],
                            }
                        )
                    else:
                        next_sessions.append(session)
                else:
                    # Day+2: force recovery for anything non-low
                    if is_hard or not is_low:
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
                                "explain": ["forced recovery after hard override", f"source_day={target_key}"],
                            }
                        )
                    else:
                        next_sessions.append(session)
            ripple_day["sessions"] = next_sessions

    # NEW-F7: finger compensation — if override removed a finger session, try to place it elsewhere
    original_had_finger = any(
        (s.get("tags") or {}).get("finger") for s in original_sessions
    )
    new_has_finger = meta["finger"]
    if original_had_finger and not new_has_finger:
        _compensate_finger(updated, target_key, effective_phase, location, effective_gym_id)

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

    # NEW-F6: append phase mismatch warning if detected
    if phase_mismatch_warning:
        updated["adaptations"].append(phase_mismatch_warning)

    return updated
