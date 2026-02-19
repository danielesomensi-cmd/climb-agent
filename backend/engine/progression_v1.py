from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

FONT_GRADES: List[str] = [
    "5A", "5A+", "5B", "5B+", "5C", "5C+",
    "6A", "6A+", "6B", "6B+", "6C", "6C+",
    "7A", "7A+", "7B", "7B+", "7C", "7C+",
    "8A", "8A+", "8B", "8B+", "8C", "8C+",
]
FONT_GRADE_TO_INDEX = {grade: idx for idx, grade in enumerate(FONT_GRADES)}
LOAD_BASED_EXERCISES = {"max_hang_5s", "weighted_pullup", "pullup"}
GRADE_BASED_EXERCISES = {"limit_bouldering"}
SURFACE_PRIORITY = ("board_kilter", "spraywall", "gym_boulder")
VALID_FEEDBACK = {"very_easy", "easy", "ok", "hard", "very_hard"}
LEGACY_DIFFICULTY_MAP = {
    "too_easy": "very_easy",
    "easy": "easy",
    "ok": "ok",
    "hard": "hard",
    "too_hard": "very_hard",
    "fail": "very_hard",
}



def canonical_feedback_label(item: Dict[str, Any]) -> str:
    feedback = str(item.get("feedback_label") or "").strip().lower()
    if feedback in VALID_FEEDBACK:
        return feedback

    legacy = str(item.get("difficulty") or item.get("difficulty_label") or "").strip().lower()
    if legacy in LEGACY_DIFFICULTY_MAP:
        return LEGACY_DIFFICULTY_MAP[legacy]

    if bool(item.get("too_hard")) or bool(item.get("fail")):
        return "very_hard"

    return "ok"


def _round_half_step(value: float) -> float:
    return round(value / 0.5) * 0.5


def _parse_day(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _is_fresh(updated_at: str | None, target_date: str | None, freshness_days: int) -> bool:
    updated = _parse_day(updated_at)
    target = _parse_day(target_date)
    if updated is None or target is None:
        return False
    delta = (target - updated).days
    return 0 <= delta <= freshness_days


def _relevant_setup(exercise_id: str, source: Dict[str, Any]) -> Dict[str, Any]:
    if exercise_id == "max_hang_5s":
        return {
            "edge_mm": source.get("edge_mm"),
            "grip": source.get("grip"),
            "load_method": source.get("load_method"),
        }
    if exercise_id == "limit_bouldering":
        return {"surface": source.get("surface_selected") or source.get("surface")}
    return {}


def _progression_setup_and_key(exercise_id: str, source: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    setup = _relevant_setup(exercise_id, source)
    return setup, _setup_key(exercise_id, setup)


def _setup_key(exercise_id: str, setup: Dict[str, Any]) -> str:
    if exercise_id == "max_hang_5s":
        pairs = [
            ("edge_mm", setup.get("edge_mm")),
            ("grip", setup.get("grip")),
            ("load_method", setup.get("load_method")),
        ]
    elif exercise_id == "limit_bouldering":
        pairs = [("surface", setup.get("surface"))]
    else:
        pairs = []
    serialized = "|".join(f"{k}={str(v)}" for k, v in pairs if v not in (None, ""))
    return f"{exercise_id}|{serialized}" if serialized else exercise_id


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
    equip = set(_gym_equipment(user_state, gym_id))
    return [surface for surface in SURFACE_PRIORITY if surface in equip]


def _select_surface(*, preferred: str | None, options: List[str], gym_id: str | None, user_state: Dict[str, Any]) -> str:
    normalized = str(preferred or "").strip().lower()
    if normalized in SURFACE_PRIORITY:
        return normalized
    if options:
        return options[0]
    gym_equip = set(_gym_equipment(user_state, gym_id))
    for surface in SURFACE_PRIORITY:
        if surface in gym_equip:
            return surface
    return "gym_boulder"


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


def _working_entries(user_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    working = user_state.setdefault("working_loads", {})
    return working.setdefault("entries", [])


def _find_working_load_entry(user_state: Dict[str, Any], exercise_id: str, setup: Dict[str, Any]) -> Dict[str, Any]:
    _, key = _progression_setup_and_key(exercise_id, setup)
    entries = _working_entries(user_state)
    for item in entries:
        if str(item.get("key") or "") == key:
            return item
    new_item = {"exercise_id": exercise_id, "key": key, "setup": setup}
    entries.append(new_item)
    entries.sort(key=lambda e: str(e.get("key") or ""))
    return new_item


def _best_entry(user_state: Dict[str, Any], exercise_id: str, setup: Dict[str, Any], date_value: str, freshness_days: int = 60) -> Optional[Dict[str, Any]]:
    _, key = _progression_setup_and_key(exercise_id, setup)
    fresh_matching: List[Dict[str, Any]] = []
    fresh_by_exercise: List[Dict[str, Any]] = []
    for item in _working_entries(user_state):
        if str(item.get("exercise_id") or "") != exercise_id:
            continue
        if not _is_fresh(item.get("updated_at"), date_value, freshness_days):
            continue
        fresh_by_exercise.append(item)
        if str(item.get("key") or "") == key:
            fresh_matching.append(item)

    if fresh_matching:
        fresh_matching.sort(key=lambda e: (str(e.get("updated_at") or ""), str(e.get("key") or "")), reverse=True)
        return fresh_matching[0]

    meaningful_setup = any(v not in (None, "") for v in setup.values())
    if not meaningful_setup and len(fresh_by_exercise) == 1:
        return fresh_by_exercise[0]
    return None


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

            if ex_id in LOAD_BASED_EXERCISES:
                if ex_id == "max_hang_5s":
                    suggested.update(_max_hang_suggested(user_state, prescription))
                    inject_source = dict(prescription)
                    inject_source.update(inst.get("suggested") or {})
                    setup, _ = _progression_setup_and_key(ex_id, inject_source)
                    entry = _best_entry(user_state, ex_id, setup, out.get("date") or "")
                    bodyweight = float(user_state.get("bodyweight_kg") or ((user_state.get("body") or {}).get("weight_kg") or 0.0))

                    if entry and entry.get("next_external_load_kg") is not None:
                        external = _round_half_step(float(entry["next_external_load_kg"]))
                        suggested["suggested_external_load_kg"] = external
                        suggested["suggested_total_load_kg"] = _round_half_step(bodyweight + external)
                    elif entry and entry.get("next_total_load_kg") is not None:
                        total = _round_half_step(float(entry["next_total_load_kg"]))
                        suggested["suggested_total_load_kg"] = total
                        suggested["suggested_external_load_kg"] = _round_half_step(total - bodyweight)
                    elif entry and str(entry.get("last_feedback_label") or "") in {"hard", "very_hard"}:
                        pct = _rule_midpoint_pct(user_state, str(entry.get("last_feedback_label") or "ok"))
                        next_external = _round_half_step(float(suggested.get("suggested_external_load_kg") or 0.0) * (1.0 + pct))
                        suggested["suggested_external_load_kg"] = next_external
                        suggested["suggested_total_load_kg"] = _round_half_step(bodyweight + next_external)
                        write_entry = _find_working_load_entry(user_state, ex_id, setup)
                        write_entry["next_external_load_kg"] = next_external
                        write_entry["updated_at"] = out.get("date")
                else:
                    entry = _best_entry(user_state, ex_id, {}, out.get("date") or "")
                    next_external = float((entry or {}).get("next_external_load_kg") or 0.0)
                    reps = prescription.get("reps") or (prescription.get("reps_range") or [5])[0]
                    sets = prescription.get("sets") or (prescription.get("sets_range") or [4])[0]
                    suggested.update({
                        "schema_version": "progression_targets.v1",
                        "suggested_external_load_kg": _round_half_step(next_external),
                        "suggested_rep_scheme": f"{sets}x{reps}",
                    })

            if ex_id == "limit_bouldering":
                options = _surface_options(user_state, session.get("gym_id"))
                selected_surface = _select_surface(preferred=None, options=options, gym_id=session.get("gym_id"), user_state=user_state)
                target_grade = step_grade(benchmark_grade, offset)
                grade_entry = _best_entry(
                    user_state,
                    ex_id,
                    {"surface": selected_surface},
                    out.get("date") or "",
                )
                if grade_entry and normalize_font_grade(grade_entry.get("next_target_grade")):
                    target_grade = grade_entry["next_target_grade"]
                suggested["suggested_boulder_target"] = {
                    "schema_version": "boulder_grade_font_v0",
                    "surface_options": options,
                    "surface_selected": selected_surface,
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


def _grade_delta_for_feedback(label: str) -> int:
    return {
        "very_easy": 2,
        "easy": 1,
        "ok": 0,
        "hard": -1,
        "very_hard": -2,
    }.get(label, 0)


def _flatten_planned_instances(log_entry: Dict[str, Any]) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for session in log_entry.get("planned") or []:
        for inst in session.get("exercise_instances") or []:
            pairs.append((session, inst))
    return pairs


def _lookup_planned_instance(log_entry: Dict[str, Any], exercise_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    for session, inst in _flatten_planned_instances(log_entry):
        if str(inst.get("exercise_id") or "") == exercise_id:
            return session, inst
    return {}, {}


def _ensure_test_queue(user_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    queue = user_state.setdefault("test_queue", [])
    if not isinstance(queue, list):
        queue = []
        user_state["test_queue"] = queue
    return queue


def _enqueue_test(user_state: Dict[str, Any], *, test_id: str, date_value: str, offset_days: int, reason: str) -> None:
    queue = _ensure_test_queue(user_state)
    created = _parse_day(date_value)
    by_date = (created + timedelta(days=offset_days)).date().isoformat() if created else date_value

    dedupe_window_days = 21
    for item in queue:
        if str(item.get("test_id") or "") != test_id:
            continue
        existing_created = _parse_day(str(item.get("created_at") or ""))
        if created is None or existing_created is None:
            if str(item.get("created_at") or "") == date_value:
                return
            continue
        if abs((created - existing_created).days) <= dedupe_window_days:
            return
    queue.append(
        {
            "test_id": test_id,
            "recommended_by_date": by_date,
            "reason": reason,
            "created_at": date_value,
        }
    )
    queue.sort(key=lambda x: (str(x.get("recommended_by_date") or ""), str(x.get("test_id") or ""), str(x.get("created_at") or "")))


def _update_test_from_log(log_entry: Dict[str, Any], updated: Dict[str, Any], bodyweight: float) -> None:
    planned_sessions = log_entry.get("planned") or []
    feedback_items = ((log_entry.get("actual") or {}).get("exercise_feedback_v1") or [])
    test_sessions = [s for s in planned_sessions if str(s.get("session_id") or "").startswith("test_") or bool((s.get("tags") or {}).get("test"))]
    if not test_sessions:
        return
    for item in feedback_items:
        if str(item.get("exercise_id") or "") != "max_hang_5s":
            continue
        used_total = item.get("used_total_load_kg")
        if used_total is None:
            continue
        total = _round_half_step(float(used_total))
        external = _round_half_step(total - bodyweight)
        tests = updated.setdefault("tests", {})
        max_strength = tests.setdefault("max_strength", [])
        entry = {
            "test_id": "max_hang_5s_total_load",
            "date": str(log_entry.get("date") or ""),
            "exercise_id": "max_hang_5s",
            "bodyweight_kg": bodyweight,
            "total_load_kg": total,
            "external_load_kg": external,
            "setup": {"hang_seconds": 5},
            "freshness_policy": {"stale_after_days": 90},
            "confidence": "high",
        }
        max_strength.append(entry)
        max_strength.sort(key=lambda x: (str(x.get("date") or ""), str(x.get("test_id") or "")))
        baselines = updated.setdefault("baselines", {}).setdefault("hangboard", [{"max_total_load_kg": total}])
        if baselines:
            baselines[0]["max_total_load_kg"] = total


def apply_feedback(log_entry: Dict[str, Any], user_state: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(user_state)
    actual = log_entry.get("actual") or {}
    feedback_items = actual.get("exercise_feedback_v1") or []
    date_value = str(log_entry.get("date") or "")
    bodyweight = float(updated.get("bodyweight_kg") or ((updated.get("body") or {}).get("weight_kg") or 0.0))

    counters = updated.setdefault("progression_counters", {})
    if not isinstance(counters, dict):
        counters = {}
        updated["progression_counters"] = counters
    _ensure_test_queue(updated)
    max_hang_hard = int(counters.get("max_hang_5s_hard_streak") or 0)
    max_hang_easy = int(counters.get("max_hang_5s_easy_streak") or 0)

    for item in feedback_items:
        exercise_id = str(item.get("exercise_id") or "").strip()
        if not exercise_id:
            continue
        feedback_label = canonical_feedback_label(item)

        session, planned_inst = _lookup_planned_instance(log_entry, exercise_id)
        planned_prescription = (planned_inst.get("prescription") or {}) if planned_inst else {}
        planned_target = (((planned_inst.get("suggested") or {}).get("suggested_boulder_target") or {}) if planned_inst else {})

        if exercise_id in LOAD_BASED_EXERCISES:
            used_total = item.get("used_total_load_kg")
            used_external = item.get("used_external_load_kg")
            if used_total is None and used_external is not None:
                used_total = float(used_external) + bodyweight
            if used_external is None and used_total is not None:
                used_external = float(used_total) - bodyweight
            if used_total is None and used_external is None:
                continue

            base = float(used_external)
            pct = _rule_midpoint_pct(updated, feedback_label)
            next_load = _round_half_step(base * (1.0 + pct))
            setup_source = dict(planned_prescription)
            setup_source.update(item)
            setup, setup_key = _progression_setup_and_key(exercise_id, setup_source)

            entry = _find_working_load_entry(updated, exercise_id, setup)
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": setup_key,
                    "setup": setup,
                    "last_completed": bool(item.get("completed", False)),
                    "last_feedback_label": feedback_label,
                    "last_external_load_kg": _round_half_step(base),
                    "last_total_load_kg": _round_half_step(float(used_total)),
                    "next_external_load_kg": next_load,
                    "next_total_load_kg": _round_half_step(float(used_total) * (1.0 + pct)),
                    "updated_at": date_value,
                }
            )

            if exercise_id == "max_hang_5s":
                if feedback_label in {"hard", "very_hard"}:
                    max_hang_hard += 1
                    max_hang_easy = 0
                elif feedback_label in {"easy", "very_easy"}:
                    max_hang_easy += 1
                    max_hang_hard = 0
                else:
                    max_hang_hard = 0
                    max_hang_easy = 0

        elif exercise_id in GRADE_BASED_EXERCISES:
            used_grade = normalize_font_grade(item.get("used_grade"))
            if not used_grade:
                continue
            options = list(planned_target.get("surface_options") or _surface_options(updated, session.get("gym_id")))
            surface_selected = _select_surface(
                preferred=item.get("surface_selected") or planned_target.get("surface_selected"),
                options=options,
                gym_id=session.get("gym_id"),
                user_state=updated,
            )
            next_grade = step_grade(used_grade, _grade_delta_for_feedback(feedback_label))
            setup, setup_key = _progression_setup_and_key(exercise_id, {"surface": surface_selected})
            entry = _find_working_load_entry(updated, exercise_id, setup)
            entry.update(
                {
                    "exercise_id": exercise_id,
                    "key": setup_key,
                    "setup": setup,
                    "surface_selected": surface_selected,
                    "last_feedback_label": feedback_label,
                    "last_used_grade": used_grade,
                    "next_target_grade": next_grade,
                    "updated_at": date_value,
                }
            )

    counters["max_hang_5s_hard_streak"] = max_hang_hard
    counters["max_hang_5s_easy_streak"] = max_hang_easy
    if max_hang_hard >= 2:
        _enqueue_test(
            updated,
            test_id="max_hang_5s_total_load",
            date_value=date_value,
            offset_days=7,
            reason="two_recent_hard_feedback_on_max_hang_5s",
        )
    elif max_hang_easy >= 2:
        _enqueue_test(
            updated,
            test_id="max_hang_5s_total_load",
            date_value=date_value,
            offset_days=14,
            reason="two_recent_easy_feedback_on_max_hang_5s",
        )

    _update_test_from_log(log_entry, updated, bodyweight)
    return updated
