from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from catalog.engine.planner_v1 import SESSION_LIBRARY

INTENT_TO_SESSION = {
    "rest": "deload_recovery",
    "recovery": "deload_recovery",
    "technique": "gym_technique_boulder",
    "strength": "strength_long",
    "power": "gym_power_bouldering",
    "power_endurance": "gym_power_endurance",
    "aerobic_endurance": "gym_aerobic_endurance",
}


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
