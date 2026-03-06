"""Phase-aware weekly planner v2 — generates a week plan from macrocycle phase context.

This planner is macrocycle-aware: it selects sessions from the phase's session pool,
respects domain weights, and enforces per-phase intensity caps and constraints.

Constraints:
- No consecutive finger days (48h gap)
- No consecutive max-intensity days
- Hard day cap per week (from planning_prefs)
- Phase intensity cap limits session selection
- Deload weeks enforce reduced volume
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.engine.macrocycle_v1 import (
    PHASE_INTENSITY_CAP,
    PHASE_ORDER,
    _build_session_pool,
    apply_deload_week,
)

SLOTS: Tuple[str, ...] = ("morning", "lunch", "evening")
WEEKDAYS: Tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Session metadata — maps session_id to its properties
# hard: counts against hard_cap; finger: needs 48h gap; intensity: max/high/medium/low
# climbing: True for climbing-related sessions (placed first in pass 1)
_SESSION_META: Dict[str, Dict[str, Any]] = {
    "strength_long": {"hard": True, "finger": True, "intensity": "max", "climbing": True, "location": ("gym", "home"), "required_equipment": ["hangboard"]},
    "power_contact_gym": {"hard": True, "finger": False, "intensity": "max", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"]},
    "power_endurance_gym": {"hard": True, "finger": False, "intensity": "high", "climbing": True, "location": ("gym",), "required_equipment": ["gym_routes"]},
    "endurance_aerobic_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "max_per_week": 2, "required_equipment": ["gym_routes"]},
    "technique_focus_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"]},
    "finger_strength_home": {"hard": True, "finger": True, "intensity": "high", "climbing": True, "location": ("home",), "required_equipment": ["hangboard"]},
    "prehab_maintenance": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym")},
    "flexibility_full": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym")},
    "yoga_recovery": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home",)},
    "handstand_practice": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym")},
    "complementary_conditioning": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym")},
    "regeneration_easy": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym", "outdoor")},
    "finger_maintenance_home": {"hard": False, "finger": True, "intensity": "medium", "climbing": True, "location": ("home",), "required_equipment": ["hangboard"]},
    "test_max_hang_5s": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["hangboard"]},
    "test_repeater_7_3": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["hangboard"]},
    "test_max_weighted_pullup": {"hard": True, "finger": False, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["pullup_bar"]},
    "easy_climbing_deload": {"hard": False, "finger": False, "intensity": "low", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"]},
    "finger_maintenance_gym": {"hard": False, "finger": True, "intensity": "medium", "climbing": True, "location": ("gym",), "required_equipment": ["hangboard"]},
    "route_endurance_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "required_equipment": ["gym_routes"]},
    "pulling_strength_gym": {"hard": True, "finger": False, "intensity": "high", "climbing": False, "location": ("gym",), "required_equipment": ["pullup_bar"]},
    "heavy_conditioning_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym",), "required_equipment": ["dumbbell"]},
    "lower_body_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym",), "required_equipment": ["dumbbell"]},
    "finger_aerobic_base": {"hard": False, "finger": True, "intensity": "low", "climbing": False, "location": ("home",), "required_equipment": ["hangboard"]},
    "deload_recovery": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym")},
    "finger_endurance_short": {"hard": False, "finger": True, "intensity": "medium", "climbing": False, "location": ("home",), "required_equipment": ["hangboard"]},
    "boulder_circuit_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "max_per_week": 2, "required_equipment": ["gym_boulder"]},
    "upper_body_weights": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym", "home"), "required_equipment": [], "max_per_week": 2},
    "legs_strength": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym", "home"), "required_equipment": [], "max_per_week": 2},
    "core_training": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym", "home"), "required_equipment": [], "max_per_week": 3},
}

_INTENSITY_ORDER = {"low": 0, "medium": 1, "high": 2, "max": 3}

# Fallback load score for unresolved sessions (real score uses fatigue_cost from exercises)
_INTENSITY_TO_LOAD: Dict[str, int] = {"low": 20, "medium": 40, "high": 65, "max": 85}

# Fallback climbing sessions tried (in order) when Pass 1 couldn't place any climbing
# on a gym-available day due to equipment constraints (Bug B fix).
# All require only gym_boulder — the most common gym equipment.
_CLIMBING_FALLBACKS: Tuple[str, ...] = ("technique_focus_gym", "easy_climbing_deload")


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _weekday_key(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def _intensity_allowed(session_intensity: str, phase_cap: str) -> bool:
    """Check if a session's intensity level is within the phase cap."""
    return _INTENSITY_ORDER.get(session_intensity, 0) <= _INTENSITY_ORDER.get(phase_cap, 3)


def _equipment_for_location(
    location: str,
    slot_info: Dict[str, Any],
    home_equipment: Optional[List[str]],
    gyms: Optional[Sequence[Dict[str, Any]]],
    default_gym_id: Optional[str],
) -> Optional[List[str]]:
    """Return equipment list available at *location* for the given slot.

    Returns None when equipment is unknown (no gym data / no home data),
    meaning "assume everything is available" (backwards compat).
    """
    if location == "gym":
        # Every gym implicitly has a pullup_bar (commit 6bf5e75).
        gym_id = slot_info.get("gym_id") or default_gym_id
        equip: List[str] = []
        matched = False
        for g in (gyms or []):
            if gym_id and g.get("gym_id") == gym_id:
                equip = list(g.get("equipment", []))
                matched = True
                break
        if not matched and gyms:
            sorted_g = sorted(gyms, key=lambda g: (g.get("priority", 999), g.get("gym_id", "")))
            equip = list(sorted_g[0].get("equipment", []))
            matched = True
        if not matched:
            return None  # no gym info → assume everything available
        if "pullup_bar" not in equip:
            equip.append("pullup_bar")
        return equip
    elif location == "home":
        if home_equipment is None:
            return None  # no home info → assume everything available
        return list(home_equipment)
    return None


def _location_has_equipment(
    location: str,
    required_equipment: List[str],
    slot_info: Dict[str, Any],
    home_equipment: Optional[List[str]],
    gyms: Optional[Sequence[Dict[str, Any]]],
    default_gym_id: Optional[str],
) -> bool:
    """Check if *location* provides all items in *required_equipment*.

    For gym locations with no specific gym_id, iterates ALL gyms by priority
    and returns True if ANY gym satisfies the required equipment (Bug A fix).
    """
    if not required_equipment:
        return True
    if location == "gym":
        gym_id = slot_info.get("gym_id") or default_gym_id
        if gym_id:
            # Specific gym requested — check only that gym
            avail = _equipment_for_location(location, slot_info, home_equipment, gyms, default_gym_id)
            if avail is None:
                return True
            return all(eq in avail for eq in required_equipment)
        # No specific gym: check if ANY gym has all required equipment
        if not gyms:
            return True  # no gym info → assume available (backwards compat)
        for g in sorted(gyms, key=lambda g: (g.get("priority", 999), g.get("gym_id", ""))):
            equip = list(g.get("equipment", []))
            if "pullup_bar" not in equip:
                equip.append("pullup_bar")
            if all(eq in equip for eq in required_equipment):
                return True
        return False
    avail = _equipment_for_location(location, slot_info, home_equipment, gyms, default_gym_id)
    if avail is None:
        return True  # unknown equipment → assume available (backwards compat)
    return all(eq in avail for eq in required_equipment)


def _pick_location(
    session_locations: Tuple[str, ...],
    slot_info: Dict[str, Any],
    allowed_locations: Sequence[str],
    required_equipment: Optional[List[str]] = None,
    home_equipment: Optional[List[str]] = None,
    gyms: Optional[Sequence[Dict[str, Any]]] = None,
    default_gym_id: Optional[str] = None,
) -> Optional[str]:
    slot_locations = slot_info.get("locations") or list(allowed_locations)
    viable = sorted(set(slot_locations).intersection(session_locations).intersection(allowed_locations))
    if not viable:
        return None
    preferred = slot_info.get("preferred_location")
    if isinstance(preferred, str):
        if preferred in viable:
            # Preferred is viable by location rules — check equipment
            if required_equipment and not _location_has_equipment(
                preferred, required_equipment, slot_info, home_equipment, gyms, default_gym_id
            ):
                # Preferred lacks equipment → try other viable locations
                for loc in viable:
                    if loc != preferred and _location_has_equipment(
                        loc, required_equipment, slot_info, home_equipment, gyms, default_gym_id
                    ):
                        return loc
                return None  # no viable location has the equipment
            return preferred
        return None  # session can't satisfy location preference
    # No preference — pick first viable with equipment
    if required_equipment:
        viable = [
            loc for loc in viable
            if _location_has_equipment(loc, required_equipment, slot_info, home_equipment, gyms, default_gym_id)
        ]
        if not viable:
            return None
    return viable[0]


def _normalize_availability(
    availability: Optional[Dict[str, Any]],
    allowed_locations: Sequence[str],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    normalized: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for wd in WEEKDAYS:
        day = (availability or {}).get(wd) or {}
        # Detect whether this day dict has any explicit slot keys
        has_explicit_slots = isinstance(day, dict) and any(
            s in day for s in SLOTS
        )
        day_slots: Dict[str, Dict[str, Any]] = {}
        for slot in SLOTS:
            default = {"available": True, "locations": sorted(set(allowed_locations)),
                        "preferred_location": None, "gym_id": None}
            if isinstance(day, dict) and day.get("available") is False:
                default["available"] = False
                day_slots[slot] = default
                continue
            slot_value = day.get(slot)
            if slot_value is None:
                if has_explicit_slots:
                    default["available"] = False
                day_slots[slot] = default
                continue
            if isinstance(slot_value, bool):
                default["available"] = slot_value
            elif isinstance(slot_value, dict):
                default["available"] = bool(slot_value.get("available", True))
                # Slot used for other sport → not available for climbing
                if slot_value.get("preferred_location") == "other_sport":
                    default["available"] = False
                    day_slots[slot] = default
                    continue
                if "locations" in slot_value and isinstance(slot_value["locations"], list):
                    default["locations"] = sorted(set(slot_value["locations"]))
                preferred = slot_value.get("preferred_location")
                if isinstance(preferred, str):
                    default["preferred_location"] = preferred
                gym_id = slot_value.get("gym_id")
                if isinstance(gym_id, str) and gym_id:
                    default["gym_id"] = gym_id
            day_slots[slot] = default
        normalized[wd] = day_slots
    return normalized


def _select_gym_id(
    slot_info: Dict[str, Any],
    default_gym_id: Optional[str],
    gyms: Sequence[Dict[str, Any]],
    required_equipment: Optional[List[str]] = None,
) -> Optional[str]:
    """Return the gym_id to assign to a session.

    When no specific gym is requested and required_equipment is given,
    picks the first gym by priority that satisfies all required equipment (Bug A fix).
    Falls back to first-by-priority gym if none fully satisfies requirements.
    """
    slot_gym = slot_info.get("gym_id")
    if slot_gym:
        return slot_gym
    if default_gym_id:
        return default_gym_id
    if gyms:
        sorted_gyms = sorted(gyms, key=lambda g: (g.get("priority", 999), g.get("gym_id", "")))
        if required_equipment:
            for g in sorted_gyms:
                equip = list(g.get("equipment", []))
                if "pullup_bar" not in equip:
                    equip.append("pullup_bar")
                if all(eq in equip for eq in required_equipment):
                    return g.get("gym_id")
        return sorted_gyms[0].get("gym_id")
    return None


def _is_primary_session(meta: Dict[str, Any]) -> bool:
    """A session is primary if it's hard or climbing-related."""
    return bool(meta.get("hard") or meta.get("climbing"))


def _find_best_slot(
    day_availability: Dict[str, Dict[str, Any]],
    meta: Dict[str, Any],
    locations: Sequence[str],
    prefer_evening: bool = True,
    home_equipment: Optional[List[str]] = None,
    gyms: Optional[Sequence[Dict[str, Any]]] = None,
    default_gym_id: Optional[str] = None,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Find the best available slot for a session on a given day.

    Primary sessions prefer evening > morning > lunch.
    Complementary sessions prefer lunch > morning > evening.
    """
    if prefer_evening:
        slot_order = ("evening", "morning", "lunch")
    else:
        slot_order = ("lunch", "morning", "evening")

    req_equip = meta.get("required_equipment")
    for slot in slot_order:
        slot_info = day_availability[slot]
        if not slot_info["available"]:
            continue
        location = _pick_location(
            meta["location"], slot_info, locations,
            required_equipment=req_equip,
            home_equipment=home_equipment,
            gyms=gyms,
            default_gym_id=default_gym_id,
        )
        if location is not None:
            return slot, slot_info
    return None


def _make_session_entry(
    slot: str,
    sid: str,
    meta: Dict[str, Any],
    slot_info: Dict[str, Any],
    locations: Sequence[str],
    phase_id: str,
    day_key: str,
    default_gym_id: Optional[str],
    gyms: Sequence[Dict[str, Any]],
    pass_label: str,
    home_equipment: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a session entry dict for the week plan."""
    req_equip = meta.get("required_equipment")
    location = _pick_location(
        meta["location"], slot_info, locations,
        required_equipment=req_equip,
        home_equipment=home_equipment,
        gyms=gyms,
        default_gym_id=default_gym_id,
    )
    gym_id = None
    if location == "gym":
        gym_id = _select_gym_id(slot_info, default_gym_id, gyms, required_equipment=req_equip)

    return {
        "slot": slot,
        "session_id": sid,
        "location": location,
        "gym_id": gym_id,
        "phase_id": phase_id,
        "intensity": meta["intensity"],
        "estimated_load_score": _INTENSITY_TO_LOAD.get(meta["intensity"], 40),
        "tags": {"hard": meta["hard"], "finger": meta["finger"], **({"test": True} if meta.get("test") else {})},
        "explain": [
            f"phase={phase_id}",
            f"slot={slot}",
            f"day={day_key}",
            pass_label,
        ],
    }


def generate_phase_week(
    *,
    phase_id: str,
    domain_weights: Dict[str, float],
    session_pool: List[str],
    start_date: str,
    availability: Optional[Dict[str, Any]] = None,
    allowed_locations: Optional[List[str]] = None,
    hard_cap_per_week: int = 3,
    planning_prefs: Optional[Dict[str, Any]] = None,
    default_gym_id: Optional[str] = None,
    gyms: Optional[List[Dict[str, Any]]] = None,
    intensity_cap: Optional[str] = None,
    pretrip_dates: Optional[List[str]] = None,
    is_last_week_of_phase: bool = False,
    home_equipment: Optional[List[str]] = None,
    today: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a single week plan within a macrocycle phase.

    Uses a 2-pass algorithm:
      PASS 1: Place primary sessions (hard + climbing-related) with spacing constraints.
      PASS 2: Fill remaining days with complementary sessions.
    Both passes cycle through the pool (max 2 full cycles per pass).

    Args:
        phase_id: Current macrocycle phase (base, strength_power, etc.).
        domain_weights: Domain weight dict from the macrocycle phase.
        session_pool: Ordered list of session_ids for this phase.
        start_date: YYYY-MM-DD Monday of the week.
        availability: User availability dict.
        allowed_locations: Allowed location strings.
        hard_cap_per_week: Max hard sessions per week.
        planning_prefs: User planning preferences.
        default_gym_id: Default gym for gym sessions.
        gyms: List of gym dicts with equipment.
        intensity_cap: Phase intensity cap (overrides PHASE_INTENSITY_CAP if provided).
        pretrip_dates: List of YYYY-MM-DD dates that are in pre-trip deload window.
            Hard/max sessions are blocked on these dates.

    Returns:
        Week plan dict compatible with planner.v1 format.
    """
    locations = sorted(set(allowed_locations or ["home", "gym"]))
    normalized = _normalize_availability(availability, locations)
    cap = intensity_cap or PHASE_INTENSITY_CAP.get(phase_id, "max")
    prefs = planning_prefs or {}
    effective_hard_cap = min(hard_cap_per_week, prefs.get("hard_day_cap_per_week", hard_cap_per_week))

    # Build set of pre-trip deload dates for fast lookup
    pretrip_set: set = set()
    for d_str in (pretrip_dates or []):
        pretrip_set.add(_parse_date(d_str))

    if phase_id == "deload":
        effective_hard_cap = 0

    # Filter session pool by intensity cap and available metadata
    filtered_pool: List[str] = []
    for sid in session_pool:
        meta = _SESSION_META.get(sid)
        if meta is None:
            continue
        if not _intensity_allowed(meta["intensity"], cap):
            continue
        filtered_pool.append(sid)

    # Split into primary (hard/climbing) and complementary pools
    primary_pool = [s for s in filtered_pool if _is_primary_session(_SESSION_META[s])]
    complementary_pool = [s for s in filtered_pool if not _is_primary_session(_SESSION_META[s])]

    start = _parse_date(start_date)
    target_days = prefs.get("target_training_days_per_week", 4)

    # B95: resolve "today" for skipping past days
    today_date: Optional[date] = _parse_date(today) if today else None

    # Build day structures
    day_dates: List[date] = [start + timedelta(days=i) for i in range(7)]
    day_keys: List[str] = [_weekday_key(d) for d in day_dates]
    day_sessions: List[List[Dict[str, Any]]] = [[] for _ in range(7)]

    # Extract other-activity flags from availability.
    # Sources: legacy _day_meta OR per-slot preferred_location="other_sport".
    day_other_activity: List[bool] = [False] * 7
    day_reduce_after: List[bool] = [False] * 7
    day_activity_name: List[Optional[str]] = [None] * 7
    day_activity_slot: List[Optional[str]] = [None] * 7
    for offset in range(7):
        raw_day = (availability or {}).get(day_keys[offset]) or {}
        if not isinstance(raw_day, dict):
            continue
        # Legacy _day_meta approach
        meta = raw_day.get("_day_meta")
        if isinstance(meta, dict) and meta.get("other_activity"):
            day_other_activity[offset] = True
            day_activity_name[offset] = meta.get("other_activity_name")
            day_activity_slot[offset] = meta.get("other_activity_slot")
            day_reduce_after[offset] = bool(meta.get("reduce_intensity_after"))
        # Per-slot approach: preferred_location="other_sport"
        for s_key in SLOTS:
            slot_val = raw_day.get(s_key)
            if isinstance(slot_val, dict) and slot_val.get("preferred_location") == "other_sport":
                day_other_activity[offset] = True
                day_activity_slot[offset] = s_key
                day_activity_name[offset] = slot_val.get("other_activity_name") or day_activity_name[offset]
                day_reduce_after[offset] = day_reduce_after[offset] or bool(slot_val.get("reduce_intensity_after"))

    # Track constraints
    hard_days = 0
    finger_day_offsets: List[int] = []
    hard_day_offsets: List[int] = []
    session_count: Dict[str, int] = {}  # anti-repetition: session_id → times placed this week

    # Reduce intensity on day after other-activity (when flagged)
    # AND on the other-activity day itself (no hard sessions alongside other sport).
    day_intensity_reduced: List[bool] = [False] * 7
    for offset in range(7):
        if offset > 0 and day_other_activity[offset - 1] and day_reduce_after[offset - 1]:
            day_intensity_reduced[offset] = True

    # Determine which days have available slots
    # Track outdoor-only days — they get no sessions from the planner
    day_is_outdoor: List[bool] = [False] * 7
    day_has_available_slot: List[bool] = []
    for offset in range(7):
        # B95: skip past days — no sessions assigned to days before today
        if today_date is not None and day_dates[offset] < today_date:
            day_has_available_slot.append(False)
            continue
        day_avail = normalized[day_keys[offset]]
        if day_other_activity[offset]:
            # other_activity occupies one slot but does NOT block all sessions;
            # the day is still available but intensity-reduced (no hard sessions).
            day_intensity_reduced[offset] = True
        # Check if ALL available slots on this day are outdoor-only
        available_slots = [s for s in SLOTS if day_avail[s]["available"]]
        if available_slots:
            all_outdoor = all(
                day_avail[s].get("preferred_location") == "outdoor"
                or day_avail[s].get("locations") == ["outdoor"]
                for s in available_slots
            )
            if all_outdoor:
                day_is_outdoor[offset] = True
                day_has_available_slot.append(False)  # skip for session assignment
                continue
        has_slot = any(day_avail[slot]["available"] for slot in SLOTS)
        day_has_available_slot.append(has_slot)

    # Cap available days to target_training_days_per_week
    available_day_count = sum(day_has_available_slot)
    if available_day_count > target_days:
        day_scores: List[Tuple[int, int]] = []
        for offset in range(7):
            if not day_has_available_slot[offset]:
                continue
            day_avail = normalized[day_keys[offset]]
            score = 0
            for s in SLOTS:
                si = day_avail[s]
                if not si["available"]:
                    continue
                # Scoring priorities:
                # 1. Gym preferred or gym-only slot: +100 (climbing sessions need gym)
                # 2. Gym available but not preferred: +50
                # 3. Home-only slot: +1 (baseline)
                slot_locs = si.get("locations", [])
                preferred = si.get("preferred_location")
                is_gym = preferred == "gym" or (preferred is None and "gym" in slot_locs)
                if is_gym:
                    score += 100
                elif "gym" in slot_locs:
                    score += 50
                else:
                    score += 1
                if s == "evening":
                    score += 10
            day_scores.append((score, offset))
        # Stable sort: by score descending, then offset ascending
        day_scores.sort(key=lambda x: (-x[0], x[1]))
        keep_offsets = set(x[1] for x in day_scores[:target_days])
        for offset in range(7):
            if offset not in keep_offsets:
                day_has_available_slot[offset] = False

    # ── PASS 1: Place primary sessions (climbing-first) ──
    primary_idx = 0
    primary_uses = 0
    max_primary_uses = len(primary_pool) * 2 if primary_pool else 0  # max 2 cycles

    # Sort day offsets: gym-available days first, then home-only, preserving weekday order within groups
    def _day_has_gym(offset: int) -> bool:
        day_avail = normalized[day_keys[offset]]
        return any(
            day_avail[s]["available"] and (
                day_avail[s].get("preferred_location") == "gym"
                or "gym" in day_avail[s].get("locations", [])
            )
            for s in SLOTS
        )

    pass1_day_order = sorted(
        [o for o in range(7) if day_has_available_slot[o]],
        key=lambda o: (0 if _day_has_gym(o) else 1, o),
    )

    for offset in pass1_day_order:
        if not day_has_available_slot[offset]:
            continue
        if not primary_pool:
            break
        if primary_uses >= max_primary_uses:
            break

        placed = False
        attempts = 0
        while attempts < len(primary_pool) and primary_uses < max_primary_uses:
            sid = primary_pool[primary_idx % len(primary_pool)]
            meta = _SESSION_META[sid]

            skip = False

            # Anti-repetition: max N times per week (default 1)
            max_pw = meta.get("max_per_week", 1)
            if session_count.get(sid, 0) >= max_pw:
                skip = True

            # Other-activity intensity reduction: no hard sessions on reduced day
            if not skip and day_intensity_reduced[offset] and meta["hard"]:
                skip = True

            # Pre-trip deload: no hard/max sessions on pretrip dates
            if not skip and day_dates[offset] in pretrip_set and (meta["hard"] or meta["intensity"] == "max"):
                skip = True

            # Hard day cap
            if not skip and meta["hard"] and hard_days >= effective_hard_cap:
                skip = True

            # No consecutive finger days (48h gap)
            if not skip and meta["finger"] and finger_day_offsets:
                last_finger_offset = finger_day_offsets[-1]
                if (offset - last_finger_offset) <= 1:
                    skip = True

            # No consecutive hard/max-intensity days
            if not skip and meta["hard"] and hard_day_offsets:
                last_hard_offset = hard_day_offsets[-1]
                if (offset - last_hard_offset) <= 1:
                    skip = True

            if skip:
                primary_idx += 1
                primary_uses += 1
                attempts += 1
                continue

            day_avail = normalized[day_keys[offset]]
            result = _find_best_slot(day_avail, meta, locations, prefer_evening=True,
                                     home_equipment=home_equipment, gyms=gyms, default_gym_id=default_gym_id)
            if result is None:
                # Equipment/location mismatch for THIS day — don't burn a pool
                # cycle use.  The session may fit on a later day with different
                # equipment, so only advance the index and attempt counter.
                primary_idx += 1
                attempts += 1
                continue  # try next session for SAME day

            slot, slot_info = result
            entry = _make_session_entry(
                slot, sid, meta, slot_info, locations, phase_id, day_keys[offset],
                default_gym_id, gyms or [], "pass1:primary", home_equipment=home_equipment,
            )
            day_sessions[offset].append(entry)
            session_count[sid] = session_count.get(sid, 0) + 1
            primary_idx += 1
            primary_uses += 1

            if meta["hard"]:
                hard_days += 1
                hard_day_offsets.append(offset)
            if meta["finger"]:
                finger_day_offsets.append(offset)
            placed = True
            break

    # ── PASS 1.5: Climbing fallback for gym days left empty by Pass 1 ──
    # Triggers only when:
    #   (a) pool has climbing sessions but NONE are gym_boulder-compatible (all require gym_routes),
    #   (b) the specific gym accessible on the day lacks gym_routes.
    # In this narrow case Pass 1 could not place any climbing due to equipment mismatch,
    # so we inject a fallback gym_boulder session rather than losing climbing entirely.
    pool_has_climbing = any(_SESSION_META.get(sid, {}).get("climbing") for sid in primary_pool)
    pool_has_gym_boulder_climbing = any(
        _SESSION_META.get(sid, {}).get("climbing")
        and "gym_boulder" in _SESSION_META.get(sid, {}).get("required_equipment", [])
        for sid in primary_pool
    )
    # If pool already has gym_boulder climbing options, pass 1 handles them normally.
    if pool_has_climbing and not pool_has_gym_boulder_climbing:
        for offset in pass1_day_order:
            if not day_has_available_slot[offset]:
                continue
            # Only apply when pass 1 left the day completely empty
            if day_sessions[offset]:
                continue
            # Only apply when the day has gym availability
            day_avail = normalized[day_keys[offset]]
            has_gym_slot = any(
                day_avail[s]["available"] and (
                    day_avail[s].get("preferred_location") == "gym"
                    or "gym" in day_avail[s].get("locations", [])
                )
                for s in SLOTS
            )
            if not has_gym_slot:
                continue
            # Only trigger when the accessible gym actually lacks gym_routes.
            # If ANY gym on this day has gym_routes, pass 1 should have placed normally;
            # an empty day here means pool exhaustion, not an equipment gap.
            day_gym_can_do_routes = False
            for s_name in SLOTS:
                if not day_avail[s_name]["available"]:
                    continue
                slot_gym = day_avail[s_name].get("gym_id") or default_gym_id
                if slot_gym:
                    for g in (gyms or []):
                        if g.get("gym_id") == slot_gym and "gym_routes" in g.get("equipment", []):
                            day_gym_can_do_routes = True
                            break
                elif gyms:
                    for g in sorted(gyms, key=lambda g: (g.get("priority", 999), g.get("gym_id", ""))):
                        if "gym_routes" in g.get("equipment", []):
                            day_gym_can_do_routes = True
                            break
                if day_gym_can_do_routes:
                    break
            if day_gym_can_do_routes:
                continue  # gym can do routes — pool sessions should have been placed
            for fb_sid in _CLIMBING_FALLBACKS:
                fb_meta = _SESSION_META.get(fb_sid)
                if fb_meta is None:
                    continue
                if not _intensity_allowed(fb_meta["intensity"], cap):
                    continue
                if session_count.get(fb_sid, 0) >= fb_meta.get("max_per_week", 1):
                    continue
                if fb_meta.get("hard") and hard_days >= effective_hard_cap:
                    continue
                if fb_meta.get("finger") and finger_day_offsets and (offset - finger_day_offsets[-1]) <= 1:
                    continue
                result = _find_best_slot(
                    day_avail, fb_meta, locations, prefer_evening=True,
                    home_equipment=home_equipment, gyms=gyms, default_gym_id=default_gym_id,
                )
                if result:
                    slot, slot_info = result
                    entry = _make_session_entry(
                        slot, fb_sid, fb_meta, slot_info, locations, phase_id,
                        day_keys[offset], default_gym_id, gyms or [],
                        "pass1.5:climbing_fallback", home_equipment=home_equipment,
                    )
                    day_sessions[offset].append(entry)
                    session_count[fb_sid] = session_count.get(fb_sid, 0) + 1
                    if fb_meta.get("hard"):
                        hard_days += 1
                        hard_day_offsets.append(offset)
                    if fb_meta.get("finger"):
                        finger_day_offsets.append(offset)
                    break

    # ── PASS 2: Fill remaining days with complementary sessions ──
    days_with_sessions = sum(1 for ds in day_sessions if ds)
    comp_idx = 0
    comp_uses = 0
    max_comp_uses = len(complementary_pool) * 2 if complementary_pool else 0

    for offset in range(7):
        if days_with_sessions >= target_days:
            break
        if day_sessions[offset]:
            continue  # Already has a session from pass 1
        if not day_has_available_slot[offset]:
            continue
        if not complementary_pool:
            break
        if comp_uses >= max_comp_uses:
            break

        attempts = 0
        while attempts < len(complementary_pool) and comp_uses < max_comp_uses:
            sid = complementary_pool[comp_idx % len(complementary_pool)]
            meta = _SESSION_META[sid]

            # Anti-repetition check
            max_pw = meta.get("max_per_week", 1)
            if session_count.get(sid, 0) >= max_pw:
                comp_idx += 1
                comp_uses += 1
                attempts += 1
                continue

            day_avail = normalized[day_keys[offset]]
            result = _find_best_slot(day_avail, meta, locations, prefer_evening=False,
                                     home_equipment=home_equipment, gyms=gyms, default_gym_id=default_gym_id)
            if result is None:
                comp_idx += 1
                attempts += 1
                continue  # try next session for SAME day

            slot, slot_info = result
            entry = _make_session_entry(
                slot, sid, meta, slot_info, locations, phase_id, day_keys[offset],
                default_gym_id, gyms or [], "pass2:complementary", home_equipment=home_equipment,
            )
            day_sessions[offset].append(entry)
            session_count[sid] = session_count.get(sid, 0) + 1
            comp_idx += 1
            comp_uses += 1
            days_with_sessions += 1
            break

    # ── PASS 2.5 (NEW-F9): Ensure PE phase has at least 1 finger maintenance session ──
    if phase_id == "power_endurance":
        has_finger_maintenance = any(
            s.get("session_id", "").startswith("finger_maintenance")
            for day_list in day_sessions for s in day_list
        )
        if not has_finger_maintenance:
            fm_candidates = [
                ("finger_maintenance_home", _SESSION_META.get("finger_maintenance_home")),
                ("finger_maintenance_gym", _SESSION_META.get("finger_maintenance_gym")),
            ]
            fm_placed = False
            for offset in range(7):
                if fm_placed:
                    break
                if not day_has_available_slot[offset]:
                    continue
                if day_is_outdoor[offset]:
                    continue
                # Respect 48h finger gap
                if finger_day_offsets and any(abs(offset - fo) <= 1 for fo in finger_day_offsets):
                    continue
                # Try to place in an empty complementary slot first
                if day_sessions[offset]:
                    # Check if we can replace a non-primary session
                    for i, entry in enumerate(day_sessions[offset]):
                        sid_meta = _SESSION_META.get(entry.get("session_id", ""), {})
                        if not _is_primary_session(sid_meta) and not sid_meta.get("finger"):
                            # Replace this complementary session
                            day_avail = normalized[day_keys[offset]]
                            for fm_sid, fm_meta in fm_candidates:
                                if fm_meta is None:
                                    continue
                                result = _find_best_slot(day_avail, fm_meta, locations, prefer_evening=False,
                                                         home_equipment=home_equipment, gyms=gyms, default_gym_id=default_gym_id)
                                if result:
                                    slot, slot_info = result
                                    fm_entry = _make_session_entry(
                                        slot, fm_sid, fm_meta, slot_info, locations,
                                        phase_id, day_keys[offset],
                                        default_gym_id, gyms or [], "pass2.5:pe_finger_maintenance",
                                        home_equipment=home_equipment,
                                    )
                                    day_sessions[offset][i] = fm_entry
                                    finger_day_offsets.append(offset)
                                    fm_placed = True
                                    break
                            break
                else:
                    # Empty day — place directly
                    day_avail = normalized[day_keys[offset]]
                    for fm_sid, fm_meta in fm_candidates:
                        if fm_meta is None:
                            continue
                        result = _find_best_slot(day_avail, fm_meta, locations, prefer_evening=False,
                                                 home_equipment=home_equipment, gyms=gyms, default_gym_id=default_gym_id)
                        if result:
                            slot, slot_info = result
                            fm_entry = _make_session_entry(
                                slot, fm_sid, fm_meta, slot_info, locations,
                                phase_id, day_keys[offset],
                                default_gym_id, gyms or [], "pass2.5:pe_finger_maintenance",
                                home_equipment=home_equipment,
                            )
                            day_sessions[offset].append(fm_entry)
                            finger_day_offsets.append(offset)
                            days_with_sessions += 1
                            fm_placed = True
                            break

    # ── PASS 3 (optional): Inject test sessions on last week of eligible phase ──
    if is_last_week_of_phase and phase_id in ("base", "strength_power"):
        # Required tests first, then optional
        _test_schedule = [
            ("test_max_hang_5s", True),
            ("test_repeater_7_3", True),
            ("test_max_weighted_pullup", False),
        ]
        test_placed_offsets: set = set()
        for test_sid, _required in _test_schedule:
            test_meta = _SESSION_META.get(test_sid)
            if test_meta is None:
                continue
            # Test sessions bypass phase intensity cap — they're assessment protocols
            placed = False
            for offset in range(7):
                if placed:
                    break
                # Skip days already used by a test session in this pass
                if offset in test_placed_offsets:
                    continue
                # Check if this day already has a finger/hard session we'd swap
                day_has_finger = any(
                    _SESSION_META.get(e.get("session_id", ""), {}).get("finger")
                    for e in day_sessions[offset]
                )
                day_has_hard = any(
                    _SESSION_META.get(e.get("session_id", ""), {}).get("hard")
                    for e in day_sessions[offset]
                )
                # Respect finger spacing — but swapping on a day that already has finger is OK
                if test_meta["finger"] and not day_has_finger and finger_day_offsets:
                    if any(abs(offset - fo) <= 1 for fo in finger_day_offsets):
                        continue
                # Respect hard-day spacing — but swapping on a day that already has hard is OK
                if test_meta["hard"] and not day_has_hard and hard_day_offsets:
                    if any(abs(offset - ho) <= 1 for ho in hard_day_offsets):
                        continue
                # Hard cap check
                if test_meta["hard"] and hard_days >= effective_hard_cap:
                    continue
                if not day_sessions[offset]:
                    continue
                day_avail = normalized[day_keys[offset]]
                result = _find_best_slot(day_avail, test_meta, locations, prefer_evening=True,
                                         home_equipment=home_equipment, gyms=gyms, default_gym_id=default_gym_id)
                if result is None:
                    continue
                slot, slot_info = result
                # Pick best session to replace: prefer complementary, fall back to any
                replace_idx = None
                for i, entry in enumerate(day_sessions[offset]):
                    sid_meta = _SESSION_META.get(entry.get("session_id", ""), {})
                    if not _is_primary_session(sid_meta):
                        replace_idx = i
                        break
                if replace_idx is None:
                    # No complementary — replace the last session on this day
                    replace_idx = len(day_sessions[offset]) - 1
                # Check if replacing a hard/finger session frees up constraints
                old_entry = day_sessions[offset][replace_idx]
                old_meta = _SESSION_META.get(old_entry.get("session_id", ""), {})
                test_entry = _make_session_entry(
                    slot, test_sid, test_meta, slot_info, locations,
                    phase_id, day_keys[offset],
                    default_gym_id, gyms or [], "pass3:test_session",
                    home_equipment=home_equipment,
                )
                day_sessions[offset][replace_idx] = test_entry
                if test_meta["hard"] and not old_meta.get("hard"):
                    hard_days += 1
                    hard_day_offsets.append(offset)
                if test_meta["finger"] and not old_meta.get("finger"):
                    finger_day_offsets.append(offset)
                test_placed_offsets.add(offset)
                placed = True

    # Build plan_days
    plan_days: List[Dict[str, Any]] = []
    for offset in range(7):
        day_entry: Dict[str, Any] = {
            "date": day_dates[offset].isoformat(),
            "weekday": day_keys[offset],
            "sessions": day_sessions[offset],
        }
        if day_is_outdoor[offset]:
            day_entry["outdoor_slot"] = True
        if day_dates[offset] in pretrip_set:
            day_entry["pretrip_deload"] = True
        if day_other_activity[offset]:
            day_entry["other_activity"] = True
            if day_activity_name[offset]:
                day_entry["other_activity_name"] = day_activity_name[offset]
            if day_activity_slot[offset]:
                day_entry["other_activity_slot"] = day_activity_slot[offset]
        if day_intensity_reduced[offset]:
            day_entry["prev_other_activity_reduce"] = True
        plan_days.append(day_entry)

    finger_days_count = len(finger_day_offsets)

    # Compute weekly load summary
    total_load = sum(
        s.get("estimated_load_score", 0)
        for day_list in day_sessions for s in day_list
    )
    hard_days_count = sum(
        1 for day_list in day_sessions
        if any(s.get("tags", {}).get("hard") for s in day_list)
    )
    recovery_days_count = sum(
        1 for day_list in day_sessions
        if not day_list or all(s.get("intensity") == "low" for s in day_list)
    )

    week_plan = {
        "plan_version": "planner.v2",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": start_date,
        "profile_snapshot": {
            "phase_id": phase_id,
            "domain_weights": domain_weights,
            "intensity_cap": cap,
            "allowed_locations": locations,
            "hard_cap_per_week": effective_hard_cap,
        },
        "weekly_load_summary": {
            "total_load": total_load,
            "hard_days_count": hard_days_count,
            "recovery_days_count": recovery_days_count,
        },
        "weeks": [
            {
                "week_index": 1,
                "phase": phase_id,
                "targets": {
                    "hard_days": effective_hard_cap,
                    "finger_days": finger_days_count,
                    "deload_factor": 0.5 if phase_id == "deload" else 1.0,
                },
                "days": plan_days,
            }
        ],
    }

    if phase_id == "deload":
        week_plan = apply_deload_week(week_plan)
        # Recompute load summary after deload transformation
        all_deload_sessions = [
            s for d in week_plan["weeks"][0]["days"] for s in d["sessions"]
        ]
        week_plan["weekly_load_summary"] = {
            "total_load": sum(s.get("estimated_load_score", 0) for s in all_deload_sessions),
            "hard_days_count": 0,
            "recovery_days_count": sum(
                1 for d in week_plan["weeks"][0]["days"]
                if not d["sessions"] or all(s.get("intensity") == "low" for s in d["sessions"])
            ),
        }

    return week_plan


# ---------------------------------------------------------------------------
# Test week generation
# ---------------------------------------------------------------------------

# Test schedule: (session_id, is_finger).  Finger tests need 48h spacing.
_TEST_SESSIONS = [
    ("test_max_hang_5s", True),          # finger test — day 1
    ("test_max_weighted_pullup", False),  # non-finger — day 2 (can be consecutive)
    ("test_repeater_7_3", True),          # finger test — day 3 (48h gap from max_hang)
]

_FILLER_SESSIONS = ["prehab_maintenance", "flexibility_full"]


def generate_test_week(
    start_date: str,
    availability: Optional[Dict[str, Any]] = None,
    allowed_locations: Optional[Sequence[str]] = None,
    gyms: Optional[Sequence[Dict[str, Any]]] = None,
    default_gym_id: Optional[str] = None,
    home_equipment: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a 1-week assessment plan with 3 test sessions on non-consecutive days.

    Places test_max_hang_5s and test_repeater_7_3 (both finger) with at least a
    48-hour gap.  test_max_weighted_pullup is placed between them (not a finger test).
    Remaining available days get prehab/flexibility filler sessions.
    """
    locations = list(allowed_locations or ["gym", "home"])
    gyms_list = list(gyms or [])
    norm_avail = _normalize_availability(availability, locations)

    start = _parse_date(start_date)
    days_info: List[Dict[str, Any]] = []
    available_offsets: List[int] = []

    for offset in range(7):
        d = start + timedelta(days=offset)
        wd = _weekday_key(d)
        day_avail = norm_avail.get(wd, {})
        has_slot = any(slot.get("available") for slot in day_avail.values())
        days_info.append({
            "date": d.isoformat(),
            "weekday": wd,
            "day_avail": day_avail,
        })
        if has_slot:
            available_offsets.append(offset)

    # Place 3 test sessions on non-consecutive available days
    # Strategy: pick first available for max_hang, then next non-finger for pullup,
    # then next available ≥2 days after max_hang for repeater
    placed: Dict[int, str] = {}  # offset → session_id

    # Place max_hang_5s (finger)
    hang_offset = None
    for off in available_offsets:
        hang_offset = off
        placed[off] = "test_max_hang_5s"
        break

    # Place weighted_pullup (non-finger) on next available day after hang
    pullup_offset = None
    if hang_offset is not None:
        for off in available_offsets:
            if off > hang_offset and off not in placed:
                pullup_offset = off
                placed[off] = "test_max_weighted_pullup"
                break

    # Place repeater (finger) at least 2 days after max_hang
    if hang_offset is not None:
        min_repeater = hang_offset + 2  # 48h gap
        for off in available_offsets:
            if off >= min_repeater and off not in placed:
                placed[off] = "test_repeater_7_3"
                break

    # Build day plan entries
    plan_days: List[Dict[str, Any]] = []
    total_load = 0
    filler_idx = 0

    for offset in range(7):
        info = days_info[offset]
        day_avail = info["day_avail"]
        sessions: List[Dict[str, Any]] = []

        if offset in placed:
            sid = placed[offset]
            meta = _SESSION_META.get(sid, {})
            req_equip = meta.get("required_equipment")
            # Find a slot
            slot_result = _find_best_slot(day_avail, meta, locations,
                                          home_equipment=home_equipment, gyms=gyms_list, default_gym_id=default_gym_id)
            if slot_result:
                slot_name, slot_info = slot_result
                location = _pick_location(meta.get("location", ("gym", "home")), slot_info, locations,
                                          required_equipment=req_equip, home_equipment=home_equipment,
                                          gyms=gyms_list, default_gym_id=default_gym_id)
                gym_id = _select_gym_id(slot_info, default_gym_id, gyms_list) if location == "gym" else None
                load_score = _INTENSITY_TO_LOAD.get(meta.get("intensity", "high"), 65)
                total_load += load_score
                sessions.append({
                    "slot": slot_name,
                    "session_id": sid,
                    "location": location or "gym",
                    "gym_id": gym_id,
                    "phase_id": "test_week",
                    "intensity": meta.get("intensity", "high"),
                    "estimated_load_score": load_score,
                    "tags": {"hard": meta.get("hard", True), "finger": meta.get("finger", False), "test": True},
                    "explain": [f"test_week: {sid}"],
                })
        elif offset in available_offsets:
            # Fill with easy session
            filler_sid = _FILLER_SESSIONS[filler_idx % len(_FILLER_SESSIONS)]
            filler_idx += 1
            meta = _SESSION_META.get(filler_sid, {})
            slot_result = _find_best_slot(day_avail, meta, locations,
                                          home_equipment=home_equipment, gyms=gyms_list, default_gym_id=default_gym_id)
            if slot_result:
                slot_name, slot_info = slot_result
                location = _pick_location(meta.get("location", ("home", "gym")), slot_info, locations,
                                          required_equipment=meta.get("required_equipment"),
                                          home_equipment=home_equipment, gyms=gyms_list, default_gym_id=default_gym_id)
                gym_id = _select_gym_id(slot_info, default_gym_id, gyms_list) if location == "gym" else None
                load_score = _INTENSITY_TO_LOAD.get(meta.get("intensity", "low"), 20)
                total_load += load_score
                sessions.append({
                    "slot": slot_name,
                    "session_id": filler_sid,
                    "location": location or "home",
                    "gym_id": gym_id,
                    "phase_id": "test_week",
                    "intensity": meta.get("intensity", "low"),
                    "estimated_load_score": load_score,
                    "tags": {"hard": False, "finger": False},
                    "explain": [f"test_week: filler {filler_sid}"],
                })

        plan_days.append({
            "date": info["date"],
            "weekday": info["weekday"],
            "sessions": sessions,
        })

    hard_days_count = sum(1 for d in plan_days if any(s.get("tags", {}).get("hard") for s in d["sessions"]))
    recovery_days_count = sum(1 for d in plan_days if not d["sessions"] or all(s.get("intensity") == "low" for s in d["sessions"]))

    return {
        "plan_version": "test_week.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": start_date,
        "profile_snapshot": {
            "phase_id": "test_week",
            "allowed_locations": locations,
        },
        "weekly_load_summary": {
            "total_load": total_load,
            "hard_days_count": hard_days_count,
            "recovery_days_count": recovery_days_count,
        },
        "weeks": [
            {
                "week_index": 1,
                "phase": "test_week",
                "targets": {
                    "hard_days": hard_days_count,
                    "finger_days": 2,
                    "deload_factor": 1.0,
                },
                "days": plan_days,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Periodic test reminder
# ---------------------------------------------------------------------------

def should_show_test_reminder(user_state: Dict[str, Any], current_week_num: int) -> Optional[Dict[str, Any]]:
    """Return reminder dict when (current_week_num + 1) % 6 == 0 (weeks 5, 11, 17...).

    Checks state for postpone/skip overrides.
    """
    # Check skip
    skip_until = user_state.get("test_reminder_skipped_until")
    if skip_until is not None and current_week_num < int(skip_until):
        return None

    # Check postpone
    postponed_to = user_state.get("test_reminder_postponed_to")
    if postponed_to is not None:
        if current_week_num < int(postponed_to):
            return None
        # If we've reached the postponed week, show it
        if current_week_num == int(postponed_to):
            return {
                "type": "test_week_reminder",
                "message": "Time to refresh your test baselines! A test week helps keep your plan accurate.",
                "options": ["confirm", "postpone_1_week", "skip_cycle"],
            }

    # Regular trigger: weeks 5, 11, 17, 23...
    if (current_week_num + 1) % 6 == 0:
        return {
            "type": "test_week_reminder",
            "message": "Time to refresh your test baselines! A test week helps keep your plan accurate.",
            "options": ["confirm", "postpone_1_week", "skip_cycle"],
        }

    return None
