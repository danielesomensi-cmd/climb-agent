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
  pulling-hard, test or ``intensity: max`` session) or an outdoor day (an
  outdoor slot, the day-level outdoor block of the plan, a trip departure);
- at most one HIIT per week (``is_hiit_like``: the catalog ``tags.hiit``, the
  ``conditioning_hiit`` exercises, the name regex only for legacy customs). HIIT
  is ``hard: False`` in the catalog: it never consumes the hard-day cap;
- biceps (``upper_push_arms_lunch`` carries curls) not within the 24 h before a
  heavy pull (``is_pulling_hard_session``);
- legs not within the 48 h before a limit session (``limit_power`` stimulus or a
  max-intensity climbing session on a wall) or an outdoor day;
- Z2 anywhere;
- HIIT and legs not on a pre-trip no-hard day (``pretrip_dates``).

The rules see the week **as the user will see it**: the cached plan of the
week (``existing_week_plan``) is merged back exactly as B369's
``regenerate_preserving_completed`` will do, so the user's customs, forced and
moved sessions and outdoor days count, and a complementary slot the user filled
or emptied is never refilled (its family counts as done for the week). Beyond
the week: trip departures up to the Tuesday after and the first two days of the
cached next week. After an edit the alerts are recomputed on the stored week
(``refresh_secondary_warnings``, from ``GET /api/week`` after the merge and
from ``persist_week_plan``) — alerts only, nothing is rewritten.

The rules are **penalties, never blocks**: when no pairing satisfies all of
them the least penalised one is used and every violation is reported in
``week_plan["secondary_warnings"]``; a slot no session can fill is reported in
``week_plan["unmet_secondary"]``, and so is a family of the week's rotation
that found no slot (``rotation_overflow``) — nothing is dropped silently. Ties are broken
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


#: Every catalog session a focus family can place (a removal of one of these
#: with no slot recorded is a removal of a complementary session).
_FAMILY_SIDS = frozenset(sid for sids in FAMILY_SESSIONS.values() for sid in sids)


def _family_incl_skip(session: Mapping[str, Any]) -> Optional[str]:
    """``family_of``, reading a skip stub as the session it replaced (the stub
    itself is ``regeneration_easy``)."""
    if session.get("status") == "skipped":
        orig = session.get("skipped_original")
        if isinstance(orig, Mapping):
            fam = family_of(orig)
            if fam:
                return fam
        sid = session.get("skipped_session_id")
        if sid:
            return family_of({"session_id": sid})
    return family_of(session)


def _is_outdoor_day(day: Mapping[str, Any]) -> bool:
    """A day the athlete climbs outside: the planner's ``outdoor_slot`` or the
    day-level outdoor block a user set on the plan (override / set_outdoor_plan)."""
    return bool(
        day.get("outdoor_slot") or day.get("outdoor_spot_name") or day.get("outdoor_spot_id")
        or day.get("outdoor_plan") or day.get("outdoor_session_status") in ("planned", "done")
    )


def _session_kinds(s: Mapping[str, Any]) -> set:
    from backend.engine.stimulus import (
        FAMILY_LIMIT_POWER,
        is_finger_hard_session,
        is_pulling_hard_session,
        is_test_session,
        session_flag,
        session_stimuli,
    )

    stimuli = session_stimuli(s)
    max_intensity = s.get("intensity") == "max"
    kinds = set()
    if is_finger_hard_session(s) or is_pulling_hard_session(s) or is_test_session(s) or max_intensity:
        kinds.add("max")
    if is_pulling_hard_session(s):
        kinds.add("heavy_pull")
    if FAMILY_LIMIT_POWER in stimuli or (max_intensity and session_flag(s, "climbing") and _on_wall(s)):
        kinds.add("limit")
    return kinds


def _is_complementary_like(s: Mapping[str, Any]) -> bool:
    return s.get("slot_role") == "complementary" or family_of(s) is not None


def _day_events(day: Mapping[str, Any], offset: int, day_avail: Mapping[str, Any]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for s in day.get("sessions") or []:
        if s.get("status") == "skipped" or _is_complementary_like(s):
            continue
        kinds = _session_kinds(s)
        if kinds:
            events.append({"offset": offset, "t": offset * 24 + SLOT_HOUR.get(str(s.get("slot")), 19),
                           "kinds": kinds, "date": day.get("date"), "session_id": s.get("session_id")})
    outdoor = _is_outdoor_day(day) or any(
        si.get("available") and (si.get("preferred_location") == "outdoor" or si.get("locations") == ["outdoor"])
        for si in (day_avail or {}).values()
    )
    if outdoor:
        events.append({"offset": offset, "t": offset * 24 + OUTDOOR_START_HOUR, "kinds": {"outdoor"},
                       "date": day.get("date"), "session_id": None})
    return events


def _classify_events(
    days: Sequence[Mapping[str, Any]],
    normalized_full: Mapping[str, Any],
    *,
    week_start: Optional[str] = None,
    trip_start_dates: Optional[Sequence[str]] = None,
    next_week_plan: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Every session that matters to the rules (and every outdoor day) as a
    timed event with its kinds.

    Beyond the week itself: the departure of a trip (``trip_start_dates``, an
    outdoor event at 08:00 — also when it falls early next week, so the 48 h
    legs window crosses Monday) and the first two days of the cached next week
    (``next_week_plan``), so a Sunday-lunch HIIT before Monday's max is seen.
    Skipped sessions and complementary-like sessions (a family session, engine
    or user) are not events."""
    events: List[Dict[str, Any]] = []
    for offset, day in enumerate(days):
        wd = day.get("weekday") or _WEEKDAYS[offset % 7]
        events.extend(_day_events(day, offset, normalized_full.get(wd) or {}))
    ws = week_start or (days[0].get("date") if days else None)
    if not ws:
        return events
    ws_d = date.fromisoformat(ws)
    seen_outdoor = {e["offset"] for e in events if "outdoor" in e["kinds"]}
    for d_iso in sorted(set(trip_start_dates or [])):
        try:
            off = (date.fromisoformat(str(d_iso)[:10]) - ws_d).days
        except ValueError:
            continue
        if 0 <= off <= 8 and off not in seen_outdoor:
            seen_outdoor.add(off)
            events.append({"offset": off, "t": off * 24 + OUTDOOR_START_HOUR, "kinds": {"outdoor"},
                           "date": str(d_iso)[:10], "session_id": "trip"})
    if isinstance(next_week_plan, Mapping) and next_week_plan.get("start_date") == \
            date.fromordinal(ws_d.toordinal() + 7).isoformat():
        nxt = ((next_week_plan.get("weeks") or [{}])[0] or {}).get("days") or []
        for j, day in enumerate(nxt[:2]):
            for e in _day_events(day, 7 + j, {}):
                if "outdoor" in e["kinds"] and e["offset"] in seen_outdoor:
                    continue
                events.append(e)
    return events


def _rule_family(session: Mapping[str, Any]) -> Tuple[bool, bool, bool]:
    """(hiit, biceps, legs) — which placement rules apply to *session*."""
    from backend.engine.stimulus import is_hiit_like

    sid = str(session.get("session_id") or "")
    return (is_hiit_like(session), sid in BICEPS_SESSIONS,
            sid in LEGS_SESSIONS or session.get("focus") == "legs")


def _session_violations(
    session: Mapping[str, Any], offset: int, slot: str, events: Sequence[Mapping[str, Any]],
    pretrip_offsets: frozenset = frozenset(),
) -> List[Dict[str, Any]]:
    hiit, biceps, legs = _rule_family(session)
    t = offset * 24 + SLOT_HOUR.get(slot, 13)
    out: List[Dict[str, Any]] = []
    if hiit:
        # An outdoor day is a max day for HIIT: Friday lunch HIIT before a
        # Saturday at the crag is exactly what the rule is for.
        hits = [e for e in events if e["kinds"] & {"max", "outdoor"} and e["offset"] in (offset, offset + 1)]
        if hits:
            out.append({"code": "hiit_near_max",
                        "with": [f"{e['date']} {e['session_id'] or 'outdoor'}" for e in hits]})
    if biceps:
        hits = [e for e in events if "heavy_pull" in e["kinds"] and 0 < e["t"] - t <= BICEPS_WINDOW_H]
        if hits:
            out.append({"code": "biceps_before_heavy_pull",
                        "with": [f"{e['date']} {e['session_id']}" for e in hits]})
    if legs:
        hits = [e for e in events if e["kinds"] & {"limit", "outdoor"} and 0 < e["t"] - t <= LEGS_WINDOW_H]
        if hits:
            out.append({"code": "legs_before_limit",
                        "with": [f"{e['date']} {e['session_id'] or 'outdoor'}" for e in hits]})
    if (hiit or legs) and offset in pretrip_offsets:
        out.append({"code": "pretrip_no_hard", "with": []})
    return out


def _violations(sid: str, offset: int, slot: str, events: Sequence[Mapping[str, Any]],
                pretrip_offsets: frozenset = frozenset()) -> List[Dict[str, Any]]:
    return _session_violations({"session_id": sid}, offset, slot, events, pretrip_offsets)


def _pretrip_offsets(week_start: str, pretrip_dates: Optional[Sequence[str]]) -> frozenset:
    ws_d = date.fromisoformat(week_start)
    out = set()
    for d_iso in pretrip_dates or []:
        try:
            off = (date.fromisoformat(str(d_iso)[:10]) - ws_d).days
        except ValueError:
            continue
        if 0 <= off <= 6:
            out.add(off)
    return frozenset(out)


def trip_start_dates(trips: Any, week_start: str) -> List[str]:
    """Departures between ``week_start`` and two days after the week's end —
    the ones a lunch of this week can be within 48 h of."""
    ws_d = date.fromisoformat(week_start)
    out = set()
    for t in trips or []:
        if not isinstance(t, Mapping):
            continue
        try:
            d = date.fromisoformat(str(t.get("start_date") or "")[:10])
        except ValueError:
            continue
        if 0 <= (d - ws_d).days <= 8:
            out.add(d.isoformat())
    return sorted(out)


def complementary_warnings(
    week_plan: Mapping[str, Any],
    normalized_full: Optional[Mapping[str, Any]] = None,
    *,
    pretrip_dates: Optional[Sequence[str]] = None,
    trip_start_dates: Optional[Sequence[str]] = None,
    next_week_plan: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """The placement rules checked on a whole week as it stands — engine
    lunches and every session the user owns (custom, forced, moved…).

    Alerts only (A301: the user's sessions are the user's decision). Sessions
    already done or skipped are not flagged (that is history). Engine
    primaries are not flagged either — they are the planner's job and its own
    guards cover them. Same events and rules as the placement, so the alerts of
    a freshly generated week and of the same week re-checked after the merge /
    an edit agree.
    """
    from backend.engine.user_owned import is_user_owned

    days = ((week_plan.get("weeks") or [{}])[0] or {}).get("days") or []
    if not days:
        return []
    ws = str(week_plan.get("start_date") or days[0].get("date"))
    events = _classify_events(days, normalized_full or {}, week_start=ws,
                              trip_start_dates=trip_start_dates, next_week_plan=next_week_plan)
    pre = _pretrip_offsets(ws, pretrip_dates)
    out: List[Dict[str, Any]] = []
    hiit_seen = 0
    for offset, day in enumerate(days):
        for s in sorted(day.get("sessions") or [],
                        key=lambda x: _SLOTS.index(x["slot"]) if x.get("slot") in _SLOTS else 2):
            if s.get("status") == "skipped":
                continue
            hiit, biceps, legs = _rule_family(s)
            if not (hiit or biceps or legs):
                continue
            if hiit:
                hiit_seen += 1
            if s.get("status") == "done":
                continue
            if not (s.get("slot_role") == "complementary" or is_user_owned(s)):
                continue
            sn = str(s.get("slot") or "lunch")
            base = {"date": day.get("date"), "slot": sn, "session_id": s.get("session_id"),
                    "focus": _family_incl_skip(s)}
            for v in _session_violations(s, offset, sn, events, pre):
                out.append({**base, **v})
            if hiit and hiit_seen > HIIT_MAX_PER_WEEK:
                out.append({**base, "code": "hiit_weekly_cap", "with": []})
    return out


def _effective_view(
    week_plan: Mapping[str, Any], existing: Optional[Mapping[str, Any]], today: Optional[date],
) -> Mapping[str, Any]:
    """*week_plan* as it will look once the user's content of *existing* is
    merged back (B369 ``regenerate_preserving_completed``, the very merge
    ``GET /api/week`` runs). Falls back to *week_plan* if the merge fails."""
    if not isinstance(existing, Mapping) or existing.get("start_date") != week_plan.get("start_date"):
        return week_plan
    from copy import deepcopy

    from backend.engine.replanner_v1 import regenerate_preserving_completed

    try:
        return regenerate_preserving_completed(
            deepcopy(dict(existing)), deepcopy(dict(week_plan)),
            preserve_before=today.isoformat() if today else None,
        )
    except Exception:  # an alert must never break the week
        return week_plan


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
    pretrip_dates: Optional[Sequence[str]] = None,
    trip_start_dates: Optional[Sequence[str]] = None,
    next_week_plan: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Fill the complementary slots of ``week_plan`` in place (see module doc).

    ``existing_week_plan`` (the cached plan of this same week) is read the way
    the B369 merge will put it back: the days already lived (before today, or
    today with something done) count what happened there; on the other days
    every session the user owns (custom, forced, moved, skipped…) stays, and a
    complementary slot holding one — or one the user emptied — is never
    refilled; their families count as this week's rotation and their HIIT
    toward the weekly cap. The rules are checked against that merged week.

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
    from backend.engine.user_owned import is_preservable, removal_records, whole_day_override_dates

    days: List[Dict[str, Any]] = week_plan["weeks"][0]["days"]
    ws = str(week_plan["start_date"])
    unmet: List[Dict[str, Any]] = []

    # Complementary slots of the week, chronological.
    all_slots: List[Tuple[int, str, Dict[str, Any]]] = []
    for offset, day in enumerate(days):
        wd = day.get("weekday") or _WEEKDAYS[offset]
        for sn in _SLOTS:
            si = (normalized_full.get(wd) or {}).get(sn) or {}
            if si.get("role") == "complementary" and si.get("available"):
                all_slots.append((offset, sn, si))

    # ── What the user's plan of this week already holds ──
    same_week = isinstance(existing_week_plan, Mapping) \
        and existing_week_plan.get("start_date") == week_plan.get("start_date")
    old_days: Dict[str, Mapping[str, Any]] = {}
    removals: List[Dict[str, Any]] = []
    whole_day: set = set()
    if same_week:
        for wk in existing_week_plan.get("weeks") or []:
            for day in wk.get("days") or []:
                if day.get("date"):
                    old_days[str(day["date"])] = day
        removals = removal_records(existing_week_plan)
        whole_day = set(whole_day_override_dates(existing_week_plan))
    today_iso = today.isoformat() if today is not None else None

    def _frozen(d_iso: str) -> bool:
        """Lived days — the merge copies them wholesale (same rule as B369)."""
        if today_iso is None:
            return False
        if d_iso < today_iso:
            return True
        old = old_days.get(d_iso)
        return d_iso == today_iso and old is not None and (
            any(s.get("status") == "done" for s in old.get("sessions") or [])
            or old.get("outdoor_session_status") == "done")

    consumed: List[str] = []
    hiit_done = 0  # HIIT the week already holds (lived, or the user's own)
    for d_iso, old in sorted(old_days.items()):
        frozen = _frozen(d_iso)
        for s in old.get("sessions") or []:
            if not frozen and not is_preservable(s):
                continue
            fam = _family_incl_skip(s)
            if fam:
                consumed.append(fam)
            if s.get("status") != "skipped" and is_hiit_like(s):
                hiit_done += 1
    for r in removals:
        if r["kind"] == "moved":
            continue  # counted where it landed
        if r["ref"] and r["date"] in old_days:
            fam = family_of({"session_id": r["ref"]})
            if fam:
                consumed.append(fam)

    def _slot_removed(d_iso: str, sn: str) -> bool:
        if d_iso in whole_day:
            return True
        return any(r["date"] == d_iso and (r["slot"] == sn or (r["slot"] is None and r["ref"] in _FAMILY_SIDS))
                   for r in removals)

    variant = DEFAULT_PHASE_VARIANTS.get(phase_id) or {}
    rotation = resolve_rotation(planning_prefs, phase_id)

    fixed: List[Tuple[int, str, Dict[str, Any], str]] = []  # future slots with a pinned focus
    free: List[Tuple[int, str, Dict[str, Any]]] = []
    n_known = 0  # slots that count toward this week's rotation
    for offset, sn, si in all_slots:
        d_iso = days[offset]["date"]
        old = old_days.get(d_iso)
        old_slot = [s for s in (old or {}).get("sessions") or [] if s.get("slot") == sn]
        if _frozen(d_iso):
            # Lived: what is there (or was removed) counted above; a lived slot
            # with no trace at all is unknown and left out of the rotation.
            if old_slot or _slot_removed(d_iso, sn):
                n_known += 1
            continue
        n_known += 1
        kept = [s for s in old_slot if is_preservable(s)]
        shared = any(not is_preservable(s) for s in old_slot)
        if _slot_removed(d_iso, sn) or (kept and not shared):
            continue  # the user's slot: never refilled
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
        shift = 0
        if n_known < len(rotation):
            # Fewer slots than families: rotate the start week by week so every
            # family comes round (deterministic from the week's Monday).
            shift = (date.fromisoformat(ws).toordinal() // 7) % len(rotation)
        cycle = [rotation[(shift + i) % len(rotation)] for i in range(n_known)]
        for fam in consumed:
            if fam in cycle:
                cycle.remove(fam)
        pool = cycle
        i = 0
        while len(pool) < len(free):  # pinned families outside the rotation
            pool.append(rotation[i % len(rotation)])
            i += 1
        # HIIT cap: the week holds at most HIIT_MAX_PER_WEEK.
        hiit_budget = HIIT_MAX_PER_WEEK - hiit_done - sum(1 for *_x, f in fixed if f == "hiit")
        capped: List[str] = []
        for fam in pool:
            if fam == "hiit":
                if hiit_budget > 0:
                    hiit_budget -= 1
                else:
                    fam = "z2"
            capped.append(fam)
        pool = capped

    view = _effective_view(week_plan, existing_week_plan, today)
    view_days = ((view.get("weeks") or [{}])[0] or {}).get("days") or days
    events = _classify_events(view_days, normalized_full, week_start=ws,
                              trip_start_dates=trip_start_dates, next_week_plan=next_week_plan)
    pre = _pretrip_offsets(ws, pretrip_dates)

    def _candidate(fam: str, si: Dict[str, Any], used: Mapping[str, int], pinned: bool = False) -> Optional[str]:
        for sid in FAMILY_SESSIONS.get(fam, ()):
            meta = _SESSION_META.get(sid)
            if meta is None:
                continue
            # A pin is the user's decision: the catalog weekly cap does not
            # refuse it (an alert does — hiit_weekly_cap).
            if not pinned and used.get(sid, 0) >= meta.get("max_per_week", 1):
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
    for day in view_days:
        for s in day.get("sessions") or []:
            if s.get("status") == "skipped":
                continue
            used0[str(s.get("session_id"))] = used0.get(str(s.get("session_id")), 0) + 1

    # Pinned slots first: their sessions are fixed, the search works around them.
    fixed_sids: List[Optional[str]] = []
    for offset, sn, si, fam in fixed:
        sid = _candidate(fam, si, used0, pinned=True)
        fixed_sids.append(sid)
        if sid:
            used0[sid] = used0.get(sid, 0) + 1

    cand_cache: Dict[Tuple[str, int, Tuple[int, ...]], Optional[str]] = {}
    viol_cache: Dict[Tuple[str, int], int] = {}

    def _pick(fam: str, idx: int, used: Mapping[str, int]) -> Optional[str]:
        key = (fam, idx, tuple(used.get(x, 0) for x in FAMILY_SESSIONS.get(fam, ())))
        if key not in cand_cache:
            cand_cache[key] = _candidate(fam, free[idx][2], used)
        return cand_cache[key]

    def _cost_of(fams: Sequence[str]) -> Tuple[int, List[Optional[str]]]:
        """Cost of one pairing, with the catalog weekly caps counted along
        the pairing itself (a family repeated in the pool)."""
        used = dict(used0)
        total = 0
        sids: List[Optional[str]] = []
        for idx, fam in enumerate(fams):
            sid = _pick(fam, idx, used)
            sids.append(sid)
            if sid is None:
                total += PENALTY_NO_SESSION
                continue
            vk = (sid, idx)
            if vk not in viol_cache:
                offset, sn, _si = free[idx]
                viol_cache[vk] = PENALTY_RULE * len(_violations(sid, offset, sn, events, pre))
            total += viol_cache[vk]
            used[sid] = used.get(sid, 0) + 1
        return total, sids

    k = len(free)
    best: Optional[Tuple[str, ...]] = None
    best_sids: List[Optional[str]] = []
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
                c, sids = _cost_of(fams)
                if best_cost is None or c < best_cost:
                    best_cost, best, best_sids = c, fams, sids
                    if c == 0:
                        break
        else:
            best = tuple(pool[:take])
            best_sids = _cost_of(best)[1]

    # Families of the week that found no slot: reported, never dropped silently.
    if best is not None or pool:
        leftover = list(pool)
        for fam in best or ():
            leftover.remove(fam)
        for fam in leftover:
            unmet.append({"date": None, "slot": None, "focus": fam, "reason": "rotation_overflow"})

    assignment: List[Tuple[int, str, Dict[str, Any], Optional[str], Optional[str]]] = []
    for i, (offset, sn, si) in enumerate(free):
        fam = best[i] if best is not None and i < len(best) else None
        sid = best_sids[i] if fam is not None and i < len(best_sids) else None
        assignment.append((offset, sn, si, fam, sid))
    for (offset, sn, si, fam), sid in zip(fixed, fixed_sids):
        assignment.append((offset, sn, si, fam, sid))
    assignment.sort(key=lambda a: (a[0], _SLOTS.index(a[1])))

    added_load = 0
    for offset, sn, si, fam, sid in assignment:
        day = days[offset]
        if fam is None:
            unmet.append({"date": day["date"], "slot": sn, "focus": None,
                          "reason": "no_focus" if not rotation else "rotation_exhausted"})
            continue
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
    # The alerts of the week as the user will see it: engine lunches and the
    # user's own sessions, on the merged week.
    week_plan["secondary_warnings"] = complementary_warnings(
        _effective_view(week_plan, existing_week_plan, today), normalized_full,
        pretrip_dates=pretrip_dates, trip_start_dates=trip_start_dates, next_week_plan=next_week_plan,
    )
    return week_plan


def refresh_secondary_warnings(week_plan: Dict[str, Any], state: Mapping[str, Any]) -> None:
    """Recompute ``secondary_warnings`` of a stored week after the user changed
    it (merge, move, quick-add, key re-schedule…). Only on a week that carries
    the key (a week planned with complementary slots): every other plan is left
    untouched. Never raises."""
    if not isinstance(week_plan, dict) or "secondary_warnings" not in week_plan:
        return
    try:
        from backend.engine.key_sessions_v1 import _effective_availability
        from backend.engine.macrocycle_v1 import compute_taper_windows
        from backend.engine.planner_v2 import _normalize_availability, allowed_locations_for

        ws = str(week_plan.get("start_date"))
        ws_d = date.fromisoformat(ws)
        try:
            locations = list(allowed_locations_for(state.get("equipment") or {}))
        except Exception:
            locations = ["gym", "home"]
        norm = _normalize_availability(_effective_availability(state, ws_d), locations)
        trips = state.get("trips") or []
        we = date.fromordinal(ws_d.toordinal() + 6).isoformat()
        pretrip = compute_taper_windows(trips, ws, we).get("no_hard") or []
        nxt = ((state.get("week_plans") or {}).get(date.fromordinal(ws_d.toordinal() + 7).isoformat()))
        week_plan["secondary_warnings"] = complementary_warnings(
            week_plan, norm, pretrip_dates=pretrip,
            trip_start_dates=trip_start_dates(trips, ws), next_week_plan=nxt,
        )
    except Exception:
        import logging

        logging.getLogger(__name__).warning("A300: secondary warnings refresh failed", exc_info=True)


__all__ = [
    "BICEPS_SESSIONS", "DEFAULT_PHASE_VARIANTS", "DEFAULT_ROTATION", "FAMILY_SESSIONS",
    "FOCUS_FAMILIES", "HIIT_MAX_PER_WEEK", "complementary_warnings", "family_of",
    "place_complementary", "refresh_secondary_warnings", "resolve_rotation", "trip_start_dates",
    "validate_structure",
]
