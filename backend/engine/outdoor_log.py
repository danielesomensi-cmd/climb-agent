"""Outdoor session logging — validation, stats, and thin wrappers over storage.

I/O is delegated to backend.engine.storage.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.engine import storage


REQUIRED_FIELDS = {"log_version", "date", "spot_name", "discipline", "duration_minutes", "routes"}

# A225: accepted log schema versions. v1 logs predate the v2 optional fields
# (day_type, route_profile, conditions.temperature/condition_band) and stay valid.
VALID_LOG_VERSIONS = {"outdoor.v1", "outdoor.v2"}
CURRENT_LOG_VERSION = "outdoor.v2"

# outdoor.v2 optional-field vocabularies (mirror the C241 strategy catalog).
VALID_DAY_TYPES = {"project", "onsight_flash", "volume", "scout_easy"}
VALID_ROUTE_PROFILE = {
    "wall_angle": {"slab", "vertical", "overhang", "roof"},
    "route_length": {"short_power", "medium", "long_endurance"},
    "hold_style": {"crimp", "sloper_pinch", "mixed"},
    "target_grade_relative": {"within_limit", "at_or_above_limit"},
}
VALID_CONDITION_BANDS = {"prime", "ok", "poor_hot_humid", "poor_cold_dry"}

# ---------------------------------------------------------------------------
# Outdoor load score helpers
# ---------------------------------------------------------------------------

# Outdoor load weight per grade. Anchored to the PRE-B302 grade spacing so the
# ladder fix (which inserted 5a+/5b+/5c+ into GRADE_ORDER) does not perturb
# historical outdoor load: the new grade-5 half-steps share their base grade's
# weight, and every grade from 6a up keeps its original weight.
# NOTE: this weight is ABSOLUTE per grade, not relative to the climber's max —
# a 6a weighs the same for an 8a and a 6a climber. Making it relative to ability
# is tracked separately as B-OUTDOOR-RELATIVE-LOAD.
_OUTDOOR_WEIGHT_ANCHOR: List[str] = [
    "5a", "5b", "5c",
    "6a", "6a+", "6b", "6b+", "6c", "6c+",
    "7a", "7a+", "7b", "7b+", "7c", "7c+",
    "8a", "8a+", "8b", "8b+", "8c", "8c+",
    "9a", "9a+",
]
_GRADE_WEIGHT: Dict[str, int] = {g: i + 3 for i, g in enumerate(_OUTDOOR_WEIGHT_ANCHOR)}
# Fold the newly-added grade-5 half-steps onto their base grade's weight.
_GRADE_WEIGHT.update({
    "5a+": _GRADE_WEIGHT["5a"],
    "5b+": _GRADE_WEIGHT["5b"],
    "5c+": _GRADE_WEIGHT["5c"],
})
_UNKNOWN_GRADE_WEIGHT = 10

_STYLE_MODIFIER: Dict[str, float] = {
    "onsight": 1.2,
    "flash": 1.1,
    "redpoint": 1.0,
    "project": 0.7,
    "repeat": 0.5,
}

_LOAD_CAP = 85


def _duration_factor(duration_minutes: int) -> float:
    """Baseline 120 min, clamped [0.5, 1.5]."""
    return max(0.5, min(1.5, duration_minutes / 120))


def _volume_factor(num_routes: int) -> float:
    """Log-scaled volume factor: 1 route=1.0, 5=2.0, capped at 2.0."""
    if num_routes <= 1:
        return 1.0
    return min(2.0, 1.0 + math.log(num_routes, 5))


def compute_outdoor_load_score(entry: Dict[str, Any]) -> int:
    """Compute a deterministic load score for an outdoor session.

    D151 formula: avg(grade_weight × style_modifier) × volume_factor × duration_factor.
    Returns an int capped at 85, comparable to indoor session_load_score.
    """
    routes = entry.get("routes") or []
    if not routes:
        return 0

    route_scores = []
    for route in routes:
        grade = route.get("grade", "")
        weight = _GRADE_WEIGHT.get(grade, _UNKNOWN_GRADE_WEIGHT)
        style = route.get("style")
        modifier = _STYLE_MODIFIER.get(style, 1.0) if style else 1.0
        route_scores.append(weight * modifier)

    avg_score = sum(route_scores) / len(route_scores)
    vol = _volume_factor(len(route_scores))
    duration = entry.get("duration_minutes", 120)
    dur = _duration_factor(duration)

    return round(min(_LOAD_CAP, avg_score * vol * dur))
VALID_DISCIPLINES = {"lead", "boulder", "both"}


# ---------------------------------------------------------------------------
# Active outdoor session — duration derivation (A225)
# ---------------------------------------------------------------------------

# A real outdoor day rarely exceeds ~10 h. A timer left running ("Start" pressed
# then the session closed the next day) would otherwise derive an absurd
# duration. We cap derived durations here so a stale ``started_at`` can never
# silently overwrite a reasonable value.
OUTDOOR_SESSION_MAX_MINUTES = 600  # 10 hours


def derive_outdoor_duration(
    started_at_iso: Optional[str],
    now: datetime,
    manual_override: Optional[int] = None,
) -> Dict[str, Any]:
    """Resolve an outdoor session's ``duration_minutes`` at close time.

    Rules (deterministic):
      1. An explicit, valid ``manual_override`` (int ≥ 1) always wins — it is the
         user's typed value and must never be clobbered by a stale timer.
      2. Otherwise derive from ``started_at → now`` (floored at 1 min).
      3. If the derived value exceeds ``OUTDOOR_SESSION_MAX_MINUTES`` (stale /
         overnight timer), cap it and flag ``capped=True`` + ``raw_minutes`` so the
         caller can ask the user to confirm instead of writing an absurd number.
      4. If ``started_at`` is missing/invalid and no override is given → ``None``
         (the caller must supply a manual value).

    Returns ``{minutes, capped, raw_minutes, source}`` where ``source`` is one of
    ``manual | timer | timer_capped | none``.
    """
    if isinstance(manual_override, int) and not isinstance(manual_override, bool) and manual_override >= 1:
        return {"minutes": manual_override, "capped": False, "raw_minutes": None, "source": "manual"}

    try:
        started = datetime.fromisoformat(started_at_iso) if started_at_iso else None
    except (ValueError, TypeError):
        started = None
    if started is None:
        return {"minutes": None, "capped": False, "raw_minutes": None, "source": "none"}

    raw = round((now - started).total_seconds() / 60)
    if raw < 1:
        raw = 1

    if raw > OUTDOOR_SESSION_MAX_MINUTES:
        return {
            "minutes": OUTDOOR_SESSION_MAX_MINUTES,
            "capped": True,
            "raw_minutes": raw,
            "source": "timer_capped",
        }
    return {"minutes": raw, "capped": False, "raw_minutes": None, "source": "timer"}


def validate_outdoor_entry(entry: Dict[str, Any]) -> List[str]:
    """Validate an outdoor session entry. Returns list of error strings (empty = valid)."""
    errors: List[str] = []

    missing = REQUIRED_FIELDS - set(entry.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")
        return errors

    if entry.get("log_version") not in VALID_LOG_VERSIONS:
        errors.append(
            f"Invalid log_version: {entry.get('log_version')} "
            f"(expected one of {sorted(VALID_LOG_VERSIONS)})"
        )

    if entry.get("discipline") not in VALID_DISCIPLINES:
        errors.append(f"Invalid discipline: {entry.get('discipline')}")

    # --- outdoor.v2 optional fields (A225) — only validated when present ----
    day_type = entry.get("day_type")
    if day_type is not None and day_type not in VALID_DAY_TYPES:
        errors.append(f"Invalid day_type: {day_type} (expected one of {sorted(VALID_DAY_TYPES)})")

    route_profile = entry.get("route_profile")
    if route_profile is not None:
        if not isinstance(route_profile, dict):
            errors.append("route_profile must be a dict")
        else:
            for key, value in route_profile.items():
                if key not in VALID_ROUTE_PROFILE:
                    errors.append(f"Unknown route_profile key: {key}")
                elif value is not None and value not in VALID_ROUTE_PROFILE[key]:
                    errors.append(
                        f"Invalid route_profile.{key}: {value} "
                        f"(expected one of {sorted(VALID_ROUTE_PROFILE[key])})"
                    )

    conditions = entry.get("conditions")
    if isinstance(conditions, dict):
        band = conditions.get("condition_band")
        if band is not None and band not in VALID_CONDITION_BANDS:
            errors.append(
                f"Invalid conditions.condition_band: {band} "
                f"(expected one of {sorted(VALID_CONDITION_BANDS)})"
            )
        temp = conditions.get("temperature")
        if temp is not None and not isinstance(temp, (int, float)):
            errors.append(f"Invalid conditions.temperature: {temp} (expected a number)")

    date_str = entry.get("date", "")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        errors.append(f"Invalid date format: {date_str} (expected YYYY-MM-DD)")

    duration = entry.get("duration_minutes")
    if not isinstance(duration, int) or duration < 1:
        errors.append(f"Invalid duration_minutes: {duration}")

    routes = entry.get("routes")
    if not isinstance(routes, list):
        errors.append("routes must be a list")
    else:
        for i, route in enumerate(routes):
            if not isinstance(route, dict):
                errors.append(f"routes[{i}] must be a dict")
                continue
            if not route.get("name"):
                errors.append(f"routes[{i}].name is required")
            if not route.get("grade"):
                errors.append(f"routes[{i}].grade is required")
            attempts = route.get("attempts")
            if not isinstance(attempts, list) or len(attempts) < 1:
                errors.append(f"routes[{i}].attempts must be a non-empty list")

    return errors


def append_outdoor_session(entry: Dict[str, Any], user_id: Optional[str] = None) -> str:
    """Validate and append an outdoor session entry to the yearly JSONL log.

    Returns the path of the log file written to.
    Raises ValueError if validation fails.
    """
    errors = validate_outdoor_entry(entry)
    if errors:
        raise ValueError(f"Invalid outdoor session entry: {'; '.join(errors)}")

    return storage.append_outdoor_log_line(user_id, entry)


def remove_outdoor_session(user_id: Optional[str], date: str) -> int:
    """Remove all outdoor session entries for a given date.

    Returns the number of entries removed.
    """
    return storage.remove_outdoor_log_by_date(user_id, date)


def update_outdoor_session(user_id: Optional[str], date: str, new_entry: Dict[str, Any]) -> str:
    """Replace the outdoor session entry for a given date.

    Validates the new entry, removes the old one, and appends the replacement.
    Returns the JSONL log path.
    Raises ValueError if validation fails or no entry exists for that date.
    """
    if not storage.outdoor_log_date_exists(user_id, date):
        raise ValueError(f"No outdoor session found for date {date}")

    # Validate new entry before touching the file
    errors = validate_outdoor_entry(new_entry)
    if errors:
        raise ValueError(f"Invalid outdoor session entry: {'; '.join(errors)}")

    # Remove old, append new
    storage.remove_outdoor_log_by_date(user_id, date)
    return storage.append_outdoor_log_line(user_id, new_entry)


def load_outdoor_sessions(
    user_id: Optional[str] = None,
    since_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load outdoor sessions from JSONL logs, optionally filtered by date.

    Deduplicates by date (last entry wins). Sorted by date ascending.
    """
    return storage.read_outdoor_logs(user_id, since_date=since_date)


def compute_outdoor_stats(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregated statistics from outdoor sessions."""
    if not sessions:
        return {
            "total_sessions": 0,
            "total_routes": 0,
            "grade_histogram": {},
            "onsight_pct": 0.0,
            "flash_pct": 0.0,
            "sent_pct": 0.0,
            "top_grade_sent": None,
            "total_load": 0,
            "avg_load_per_session": 0.0,
        }

    total_routes = 0
    onsight_count = 0
    flash_count = 0
    sent_count = 0
    grade_counts: Dict[str, int] = {}
    grades_sent: List[str] = []

    for session in sessions:
        for route in session.get("routes", []):
            total_routes += 1
            grade = route.get("grade", "unknown")
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

            attempts = route.get("attempts", [])
            any_sent = any(a.get("result") == "sent" for a in attempts)

            if any_sent:
                sent_count += 1
                grades_sent.append(grade)

                # Onsight: first attempt is sent and style is onsight (or no style but first attempt sent)
                style = route.get("style")
                if style == "onsight":
                    onsight_count += 1
                elif style == "flash":
                    flash_count += 1
                elif style is None and len(attempts) == 1 and attempts[0].get("result") == "sent":
                    # Auto-detect: single attempt sent = potential onsight
                    onsight_count += 1

    # Top grade sent (lexicographic — works for Font/French scales approximately)
    top_grade = max(grades_sent) if grades_sent else None

    total_load = sum(compute_outdoor_load_score(s) for s in sessions)
    avg_load = round(total_load / len(sessions), 1) if sessions else 0.0

    return {
        "total_sessions": len(sessions),
        "total_routes": total_routes,
        "grade_histogram": dict(sorted(grade_counts.items())),
        "onsight_pct": round(onsight_count / total_routes * 100, 1) if total_routes else 0.0,
        "flash_pct": round(flash_count / total_routes * 100, 1) if total_routes else 0.0,
        "sent_pct": round(sent_count / total_routes * 100, 1) if total_routes else 0.0,
        "top_grade_sent": top_grade,
        "total_load": total_load,
        "avg_load_per_session": avg_load,
    }
