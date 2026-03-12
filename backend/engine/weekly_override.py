"""Weekly override merge utility.

Merges per-week availability overrides with the user's default availability
settings, producing an effective availability dict for the planner.

The override is a *temporary layer* — it never modifies state.availability.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

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
    """Build a 7-day merged view for the GET endpoint.

    Returns a list of 7 dicts (Monday→Sunday), each with:
      - ``day``: short weekday key
      - ``available``: bool
      - ``location``: "gym" | "outdoor" | "home" | "rest"
      - ``gym_id``: str | None
      - ``is_overridden``: bool
    """
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
    """Replace a single day's availability based on the override."""
    available = day_override.get("available", True)
    location = day_override.get("location", "rest")
    gym_id = day_override.get("gym_id")

    if not available or location == "rest":
        return {"available": False}

    locations = _LOCATION_MAP.get(location, ["home"])

    # Build all slots with the override values
    slots: Dict[str, Any] = {}
    for slot in ("morning", "lunch", "evening"):
        slot_data = base_day.get(slot)
        if isinstance(slot_data, dict) and slot_data.get("available", False):
            slots[slot] = {
                "available": True,
                "preferred_location": location,
                "locations": locations,
                "gym_id": gym_id if location == "gym" else None,
            }
        elif isinstance(slot_data, dict):
            # Slot was not available in defaults — keep it unavailable
            slots[slot] = {
                "available": False,
                "preferred_location": location,
                "locations": locations,
                "gym_id": None,
            }
    # If base_day had no explicit slots (legacy format), create evening slot
    if not slots:
        slots["evening"] = {
            "available": True,
            "preferred_location": location,
            "locations": locations,
            "gym_id": gym_id if location == "gym" else None,
        }
    return slots


def _summarize_day(day_data: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a day's availability into a compact view."""
    # Day-level available: False
    if isinstance(day_data.get("available"), bool) and not day_data["available"]:
        return {"available": False, "location": "rest", "gym_id": None}

    # Check slots
    has_any_available = False
    location = "home"
    gym_id = None
    for slot in ("morning", "lunch", "evening"):
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
                continue  # skip other sport slots
            elif pref == "home" or (isinstance(slot_data.get("locations"), list) and slot_data["locations"] == ["home"]):
                if location != "gym":
                    location = "home"

    if not has_any_available:
        # Check if day has no slots at all (could be legacy {available: True} without slots)
        if not any(day_data.get(s) for s in ("morning", "lunch", "evening")):
            return {"available": False, "location": "rest", "gym_id": None}
        return {"available": False, "location": "rest", "gym_id": None}

    return {"available": has_any_available, "location": location, "gym_id": gym_id}
