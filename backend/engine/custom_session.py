"""Custom session helpers — load score and duration estimation (A205)."""

from __future__ import annotations

from typing import Any, Dict, List


def compute_custom_session_load(exercise_ids: List[str], catalog: Dict[str, Any]) -> int:
    """Sum fatigue_cost x 1.5, capped at 85 — same formula as resolve_session."""
    raw = sum(catalog.get(eid, {}).get("fatigue_cost", 0) for eid in exercise_ids)
    return round(min(85, raw * 1.5))


def estimate_custom_session_duration(exercises: List[Dict[str, Any]]) -> int:
    """Estimate duration in minutes from exercise params."""
    total_seconds = 0
    for ex in exercises:
        sets = ex.get("sets", 1)
        # Work time per set
        if ex.get("work_seconds"):
            work_per_set = ex["work_seconds"]
        elif ex.get("reps"):
            work_per_set = ex["reps"] * 4  # ~4s per rep rough estimate
        else:
            work_per_set = 30  # fallback
        # Rest time
        rest_per_set = ex.get("rest_between_sets_seconds") or 60
        # Total: sets x work + (sets-1) x rest
        total_seconds += sets * work_per_set + max(0, sets - 1) * rest_per_set
    return max(1, round(total_seconds / 60))
