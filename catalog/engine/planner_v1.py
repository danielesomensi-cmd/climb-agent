from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

SLOTS: Tuple[str, ...] = ("morning", "lunch", "evening")
WEEKDAYS: Tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class SessionSpec:
    session_id: str
    intent: str
    priority: int
    locations: Tuple[str, ...]
    hard: bool
    finger: bool


SESSION_LIBRARY: Dict[str, SessionSpec] = {
    "strength_long": SessionSpec("strength_long", "strength", 1, ("gym", "home"), True, True),
    "blocx_power_bouldering": SessionSpec("blocx_power_bouldering", "power", 2, ("gym",), True, False),
    "blocx_power_endurance": SessionSpec("blocx_power_endurance", "power_endurance", 2, ("gym",), True, False),
    "blocx_aerobic_endurance": SessionSpec("blocx_aerobic_endurance", "aerobic_endurance", 3, ("gym", "home"), False, False),
    "blocx_technique_boulder": SessionSpec("blocx_technique_boulder", "technique", 3, ("gym", "outdoor"), False, False),
    "general_strength_short": SessionSpec("general_strength_short", "accessory", 4, ("home", "gym"), False, False),
    "deload_recovery": SessionSpec("deload_recovery", "recovery", 5, ("home", "gym", "outdoor"), False, False),
}

MODE_QUEUES: Dict[str, Tuple[str, ...]] = {
    "balanced": (
        "strength_long",
        "blocx_power_bouldering",
        "blocx_power_endurance",
        "blocx_aerobic_endurance",
        "blocx_technique_boulder",
    ),
    "strength": (
        "strength_long",
        "blocx_power_bouldering",
        "strength_long",
        "blocx_technique_boulder",
    ),
    "endurance": (
        "strength_long",
        "blocx_aerobic_endurance",
        "blocx_power_endurance",
        "blocx_technique_boulder",
    ),
    "maintenance": (
        "strength_long",
        "blocx_technique_boulder",
        "blocx_aerobic_endurance",
    ),
}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _weekday_key(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def _default_slots(locations: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    return {slot: {"available": True, "locations": sorted(set(locations))} for slot in SLOTS}


def normalize_availability(availability: Optional[Dict[str, Any]], allowed_locations: Sequence[str]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    normalized: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for wd in WEEKDAYS:
        day = (availability or {}).get(wd) or {}
        default_day = _default_slots(allowed_locations)
        if isinstance(day, dict) and day.get("available") is False:
            for slot in SLOTS:
                default_day[slot]["available"] = False
            normalized[wd] = default_day
            continue
        for slot in SLOTS:
            slot_value = day.get(slot)
            if slot_value is None:
                continue
            if isinstance(slot_value, bool):
                default_day[slot]["available"] = slot_value
            elif isinstance(slot_value, dict):
                default_day[slot]["available"] = bool(slot_value.get("available", True))
                if "locations" in slot_value and isinstance(slot_value["locations"], list):
                    default_day[slot]["locations"] = sorted(set(slot_value["locations"]))
        normalized[wd] = default_day
    return normalized


def _pick_location(spec: SessionSpec, slot_locations: Sequence[str], allowed_locations: Sequence[str]) -> Optional[str]:
    viable = sorted(set(slot_locations).intersection(spec.locations).intersection(allowed_locations))
    return viable[0] if viable else None


def _make_session_entry(spec: SessionSpec, location: str, slot: str, explain: List[str]) -> Dict[str, Any]:
    return {
        "slot": slot,
        "session_id": spec.session_id,
        "location": location,
        "intent": spec.intent,
        "priority": spec.priority,
        "constraints_applied": ["location_allowed", "availability_slot"],
        "tags": {"hard": spec.hard, "finger": spec.finger},
        "explain": explain,
    }


def generate_week_plan(
    *,
    start_date: str,
    mode: str = "balanced",
    availability: Optional[Dict[str, Any]] = None,
    allowed_locations: Optional[List[str]] = None,
    hard_cap_per_week: int = 3,
) -> Dict[str, Any]:
    if mode not in MODE_QUEUES:
        raise ValueError(f"Unsupported mode: {mode}")

    locations = sorted(set(allowed_locations or ["home", "gym"]))
    normalized = normalize_availability(availability, locations)
    queue = [SESSION_LIBRARY[key] for key in MODE_QUEUES[mode]]

    plan_days: List[Dict[str, Any]] = []
    start = _parse_date(start_date)
    hard_days = 0
    last_finger_date: Optional[date] = None
    queue_index = 0

    for offset in range(7):
        current_date = start + timedelta(days=offset)
        day_key = _weekday_key(current_date)
        day_availability = normalized[day_key]
        sessions: List[Dict[str, Any]] = []

        for slot in ("evening", "morning", "lunch"):
            if len(sessions) >= 3 or queue_index >= len(queue):
                break
            slot_info = day_availability[slot]
            if not slot_info["available"]:
                continue

            candidate = queue[queue_index]
            if candidate.hard and hard_days >= hard_cap_per_week:
                queue_index += 1
                continue
            if candidate.finger and last_finger_date and (current_date - last_finger_date).days <= 1:
                continue

            location = _pick_location(candidate, slot_info["locations"], locations)
            if location is None:
                continue

            explain = [
                f"mode={mode}",
                f"slot={slot}",
                f"day={day_key}",
                "deterministic queue placement",
            ]
            sessions.append(_make_session_entry(candidate, location, slot, explain))
            queue_index += 1
            if candidate.hard:
                hard_days += 1
            if candidate.finger:
                last_finger_date = current_date

            if candidate.hard and day_availability["lunch"]["available"] and len(sessions) < 3:
                accessory = SESSION_LIBRARY["general_strength_short"]
                accessory_location = _pick_location(accessory, day_availability["lunch"]["locations"], locations)
                if accessory_location and slot != "lunch":
                    sessions.append(
                        _make_session_entry(
                            accessory,
                            accessory_location,
                            "lunch",
                            ["optional accessory", "recovery-safe add-on", "deterministic insertion"],
                        )
                    )

        plan_days.append({"date": current_date.isoformat(), "weekday": day_key, "sessions": sessions})

    return {
        "plan_version": "planner.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": start_date,
        "profile_snapshot": {
            "mode": mode,
            "allowed_locations": locations,
            "hard_cap_per_week": hard_cap_per_week,
        },
        "weeks": [
            {
                "week_index": 1,
                "phase": "build",
                "targets": {"hard_days": hard_cap_per_week, "finger_days": 1, "deload_factor": 1.0},
                "days": plan_days,
            }
        ],
    }
