"""Phase-aware weekly planner v2 — generates a week plan from macrocycle phase context.

This planner is macrocycle-aware: it selects sessions from the phase's session pool,
respects domain weights, and enforces per-phase intensity caps and constraints.

Constraints:
- No consecutive finger days (48h gap)
- No consecutive max-intensity days
- Hard day cap per week (from planning_prefs)
- Phase intensity cap limits session selection
- Deload weeks enforce reduced volume
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.engine.macrocycle_v1 import (
    PHASE_INTENSITY_CAP,
    PHASE_ORDER,
    _build_session_pool,
    apply_deload_week,
)

SLOTS: Tuple[str, ...] = ("morning", "lunch", "evening")
WEEKDAYS: Tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Session metadata — maps session_id to its properties
# hard: counts against hard_cap; finger: needs 48h gap; intensity: max/high/medium/low
_SESSION_META: Dict[str, Dict[str, Any]] = {
    "strength_long": {"hard": True, "finger": True, "intensity": "max", "location": ("gym", "home")},
    "power_contact_gym": {"hard": True, "finger": False, "intensity": "max", "location": ("gym",)},
    "power_endurance_gym": {"hard": True, "finger": False, "intensity": "high", "location": ("gym",)},
    "endurance_aerobic_gym": {"hard": False, "finger": False, "intensity": "medium", "location": ("gym",)},
    "technique_focus_gym": {"hard": False, "finger": False, "intensity": "medium", "location": ("gym",)},
    "finger_strength_home": {"hard": True, "finger": True, "intensity": "max", "location": ("home",)},
    "prehab_maintenance": {"hard": False, "finger": False, "intensity": "low", "location": ("home", "gym")},
    "flexibility_full": {"hard": False, "finger": False, "intensity": "low", "location": ("home", "gym")},
    "yoga_recovery": {"hard": False, "finger": False, "intensity": "low", "location": ("home",)},
    "handstand_practice": {"hard": False, "finger": False, "intensity": "medium", "location": ("home", "gym")},
    "complementary_conditioning": {"hard": False, "finger": False, "intensity": "medium", "location": ("home", "gym")},
    "regeneration_easy": {"hard": False, "finger": False, "intensity": "low", "location": ("home", "gym", "outdoor")},
}

_INTENSITY_ORDER = {"low": 0, "medium": 1, "high": 2, "max": 3}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _weekday_key(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def _intensity_allowed(session_intensity: str, phase_cap: str) -> bool:
    """Check if a session's intensity level is within the phase cap."""
    return _INTENSITY_ORDER.get(session_intensity, 0) <= _INTENSITY_ORDER.get(phase_cap, 3)


def _pick_location(
    session_locations: Tuple[str, ...],
    slot_info: Dict[str, Any],
    allowed_locations: Sequence[str],
) -> Optional[str]:
    slot_locations = slot_info.get("locations") or list(allowed_locations)
    viable = sorted(set(slot_locations).intersection(session_locations).intersection(allowed_locations))
    if not viable:
        return None
    preferred = slot_info.get("preferred_location")
    if isinstance(preferred, str) and preferred in viable:
        return preferred
    return viable[0]


def _normalize_availability(
    availability: Optional[Dict[str, Any]],
    allowed_locations: Sequence[str],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    normalized: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for wd in WEEKDAYS:
        day = (availability or {}).get(wd) or {}
        day_slots: Dict[str, Dict[str, Any]] = {}
        for slot in SLOTS:
            default = {"available": True, "locations": sorted(set(allowed_locations)),
                        "preferred_location": None, "gym_id": None}
            if isinstance(day, dict) and day.get("available") is False:
                default["available"] = False
                day_slots[slot] = default
                continue
            slot_value = day.get(slot)
            if slot_value is None:
                day_slots[slot] = default
                continue
            if isinstance(slot_value, bool):
                default["available"] = slot_value
            elif isinstance(slot_value, dict):
                default["available"] = bool(slot_value.get("available", True))
                if "locations" in slot_value and isinstance(slot_value["locations"], list):
                    default["locations"] = sorted(set(slot_value["locations"]))
                preferred = slot_value.get("preferred_location")
                if isinstance(preferred, str):
                    default["preferred_location"] = preferred
                gym_id = slot_value.get("gym_id")
                if isinstance(gym_id, str) and gym_id:
                    default["gym_id"] = gym_id
            day_slots[slot] = default
        normalized[wd] = day_slots
    return normalized


def _select_gym_id(
    slot_info: Dict[str, Any],
    default_gym_id: Optional[str],
    gyms: Sequence[Dict[str, Any]],
) -> Optional[str]:
    slot_gym = slot_info.get("gym_id")
    if slot_gym:
        return slot_gym
    if default_gym_id:
        return default_gym_id
    if gyms:
        sorted_gyms = sorted(gyms, key=lambda g: (g.get("priority", 999), g.get("gym_id", "")))
        return sorted_gyms[0].get("gym_id")
    return None


def generate_phase_week(
    *,
    phase_id: str,
    domain_weights: Dict[str, float],
    session_pool: List[str],
    start_date: str,
    availability: Optional[Dict[str, Any]] = None,
    allowed_locations: Optional[List[str]] = None,
    hard_cap_per_week: int = 3,
    planning_prefs: Optional[Dict[str, Any]] = None,
    default_gym_id: Optional[str] = None,
    gyms: Optional[List[Dict[str, Any]]] = None,
    intensity_cap: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a single week plan within a macrocycle phase.

    Args:
        phase_id: Current macrocycle phase (base, strength_power, etc.).
        domain_weights: Domain weight dict from the macrocycle phase.
        session_pool: Ordered list of session_ids for this phase.
        start_date: YYYY-MM-DD Monday of the week.
        availability: User availability dict.
        allowed_locations: Allowed location strings.
        hard_cap_per_week: Max hard sessions per week.
        planning_prefs: User planning preferences.
        default_gym_id: Default gym for gym sessions.
        gyms: List of gym dicts with equipment.
        intensity_cap: Phase intensity cap (overrides PHASE_INTENSITY_CAP if provided).

    Returns:
        Week plan dict compatible with planner.v1 format.
    """
    locations = sorted(set(allowed_locations or ["home", "gym"]))
    normalized = _normalize_availability(availability, locations)
    cap = intensity_cap or PHASE_INTENSITY_CAP.get(phase_id, "max")
    prefs = planning_prefs or {}
    effective_hard_cap = min(hard_cap_per_week, prefs.get("hard_day_cap_per_week", hard_cap_per_week))

    # For deload, further restrict
    if phase_id == "deload":
        effective_hard_cap = 0

    # Filter session pool by intensity cap and available metadata
    filtered_pool = []
    for sid in session_pool:
        meta = _SESSION_META.get(sid)
        if meta is None:
            continue
        if not _intensity_allowed(meta["intensity"], cap):
            continue
        filtered_pool.append(sid)

    start = _parse_date(start_date)
    plan_days: List[Dict[str, Any]] = []
    hard_days = 0
    finger_days_dates: List[date] = []
    last_hard_date: Optional[date] = None
    pool_index = 0

    target_days = prefs.get("target_training_days_per_week", 4)
    days_placed = 0

    for offset in range(7):
        current_date = start + timedelta(days=offset)
        day_key = _weekday_key(current_date)
        day_availability = normalized[day_key]
        sessions: List[Dict[str, Any]] = []

        if days_placed >= target_days and pool_index >= len(filtered_pool):
            plan_days.append({"date": current_date.isoformat(), "weekday": day_key, "sessions": []})
            continue

        for slot in ("evening", "morning", "lunch"):
            if len(sessions) >= 2 or pool_index >= len(filtered_pool):
                break
            slot_info = day_availability[slot]
            if not slot_info["available"]:
                continue

            candidate_sid = filtered_pool[pool_index]
            meta = _SESSION_META[candidate_sid]

            # Hard day cap
            if meta["hard"] and hard_days >= effective_hard_cap:
                pool_index += 1
                continue

            # No consecutive finger days (48h)
            if meta["finger"] and finger_days_dates:
                last_finger = finger_days_dates[-1]
                if (current_date - last_finger).days <= 1:
                    continue

            # No consecutive max-intensity days
            if meta["intensity"] == "max" and last_hard_date and (current_date - last_hard_date).days <= 1:
                continue

            location = _pick_location(meta["location"], slot_info, locations)
            if location is None:
                continue

            gym_id = None
            if location == "gym":
                gym_id = _select_gym_id(slot_info, default_gym_id, gyms or [])

            session_entry = {
                "slot": slot,
                "session_id": candidate_sid,
                "location": location,
                "gym_id": gym_id,
                "phase_id": phase_id,
                "intensity": meta["intensity"],
                "tags": {"hard": meta["hard"], "finger": meta["finger"]},
                "explain": [
                    f"phase={phase_id}",
                    f"slot={slot}",
                    f"day={day_key}",
                    "phase-aware pool placement",
                ],
            }
            sessions.append(session_entry)
            pool_index += 1

            if meta["hard"]:
                hard_days += 1
                last_hard_date = current_date
            if meta["finger"]:
                finger_days_dates.append(current_date)

        if sessions:
            days_placed += 1
        plan_days.append({"date": current_date.isoformat(), "weekday": day_key, "sessions": sessions})

    # Cycle pool for remaining sessions (wrap around)
    # Already placed what we can — no need to force more

    week_plan = {
        "plan_version": "planner.v2",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": start_date,
        "profile_snapshot": {
            "phase_id": phase_id,
            "domain_weights": domain_weights,
            "intensity_cap": cap,
            "allowed_locations": locations,
            "hard_cap_per_week": effective_hard_cap,
        },
        "weeks": [
            {
                "week_index": 1,
                "phase": phase_id,
                "targets": {
                    "hard_days": effective_hard_cap,
                    "finger_days": len(finger_days_dates),
                    "deload_factor": 0.5 if phase_id == "deload" else 1.0,
                },
                "days": plan_days,
            }
        ],
    }

    # Apply deload transformation if deload phase
    if phase_id == "deload":
        week_plan = apply_deload_week(week_plan)

    return week_plan
