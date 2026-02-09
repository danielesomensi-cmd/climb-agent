from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple


STIMULUS_CATEGORIES: Tuple[str, ...] = (
    "finger_strength",
    "boulder_power",
    "endurance",
    "complementaries",
)


def _parse_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_sessions_log_path(user_state: Dict[str, Any]) -> Path:
    history = user_state.get("history_index") or {}
    candidates = history.get("session_log_paths") or []
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.endswith("sessions_2026.jsonl"):
            return Path(candidate)
    if candidates and isinstance(candidates[0], str):
        return Path(candidates[0])
    return Path("data/logs/sessions_2026.jsonl")


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


def load_user_state(path: Path) -> Dict[str, Any]:
    return _parse_json(path)


def save_user_state(path: Path, user_state: Dict[str, Any]) -> None:
    _dump_json(path, user_state)


def _session_categories(session: Dict[str, Any]) -> List[str]:
    sid = str(session.get("session_id") or "")
    intent = str(session.get("intent") or "")
    tags = session.get("tags") or {}
    categories: List[str] = []

    if tags.get("finger") or "finger" in sid or intent == "strength":
        categories.append("finger_strength")
    if "power" in sid or intent == "power":
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


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
