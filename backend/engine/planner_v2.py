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
    "strength_long": {"hard": True, "finger": True, "intensity": "max", "climbing": True, "location": ("gym", "home")},
    "power_contact_gym": {"hard": True, "finger": False, "intensity": "max", "climbing": True, "location": ("gym",)},
    "power_endurance_gym": {"hard": True, "finger": False, "intensity": "high", "climbing": True, "location": ("gym",)},
    "endurance_aerobic_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",)},
    "technique_focus_gym": {"hard": False, "finger": False, "intensity": "medium", "climbing": True, "location": ("gym",)},
    "finger_strength_home": {"hard": True, "finger": True, "intensity": "max", "climbing": True, "location": ("home",)},
    "prehab_maintenance": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym")},
    "flexibility_full": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym")},
    "yoga_recovery": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home",)},
    "handstand_practice": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym")},
    "complementary_conditioning": {"hard": False, "finger": False, "intensity": "medium", "climbing": False, "location": ("home", "gym")},
    "regeneration_easy": {"hard": False, "finger": False, "intensity": "low", "climbing": False, "location": ("home", "gym", "outdoor")},
    "finger_maintenance_home": {"hard": False, "finger": True, "intensity": "medium", "climbing": True, "location": ("home",)},
    "test_max_hang_5s": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym")},
    "test_repeater_7_3": {"hard": True, "finger": True, "intensity": "high", "climbing": False, "location": ("home", "gym")},
    "test_max_weighted_pullup": {"hard": True, "finger": False, "intensity": "high", "climbing": False, "location": ("home", "gym")},
}

_INTENSITY_ORDER = {"low": 0, "medium": 1, "high": 2, "max": 3}

# Fallback load score for unresolved sessions (real score uses fatigue_cost from exercises)
_INTENSITY_TO_LOAD: Dict[str, int] = {"low": 20, "medium": 40, "high": 65, "max": 85}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _weekday_key(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def _intensity_allowed(session_intensity: str, phase_cap: str) -> bool:
    """Check if a session's intensity level is within the phase cap."""
    return _INTENSITY_ORDER.get(session_intensity, 0) <= _INTENSITY_ORDER.get(phase_cap, 3)


def _pick_location(
    session_locations: Tuple[str, ...],
    slot_info: Dict[str, Any],
    allowed_locations: Sequence[str],
) -> Optional[str]:
    slot_locations = slot_info.get("locations") or list(allowed_locations)
    viable = sorted(set(slot_locations).intersection(session_locations).intersection(allowed_locations))
    if not viable:
        return None
    preferred = slot_info.get("preferred_location")
    if isinstance(preferred, str):
        if preferred in viable:
            return preferred
        return None  # session can't satisfy location preference
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
) -> Optional[str]:
    slot_gym = slot_info.get("gym_id")
    if slot_gym:
        return slot_gym
    if default_gym_id:
        return default_gym_id
    if gyms:
        sorted_gyms = sorted(gyms, key=lambda g: (g.get("priority", 999), g.get("gym_id", "")))
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
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Find the best available slot for a session on a given day.

    Primary sessions prefer evening > morning > lunch.
    Complementary sessions prefer lunch > morning > evening.
    """
    if prefer_evening:
        slot_order = ("evening", "morning", "lunch")
    else:
        slot_order = ("lunch", "morning", "evening")

    for slot in slot_order:
        slot_info = day_availability[slot]
        if not slot_info["available"]:
            continue
        location = _pick_location(meta["location"], slot_info, locations)
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
) -> Dict[str, Any]:
    """Build a session entry dict for the week plan."""
    location = _pick_location(meta["location"], slot_info, locations)
    gym_id = None
    if location == "gym":
        gym_id = _select_gym_id(slot_info, default_gym_id, gyms)

    return {
        "slot": slot,
        "session_id": sid,
        "location": location,
        "gym_id": gym_id,
        "phase_id": phase_id,
        "intensity": meta["intensity"],
        "estimated_load_score": _INTENSITY_TO_LOAD.get(meta["intensity"], 40),
        "tags": {"hard": meta["hard"], "finger": meta["finger"]},
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

    # Build day structures
    day_dates: List[date] = [start + timedelta(days=i) for i in range(7)]
    day_keys: List[str] = [_weekday_key(d) for d in day_dates]
    day_sessions: List[List[Dict[str, Any]]] = [[] for _ in range(7)]

    # Track constraints
    hard_days = 0
    finger_day_offsets: List[int] = []
    hard_day_offsets: List[int] = []

    # Determine which days have available slots
    day_has_available_slot: List[bool] = []
    for offset in range(7):
        day_avail = normalized[day_keys[offset]]
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

            # Pre-trip deload: no hard/max sessions on pretrip dates
            if day_dates[offset] in pretrip_set and (meta["hard"] or meta["intensity"] == "max"):
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
            result = _find_best_slot(day_avail, meta, locations, prefer_evening=True)
            if result is None:
                primary_idx += 1
                primary_uses += 1
                attempts += 1
                continue  # try next session for SAME day

            slot, slot_info = result
            entry = _make_session_entry(
                slot, sid, meta, slot_info, locations, phase_id, day_keys[offset],
                default_gym_id, gyms or [], "pass1:primary",
            )
            day_sessions[offset].append(entry)
            primary_idx += 1
            primary_uses += 1

            if meta["hard"]:
                hard_days += 1
                hard_day_offsets.append(offset)
            if meta["finger"]:
                finger_day_offsets.append(offset)
            placed = True
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

            day_avail = normalized[day_keys[offset]]
            result = _find_best_slot(day_avail, meta, locations, prefer_evening=False)
            if result is None:
                comp_idx += 1
                comp_uses += 1
                attempts += 1
                continue  # try next session for SAME day

            slot, slot_info = result
            entry = _make_session_entry(
                slot, sid, meta, slot_info, locations, phase_id, day_keys[offset],
                default_gym_id, gyms or [], "pass2:complementary",
            )
            day_sessions[offset].append(entry)
            comp_idx += 1
            comp_uses += 1
            days_with_sessions += 1
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
                result = _find_best_slot(day_avail, test_meta, locations, prefer_evening=True)
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
        if day_dates[offset] in pretrip_set:
            day_entry["pretrip_deload"] = True
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
