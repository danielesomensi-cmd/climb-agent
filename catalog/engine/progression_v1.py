from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

FONT_GRADES: List[str] = [
    "5A", "5A+", "5B", "5B+", "5C", "5C+",
    "6A", "6A+", "6B", "6B+", "6C", "6C+",
    "7A", "7A+", "7B", "7B+", "7C", "7C+",
    "8A", "8A+", "8B", "8B+", "8C", "8C+",
]
FONT_GRADE_TO_INDEX = {grade: idx for idx, grade in enumerate(FONT_GRADES)}


def _round_half_step(value: float) -> float:
    return round(value / 0.5) * 0.5


def normalize_font_grade(grade: str | None) -> Optional[str]:
    if grade is None:
        return None
    cleaned = str(grade).strip().upper().replace(" ", "")
    return cleaned if cleaned in FONT_GRADE_TO_INDEX else None


def step_grade(grade: str, steps: int) -> str:
    normalized = normalize_font_grade(grade) or "6C"
    idx = FONT_GRADE_TO_INDEX[normalized] + int(steps)
    idx = max(0, min(len(FONT_GRADES) - 1, idx))
    return FONT_GRADES[idx]


def _extract_grade_benchmark(user_state: Dict[str, Any]) -> str:
    performance = user_state.get("performance") or {}
    preferred = (((performance.get("gym_reference") or {}).get("kilter") or {}).get("benchmark") or {}).get("grade")
    if normalize_font_grade(preferred):
        return normalize_font_grade(preferred) or "6C"

    current_level = performance.get("current_level") or {}
    nested = ((((current_level.get("gym_reference") or {}).get("kilter") or {}).get("benchmark") or {}).get("grade"))
    if normalize_font_grade(nested):
        return normalize_font_grade(nested) or "6C"

    worked = (((current_level.get("boulder") or {}).get("worked") or {}).get("grade"))
    if normalize_font_grade(worked):
        return normalize_font_grade(worked) or "6C"
    return "6C"


def _gym_equipment(user_state: Dict[str, Any], gym_id: str | None) -> List[str]:
    gyms = ((user_state.get("equipment") or {}).get("gyms") or [])
    for gym in gyms:
        if str((gym or {}).get("gym_id") or "").strip().lower() == str(gym_id or "").strip().lower():
            return [str(x).strip().lower() for x in (gym.get("equipment") or []) if str(x).strip()]
    return []


def _surface_options(user_state: Dict[str, Any], gym_id: str | None) -> List[str]:
    allowed = ["board_kilter", "spraywall", "gym_boulder"]
    equip = set(_gym_equipment(user_state, gym_id))
    return [surface for surface in allowed if surface in equip]


def _intensity_label(session: Dict[str, Any]) -> str:
    intent = str(session.get("intent") or "").strip().lower()
    tags = session.get("tags") or {}
    if intent in {"warmup", "technique", "recovery", "accessory"} or tags.get("technique"):
        return "easy"
    if intent in {"power_endurance", "aerobic_endurance", "endurance", "volume"} or tags.get("volume"):
        return "medium"
    return "hard"


def _boulder_offset(session: Dict[str, Any], user_state: Dict[str, Any]) -> int:
    intent = str(session.get("intent") or "").strip().lower()
    tags = session.get("tags") or {}
    cfg = (((user_state.get("progression_config") or {}).get("boulder_targets") or {}).get("offsets") or {})
    if intent in {"warmup", "technique", "recovery", "accessory"} or tags.get("technique"):
        return int(cfg.get("warmup_tech", -2))
    if intent in {"power_endurance", "aerobic_endurance", "endurance", "volume"} or tags.get("volume"):
        return int(cfg.get("volume", -1))
    if intent in {"power", "limit"} or tags.get("hard"):
        return int(cfg.get("limit_power", 0))
    return int(cfg.get("default", -1))


def _find_working_load_entry(user_state: Dict[str, Any], exercise_id: str) -> Dict[str, Any]:
    working = user_state.setdefault("working_loads", {})
    entries = working.setdefault("entries", [])
    for item in entries:
        if str(item.get("exercise_id") or "") == exercise_id:
            return item
    new_item = {"exercise_id": exercise_id, "next_external_load_kg": 0.0}
    entries.append(new_item)
    entries.sort(key=lambda e: str(e.get("exercise_id") or ""))
    return new_item


def _max_hang_suggested(user_state: Dict[str, Any], prescription: Dict[str, Any]) -> Dict[str, Any]:
    bodyweight = float(user_state.get("bodyweight_kg") or ((user_state.get("body") or {}).get("weight_kg") or 0.0))
    intensity = float(prescription.get("intensity_pct_of_total_load") or 0.9)
    baselines = ((user_state.get("baselines") or {}).get("hangboard") or [])
    baseline = baselines[0] if baselines else {}
    max_total = float(baseline.get("max_total_load_kg") or bodyweight)
    target_total = _round_half_step(max_total * intensity)
    suggested_external = _round_half_step(target_total - bodyweight)
    return {
        "schema_version": "progression_targets.v1",
        "suggested_total_load_kg": target_total,
        "suggested_external_load_kg": suggested_external,
        "suggested_rep_scheme": f"{prescription.get('sets', 6)}x{prescription.get('hang_seconds', 5)}s",
    }


def inject_targets(resolved_day: Dict[str, Any], user_state: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(resolved_day)
    out["targets_schema_version"] = "progression_targets.v1"
    benchmark_grade = _extract_grade_benchmark(user_state)

    for session in out.get("sessions") or []:
        intensity = _intensity_label(session)
        offset = _boulder_offset(session, user_state)
        for inst in session.get("exercise_instances") or []:
            ex_id = str(inst.get("exercise_id") or "")
            prescription = inst.get("prescription") or {}
            suggested: Dict[str, Any] = dict(inst.get("suggested") or {})

            if ex_id in {"max_hang_5s", "weighted_pullup", "pullup"}:
                entry = _find_working_load_entry(user_state, ex_id)
                if ex_id == "max_hang_5s":
                    suggested.update(_max_hang_suggested(user_state, prescription))
                else:
                    next_external = float(entry.get("next_external_load_kg") or entry.get("external_load_kg") or 0.0)
                    reps = prescription.get("reps") or (prescription.get("reps_range") or [5])[0]
                    sets = prescription.get("sets") or (prescription.get("sets_range") or [4])[0]
                    suggested.update({
                        "schema_version": "progression_targets.v1",
                        "suggested_external_load_kg": _round_half_step(next_external),
                        "suggested_rep_scheme": f"{sets}x{reps}",
                    })

            if ex_id == "gym_limit_bouldering":
                target_grade = step_grade(benchmark_grade, offset)
                suggested["suggested_boulder_target"] = {
                    "schema_version": "boulder_grade_font_v0",
                    "surface_options": _surface_options(user_state, session.get("gym_id")),
                    "target_grade": target_grade,
                    "intensity_label": intensity,
                }

            if suggested:
                inst["suggested"] = suggested

    return out


def _rule_midpoint_pct(user_state: Dict[str, Any], label: str) -> float:
    rules = (((user_state.get("working_loads") or {}).get("rules") or {}).get("adjustment_policy") or {})
    policy = rules.get(label) or {}
    pct_range = policy.get("pct_range") or [0.0, 0.0]
    if len(pct_range) != 2:
        return 0.0
    return float(pct_range[0] + pct_range[1]) / 2.0


def apply_feedback(log_entry: Dict[str, Any], user_state: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(user_state)
    actual = log_entry.get("actual") or {}
    feedback_items = actual.get("exercise_feedback_v1") or []
    date_value = str(log_entry.get("date") or "")

    for item in feedback_items:
        exercise_id = str(item.get("exercise_id") or "").strip()
        if not exercise_id:
            continue
        feedback_label = str(item.get("feedback_label") or "ok").strip().lower()
        if feedback_label not in {"very_easy", "easy", "ok", "hard", "very_hard"}:
            feedback_label = "ok"

        base_load = item.get("used_external_load_kg")
        if base_load is None:
            base_load = item.get("used_load_kg")
        if base_load is None:
            continue

        base = float(base_load)
        pct = _rule_midpoint_pct(updated, feedback_label)
        next_load = _round_half_step(base * (1.0 + pct))

        entry = _find_working_load_entry(updated, exercise_id)
        entry.update(
            {
                "exercise_id": exercise_id,
                "last_completed": bool(item.get("completed", False)),
                "last_feedback": feedback_label,
                "last_external_load_kg": _round_half_step(base),
                "next_external_load_kg": next_load,
                "updated_at": date_value,
            }
        )

    return updated
