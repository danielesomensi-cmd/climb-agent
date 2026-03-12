"""Weekly override merge utility.

Merges per-week availability overrides with the user's default availability
settings, producing an effective availability dict for the planner.

The override is a *temporary layer* — it never modifies state.availability.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
SLOTS = ("morning", "lunch", "evening")

# Maps brief DayOverride.location to the locations list used by the planner
_LOCATION_MAP = {
    "gym": ["gym"],
    "outdoor": ["outdoor"],
    "home": ["home"],
}


def merge_override_into_availability(
    availability: Optional[Dict[str, Any]],
    override: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return an effective availability dict with override applied.

    *availability* is the user's default settings (never mutated).
    *override* is the weekly override dict (``{days: {monday: {...}, ...}}``).

    Override day keys use full names (``monday``–``sunday``); they are mapped
    to the short keys used by the planner (``mon``–``sun``).

    Only days present in ``override.days`` are modified; missing days keep
    the original defaults.
    """
    base = deepcopy(availability or {})
    if not override:
        return base

    days = override.get("days") or {}
    for long_name, day_override in days.items():
        short = _long_to_short(long_name)
        if short is None:
            continue
        base[short] = _apply_day_override(base.get(short, {}), day_override)
    return base


def build_merged_view(
    availability: Optional[Dict[str, Any]],
    override: Optional[Dict[str, Any]],
    gyms: Optional[list] = None,
) -> list:
    """Build a 7-day merged view (day-level summary) for backwards compat."""
    effective = merge_override_into_availability(availability, override)
    override_days = (override or {}).get("days", {})
    result = []
    for wd in WEEKDAYS:
        long = _short_to_long(wd)
        is_overridden = long in override_days
        day_data = effective.get(wd, {})
        result.append({
            "day": wd,
            **_summarize_day(day_data),
            "is_overridden": is_overridden,
        })
    return result


def build_slot_view(
    availability: Optional[Dict[str, Any]],
    override: Optional[Dict[str, Any]],
    gyms: Optional[list] = None,
) -> List[Dict[str, Any]]:
    """Build a 7-day slot-level view for the GET endpoint.

    Each day includes a ``slots`` array with per-slot availability, plus
    a day-level ``summary`` for compact display and ``is_overridden`` flag.
    """
    effective = merge_override_into_availability(availability, override)
    raw_avail = availability or {}
    override_days = (override or {}).get("days", {})
    result = []
    for wd in WEEKDAYS:
        long = _short_to_long(wd)
        is_overridden = long in override_days
        day_data = effective.get(wd, {})

        # Build default_slots from the *original* (un-merged) availability
        raw_day = raw_avail.get(wd, {})
        default_slots = _extract_slots(raw_day)

        # Check day-level available: False
        if isinstance(day_data.get("available"), bool) and not day_data["available"]:
            result.append({
                "day": wd,
                "available": False,
                "slots": [],
                "default_slots": default_slots,
                "summary": "Rest",
                "is_overridden": is_overridden,
            })
            continue

        slots = []
        for slot_key in SLOTS:
            slot_data = day_data.get(slot_key)
            if not isinstance(slot_data, dict):
                # Slot not configured → include as unavailable (toggleable by user)
                slots.append({
                    "slot": slot_key,
                    "available": False,
                    "location": "home",
                    "gym_id": None,
                })
                continue
            avail = slot_data.get("available", False)
            pref = slot_data.get("preferred_location", "home")
            gym_id = slot_data.get("gym_id")
            location = pref if pref in ("gym", "outdoor", "home") else "home"
            slots.append({
                "slot": slot_key,
                "available": avail,
                "location": location,
                "gym_id": gym_id if location == "gym" else None,
            })

        has_any = any(s["available"] for s in slots)
        summary = _build_summary(slots, gyms) if has_any else "Rest"

        result.append({
            "day": wd,
            "available": has_any,
            "slots": slots,
            "default_slots": default_slots,
            "summary": summary,
            "is_overridden": is_overridden,
        })
    return result


def _build_summary(slots: List[Dict[str, Any]], gyms: Optional[list] = None) -> str:
    """Build a compact summary string from slot data."""
    parts = []
    gym_name_cache: Dict[str, str] = {}
    if gyms:
        for g in gyms:
            gid = g.get("gym_id") or g.get("name", "")
            gym_name_cache[gid] = g.get("name", gid)

    slot_labels = {"morning": "AM", "lunch": "Lunch", "evening": "PM"}

    for s in slots:
        if not s["available"]:
            continue
        loc = s["location"]
        slot_label = slot_labels.get(s["slot"], s["slot"])
        if loc == "gym":
            gid = s.get("gym_id")
            gname = gym_name_cache.get(gid, gid) if gid else "Gym"
            parts.append(f"{gname} {slot_label}")
        elif loc == "outdoor":
            parts.append(f"Outdoor {slot_label}")
        else:
            parts.append(f"Home {slot_label}")

    return ", ".join(parts) if parts else "Rest"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_LONG_TO_SHORT = {
    "monday": "mon", "tuesday": "tue", "wednesday": "wed",
    "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun",
}
_SHORT_TO_LONG = {v: k for k, v in _LONG_TO_SHORT.items()}


def _long_to_short(name: str) -> Optional[str]:
    return _LONG_TO_SHORT.get(name.lower())


def _short_to_long(name: str) -> str:
    return _SHORT_TO_LONG.get(name.lower(), name)


def _apply_day_override(
    base_day: Dict[str, Any],
    day_override: Dict[str, Any],
) -> Dict[str, Any]:
    """Replace a single day's availability based on the override.

    Supports two formats:
    - Day-level rest: ``{available: false}`` → entire day unavailable
    - Slot-level: ``{available: true, slots: {morning: {...}, ...}}`` → per-slot
    """
    available = day_override.get("available", True)

    if not available:
        return {"available": False}

    # Slot-level override
    slot_overrides = day_override.get("slots")
    if slot_overrides:
        result: Dict[str, Any] = {}
        for slot_key in SLOTS:
            if slot_key in slot_overrides:
                so = slot_overrides[slot_key]
                s_avail = so.get("available", True)
                s_loc = so.get("location", "home")
                s_gym = so.get("gym_id")
                locations = _LOCATION_MAP.get(s_loc, ["home"])
                result[slot_key] = {
                    "available": s_avail,
                    "preferred_location": s_loc,
                    "locations": locations,
                    "gym_id": s_gym if s_loc == "gym" else None,
                }
            else:
                # Keep original slot data
                slot_data = base_day.get(slot_key)
                if isinstance(slot_data, dict):
                    result[slot_key] = slot_data
        return result

    # Legacy day-level override (location field) — backwards compat
    location = day_override.get("location", "rest")
    gym_id = day_override.get("gym_id")

    if location == "rest":
        return {"available": False}

    locations = _LOCATION_MAP.get(location, ["home"])
    slots: Dict[str, Any] = {}
    for slot in SLOTS:
        slot_data = base_day.get(slot)
        if isinstance(slot_data, dict) and slot_data.get("available", False):
            slots[slot] = {
                "available": True,
                "preferred_location": location,
                "locations": locations,
                "gym_id": gym_id if location == "gym" else None,
            }
        elif isinstance(slot_data, dict):
            slots[slot] = {
                "available": False,
                "preferred_location": location,
                "locations": locations,
                "gym_id": None,
            }
    if not slots:
        slots["evening"] = {
            "available": True,
            "preferred_location": location,
            "locations": locations,
            "gym_id": gym_id if location == "gym" else None,
        }
    return slots


def _extract_slots(day_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract slot entries from a day's raw availability data.

    Always returns exactly 3 slots (morning, lunch, evening).
    Missing or rest-day slots are returned as ``available=False``.
    """
    is_rest = isinstance(day_data.get("available"), bool) and not day_data["available"]
    slots = []
    for slot_key in SLOTS:
        slot_data = day_data.get(slot_key) if not is_rest else None
        if not isinstance(slot_data, dict):
            slots.append({
                "slot": slot_key,
                "available": False,
                "location": "home",
                "gym_id": None,
            })
            continue
        pref = slot_data.get("preferred_location", "home")
        location = pref if pref in ("gym", "outdoor", "home") else "home"
        slots.append({
            "slot": slot_key,
            "available": slot_data.get("available", False),
            "location": location,
            "gym_id": slot_data.get("gym_id") if location == "gym" else None,
        })
    return slots


def _summarize_day(day_data: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a day's availability into a compact view."""
    if isinstance(day_data.get("available"), bool) and not day_data["available"]:
        return {"available": False, "location": "rest", "gym_id": None}

    has_any_available = False
    location = "home"
    gym_id = None
    for slot in SLOTS:
        slot_data = day_data.get(slot)
        if isinstance(slot_data, dict) and slot_data.get("available", False):
            has_any_available = True
            pref = slot_data.get("preferred_location")
            if pref == "outdoor":
                location = "outdoor"
            elif pref == "gym" or (isinstance(slot_data.get("locations"), list) and "gym" in slot_data["locations"]):
                location = "gym"
                if slot_data.get("gym_id"):
                    gym_id = slot_data["gym_id"]
            elif pref == "other_sport":
                continue
            elif pref == "home" or (isinstance(slot_data.get("locations"), list) and slot_data["locations"] == ["home"]):
                if location != "gym":
                    location = "home"

    if not has_any_available:
        if not any(day_data.get(s) for s in SLOTS):
            return {"available": False, "location": "rest", "gym_id": None}
        return {"available": False, "location": "rest", "gym_id": None}

    return {"available": has_any_available, "location": location, "gym_id": gym_id}
