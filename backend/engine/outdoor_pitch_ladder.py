"""Deterministic pitch ladder for an outdoor day (A265).

The C241 strategy catalog (``backend/catalog/outdoor/v1/strategy.json``) speaks
in *relative* terms — "ramp grades into the day", "onsight is about redpoint
minus one number grade", "20-45 min between near-max attempts". That is correct
guidance and useless standing at the base of a route: it never names a grade.

This module turns those rules into an ordered list of pitches with an **absolute
grade, an attempt count and a rest** for each one, derived from the athlete's own
onsight/redpoint grades. No LLM, no randomness: same grades + same day_type
always produce the same ladder, which is what makes it testable.

Scale: French sport grades, via ``assessment_v1.GRADE_ORDER`` (half-grade steps —
``7a → 7a+`` is one step, ``7a → 8a`` is six). Offsets below are in those steps.

v1 is lead-only, matching the strategy catalog (``base`` has no boulder entry).
``build_pitch_ladder`` returns ``None`` for anything else rather than inventing a
boulder ladder the catalog cannot back.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.engine.assessment_v1 import GRADE_ORDER, _GRADE_INDEX

# One whole number grade (7a → 8a) on the half-grade scale.
_NUMBER_GRADE_STEPS = 6

# Roles, in the order they appear in a day.
ROLE_WARMUP = "warmup"
ROLE_BUILD = "build"
ROLE_MAIN = "main"
ROLE_PE = "power_endurance"
ROLE_COOLDOWN = "cooldown"

# Ladder templates, per day_type. Each row is
# ``(role, anchor, offset_steps, attempts, rest_after_min, note)`` where *anchor*
# is "onsight" or "redpoint" and *offset_steps* moves on the half-grade scale.
#
# The rests are the point of the whole thing: on onsight_flash the closing pitch
# deliberately gets a SHORT rest (10 min, not the 15 of the pitches before it) —
# that is the power-endurance stimulus, and it is the one number a climber
# improvises wrong when tired.
_TEMPLATES: Dict[str, List[tuple]] = {
    "onsight_flash": [
        (ROLE_WARMUP, "onsight", -7, 1, 10, "Easy, on the feet. No hard pulling while cold (D72)."),
        (ROLE_WARMUP, "onsight", -4, 1, 10, "Second warm-up: climb it smoothly, build the pump gradually."),
        (ROLE_BUILD, "onsight", -1, 1, 12, "First real effort. Read from the ground, then commit."),
        (ROLE_MAIN, "onsight", 0, 1, 15, "Onsight attempt at your ceiling — one try, by definition."),
        (ROLE_MAIN, "onsight", +1, 2, 15, "Above the onsight ceiling: two burns maximum, then let it go."),
        (ROLE_PE, "onsight", -1, 1, 10, "SHORT rest on purpose — climbing this one pumped is the point."),
        (ROLE_COOLDOWN, "onsight", -5, 1, 0, "Close relaxed, with skin and fingers intact."),
    ],
    "project": [
        (ROLE_WARMUP, "onsight", -7, 1, 10, "Easy, on the feet. No full-crimp loading while cold (D72)."),
        (ROLE_WARMUP, "onsight", -4, 1, 12, "Second warm-up, smooth and controlled."),
        (ROLE_BUILD, "onsight", -1, 1, 20, "Last pitch before the project — wake the system up, don't drain it."),
        (ROLE_MAIN, "redpoint", 0, 3, 30, "Project burns: full rest between attempts, quality over quantity."),
        (ROLE_COOLDOWN, "onsight", -5, 1, 0, "Easy pitch to flush, then stop."),
    ],
    "volume": [
        (ROLE_WARMUP, "onsight", -7, 1, 8, "The early pitches double as warm-up — ramp, don't jump."),
        (ROLE_WARMUP, "onsight", -5, 1, 8, "Still easy. Movement quality is the target today."),
        (ROLE_MAIN, "onsight", -3, 1, 8, "Sub-max, active rest between pitches (walk, shake, G-Tox)."),
        (ROLE_MAIN, "onsight", -3, 1, 8, "Keep every effort below the pump threshold."),
        (ROLE_MAIN, "onsight", -2, 1, 10, "Slightly harder, still comfortably below your onsight."),
        (ROLE_MAIN, "onsight", -2, 1, 10, "Pace to skin and pump, not to the clock."),
        (ROLE_MAIN, "onsight", -3, 1, 8, "Volume pitch — smooth, efficient, no fighting."),
        (ROLE_COOLDOWN, "onsight", -6, 1, 0, "Last easy one. Stop while it still feels good."),
    ],
    "scout_easy": [
        (ROLE_WARMUP, "onsight", -7, 1, 10, "Easy start, feel the rock and the friction."),
        (ROLE_MAIN, "onsight", -5, 1, 10, "Scouting: read lines, clip positions, rests."),
        (ROLE_MAIN, "onsight", -4, 1, 10, "Comfortable pitch — information, not performance."),
        (ROLE_COOLDOWN, "onsight", -6, 1, 0, "Close early. Today is reconnaissance."),
    ],
}

DAY_TYPES = tuple(_TEMPLATES.keys())


def _shift(grade: str, steps: int) -> str:
    """Move *grade* by *steps* half-grades, clamped to the scale ends."""
    idx = _GRADE_INDEX[grade] + steps
    idx = max(0, min(len(GRADE_ORDER) - 1, idx))
    return GRADE_ORDER[idx]


def infer_onsight(redpoint: str) -> str:
    """Catalog rule: onsight is about one NUMBER grade below redpoint.

    Used only when the athlete has no recorded onsight grade.
    """
    return _shift(redpoint, -_NUMBER_GRADE_STEPS)


def grades_from_state(user_state: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Extract ``{onsight, redpoint}`` sport grades from a user state.

    Returns ``None`` when the state has no usable redpoint grade — the caller
    then skips the ladder instead of falling back to a made-up default, which
    would silently prescribe grades that are not the athlete's.
    """
    sport = (((user_state or {}).get("performance") or {}).get("current_level") or {}).get("sport") or {}
    redpoint = ((sport.get("worked") or {}).get("grade") or "").strip()
    onsight = ((sport.get("onsight") or {}).get("grade") or "").strip()

    if redpoint not in _GRADE_INDEX:
        # Fall back to the goal's current_grade before giving up.
        redpoint = str(((user_state or {}).get("goal") or {}).get("current_grade") or "").strip()
    if redpoint not in _GRADE_INDEX:
        return None
    if onsight not in _GRADE_INDEX:
        onsight = infer_onsight(redpoint)
    return {"onsight": onsight, "redpoint": redpoint}


def build_pitch_ladder(
    day_type: str,
    *,
    onsight_grade: Optional[str] = None,
    redpoint_grade: Optional[str] = None,
    discipline: str = "lead",
) -> Optional[Dict[str, Any]]:
    """Build the ordered pitch list for an outdoor day.

    Returns ``None`` (never a guess) when the discipline is not lead, the
    day_type is unknown, or no usable grade was supplied.
    """
    if discipline != "lead":
        return None
    template = _TEMPLATES.get(day_type)
    if template is None:
        return None

    redpoint = (redpoint_grade or "").strip()
    onsight = (onsight_grade or "").strip()
    if onsight not in _GRADE_INDEX and redpoint in _GRADE_INDEX:
        onsight = infer_onsight(redpoint)
    if redpoint not in _GRADE_INDEX and onsight in _GRADE_INDEX:
        redpoint = _shift(onsight, _NUMBER_GRADE_STEPS)
    if onsight not in _GRADE_INDEX:
        return None

    anchors = {"onsight": onsight, "redpoint": redpoint}
    pitches: List[Dict[str, Any]] = []
    total_attempts = 0
    total_rest = 0

    for i, (role, anchor, offset, attempts, rest, note) in enumerate(template, start=1):
        pitches.append({
            "index": i,
            "role": role,
            "grade": _shift(anchors[anchor], offset),
            "attempts": attempts,
            "rest_after_min": rest,
            "note": note,
        })
        total_attempts += attempts
        total_rest += rest

    # Rough clock: ~12 min of climbing+rigging per attempt, plus the prescribed
    # rests. Deliberately coarse — it frames the day, it is not a schedule.
    estimated_hours = round((total_attempts * 12 + total_rest) / 60, 1)

    return {
        "discipline": discipline,
        "day_type": day_type,
        "onsight_grade": onsight,
        "redpoint_grade": redpoint,
        "pitches": pitches,
        "summary": {
            "pitch_count": len(pitches),
            "total_attempts": total_attempts,
            "estimated_hours": estimated_hours,
        },
        "generated": True,
    }
