"""Shared helpers for per-day "other activities" (B276).

Historically each day of a week plan carried a *single* other activity, stored
as flat scalar fields (``other_activity``, ``other_activity_name``,
``other_activity_slot`` …). B276 introduces support for **multiple** other
activities per day (up to one per slot: morning / lunch / evening), stored as a
list under ``other_activities``:

    day["other_activities"] = [
        {"slot": "lunch",   "name": "Chest", "status": "completed",
         "feedback": "ok", "load": 40, "duration_minutes": 45},
        {"slot": "evening", "name": "HIIT"},
    ]

These helpers provide a single reading surface that transparently supports both
the new list form and the legacy scalar form, so preserved (immutable) past
days written before B276 keep rendering/reporting correctly without mutation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Canonical slot ordering for other activities (mirrors planner SLOTS).
OTHER_ACTIVITY_SLOTS = ("morning", "lunch", "evening")

# Legacy scalar field names (pre-B276). Kept for read-fallback + cleanup.
_LEGACY_SCALAR_FIELDS = (
    "other_activity",
    "other_activity_name",
    "other_activity_slot",
    "other_activity_status",
    "other_activity_feedback",
    "other_activity_load",
    "other_activity_duration_minutes",
)


def normalize_other_activities(day: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the day's other activities as a list of item dicts (non-mutating).

    Prefers the new ``other_activities`` list; falls back to synthesizing a
    single-item list from legacy scalar fields for pre-B276 days. Returns an
    empty list when the day has no other activity.
    """
    items = day.get("other_activities")
    if isinstance(items, list):
        return items
    if day.get("other_activity"):
        item: Dict[str, Any] = {}
        if day.get("other_activity_slot") is not None:
            item["slot"] = day.get("other_activity_slot")
        if day.get("other_activity_name") is not None:
            item["name"] = day.get("other_activity_name")
        if day.get("other_activity_status") is not None:
            item["status"] = day.get("other_activity_status")
        if day.get("other_activity_feedback") is not None:
            item["feedback"] = day.get("other_activity_feedback")
        if day.get("other_activity_load") is not None:
            item["load"] = day.get("other_activity_load")
        if day.get("other_activity_duration_minutes") is not None:
            item["duration_minutes"] = day.get("other_activity_duration_minutes")
        return [item]
    return []


def day_has_other_activity(day: Dict[str, Any]) -> bool:
    """True if the day carries at least one other activity (list or legacy)."""
    return bool(normalize_other_activities(day))


def other_activity_slots(day: Dict[str, Any]) -> List[str]:
    """Slots occupied by other activities on this day (skips slot-less items)."""
    return [it["slot"] for it in normalize_other_activities(day) if it.get("slot")]


def other_activity_total_load(day: Dict[str, Any]) -> int:
    """Sum of ``load`` across the day's other activities (0 when none)."""
    return sum(int(it.get("load") or 0) for it in normalize_other_activities(day))


def _sort_key(item: Dict[str, Any]) -> int:
    slot = item.get("slot")
    try:
        return OTHER_ACTIVITY_SLOTS.index(slot)
    except ValueError:
        return len(OTHER_ACTIVITY_SLOTS)


def sort_other_activities(items: List[Dict[str, Any]]) -> None:
    """Sort a list of activity items by slot order, in place."""
    items.sort(key=_sort_key)


def ensure_other_activities_list(day: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the day's mutable ``other_activities`` list, migrating in place.

    If the day still uses legacy scalar fields, they are converted to a
    single-item list and the scalar keys are stripped so there is exactly one
    canonical representation (prevents double-counting). Called only from
    mutation paths (event handlers) — read paths use ``normalize_*`` instead so
    preserved past days are never mutated.
    """
    items = day.get("other_activities")
    if not isinstance(items, list):
        items = normalize_other_activities(day)
        day["other_activities"] = items
        for key in _LEGACY_SCALAR_FIELDS:
            day.pop(key, None)
    return items


def select_activity(
    items: List[Dict[str, Any]], slot: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Pick the activity item to act on.

    With an explicit *slot*, returns the matching item. Without a slot, returns
    the sole item when unambiguous (single-activity days / legacy callers) or
    ``None`` when the day has zero or multiple activities.
    """
    if slot:
        return next((it for it in items if it.get("slot") == slot), None)
    if len(items) == 1:
        return items[0]
    return None
