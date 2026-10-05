"""A300 — complementary slots: an adaptive, deterministic lunch rotation.

A slot of the availability may say ``role: "complementary"`` (typically a lunch
break at a weights gym, ``max_minutes: 45``). The placement passes of
``planner_v2`` never see such a slot (``planner_v2._primary_view``): primaries,
quality floors, tests and substitutions stay on the other slots. This module
fills the complementary slots **after** every other pass, with their own budget
(one session per complementary slot), outside ``target_training_days_per_week``,
the target-days pruning, the hard cap and the deload 5-session cap.

What goes where
---------------
The athlete names **focus families** (``planning_prefs.complementary_rotation``,
default all four): ``legs``, ``hiit``, ``z2``, ``upper_push_arms``. Each family
maps to catalog sessions (C274), first fitting one wins: equipment of the slot's
location/gym and the slot's ``max_minutes`` against the catalog
``time_budget.hard_cap_min``. A slot may pin its own ``focus``.

The pairing family ↔ slot is **adaptive**: it is chosen each week from the
primaries actually placed, by minimum penalty, never by fixed weekday:

- HIIT not on the same day as, nor the day before, a max day (finger-hard,
  pulling-hard, test or ``intensity: max`` session) — same definition as
  ``athlete_context`` ``max_day`` plus tests;
- at most one HIIT per week (``is_hiit_like``: the catalog ``tags.hiit``, the
  ``conditioning_hiit`` exercises, the name regex only for legacy customs). HIIT
  is ``hard: False`` in the catalog: it never consumes the hard-day cap;
- biceps (``upper_push_arms_lunch`` carries curls) not within the 24 h before a
  heavy pull (``is_pulling_hard_session``);
- legs not within the 48 h before a limit session (``limit_power`` stimulus or a
  max-intensity climbing session on a wall) or an outdoor day;
- Z2 anywhere.

The rules are **penalties, never blocks**: when no pairing satisfies all of
them the least penalised one is used and every violation is reported in
``week_plan["secondary_warnings"]``; a slot no session can fill is reported in
``week_plan["unmet_secondary"]`` — nothing is dropped silently. Ties are broken
by the rotation order (the first minimum in lexicographic order of the
permutations of the rotation), so the result is deterministic.

Phase variants: in ``deload`` HIIT becomes Z2 (``DEFAULT_PHASE_VARIANTS``);
``planning_prefs.complementary_rotation_by_phase[phase]`` replaces the rotation
of that phase verbatim.

Time model: morning 08:00, lunch 13:00, evening 19:00 of the slot's day; an
outdoor day counts from 08:00. Pure and deterministic: no clock, no I/O beyond
the catalog files read by ``stimulus`` / ``planner_v2``.
"""

from __future__ import annotations

from datetime import date
from itertools import permutations
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

FOCUS_FAMILIES: Tuple[str, ...] = ("legs", "hiit", "z2", "upper_push_arms")

#: Catalog sessions of each family, in order of preference (first that fits).
FAMILY_SESSIONS: Dict[str, Tuple[str, ...]] = {
    "legs": ("legs_maintenance_lunch", "legs_strength", "lower_body_gym"),
    "hiit": ("treadmill_hiit_4x4",),
    "z2": ("treadmill_zone2_cardio",),
    "upper_push_arms": ("upper_push_arms_lunch", "upper_body_weights"),
}

DEFAULT_ROTATION: Tuple[str, ...] = ("legs", "hiit", "z2", "upper_push_arms")

#: Family substitutions per phase, applied to the general rotation and to the
#: pinned ``focus`` of a slot (decision 2026-10-05: in deload HIIT becomes Z2).
DEFAULT_PHASE_VARIANTS: Dict[str, Dict[str, str]] = {"deload": {"hiit": "z2"}}

HIIT_MAX_PER_WEEK = 1

#: Sessions carrying elbow-flexor work (the curl block of C274).
BICEPS_SESSIONS = frozenset({"upper_push_arms_lunch"})
LEGS_SESSIONS = frozenset(FAMILY_SESSIONS["legs"])

SLOT_HOUR: Dict[str, int] = {"morning": 8, "lunch": 13, "evening": 19}
OUTDOOR_START_HOUR = 8
BICEPS_WINDOW_H = 24
LEGS_WINDOW_H = 48

PENALTY_RULE = 100
PENALTY_NO_SESSION = 1000
#: Above this many free slots the permutation search falls back to the rotation
#: order (8! = 40320 pairings is the most a week is allowed to cost).
MAX_SEARCH_SLOTS = 8

_SLOTS: Tuple[str, ...] = ("morning", "lunch", "evening")
_WEEKDAYS: Tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------

def _valid_families(raw: Any) -> Optional[List[str]]:
    if not isinstance(raw, list):
        return None
    return [f for f in raw if isinstance(f, str) and f in FOCUS_FAMILIES]


def resolve_rotation(planning_prefs: Optional[Mapping[str, Any]], phase_id: str) -> List[str]:
    """The rotation of this phase: per-phase override verbatim, else the
    general rotation (default all four families) with the phase variants."""
    prefs = planning_prefs or {}
    by_phase = prefs.get("complementary_rotation_by_phase")
    if isinstance(by_phase, Mapping):
        explicit = _valid_families(by_phase.get(phase_id))
        if explicit is not None:
            return explicit
    general = _valid_families(prefs.get("complementary_rotation"))
    rotation = list(DEFAULT_ROTATION) if general is None else general
    variant = DEFAULT_PHASE_VARIANTS.get(phase_id) or {}
    return [variant.get(f, f) for f in rotation]


def family_of(session: Mapping[str, Any]) -> Optional[str]:
    """The family of a planned session (by catalog id, else HIIT-like)."""
    from backend.engine.stimulus import is_hiit_like

    sid = str(session.get("session_id") or "")
    focus = session.get("focus")
    if isinstance(focus, str) and focus in FOCUS_FAMILIES:
        return focus
    for fam, sids in FAMILY_SESSIONS.items():
        if sid in sids:
            return fam
    if is_hiit_like(session):
        return "hiit"
    return None


# ---------------------------------------------------------------------------
# Validation (API)
# ---------------------------------------------------------------------------

def validate_structure(
    availability: Any = None, planning_prefs: Any = None,
) -> List[str]:
    """Errors in the A300 fields of an availability / planning_prefs patch.

    Only the new fields are checked; everything else is left to the existing
    tolerant normalisation. Empty list = valid.
    """
    from backend.engine.macrocycle_v1 import PHASE_ORDER
    from backend.engine.planner_v2 import SLOT_MAX_MINUTES_RANGE, SLOT_ROLES

    errors: List[str] = []
    if isinstance(availability, Mapping):
        for wd, day in availability.items():
            if not isinstance(day, Mapping):
                continue
            for slot in _SLOTS:
                sv = day.get(slot)
                if not isinstance(sv, Mapping):
                    continue
                where = f"availability.{wd}.{slot}"
                if "role" in sv and sv["role"] is not None and sv["role"] not in SLOT_ROLES:
                    errors.append(f"{where}.role must be one of {', '.join(SLOT_ROLES)}")
                if "max_minutes" in sv and sv["max_minutes"] is not None:
                    mm = sv["max_minutes"]
                    lo, hi = SLOT_MAX_MINUTES_RANGE
                    if not isinstance(mm, int) or isinstance(mm, bool) or not lo <= mm <= hi:
                        errors.append(f"{where}.max_minutes must be an integer between {lo} and {hi}")
                if "focus" in sv and sv["focus"] is not None and sv["focus"] not in FOCUS_FAMILIES:
                    errors.append(f"{where}.focus must be one of {', '.join(FOCUS_FAMILIES)}")
    if isinstance(planning_prefs, Mapping):
        def _check_list(value: Any, where: str) -> None:
            if value is None:
                return
            if not isinstance(value, list) or len(value) > 21:
                errors.append(f"{where} must be a list of at most 21 focus families")
                return
            bad = [f for f in value if f not in FOCUS_FAMILIES]
            if bad:
                errors.append(f"{where}: unknown focus {', '.join(map(str, bad))} "
                              f"(expected {', '.join(FOCUS_FAMILIES)})")

        _check_list(planning_prefs.get("complementary_rotation"), "planning_prefs.complementary_rotation")
        by_phase = planning_prefs.get("complementary_rotation_by_phase")
        if by_phase is not None:
            if not isinstance(by_phase, Mapping):
                errors.append("planning_prefs.complementary_rotation_by_phase must be an object")
            else:
                for ph, lst in by_phase.items():
                    if ph not in PHASE_ORDER:
                        errors.append(f"planning_prefs.complementary_rotation_by_phase: unknown phase {ph}")
                        continue
                    _check_list(lst, f"planning_prefs.complementary_rotation_by_phase.{ph}")
    return errors


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def _on_wall(session: Mapping[str, Any]) -> bool:
    """A session climbed on a wall (boulder / routes), not a hangboard one —
    sore legs hurt foot precision on the wall, not on a hangboard."""
    from backend.engine.planner_v2 import _SESSION_META, _WALL_SURFACES_REQUIRING_HOME_EXPANSION

    req = (_SESSION_META.get(str(session.get("session_id") or "")) or {}).get("required_equipment") or []
    return bool(set(req) & _WALL_SURFACES_REQUIRING_HOME_EXPANSION)


def _classify_events(days: Sequence[Mapping[str, Any]], normalized_full: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Every placed session (and outdoor day) as a timed event with its kinds."""
    from backend.engine.stimulus import (
        FAMILY_LIMIT_POWER,
        is_finger_hard_session,
        is_pulling_hard_session,
        is_test_session,
        session_flag,
        session_stimuli,
    )

    events: List[Dict[str, Any]] = []
    for offset, day in enumerate(days):
        for s in day.get("sessions") or []:
            if s.get("slot_role") == "complementary":
                continue
            stimuli = session_stimuli(s)
            max_intensity = s.get("intensity") == "max"
            kinds = set()
            if is_finger_hard_session(s) or is_pulling_hard_session(s) or is_test_session(s) or max_intensity:
                kinds.add("max")
            if is_pulling_hard_session(s):
                kinds.add("heavy_pull")
            if FAMILY_LIMIT_POWER in stimuli or (max_intensity and session_flag(s, "climbing") and _on_wall(s)):
                kinds.add("limit")
            if kinds:
                events.append({"offset": offset, "t": offset * 24 + SLOT_HOUR.get(str(s.get("slot")), 19),
                               "kinds": kinds, "date": day.get("date"), "session_id": s.get("session_id")})
        wd = day.get("weekday") or _WEEKDAYS[offset]
        day_avail = normalized_full.get(wd) or {}
        outdoor = bool(day.get("outdoor_slot")) or any(
            si.get("available") and (si.get("preferred_location") == "outdoor" or si.get("locations") == ["outdoor"])
            for si in day_avail.values()
        )
        if outdoor:
            events.append({"offset": offset, "t": offset * 24 + OUTDOOR_START_HOUR, "kinds": {"outdoor"},
                           "date": day.get("date"), "session_id": None})
    return events


def _violations(sid: str, offset: int, slot: str, events: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    from backend.engine.stimulus import is_hiit_like

    t = offset * 24 + SLOT_HOUR.get(slot, 13)
    out: List[Dict[str, Any]] = []
    if is_hiit_like({"session_id": sid}):
        hits = [e for e in events if "max" in e["kinds"] and e["offset"] in (offset, offset + 1)]
        if hits:
            out.append({"code": "hiit_near_max",
                        "with": [f"{e['date']} {e['session_id']}" for e in hits]})
    if sid in BICEPS_SESSIONS:
        hits = [e for e in events if "heavy_pull" in e["kinds"] and 0 < e["t"] - t <= BICEPS_WINDOW_H]
        if hits:
            out.append({"code": "biceps_before_heavy_pull",
                        "with": [f"{e['date']} {e['session_id']}" for e in hits]})
    if sid in LEGS_SESSIONS:
        hits = [e for e in events if e["kinds"] & {"limit", "outdoor"} and 0 < e["t"] - t <= LEGS_WINDOW_H]
        if hits:
            out.append({"code": "legs_before_limit",
                        "with": [f"{e['date']} {e['session_id'] or 'outdoor'}" for e in hits]})
    return out


def place_complementary(
    week_plan: Dict[str, Any],
    *,
    normalized_full: Mapping[str, Mapping[str, Dict[str, Any]]],
    phase_id: str,
    planning_prefs: Optional[Mapping[str, Any]],
    locations: Sequence[str],
    home_equipment: Optional[List[str]],
    gyms: Sequence[Dict[str, Any]],
    default_gym_id: Optional[str],
    today: Optional[date] = None,
    existing_week_plan: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Fill the complementary slots of ``week_plan`` in place (see module doc).

    Always sets ``week_plan["unmet_secondary"]`` and
    ``week_plan["secondary_warnings"]`` (lists, possibly empty) — the caller
    only invokes it when the availability has at least one complementary slot.
    """
    from backend.engine.planner_v2 import (
        _SESSION_META,
        _INTENSITY_TO_LOAD,
        _expand_session_locations,
        _fits_max_minutes,
        _make_session_entry,
        _pick_location,
    )
    from backend.engine.stimulus import is_hiit_like

    days: List[Dict[str, Any]] = week_plan["weeks"][0]["days"]
    unmet: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    # Complementary slots of the week, chronological.
    all_slots: List[Tuple[int, str, Dict[str, Any]]] = []
    for offset, day in enumerate(days):
        wd = day.get("weekday") or _WEEKDAYS[offset]
        for sn in _SLOTS:
            si = (normalized_full.get(wd) or {}).get(sn) or {}
            if si.get("role") == "complementary" and si.get("available"):
                all_slots.append((offset, sn, si))

    def _is_past(offset: int) -> bool:
        return today is not None and date.fromisoformat(days[offset]["date"]) < today

    # What already happened on the past days of this week (regeneration).
    past_by_slot: Dict[Tuple[str, str], List[Mapping[str, Any]]] = {}
    past_hiit = 0
    if today is not None and isinstance(existing_week_plan, Mapping) \
            and existing_week_plan.get("start_date") == week_plan.get("start_date"):
        for wk in existing_week_plan.get("weeks") or []:
            for day in wk.get("days") or []:
                d = str(day.get("date") or "")
                if not d or d >= today.isoformat():
                    continue
                for s in day.get("sessions") or []:
                    past_by_slot.setdefault((d, str(s.get("slot"))), []).append(s)
                    if is_hiit_like(s) and s.get("status") != "skipped":
                        past_hiit += 1

    variant = DEFAULT_PHASE_VARIANTS.get(phase_id) or {}
    rotation = resolve_rotation(planning_prefs, phase_id)

    fixed: List[Tuple[int, str, Dict[str, Any], str]] = []  # future slots with a pinned focus
    free: List[Tuple[int, str, Dict[str, Any]]] = []
    consumed: List[str] = []
    for offset, sn, si in all_slots:
        if _is_past(offset):
            for s in past_by_slot.get((days[offset]["date"], sn), []):
                fam = family_of(s)
                if fam:
                    consumed.append(fam)
                    break
            continue
        pinned = si.get("focus")
        if isinstance(pinned, str) and pinned in FOCUS_FAMILIES:
            fam = variant.get(pinned, pinned)
            fixed.append((offset, sn, si, fam))
            consumed.append(fam)
        else:
            free.append((offset, sn, si))

    # The week's family multiset, in rotation order, minus what is consumed.
    pool: List[str] = []
    if rotation:
        n_total = len(all_slots)
        shift = 0
        if n_total < len(rotation):
            # Fewer slots than families: rotate the start week by week so every
            # family comes round (deterministic from the week's Monday).
            shift = (date.fromisoformat(week_plan["start_date"]).toordinal() // 7) % len(rotation)
        cycle = [rotation[(shift + i) % len(rotation)] for i in range(n_total)]
        for fam in consumed:
            if fam in cycle:
                cycle.remove(fam)
        pool = cycle
        i = 0
        while len(pool) < len(free):  # pinned families outside the rotation
            pool.append(rotation[i % len(rotation)])
            i += 1
        # HIIT cap: the week holds at most HIIT_MAX_PER_WEEK.
        hiit_budget = HIIT_MAX_PER_WEEK - past_hiit - sum(1 for *_x, f in fixed if f == "hiit")
        capped: List[str] = []
        for fam in pool:
            if fam == "hiit":
                if hiit_budget > 0:
                    hiit_budget -= 1
                else:
                    fam = "z2"
            capped.append(fam)
        pool = capped

    events = _classify_events(days, normalized_full)

    def _candidate(fam: str, offset: int, sn: str, si: Dict[str, Any], used: Mapping[str, int]) -> Optional[str]:
        for sid in FAMILY_SESSIONS.get(fam, ()):
            meta = _SESSION_META.get(sid)
            if meta is None:
                continue
            if used.get(sid, 0) >= meta.get("max_per_week", 1):
                continue
            if not _fits_max_minutes(si, sid):
                continue
            locs = _expand_session_locations(meta["location"], meta.get("required_equipment"), home_equipment)
            if _pick_location(locs, si, locations, required_equipment=meta.get("required_equipment"),
                              home_equipment=home_equipment, gyms=gyms, default_gym_id=default_gym_id) is None:
                continue
            return sid
        return None

    used0: Dict[str, int] = {}
    for day in days:
        for s in day.get("sessions") or []:
            used0[str(s.get("session_id"))] = used0.get(str(s.get("session_id")), 0) + 1

    cost_cache: Dict[Tuple[str, int], int] = {}

    def _cost(fam: str, idx: int) -> int:
        key = (fam, idx)
        if key not in cost_cache:
            offset, sn, si = free[idx]
            sid = _candidate(fam, offset, sn, si, used0)
            cost_cache[key] = PENALTY_NO_SESSION if sid is None else \
                PENALTY_RULE * len(_violations(sid, offset, sn, events))
        return cost_cache[key]

    k = len(free)
    best: Optional[Tuple[str, ...]] = None
    if k and pool:
        take = min(k, len(pool))
        if k <= MAX_SEARCH_SLOTS and len(pool) <= MAX_SEARCH_SLOTS:
            best_cost: Optional[int] = None
            seen = set()
            for perm in permutations(range(len(pool)), take):
                fams = tuple(pool[j] for j in perm)
                if fams in seen:
                    continue
                seen.add(fams)
                c = sum(_cost(f, i) for i, f in enumerate(fams))
                if best_cost is None or c < best_cost:
                    best_cost, best = c, fams
                    if c == 0:
                        break
        else:
            best = tuple(pool[:take])

    assignment: List[Tuple[int, str, Dict[str, Any], Optional[str]]] = []
    for i, (offset, sn, si) in enumerate(free):
        fam = best[i] if best is not None and i < len(best) else None
        assignment.append((offset, sn, si, fam))
    assignment.extend(fixed)
    assignment.sort(key=lambda a: (a[0], _SLOTS.index(a[1])))

    used = dict(used0)
    added_load = 0
    for offset, sn, si, fam in assignment:
        day = days[offset]
        if fam is None:
            unmet.append({"date": day["date"], "slot": sn, "focus": None,
                          "reason": "no_focus" if not rotation else "rotation_exhausted"})
            continue
        sid = _candidate(fam, offset, sn, si, used)
        if sid is None:
            unmet.append({"date": day["date"], "slot": sn, "focus": fam, "reason": "no_session_fits",
                          "candidates": list(FAMILY_SESSIONS.get(fam, ()))})
            continue
        meta = _SESSION_META[sid]
        entry = _make_session_entry(
            sn, sid, meta, si, locations, phase_id, day.get("weekday") or _WEEKDAYS[offset],
            default_gym_id, list(gyms), "pass_complementary:a300", home_equipment=home_equipment,
        )
        entry["slot_role"] = "complementary"
        entry["focus"] = fam
        entry["explain"].append(f"focus={fam}")
        for v in _violations(sid, offset, sn, events):
            warnings.append({"date": day["date"], "slot": sn, "session_id": sid, "focus": fam, **v})
        if fam == "hiit" and past_hiit + sum(1 for a in assignment if a[3] == "hiit") > HIIT_MAX_PER_WEEK:
            warnings.append({"date": day["date"], "slot": sn, "session_id": sid, "focus": fam,
                             "code": "hiit_weekly_cap", "with": []})
        used[sid] = used.get(sid, 0) + 1
        added_load += _INTENSITY_TO_LOAD.get(meta["intensity"], 40)
        sessions = day.setdefault("sessions", [])
        # Chronological within the day: before the first session of a later slot.
        later = [j for j, s in enumerate(sessions)
                 if s.get("slot") in _SLOTS and _SLOTS.index(s["slot"]) > _SLOTS.index(sn)]
        sessions.insert(later[0] if later else len(sessions), entry)

    summary = week_plan.get("weekly_load_summary")
    if isinstance(summary, dict) and added_load:
        summary["planned_load"] = summary.get("planned_load", 0) + added_load
        summary["total_load"] = summary.get("total_load", 0) + added_load
        summary["recovery_days_count"] = sum(
            1 for d in days if not d.get("sessions") or all(s.get("intensity") == "low" for s in d["sessions"])
        )
    week_plan["unmet_secondary"] = unmet
    week_plan["secondary_warnings"] = warnings
    return week_plan


__all__ = [
    "BICEPS_SESSIONS", "DEFAULT_PHASE_VARIANTS", "DEFAULT_ROTATION", "FAMILY_SESSIONS",
    "FOCUS_FAMILIES", "HIIT_MAX_PER_WEEK", "family_of", "place_complementary",
    "resolve_rotation", "validate_structure",
]
