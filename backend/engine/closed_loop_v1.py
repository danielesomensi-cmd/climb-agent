from __future__ import annotations

import json
import logging
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

logger = logging.getLogger(__name__)


STIMULUS_CATEGORIES: Tuple[str, ...] = (
    "finger_strength",
    "boulder_power",
    "endurance",
    "complementaries",
)




def ensure_planning_defaults(user_state: Dict[str, Any]) -> Dict[str, Any]:
    state = deepcopy(user_state)
    state["schema_version"] = "1.4"

    equipment = state.setdefault("equipment", {})
    gyms = equipment.setdefault("gyms", [])
    if not any((g or {}).get("gym_id") == "work_gym" for g in gyms if isinstance(g, dict)):
        gyms.append({"gym_id": "work_gym", "name": "Work Gym", "equipment": []})
        gyms.sort(key=lambda g: str((g or {}).get("gym_id") or ""))

    prefs = state.setdefault("planning_prefs", {})
    prefs.setdefault("target_training_days_per_week", 4)
    prefs.setdefault("hard_day_cap_per_week", 3)

    availability = state.setdefault("availability", {})
    weekdays = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    slots = ("morning", "lunch", "evening")
    for wd in weekdays:
        day = availability.setdefault(wd, {})
        for slot in slots:
            slot_entry = day.setdefault(slot, {})
            if not isinstance(slot_entry, dict):
                slot_entry = {"available": bool(slot_entry)}
                day[slot] = slot_entry
            slot_entry.setdefault("available", True)
            slot_entry.setdefault("preferred_location", "home")
            slot_entry.setdefault("gym_id", None)

    recency = state.setdefault("stimulus_recency", {})
    for cat in STIMULUS_CATEGORIES:
        recency.setdefault(cat, {"last_done_date": None, "last_skipped_date": None, "done_count": 0, "skipped_count": 0})

    fatigue = state.setdefault("fatigue_proxy", {})
    fatigue.setdefault("done_sessions_total", 0)
    fatigue.setdefault("skipped_sessions_total", 0)
    fatigue.setdefault("hard_sessions_total", 0)
    fatigue.setdefault("finger_sessions_total", 0)
    fatigue.setdefault("endurance_sessions_total", 0)
    fatigue.setdefault("last_updated_date", None)

    return state



# A291 (R6a): stimulus categories from the catalog's intent.primary_goal.
# The week plan carries intent=None for planned sessions, so the old
# intent-based branch never fired in prod, and the `'power' in sid` substring
# counted power_endurance_gym as boulder_power. Report/data correction only:
# stimulus_recency is read by report_engine and body_part_picker, never by the
# planner.
_PRIMARY_GOAL_CATEGORIES: Dict[str, FrozenSet[str]] = {
    "limit_projecting": frozenset({"boulder_power", "finger_strength"}),
    "contact_strength": frozenset({"boulder_power", "finger_strength"}),
    "finger_max_strength": frozenset({"finger_strength"}),
    # finger_maintenance_*, repeater tests: the substring rule already gave
    # finger_strength — kept.
    "finger_strength_endurance": frozenset({"finger_strength"}),
    "power_endurance": frozenset({"endurance"}),
    "aerobic_capacity": frozenset({"endurance"}),
    "aerobic_endurance": frozenset({"endurance"}),
    # R6a spec ("da confermare"): lead projecting is a long effort at the
    # redpoint, with technique_lead as secondary goal.
    "route_projecting": frozenset({"endurance", "complementaries"}),
}

# The two catalog sessions without intent.primary_goal (R6a: "vanno elencate e
# mappate"). Mapped here rather than editing the catalog, because the resolver
# feeds primary_goal into _intensity_label and adding one would change their
# prescriptions — out of scope for a report fix.
_SESSION_CATEGORY_OVERRIDES: Dict[str, FrozenSet[str]] = {
    "finger_aerobic_base": frozenset({"finger_strength", "endurance"}),
    "finger_endurance_short": frozenset({"finger_strength", "endurance"}),
}

_SESSIONS_DIR = Path(__file__).resolve().parents[1] / "catalog" / "sessions" / "v1"


@lru_cache(maxsize=1)
def _catalog_primary_goals() -> Dict[str, Optional[str]]:
    """session_id → intent.primary_goal (None when the session has none)."""
    out: Dict[str, Optional[str]] = {}
    if not _SESSIONS_DIR.is_dir():
        return out
    for path in sorted(_SESSIONS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        sid = str(data.get("id") or path.stem)
        intent = data.get("intent")
        goal = intent.get("primary_goal") if isinstance(intent, dict) else (intent if isinstance(intent, str) else None)
        out[sid] = str(goal) if goal else None
    return out


def _goal_categories(goal: str) -> List[str]:
    # Every other goal — technique_*, strength_general, core, regeneration,
    # flexibility, pulling_strength, volume_climbing, prehab_*, handstand_skill —
    # is complementaries, which is what the old rule gave those sessions.
    return sorted(_PRIMARY_GOAL_CATEGORIES.get(goal, frozenset({"complementaries"})))


def _session_categories(session: Dict[str, Any]) -> List[str]:
    """Stimulus categories of one session (A291: catalog first).

    1. a catalog session → its intent.primary_goal (or the explicit override
       for the 2 catalog sessions without one);
    2. otherwise an `intent` that is itself a known primary_goal (the
       resolver's pseudo-day passes it as a string);
    3. otherwise the legacy substring/intent rule, for custom/outdoor/unknown
       ids — with 'power' no longer matching 'power_endurance'.
    The planner tag `finger` adds finger_strength in every case, as before.
    """
    sid = str(session.get("session_id") or "")
    intent = str(session.get("intent") or "")
    tags = session.get("tags") or {}

    categories: List[str]
    goals = _catalog_primary_goals()
    if sid in _SESSION_CATEGORY_OVERRIDES:
        categories = sorted(_SESSION_CATEGORY_OVERRIDES[sid])
    elif goals.get(sid):
        categories = _goal_categories(str(goals[sid]))
    elif intent in _PRIMARY_GOAL_CATEGORIES:
        categories = _goal_categories(intent)
    else:
        categories = _legacy_session_categories(sid, intent, tags)
    if tags.get("finger") and "finger_strength" not in categories:
        categories = [*categories, "finger_strength"]
    return sorted(set(categories))


def _legacy_session_categories(sid: str, intent: str, tags: Dict[str, Any]) -> List[str]:
    categories: List[str] = []

    if tags.get("finger") or "finger" in sid or intent == "strength":
        categories.append("finger_strength")
    if "power" in sid.replace("power_endurance", "") or intent == "power":
        categories.append("boulder_power")
    if "endurance" in sid or intent in {"aerobic_endurance", "power_endurance", "endurance"}:
        categories.append("endurance")
    if not categories:
        categories.append("complementaries")
    if "technique" in sid or intent in {"accessory", "recovery", "technique"}:
        categories.append("complementaries")

    return sorted(set(categories))


def build_log_entry(*, resolved_day: Dict[str, Any], status: str, notes: str | None = None, outcomes: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if status not in {"done", "skipped"}:
        raise ValueError("status must be one of: done|skipped")
    date = resolved_day["date"]
    sessions = resolved_day.get("sessions") or []
    session_ids = [str(s.get("session_id") or "") for s in sessions]

    categories = sorted({c for s in sessions for c in _session_categories(s)})
    summary = {
        "session_count": len(sessions),
        "status": status,
        "categories": categories,
        "session_ids": session_ids,
    }
    return {
        "schema_version": "resolved_day_log_entry.v1",
        "log_version": "closed_loop.v1",
        "date": date,
        "status": status,
        "plan_version": (resolved_day.get("plan") or {}).get("plan_version"),
        "start_date": (resolved_day.get("plan") or {}).get("start_date"),
        "location": sessions[0].get("location") if sessions else None,
        "gym_id": sessions[0].get("gym_id") if sessions else None,
        "session_ids": session_ids,
        "resolved_ref": resolved_day.get("resolved_ref"),
        "planned": resolved_day.get("sessions") or [],
        "actual": outcomes or {},
        "actual_feedback_v1": (outcomes or {}).get("exercise_feedback_v1") or [],
        "notes": notes or "",
        "summary": summary,
    }


def apply_day_result_to_user_state(user_state: Dict[str, Any], *, resolved_day: Dict[str, Any], status: str) -> Dict[str, Any]:
    state = ensure_planning_defaults(user_state)
    date = resolved_day["date"]
    sessions = resolved_day.get("sessions") or []

    recency = state["stimulus_recency"]
    fatigue = state["fatigue_proxy"]

    categories = sorted({c for s in sessions for c in _session_categories(s)})
    for cat in categories:
        entry = recency.setdefault(cat, {"last_done_date": None, "last_skipped_date": None, "done_count": 0, "skipped_count": 0})
        if status == "done":
            entry["last_done_date"] = date
            entry["done_count"] = int(entry.get("done_count") or 0) + 1
        else:
            entry["last_skipped_date"] = date
            entry["skipped_count"] = int(entry.get("skipped_count") or 0) + 1

    if status == "done":
        fatigue["done_sessions_total"] = int(fatigue.get("done_sessions_total") or 0) + len(sessions)
        fatigue["hard_sessions_total"] = int(fatigue.get("hard_sessions_total") or 0) + sum(1 for s in sessions if (s.get("tags") or {}).get("hard"))
        fatigue["finger_sessions_total"] = int(fatigue.get("finger_sessions_total") or 0) + sum(1 for s in sessions if (s.get("tags") or {}).get("finger"))
        fatigue["endurance_sessions_total"] = int(fatigue.get("endurance_sessions_total") or 0) + sum(1 for s in sessions if "endurance" in str(s.get("session_id") or ""))
    else:
        fatigue["skipped_sessions_total"] = int(fatigue.get("skipped_sessions_total") or 0) + len(sessions)

    fatigue["last_updated_date"] = date
    return state


