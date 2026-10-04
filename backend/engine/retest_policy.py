"""A288 (F0) — read-only primitives of the retest policy.

Four train-harder analyses read "the athlete's max" four different ways
(persisted baselines before/after ``estimate_missing_baselines``, ``tests.*``
only, the same-duration test even when it is 6 months old, a stored
``confidence`` that measures nothing). This module is the one reading.

Primitives (pure, deterministic, never write state, never ``date.today()``):

- ``official_max(state, protocol, as_of)`` — the official max for a test
  protocol on a date: the FRESHEST test ≤ ``as_of``. Hang protocols convert
  between durations with ``HANG_PCT_PER_S`` (a 5 s max comes from the
  freshest 7 s test, never from a > 90-day 5 s test). Official max =
  tests/baselines, which only test logs write; feedback never does.
- ``is_tested(...)`` — the gate every "train harder" rule uses: source
  test/test_session and younger than ``TEST_FRESH_DAYS``. Untested users keep
  today's behaviour bit for bit.
- ``test_confidence(state, test, archived_weeks=...)`` — computed, never read
  from the stored ``confidence`` field: low when the athlete had fewer than
  ``LOW_CONF_MIN_EXPOSURES`` exposure days of the same family in the
  ``LOW_CONF_WINDOW_D`` days before the test. Needs the archived weeks
  (A221 moves past weeks to ``week_archive``): pass them, or the count is an
  under-estimate.
- ``reentry_step(state, family, as_of, archived_weeks=...)`` — the single
  re-entry ramp: n exposures since the last gap ≥ ``REENTRY_GAP_D`` days,
  counting the session being prescribed; factor 0.90 / 0.95 / 1.0.
- ``is_heavy_pulling_session(state, session, as_of)`` — the "heavy pulling"
  blocker definition.
- Shared constants for the scheduling briefs (A289 / A293 / A294).

IMPORTANT: always call these on the PERSISTED state, never on the output of
``progression_v1.estimate_missing_baselines``: that helper stamps
``source='test'`` with ``updated_at=today`` on estimated baselines (B364 §0).

A289 adds the scheduling half: ``retest_decisions`` (what planner PASS 3 must
place, week by week) and ``retest_status`` (the live payload for the UI).

Production callers since B364: ``anchored_load`` (official max, tested gate,
re-entry ramp) and ``progression_v1._update_test_from_log`` (confidence).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from backend.engine.stimulus import (
    FAMILY_FINGER_MAX,
    FAMILY_PULLING_MAX,
    count_exposures,
    counted_entries,
    exposure_dates,
    is_pulling_hard_session,
    session_flag,
    stimulus_of,
)

DateLike = Union[date, str]

# ---------------------------------------------------------------------------
# Constants (decisions 2026-10-04). Values without a published source are
# ENGINEERING CONSTANTS and are labelled as such.
# ---------------------------------------------------------------------------

#: A test older than this is not a usable official max for intensity rules.
TEST_FRESH_DAYS = 90

#: Confidence of a test: fewer than LOW_CONF_MIN_EXPOSURES exposure days of the
#: tested family in the LOW_CONF_WINDOW_D days before it → "low".
LOW_CONF_MIN_EXPOSURES = 2
LOW_CONF_WINDOW_D = 21
#: A low-confidence test may be repeated after this many days.
LOW_CONF_RETEST_D = 28

#: Re-entry ramp. ENGINEERING CONSTANTS. A gap of at least REENTRY_GAP_D days
#: without an exposure re-opens the ramp; the test counts as an exposure.
REENTRY_GAP_D = 14
#: Factor on the CAP by exposure index n (the session being prescribed
#: included): n=1 → 0.90, n=2 → 0.95, n≥3 → 1.0. floor_eff = min(floor, cap_eff).
REENTRY_FACTORS: Dict[int, float] = {1: 0.90, 2: 0.95}
REENTRY_FULL_FACTOR = 1.0

#: ENGINEERING CONSTANT: relative load change per second of hang duration
#: (official_t = official_src × (1 + HANG_PCT_PER_S × (t_src − t))).
HANG_PCT_PER_S = 0.015

#: Finger days need this gap (aligned with the planner's no-consecutive-finger rule).
FINGER_GAP_H = 48
#: A hang test is blocked this long after a finger-hard day (max hang family,
#: limit, outdoor-hard).
RETEST_BLOCK_H = 72
#: A pull-up test is blocked this long after a heavy pulling session.
PULL_TEST_BLOCK_H = 48
#: ENGINEERING CONSTANT: a weighted pull at or above this share of the official
#: 1RM is "heavy".
HEAVY_PULL_PCT_1RM = 0.85
#: very_hard feedback in the last N days blocks a retest.
VERY_HARD_BLOCK_D = 3
#: No retest this many days (or fewer) before a trip.
PRE_TRIP_BLOCK_D = 10
#: Phases in which no retest is scheduled.
RETEST_BLOCKED_PHASES = ("performance", "deload")

# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------

PROTOCOL_HANG_7S = "max_hang_7s_total_load"
PROTOCOL_HANG_5S = "max_hang_5s_total_load"
PROTOCOL_PULLUP_2RM = "weighted_pullup_2rm"

_HANG_PROTOCOL_SECONDS: Dict[str, int] = {PROTOCOL_HANG_7S: 7, PROTOCOL_HANG_5S: 5}

PROTOCOL_FAMILY: Dict[str, str] = {
    PROTOCOL_HANG_7S: FAMILY_FINGER_MAX,
    PROTOCOL_HANG_5S: FAMILY_FINGER_MAX,
    PROTOCOL_PULLUP_2RM: FAMILY_PULLING_MAX,
}

#: Exercises anchored to a protocol (for consumers mapping an exercise to its
#: reference max). The chin-up uses the pull-up 2RM (CHINUP_TO_PULLUP_RATIO 1.0,
#: applied by B364, not here).
EXERCISE_PROTOCOL: Dict[str, str] = {
    "max_hang_7s": PROTOCOL_HANG_7S,
    "horst_7_53": PROTOCOL_HANG_7S,
    "max_hang_5s": PROTOCOL_HANG_5S,
    "weighted_pullup": PROTOCOL_PULLUP_2RM,
    "weighted_chinup": PROTOCOL_PULLUP_2RM,
}

_TESTED_SOURCES = ("test", "test_session")

# B364 review: the baseline fallback is "tested" only when a TEST LOG wrote it.
# ``_update_test_from_log`` always appends a ``tests.*`` entry (so the fallback
# is not even reached) and stamps the pulling baseline ``test_session``. A
# baseline-only ``source='test'`` is what ``estimate_missing_baselines``
# persists at onboarding / assessment from a SELF-REPORTED measured value —
# not an official max written by a test log, so it does not open the gate.
_BASELINE_TESTED_SOURCES = ("test_session",)


def _cand_tested(cand: Mapping[str, Any]) -> bool:
    if cand.get("from_baseline"):
        return cand.get("source") in _BASELINE_TESTED_SOURCES
    return cand.get("source") in _TESTED_SOURCES


def _om_is_test(om: Mapping[str, Any]) -> bool:
    """The official max comes from a real test (any age) — not from a baseline
    estimated or self-reported at onboarding (A289 review: those must never be
    shown as "tested maxes")."""
    return _cand_tested(om)


def _as_date(value: DateLike) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return _as_date(value)
    except (TypeError, ValueError):
        return None


def _estimate_1rm_from_2rm(total_2rm: float) -> float:
    # Lazy import keeps this module importable from progression_v1 later (B364).
    from backend.engine.progression_v1 import estimate_1rm_from_2rm

    return estimate_1rm_from_2rm(total_2rm)


def convert_hang_seconds(total_kg: float, from_s: float, to_s: float) -> float:
    """Convert a hang max between durations (ENGINEERING CONSTANT 0.015/s)."""
    return round(float(total_kg) * (1 + HANG_PCT_PER_S * (float(from_s) - float(to_s))), 1)


# ---------------------------------------------------------------------------
# official_max
# ---------------------------------------------------------------------------

def _hang_candidates(state: Mapping[str, Any], as_of: date) -> List[Dict[str, Any]]:
    cands: List[Dict[str, Any]] = []
    for t in ((state.get("tests") or {}).get("max_strength") or []):
        if not isinstance(t, Mapping):
            continue
        secs = _HANG_PROTOCOL_SECONDS.get(str(t.get("test_id") or ""))
        if secs is None:
            continue
        d = _parse_date(t.get("date"))
        total = _num(t.get("total_load_kg"))
        if d is None or total is None or d > as_of:
            continue
        cands.append({
            "date": d, "total": total, "seconds": secs, "source": "test",
            "test_id": t.get("test_id"), "bodyweight_kg": _num(t.get("bodyweight_kg")),
            "stored_confidence": t.get("confidence"),
        })
    if cands:
        return cands
    # Fallback: a persisted hangboard baseline written by a test session.
    hb = (state.get("baselines") or {}).get("hangboard") or []
    if hb and isinstance(hb[0], Mapping):
        b = hb[0]
        d = _parse_date(b.get("updated_at"))
        total = _num(b.get("max_total_load_kg"))
        if d is not None and total is not None and d <= as_of:
            cands.append({
                "date": d, "total": total, "seconds": int(_num(b.get("hang_seconds")) or 7),
                "source": str(b.get("source") or "unknown"), "test_id": None,
                "bodyweight_kg": _num(b.get("bodyweight_at_test_kg") or b.get("bodyweight_kg")),
                "stored_confidence": None, "from_baseline": True,
            })
    return cands


def _pull_candidates(state: Mapping[str, Any], as_of: date) -> List[Dict[str, Any]]:
    cands: List[Dict[str, Any]] = []
    for t in ((state.get("tests") or {}).get("pulling_strength") or []):
        if not isinstance(t, Mapping) or t.get("test_id") != PROTOCOL_PULLUP_2RM:
            continue
        d = _parse_date(t.get("date"))
        total = _num(t.get("total_load_2rm_kg"))
        if d is None or total is None or d > as_of:
            continue
        cands.append({
            "date": d, "total": total, "source": "test", "test_id": t.get("test_id"),
            "one_rm": _num(t.get("estimated_1rm_kg")),
            "bodyweight_kg": _num(t.get("bodyweight_kg")),
            "stored_confidence": t.get("confidence"),
        })
    if cands:
        return cands
    b = (state.get("baselines") or {}).get("pulling") or {}
    if isinstance(b, Mapping):
        d = _parse_date(b.get("updated_at"))
        total = _num(b.get("weighted_pullup_2rm_total_kg"))
        if d is not None and total is not None and d <= as_of:
            cands.append({
                "date": d, "total": total, "source": str(b.get("source") or "unknown"),
                "test_id": None,
                "one_rm": _num(b.get("weighted_pullup_1rm_total_kg") or b.get("weighted_pullup_1rm_estimated_kg")),
                "bodyweight_kg": _num(b.get("bodyweight_at_test_kg") or b.get("bodyweight_kg")),
                "stored_confidence": None, "from_baseline": True,
            })
    return cands


def official_max(state: Mapping[str, Any], protocol: str, as_of: DateLike) -> Optional[Dict[str, Any]]:
    """The official max for ``protocol`` on ``as_of``, or ``None``.

    Returns::

        {protocol, family, total_kg, date, age_days, fresh, tested, source,
         test_id, seconds?, source_seconds?, converted?, one_rm_kg?,
         bodyweight_kg, edge_mm?, grip?, stored_confidence}

    - Freshest candidate ≤ ``as_of`` wins; on a date tie a same-duration hang
      test wins over a converted one.
    - ``tests.*`` entries are the source (``source: "test"``). The persisted
      baseline is read only when ``tests.*`` has nothing (its own ``source``
      is reported as-is, ``from_baseline: True``; only ``test_session`` counts
      as tested there — a baseline-only ``test`` is an onboarding self-report
      persisted by ``estimate_missing_baselines``, B364 review).
    - ``stored_confidence`` is informational: use ``test_confidence``.
    """
    on = _as_date(as_of)
    if protocol in _HANG_PROTOCOL_SECONDS:
        target_s = _HANG_PROTOCOL_SECONDS[protocol]
        cands = _hang_candidates(state, on)
        if not cands:
            return None
        best = max(cands, key=lambda c: (c["date"], c["seconds"] == target_s))
        converted = best["seconds"] != target_s
        total = convert_hang_seconds(best["total"], best["seconds"], target_s) if converted else best["total"]
        hb = (state.get("baselines") or {}).get("hangboard") or []
        hb0 = hb[0] if hb and isinstance(hb[0], Mapping) else {}
        age = (on - best["date"]).days
        return {
            "protocol": protocol,
            "family": PROTOCOL_FAMILY[protocol],
            "total_kg": total,
            "date": best["date"].isoformat(),
            "age_days": age,
            "fresh": age < TEST_FRESH_DAYS,
            "tested": _cand_tested(best) and age < TEST_FRESH_DAYS,
            "from_baseline": bool(best.get("from_baseline")),
            "source": best["source"],
            "test_id": best["test_id"],
            "seconds": target_s,
            "source_seconds": best["seconds"],
            "converted": converted,
            "bodyweight_kg": best["bodyweight_kg"],
            "edge_mm": hb0.get("edge_mm"),
            "grip": hb0.get("grip"),
            "stored_confidence": best["stored_confidence"],
        }
    if protocol == PROTOCOL_PULLUP_2RM:
        cands = _pull_candidates(state, on)
        if not cands:
            return None
        best = max(cands, key=lambda c: c["date"])
        age = (on - best["date"]).days
        one_rm = best["one_rm"] if best["one_rm"] is not None else _estimate_1rm_from_2rm(best["total"])
        return {
            "protocol": protocol,
            "family": PROTOCOL_FAMILY[protocol],
            "total_kg": best["total"],
            "one_rm_kg": one_rm,
            "date": best["date"].isoformat(),
            "age_days": age,
            "fresh": age < TEST_FRESH_DAYS,
            "tested": _cand_tested(best) and age < TEST_FRESH_DAYS,
            "from_baseline": bool(best.get("from_baseline")),
            "source": best["source"],
            "test_id": best["test_id"],
            "bodyweight_kg": best["bodyweight_kg"],
            "stored_confidence": best["stored_confidence"],
        }
    return None


def is_tested(state: Mapping[str, Any], protocol: str, as_of: DateLike) -> bool:
    """The "tested baseline" gate: official max with source test/test_session, < 90 days."""
    om = official_max(state, protocol, as_of)
    return bool(om and om["tested"])


# ---------------------------------------------------------------------------
# test_confidence
# ---------------------------------------------------------------------------

def test_confidence(
    state: Mapping[str, Any],
    test: Mapping[str, Any],
    *,
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Computed confidence of a test. ``test`` is a ``tests.*`` entry or an
    ``official_max`` result (needs ``date`` and ``test_id`` or ``protocol``).

    Returns ``{confidence, exposures, window_start, window_end, min_required,
    family, test_date}``. ``confidence`` is ``"high"`` | ``"low"``, or
    ``None`` when the protocol has no stimulus family (e.g. repeater tests)
    or the test has no date. The stored ``confidence`` field is ignored.
    """
    protocol = str(test.get("protocol") or test.get("test_id") or "")
    family = PROTOCOL_FAMILY.get(protocol)
    d = _parse_date(test.get("date"))
    out: Dict[str, Any] = {
        "confidence": None, "exposures": None, "window_start": None, "window_end": None,
        "min_required": LOW_CONF_MIN_EXPOSURES, "family": family,
        "test_date": d.isoformat() if d else None,
    }
    if family is None or d is None:
        return out
    start = d - timedelta(days=LOW_CONF_WINDOW_D)
    end = d - timedelta(days=1)
    n = count_exposures(state, family, since=start, until=end, archived_weeks=archived_weeks)
    out.update({
        "confidence": "low" if n < LOW_CONF_MIN_EXPOSURES else "high",
        "exposures": n,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
    })
    return out


# Not a pytest test, despite the name (tests import it).
test_confidence.__test__ = False  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# reentry_step
# ---------------------------------------------------------------------------

def reentry_factor(n: int) -> float:
    """Cap factor for exposure index ``n`` (n ≤ 1 → 0.90)."""
    if n <= 1:
        return REENTRY_FACTORS[1]
    return REENTRY_FACTORS.get(n, REENTRY_FULL_FACTOR)


def reentry_step(
    state: Mapping[str, Any],
    family: str,
    as_of: DateLike,
    *,
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
    include_current: bool = True,
    extra_dates: Optional[Sequence[DateLike]] = None,
) -> Dict[str, Any]:
    """Where the athlete is on the re-entry ramp for ``family`` on ``as_of``.

    ``extra_dates`` (B364): exposure days the view cannot see — the dates of
    the ``tests.*`` entries of the family (a test counts as an exposure even
    when its week was archived or the test was logged outside a plan session).
    Only dates strictly before ``as_of`` are used; duplicates collapse.

    n = distinct exposure days strictly before ``as_of`` after the last gap of
    at least ``REENTRY_GAP_D`` days (tests included), plus 1 for the session
    being prescribed when ``include_current``. A gap between the last exposure
    and ``as_of`` itself also re-opens the ramp. No history → n = 1.

    Returns ``{family, as_of, n, factor, gap_days, run_start, last_exposure,
    run_dates, in_reentry}``:
    - ``gap_days``: length of the gap that opened the current run (``None``
      when the history holds no such gap).
    - ``in_reentry``: ``factor < 1.0``.
    """
    on = _as_date(as_of)
    day_set = {
        _as_date(d) for d in exposure_dates(
            state, family, until=on - timedelta(days=1), archived_weeks=archived_weeks
        )
    }
    for extra in extra_dates or ():
        d = _parse_date(extra)
        if d is not None and d < on:
            day_set.add(d)
    dates = sorted(day_set)
    run: List[date] = []
    prev = on
    gap_days: Optional[int] = None
    for d in reversed(dates):
        if (prev - d).days >= REENTRY_GAP_D:
            gap_days = (prev - d).days
            break
        run.insert(0, d)
        prev = d
    n = len(run) + (1 if include_current else 0)
    factor = reentry_factor(n)
    return {
        "family": family,
        "as_of": on.isoformat(),
        "n": n,
        "factor": factor,
        "gap_days": gap_days,
        "run_start": run[0].isoformat() if run else None,
        "last_exposure": dates[-1].isoformat() if dates else None,
        "run_dates": [d.isoformat() for d in run],
        "in_reentry": factor < REENTRY_FULL_FACTOR,
    }


# ---------------------------------------------------------------------------
# Heavy pulling (retest blocker)
# ---------------------------------------------------------------------------

def _entry_total_load(entry: Mapping[str, Any], bodyweight: Optional[float]) -> Optional[float]:
    total = _num(entry.get("used_total_load_kg"))
    if total is not None:
        return total
    ext = _num(entry.get("used_external_load_kg"))
    if ext is not None and bodyweight is not None:
        return bodyweight + ext
    suggested = entry.get("suggested") or {}
    total = _num(suggested.get("target_total_load_kg"))
    if total is not None:
        return total
    ext = _num(entry.get("load_kg"))
    if ext is not None and bodyweight is not None:
        return bodyweight + ext
    return None


def is_heavy_pulling_session(
    state: Mapping[str, Any], session: Mapping[str, Any], as_of: DateLike
) -> bool:
    """Heavy pulling (decision 2026-10-04): a weighted pull at ≥ 85 % of the
    official 1RM, or a session tagged/catalogued pulling + hard.

    - A pulling_max exercise whose load cannot be read, or with no official
      max to compare against, counts as heavy (prudent: it can only delay a
      test, never put one on top of real fatigue).
    - Literal consequence, flagged for A289: ``power_endurance_gym`` is
      catalogued ``pulling: True, hard: True`` → heavy pulling.
    """
    # Same "was it done" rule as stimulus.py: a skipped / not-completed /
    # 0-set logged pull is not a heavy pull.
    entries, _origin = counted_entries(session)
    pulls = [e for e in entries if stimulus_of(e.get("exercise_id")) == FAMILY_PULLING_MAX]
    if pulls:
        om = official_max(state, PROTOCOL_PULLUP_2RM, as_of)
        bw = _num(state.get("bodyweight_kg")) or _num((state.get("body") or {}).get("weight_kg"))
        for e in pulls:
            total = _entry_total_load(e, bw)
            if om is None or total is None:
                return True
            if total >= HEAVY_PULL_PCT_1RM * float(om["one_rm_kg"]):
                return True
    # Label-level rule (tags / _SESSION_META); the exercise clause was
    # already decided above by load.
    return session_flag(session, "pulling") and session_flag(session, "hard")


# ---------------------------------------------------------------------------
# A289 — retest DECISIONS (planner PASS 3) and retest STATUS (UI)
# ---------------------------------------------------------------------------
#
# Only this module schedules a test of a tested axis (decision 2026-10-04:
# "only retest_policy schedules tests"). It answers, for one week, "is a test
# of axis X due here, from which day, and which days are blocked before the
# planner even looks at its own sessions". The planner then places the test
# against its in-week sessions with the SAME blocker definitions (finger-hard
# day, heavy pulling) — see ``planner_v2`` PASS 3.
#
# Scope: an axis is COVERED only when the athlete has a tested official max
# for it on the week start (``official_max(...)["tested"]``: source
# test/test_session, < 90 days). Untested axes, stale tests and loading-pin
# finger users are not covered: the legacy PASS 3 keeps scheduling them bit
# for bit. ``retest_decisions`` returns ``None`` when nothing is covered, and
# the planner is byte-identical to the pre-A289 one with ``None``.
#
# Triggers (one test per axis per trigger; the first that applies wins):
#   end_of_phase           last week of strength_power
#   end_of_phase_slipped   the week after it, when the gap since the last test
#                          kept the whole end-of-phase week out of reach (ONE
#                          slip of one week — "option B", decision 2026-10-04)
#   cycle_start            first week of a macrocycle
#   maintenance            MAINTENANCE_RETEST_D since the last test
#   early_retest           EARLY_RETEST_SIGNALS measured sessions above the max
#                          (``progression_counters.retest_signals``, B364)
# Week blockers: performance / deload phase, gap since the last test
# (LOW_CONF_RETEST_D when the test had low confidence, HIGH_CONF_RETEST_D
# otherwise). Day blockers: ≤ PRE_TRIP_BLOCK_D days before a trip (or during
# it), very_hard feedback in the VERY_HARD_BLOCK_D days before, a finger-hard
# day < RETEST_BLOCK_H before a hang test, a heavy pull < PULL_TEST_BLOCK_H
# before a pull-up test.
#
# Hours → days: the planner works in whole days (one session per slot, slots
# are not timed), so "< 72 h after X" means "fewer than 3 calendar days after
# the day of X" and "< 48 h" means "fewer than 2". A session two days earlier
# in the same slot is exactly 48 h away and does NOT block a pull-up test.

AXIS_FINGER = "finger"
AXIS_PULLING = "pulling"
RETEST_AXES = (AXIS_FINGER, AXIS_PULLING)

#: Test session the policy schedules per axis (hangboard users; loading-pin
#: users are not covered on the finger axis).
AXIS_TEST_SESSION: Dict[str, str] = {
    AXIS_FINGER: "test_max_hang_7s",
    AXIS_PULLING: "test_max_weighted_pullup",
}
AXIS_PROTOCOL: Dict[str, str] = {
    AXIS_FINGER: PROTOCOL_HANG_7S,
    AXIS_PULLING: PROTOCOL_PULLUP_2RM,
}
#: Sessions that test an axis (for "is a test already planned").
AXIS_TEST_SESSIONS_ALL: Dict[str, Tuple[str, ...]] = {
    AXIS_FINGER: ("test_max_hang_7s", "test_max_hang_5s", "test_lp_max_5s"),
    AXIS_PULLING: ("test_max_weighted_pullup", "test_pullup_bw"),
}
#: Exercises whose measured sessions feed ``retest_signals`` per axis.
AXIS_SIGNAL_EXERCISES: Dict[str, Tuple[str, ...]] = {
    AXIS_FINGER: ("max_hang_7s", "max_hang_5s"),
    AXIS_PULLING: ("weighted_pullup", "weighted_chinup"),
}

#: Gap after a high-confidence test (the planner's historical 42-day freshness).
HIGH_CONF_RETEST_D = 42
#: A tested axis is re-measured at the latest after 12 weeks (same as the
#: planner's MAX_WEEKS_UNTESTED; after 90 days the axis is no longer "tested"
#: and the legacy schedule takes over).
MAINTENANCE_RETEST_D = 84
#: Measured sessions above the official max needed for an early retest.
EARLY_RETEST_SIGNALS = 2
#: ENGINEERING CONSTANT: how far ahead ``retest_status`` projects the next test.
STATUS_HORIZON_WEEKS = 16
#: |Δ| below this (percent) between two tests of one protocol = "stable".
TREND_STABLE_PCT = 5.0

TRIGGER_END_OF_PHASE = "end_of_phase"
TRIGGER_END_OF_PHASE_SLIPPED = "end_of_phase_slipped"
TRIGGER_CYCLE_START = "cycle_start"
TRIGGER_MAINTENANCE = "maintenance"
TRIGGER_EARLY = "early_retest"

_TRIGGER_TEXT: Dict[str, str] = {
    TRIGGER_END_OF_PHASE: "End of the strength phase: measure what the block built.",
    TRIGGER_END_OF_PHASE_SLIPPED: (
        "End-of-strength retest moved one week: the last test needs {gap} days "
        "before it can be repeated ({confidence} confidence)."
    ),
    TRIGGER_CYCLE_START: "New cycle: a fresh baseline for the loads.",
    TRIGGER_MAINTENANCE: "12 weeks since the last test: keep the max honest.",
    TRIGGER_EARLY: "Two measured sessions above your tested max: time to raise it.",
}

_DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def retest_gap_days(confidence: Optional[str]) -> int:
    """Days before a test of the same axis may be repeated."""
    return LOW_CONF_RETEST_D if confidence == "low" else HIGH_CONF_RETEST_D


def axis_official(
    state: Mapping[str, Any], axis: str, as_of: DateLike, *, finger_device: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """The official max the policy reads for ``axis`` (``None`` = not covered
    by tests at all). Loading-pin users have no hang protocol → ``None``."""
    if axis == AXIS_FINGER and finger_device == "loading_pin":
        return None
    return official_max(state, AXIS_PROTOCOL[axis], as_of)


def _find_test_entry(state: Mapping[str, Any], om: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    key = "pulling_strength" if om.get("protocol") == PROTOCOL_PULLUP_2RM else "max_strength"
    for t in ((state.get("tests") or {}).get(key) or []):
        if (isinstance(t, Mapping) and str(t.get("date") or "")[:10] == om.get("date")
                and t.get("test_id") == om.get("test_id")):
            return t
    return None


def axis_confidence(
    state: Mapping[str, Any],
    om: Mapping[str, Any],
    *,
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Confidence of the test behind ``om``.

    A confidence COMPUTED and stored by a test log or by the B364 migration
    (it carries ``confidence_basis``) wins — the migration computed it with
    the archived weeks. Otherwise (pre-B364 constant ``"high"``, baseline-only
    maxes) it is computed here with ``test_confidence``.
    """
    entry = _find_test_entry(state, om)
    if entry is not None and isinstance(entry.get("confidence_basis"), Mapping) \
            and entry.get("confidence") in ("low", "high"):
        basis = entry["confidence_basis"]
        return {"confidence": entry["confidence"], "exposures": basis.get("exposures"),
                "min_required": basis.get("min_required", LOW_CONF_MIN_EXPOSURES), "basis": "stored"}
    conf = test_confidence(state, {"protocol": om.get("protocol"), "date": om.get("date")},
                           archived_weeks=archived_weeks)
    return {"confidence": conf.get("confidence") or "high", "exposures": conf.get("exposures"),
            "min_required": conf.get("min_required"), "basis": "computed"}


def axis_trend(state: Mapping[str, Any], om: Mapping[str, Any]) -> Dict[str, Any]:
    """Δ vs the previous test of the same protocol (stored by B364 when present).

    ``{trend: stable|up|down|None, delta_pct, previous_date}``; |Δ| <
    ``TREND_STABLE_PCT`` → stable. Same rule as ``progression_v1._trend``.
    """
    entry = _find_test_entry(state, om)
    if entry is not None and entry.get("trend") in ("stable", "up", "down"):
        return {"trend": entry["trend"], "delta_pct": _num(entry.get("delta_pct")),
                "previous_date": entry.get("previous_date")}
    if entry is None:
        return {"trend": None, "delta_pct": None, "previous_date": None}
    pulling = om.get("protocol") == PROTOCOL_PULLUP_2RM
    key = "pulling_strength" if pulling else "max_strength"
    value_key = "total_load_2rm_kg" if pulling else "total_load_kg"
    value = _num(entry.get(value_key))
    prev = [t for t in ((state.get("tests") or {}).get(key) or [])
            if isinstance(t, Mapping) and t.get("test_id") == entry.get("test_id")
            and str(t.get("date") or "")[:10] < str(om.get("date")) and _num(t.get(value_key))]
    if value is None or not prev:
        return {"trend": None, "delta_pct": None, "previous_date": None}
    prev.sort(key=lambda t: str(t.get("date") or ""))
    before = float(_num(prev[-1].get(value_key)) or 0)
    if before <= 0:
        return {"trend": None, "delta_pct": None, "previous_date": None}
    delta = round((value - before) / before * 100, 1)
    trend = "stable" if abs(delta) < TREND_STABLE_PCT else ("up" if delta > 0 else "down")
    return {"trend": trend, "delta_pct": delta, "previous_date": str(prev[-1].get("date"))[:10]}


def axis_signals(state: Mapping[str, Any], axis: str, om: Mapping[str, Any]) -> Dict[str, Any]:
    """Measured early-retest evidence for ``axis`` against the CURRENT official
    max (signals recorded against an older test do not count).

    Distinct days across the axis exercises: ``{count, last_date, dates, needed}``.
    """
    sig = ((state.get("progression_counters") or {}).get("retest_signals") or {})
    days: set = set()
    if isinstance(sig, Mapping):
        for ex in AXIS_SIGNAL_EXERCISES[axis]:
            row = sig.get(ex)
            if not isinstance(row, Mapping):
                continue
            if str(row.get("official_date") or "")[:10] != str(om.get("date")):
                continue
            for d in row.get("dates") or []:
                pd = _parse_date(d)
                if pd is not None:
                    days.add(pd)
    dates = sorted(days)
    return {"count": len(dates), "last_date": dates[-1].isoformat() if dates else None,
            "dates": [d.isoformat() for d in dates], "needed": EARLY_RETEST_SIGNALS}


def very_hard_dates(state: Mapping[str, Any]) -> List[str]:
    """Days with a very_hard feedback (session difficulty or any exercise label)."""
    out: set = set()
    for e in state.get("feedback_log") or []:
        if not isinstance(e, Mapping) or not e.get("date"):
            continue
        labels = [e.get("difficulty")] + list((e.get("exercise_feedback") or {}).values()) \
            if isinstance(e.get("exercise_feedback"), Mapping) else [e.get("difficulty")]
        if "very_hard" in labels:
            out.add(str(e["date"])[:10])
    return sorted(out)


def trip_blocked(state: Mapping[str, Any], d: date) -> bool:
    """``d`` falls ≤ PRE_TRIP_BLOCK_D days before a trip, or during it."""
    for trip in state.get("trips") or []:
        if not isinstance(trip, Mapping):
            continue
        start = _parse_date(trip.get("start_date"))
        if start is None:
            continue
        end = _parse_date(trip.get("end_date")) or start
        if start - timedelta(days=PRE_TRIP_BLOCK_D) <= d <= end:
            return True
    return False


def _very_hard_blocked(vh: Sequence[str], d: date) -> bool:
    lo = (d - timedelta(days=VERY_HARD_BLOCK_D)).isoformat()
    hi = (d - timedelta(days=1)).isoformat()
    return any(lo <= v <= hi for v in vh)


def _hot_plan(state: Mapping[str, Any], ws_iso: str) -> Optional[Mapping[str, Any]]:
    """The generated (hot) plan of the week starting ``ws_iso``, or None."""
    plan = (state.get("week_plans") or {}).get(ws_iso)
    if isinstance(plan, Mapping):
        return plan
    cur = state.get("current_week_plan")
    if isinstance(cur, Mapping) and cur.get("start_date") == ws_iso:
        return cur
    return None


def _plan_days(plan: Optional[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    weeks = (plan or {}).get("weeks") or []
    if not weeks or not isinstance(weeks[0], Mapping):
        return []
    return [d for d in (weeks[0].get("days") or []) if isinstance(d, Mapping)]


def _locked_by_merge(state: Mapping[str, Any], ws: date, today: Optional[date]) -> Dict[str, Any]:
    """What ``regenerate_preserving_completed`` will put back over a freshly
    generated week (A289 review): the old plan's done/skipped sessions take
    their slot, and today is copied wholesale when it holds a done session.
    A test placed there would be silently overwritten after generation."""
    slots: List[Dict[str, Any]] = []
    dates: List[str] = []
    for day in _plan_days(_hot_plan(state, ws.isoformat())):
        d_iso = str(day.get("date") or "")[:10]
        d = _parse_date(d_iso)
        if d is None or (today is not None and d < today):
            continue
        sessions = [x for x in (day.get("sessions") or []) if isinstance(x, Mapping)]
        if today is not None and d == today and (
            any(x.get("status") == "done" for x in sessions)
            or day.get("outdoor_session_status") == "done"
        ):
            dates.append(d_iso)
            continue
        for x in sessions:
            if x.get("status") in ("done", "skipped") and x.get("slot"):
                slots.append({"date": d_iso, "slot": x.get("slot")})
    return {"locked_slots": slots, "locked_dates": dates}


def _planned_axis_tests(
    state: Mapping[str, Any], axis: str, *, since: date, exclude_week: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Not-yet-done, not-skipped tests of ``axis`` dated ≥ ``since`` in the hot
    week plans (``exclude_week`` = the week being regenerated)."""
    from backend.engine.stimulus import iter_plan_sessions

    sids = AXIS_TEST_SESSIONS_ALL[axis]
    rows = []
    for d, session, _src in iter_plan_sessions(state):
        if d < since.isoformat():
            continue
        if exclude_week and _monday(_as_date(d)).isoformat() == exclude_week:
            continue
        if session.get("session_id") not in sids:
            continue
        if session.get("status") in ("done", "skipped"):
            continue
        rows.append({"date": d, "session_id": session.get("session_id"), "slot": session.get("slot")})
    return sorted(rows, key=lambda r: (r["date"], str(r["slot"] or "")))


def _trigger_for_week(
    macrocycle: Mapping[str, Any],
    ws: date,
    last: date,
    earliest: date,
    signals: Mapping[str, Any],
) -> Tuple[Optional[str], Optional[date]]:
    """(trigger, trigger_earliest) for the week starting ``ws``, or (None, None).

    ``trigger_earliest`` is the first day the trigger itself allows (the
    early retest waits for the day after its last signal); the gap since the
    last test is applied by the caller.
    """
    from backend.engine.macro_position import position_on

    we = ws + timedelta(days=6)
    pos = position_on(dict(macrocycle), ws.isoformat())
    if not pos or pos["before_start"] or pos["after_end"]:
        return None, None
    if pos["phase_id"] == "strength_power" and pos["is_last_week_of_phase"] and last < ws:
        return TRIGGER_END_OF_PHASE, ws
    prev_ws = ws - timedelta(days=7)
    prev = position_on(dict(macrocycle), prev_ws.isoformat())
    if (prev and not prev["before_start"] and prev["phase_id"] == "strength_power"
            and prev["is_last_week_of_phase"] and last < prev_ws
            and earliest > prev_ws + timedelta(days=6) and earliest <= we):
        return TRIGGER_END_OF_PHASE_SLIPPED, ws
    if pos["abs_week"] == 1 and last < ws:
        return TRIGGER_CYCLE_START, ws
    if signals.get("count", 0) >= EARLY_RETEST_SIGNALS and signals.get("last_date"):
        t_e = _as_date(signals["last_date"]) + timedelta(days=1)
        if t_e <= we:
            return TRIGGER_EARLY, t_e
    maint = last + timedelta(days=MAINTENANCE_RETEST_D)
    if maint <= we:
        return TRIGGER_MAINTENANCE, maint
    return None, None


def _axis_week_decision(
    state: Mapping[str, Any],
    axis: str,
    ws: date,
    *,
    today: Optional[date],
    finger_device: Optional[str],
    archived_weeks: Any,
    check_already_scheduled: bool,
) -> Optional[Dict[str, Any]]:
    """Week-level decision for one axis. ``None`` = axis not covered.

    With ``check_already_scheduled`` (the planner's call) a test that was
    already due in an EARLIER week (from the current week on) that is not
    generated yet is deferred to that week: the week it lands in does not
    depend on which week the athlete opens first (A289 review)."""
    from backend.engine.macro_position import position_on

    om = axis_official(state, axis, ws, finger_device=finger_device)
    if om is None or not om.get("tested"):
        return None
    macrocycle = state.get("macrocycle") or {}
    last = _as_date(om["date"])
    conf = axis_confidence(state, om, archived_weeks=archived_weeks)
    gap = retest_gap_days(conf["confidence"])
    earliest = last + timedelta(days=gap)
    signals = axis_signals(state, axis, om)
    base = {
        "axis": axis,
        "session_id": AXIS_TEST_SESSION[axis],
        "protocol": AXIS_PROTOCOL[axis],
        "last_test_date": last.isoformat(),
        "confidence": conf["confidence"],
        "gap_days": gap,
        "earliest_date": earliest.isoformat(),
    }
    trigger, t_earliest = _trigger_for_week(macrocycle, ws, last, earliest, signals)
    if trigger is None:
        return {**base, "status": "not_due"}
    if trigger == TRIGGER_EARLY:
        # Measured evidence says the max is too low: the confidence of the old
        # test no longer matters, only the low-confidence floor applies.
        earliest = last + timedelta(days=LOW_CONF_RETEST_D)
        base["earliest_date"] = earliest.isoformat()
    we = ws + timedelta(days=6)
    first = max(earliest, t_earliest or ws, ws)
    reason = _TRIGGER_TEXT[trigger].format(gap=gap, confidence=conf["confidence"])
    out = {**base, "trigger": trigger, "reason": reason}
    pos = position_on(dict(macrocycle), ws.isoformat()) or {}
    if pos.get("phase_id") in RETEST_BLOCKED_PHASES:
        return {**out, "status": "skipped", "skip_reason": "blocked:phase"}
    if first > we:
        # The end-of-phase week that cannot reach the gap slips once.
        nxt_we = we + timedelta(days=7)
        if trigger == TRIGGER_END_OF_PHASE and earliest <= nxt_we:
            return {**out, "status": "skipped", "skip_reason": "slipped:gap",
                    "slipped_to_week": (ws + timedelta(days=7)).isoformat()}
        return {**out, "status": "skipped", "skip_reason": "blocked:gap"}
    if check_already_scheduled:
        planned = _planned_axis_tests(state, axis, since=today or ws, exclude_week=ws.isoformat())
        if planned:
            return {**out, "status": "already_scheduled", "scheduled_date": planned[0]["date"]}
        floor = _monday(today) if today is not None else ws
        natural = max(earliest, t_earliest or ws)
        wk = max(_monday(natural), floor)
        while wk < ws:
            if _hot_plan(state, wk.isoformat()) is None:
                prior = _axis_week_decision(state, axis, wk, today=today, finger_device=finger_device,
                                            archived_weeks=archived_weeks, check_already_scheduled=False)
                if prior and prior.get("status") == "due":
                    return {**out, "status": "skipped", "skip_reason": "deferred:earlier_week",
                            "deferred_to_week": wk.isoformat()}
            wk += timedelta(days=7)
    vh = very_hard_dates(state)
    allowed: List[str] = []
    last_block = None
    d = first
    while d <= we:
        if today is not None and d < today:
            d += timedelta(days=1)
            continue
        if trip_blocked(state, d):
            last_block = "blocked:trip"
        elif _very_hard_blocked(vh, d):
            last_block = "blocked:very_hard"
        else:
            allowed.append(d.isoformat())
        d += timedelta(days=1)
    if not allowed:
        return {**out, "status": "skipped", "skip_reason": last_block or "blocked:past"}
    return {**out, "status": "due", "first_date": first.isoformat(), "allowed_dates": allowed}


def _external_blockers(
    state: Mapping[str, Any],
    ws: date,
    *,
    archived_weeks: Any,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]],
) -> Dict[str, List[str]]:
    """Blocking days the planner cannot see in its own week: everything before
    the week (planned or done, custom sessions included, outdoor-hard days,
    free-session limit days) plus what is already DONE inside the week (a
    mid-week regeneration preserves done sessions after generating)."""
    from backend.engine.stimulus import finger_hard_days, iter_plan_sessions

    we = ws + timedelta(days=6)
    look = ws - timedelta(days=max(RETEST_BLOCK_H, PULL_TEST_BLOCK_H) // 24)
    finger: set = set()
    for row in finger_hard_days(state, since=look, until=we, archived_weeks=archived_weeks,
                                outdoor_rows=outdoor_rows, include_planned=True):
        d = _as_date(row["date"])
        if d < ws or row.get("status") == "done":
            finger.add(row["date"])
    heavy: set = set()
    for d_iso, session, _src in iter_plan_sessions(state, archived_weeks):
        d = _as_date(d_iso)
        if d < look or d > we or session.get("status") == "skipped":
            continue
        if d >= ws and session.get("status") != "done":
            continue
        if is_heavy_pulling_session(state, session, d):
            heavy.add(d_iso)
    return {"finger_hard_dates": sorted(finger), "heavy_pull_dates": sorted(heavy)}


def retest_decisions(
    state: Mapping[str, Any],
    week_start: DateLike,
    *,
    today: Optional[DateLike] = None,
    finger_device: Optional[str] = None,
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """The retest decisions for the week starting ``week_start`` (a Monday).

    Returns ``None`` when no axis is covered (untested athlete → the planner
    stays byte-identical). Otherwise::

        {
          "version": 1, "week_start", "covered_axes": [...],
          "required_sessions": [            # what PASS 3 must place
            {kind: "test", axis, session_id, protocol, trigger, reason,
             earliest_date, allowed_dates, required: True, order, paired_with,
             last_test_date, confidence, gap_days}
          ],
          "skipped": [{axis, session_id, trigger, reason, skip_reason, ...}],
          "already_scheduled": [{axis, date, trigger}],
          "axes": {axis: <week-level decision>},
          "finger_hard_dates": [...], "heavy_pull_dates": [...],
          "block_hours": {"hang": 72, "pull": 48},
        }

    Pure: everything derives from the state (macrocycle, tests, trips,
    feedback_log, progression_counters, week plans), the archived weeks and
    outdoor rows passed in, and ``today`` — never ``date.today()``.
    """
    ws = _monday(_as_date(week_start))
    td = _as_date(today) if today else None
    axes: Dict[str, Dict[str, Any]] = {}
    for axis in RETEST_AXES:
        dec = _axis_week_decision(state, axis, ws, today=td, finger_device=finger_device,
                                  archived_weeks=archived_weeks, check_already_scheduled=True)
        if dec is not None:
            axes[axis] = dec
    if not axes:
        return None
    due = [axes[a] for a in RETEST_AXES if a in axes and axes[a]["status"] == "due"]
    required: List[Dict[str, Any]] = []
    for i, dec in enumerate(due):
        required.append({
            "kind": "test",
            "axis": dec["axis"],
            "session_id": dec["session_id"],
            "protocol": dec["protocol"],
            "trigger": dec["trigger"],
            "reason": dec["reason"],
            "earliest_date": dec["first_date"],
            "allowed_dates": list(dec["allowed_dates"]),
            "required": True,
            "order": i + 1,
            "paired_with": None,
            "last_test_date": dec["last_test_date"],
            "confidence": dec["confidence"],
            "gap_days": dec["gap_days"],
        })
    if len(required) == 2:
        # Paired test day: hang first, then the pull-up (decision 2026-10-04).
        required[0]["paired_with"] = required[1]["session_id"]
        required[1]["paired_with"] = required[0]["session_id"]
    skipped = [
        {k: dec.get(k) for k in ("axis", "session_id", "trigger", "reason", "skip_reason",
                                 "earliest_date", "slipped_to_week", "deferred_to_week")
         if dec.get(k) is not None}
        for dec in axes.values() if dec["status"] == "skipped"
    ]
    already = [{"axis": dec["axis"], "date": dec["scheduled_date"], "trigger": dec.get("trigger")}
               for dec in axes.values() if dec["status"] == "already_scheduled"]
    ext = _external_blockers(state, ws, archived_weeks=archived_weeks, outdoor_rows=outdoor_rows) \
        if required else {"finger_hard_dates": [], "heavy_pull_dates": []}
    locked = _locked_by_merge(state, ws, td) if required else {"locked_slots": [], "locked_dates": []}
    return {
        "version": 1,
        "week_start": ws.isoformat(),
        "covered_axes": [a for a in RETEST_AXES if a in axes],
        "required_sessions": required,
        "skipped": skipped,
        "already_scheduled": already,
        "axes": axes,
        "finger_hard_dates": ext["finger_hard_dates"],
        "heavy_pull_dates": ext["heavy_pull_dates"],
        "locked_slots": locked["locked_slots"],
        "locked_dates": locked["locked_dates"],
        "block_hours": {"hang": RETEST_BLOCK_H, "pull": PULL_TEST_BLOCK_H},
    }


def test_day_blockers(
    state: Mapping[str, Any],
    axis: str,
    on: DateLike,
    *,
    archived_weeks: Any = None,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Live blockers of a test of ``axis`` planned on ``on``, with the SAME
    definitions the planner used — but over the plan as it is NOW (custom
    sessions added after generation, a very_hard logged since). Used for the
    "flag on the test card" (decision 2026-10-04: no auto-shift)."""
    from backend.engine.stimulus import finger_hard_days, iter_plan_sessions

    d = _as_date(on)
    out: List[Dict[str, Any]] = []
    if _very_hard_blocked(very_hard_dates(state), d):
        out.append({"code": "very_hard", "detail": "very_hard feedback in the 3 days before"})
    if trip_blocked(state, d):
        out.append({"code": "trip", "detail": "within 10 days of a trip"})
    if axis == AXIS_FINGER:
        # Whole calendar days, inclusive (same reading as PASS 3a, A289 review):
        # a finger-hard evening 3 days before a morning test is ~60 h < 72 h.
        lo = d - timedelta(days=RETEST_BLOCK_H // 24)
        for row in finger_hard_days(state, since=lo, until=d - timedelta(days=1),
                                    archived_weeks=archived_weeks, outdoor_rows=outdoor_rows,
                                    include_planned=True):
            out.append({"code": "recent_finger", "date": row["date"],
                        "session_id": row.get("session_id"), "detail": row.get("reason")})
    else:
        lo = d - timedelta(days=PULL_TEST_BLOCK_H // 24 - 1)
        for d_iso, session, _src in iter_plan_sessions(state, archived_weeks):
            sd = _as_date(d_iso)
            if sd < lo or sd >= d or session.get("status") == "skipped":
                continue
            if is_heavy_pulling_session(state, session, sd):
                out.append({"code": "heavy_pull", "date": d_iso,
                            "session_id": session.get("session_id")})
    return out


def retest_status(
    state: Mapping[str, Any],
    today: DateLike,
    *,
    finger_device: Optional[str] = None,
    archived_weeks: Optional[Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]] = None,
    outdoor_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    horizon_weeks: int = STATUS_HORIZON_WEEKS,
) -> Dict[str, Any]:
    """Live, read-only retest status per axis for the UI (computed on every
    GET, so it is right for cached weeks too).

    Per axis::

        {axis, covered, official_total_kg, test_date, age_days, protocol,
         confidence, confidence_exposures, trend, delta_pct, previous_date,
         earliest_retest, signals: {count, needed}, fatigue,
         next_test: {date, session_id, source: planned|projected, trigger,
                     reason, blockers: [...]} | None,
         next_test_reason}       # why there is no next test, when None

    ``covered`` False → the axis is scheduled by the legacy planner rules
    (untested, test older than 90 days, loading pin).
    """
    td = _as_date(today)
    out_axes: Dict[str, Dict[str, Any]] = {}
    for axis in RETEST_AXES:
        om = axis_official(state, axis, td, finger_device=finger_device)
        if om is None or not _om_is_test(om):
            continue  # never tested: nothing to show (an estimate is not a max)
        row: Dict[str, Any] = {
            "axis": axis,
            "covered": bool(om.get("tested")),
            "protocol": om.get("protocol"),
            "official_total_kg": om.get("total_kg"),
            "test_date": om.get("date"),
            "age_days": om.get("age_days"),
        }
        conf = axis_confidence(state, om, archived_weeks=archived_weeks)
        row.update({"confidence": conf["confidence"], "confidence_exposures": conf["exposures"],
                    "confidence_min_exposures": conf["min_required"]})
        row.update(axis_trend(state, om))
        gap = retest_gap_days(conf["confidence"])
        row["earliest_retest"] = (_as_date(om["date"]) + timedelta(days=gap)).isoformat()
        sig = axis_signals(state, axis, om)
        row["signals"] = {"count": sig["count"], "needed": sig["needed"]}
        try:
            from backend.engine.anchored_load import fatigue_for

            row["fatigue"] = fatigue_for(state, axis, td)
        except Exception:  # pragma: no cover - defensive: status must never break GET /week
            row["fatigue"] = None
        row["next_test"] = None
        row["next_test_reason"] = None
        if not row["covered"]:
            row["next_test_reason"] = "not_tested_recently"
            out_axes[axis] = row
            continue
        planned = _planned_axis_tests(state, axis, since=td)
        if planned:
            p = planned[0]
            trig, reason = _planned_reason(state, axis, p)
            if trig is None:
                # A test placed before A289 (or by hand): explain it with the
                # policy's own reading of that week when the policy agrees.
                pdec = _axis_week_decision(state, axis, _monday(_as_date(p["date"])), today=None,
                                           finger_device=finger_device, archived_weeks=archived_weeks,
                                           check_already_scheduled=False)
                if pdec and pdec.get("status") == "due" and p["date"] in pdec["allowed_dates"]:
                    trig, reason = pdec["trigger"], pdec["reason"]
            row["next_test"] = {
                "date": p["date"], "session_id": p["session_id"], "source": "planned",
                "trigger": trig, "reason": reason,
                "blockers": test_day_blockers(state, axis, p["date"], archived_weeks=archived_weeks,
                                              outdoor_rows=outdoor_rows),
            }
            out_axes[axis] = row
            continue
        ws = _monday(td)
        last_skip = None
        for k in range(max(1, horizon_weeks)):
            wk = ws + timedelta(days=7 * k)
            dec = _axis_week_decision(state, axis, wk, today=td, finger_device=finger_device,
                                      archived_weeks=archived_weeks, check_already_scheduled=False)
            if dec is None:
                last_skip = "not_tested_recently"
                break
            if dec["status"] == "due" and _hot_plan(state, wk.isoformat()) is not None:
                # The week is already generated and holds no planned test of
                # this axis: cached weeks are never regenerated, so projecting
                # it there would promise a test that never comes (A289 review).
                last_skip = _generated_week_skip(state, axis, wk, td)
                continue
            if dec["status"] == "due":
                row["next_test"] = {
                    "date": dec["allowed_dates"][0], "session_id": dec["session_id"],
                    "source": "projected", "trigger": dec["trigger"], "reason": dec["reason"],
                    "week_start": wk.isoformat(), "blockers": [],
                }
                break
            if dec["status"] == "skipped":
                last_skip = dec["skip_reason"]
        if row["next_test"] is None:
            row["next_test_reason"] = last_skip or "not_due_within_horizon"
        out_axes[axis] = row
    return {
        "as_of": td.isoformat(),
        "stable_band_pct": TREND_STABLE_PCT,
        "axes": out_axes,
        "covered_axes": [a for a in RETEST_AXES if out_axes.get(a, {}).get("covered")],
    }


def _generated_week_skip(state: Mapping[str, Any], axis: str, wk: date, today: date) -> str:
    """Why a generated week has no upcoming test of ``axis`` although the
    policy would call it due: what PASS 3a recorded, else ``not_in_plan``
    (week generated before A289, or the slot was lost to a regeneration)."""
    snap = ((_hot_plan(state, wk.isoformat()) or {}).get("profile_snapshot") or {}).get("retest_decisions") or {}
    for req in snap.get("required_sessions") or []:
        if not isinstance(req, Mapping) or req.get("axis") != axis:
            continue
        if req.get("status") == "skipped" and req.get("skip_reason"):
            return str(req["skip_reason"])
        if req.get("status") == "placed" and str(req.get("placed_date") or "") < today.isoformat():
            return "missed"
    for sk in snap.get("skipped") or []:
        if isinstance(sk, Mapping) and sk.get("axis") == axis and sk.get("skip_reason"):
            return str(sk["skip_reason"])
    return "not_in_plan"


def _planned_reason(state: Mapping[str, Any], axis: str, planned: Mapping[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Trigger + reason the planner stored for a planned test
    (``profile_snapshot.retest_decisions``), else (None, None)."""
    ws = _monday(_as_date(planned["date"])).isoformat()
    plan = _hot_plan(state, ws)
    snap = ((plan or {}).get("profile_snapshot") or {}).get("retest_decisions") or {}
    for req in snap.get("required_sessions") or []:
        if isinstance(req, Mapping) and req.get("axis") == axis:
            return req.get("trigger"), req.get("reason")
    return None, None


__all__ = [
    "TEST_FRESH_DAYS", "LOW_CONF_MIN_EXPOSURES", "LOW_CONF_WINDOW_D", "LOW_CONF_RETEST_D",
    "REENTRY_GAP_D", "REENTRY_FACTORS", "REENTRY_FULL_FACTOR", "HANG_PCT_PER_S",
    "FINGER_GAP_H", "RETEST_BLOCK_H", "PULL_TEST_BLOCK_H", "HEAVY_PULL_PCT_1RM",
    "VERY_HARD_BLOCK_D", "PRE_TRIP_BLOCK_D", "RETEST_BLOCKED_PHASES",
    "PROTOCOL_HANG_7S", "PROTOCOL_HANG_5S", "PROTOCOL_PULLUP_2RM", "PROTOCOL_FAMILY",
    "EXERCISE_PROTOCOL", "convert_hang_seconds", "official_max", "is_tested",
    "test_confidence", "reentry_factor", "reentry_step", "is_heavy_pulling_session",
    "is_pulling_hard_session",
    # A289
    "AXIS_FINGER", "AXIS_PULLING", "RETEST_AXES", "AXIS_TEST_SESSION", "AXIS_PROTOCOL",
    "AXIS_TEST_SESSIONS_ALL", "HIGH_CONF_RETEST_D", "MAINTENANCE_RETEST_D", "EARLY_RETEST_SIGNALS",
    "STATUS_HORIZON_WEEKS", "TREND_STABLE_PCT", "TRIGGER_END_OF_PHASE", "TRIGGER_END_OF_PHASE_SLIPPED",
    "TRIGGER_CYCLE_START", "TRIGGER_MAINTENANCE", "TRIGGER_EARLY", "retest_gap_days",
    "axis_official", "axis_confidence", "axis_trend", "axis_signals", "very_hard_dates",
    "trip_blocked", "retest_decisions", "test_day_blockers", "retest_status",
]
