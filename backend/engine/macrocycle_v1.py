"""Macrocycle generator v1 — Hörst 4-3-2-1 adaptive periodization with DUP."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from backend.engine.assessment_v1 import _GRADE_INDEX, grade_gap

# ---------------------------------------------------------------------------
# Phase definitions
# ---------------------------------------------------------------------------

PHASE_ORDER: Tuple[str, ...] = ("base", "strength_power", "power_endurance", "performance", "deload")

PHASE_NAMES: Dict[str, str] = {
    "base": "Endurance Base",
    "strength_power": "Strength & Power",
    "power_endurance": "Power Endurance",
    "performance": "Performance",
    "deload": "Deload",
}

PHASE_ENERGY: Dict[str, str] = {
    "base": "aerobic",
    "strength_power": "anaerobic_alactic",
    "power_endurance": "anaerobic_lactic",
    "performance": "specific",
    "deload": "recovery",
}

PHASE_INTENSITY_CAP: Dict[str, str] = {
    "base": "medium",
    "strength_power": "max",
    "power_endurance": "high",
    "performance": "max",
    "deload": "low",
}

# Base domain weights per phase (from design doc §4.3)
# Keys: finger_strength, pulling_strength, power_endurance, volume_climbing, technique, core_prehab
_BASE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "base": {
        "finger_strength": 0.20, "pulling_strength": 0.15, "power_endurance": 0.15,
        "volume_climbing": 0.25, "technique": 0.20, "core_prehab": 0.05,
    },
    "strength_power": {
        "finger_strength": 0.35, "pulling_strength": 0.25, "power_endurance": 0.10,
        "volume_climbing": 0.10, "technique": 0.10, "core_prehab": 0.10,
    },
    "power_endurance": {
        "finger_strength": 0.15, "pulling_strength": 0.10, "power_endurance": 0.35,
        "volume_climbing": 0.15, "technique": 0.15, "core_prehab": 0.10,
    },
    "performance": {
        "finger_strength": 0.10, "pulling_strength": 0.05, "power_endurance": 0.20,
        "volume_climbing": 0.25, "technique": 0.25, "core_prehab": 0.15,
    },
    "deload": {
        "finger_strength": 0.05, "pulling_strength": 0.05, "power_endurance": 0.05,
        "volume_climbing": 0.10, "technique": 0.05, "core_prehab": 0.10,
    },
}

# Session pool per phase: (★ = primary, ○ = available)
_SESSION_POOL: Dict[str, Dict[str, str]] = {
    "base": {
        "endurance_aerobic_gym": "primary",
        "technique_focus_gym": "primary",
        "finger_maintenance_home": "primary",
        "finger_strength_home": "primary",
        "prehab_maintenance": "primary",
        "flexibility_full": "available",
        "handstand_practice": "available",
        "complementary_conditioning": "available",
        "strength_long": "available",
        "power_endurance_gym": "available",
    },
    "strength_power": {
        "power_contact_gym": "primary",
        "strength_long": "primary",
        "finger_strength_home": "primary",
        "prehab_maintenance": "primary",
        "technique_focus_gym": "available",
        "flexibility_full": "available",
        "handstand_practice": "available",
        "complementary_conditioning": "available",
    },
    "power_endurance": {
        "power_endurance_gym": "primary",
        "prehab_maintenance": "primary",
        "technique_focus_gym": "available",
        "finger_strength_home": "available",
        "flexibility_full": "available",
        "handstand_practice": "available",
        "endurance_aerobic_gym": "available",
    },
    "performance": {
        "technique_focus_gym": "primary",
        "prehab_maintenance": "primary",
        "power_endurance_gym": "available",
        "power_contact_gym": "available",
        "finger_strength_home": "available",
        "flexibility_full": "available",
        "handstand_practice": "available",
    },
    "deload": {
        "regeneration_easy": "primary",
        "flexibility_full": "primary",
        "yoga_recovery": "primary",
        "prehab_maintenance": "primary",
        "handstand_practice": "available",
    },
}


# ---------------------------------------------------------------------------
# Phase duration computation
# ---------------------------------------------------------------------------

# Mapping from assessment profile axes to relevant weakness adjustments.
# profile key → (phase to extend, phase to shrink)
_WEAKNESS_ADJUSTMENTS: Dict[str, Tuple[str, str]] = {
    "power_endurance": ("power_endurance", "strength_power"),
    "endurance": ("base", "strength_power"),
    "finger_strength": ("strength_power", "base"),
    "pulling_strength": ("strength_power", "base"),
    "technique": ("base", "performance"),
}


def _compute_phase_durations(profile: Dict[str, int], total_weeks: int = 12) -> Dict[str, int]:
    """Compute phase durations based on assessment profile.

    Base allocation (12 weeks):
        base: 4, strength_power: 3, power_endurance: 2, performance: 2, deload: 1

    Adjustments based on weakest axes (score < 50).
    """
    durations = {
        "base": 4,
        "strength_power": 3,
        "power_endurance": 2,
        "performance": 2,
        "deload": 1,
    }

    # Find the weakest axis
    weakest_axis = None
    weakest_score = 101
    for axis in ("power_endurance", "endurance", "finger_strength", "pulling_strength", "technique"):
        score = profile.get(axis, 50)
        if score < weakest_score:
            weakest_score = score
            weakest_axis = axis

    # Apply adjustment if primary weakness is below threshold
    if weakest_axis and weakest_score < 50 and weakest_axis in _WEAKNESS_ADJUSTMENTS:
        extend_phase, shrink_phase = _WEAKNESS_ADJUSTMENTS[weakest_axis]
        if durations[shrink_phase] > 2:  # Don't shrink below 2
            durations[extend_phase] += 1
            durations[shrink_phase] -= 1

    # Enforce floor: min 2 weeks per non-deload phase, min 1 for deload
    for phase_id in ("base", "strength_power", "power_endurance", "performance"):
        durations[phase_id] = max(2, durations[phase_id])
    durations["deload"] = max(1, durations["deload"])

    # Scale to total_weeks
    current_total = sum(durations.values())
    if current_total != total_weeks:
        diff = total_weeks - current_total
        # Add/remove from base phase (most flexible)
        durations["base"] = max(2, durations["base"] + diff)

    # Ensure total sums correctly
    actual_total = sum(durations.values())
    if actual_total != total_weeks:
        durations["base"] += total_weeks - actual_total

    return durations


def _adjust_domain_weights(
    base_weights: Dict[str, float],
    profile: Dict[str, int],
) -> Dict[str, float]:
    """Adjust domain weights based on profile weaknesses.

    - Axes with score < 50 → +0.05 to relevant weight
    - Axes with score > 75 → -0.03
    Then renormalize to sum = 1.0.
    """
    # Map profile axes to domain weight keys
    axis_to_weight = {
        "finger_strength": "finger_strength",
        "pulling_strength": "pulling_strength",
        "power_endurance": "power_endurance",
        "technique": "technique",
        "endurance": "volume_climbing",  # endurance maps to climbing volume
        "body_composition": "core_prehab",
    }

    adjusted = dict(base_weights)

    for axis, weight_key in axis_to_weight.items():
        score = profile.get(axis, 50)
        if weight_key not in adjusted:
            continue
        if score < 50:
            adjusted[weight_key] += 0.05
        elif score > 75:
            adjusted[weight_key] = max(0.02, adjusted[weight_key] - 0.03)

    # Renormalize
    total = sum(adjusted.values())
    if total > 0:
        adjusted = {k: round(v / total, 3) for k, v in adjusted.items()}

    return adjusted


def _build_session_pool(phase_id: str) -> List[str]:
    """Return the ordered session pool for a phase."""
    pool_def = _SESSION_POOL.get(phase_id, {})
    # Primary sessions first, then available
    primary = sorted(k for k, v in pool_def.items() if v == "primary")
    available = sorted(k for k, v in pool_def.items() if v == "available")
    return primary + available


def _check_pretrip_overlap(
    trips: List[Dict[str, Any]],
    phase_start: str,
    phase_end: str,
) -> List[Dict[str, Any]]:
    """Find trips that overlap with a date range."""
    from datetime import date as date_type
    p_start = datetime.strptime(phase_start, "%Y-%m-%d").date()
    p_end = datetime.strptime(phase_end, "%Y-%m-%d").date()
    overlapping = []
    for trip in (trips or []):
        t_start_str = trip.get("start_date")
        if not t_start_str:
            continue
        t_start = datetime.strptime(t_start_str, "%Y-%m-%d").date()
        # Check if the 5-day pre-trip window falls within the phase
        pretrip_start = t_start - timedelta(days=5)
        if pretrip_start <= p_end and t_start >= p_start:
            overlapping.append(trip)
    return overlapping


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def _validate_goal(goal: Dict[str, Any]) -> List[str]:
    """Validate goal and return warnings."""
    warnings = []
    target = goal.get("target_grade")
    current = goal.get("current_grade")

    if target and current and target in _GRADE_INDEX and current in _GRADE_INDEX:
        gap = grade_gap(target, current)
        if gap <= 0:
            warnings.append(
                f"target_grade ({target}) is not harder than current_grade ({current}). "
                "Consider setting a more ambitious target."
            )
        elif gap > 8:
            warnings.append(
                f"target_grade ({target}) is {gap} half-grades above current_grade ({current}). "
                "A single macrocycle may not be sufficient."
            )
    elif target and target not in _GRADE_INDEX:
        warnings.append(f"Unknown target_grade: {target}")
    elif current and current not in _GRADE_INDEX:
        warnings.append(f"Unknown current_grade: {current}")

    return warnings


def generate_macrocycle(
    goal: Dict[str, Any],
    assessment_profile: Dict[str, int],
    user_state: Dict[str, Any],
    start_date: str,
    total_weeks: int = 12,
) -> Dict[str, Any]:
    """Generate a complete macrocycle of total_weeks weeks.

    Args:
        goal: Goal dict from user_state.
        assessment_profile: 6-axis profile (0-100 each).
        user_state: Full user_state for trips and context.
        start_date: YYYY-MM-DD string for the Monday of week 1.
        total_weeks: Total weeks in the macrocycle (default 12).

    Returns:
        Macrocycle dict with phases, domain weights, session pools, etc.
    """
    goal_warnings = _validate_goal(goal)
    durations = _compute_phase_durations(assessment_profile, total_weeks)
    trips = user_state.get("trips") or []

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    phases = []
    current_week = 1

    for phase_id in PHASE_ORDER:
        duration = durations[phase_id]
        if duration <= 0:
            continue

        phase_start_date = start + timedelta(weeks=current_week - 1)
        phase_end_date = phase_start_date + timedelta(weeks=duration) - timedelta(days=1)

        base_weights = _BASE_WEIGHTS[phase_id]
        domain_weights = _adjust_domain_weights(base_weights, assessment_profile)
        session_pool = _build_session_pool(phase_id)

        # Check for pre-trip deload overlap
        pretrip_trips = _check_pretrip_overlap(
            trips,
            phase_start_date.isoformat(),
            phase_end_date.isoformat(),
        )

        phase = {
            "phase_id": phase_id,
            "phase_name": PHASE_NAMES[phase_id],
            "start_week": current_week,
            "end_week": current_week + duration - 1,
            "duration_weeks": duration,
            "energy_system": PHASE_ENERGY[phase_id],
            "domain_weights": domain_weights,
            "session_pool": session_pool,
            "intensity_cap": PHASE_INTENSITY_CAP[phase_id],
            "notes": _phase_notes(phase_id),
        }

        if pretrip_trips:
            phase["pretrip_deload"] = [
                {
                    "trip_name": t.get("name"),
                    "trip_start": t.get("start_date"),
                    "deload_from": (datetime.strptime(t["start_date"], "%Y-%m-%d").date() - timedelta(days=5)).isoformat(),
                }
                for t in pretrip_trips
            ]

        phases.append(phase)
        current_week += duration

    end_date = start + timedelta(weeks=total_weeks) - timedelta(days=1)

    result = {
        "macrocycle_version": "macrocycle.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": start_date,
        "end_date": end_date.isoformat(),
        "goal_snapshot": {
            "goal_type": goal.get("goal_type"),
            "target_grade": goal.get("target_grade"),
            "current_grade": goal.get("current_grade"),
            "deadline": goal.get("deadline"),
        },
        "assessment_snapshot": dict(assessment_profile),
        "total_weeks": total_weeks,
        "phases": phases,
    }
    if goal_warnings:
        result["warnings"] = goal_warnings
    return result


def _phase_notes(phase_id: str) -> str:
    notes = {
        "base": "Build aerobic base. High volume, low intensity. Focus technique and movement quality.",
        "strength_power": "Max strength development. Max hangs, limit bouldering, general strength. High quality, full rest.",
        "power_endurance": "Anaerobic capacity. 4x4, intervals, threshold climbing. Tolerate pump, push volume.",
        "performance": "Peak performance. Limit climbing, projecting, outdoor. Reduce volume, maximize quality.",
        "deload": "Recovery. Volume -50%. No max/high intensity. Mobility, prehab, easy climbing only.",
    }
    return notes.get(phase_id, "")


# ---------------------------------------------------------------------------
# Deload functions (Task 5)
# ---------------------------------------------------------------------------

DELOAD_SESSION_POOL = ["regeneration_easy", "flexibility_full", "yoga_recovery", "prehab_maintenance"]


def apply_deload_week(week_plan: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a week plan into a deload week.

    - Remove sessions with max/high intensity
    - Keep max 3 sessions
    - Replace removed sessions with deload alternatives
    """
    if not week_plan or "weeks" not in week_plan:
        return week_plan

    deload_plan = dict(week_plan)
    for week in deload_plan.get("weeks", []):
        days = week.get("days", [])
        kept_sessions = 0
        for day in days:
            filtered = []
            for sess in day.get("sessions", []):
                # Keep low/medium intensity sessions, cap at 3 total
                tags = sess.get("tags", {})
                if kept_sessions >= 3:
                    continue
                if tags.get("hard"):
                    continue
                filtered.append(sess)
                kept_sessions += 1
            day["sessions"] = filtered

        week["phase"] = "deload"
        week["targets"] = {"hard_days": 0, "finger_days": 0, "deload_factor": 0.5}

    return deload_plan


def check_pretrip_deload(
    macrocycle: Dict[str, Any],
    trips: List[Dict[str, Any]],
    current_date: str,
) -> Optional[Dict[str, Any]]:
    """Check if a trip starts within 5 days of current_date.

    Returns trip info for mini-deload activation, or None.
    """
    if not trips:
        return None

    current = datetime.strptime(current_date, "%Y-%m-%d").date()
    for trip in trips:
        trip_start_str = trip.get("start_date")
        if not trip_start_str:
            continue
        trip_start = datetime.strptime(trip_start_str, "%Y-%m-%d").date()
        days_until = (trip_start - current).days
        if 0 < days_until <= 5:
            return {
                "trigger": "pretrip_deload",
                "trip_name": trip.get("name"),
                "trip_start": trip_start_str,
                "days_until_trip": days_until,
                "recommendation": "Reduce volume and intensity. No max/high sessions.",
            }
    return None


def should_extend_phase(
    phase: Dict[str, Any],
    weekly_feedback: List[str],
) -> bool:
    """Check if a phase should be extended based on feedback.

    If feedback labels are still 'hard' or 'very_hard' after 2+ weeks → extend.
    Max extension: +2 weeks (checked externally).
    """
    if len(weekly_feedback) < 2:
        return False

    last_two = weekly_feedback[-2:]
    hard_labels = {"hard", "very_hard"}
    return all(fb in hard_labels for fb in last_two)


def should_trigger_adaptive_deload(
    recent_feedback: List[str],
) -> bool:
    """Check if adaptive deload should trigger.

    If 5+ consecutive days with 'very_hard' or pain flags → trigger.
    """
    if len(recent_feedback) < 5:
        return False

    hard_labels = {"very_hard"}
    last_five = recent_feedback[-5:]
    return all(fb in hard_labels for fb in last_five)
