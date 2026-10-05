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

Since B364 ``anchored_load`` reads the exposure view (re-entry ramp, heavy-pull
guard, finger-hard days) and ``apply_feedback`` writes the registry.

Session exercise rule (one rule, from R3/R7):
- ``actual_exercises`` when present and non-empty (what was logged), else
  ``exercises`` (custom / generated sessions), else the resolved
  ``exercise_instances`` (catalog sessions). Never the union.
- A logged entry counts only if it was actually done: not ``completed: False``,
  not labelled ``skipped``, and with some measure of work. For sessions played
  through the custom/generated player (``is_custom`` or a ``custom_`` /
  ``generated_`` id) the player pre-fills ``completed: true`` and the load even
  for skipped exercises, so ``completed_sets >= 1`` or ``completed_reps >= 1``
  is REQUIRED there. Catalog sessions also accept a logged load.
- A done session with no logged entries contributes its planned exercises
  with ``evidence: "planned"``; logged entries carry ``evidence: "measured"``.
"""

from __future__ import annotations

from datetime import date, datetime
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


def logged_entry_counts(entry: Mapping[str, Any], *, player_session: bool) -> bool:
    """Whether a logged (``actual_exercises``) entry is real work. See module doc."""
    if entry.get("completed") is False:
        return False
    if str(entry.get("feedback_label") or "") == "skipped":
        return False
    sets = _num(entry.get("completed_sets")) or 0
    reps = _num(entry.get("completed_reps")) or 0
    if sets >= 1 or reps >= 1:
        return True
    if player_session:
        return False
    return (
        _num(entry.get("used_total_load_kg")) is not None
        or _num(entry.get("used_external_load_kg")) is not None
    )


def counted_entries(session: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    """``session_exercise_entries`` with the "was it done" rule applied: logged
    entries that are not real work (skipped, not completed, player pre-fill
    with 0 sets/reps) are dropped. Planned entries are returned as they are."""
    entries, origin = session_exercise_entries(session)
    if origin != "actual":
        return entries, origin
    player = _is_player_session(session)
    return [e for e in entries if logged_entry_counts(e, player_session=player)], origin


def session_stimuli(session: Mapping[str, Any]) -> List[str]:
    """Sorted families a session delivers (planned or logged, see the rule)."""
    entries, origin = session_exercise_entries(session)
    fams = set()
    if origin == "none":
        fams.update(SESSION_FALLBACK_STIMULI.get(str(session.get("session_id") or ""), ()))
    else:
        player = _is_player_session(session)
        for e in entries:
            if origin == "actual" and not logged_entry_counts(e, player_session=player):
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


def is_finger_hard_session(session: Mapping[str, Any]) -> bool:
    """A session that loads the fingers hard.

    True when the session is tagged (or catalogued in ``_SESSION_META``) both
    ``finger`` and ``hard``, OR when it delivers a finger_max / limit_power
    stimulus — the second clause is what makes custom sessions visible
    (``_SESSION_META`` has no entry for ``custom_*``) — OR when it carries a
    ``FINGER_FATIGUE_EXTRA_IDS`` hang (min-edge / 10 s max hangs: not a
    finger_max exposure, but a max-intensity finger load all the same).
    """
    if session_flag(session, "finger") and session_flag(session, "hard"):
        return True
    stimuli = session_stimuli(session)
    if FAMILY_FINGER_MAX in stimuli or FAMILY_LIMIT_POWER in stimuli:
        return True
    entries, _origin = counted_entries(session)
    return any(str(e.get("exercise_id") or "") in FINGER_FATIGUE_EXTRA_IDS for e in entries)


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


def iter_plan_sessions(
    state: Mapping[str, Any],
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
) -> Iterable[Tuple[str, Dict[str, Any], str]]:
    """Yield ``(date_iso, session, source)`` over hot + archived week plans.

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
                d = str(day.get("date") or "")[:10]
                if not d:
                    continue
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
                if not logged_entry_counts(e, player_session=player):
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
