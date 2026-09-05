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

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

from backend.engine.equipment_utils import BOULDER_SURFACES, expand_equipment
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
    "strength_long": {"pulling": True, "hard": True, "finger": True, "intensity": "max", "climbing": True, "location": ("gym", "home"), "required_equipment": ["hangboard"]},
    "power_contact_gym": {"hard": True, "finger": True, "intensity": "max", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"]},
    "limit_boulder_gym": {"pulling": True, "hard": True, "finger": True, "intensity": "max", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"]},
    "power_endurance_gym": {"pulling": True, "hard": True, "finger": False, "intensity": "high", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"], "preferred_equipment": ["gym_routes"]},
    "endurance_aerobic_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "max_per_week": 2, "required_equipment": ["gym_routes"]},
    "technique_focus_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"]},
    "finger_strength_home": {"pulling": True, "hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home",), "required_equipment": ["hangboard"]},
    "prehab_maintenance": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym")},
    "flexibility_full": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym"), "max_per_week": 2},
    "yoga_recovery": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home",), "max_per_week": 2},
    "handstand_practice": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym")},
    "complementary_conditioning": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym")},
    "regeneration_easy": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym", "outdoor"), "required_equipment": ["gym_boulder"]},
    "finger_maintenance_home": {"pulling": True, "hard": False, "finger": True, "intensity": "medium", "climbing": True, "location": ("home",), "required_equipment": ["hangboard"]},
    "test_max_hang_5s": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["hangboard"]},
    "test_max_hang_7s": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["hangboard"]},
    "test_lp_max_5s": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["loading_pin"]},
    "test_repeater_7_3": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["hangboard"]},
    "test_lp_repeater": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["loading_pin"]},
    "test_max_weighted_pullup": {"hard": True, "finger": False, "intensity": "high", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["pullup_bar"]},
    "test_pullup_bw": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym"), "test": True, "required_equipment": ["pullup_bar"]},
    "easy_climbing_deload": {"hard": False, "finger": False, "intensity": "low", "climbing": True, "location": ("gym",), "required_equipment": ["gym_boulder"]},
    "finger_maintenance_gym": {"hard": False, "finger": True, "intensity": "medium", "climbing": True, "location": ("gym",), "required_equipment": ["hangboard"]},
    "route_endurance_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "required_equipment": ["gym_routes"]},
    "pulling_strength_gym": {"pulling": True, "hard": True, "finger": False, "intensity": "high", "climbing": False, "location": ("gym",), "required_equipment": ["pullup_bar"]},
    "heavy_conditioning_gym": {"pulling": True, "hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym",), "required_equipment": ["dumbbell"]},
    "lower_body_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym",), "required_equipment": ["dumbbell"]},
    "finger_aerobic_base": {"hard": False, "finger": True, "intensity": "low", "climbing": False, "location": ("home",), "required_equipment": ["hangboard"]},
    "deload_recovery": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym"), "max_per_week": 2},
    "finger_endurance_short": {"hard": False, "finger": True, "intensity": "medium", "climbing": False, "location": ("home",), "required_equipment": ["hangboard"]},
    "boulder_circuit_gym": {"pulling": True, "hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",), "max_per_week": 2, "required_equipment": ["gym_boulder"]},
    "route_projecting_gym": {"hard": True, "finger": True, "intensity": "max", "climbing": True, "location": ("gym",), "required_equipment": ["gym_routes"], "max_per_week": 2},
    "upper_body_weights": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym", "home"), "required_equipment": [], "max_per_week": 2},
    "legs_strength": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym", "home"), "required_equipment": [], "max_per_week": 2},
    "core_training": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("gym", "home"), "required_equipment": [], "max_per_week": 3},
}


# B191/D92: phase-aware test gating — only schedule tests for axes the current phase stimulates.
# Avoids scientifically indefensible retests (e.g. max finger strength test after a Base/ARC phase).
# Safety cap: axes untested for 12+ weeks get a maintenance retest regardless of phase.
_PHASE_TEST_MAP: Dict[str, Dict[str, bool]] = {
    "base": {
        "finger": False,    # Base phase targets endurance, not max finger strength
        "repeater": True,   # ARC/volume stimulus → endurance retest appropriate
        "pulling": False,   # No pulling strength stimulus in Base
    },
    "strength_power": {
        "finger": True,
        "repeater": True,
        "pulling": True,
    },
    "power_endurance": {
        "finger": False,    # PE phase targets lactate tolerance, not max force
        "repeater": True,   # PE stimulus → endurance retest appropriate
        "pulling": False,
    },
    "performance": {
        "finger": False,
        "repeater": False,
        "pulling": False,
    },
    "deload": {
        "finger": False,
        "repeater": False,
        "pulling": False,
    },
}
MAX_WEEKS_UNTESTED = 12  # Force maintenance retest if axis untested for 12+ weeks

# B346: test_queue entry `test_id` → the session that actually runs that test.
# `progression_v1._enqueue_test` writes a TEST id after two concordant feedbacks
# on a max hang ("the load stopped making sense — go remeasure"); PASS 3 places
# SESSIONS. Before B346 the only consumer of that queue was `planner_v1`, which
# no module imports: the engine's one self-correction mechanism wrote into a
# channel with no outlet.
_TEST_QUEUE_SESSION: Dict[str, str] = {
    "max_hang_5s_total_load": "test_max_hang_5s",
    "max_hang_7s_total_load": "test_max_hang_7s",
    "lp_max_test_5s": "test_lp_max_5s",
}


def _validate_session_meta_equipment() -> None:
    """D172-17: warn if _SESSION_META.required_equipment differs from session JSON files.

    A245 E-6 (B19): this used to be CALLED at module import, opening ~35 JSON
    files every time anything imported planner_v2 — including every worker boot
    and every test collection — with `except Exception: pass` swallowing any
    problem. Import-time I/O in a hot module is both a startup cost and a
    silent failure mode: a real mismatch produced a log line nobody reads.

    The call now lives in `test_a245_catalog_meta_consistency.py`, where drift
    fails the suite instead. The function body is unchanged.
    """
    import os as _os
    import json as _json
    sessions_dir = _os.path.join(_os.path.dirname(__file__), "..", "catalog", "sessions", "v1")
    for sid, meta in _SESSION_META.items():
        path = _os.path.join(sessions_dir, f"{sid}.json")
        if not _os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as _f:
                data = _json.load(_f)
            json_eq = set(data.get("required_equipment") or [])
            meta_eq = set(meta.get("required_equipment") or [])
            if json_eq != meta_eq:
                logger.warning(
                    "_SESSION_META/%s required_equipment mismatch: meta=%r json=%r",
                    sid, sorted(meta_eq), sorted(json_eq),
                )
        except Exception:
            pass


# A245 E-6 (B19): the import-time call that used to sit here was removed —
# see the docstring above. Catalog drift is checked by the test suite.

_INTENSITY_ORDER = {"low": 0, "medium": 1, "high": 2, "max": 3}

# Fallback load score for unresolved sessions (real score uses fatigue_cost from exercises)
_INTENSITY_TO_LOAD: Dict[str, int] = {"low": 20, "medium": 40, "high": 65, "max": 85}

# Fallback climbing sessions tried (in order) when Pass 1 couldn't place any climbing
# on a gym-available day due to equipment constraints (Bug B fix).
# All require only gym_boulder — the most common gym equipment.
_CLIMBING_FALLBACKS: Tuple[str, ...] = ("technique_focus_gym", "easy_climbing_deload")


# B208: a session is expanded to "home" only when it requires a wall surface
# AND the user has a wall-equivalent at home. This preserves the B137/B159
# homewall/board case without re-routing hangboard- or weights-only gym
# sessions to home (which produced the Daniele 2026-04-17 bug).
_WALL_SURFACES_REQUIRING_HOME_EXPANSION: frozenset[str] = BOULDER_SURFACES | {"gym_routes"}


def _expand_session_locations(
    session_locations: Tuple[str, ...],
    required_equipment: Optional[List[str]],
    home_equipment: Optional[List[str]],
) -> Tuple[str, ...]:
    """Expand session locations when home equipment satisfies gym requirements.

    B137: homewall → gym_boulder.  B159: generalised via expand_equipment.
    B208: scoped to wall-surface requirements only — sessions requiring just
    hangboard/pullup_bar/dumbbell are NOT re-routed to home (the planner must
    respect the catalog's explicit gym intent for non-wall sessions).
    """
    if "home" in session_locations:
        return session_locations  # already home-compatible
    if not home_equipment or not required_equipment:
        return session_locations
    if not set(required_equipment) & _WALL_SURFACES_REQUIRING_HOME_EXPANSION:
        return session_locations  # B208: non-wall sessions stay at declared locations
    home_eq = set(expand_equipment(home_equipment))
    if all(eq in home_eq for eq in required_equipment):
        return tuple(session_locations) + ("home",)
    return session_locations


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
        # B159: expand boulder surfaces + weight subtypes
        return expand_equipment(equip)
    elif location == "home":
        if home_equipment is None:
            return None  # no home info → assume everything available
        equip = list(home_equipment)
        # B159: expand boulder surfaces + weight subtypes (supersedes B137)
        return expand_equipment(equip)
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
            expanded = expand_equipment(equip)
            if all(eq in expanded for eq in required_equipment):
                return True
        return False
    avail = _equipment_for_location(location, slot_info, home_equipment, gyms, default_gym_id)
    if avail is None:
        return True  # unknown equipment → assume available (backwards compat)
    return all(eq in avail for eq in required_equipment)


def allowed_locations_for(equipment: Optional[Dict[str, Any]]) -> List[str]:
    """Derive the allowed planning locations from the user's equipment block.

    B322: ``equipment.home_enabled`` was written by the wizard and then read by
    nobody — the planner only ever looked at ``equipment.home``. A user who
    explicitly said "I don't train at home" still got home sessions placed on
    their week. Honour the flag, but only when there is somewhere else to train:
    dropping "home" for a user with no gym would leave the planner with no
    location at all, which is strictly worse than ignoring the preference.
    """
    equipment = equipment or {}
    gyms = equipment.get("gyms") or []
    if equipment.get("home_enabled") is False and gyms:
        return ["gym"]
    return ["home", "gym"]


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
        # B322: the preferred location cannot host this session. Dropping it is
        # correct when the preference is a real choice — "Tuesday I train at
        # home" must never silently become a gym session (UI batch 1b).
        #
        # But "home" is not a choice when the user has no home setup: the wizard
        # defaults every slot to home, so someone who ticked "Yes" without
        # opening the location control had their whole climbing week deleted. In
        # prod a boulderer with a fully equipped gym, `home_enabled=false` and an
        # empty home kit got nothing but stretching and prehab.
        #
        # So fall back only when home is demonstrably not a place this user can
        # train: an explicitly EMPTY home kit, or home excluded from the allowed
        # locations (home_enabled=false, see allowed_locations_for). A home kit
        # of None means "unknown" — treated as available everywhere else in this
        # module — and keeps the preference binding.
        home_is_dead_end = not home_equipment and home_equipment is not None
        if preferred == "home" and (home_is_dead_end or "home" not in allowed_locations):
            for loc in viable:
                if not required_equipment or _location_has_equipment(
                    loc, required_equipment, slot_info, home_equipment, gyms, default_gym_id
                ):
                    return loc
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
    raw = availability or {}
    locs = sorted(set(allowed_locations))

    # Warn about unknown weekday keys
    _VALID_WEEKDAYS = set(WEEKDAYS)
    for wd_key in raw:
        if wd_key not in _VALID_WEEKDAYS:
            logger.warning(
                "_normalize_availability: unknown availability key %r — treating as rest day",
                wd_key,
            )

    def _unavailable() -> Dict[str, Any]:
        return {"available": False, "locations": locs,
                "preferred_location": None, "gym_id": None}

    for wd in WEEKDAYS:
        # Case 1: Key absent → rest day (all slots unavailable)
        if wd not in raw:
            normalized[wd] = {s: _unavailable() for s in SLOTS}
            continue

        day = raw[wd]

        # Cases 9-12 (D150): Non-dict values — defensive handling
        if not isinstance(day, dict):
            # Bare True → available with home fallback (explicit intent)
            if day is True:
                normalized[wd] = {
                    s: {"available": True, "locations": ["home"],
                        "preferred_location": "home", "gym_id": None}
                    for s in SLOTS
                }
            else:
                # None, False, 0, "", [], "string" → rest
                normalized[wd] = {s: _unavailable() for s in SLOTS}
            continue

        # Case 4: Explicit {"available": False} → rest
        if day.get("available") is False:
            normalized[wd] = {s: _unavailable() for s in SLOTS}
            continue

        has_explicit_slots = any(s in day for s in SLOTS)

        # Cases 2,3,8,13 (D150): Dict with no slot keys and no explicit
        # available=True → rest.  Catches empty dicts {}, None-coerced {},
        # and legacy _day_meta-only entries.
        if not has_explicit_slots and day.get("available") is not True:
            normalized[wd] = {s: _unavailable() for s in SLOTS}
            continue

        # Case 5: {"available": True} without slot keys → available, all
        # allowed locations, no preference (user said "available" but gave
        # no slot/location detail).
        if not has_explicit_slots and day.get("available") is True:
            normalized[wd] = {
                s: {"available": True, "locations": locs,
                    "preferred_location": None, "gym_id": None}
                for s in SLOTS
            }
            continue

        # Cases 6,7: Has explicit slot keys → process per-slot
        day_slots: Dict[str, Dict[str, Any]] = {}
        for slot in SLOTS:
            default: Dict[str, Any] = {"available": True, "locations": locs,
                        "preferred_location": None, "gym_id": None}
            slot_value = day.get(slot)
            if slot_value is None:
                # has_explicit_slots is True here: unmentioned slots → unavailable
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
    preferred_equipment: Optional[List[str]] = None,
) -> Optional[str]:
    """Return the gym_id to assign to a session.

    Selection order:
      1. slot_info.gym_id if explicitly set
      2. default_gym_id if set
      3. B201: first gym by priority satisfying BOTH required AND preferred
         equipment (soft bonus — applies only when the user has multiple gyms
         and one of them has the preferred equipment)
      4. first gym by priority satisfying required_equipment (Bug A fix)
      5. fallback: first gym by priority

    ``preferred_equipment`` is a SOFT preference. If no gym has it, this
    step is skipped silently and step 4 handles placement — sessions are
    never dropped due to a missing preferred equipment.
    """
    slot_gym = slot_info.get("gym_id")
    if slot_gym:
        return slot_gym
    if default_gym_id:
        return default_gym_id
    if gyms:
        sorted_gyms = sorted(gyms, key=lambda g: (g.get("priority", 999), g.get("gym_id", "")))

        def _satisfies(gym: Dict[str, Any], eq_list: List[str]) -> bool:
            equip = list(gym.get("equipment", []))
            if "pullup_bar" not in equip:
                equip.append("pullup_bar")
            return all(eq in equip for eq in eq_list)

        # B201: soft bonus for gyms that also satisfy preferred_equipment.
        # Example: PE session (required=gym_boulder, preferred=gym_routes) →
        # prefer a route-gym over a boulder-only gym when both are available.
        if required_equipment and preferred_equipment:
            for g in sorted_gyms:
                if _satisfies(g, required_equipment) and _satisfies(g, preferred_equipment):
                    return g.get("gym_id")

        if required_equipment:
            for g in sorted_gyms:
                if _satisfies(g, required_equipment):
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
    occupied_slots: Optional[set] = None,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Find the best available slot for a session on a given day.

    Primary sessions prefer evening > morning > lunch.
    Complementary sessions prefer lunch > morning > evening.

    Args:
        occupied_slots: Set of slot names already taken on this day (skipped).
    """
    if prefer_evening:
        slot_order = ("evening", "morning", "lunch")
    else:
        slot_order = ("lunch", "morning", "evening")

    _occupied = occupied_slots or set()
    req_equip = meta.get("required_equipment")
    # B137: expand locations when homewall satisfies gym_boulder requirement
    effective_locations = _expand_session_locations(meta["location"], req_equip, home_equipment)
    for slot in slot_order:
        if slot in _occupied:
            continue
        slot_info = day_availability[slot]
        if not slot_info["available"]:
            continue
        location = _pick_location(
            effective_locations, slot_info, locations,
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
    # B137: expand locations when homewall satisfies gym_boulder requirement
    effective_locations = _expand_session_locations(meta["location"], req_equip, home_equipment)
    location = _pick_location(
        effective_locations, slot_info, locations,
        required_equipment=req_equip,
        home_equipment=home_equipment,
        gyms=gyms,
        default_gym_id=default_gym_id,
    )
    gym_id = None
    if location == "gym":
        gym_id = _select_gym_id(
            slot_info, default_gym_id, gyms,
            required_equipment=req_equip,
            preferred_equipment=meta.get("preferred_equipment"),
        )

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


def _pick_pulling_test_session(
    pulling_baseline: Optional[Dict[str, Any]],
    max_pullups_bw: Optional[int],
) -> str:
    """B128: Choose pulling test session based on user state.

    - Has pulling baseline (from onboarding) → weighted 2RM directly
    - No baseline, no BW result → BW-only test
    - No baseline, BW >= 15 → weighted 2RM
    - No baseline, BW < 15 → BW-only re-test
    """
    if pulling_baseline:
        return "test_max_weighted_pullup"
    if max_pullups_bw is not None and max_pullups_bw >= 15:
        return "test_max_weighted_pullup"
    return "test_pullup_bw"


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
    inject_tests: bool = False,
    finger_device: Optional[str] = None,
    user_age: Optional[int] = None,
    pulling_baseline: Optional[Dict[str, Any]] = None,
    max_pullups_bw: Optional[int] = None,
    recent_test_dates: Optional[Dict[str, str]] = None,
    prev_week_plan: Optional[Dict[str, Any]] = None,
    test_queue: Optional[List[Dict[str, Any]]] = None,
    taper_volume: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Generate a single week plan within a macrocycle phase.

    Uses a multi-pass algorithm:
      PASS 1:   Place primary sessions (hard + climbing-related) with spacing constraints.
      PASS 1.5: Climbing fallback for gym days left empty by Pass 1.
      PASS 2:   Fill remaining days with complementary sessions.
      PASS 2.2: Fill extra slots on multi-slot days (B121).
      PASS 2.5: Ensure PE phase has at least 1 finger maintenance session.
      PASS 3:   (optional) Inject test sessions when inject_tests=True.

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
        pretrip_dates: YYYY-MM-DD dates on which no hard/max session may be
            placed. A281 narrowed this from 6 days to 3 (see
            ``macrocycle_v1.TAPER_NO_HARD_DAYS``) and made it enforced after
            every pass instead of only PASS 1.
        taper_volume: YYYY-MM-DD → set multiplier (<1.0) for the two weeks
            before a trip. Stamped onto the day as ``taper_volume_multiplier``
            and applied to the resolved prescription, never to the session
            selection: intensity and training days stay untouched.
            Hard/max sessions are blocked on these dates.

    Returns:
        Week plan dict compatible with planner.v1 format.
    """
    # --- Input validation ---
    if phase_id not in PHASE_ORDER:
        raise ValueError(f"generate_phase_week: invalid phase_id '{phase_id}', must be one of {PHASE_ORDER}")
    try:
        _sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        if _sd.weekday() != 0:
            # Auto-fix to previous Monday (same pattern as generate_macrocycle)
            _sd -= timedelta(days=_sd.weekday())
            start_date = _sd.isoformat()
            logger.warning("generate_phase_week: start_date adjusted to Monday %s", start_date)
            # D172-24: start_date is corrected here; all subsequent uses of start_date
            # in this function use the corrected Monday value.
    except (ValueError, TypeError) as exc:
        raise ValueError(f"generate_phase_week: invalid start_date format '{start_date}', expected YYYY-MM-DD") from exc

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

    # D81: youth training cap — max 4 days/week for users under 18
    if user_age is not None and user_age < 18:
        target_days = min(target_days, 4)

    # D83: recovery multiplier increases minimum gap between hard sessions
    recovery_mult = float(prefs.get("recovery_multiplier", 1.0))
    hard_gap_days = math.ceil(1 * recovery_mult)  # base gap = 1 day (48h)
    finger_gap_days = math.ceil(1 * recovery_mult)

    # B95: resolve "today" for skipping past days
    today_date: Optional[date] = _parse_date(today) if today else None

    # Build day structures
    day_dates: List[date] = [start + timedelta(days=i) for i in range(7)]
    day_keys: List[str] = [_weekday_key(d) for d in day_dates]
    day_sessions: List[List[Dict[str, Any]]] = [[] for _ in range(7)]

    # Extract other-activity flags from availability.
    # Sources: legacy _day_meta OR per-slot preferred_location="other_sport".
    # B276: multiple other activities per day (one per slot). day_other_activity
    # stays as a per-day bool for the intensity-reduction logic below; the full
    # list is emitted into the plan as `other_activities`.
    day_other_activity: List[bool] = [False] * 7
    day_reduce_after: List[bool] = [False] * 7
    day_other_activities: List[List[Dict[str, Any]]] = [[] for _ in range(7)]
    for offset in range(7):
        raw_day = (availability or {}).get(day_keys[offset]) or {}
        if not isinstance(raw_day, dict):
            continue

        def _append_activity(slot_key: Optional[str], name: Optional[str]) -> None:
            # One item per slot — skip if this slot already recorded.
            if slot_key and any(
                it.get("slot") == slot_key for it in day_other_activities[offset]
            ):
                return
            item: Dict[str, Any] = {}
            if slot_key:
                item["slot"] = slot_key
            if name:
                item["name"] = name
            day_other_activities[offset].append(item)
            day_other_activity[offset] = True

        # Legacy _day_meta approach
        meta = raw_day.get("_day_meta")
        if isinstance(meta, dict) and meta.get("other_activity"):
            _append_activity(meta.get("other_activity_slot"), meta.get("other_activity_name"))
            day_reduce_after[offset] = bool(meta.get("reduce_intensity_after"))
        # Per-slot approach: preferred_location="other_sport"
        for s_key in SLOTS:
            slot_val = raw_day.get(s_key)
            if isinstance(slot_val, dict) and slot_val.get("preferred_location") == "other_sport":
                _append_activity(s_key, slot_val.get("other_activity_name"))
                day_reduce_after[offset] = day_reduce_after[offset] or bool(slot_val.get("reduce_intensity_after"))

    # Track constraints
    hard_days = 0
    finger_day_offsets: List[int] = []
    hard_day_offsets: List[int] = []
    session_count: Dict[str, int] = {}  # anti-repetition: session_id → times placed this week

    # B161: seed spacing constraints from previous week's trailing days.
    # Offsets are negative (e.g., Sunday of prev week = -1, Saturday = -2).
    if prev_week_plan:
        prev_days = (prev_week_plan.get("weeks") or [{}])[0].get("days", [])
        for i, pd in enumerate(prev_days):
            neg_offset = i - 7  # Mon=-7 … Sun=-1
            for s in pd.get("sessions", []):
                sid = s.get("session_id", "")
                meta = _SESSION_META.get(sid)
                if meta is None:
                    continue
                if meta.get("hard") and s.get("tags", {}).get("hard", meta["hard"]):
                    hard_day_offsets.append(neg_offset)
                if meta.get("finger") and s.get("tags", {}).get("finger", meta["finger"]):
                    finger_day_offsets.append(neg_offset)

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

    # Count total available slots across all available days (for multi-slot-per-day support)
    day_available_slots: List[List[str]] = [[] for _ in range(7)]
    for offset in range(7):
        if not day_has_available_slot[offset]:
            continue
        day_avail = normalized[day_keys[offset]]
        for s in SLOTS:
            if day_avail[s]["available"]:
                day_available_slots[offset].append(s)
    total_available_slots = sum(len(sl) for sl in day_available_slots)

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
            permanent_skip = False  # B157: only permanent skips burn the uses budget

            # Anti-repetition: max N times per week (default 1) — PERMANENT
            max_pw = meta.get("max_per_week", 1)
            if session_count.get(sid, 0) >= max_pw:
                skip = True
                permanent_skip = True

            # Other-activity intensity reduction: no hard sessions on reduced day — TEMPORARY
            if not skip and day_intensity_reduced[offset] and meta["hard"]:
                skip = True

            # Pre-trip deload: no hard/max sessions on pretrip dates — TEMPORARY
            if not skip and day_dates[offset] in pretrip_set and (meta["hard"] or meta["intensity"] == "max"):
                skip = True

            # Hard day cap — PERMANENT
            if not skip and meta["hard"] and hard_days >= effective_hard_cap:
                skip = True
                permanent_skip = True

            # No consecutive finger days (48h+ gap, extended by D83 recovery multiplier) — TEMPORARY
            if not skip and meta["finger"] and finger_day_offsets:
                last_finger_offset = finger_day_offsets[-1]
                if (offset - last_finger_offset) <= finger_gap_days:
                    skip = True

            # No consecutive hard/max-intensity days (extended by D83 recovery multiplier) — TEMPORARY
            if not skip and meta["hard"] and hard_day_offsets:
                last_hard_offset = hard_day_offsets[-1]
                if (offset - last_hard_offset) <= hard_gap_days:
                    skip = True

            if skip:
                primary_idx += 1
                if permanent_skip:
                    primary_uses += 1
                attempts += 1
                continue

            day_avail = normalized[day_keys[offset]]

            # B160d: if session has preferred_equipment and this day's gym lacks
            # it, defer to a later day that might have it (don't burn uses).
            pref_equip = meta.get("preferred_equipment")
            if pref_equip and session_count.get(sid, 0) == 0:
                day_equip = _equipment_for_location(
                    "gym", day_avail.get("evening") or day_avail.get("morning") or day_avail.get("lunch") or {},
                    home_equipment, gyms, default_gym_id,
                )
                if day_equip is not None and not any(pe in day_equip for pe in pref_equip):
                    # Check if any LATER unprocessed day has the preferred equipment
                    remaining = [o for o in pass1_day_order if o > offset and day_has_available_slot[o] and o not in {off for off, _ in enumerate(day_sessions) if day_sessions[off]}]
                    has_better_day = False
                    for ro in remaining:
                        r_avail = normalized[day_keys[ro]]
                        for rs in SLOTS:
                            if r_avail[rs]["available"]:
                                r_equip = _equipment_for_location("gym", r_avail[rs], home_equipment, gyms, default_gym_id)
                                if r_equip and any(pe in r_equip for pe in pref_equip):
                                    has_better_day = True
                                    break
                        if has_better_day:
                            break
                    if has_better_day:
                        primary_idx += 1
                        attempts += 1
                        continue  # defer to day with preferred equipment

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
                if fb_meta.get("finger") and finger_day_offsets and (offset - finger_day_offsets[-1]) <= finger_gap_days:
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

            # Anti-repetition check — PERMANENT skip (burns uses)
            max_pw = meta.get("max_per_week", 1)
            if session_count.get(sid, 0) >= max_pw:
                comp_idx += 1
                comp_uses += 1  # permanent: session exhausted for the week
                attempts += 1
                continue

            day_avail = normalized[day_keys[offset]]
            result = _find_best_slot(day_avail, meta, locations, prefer_evening=False,
                                     home_equipment=home_equipment, gyms=gyms, default_gym_id=default_gym_id)
            if result is None:
                comp_idx += 1
                attempts += 1
                continue  # location mismatch — don't burn uses

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

    # ── PASS 2.2 (B121): Fill extra slots on multi-slot days ──
    # When total sessions placed < target AND a day has unused slots, place
    # additional NON-hard sessions to fill them.
    total_sessions_placed = sum(len(ds) for ds in day_sessions)
    session_target = min(target_days, total_available_slots)

    if total_sessions_placed < session_target:
        # Build combined pool: primary non-hard + all complementary
        extra_pool = [s for s in filtered_pool if not _SESSION_META[s]["hard"]]
        if not extra_pool:
            extra_pool = list(complementary_pool)

        extra_idx = 0
        extra_uses = 0
        max_extra_uses = len(extra_pool) * 2 if extra_pool else 0

        for offset in range(7):
            if total_sessions_placed >= session_target:
                break
            if not day_has_available_slot[offset]:
                continue
            # Only consider days that already have sessions (extra slot filling)
            if not day_sessions[offset]:
                continue
            if not extra_pool:
                break
            if extra_uses >= max_extra_uses:
                break

            # Determine which slots are already occupied on this day
            occupied = {entry["slot"] for entry in day_sessions[offset]}
            # Check if the day has any free slots left
            free_slots = [s for s in day_available_slots[offset] if s not in occupied]
            if not free_slots:
                continue

            attempts = 0
            while attempts < len(extra_pool) and extra_uses < max_extra_uses:
                sid = extra_pool[extra_idx % len(extra_pool)]
                meta = _SESSION_META[sid]

                skip = False

                # No hard sessions in extra slots (B121 constraint)
                if meta["hard"]:
                    skip = True

                # Anti-repetition check
                if not skip:
                    max_pw = meta.get("max_per_week", 1)
                    if session_count.get(sid, 0) >= max_pw:
                        skip = True

                # No consecutive finger days (gap extended by D83 recovery multiplier)
                if not skip and meta["finger"] and finger_day_offsets:
                    if any(abs(offset - fo) <= finger_gap_days for fo in finger_day_offsets):
                        skip = True

                if skip:
                    extra_idx += 1
                    extra_uses += 1
                    attempts += 1
                    continue

                day_avail = normalized[day_keys[offset]]
                result = _find_best_slot(
                    day_avail, meta, locations, prefer_evening=False,
                    home_equipment=home_equipment, gyms=gyms,
                    default_gym_id=default_gym_id, occupied_slots=occupied,
                )
                if result is None:
                    extra_idx += 1
                    attempts += 1
                    continue

                slot, slot_info = result
                entry = _make_session_entry(
                    slot, sid, meta, slot_info, locations, phase_id,
                    day_keys[offset], default_gym_id, gyms or [],
                    "pass2.2:extra_slot", home_equipment=home_equipment,
                )
                day_sessions[offset].append(entry)
                occupied.add(slot)
                session_count[sid] = session_count.get(sid, 0) + 1
                extra_idx += 1
                extra_uses += 1
                total_sessions_placed += 1
                if meta["finger"]:
                    finger_day_offsets.append(offset)
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
                # Respect finger gap (extended by D83 recovery multiplier)
                if finger_day_offsets and any(abs(offset - fo) <= finger_gap_days for fo in finger_day_offsets):
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

    # ── PASS 2.6 (B308): guarantee a weekly pulling stimulus ──
    #
    # Why: a domain weight does not guarantee a dose — it makes a session more
    # likely to be picked, which is not the same thing. Measured on a real plan
    # (D263), pulling strength went untrained for 8 of 12 weeks: past the ~4-week
    # detraining window for maximal strength (Mujika & Padilla 2000), and in
    # contradiction with the DUP model the project documents ("phase weights
    # shift gradually, not binary on/off for any quality").
    #
    # Maintenance needs guaranteed FREQUENCY, so this pass forces one session
    # that trains pulling when the week has none. Same shape as PASS 2.5 above:
    # empty day first, otherwise replace a COMPLEMENTARY session (never a
    # primary one), and never at the cost of a safety constraint — if the only
    # way to place it would breach the hard-day cap or the finger gap, we do not
    # place it and say so (B308: silence is what let D263 hide for months).
    #
    # Deload is exempt by design (KB: zero pulling in a deload week is correct).
    unmet_stimulus: list = []
    if phase_id != "deload":
        _has_pulling = any(
            _SESSION_META.get(s.get("session_id", ""), {}).get("pulling")
            for day_list in day_sessions for s in day_list
        )
        if not _has_pulling:
            _pull_candidates = [
                (sid, _SESSION_META.get(sid))
                for sid in filtered_pool
                if _SESSION_META.get(sid, {}).get("pulling")
                and not _SESSION_META.get(sid, {}).get("test")
            ]
            _placed = False
            for offset in range(7):
                if _placed or not _pull_candidates:
                    break
                if not day_has_available_slot[offset] or day_is_outdoor[offset]:
                    continue
                day_avail = normalized[day_keys[offset]]
                for _sid, _meta in _pull_candidates:
                    if _meta is None:
                        continue
                    # Never breach the hard-day cap to satisfy a maintenance dose.
                    if _meta.get("hard") and hard_days >= effective_hard_cap:
                        continue
                    if _meta.get("hard") and any(
                        abs(offset - ho) <= hard_gap_days for ho in hard_day_offsets
                    ):
                        continue
                    if _meta.get("finger") and any(
                        abs(offset - fo) <= finger_gap_days for fo in finger_day_offsets
                    ):
                        continue
                    result = _find_best_slot(
                        day_avail, _meta, locations, prefer_evening=False,
                        home_equipment=home_equipment, gyms=gyms, default_gym_id=default_gym_id,
                    )
                    if not result:
                        continue
                    slot, slot_info = result
                    entry = _make_session_entry(
                        slot, _sid, _meta, slot_info, locations, phase_id, day_keys[offset],
                        default_gym_id, gyms or [], "pass2.6:pulling_maintenance",
                        home_equipment=home_equipment,
                    )
                    if day_sessions[offset]:
                        # Replace a complementary session, never a primary one.
                        _victim = next(
                            (i for i, e in enumerate(day_sessions[offset])
                             if not _is_primary_session(_SESSION_META.get(e.get("session_id", ""), {}))),
                            None,
                        )
                        if _victim is None:
                            continue
                        day_sessions[offset][_victim] = entry
                    else:
                        day_sessions[offset].append(entry)
                        days_with_sessions += 1
                    if _meta.get("hard"):
                        hard_days += 1
                        hard_day_offsets.append(offset)
                    if _meta.get("finger"):
                        finger_day_offsets.append(offset)
                    _placed = True
                    break
            if not _placed:
                # B346: kept, and made audible. D280 listed `unmet_stimulus`
                # among the "written and never read" fields and the first plan
                # was to delete it — but B308 added it *because* "silence is
                # what let D263 hide for months". Deleting a diagnostic on the
                # grounds that nobody displays it is backwards; the answer is to
                # stop it being silent. Surfacing it in the UI is a separate,
                # frontend brief (UNMET-STIMULUS-VISIBILITY).
                logger.warning(
                    "unmet stimulus: pulling could not be placed in week %s (phase %s) "
                    "without breaching the hard-day cap, the recovery gaps or the slots",
                    start_date,
                    phase_id,
                )
                unmet_stimulus.append({
                    "stimulus": "pulling",
                    "phase_id": phase_id,
                    "reason": (
                        "no session training pulling could be placed without breaching "
                        "the hard-day cap, the recovery gaps or the available slots"
                    ),
                })

    # ── PASS 3 (optional): Inject test sessions ──
    # Triggers on: last week of base/strength_power, OR explicitly via inject_tests
    skipped_tests: list = []  # B191: populated by phase-gating logic below

    # B346: a queued retest is a third reason to run PASS 3, next to the
    # explicit assessment and the end of a base/strength_power phase. Only
    # entries already due (recommended_by_date within this week) count.
    _queued_test_sids: List[str] = []
    _week_end_iso = (_parse_date(start_date) + timedelta(days=6)).isoformat()
    for _item in test_queue or []:
        _sid = _TEST_QUEUE_SESSION.get(str(_item.get("test_id") or ""))
        _rec_by = _item.get("recommended_by_date")
        if not _sid or not isinstance(_rec_by, str):
            continue
        if _rec_by <= _week_end_iso and _sid not in _queued_test_sids:
            _queued_test_sids.append(_sid)

    _run_pass3 = (
        inject_tests
        or (is_last_week_of_phase and phase_id in ("base", "strength_power"))
        or bool(_queued_test_sids)
    )
    if _run_pass3:
        # B128/B138: freshness check — skip tests completed within TEST_FRESHNESS_DAYS
        # 42 days = 6 weeks minimum between retests (Hörst, Lattice, Eva López)
        TEST_FRESHNESS_DAYS = 42
        _test_type_map = {
            "test_max_hang_5s": "finger", "test_max_hang_7s": "finger", "test_lp_max_5s": "finger",
            "test_repeater_7_3": "repeater", "test_lp_repeater": "repeater",
            "test_max_weighted_pullup": "pulling", "test_pullup_bw": "pulling",
        }
        _recent = recent_test_dates or {}
        _week_start = _parse_date(start_date)

        # Required tests first, then optional
        # Finger test depends on device preference (A120)
        _finger_test_sid = "test_lp_max_5s" if finger_device == "loading_pin" else "test_max_hang_7s"
        _repeater_test_sid = "test_lp_repeater" if finger_device == "loading_pin" else "test_repeater_7_3"
        # Pulling test routing — skip BW gate for users with pulling baseline
        _pulling_test_sid = _pick_pulling_test_session(pulling_baseline, max_pullups_bw)
        _test_schedule = [
            (_finger_test_sid, True),
            (_repeater_test_sid, True),
            (_pulling_test_sid, False),
        ]
        # B346: in practice _enqueue_test only ever queues the same finger test
        # the device preference already selects, so this is belt-and-braces —
        # but a queued test that is not on the standard schedule must still be
        # placeable, otherwise the queue would silently drop it.
        _scheduled_sids = {sid for sid, _ in _test_schedule}
        for _sid in _queued_test_sids:
            if _sid not in _scheduled_sids:
                _test_schedule.append((_sid, True))

        # B191/D92+B128: phase-aware gating then freshness check
        # inject_tests=True means explicit baseline assessment (initial or manual) — bypass phase gate
        _phase_map = _PHASE_TEST_MAP.get(phase_id, {}) if not inject_tests else {}
        _filtered_schedule = []
        skipped_tests: list = []
        for test_sid, _required in _test_schedule:
            test_type = _test_type_map.get(test_sid)

            # 1. Phase-aware gate (D92): skip axes not stimulated by this phase,
            #    unless inject_tests=True (explicit assessment) or axis untested 12+ weeks.
            # B346: a queued retest bypasses the PHASE gate — it exists precisely
            # because two concordant feedbacks said the recorded max no longer
            # matches reality, and the phase the athlete happens to be in does
            # not change that. It does NOT bypass the 42-day freshness gate
            # below: that is what stops a queue entry from re-placing the same
            # test every week once it has been done.
            phase_allows = (
                True if test_sid in _queued_test_sids
                else (_phase_map.get(test_type, True) if test_type else True)
            )
            if not phase_allows:
                last_date_str = _recent.get(test_type) if test_type else None
                weeks_since: float | None = None
                if last_date_str:
                    try:
                        weeks_since = (_week_start - _parse_date(last_date_str)).days / 7
                    except (ValueError, TypeError):
                        pass
                if weeks_since is None or weeks_since < MAX_WEEKS_UNTESTED:
                    skipped_tests.append({
                        "test_id": test_sid,
                        "axis": test_type,
                        "reason": f"Phase '{phase_id}' does not target {test_type} axis (D92/B191)",
                        "weeks_since_last": round(weeks_since, 1) if weeks_since is not None else None,
                    })
                    continue  # Skip — phase doesn't target this axis
                # Fall through: axis untested for 12+ weeks → maintenance retest

            # 2. Freshness check (B128): skip if tested within 42 days
            last_date_str = _recent.get(test_type) if test_type else None
            if last_date_str and not inject_tests:  # B210: explicit user intent overrides freshness window
                try:
                    days_ago = (_week_start - _parse_date(last_date_str)).days
                    if 0 <= days_ago < TEST_FRESHNESS_DAYS:
                        continue  # Skip — test completed recently
                except (ValueError, TypeError):
                    logger.warning("Invalid test date '%s' for %s — scheduling normally", last_date_str, test_sid)
            _filtered_schedule.append((test_sid, _required))

        test_placed_offsets: set = set()
        # B297 (D211-F9): pass 1 below is the historical replace-only logic,
        # untouched — weeks it can serve stay byte-identical. Tests it cannot
        # place land in _unplaced_tests for pass 2 / skipped_tests reporting.
        _unplaced_tests: List[Tuple[str, Dict[str, Any], bool]] = []
        for test_sid, _required in _filtered_schedule:
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
                # Respect finger spacing (extended by D83 recovery multiplier)
                if test_meta["finger"] and not day_has_finger and finger_day_offsets:
                    if any(abs(offset - fo) <= finger_gap_days for fo in finger_day_offsets):
                        continue
                # Respect hard-day spacing (extended by D83 recovery multiplier)
                if test_meta["hard"] and not day_has_hard and hard_day_offsets:
                    if any(abs(offset - ho) <= hard_gap_days for ho in hard_day_offsets):
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
            if not placed:
                _unplaced_tests.append((test_sid, test_meta, bool(_required)))

        # B297 (D211-F9) pass 2: a REQUIRED test that pass 1 could not place by
        # replacement may occupy an empty available day (volume +1 accepted by
        # design — losing a baseline test is worse than one extra session).
        # Optional tests stay replace-only. Same spacing/cap gates as pass 1;
        # on an empty day day_has_finger/day_has_hard are trivially False, so
        # the spacing checks apply unconditionally.
        _still_unplaced: List[Tuple[str, Dict[str, Any], bool]] = []
        for test_sid, test_meta, _required in _unplaced_tests:
            placed = False
            if _required:
                for offset in range(7):
                    if placed:
                        break
                    if offset in test_placed_offsets:
                        continue
                    if day_sessions[offset]:
                        continue  # pass 2 targets empty days only
                    if day_is_outdoor[offset]:
                        continue
                    if day_dates[offset] in pretrip_set:
                        continue  # tests are hard/max work — never on pre-trip deload days
                    if test_meta["finger"] and finger_day_offsets and any(
                        abs(offset - fo) <= finger_gap_days for fo in finger_day_offsets
                    ):
                        continue
                    if test_meta["hard"] and hard_day_offsets and any(
                        abs(offset - ho) <= hard_gap_days for ho in hard_day_offsets
                    ):
                        continue
                    if test_meta["hard"] and hard_days >= effective_hard_cap:
                        continue
                    day_avail = normalized[day_keys[offset]]
                    result = _find_best_slot(day_avail, test_meta, locations, prefer_evening=True,
                                             home_equipment=home_equipment, gyms=gyms, default_gym_id=default_gym_id)
                    if result is None:
                        continue
                    slot, slot_info = result
                    test_entry = _make_session_entry(
                        slot, test_sid, test_meta, slot_info, locations,
                        phase_id, day_keys[offset],
                        default_gym_id, gyms or [], "pass3:test_session_empty_day",
                        home_equipment=home_equipment,
                    )
                    day_sessions[offset].append(test_entry)
                    if test_meta["hard"]:
                        hard_days += 1
                        hard_day_offsets.append(offset)
                    if test_meta["finger"]:
                        finger_day_offsets.append(offset)
                    test_placed_offsets.add(offset)
                    placed = True
            if not placed:
                _still_unplaced.append((test_sid, test_meta, _required))

        # B297: placement failures are reported, never silently dropped —
        # the week view surfaces these so the user can free up a day.
        for test_sid, test_meta, _required in _still_unplaced:
            skipped_tests.append({
                "test_id": test_sid,
                "axis": _test_type_map.get(test_sid),
                "reason": "no_placement_slot",
                "required": _required,
            })

    # ── A281: no-hard sweep (closes B-PRETRIP-PASS1-ONLY) ──
    #
    # The pre-trip gate lived in PASS 1 only (`:953`), so every later pass could
    # put a hard session back. Reproduced on Daniele's real state: PASS 2.6
    # (`pulling_maintenance`) placed `finger_strength_home` — hard, intensity
    # high — on 2026-08-18, a day the planner itself had flagged
    # `pretrip_deload: True`, 48h before the flight to Kalymnos.
    #
    # Rather than repeat the check at each of the nine placement sites (there is
    # no shared placement gate, and a tenth site would silently reopen the hole),
    # this sweeps once after every pass. Trade-off recorded deliberately: it
    # REMOVES rather than replaces, so a day can end up emptier than before. On
    # at most three days immediately before departure that is the intended
    # direction, and PASS 1 still places a non-hard session there when it can.
    for offset in range(7):
        if day_dates[offset] not in pretrip_set:
            continue
        kept = []
        for session in day_sessions[offset]:
            tags = session.get("tags") or {}
            if tags.get("hard") or session.get("intensity") == "max":
                logger.info(
                    "A281 taper: dropped %s from %s (no-hard window before trip)",
                    session.get("session_id"), day_dates[offset].isoformat(),
                )
                continue
            kept.append(session)
        day_sessions[offset] = kept

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
        # A281: the volume multiplier travels ON THE DAY rather than as a
        # separate parameter, so `_auto_resolve` reads it straight off the plan
        # it is already walking — and a week generated before A281 simply has no
        # field, which means no scaling. No migration needed.
        _tv = (taper_volume or {}).get(day_dates[offset].isoformat())
        if _tv is not None and _tv < 1.0:
            day_entry["taper_volume_multiplier"] = _tv
        if day_other_activities[offset]:
            # B276: emit the full per-slot list (no legacy scalar fields).
            day_entry["other_activities"] = day_other_activities[offset]
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
        # D172-16: planning_prefs (incl. default_gym_id) are not included in profile_snapshot.
        # No current downstream consumer reads default_gym_id from snapshot, but this gap
        # must be addressed before the Supabase migration when per-request state is removed.
        "profile_snapshot": {
            "phase_id": phase_id,
            "domain_weights": domain_weights,
            # A258: the pool travels with the week, exactly like domain_weights
            # already did. The replanner used to REBUILD it from
            # (phase_id, discipline) alone — which silently dropped anything the
            # pool depends on beyond those two. That already cost a bug once
            # (B287/R-3: a boulderer got a lead pool), and with
            # profile-conditional sessions it would make a session vanish from a
            # replanned week. Carrying it removes the divergence at the root.
            "session_pool": list(session_pool),
            "intensity_cap": cap,
            "allowed_locations": locations,
            "hard_cap_per_week": effective_hard_cap,
            "recovery_multiplier": recovery_mult,
        },
        "weekly_load_summary": {
            "planned_load": total_load,
            "total_load": total_load,  # deprecated — use planned_load
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
                },
                "days": plan_days,
            }
        ],
        "skipped_tests": skipped_tests,  # B191: tests gated by phase (D92); empty if Pass 3 didn't run
        # B308: guaranteed stimuli that could NOT be placed this week. Empty is
        # the normal case. Reported rather than swallowed — an undelivered
        # "guaranteed" stimulus that fails silently is the exact bug class D263
        # took months to surface.
        "unmet_stimulus": unmet_stimulus,
    }

    if phase_id == "deload":
        week_plan = apply_deload_week(week_plan)
        # Recompute load summary after deload transformation
        all_deload_sessions = [
            s for d in week_plan["weeks"][0]["days"] for s in d["sessions"]
        ]
        deload_load = sum(s.get("estimated_load_score", 0) for s in all_deload_sessions)
        week_plan["weekly_load_summary"] = {
            "planned_load": deload_load,
            "total_load": deload_load,  # deprecated — use planned_load
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
# B128: pulling test session is resolved dynamically via _pick_pulling_test_session()
_TEST_SESSIONS_TEMPLATE = [
    ("test_max_hang_7s", True),   # finger test — day 1
    (None, False),                # pulling test — day 2 (resolved at runtime)
    ("test_repeater_7_3", True),  # finger test — day 3 (48h gap from max_hang)
]

_FILLER_SESSIONS = ["prehab_maintenance", "flexibility_full"]


def generate_test_week(
    start_date: str,
    availability: Optional[Dict[str, Any]] = None,
    allowed_locations: Optional[Sequence[str]] = None,
    gyms: Optional[Sequence[Dict[str, Any]]] = None,
    default_gym_id: Optional[str] = None,
    home_equipment: Optional[List[str]] = None,
    pulling_baseline: Optional[Dict[str, Any]] = None,
    max_pullups_bw: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a 1-week assessment plan with 3 test sessions on non-consecutive days.

    Places test_max_hang_7s and test_repeater_7_3 (both finger) with at least a
    48-hour gap.  The pulling test is placed between them (not a finger test).
    B128: pulling test is routed based on user state (BW-only vs weighted 2RM).
    Remaining available days get prehab/flexibility filler sessions.
    """
    locations = list(allowed_locations or ["gym", "home"])
    gyms_list = list(gyms or [])
    norm_avail = _normalize_availability(availability, locations)
    recovery_mult = 1.0  # test weeks always use default spacing

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

    # B128: resolve pulling test session dynamically
    _pulling_sid = _pick_pulling_test_session(pulling_baseline, max_pullups_bw)

    # Place 3 test sessions on non-consecutive available days
    # Strategy: pick first available for max_hang, then next non-finger for pullup,
    # then next available ≥2 days after max_hang for repeater
    placed: Dict[int, str] = {}  # offset → session_id

    # Place max_hang_7s (finger)
    hang_offset = None
    for off in available_offsets:
        hang_offset = off
        placed[off] = "test_max_hang_7s"
        break

    # Place pulling test (non-finger) on next available day after hang
    pullup_offset = None
    if hang_offset is not None:
        for off in available_offsets:
            if off > hang_offset and off not in placed:
                pullup_offset = off
                placed[off] = _pulling_sid
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
            "recovery_multiplier": recovery_mult,
        },
        "weekly_load_summary": {
            "planned_load": total_load,
            "total_load": total_load,  # deprecated — use planned_load
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
