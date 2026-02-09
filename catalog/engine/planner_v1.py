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
    "gym_power_bouldering": SessionSpec("gym_power_bouldering", "power", 2, ("gym",), True, False),
    "gym_power_endurance": SessionSpec("gym_power_endurance", "power_endurance", 2, ("gym",), True, False),
    "gym_aerobic_endurance": SessionSpec("gym_aerobic_endurance", "aerobic_endurance", 3, ("gym", "home"), False, False),
    "gym_technique_boulder": SessionSpec("gym_technique_boulder", "technique", 3, ("gym", "outdoor"), False, False),
    "general_strength_short": SessionSpec("general_strength_short", "accessory", 4, ("home", "gym"), False, False),
    "deload_recovery": SessionSpec("deload_recovery", "recovery", 5, ("home", "gym", "outdoor"), False, False),
}

GYM_EQUIPMENT_REQUIREMENTS: Dict[str, Tuple[str, ...]] = {
    "gym_power_bouldering": ("gym_boulder", "spraywall", "board_kilter"),
}

MODE_QUEUES: Dict[str, Tuple[str, ...]] = {
    "balanced": (
        "strength_long",
        "gym_power_bouldering",
        "gym_power_endurance",
        "gym_aerobic_endurance",
        "gym_technique_boulder",
    ),
    "strength": (
        "strength_long",
        "gym_power_bouldering",
        "strength_long",
        "gym_technique_boulder",
    ),
    "endurance": (
        "strength_long",
        "gym_aerobic_endurance",
        "gym_power_endurance",
        "gym_technique_boulder",
    ),
    "maintenance": (
        "strength_long",
        "gym_technique_boulder",
        "gym_aerobic_endurance",
    ),
}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _weekday_key(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def _default_slots(locations: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    return {
        slot: {
            "available": True,
            "locations": sorted(set(locations)),
            "preferred_location": None,
            "gym_id": None,
        }
        for slot in SLOTS
    }


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
                preferred = slot_value.get("preferred_location")
                if isinstance(preferred, str):
                    default_day[slot]["preferred_location"] = preferred
                gym_id = slot_value.get("gym_id")
                if isinstance(gym_id, str) and gym_id:
                    default_day[slot]["gym_id"] = gym_id
        normalized[wd] = default_day
    return normalized


def _pick_location(
    spec: SessionSpec,
    slot_info: Dict[str, Any],
    allowed_locations: Sequence[str],
) -> Optional[str]:
    slot_locations = slot_info.get("locations") or []
    viable = sorted(set(slot_locations).intersection(spec.locations).intersection(allowed_locations))
    if not viable:
        return None

    preferred_location = slot_info.get("preferred_location")
    if isinstance(preferred_location, str) and preferred_location in viable:
        return preferred_location
    return viable[0]


def _select_default_gym_id(
    *,
    slot_gym_id: Optional[str],
    default_gym_id: Optional[str],
    gyms: Sequence[Dict[str, Any]],
    required_any: Optional[Sequence[str]] = None,
) -> str:
    required = set(required_any or [])

    def _supports(gym: Dict[str, Any]) -> bool:
        if not required:
            return True
        equipment_raw = gym.get("equipment")
        if equipment_raw in (None, []):
            return True
        equipment = set(equipment_raw)
        return bool(equipment.intersection(required))

    by_id = {gym.get("gym_id"): gym for gym in gyms if isinstance(gym.get("gym_id"), str)}

    if slot_gym_id:
        slot_gym = by_id.get(slot_gym_id)
        if slot_gym is None or _supports(slot_gym):
            return slot_gym_id
    if default_gym_id:
        default_gym = by_id.get(default_gym_id)
        if default_gym is None or _supports(default_gym):
            return default_gym_id
    for gym in gyms:
        gym_id = gym.get("gym_id")
        if isinstance(gym_id, str) and gym_id and _supports(gym):
            return gym_id
    if "work_gym" in by_id and _supports(by_id["work_gym"]):
        return "work_gym"
    raise ValueError("Unable to resolve gym_id deterministically for gym location")


def _make_session_entry(spec: SessionSpec, location: str, slot: str, explain: List[str], gym_id: Optional[str]) -> Dict[str, Any]:
    return {
        "slot": slot,
        "session_id": spec.session_id,
        "location": location,
        "gym_id": gym_id,
        "intent": spec.intent,
        "priority": spec.priority,
        "constraints_applied": ["location_allowed", "availability_slot"],
        "tags": {"hard": spec.hard, "finger": spec.finger},
        "explain": explain,
    }


def _availability_summary(normalized: Dict[str, Dict[str, Dict[str, Any]]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    summary: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for wd in WEEKDAYS:
        summary[wd] = {}
        for slot in SLOTS:
            info = normalized[wd][slot]
            summary[wd][slot] = {
                "available": bool(info.get("available", False)),
                "preferred_location": info.get("preferred_location"),
                "gym_id": info.get("gym_id"),
            }
    return summary


def generate_week_plan(
    *,
    start_date: str,
    mode: str = "balanced",
    availability: Optional[Dict[str, Any]] = None,
    allowed_locations: Optional[List[str]] = None,
    hard_cap_per_week: int = 3,
    planning_prefs: Optional[Dict[str, Any]] = None,
    default_gym_id: Optional[str] = None,
    gyms: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if mode not in MODE_QUEUES:
        raise ValueError(f"Unsupported mode: {mode}")

    locations = sorted(set(allowed_locations or ["home", "gym"]))
    normalized = normalize_availability(availability, locations)
    queue = [SESSION_LIBRARY[key] for key in MODE_QUEUES[mode]]
    pref_default_gym_id = default_gym_id or (planning_prefs or {}).get("default_gym_id")

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

            location = _pick_location(candidate, slot_info, locations)
            if location is None:
                continue

            gym_id = None
            if location == "gym":
                required_any = GYM_EQUIPMENT_REQUIREMENTS.get(candidate.session_id)
                gym_id = _select_default_gym_id(
                    slot_gym_id=slot_info.get("gym_id"),
                    default_gym_id=pref_default_gym_id,
                    gyms=gyms or [],
                    required_any=required_any,
                )

            explain = [
                f"mode={mode}",
                f"slot={slot}",
                f"day={day_key}",
                "deterministic queue placement",
            ]
            sessions.append(_make_session_entry(candidate, location, slot, explain, gym_id))
            queue_index += 1
            if candidate.hard:
                hard_days += 1
            if candidate.finger:
                last_finger_date = current_date

            if candidate.hard and day_availability["lunch"]["available"] and len(sessions) < 3:
                accessory = SESSION_LIBRARY["general_strength_short"]
                accessory_slot_info = day_availability["lunch"]
                accessory_location = _pick_location(accessory, accessory_slot_info, locations)
                if accessory_location and slot != "lunch":
                    accessory_gym_id = None
                    if accessory_location == "gym":
                        accessory_gym_id = _select_default_gym_id(
                            slot_gym_id=accessory_slot_info.get("gym_id"),
                            default_gym_id=pref_default_gym_id,
                            gyms=gyms or [],
                        )
                    sessions.append(
                        _make_session_entry(
                            accessory,
                            accessory_location,
                            "lunch",
                            ["optional accessory", "recovery-safe add-on", "deterministic insertion"],
                            accessory_gym_id,
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
            "planning_prefs": {
                "target_training_days_per_week": (planning_prefs or {}).get("target_training_days_per_week"),
                "hard_day_cap_per_week": (planning_prefs or {}).get("hard_day_cap_per_week", hard_cap_per_week),
                "default_gym_id": pref_default_gym_id,
            },
            "availability_summary": _availability_summary(normalized),
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
