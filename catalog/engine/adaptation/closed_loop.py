from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from catalog.engine.cluster_utils import cluster_key_for_exercise, parse_date


DEFAULT_RULES = {
    "too_easy": 0.025,
    "easy": 0.01,
    "ok": 0.0,
    "hard": -0.025,
    "too_hard": -0.05,
    "fail": -0.05,
}

DEFAULT_CONFIG = {
    "delta_pct": DEFAULT_RULES,
    "min_multiplier": 0.85,
    "max_multiplier": 1.15,
}

HARD_DIFFICULTIES = {"hard", "too_hard", "fail"}
EASY_DIFFICULTIES = {"too_easy", "easy", "ok"}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def compute_next_multiplier(
    multiplier: float,
    difficulty: str,
    streak: int,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = DEFAULT_CONFIG if config is None else config
    delta_pct = cfg.get("delta_pct", DEFAULT_RULES)
    if difficulty not in delta_pct:
        raise ValueError(f"Unsupported difficulty: {difficulty}")

    next_multiplier = float(multiplier) * (1.0 + float(delta_pct[difficulty]))
    min_multiplier = float(cfg.get("min_multiplier", DEFAULT_CONFIG["min_multiplier"]))
    max_multiplier = float(cfg.get("max_multiplier", DEFAULT_CONFIG["max_multiplier"]))

    _ = streak  # reserved for future rules
    return _clamp(next_multiplier, min_multiplier, max_multiplier)


def apply_multiplier(load_kg: float, multiplier: float, rounding_step: float) -> float:
    adjusted = float(load_kg) * float(multiplier)
    step = float(rounding_step)
    if step <= 0:
        return adjusted
    return round(adjusted / step) * step


def update_user_state_adjustments(
    user_state: Dict[str, Any],
    exercise_id: str,
    outcome: Dict[str, Any],
    *,
    exercises_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    feedback_date: Optional[str] = None,
) -> Dict[str, Any]:
    difficulty = outcome.get("difficulty")
    if difficulty is None:
        difficulty = (outcome.get("actual") or {}).get("difficulty")

    if difficulty is None:
        return user_state

    adjustments = user_state.setdefault("adjustments", {})
    per_exercise = adjustments.setdefault("per_exercise", {})
    state = per_exercise.get(exercise_id, {})

    multiplier = float(state.get("multiplier", 1.0))
    streak = int(state.get("streak", 0))
    next_multiplier = compute_next_multiplier(multiplier, difficulty, streak, adjustments.get("config"))

    if difficulty in HARD_DIFFICULTIES:
        next_streak = streak + 1
    elif difficulty in EASY_DIFFICULTIES:
        next_streak = 0
    else:
        next_streak = streak

    per_exercise[exercise_id] = {
        "multiplier": next_multiplier,
        "streak": next_streak,
        "last_update": _now_iso(),
    }

    cooldown_days = 0
    if difficulty in {"fail", "too_hard"}:
        cooldown_days = 2
    elif difficulty == "hard":
        cooldown_days = 1

    if cooldown_days and exercises_by_id:
        date_value = feedback_date or outcome.get("date") or outcome.get("target_date")
        if date_value is None:
            date_value = (outcome.get("actual") or {}).get("date")
        base_date = parse_date(date_value)
        exercise = exercises_by_id.get(exercise_id)
        if base_date and exercise:
            until_date = base_date + timedelta(days=cooldown_days)
            cooldowns = user_state.setdefault("cooldowns", {})
            per_cluster = cooldowns.setdefault("per_cluster", {})
            cluster_key = cluster_key_for_exercise(exercise)
            per_cluster[cluster_key] = {
                "until_date": until_date.isoformat(),
                "reason": f"difficulty:{difficulty}",
                "last_updated": base_date.isoformat(),
            }

    return user_state
