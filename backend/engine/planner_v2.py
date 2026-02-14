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
# climbing: True for climbing-related sessions (placed first in pass 1)
_SESSION_META: Dict[str, Dict[str, Any]] = {
    "strength_long": {"hard": True, "finger": True, "intensity": "max", "climbing": True, "location": ("gym", "home")},
    "power_contact_gym": {"hard": True, "finger": False, "intensity": "max", "climbing": True, "location": ("gym",)},
    "power_endurance_gym": {"hard": True, "finger": False, "intensity": "high", "climbing": True, "location": ("gym",)},
    "endurance_aerobic_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",)},
    "technique_focus_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",)},
    "finger_strength_home": {"hard": True, "finger": True, "intensity": "max", "climbing": True, "location": ("home",)},
    "prehab_maintenance": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym")},
    "flexibility_full": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym")},
    "yoga_recovery": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home",)},
    "handstand_practice": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym")},
    "complementary_conditioning": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym")},
    "regeneration_easy": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym", "outdoor")},
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


def _is_primary_session(meta: Dict[str, Any]) -> bool:
    """A session is primary if it's hard or climbing-related."""
    return bool(meta.get("hard") or meta.get("climbing"))


def _find_best_slot(
    day_availability: Dict[str, Dict[str, Any]],
    meta: Dict[str, Any],
    locations: Sequence[str],
    prefer_evening: bool = True,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Find the best available slot for a session on a given day.

    Primary sessions prefer evening > morning > lunch.
    Complementary sessions prefer lunch > morning > evening.
    """
    if prefer_evening:
        slot_order = ("evening", "morning", "lunch")
    else:
        slot_order = ("lunch", "morning", "evening")

    for slot in slot_order:
        slot_info = day_availability[slot]
        if not slot_info["available"]:
            continue
        location = _pick_location(meta["location"], slot_info, locations)
        if location is not None:
            return slot, slot_info
    return None


def _make_session_entry(
    slot: str,
    sid: str,
    meta: Dict[str, Any],
    slot_info: Dict[str, Any],
    locations: Sequence[str],
    phase_id: str,
    day_key: str,
    default_gym_id: Optional[str],
    gyms: Sequence[Dict[str, Any]],
    pass_label: str,
) -> Dict[str, Any]:
    """Build a session entry dict for the week plan."""
    location = _pick_location(meta["location"], slot_info, locations)
    gym_id = None
    if location == "gym":
        gym_id = _select_gym_id(slot_info, default_gym_id, gyms)

    return {
        "slot": slot,
        "session_id": sid,
        "location": location,
        "gym_id": gym_id,
        "phase_id": phase_id,
        "intensity": meta["intensity"],
        "tags": {"hard": meta["hard"], "finger": meta["finger"]},
        "explain": [
            f"phase={phase_id}",
            f"slot={slot}",
            f"day={day_key}",
            pass_label,
        ],
    }


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

    Uses a 2-pass algorithm:
      PASS 1: Place primary sessions (hard + climbing-related) with spacing constraints.
      PASS 2: Fill remaining days with complementary sessions.
    Both passes cycle through the pool (max 2 full cycles per pass).

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

    if phase_id == "deload":
        effective_hard_cap = 0

    # Filter session pool by intensity cap and available metadata
    filtered_pool: List[str] = []
    for sid in session_pool:
        meta = _SESSION_META.get(sid)
        if meta is None:
            continue
        if not _intensity_allowed(meta["intensity"], cap):
            continue
        filtered_pool.append(sid)

    # Split into primary (hard/climbing) and complementary pools
    primary_pool = [s for s in filtered_pool if _is_primary_session(_SESSION_META[s])]
    complementary_pool = [s for s in filtered_pool if not _is_primary_session(_SESSION_META[s])]

    start = _parse_date(start_date)
    target_days = prefs.get("target_training_days_per_week", 4)

    # Build day structures
    day_dates: List[date] = [start + timedelta(days=i) for i in range(7)]
    day_keys: List[str] = [_weekday_key(d) for d in day_dates]
    day_sessions: List[List[Dict[str, Any]]] = [[] for _ in range(7)]

    # Track constraints
    hard_days = 0
    finger_day_offsets: List[int] = []
    hard_day_offsets: List[int] = []

    # Determine which days have available slots
    day_has_available_slot: List[bool] = []
    for offset in range(7):
        day_avail = normalized[day_keys[offset]]
        has_slot = any(day_avail[slot]["available"] for slot in SLOTS)
        day_has_available_slot.append(has_slot)

    # ── PASS 1: Place primary sessions (climbing-first) ──
    primary_idx = 0
    primary_uses = 0
    max_primary_uses = len(primary_pool) * 2 if primary_pool else 0  # max 2 cycles

    for offset in range(7):
        if not day_has_available_slot[offset]:
            continue
        if not primary_pool:
            break
        if primary_uses >= max_primary_uses:
            break

        sid = primary_pool[primary_idx % len(primary_pool)]
        meta = _SESSION_META[sid]

        # Hard day cap
        if meta["hard"] and hard_days >= effective_hard_cap:
            primary_idx += 1
            primary_uses += 1
            # Try next session in same day
            if primary_uses < max_primary_uses:
                sid = primary_pool[primary_idx % len(primary_pool)]
                meta = _SESSION_META[sid]
                if meta["hard"] and hard_days >= effective_hard_cap:
                    continue  # Skip this day for primary
            else:
                continue

        # No consecutive finger days (48h gap)
        if meta["finger"] and finger_day_offsets:
            last_finger_offset = finger_day_offsets[-1]
            if (offset - last_finger_offset) <= 1:
                continue

        # No consecutive hard/max-intensity days
        if meta["hard"] and hard_day_offsets:
            last_hard_offset = hard_day_offsets[-1]
            if (offset - last_hard_offset) <= 1:
                continue

        day_avail = normalized[day_keys[offset]]
        result = _find_best_slot(day_avail, meta, locations, prefer_evening=True)
        if result is None:
            continue

        slot, slot_info = result
        entry = _make_session_entry(
            slot, sid, meta, slot_info, locations, phase_id, day_keys[offset],
            default_gym_id, gyms or [], "pass1:primary",
        )
        day_sessions[offset].append(entry)
        primary_idx += 1
        primary_uses += 1

        if meta["hard"]:
            hard_days += 1
            hard_day_offsets.append(offset)
        if meta["finger"]:
            finger_day_offsets.append(offset)

    # ── PASS 2: Fill remaining days with complementary sessions ──
    days_with_sessions = sum(1 for ds in day_sessions if ds)
    comp_idx = 0
    comp_uses = 0
    max_comp_uses = len(complementary_pool) * 2 if complementary_pool else 0

    for offset in range(7):
        if days_with_sessions >= target_days:
            break
        if day_sessions[offset]:
            continue  # Already has a session from pass 1
        if not day_has_available_slot[offset]:
            continue
        if not complementary_pool:
            break
        if comp_uses >= max_comp_uses:
            break

        sid = complementary_pool[comp_idx % len(complementary_pool)]
        meta = _SESSION_META[sid]

        day_avail = normalized[day_keys[offset]]
        result = _find_best_slot(day_avail, meta, locations, prefer_evening=False)
        if result is None:
            continue

        slot, slot_info = result
        entry = _make_session_entry(
            slot, sid, meta, slot_info, locations, phase_id, day_keys[offset],
            default_gym_id, gyms or [], "pass2:complementary",
        )
        day_sessions[offset].append(entry)
        comp_idx += 1
        comp_uses += 1
        days_with_sessions += 1

    # Build plan_days
    plan_days: List[Dict[str, Any]] = []
    for offset in range(7):
        plan_days.append({
            "date": day_dates[offset].isoformat(),
            "weekday": day_keys[offset],
            "sessions": day_sessions[offset],
        })

    finger_days_count = len(finger_day_offsets)
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
                    "finger_days": finger_days_count,
                    "deload_factor": 0.5 if phase_id == "deload" else 1.0,
                },
                "days": plan_days,
            }
        ],
    }

    if phase_id == "deload":
        week_plan = apply_deload_week(week_plan)

    return week_plan
