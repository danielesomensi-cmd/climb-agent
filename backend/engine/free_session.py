"""Free climbing session engine — grade utilities, load calculation, summary."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ── Grade scale ──────────────────────────────────────────────────────────
# Fontainebleau full scale (half-grades included).
# Used for free session logging — supports both boulder uppercase (7A)
# and lowercase input (7a) via normalize.

FONT_GRADES: List[str] = [
    "4A", "4B", "4C",
    "5A", "5A+", "5B", "5B+", "5C", "5C+",
    "6A", "6A+", "6B", "6B+", "6C", "6C+",
    "7A", "7A+", "7B", "7B+", "7C", "7C+",
    "8A", "8A+", "8B", "8B+", "8C", "8C+",
]
_FONT_TO_INDEX = {g: i for i, g in enumerate(FONT_GRADES)}

# Surfaces (always all available, no equipment filter)
SURFACES = [
    {"id": "gym_boulder", "name": "Gym Boulder"},
    {"id": "board_kilter", "name": "Kilter Board"},
    {"id": "board_moonboard", "name": "MoonBoard"},
    {"id": "board_other", "name": "Other Board"},
    {"id": "gym_routes", "name": "Lead / Top-rope"},
    {"id": "circuit_core", "name": "Core Circuit"},
]

SURFACE_IDS = {s["id"] for s in SURFACES}

LEAD_SURFACES = {"gym_routes"}

VALID_CONTEXTS = {"standalone", "add_on", "replacement"}
VALID_SESSION_MODES = {"template", "free", "circuit"}
VALID_CLIMB_STATUSES = {"flash", "sent", "attempted"}
VALID_CLIMB_STYLES = {"onsight", "flash", "redpoint", "project"}
VALID_FEELS = {"easy", "good", "hard"}


def font_to_index(grade: str) -> Optional[int]:
    """Return 0-based index for a Fontainebleau grade, or None if invalid."""
    cleaned = str(grade).strip().upper().replace(" ", "")
    return _FONT_TO_INDEX.get(cleaned)


def index_to_font(index: int) -> Optional[str]:
    """Return Fontainebleau grade for a 0-based index, or None if out of range."""
    if 0 <= index < len(FONT_GRADES):
        return FONT_GRADES[index]
    return None


def offset_grade(base_grade: str, offset: int) -> Optional[str]:
    """Apply an integer offset to a grade. Clamps to valid range."""
    idx = font_to_index(base_grade)
    if idx is None:
        return None
    new_idx = max(0, min(len(FONT_GRADES) - 1, idx + offset))
    return index_to_font(new_idx)


def normalize_grade(grade: str) -> Optional[str]:
    """Normalize a grade string to uppercase Fontainebleau. None if invalid."""
    cleaned = str(grade).strip().upper().replace(" ", "")
    return cleaned if cleaned in _FONT_TO_INDEX else None


def is_lead_surface(surface: str) -> bool:
    """Return True if surface is a lead/route surface."""
    return surface in LEAD_SURFACES


# ── Validation ───────────────────────────────────────────────────────────

def validate_climb(climb: Dict[str, Any], surface: str) -> Optional[str]:
    """Validate a climb dict. Returns error message or None if valid."""
    grade = climb.get("grade")
    if not grade or normalize_grade(grade) is None:
        return f"Invalid grade: {grade}"

    status = climb.get("status")
    if status not in VALID_CLIMB_STATUSES:
        return f"Invalid status: {status}. Must be one of {VALID_CLIMB_STATUSES}"

    attempts = climb.get("attempts")
    if attempts is None or not isinstance(attempts, int) or attempts < 1:
        return "attempts must be a positive integer"
    if status == "flash" and attempts != 1:
        return "flash status requires exactly 1 attempt"
    if status == "sent" and attempts < 2:
        return "sent status requires at least 2 attempts"

    if is_lead_surface(surface):
        style = climb.get("style")
        if style is not None and style not in VALID_CLIMB_STYLES:
            return f"Invalid style: {style}. Must be one of {VALID_CLIMB_STYLES}"
        topped = climb.get("topped")
        if topped is not None and not isinstance(topped, bool):
            return "topped must be a boolean"

    return None


# ── Summary ──────────────────────────────────────────────────────────────

def compute_summary(climbs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute session summary from a list of climbs."""
    total = len(climbs)
    flashed = sum(1 for c in climbs if c.get("status") == "flash")
    sent = sum(1 for c in climbs if c.get("status") == "sent")
    attempted = sum(1 for c in climbs if c.get("status") == "attempted")

    sent_grades = [
        font_to_index(c["grade"]) for c in climbs
        if c.get("status") in ("flash", "sent") and font_to_index(c["grade"]) is not None
    ]
    attempted_grades = [
        font_to_index(c["grade"]) for c in climbs
        if font_to_index(c["grade"]) is not None
    ]

    max_grade_sent = index_to_font(max(sent_grades)) if sent_grades else None
    max_grade_attempted = index_to_font(max(attempted_grades)) if attempted_grades else None

    completed = flashed + sent
    send_rate = round(completed / total, 2) if total > 0 else 0.0

    return {
        "total_climbs": total,
        "flashed": flashed,
        "sent": sent,
        "attempted": attempted,
        "max_grade_sent": max_grade_sent,
        "max_grade_attempted": max_grade_attempted,
        "send_rate": send_rate,
    }


# ── Load calculation ─────────────────────────────────────────────────────

_STATUS_WEIGHT = {
    "flash": 0.8,
    "sent": 1.0,
    "attempted": 0.6,
}


def _attempt_modifier(attempts: int) -> float:
    if attempts <= 1:
        return 1.0
    if attempts == 2:
        return 1.1
    return 1.3


def compute_free_session_load(climbs: List[Dict[str, Any]], user_max_grade: str) -> float:
    """Compute load score for a free session.

    Formula v1: sum(relative_difficulty * status_weight * attempt_modifier) * SCALE_FACTOR

    SCALE_FACTOR aligns the free session scale (~1-10 raw) with the engine
    estimated_load_score scale (20-85). Calibrated so that a typical volume
    session (20 moderate boulders) ≈ 40 (engine "medium" intensity).
    """
    # Aligns raw per-climb accumulation to engine load scale (low=20..max=85)
    _SCALE_FACTOR = 4.0

    max_idx = font_to_index(user_max_grade)
    if max_idx is None or max_idx == 0:
        return 0.0

    total = 0.0
    for climb in climbs:
        grade_idx = font_to_index(climb.get("grade", ""))
        if grade_idx is None:
            continue

        relative = grade_idx / max_idx
        status = climb.get("status", "attempted")
        weight = _STATUS_WEIGHT.get(status, 0.6)
        attempts = climb.get("attempts", 1)
        mod = _attempt_modifier(attempts)

        total += relative * weight * mod

    return round(total * _SCALE_FACTOR, 1)


# ── Phase lookup ─────────────────────────────────────────────────────────

def get_phase_for_date(user_state: Dict[str, Any], date_str: str) -> str:
    """Get macrocycle phase_id for a given date. Falls back to 'base'."""
    from datetime import datetime

    mc = user_state.get("macrocycle") or {}
    phases = mc.get("phases") or []
    if not phases:
        return "base"

    start_str = mc.get("start_date")
    if not start_str:
        return str(phases[0].get("phase_id", "base"))

    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        target = datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return str(phases[0].get("phase_id", "base"))

    elapsed_weeks = max(0, (target - start).days // 7)
    cumulative = 0
    for phase in phases:
        cumulative += phase.get("duration_weeks", 1)
        if elapsed_weeks < cumulative:
            return str(phase.get("phase_id", "base"))

    return str(phases[-1].get("phase_id", "base"))


def get_user_max_grade(user_state: Dict[str, Any], surface: str) -> Optional[str]:
    """Get user's max grade for a surface from assessment."""
    grades = (user_state.get("assessment") or {}).get("grades") or {}
    if is_lead_surface(surface):
        return grades.get("lead_max_rp")
    return grades.get("boulder_max_rp")


def get_user_gyms(user_state: Dict[str, Any]) -> List[Dict[str, str]]:
    """Get list of user's saved gyms [{gym_id, name}]."""
    equipment = user_state.get("equipment") or {}
    gyms = equipment.get("gyms") or []
    return [{"gym_id": g.get("gym_id", ""), "name": g.get("name", "")} for g in gyms]
