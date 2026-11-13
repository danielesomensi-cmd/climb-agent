"""A288 (F0) — the single stimulus-family table and the exposure views.

Why this exists: five train-harder analyses (B364, R2, R3, R5, R7) each
defined "which exercises are a max-finger stimulus" and "how many times did
the athlete get it" in their own way, with different families and different
sources. This module is the one definition every later brief imports.

What it provides (all pure, deterministic, read-only — nothing here writes
state, nothing calls ``date.today()``):

- ``EXERCISE_FAMILY`` / ``stimulus_of(exercise_id)`` — one family per
  exercise, or ``None``.
- ``session_exercise_entries(session)`` / ``session_stimuli(session)`` — the
  exercise list a session really carries, with ONE rule for every caller.
- ``exposures(state, ...)`` — the exposure VIEW: done sessions in the hot
  ``week_plans`` + archived weeks (A221 ``week_archive``, passed in by the
  caller) + free sessions + the persisted registry
  ``progression_counters.stimulus_exposures`` when a later brief (B364)
  starts writing it. Outdoor days are NOT exposures of a family (decision
  2026-10-04: "outdoor near RP counts as finger-hard day only").
- ``exposure_dates`` / ``count_exposures`` — convenience reads over the view.
- ``hard_climb_threshold`` / ``is_hard_climb`` — the single OUTDOOR-HARD rule.
- ``finger_hard_days(state, ...)`` — the single definition of "a day that
  loaded the fingers hard", shared by the retest blockers (A289), the
  key-session validator (A294) and the custom-session guards (A293).

Since B364 ``anchored_load`` reads the exposure view (heavy-pull guard,
finger-hard days; B414 removed the re-entry ramp) and ``apply_feedback`` writes the registry.

Session exercise rule (one rule, from R3/R7):
- ``actual_exercises`` when present and non-empty (what was logged), else
  ``exercises`` (custom / generated sessions), else the resolved
  ``exercise_instances`` (catalog sessions). Never the union.
- A logged entry counts only if it was actually done: ``row_done`` (B414), the
  ONE rule shared with the ladders and the closed loop. Not labelled
  ``skipped``; ``completed: False`` only when the counted sets reach the dose;
  for sessions played through the custom/generated player (``is_custom`` or a
  ``custom_`` / ``generated_`` id) the player pre-fills ``completed: true`` and
  the load even for skipped exercises, so ``completed_sets >= 1`` or
  ``completed_reps >= 1`` is REQUIRED there; a catalog row needs nothing more
  than not being ``completed: False`` (Done without the set timer, the
  post-session dialog), unless it says it counted 0 sets.
- A done session with no logged entries contributes its planned exercises
  with ``evidence: "planned"``; logged entries carry ``evidence: "measured"``.
"""

from __future__ import annotations

import glob
import json
import os
import re
from datetime import date, datetime
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from backend.engine.assessment_v1 import GRADE_ORDER as LEAD_GRADES
from backend.engine.free_session import FONT_GRADES as BOULDER_GRADES

DateLike = Union[date, str]

# ---------------------------------------------------------------------------
# Families
# ---------------------------------------------------------------------------

FAMILY_FINGER_MAX = "finger_max"
FAMILY_PULLING_MAX = "pulling_max"
FAMILY_LIMIT_POWER = "limit_power"
FAMILY_POWER_ENDURANCE = "power_endurance"

FAMILIES: Tuple[str, ...] = (
    FAMILY_FINGER_MAX,
    FAMILY_PULLING_MAX,
    FAMILY_LIMIT_POWER,
    FAMILY_POWER_ENDURANCE,
)

# One family per exercise. Derived from the catalog and pinned by
# test_a288_stimulus.py (every id exists; the catalog rule below reproduces
# the table, so a catalog edit that should move an exercise fails loudly):
#
# - finger_max: domain ``finger_max_strength`` on a defined edge (edge_mm set).
#   EXCLUDES min_edge_hang (bodyweight on the smallest edge: no load, no
#   comparable edge — R3/R5 risk) and max_hang_10s / lp_max_lift_10s (catalog
#   domain is ``finger_strength`` only: a 10 s hang is not a max stimulus).
# - pulling_max: the externally loaded vertical pulls (weighted pull-up /
#   chin-up). Bodyweight pull variants are not a max-pulling stimulus.
# - limit_power: pattern ``climbing_limit_boulder`` (except the warm-up
#   boulders) + ``campus_ladder`` (except campus_sprint_endurance, an
#   anaerobic-capacity drill).
# - power_endurance: domain ``power_endurance``.
_FINGER_MAX_IDS = (
    "max_hang_5s",
    "max_hang_7s",
    "max_hang_ladder",
    "horst_7_53",
    "one_arm_hang_assisted",
    "lp_max_lift_5s",
    "lp_max_lift_7s",
    "lp_short_lifts",
    "lp_max_test_5s",
)
_PULLING_MAX_IDS = ("weighted_pullup", "weighted_chinup")
_LIMIT_POWER_IDS = (
    "limit_bouldering",
    "board_limit_boulders",
    "spray_wall_limit",
    "system_board_limit",
    # C272: library drill (role "library", never engine-selected) — limit
    # bouldering where the feet are the crux; finger-hard like any limit.
    "vertical_small_feet_limit",
    "campus_bumps",
    "campus_double_dyno",
    "campus_laddering_down",
    "campus_laddering_feet_off",
    "campus_laddering_feet_on",
    "campus_max_ladders",
    "campus_switches",
    "campus_touches",
)
_POWER_ENDURANCE_IDS = (
    "four_by_four_bouldering",
    "linked_boulders",
    "linked_boulders_circuit",
    "route_intervals",
    "threshold_climbing",
    "emom_bouldering",
    "otm_bouldering",
    "thirty_thirty_intervals",
    "route_linked_laps",
    "route_on_the_minute",
)

# Finger FATIGUE is wider than the finger_max EXPOSURE family. These hangs are
# deliberately kept out of finger_max (not a comparable max stimulus, see the
# table comment above) but they still load the fingers at max/near-max
# intensity, so a day with one of them IS a finger-hard day for the retest
# blocker and the 48 h finger gap. Used ONLY by ``is_finger_hard_session``.
FINGER_FATIGUE_EXTRA_IDS: Tuple[str, ...] = (
    "min_edge_hang",
    "max_hang_10s",
    "lp_max_lift_10s",
)

# C272 review: library drills (role "library", never engine-selected) that put
# near-limit climbing on the fingers without being a limit_power EXPOSURE.
# ``three_attempt_comp`` is prescribed at boulder flash+1 (6-8 problems x 3
# attempts) — at or above RP-2 for an athlete like Daniele, which is the
# TECH.json finger-hard rule. Rule pinned by test_c272: every library-only
# exercise with ``stress_tags.fingers == "high"`` is finger-hard. Used by
# ``is_finger_hard_session`` and athlete_context's per-session cap only — never
# an exposure, never a family.
FINGER_HARD_LIBRARY_IDS: Tuple[str, ...] = (
    "three_attempt_comp",
)

# A327 (D288, Daniele's answer 4, 2026-11-13): indoor rope redpoint attempts
# are finger-high like a hard crag day — attempts at the redpoint grade are
# above the RP−2 OUTDOOR-HARD rule by definition, and the catalog
# ``route_projecting_gym`` is already finger + hard. A custom built on them
# (D-Summit 25/10) used to count as no finger load at all. Read by
# ``is_finger_hard_session`` (so the weekly finger cap and every finger-hard
# reader see it) and by ``session_tags`` (the B405 rule: finger AND hard on its
# own). NOT read by the composer's pool exclusions (``athlete_context.
# _finger_hard_ids``): A327 adds no restriction to what the composer may pick.
FINGER_HARD_CLIMB_IDS: Tuple[str, ...] = (
    "route_redpoint_attempt",
)

EXERCISE_FAMILY: Dict[str, str] = {
    **{eid: FAMILY_FINGER_MAX for eid in _FINGER_MAX_IDS},
    **{eid: FAMILY_PULLING_MAX for eid in _PULLING_MAX_IDS},
    **{eid: FAMILY_LIMIT_POWER for eid in _LIMIT_POWER_IDS},
    **{eid: FAMILY_POWER_ENDURANCE for eid in _POWER_ENDURANCE_IDS},
}

# Used ONLY when a session carries no exercise list at all (e.g. a done
# catalog session whose resolution was never stored). With an exercise list,
# the exercises decide — a session id never adds a family on top of them.
SESSION_FALLBACK_STIMULI: Dict[str, Tuple[str, ...]] = {
    "strength_long": (FAMILY_FINGER_MAX, FAMILY_PULLING_MAX),
    "finger_strength_home": (FAMILY_FINGER_MAX,),
    "test_max_hang_5s": (FAMILY_FINGER_MAX,),
    "test_max_hang_7s": (FAMILY_FINGER_MAX,),
    "test_lp_max_5s": (FAMILY_FINGER_MAX,),
    "test_max_weighted_pullup": (FAMILY_PULLING_MAX,),
    # A319: the combined test session (max hang 7 s + weighted pull-up 2RM).
    # A planned slot is unresolved: without this row PASS 2.7, the key status
    # and is_pulling_hard_session would not see its pulling side.
    "test_max_hang_pullup": (FAMILY_FINGER_MAX, FAMILY_PULLING_MAX),
    "pulling_strength_gym": (FAMILY_PULLING_MAX,),
    "limit_boulder_gym": (FAMILY_LIMIT_POWER,),
    "power_contact_gym": (FAMILY_LIMIT_POWER,),
    "power_endurance_gym": (FAMILY_POWER_ENDURANCE,),
}


def stimulus_of(exercise_id: Optional[str]) -> Optional[str]:
    """The stimulus family of an exercise, or ``None``."""
    if not exercise_id:
        return None
    return EXERCISE_FAMILY.get(str(exercise_id))


# ---------------------------------------------------------------------------
# Climbing intensity — the single OUTDOOR-HARD rule
# ---------------------------------------------------------------------------

# ENGINEERING CONSTANT (decision 2026-10-04, no published source): a climbing
# attempt at or above (redpoint − 2 grade steps) loads the fingers like a max
# session. Steps are on the engine ladders, '+' grades included: lead 8a+ → 7c+,
# boulder 7C → 7B. Used for outdoor days, free sessions and any other
# "did yesterday's climbing count as a hard finger day" question.
HARD_CLIMB_GRADE_STEPS = 2

# ENGINEERING CONSTANT (decision 2026-10-04): a free boulder session counts as
# a limit_power exposure when at least this many problems were tried at or
# above the hard-climb threshold.
FREE_LIMIT_MIN_PROBLEMS = 2

BOULDER_SURFACES = frozenset({"gym_boulder", "board_kilter", "board_moonboard", "board_other"})

_LEAD_INDEX = {g: i for i, g in enumerate(LEAD_GRADES)}
_BOULDER_INDEX = {g: i for i, g in enumerate(BOULDER_GRADES)}


def _norm_lead(grade: Any) -> Optional[str]:
    if grade is None:
        return None
    g = str(grade).strip().lower().replace(" ", "")
    g = g.split("/")[0]  # "8a/a+" → "8a" (lower bound, the prudent read)
    return g if g in _LEAD_INDEX else None


def _norm_boulder(grade: Any) -> Optional[str]:
    if grade is None:
        return None
    g = str(grade).strip().upper().replace(" ", "")
    g = g.split("/")[0]
    return g if g in _BOULDER_INDEX else None


def redpoint_grade(state: Mapping[str, Any], discipline: str) -> Optional[str]:
    """The athlete's redpoint for ``discipline`` ('lead' | 'boulder'), normalised.

    Reads ``performance.current_level.<sport|boulder>.worked.grade``; falls back
    to ``goal.current_grade`` only when the goal is in the same discipline.
    ``None`` when no usable grade exists — callers must then NOT classify.
    """
    level = ((state.get("performance") or {}).get("current_level") or {})
    goal = state.get("goal") or {}
    if discipline == "lead":
        g = _norm_lead(((level.get("sport") or {}).get("worked") or {}).get("grade"))
        if g is None and goal.get("discipline") == "lead":
            g = _norm_lead(goal.get("current_grade"))
        return g
    if discipline == "boulder":
        g = _norm_boulder(((level.get("boulder") or {}).get("worked") or {}).get("grade"))
        if g is None and goal.get("discipline") == "boulder":
            g = _norm_boulder(goal.get("current_grade"))
        return g
    return None


def hard_climb_threshold(state: Mapping[str, Any], discipline: str) -> Optional[str]:
    """Lowest grade that makes a climb finger-hard: redpoint − 2 steps."""
    rp = redpoint_grade(state, discipline)
    if rp is None:
        return None
    if discipline == "lead":
        return LEAD_GRADES[max(0, _LEAD_INDEX[rp] - HARD_CLIMB_GRADE_STEPS)]
    return BOULDER_GRADES[max(0, _BOULDER_INDEX[rp] - HARD_CLIMB_GRADE_STEPS)]


def is_hard_climb(state: Mapping[str, Any], discipline: str, grade: Any) -> bool:
    """True iff ``grade`` is at or above the hard-climb threshold.

    Unknown grade or unknown redpoint → False (never guess).
    """
    threshold = hard_climb_threshold(state, discipline)
    if threshold is None:
        return False
    if discipline == "lead":
        g = _norm_lead(grade)
        return g is not None and _LEAD_INDEX[g] >= _LEAD_INDEX[threshold]
    g = _norm_boulder(grade)
    return g is not None and _BOULDER_INDEX[g] >= _BOULDER_INDEX[threshold]


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _as_iso(value: DateLike) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _is_player_session(session: Mapping[str, Any]) -> bool:
    """Custom / generated sessions: the player pre-fills completion and load."""
    sid = str(session.get("session_id") or "")
    return bool(session.get("is_custom")) or sid.startswith("custom_") or sid.startswith("generated_")


def is_test_session(session: Mapping[str, Any]) -> bool:
    sid = str(session.get("session_id") or "")
    return sid.startswith("test_") or bool((session.get("tags") or {}).get("test"))


def _resolved_instances(session: Mapping[str, Any]) -> List[Dict[str, Any]]:
    resolved = session.get("resolved")
    if not isinstance(resolved, dict):
        return []
    rs = resolved.get("resolved_session") if isinstance(resolved.get("resolved_session"), dict) else resolved
    inst = rs.get("exercise_instances") if isinstance(rs, dict) else None
    return [i for i in (inst or []) if isinstance(i, dict)]


def session_exercise_entries(session: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    """The exercise list a session carries, and where it came from.

    Returns ``(entries, origin)`` with origin ``"actual"`` (logged),
    ``"planned"`` (custom/generated ``exercises`` or resolved instances) or
    ``"none"``. Never the union of two lists.
    """
    actual = [e for e in (session.get("actual_exercises") or []) if isinstance(e, dict)]
    if actual:
        return actual, "actual"
    planned = [e for e in (session.get("exercises") or []) if isinstance(e, dict)]
    if planned:
        return planned, "planned"
    inst = _resolved_instances(session)
    if inst:
        return inst, "planned"
    return [], "none"


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dose_int(value: Any) -> Optional[int]:
    """First positive integer of a dose value ("4-6" → 4, 8.0 → 8), else None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else None
    try:
        n = int(float(str(value).strip().split("-")[0].strip()))
    except ValueError:
        return None
    return n if n > 0 else None


def row_done(row: Mapping[str, Any], *, player_session: bool,
             dose_sets: Optional[int] = None) -> bool:
    """B414 — THE "was this logged row done" rule, one for every reader.

    A row is a logged ``actual_exercises`` entry or a feedback item (the same
    dict: feedback.py stores the items as they are). Readers: the stimulus
    views (exposures, key sessions, finger-hard days, recency — through
    ``logged_entry_counts`` / ``counted_entries``), the ladders and the closed
    loop's "done and unrated" (``bw_ladders.ladder_row_done``). Rules, in order:

    1. a ``skipped`` label → not done;
    2. ``completed: false`` → done only when the counted sets reach the dose
       (``dose_sets``, else the row's ``prescribed_sets``): a player that saves
       a fully counted row as not completed (4x4 of 03/11) did the work;
    3. ``completed_reps`` >= 1 → done; else counted sets present → done with
       at least one (an explicit 0 is "no set counted": not done);
    4. no counted work in a player session (custom / generated): not done —
       the session-builder player pre-fills ``completed: true`` and the load
       even for skipped exercises;
    5. a catalog session otherwise → done: ``completed: true`` from the guided
       player (Done without the set timer: 1x1 drills, fall practice, timed
       work closed while running), the post-session dialog, or a row with no
       ``completed`` flag at all from a non-app client (coach, API) — the same
       "absent flag = done" ``load_score`` reads. A logged load adds nothing.

    Pure: reads only the row.
    """
    if str(row.get("feedback_label") or "").strip().lower() == "skipped":
        return False
    sets = _num(row.get("completed_sets"))
    if row.get("completed") is False:
        need = dose_sets if dose_sets else _dose_int(row.get("prescribed_sets"))
        return sets is not None and need is not None and sets >= need
    reps = _num(row.get("completed_reps"))
    if reps is not None and reps >= 1:
        return True
    if sets is not None:
        return sets >= 1
    return not player_session


def logged_entry_counts(entry: Mapping[str, Any], *, player_session: bool,
                        dose_sets: Optional[int] = None) -> bool:
    """Whether a logged (``actual_exercises``) entry is real work: ``row_done``
    (B414), with ``dose_sets`` (else the row's own ``prescribed_sets``) as the
    dose of a ``completed: false`` row."""
    return row_done(entry, player_session=player_session, dose_sets=dose_sets)


def planned_sets_of(session: Mapping[str, Any], exercise_id: str) -> Optional[int]:
    """The prescribed sets of ``exercise_id`` in the session's planned list
    (custom / generated ``exercises``, else the resolved instances), or None.

    B414 review: the dose of a logged ``completed: false`` row, looked up the
    way the ladder seed does (``bw_ladders._planned_twin`` + ``_sets_of``), so
    the stimulus views and the seed give the same verdict on the same row."""
    lists = ([e for e in (session.get("exercises") or []) if isinstance(e, Mapping)],
             _resolved_instances(session))
    for planned in lists:
        for e in planned:
            if str(e.get("exercise_id") or "") != exercise_id:
                continue
            for src in (e, e.get("prescription") or {}):
                n = _dose_int(src.get("sets")) if isinstance(src, Mapping) else None
                if n is not None:
                    return n
            return None
    return None


def _session_entry_counts(session: Mapping[str, Any], entry: Mapping[str, Any], *, player_session: bool) -> bool:
    """``logged_entry_counts`` for a logged row of *session*: the dose of a
    ``completed: false`` row is its planned twin's sets (as the ladder seed)."""
    dose = planned_sets_of(session, str(entry.get("exercise_id") or "")) if entry.get("completed") is False else None
    return logged_entry_counts(entry, player_session=player_session, dose_sets=dose)


def counted_entries(session: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    """``session_exercise_entries`` with the "was it done" rule applied
    (``row_done``): logged entries that are not real work (skipped,
    ``completed: false`` short of the dose, player pre-fill with no counted
    set) are dropped. Planned entries are returned as they are."""
    entries, origin = session_exercise_entries(session)
    if origin != "actual":
        return entries, origin
    player = _is_player_session(session)
    return [e for e in entries if _session_entry_counts(session, e, player_session=player)], origin


def session_stimuli(session: Mapping[str, Any]) -> List[str]:
    """Sorted families a session delivers (planned or logged, see the rule)."""
    entries, origin = session_exercise_entries(session)
    fams = set()
    if origin == "none":
        fams.update(SESSION_FALLBACK_STIMULI.get(str(session.get("session_id") or ""), ()))
    else:
        player = _is_player_session(session)
        for e in entries:
            if origin == "actual" and not _session_entry_counts(session, e, player_session=player):
                continue
            fam = stimulus_of(e.get("exercise_id"))
            if fam:
                fams.add(fam)
    return sorted(fams)


def _session_meta(session_id: str) -> Dict[str, Any]:
    # Lazy import: planner_v2 is heavy and later briefs make planner_v2 import
    # the retest policy, which imports this module.
    from backend.engine.planner_v2 import _SESSION_META

    return _SESSION_META.get(session_id) or {}


def session_flag(session: Mapping[str, Any], flag: str) -> bool:
    """A session flag (hard/finger/pulling/...): the session's own ``tags`` win,
    else ``planner_v2._SESSION_META`` (custom sessions have no meta entry)."""
    tags = session.get("tags") or {}
    if flag in tags and tags.get(flag) is not None:
        return bool(tags.get(flag))
    return bool(_session_meta(str(session.get("session_id") or "")).get(flag))


#: A327 (D288 R1): the two finger-load tiers. ``high`` needs the 48 h gap with
#: another ``high`` (unchanged calendar rule); ``low`` (≤ 50 % of max, no
#: failure, ≤ 10 min under load) needs ``retest_policy.FINGER_LOW_GAP_H`` from
#: any finger session, at most ``FINGER_LOW_MAX_PER_DAY`` a day.
FINGER_LOAD_HIGH = "high"
FINGER_LOAD_LOW = "low"
FINGER_LOADS = (FINGER_LOAD_HIGH, FINGER_LOAD_LOW)


def _carries_finger_hard_exercise(session: Mapping[str, Any]) -> bool:
    """The exercise part of the finger-hard rules: a finger_max / limit_power
    stimulus or a finger-hard id among the counted entries."""
    stimuli = session_stimuli(session)
    if FAMILY_FINGER_MAX in stimuli or FAMILY_LIMIT_POWER in stimuli:
        return True
    entries, _origin = counted_entries(session)
    extra = set(FINGER_FATIGUE_EXTRA_IDS) | set(FINGER_HARD_LIBRARY_IDS) | set(FINGER_HARD_CLIMB_IDS)
    return any(str(e.get("exercise_id") or "") in extra for e in entries)


def finger_load_of(session: Mapping[str, Any]) -> Optional[str]:
    """A327 (D288 R1) — THE finger-load tier of a session: ``"high"``,
    ``"low"`` or ``None`` (no finger load). One reading for every consumer
    (guards, athlete context, planner, replanner, key sessions), in order:

    1. the stored ``tags.finger_load`` (customs / generated sessions added
       since A327, ``session_tags.derive_finger_load``);
    2. unless ``tags.finger`` is an explicit False, the catalog
       ``_SESSION_META[session_id].finger_load`` (catalog sessions are read by
       id: the plan does not carry the field);
    3. ``finger`` True (own tags or meta) without a tier → ``high``: a session
       stored before A327 keeps the gap it always had;
    4. a finger-hard exercise despite stale tags (``finger: False`` stored
       before a rule change, e.g. a comp custom of 26/10) → ``high``;
    5. else ``None``.
    """
    tags = session.get("tags") or {}
    stored = tags.get("finger_load")
    if stored in FINGER_LOADS:
        return stored
    explicit_false = "finger" in tags and tags.get("finger") is not None and not bool(tags.get("finger"))
    if not explicit_false:
        meta = _session_meta(str(session.get("session_id") or ""))
        if meta.get("finger") and meta.get("finger_load") in FINGER_LOADS:
            return meta["finger_load"]
    if session_flag(session, "finger"):
        return FINGER_LOAD_HIGH
    if _carries_finger_hard_exercise(session):
        return FINGER_LOAD_HIGH
    return None


def is_finger_high(session: Mapping[str, Any]) -> bool:
    """A327: ``finger_load_of(session) == "high"``."""
    return finger_load_of(session) == FINGER_LOAD_HIGH


def is_finger_hard_session(session: Mapping[str, Any]) -> bool:
    """A session that loads the fingers hard.

    True when the session is tagged (or catalogued in ``_SESSION_META``) both
    ``finger`` and ``hard`` — A327: and its finger load is not ``low`` (a hard
    custom whose finger work is only ramp-ups / easy hangs next to weighted
    pulls is not finger-hard: D288 §1.3-2) — OR when it delivers a finger_max / limit_power
    stimulus — the second clause is what makes custom sessions visible
    (``_SESSION_META`` has no entry for ``custom_*``) — OR when it carries a
    ``FINGER_FATIGUE_EXTRA_IDS`` hang (min-edge / 10 s max hangs: not a
    finger_max exposure, but a max-intensity finger load all the same) OR a
    ``FINGER_HARD_LIBRARY_IDS`` drill (near-limit comp bouldering, C272) OR a
    ``FINGER_HARD_CLIMB_IDS`` exercise (indoor redpoint attempts, A327).
    """
    if (session_flag(session, "finger") and session_flag(session, "hard")
            and finger_load_of(session) != FINGER_LOAD_LOW):
        return True
    return _carries_finger_hard_exercise(session)


def is_finger_hard_exposure(session: Mapping[str, Any]) -> bool:
    """A327 (D288 R1): a session that is one of the week's finger-hard
    EXPOSURES — the unit of the weekly finger cap
    (``retest_policy.FINGER_HARD_WEEKLY_MAX``, crag days added by the caller).

    The exercises decide when the session carries a list (logged, custom /
    generated, resolved): a finger_max or limit_power stimulus, or a
    ``FINGER_FATIGUE_EXTRA_IDS`` / ``FINGER_HARD_LIBRARY_IDS`` /
    ``FINGER_HARD_CLIMB_IDS`` exercise (max / test hangs, limit, board,
    campus, ``three_attempt_comp``, indoor redpoint attempts). A session
    without a list (a planned catalog slot) falls back on its flags: finger
    AND hard (``_SESSION_META`` or own tags).

    Narrower than ``is_finger_hard_session`` on purpose: a session finger +
    hard only through its tags — repeaters or intermittent hangs at 60-80 %
    to failure, a ramp-up next to weighted pulls — is high for the 48 h
    spacing but not an exposure of the cap (Daniele, answer 2, 2026-11-13).
    """
    _entries, origin = counted_entries(session)
    if origin == "none" and not session_stimuli(session):
        return (session_flag(session, "finger") and session_flag(session, "hard")
                and finger_load_of(session) != FINGER_LOAD_LOW)
    return _carries_finger_hard_exercise(session)


def is_max_hang_session(session: Mapping[str, Any]) -> bool:
    """A327 (D288 R1): a session that delivers the finger_max family — max
    hangs, the max-hang tests (``SESSION_FALLBACK_STIMULI`` when unresolved:
    ``strength_long``, ``finger_strength_home``, ``test_max_hang_*``,
    ``test_lp_max_5s``, ``test_max_hang_pullup``). The unit of the weekly
    max-hang cap (``retest_policy.MAX_HANG_WEEKLY_MAX``)."""
    return FAMILY_FINGER_MAX in session_stimuli(session)


# ---------------------------------------------------------------------------
# C274: HIIT — the one entry point
# ---------------------------------------------------------------------------
#
# The HIIT flag lives in the session CATALOG (``tags.hiit`` of the session
# JSON), not in ``_SESSION_META`` and not in the plan slot tags (the planner
# and ``apply_day_add`` copy only hard/finger/test). So ``session_flag(s,
# "hiit")`` is NOT the API: it returns False for ``treadmill_hiit_4x4``.
# Every consumer (A300 weekly cap, deload → Z2, "never next to a max day"
# alert) must call :func:`is_hiit_session`.

HIIT_RECENCY_GROUP = "conditioning_hiit"

_CATALOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "catalog",
)


@lru_cache(maxsize=1)
def _hiit_catalog_session_ids() -> frozenset:
    out = set()
    for path in sorted(glob.glob(os.path.join(_CATALOG_DIR, "sessions", "v1", "*.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and (data.get("tags") or {}).get("hiit") is True:
            out.add(str(data.get("id") or os.path.splitext(os.path.basename(path))[0]))
    return frozenset(out)


@lru_cache(maxsize=1)
def _hiit_exercise_ids() -> frozenset:
    with open(os.path.join(_CATALOG_DIR, "exercises", "v1", "exercises.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    items = data.get("exercises") if isinstance(data, dict) else data
    return frozenset(
        str(e.get("id")) for e in items or []
        if isinstance(e, dict) and e.get("recency_group") == HIIT_RECENCY_GROUP
    )


def is_hiit_session(session: Mapping[str, Any]) -> bool:
    """True when a session is a HIIT session (C274).

    Rules, first match wins:
    1. an explicit ``tags.hiit`` on the slot/session (not None) — lets a later
       brief tag a slot, including ``False`` for a deload Z2 swap;
    2. the catalog session JSON carries ``tags.hiit: true`` (by ``session_id``);
    3. the session carries (planned or logged) an exercise whose catalog
       ``recency_group`` is ``conditioning_hiit`` — this is what makes custom,
       ad-hoc and generated sessions visible.
    Pure and deterministic; reads only the catalog files.
    """
    tags = session.get("tags") or {}
    if isinstance(tags, Mapping) and tags.get("hiit") is not None:
        return bool(tags.get("hiit"))
    if str(session.get("session_id") or "") in _hiit_catalog_session_ids():
        return True
    entries, _origin = counted_entries(session)
    hiit_ids = _hiit_exercise_ids()
    return any(str(e.get("exercise_id") or "") in hiit_ids for e in entries)


# A300: the name regex athlete_context used before C274. Kept ONLY as a
# fallback for legacy custom sessions that carry no catalog session id, no
# ``tags.hiit`` and no ``conditioning_hiit`` exercise (e.g. a hand-written
# "Work — HIIT" custom). Never consulted when the session states its own
# ``tags.hiit`` (True or False).
_LEGACY_HIIT_NAME_RE = re.compile(r"\b(HIIT|VO2)", re.IGNORECASE)


def is_hiit_like(session: Mapping[str, Any]) -> bool:
    """:func:`is_hiit_session`, plus the legacy name fallback for customs.

    The one predicate the planner's complementary pass (A300) and
    ``athlete_context`` share, so the app and the script never disagree.
    """
    if is_hiit_session(session):
        return True
    tags = session.get("tags") or {}
    if isinstance(tags, Mapping) and tags.get("hiit") is not None:
        return False
    return bool(_LEGACY_HIIT_NAME_RE.search(str(session.get("name") or "")))


def is_pulling_hard_session(session: Mapping[str, Any]) -> bool:
    """A session tagged/catalogued ``pulling`` + ``hard``, or delivering pulling_max.

    This is the label-level half of "heavy pulling" (decision 2026-10-04). The
    load-level half (weighted pull ≥ 85 % of the official 1RM) needs the
    official max and lives in ``retest_policy.is_heavy_pulling_session``.
    Note: ``power_endurance_gym`` is catalogued ``pulling: True, hard: True``,
    so it IS pulling-hard under this rule.
    """
    if session_flag(session, "pulling") and session_flag(session, "hard"):
        return True
    return FAMILY_PULLING_MAX in session_stimuli(session)


def is_max_for_hiit(session: Mapping[str, Any]) -> bool:
    """A max session a HIIT must not come right before (B405): finger-hard or pulling max.

    Not ``is_pulling_hard_session``: its ``pulling + hard`` label also catches
    ``power_endurance_gym`` (intensity high, no max stimulus), and with power
    endurance twice a week that left the 4x4 one free lunch (Daniele, 25/10).
    """
    return is_finger_hard_session(session) or FAMILY_PULLING_MAX in session_stimuli(session)


# ---------------------------------------------------------------------------
# Week-plan iteration
# ---------------------------------------------------------------------------

def _normalise_archive(
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]],
) -> Dict[str, Dict[str, Any]]:
    """Accept ``{week_start: plan}`` (storage reader) or ``[{week_start, plan}]`` rows."""
    out: Dict[str, Dict[str, Any]] = {}
    if not archived_weeks:
        return out
    if isinstance(archived_weeks, Mapping):
        for k, v in archived_weeks.items():
            if isinstance(v, dict):
                out[str(k)] = v
        return out
    for row in archived_weeks:
        if isinstance(row, Mapping) and isinstance(row.get("plan"), dict) and row.get("week_start"):
            out[str(row["week_start"])] = row["plan"]
    return out


def iter_plan_days(
    state: Mapping[str, Any],
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
) -> Iterable[Tuple[str, Dict[str, Any], str]]:
    """Yield ``(date_iso, day, source)`` over hot + archived week plans.

    ``source`` is ``"week_plan"`` or ``"archive"``. A week present both hot and
    archived is read from the hot copy only. ``current_week_plan`` is read only
    when its week is not already in ``week_plans``. Deterministic order.
    """
    plans: Dict[str, Tuple[Dict[str, Any], str]] = {}
    for k, v in _normalise_archive(archived_weeks).items():
        plans[k] = (v, "archive")
    for k, v in (state.get("week_plans") or {}).items():
        if isinstance(v, dict):
            plans[str(k)] = (v, "week_plan")
    cur = state.get("current_week_plan")
    if isinstance(cur, dict):
        key = str(cur.get("start_date") or "")
        if key and key not in plans:
            plans[key] = (cur, "week_plan")
    for key in sorted(plans):
        plan, source = plans[key]
        for week in plan.get("weeks") or []:
            for day in week.get("days") or []:
                if not isinstance(day, dict):
                    continue
                d = str(day.get("date") or "")[:10]
                if not d:
                    continue
                yield d, day, source


def iter_plan_sessions(
    state: Mapping[str, Any],
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
) -> Iterable[Tuple[str, Dict[str, Any], str]]:
    """Yield ``(date_iso, session, source)`` over hot + archived week plans
    (the days of ``iter_plan_days``, same order and sources)."""
    for d, day, source in iter_plan_days(state, archived_weeks):
        for session in day.get("sessions") or []:
            if isinstance(session, dict):
                yield d, session, source


# ---------------------------------------------------------------------------
# Exposure view
# ---------------------------------------------------------------------------

def _in_window(d: str, since: Optional[str], until: Optional[str]) -> bool:
    if since is not None and d < since:
        return False
    if until is not None and d > until:
        return False
    return True


def _registry_entries(state: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Entries of the persisted registry ``progression_counters.stimulus_exposures``.

    Nobody writes it yet (B364 will). Accepted shapes per family: a list of
    ISO dates or of dicts with at least ``date``.
    """
    reg = ((state.get("progression_counters") or {}).get("stimulus_exposures") or {})
    out: List[Dict[str, Any]] = []
    if not isinstance(reg, Mapping):
        return out
    for fam, items in reg.items():
        if fam not in FAMILIES or not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, str):
                out.append({"date": it[:10], "family": fam})
            elif isinstance(it, Mapping) and it.get("date"):
                row = dict(it)
                row["date"] = str(row["date"])[:10]
                row["family"] = fam
                out.append(row)
    return out


def exposures(
    state: Mapping[str, Any],
    *,
    since: Optional[DateLike] = None,
    until: Optional[DateLike] = None,
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
    families: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """All stimulus exposures in ``[since, until]`` (inclusive), sorted.

    Each row::

        {date, family, exercise_id, session_id, source, evidence, is_test,
         sets_done, sets_prescribed, used_total_load_kg, used_external_load_kg}

    ``source`` ∈ week_plan | archive | free | limit_log | registry (A296). ``evidence`` ∈
    measured | planned. Only ``status == "done"`` sessions count. Rows are
    de-duplicated on (date, family, exercise_id); a registry row is dropped
    when a derived row already covers the same (date, family).
    """
    s_iso = _as_iso(since) if since is not None else None
    u_iso = _as_iso(until) if until is not None else None
    fam_filter = set(families) if families is not None else None
    rows: List[Dict[str, Any]] = []

    for d, session, source in iter_plan_sessions(state, archived_weeks):
        if session.get("status") != "done" or not _in_window(d, s_iso, u_iso):
            continue
        entries, origin = session_exercise_entries(session)
        sid = session.get("session_id")
        test = is_test_session(session)
        if origin == "none":
            for fam in SESSION_FALLBACK_STIMULI.get(str(sid or ""), ()):
                rows.append({
                    "date": d, "family": fam, "exercise_id": None, "session_id": sid,
                    "source": source, "evidence": "planned", "is_test": test,
                    "sets_done": None, "sets_prescribed": None,
                    "used_total_load_kg": None, "used_external_load_kg": None,
                })
            continue
        player = _is_player_session(session)
        for e in entries:
            fam = stimulus_of(e.get("exercise_id"))
            if not fam:
                continue
            if origin == "actual":
                if not _session_entry_counts(session, e, player_session=player):
                    continue
                evidence = "measured"
                sets_done = _num(e.get("completed_sets"))
                sets_presc = _num(e.get("prescribed_sets"))
            else:
                evidence = "planned"
                sets_done = None
                sets_presc = _num(e.get("sets")) or _num((e.get("prescription") or {}).get("sets"))
            rows.append({
                "date": d, "family": fam, "exercise_id": e.get("exercise_id"), "session_id": sid,
                "source": source, "evidence": evidence, "is_test": test,
                "sets_done": int(sets_done) if sets_done is not None else None,
                "sets_prescribed": int(sets_presc) if sets_presc is not None else None,
                "used_total_load_kg": _num(e.get("used_total_load_kg")),
                "used_external_load_kg": _num(e.get("used_external_load_kg")),
            })

    # Free sessions: a boulder session with ≥ FREE_LIMIT_MIN_PROBLEMS climbs at
    # or above the hard-climb threshold is a limit_power exposure. Lead free
    # sessions are not classified (their grades are validated on the Font
    # scale, so a lead grade cannot be read honestly here).
    # Only FINISHED free sessions count, like plan sessions only count when
    # done: the router appends the session at /start with ``finished_at: None``.
    # A row without the key at all (legacy shape) is read as finished.
    # A296: a free session finished after A296 carries ``limit_session`` (the
    # decision taken at finish against the LIMIT TARGET, or the toggle) — its
    # exposure comes from the limit log below, not from this legacy rule.
    for fs in state.get("free_sessions") or []:
        if not isinstance(fs, Mapping):
            continue
        if "finished_at" in fs and fs.get("finished_at") is None:
            continue
        if isinstance(fs.get("limit_session"), Mapping):
            continue
        d = str(fs.get("date") or "")[:10]
        if not d or not _in_window(d, s_iso, u_iso):
            continue
        if fs.get("surface") not in BOULDER_SURFACES:
            continue
        hard = [c for c in (fs.get("climbs") or []) if isinstance(c, Mapping)
                and is_hard_climb(state, "boulder", c.get("grade"))]
        if len(hard) >= FREE_LIMIT_MIN_PROBLEMS:
            rows.append({
                "date": d, "family": FAMILY_LIMIT_POWER, "exercise_id": None,
                "session_id": fs.get("id"), "source": "free", "evidence": "measured",
                "is_test": False, "sets_done": len(hard), "sets_prescribed": None,
                "used_total_load_kg": None, "used_external_load_kg": None,
            })

    # A296: the limit log. A free entry (written only when the session
    # counted) IS the free limit_power exposure, ``source: "free"`` like the
    # legacy rule. A planned / custom / adhoc entry with logged problems is a
    # fallback source (``source: "limit_log"``), dropped below when the week
    # plan already covers that day — e.g. when the caller passes no archive.
    free_ids = {str(fs.get("id")) for fs in (state.get("free_sessions") or []) if isinstance(fs, Mapping)}
    for e in state.get("limit_log") or []:
        if not isinstance(e, Mapping):
            continue
        d = str(e.get("date") or "")[:10]
        if not d or not _in_window(d, s_iso, u_iso):
            continue
        if e.get("source") == "free":
            if str(e.get("session_id")) not in free_ids:
                continue  # the free session was deleted
            rows.append({
                "date": d, "family": FAMILY_LIMIT_POWER, "exercise_id": None,
                "session_id": e.get("session_id"), "source": "free", "evidence": "measured",
                "is_test": False, "sets_done": e.get("qualifying"), "sets_prescribed": None,
                "used_total_load_kg": None, "used_external_load_kg": None,
            })
    seen = {(r["date"], r["family"], r["exercise_id"]) for r in rows}
    covered = {(r["date"], r["family"]) for r in rows}
    for e in state.get("limit_log") or []:
        if not isinstance(e, Mapping) or e.get("source") == "free" or not e.get("problems"):
            continue
        d = str(e.get("date") or "")[:10]
        if not d or not _in_window(d, s_iso, u_iso) or (d, FAMILY_LIMIT_POWER) in covered:
            continue
        if stimulus_of(e.get("exercise_id")) != FAMILY_LIMIT_POWER:
            continue
        covered.add((d, FAMILY_LIMIT_POWER))
        seen.add((d, FAMILY_LIMIT_POWER, e.get("exercise_id")))
        rows.append({
            "date": d, "family": FAMILY_LIMIT_POWER, "exercise_id": e.get("exercise_id"),
            "session_id": e.get("session_id"), "source": "limit_log", "evidence": "measured",
            "is_test": False, "sets_done": len(e.get("problems") or []), "sets_prescribed": None,
            "used_total_load_kg": None, "used_external_load_kg": None,
        })
    for r in _registry_entries(state):
        if not _in_window(r["date"], s_iso, u_iso):
            continue
        key = (r["date"], r["family"], r.get("exercise_id"))
        if key in seen or (r["date"], r["family"]) in covered:
            continue
        seen.add(key)
        rows.append({
            "date": r["date"], "family": r["family"], "exercise_id": r.get("exercise_id"),
            "session_id": r.get("session_id"), "source": "registry",
            "evidence": r.get("evidence") or "measured", "is_test": bool(r.get("is_test")),
            "sets_done": r.get("sets_done"), "sets_prescribed": r.get("sets_prescribed"),
            "used_total_load_kg": _num(r.get("total_kg") if r.get("total_kg") is not None else r.get("used_total_load_kg")),
            "used_external_load_kg": _num(r.get("used_external_load_kg")),
        })

    # De-duplicate derived rows on (date, family, exercise_id): keep the first
    # (hot week plans sort after archive per week key, but a week is only read
    # from one source, so duplicates here come from repeated entries).
    unique: Dict[Tuple[str, str, Optional[str]], Dict[str, Any]] = {}
    for r in rows:
        if fam_filter is not None and r["family"] not in fam_filter:
            continue
        unique.setdefault((r["date"], r["family"], r["exercise_id"]), r)
    return sorted(
        unique.values(),
        key=lambda r: (r["date"], r["family"], str(r["exercise_id"] or ""), str(r["session_id"] or "")),
    )


def exposure_dates(
    state: Mapping[str, Any],
    family: str,
    *,
    since: Optional[DateLike] = None,
    until: Optional[DateLike] = None,
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
) -> List[str]:
    """Sorted distinct days with at least one ``family`` exposure (tests included)."""
    return sorted({
        r["date"] for r in exposures(
            state, since=since, until=until, archived_weeks=archived_weeks, families=[family]
        )
    })


def count_exposures(
    state: Mapping[str, Any],
    family: str,
    *,
    since: DateLike,
    until: DateLike,
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
) -> int:
    """Number of distinct exposure DAYS for ``family`` in ``[since, until]``.

    One day = one exposure: two finger_max exercises in the same session (or
    two sessions the same day) are one exposure.
    """
    return len(exposure_dates(state, family, since=since, until=until, archived_weeks=archived_weeks))


# ---------------------------------------------------------------------------
# Hard-day views
# ---------------------------------------------------------------------------

def _outdoor_entries(
    state: Mapping[str, Any], outdoor_rows: Optional[Sequence[Mapping[str, Any]]]
) -> List[Mapping[str, Any]]:
    """Outdoor entries with routes: caller rows (``outdoor_logs`` table, either
    raw entries or ``{"entry": ...}`` wrappers) + ``state.outdoor_log`` entries
    that carry routes. One entry per (date, spot)."""
    out: List[Mapping[str, Any]] = []
    for row in list(outdoor_rows or []) + list(state.get("outdoor_log") or []):
        if not isinstance(row, Mapping):
            continue
        entry = row.get("entry") if isinstance(row.get("entry"), Mapping) else row
        if entry.get("date") and entry.get("routes"):
            out.append(entry)
    seen = set()
    unique = []
    for e in out:
        key = (str(e.get("date"))[:10], str(e.get("spot_id") or e.get("spot_name") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    return unique


def _route_discipline(route: Mapping[str, Any], entry_discipline: str) -> str:
    """'boulder' | 'lead' for one outdoor route.

    The route's own discipline wins, then an explicit entry discipline
    ('lead' / 'boulder'). When neither decides (entry 'both' — the router's
    default — or missing), the grade scale does: an uppercase Font letter
    (7B+) is boulder, a lowercase French letter (7b+) is lead. Without this a
    Font grade would be lowercased into a lead grade and judged on the wrong
    ladder.
    """
    for disc in (route.get("discipline"), entry_discipline):
        if disc in ("lead", "boulder"):
            return str(disc)
    raw = str(route.get("grade") or "").split("/")[0]
    if any(ch in "ABC" for ch in raw):
        return "boulder"
    return "lead"


def outdoor_hard_days(
    state: Mapping[str, Any],
    *,
    since: Optional[DateLike] = None,
    until: Optional[DateLike] = None,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Outdoor days with at least one route attempted at/above the hard-climb
    threshold of its discipline. One row per day: ``{date, source:"outdoor",
    discipline, grade, route}`` (the hardest qualifying route)."""
    s_iso = _as_iso(since) if since is not None else None
    u_iso = _as_iso(until) if until is not None else None
    best: Dict[str, Dict[str, Any]] = {}
    for entry in _outdoor_entries(state, outdoor_rows):
        d = str(entry.get("date"))[:10]
        if not _in_window(d, s_iso, u_iso):
            continue
        disc_entry = str(entry.get("discipline") or "")
        for route in entry.get("routes") or []:
            if not isinstance(route, Mapping):
                continue
            disc = _route_discipline(route, disc_entry)
            if not is_hard_climb(state, disc, route.get("grade")):
                continue
            ladder = _LEAD_INDEX if disc == "lead" else _BOULDER_INDEX
            g = _norm_lead(route.get("grade")) if disc == "lead" else _norm_boulder(route.get("grade"))
            cur = best.get(d)
            rank = ladder[g] - ladder[hard_climb_threshold(state, disc)]
            if cur is None or rank > cur["_rank"]:
                best[d] = {"date": d, "source": "outdoor", "discipline": disc,
                           "grade": g, "route": route.get("name"), "_rank": rank}
    for v in best.values():
        v.pop("_rank", None)
    return [best[d] for d in sorted(best)]


def finger_hard_days(
    state: Mapping[str, Any],
    *,
    since: Optional[DateLike] = None,
    until: Optional[DateLike] = None,
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    include_planned: bool = False,
) -> List[Dict[str, Any]]:
    """The single definition of "a day that loaded the fingers hard".

    One row per (date, reason source): ``{date, source, session_id, reason}``
    where source ∈ week_plan | archive | outdoor | free and reason ∈
    ``finger_hard_session`` | ``outdoor_hard`` | ``free_limit``.

    - Sessions: done ones; with ``include_planned=True`` also the not-yet-done
      ones (status not done/skipped), for scheduling questions about the
      future. A skipped session never counts.
    - Tests count (they are tagged finger+hard).
    - Outdoor: the OUTDOOR-HARD rule. Free sessions: the free-limit rule.
    """
    s_iso = _as_iso(since) if since is not None else None
    u_iso = _as_iso(until) if until is not None else None
    rows: List[Dict[str, Any]] = []
    for d, session, source in iter_plan_sessions(state, archived_weeks):
        if not _in_window(d, s_iso, u_iso):
            continue
        status = session.get("status")
        if status == "skipped":
            continue
        if status != "done" and not include_planned:
            continue
        if is_finger_hard_session(session):
            rows.append({"date": d, "source": source, "session_id": session.get("session_id"),
                         "reason": "finger_hard_session", "status": status or "planned"})
    for o in outdoor_hard_days(state, since=since, until=until, outdoor_rows=outdoor_rows):
        rows.append({"date": o["date"], "source": "outdoor", "session_id": None,
                     "reason": "outdoor_hard", "status": "done"})
    free_rows = set()
    for r in exposures(state, since=since, until=until, families=[FAMILY_LIMIT_POWER]):
        if r["source"] == "free":
            free_rows.add(str(r["session_id"]))
            rows.append({"date": r["date"], "source": "free", "session_id": r["session_id"],
                         "reason": "free_limit", "status": "done"})
    # A296: a free session decided by the limit log that did NOT count as a
    # limit session still loaded the fingers hard when it had ≥ 2 climbs at the
    # OUTDOOR-HARD threshold — fatigue is not the same question as "was it the
    # limit stimulus". Same rule the exposure view applied before A296.
    for fs in state.get("free_sessions") or []:
        if not isinstance(fs, Mapping) or not isinstance(fs.get("limit_session"), Mapping):
            continue
        if str(fs.get("id")) in free_rows or fs.get("finished_at") is None and "finished_at" in fs:
            continue
        d = str(fs.get("date") or "")[:10]
        if not d or not _in_window(d, s_iso, u_iso) or fs.get("surface") not in BOULDER_SURFACES:
            continue
        hard = [c for c in (fs.get("climbs") or []) if isinstance(c, Mapping)
                and is_hard_climb(state, "boulder", c.get("grade"))]
        if len(hard) >= FREE_LIMIT_MIN_PROBLEMS:
            rows.append({"date": d, "source": "free", "session_id": fs.get("id"),
                         "reason": "free_limit", "status": "done"})
    return sorted(rows, key=lambda r: (r["date"], r["source"], str(r["session_id"] or "")))


# ---------------------------------------------------------------------------
# B372 — outdoor days in the fatigue alerts
# ---------------------------------------------------------------------------

OUTDOOR_REASON_PLANNED = "outdoor_planned"
OUTDOOR_REASON_HARD = "outdoor_hard"
OUTDOOR_REASON_LOAD = "outdoor_load"
OUTDOOR_REASON_UNLOGGED = "outdoor_unlogged"


def is_outdoor_day(day: Mapping[str, Any]) -> bool:
    """A plan day the athlete climbs outside: the planner's ``outdoor_slot``
    (an outdoor-only availability day) or the day-level outdoor block a user
    set on the plan (override / ``set_outdoor_plan`` / ``complete_outdoor``)."""
    if not isinstance(day, Mapping):
        return False
    return bool(
        day.get("outdoor_slot") or day.get("outdoor_spot_name") or day.get("outdoor_spot_id")
        or day.get("outdoor_plan") or day.get("outdoor_session_status") in ("planned", "done")
    )


def is_declared_outdoor_day(day: Mapping[str, Any]) -> bool:
    """B372: an outdoor day the USER put on the plan (spot, pitch ladder, an
    outdoor block planned / done) — never the planner's bare ``outdoor_slot``.
    B379: the predicate lives in ``user_owned`` (shared with the merge, the
    planner, the complementary pass and the retest policy); this delegates."""
    from backend.engine.user_owned import is_declared_outdoor_day as _declared
    return _declared(day)


def _outdoor_logged_loads(
    state: Mapping[str, Any], outdoor_rows: Optional[Sequence[Mapping[str, Any]]],
) -> Dict[str, float]:
    """Logged ``load_score`` per date (``outdoor_logs`` rows +
    ``state.outdoor_log``): the SUM over the day's distinct (date, spot)
    entries, the day total B341 defines for a multi-crag day (a copy of the
    same entry in both sources counts once, rows first)."""
    out: Dict[str, float] = {}
    seen = set()
    for row in list(outdoor_rows or []) + list(state.get("outdoor_log") or []):
        if not isinstance(row, Mapping):
            continue
        entry = row.get("entry") if isinstance(row.get("entry"), Mapping) else row
        d = str(entry.get("date") or "")[:10]
        v = _num(entry.get("load_score"))
        if not d or v is None:
            continue
        key = (d, str(entry.get("spot_id") or entry.get("spot_name") or ""))
        if key in seen:
            continue
        seen.add(key)
        out[d] = out.get(d, 0.0) + v
    return out


def _route_measurable(state: Mapping[str, Any], route: Mapping[str, Any], entry_discipline: str) -> bool:
    """A logged route the OUTDOOR-HARD rule can judge: its discipline has a
    threshold (the athlete has a redpoint there) AND its grade sits on that
    discipline's ladder. A '?' or a typo is unknown, not easy."""
    disc = _route_discipline(route, entry_discipline)
    if hard_climb_threshold(state, disc) is None:
        return False
    g = _norm_lead(route.get("grade")) if disc == "lead" else _norm_boulder(route.get("grade"))
    return g is not None


def outdoor_fatigue_days(
    state: Mapping[str, Any],
    days: Iterable[Mapping[str, Any]],
    *,
    load_threshold: float,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    since: Optional[DateLike] = None,
    until: Optional[DateLike] = None,
    today: Optional[DateLike] = None,
) -> Dict[str, Dict[str, Any]]:
    """B372 — the outdoor days that count as a hard, finger-loading day for the
    fatigue ALERTS (``guards_v1``, ``athlete_context`` guards). Never used to
    rewrite a plan.

    ``{date: {date, status, reason, spot, load, grade, route}}``, sorted by date.
    A day counts when, first rule that applies:

    - ``outdoor_hard``: the log (``outdoor_rows`` / ``state.outdoor_log``) has
      a route at/above the OUTDOOR-HARD threshold (``outdoor_hard_days``) —
      also a logged day with no outdoor block on the plan;
    - ``outdoor_load``: its load (day ``outdoor_load_score`` or the logged
      ``load_score``, summed over the day's crags) reaches ``load_threshold``
      (the replanner's ``OUTDOOR_RIPPLE_THRESHOLD``) — also a logged day with
      no block;
    - a day whose log carries routes, all gradable and none hard, below the
      load threshold, does NOT count: an easy day out, measured;
    - ``outdoor_unlogged``: a completed outdoor day of the plan whose routes are
      unknown (not logged, not passed in, or ungradable) — counts,
      conservatively: a day at the crag loads the fingers until the log says
      otherwise;
    - ``outdoor_planned``: an outdoor day the user declared
      (``is_declared_outdoor_day``) and has not completed yet, on or after
      *today* (``None`` = every date): counts, its intensity is not known
      before the day. A declared day already past, never completed and never
      logged, does not count — the athlete did not go.

    A bare planner ``outdoor_slot`` is availability, not a crag day: it counts
    only through its log (hard / load), like a day with no block.

    *days*: plan days (any iterable, later copies of a date win). Pure and
    deterministic.
    """
    t_iso = _as_iso(today) if today is not None else None
    s_iso = _as_iso(since) if since is not None else None
    u_iso = _as_iso(until) if until is not None else None
    hard = {o["date"]: o for o in outdoor_hard_days(state, since=since, until=until, outdoor_rows=outdoor_rows)}
    # A day is "measured" only when every route of its log can be classified
    # (the athlete has a redpoint in that discipline): without a threshold an
    # 8a is not "easy", it is unknown.
    with_routes = {
        str(e.get("date"))[:10] for e in _outdoor_entries(state, outdoor_rows)
        if all(_route_measurable(state, r, str(e.get("discipline") or ""))
               for r in e.get("routes") or [] if isinstance(r, Mapping))
    }
    logged_load = _outdoor_logged_loads(state, outdoor_rows)
    by_date: Dict[str, Mapping[str, Any]] = {}
    for day in days or []:
        if not is_declared_outdoor_day(day):
            continue
        d = str(day.get("date") or "")[:10]
        if d and _in_window(d, s_iso, u_iso):
            by_date[d] = day

    out: Dict[str, Dict[str, Any]] = {}

    def _row(d: str, status: str, reason: str, spot: Any, load: Optional[float]) -> Dict[str, Any]:
        h = hard.get(d) or {}
        return {"date": d, "status": status, "reason": reason, "spot": spot,
                "load": int(load) if load is not None else None,
                "grade": h.get("grade"), "route": h.get("route")}

    for d in sorted(by_date):
        day = by_date[d]
        loads = [v for v in (_num(day.get("outdoor_load_score")), logged_load.get(d)) if v is not None]
        load = max(loads) if loads else None
        done = day.get("outdoor_session_status") == "done"
        spot = day.get("outdoor_spot_name")
        if d in hard:
            out[d] = _row(d, "done", OUTDOOR_REASON_HARD, spot, load)
        elif load is not None and load >= load_threshold and (done or d in logged_load):
            out[d] = _row(d, "done", OUTDOOR_REASON_LOAD, spot, load)
        elif d in with_routes:
            continue  # logged, measured easy
        elif done:
            out[d] = _row(d, "done", OUTDOOR_REASON_UNLOGGED, spot, load)
        elif t_iso is None or d >= t_iso:
            out[d] = _row(d, "planned", OUTDOOR_REASON_PLANNED, spot, load)
    for d, h in hard.items():
        if d not in out:
            out[d] = _row(d, "done", OUTDOOR_REASON_HARD, None, logged_load.get(d))
    for d, v in logged_load.items():
        if d not in out and v >= load_threshold and _in_window(d, s_iso, u_iso):
            out[d] = _row(d, "done", OUTDOOR_REASON_LOAD, None, v)
    return {d: out[d] for d in sorted(out)}
