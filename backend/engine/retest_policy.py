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
#: Floor of the EARLY retest only (``early_retest``: EARLY_RETEST_SIGNALS
#: measured sessions above the max): it may come this many days after the last
#: test. A319: no longer the gap after a low-confidence test — every other test
#: waits HIGH_CONF_RETEST_D, whatever its confidence. Name and value kept.
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
# day, heavy pulling) — see ``planner_v2`` PASS 3. B400: "its in-week sessions"
# are the week as the regeneration merge will save it, the user's sessions
# included; a test the merge keeps in that week counts as already scheduled.
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
#   cycle_start            first week of a macrocycle
#   maintenance            MAINTENANCE_RETEST_D since the last test
#   early_retest           EARLY_RETEST_SIGNALS measured sessions above the max
#                          (``progression_counters.retest_signals``, B364)
# Week blockers: performance / deload phase, gap since the last test:
# HIGH_CONF_RETEST_D after ANY test (A319: the confidence is still computed
# and shown, it no longer moves a date), LOW_CONF_RETEST_D for the early
# retest only. An end-of-phase week the gap keeps out of reach is
# ``blocked:gap`` — A319 removed the one-week slip (``end_of_phase_slipped``,
# "option B" of 2026-10-04): the next test comes with the next trigger. A319
# review: a trigger the gap keeps out of the week yields to the early retest
# when that one's own floor falls in the week (its evidence is not lost).
# Day blockers: ≤ PRE_TRIP_BLOCK_D days before a trip (or during
# it), very_hard feedback in the VERY_HARD_BLOCK_D days before, a finger-hard
# day < RETEST_BLOCK_H before a hang test, a heavy pull < PULL_TEST_BLOCK_H
# before a pull-up test, pain >= 2 on the axis zone in the PAIN_BLOCK_D days
# before (or a pain block still running, A295).
#
# Hours → days: the planner works in whole days (one session per slot, slots
# are not timed), so "< 72 h after X" means "fewer than 3 calendar days after
# the day of X" and "< 48 h" means "fewer than 2". A session two days earlier
# in the same slot is exactly 48 h away and does NOT block a pull-up test.
#
# Declines (A320). The athlete (or the coach, with the athlete's OK) declines
# the pending test of an axis or postpones it — POST /api/retest/decline
# stores a record in ``state["retest_declines"]``. A record is ACTIVE while
# its ``official_date`` is the axis' official max date: a new test makes it
# inert and the next trigger proposes the test again. Re-proposal rules:
#   decline   suppresses its own trigger kind — end_of_phase / cycle_start
#             only in the macrocycle it was declined in (``macrocycle_start``:
#             the next cycle's cycle_start comes back); the early retest is
#             suppressed by ANY active decline until EARLY_RETEST_SIGNALS
#             measured signals are dated after ``declined_at`` (signals that
#             were already there never override a decline). A trigger of
#             another kind still fires (a decline of the end-of-phase test
#             does not stop the 84-day maintenance).
#   postpone  "not before ``until``": every week entirely before ``until`` is
#             skipped ``postponed``; from the week holding ``until`` on, the
#             test is due from ``until`` with the trigger ``postponed`` (a
#             natural trigger that is not declined keeps its own name), in
#             every covered week until a new test. The endpoint takes an
#             ``until`` only after the pending test's own day, and a later
#             decline ends the postpone (``retest_declines.upsert``).
# Implicit decline: a policy test the USER removed or replaced in a week
# (the plan's removal records — not a move, not an automatic A315
# re-schedule, not an extra test of their own taken back while the policy's
# is still there) declines the axis for THAT week (``source: plan_edit``),
# derived from the plan every time, never stored: the regeneration does not
# put it back on another day of the week (B382's D1 does not apply to it).
# It is read before the stored records of the week, so the regenerated
# snapshot always carries it. The way back is an explicit add: a test of the
# axis the athlete puts back in the week, still to do, lifts it.
# A declined axis is ``skipped`` (``declined`` / ``postponed``), NEVER None:
# None would uncover it, and the legacy PASS 3 / test_queue would schedule
# the test (and GET /api/week show the 6-week reminder again).
# ``inject_tests`` (an explicit "I want tests": onboarding, start-new-cycle,
# the test-reminder confirm) bypasses the policy by design — declines are not
# consulted there.

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
#: A319: both max tests in ONE session (max hang 7 s, then the weighted
#: pull-up 2RM, then the secondary measurements). PASS 3a places it when both
#: axes are due and no day offers two ordered slots — never the two tests on
#: two days. It tests BOTH axes. The id is load-bearing: ``test_`` (test log,
#: ``is_test_session``), ``test_max`` (key_sessions_v1 pending tests),
#: ``test_max_hang`` (finger-test prefixes) and ``pullup`` (composer guard).
COMBINED_TEST_SESSION = "test_max_hang_pullup"
#: Sessions that test an axis (for "is a test already planned"). The combined
#: one is listed under both axes.
AXIS_TEST_SESSIONS_ALL: Dict[str, Tuple[str, ...]] = {
    AXIS_FINGER: ("test_max_hang_7s", "test_max_hang_5s", "test_lp_max_5s", COMBINED_TEST_SESSION),
    AXIS_PULLING: ("test_max_weighted_pullup", "test_pullup_bw", COMBINED_TEST_SESSION),
}
#: Exercises whose measured sessions feed ``retest_signals`` per axis.
AXIS_SIGNAL_EXERCISES: Dict[str, Tuple[str, ...]] = {
    AXIS_FINGER: ("max_hang_7s", "max_hang_5s"),
    AXIS_PULLING: ("weighted_pullup", "weighted_chinup"),
}

#: Gap after ANY test (the planner's historical 42-day freshness). A319: the
#: confidence no longer shortens it — only the early retest has its own
#: floor (LOW_CONF_RETEST_D).
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
#: LEGACY (A319): the one-week slip of the end-of-phase test is gone and this
#: trigger is never produced again. Snapshots written before A319 still carry
#: it (``profile_snapshot.retest_decisions``, e.g. Daniele's week 2026-10-19 in
#: prod), with ``skip_reason: slipped:gap`` + ``slipped_to_week`` on the week
#: before: the readers pass them through as stored (``_planned_reason``,
#: ``_generated_week_skip``).
TRIGGER_END_OF_PHASE_SLIPPED = "end_of_phase_slipped"
TRIGGER_CYCLE_START = "cycle_start"
TRIGGER_MAINTENANCE = "maintenance"
TRIGGER_EARLY = "early_retest"
#: A320: a postponed test, due from the athlete's ``until`` on (lowest priority:
#: a natural trigger that is not declined keeps its own name).
TRIGGER_POSTPONED = "postponed"

_TRIGGER_TEXT: Dict[str, str] = {
    TRIGGER_END_OF_PHASE: "End of the strength phase: measure what the block built.",
    TRIGGER_CYCLE_START: "New cycle: a fresh baseline for the loads.",
    TRIGGER_MAINTENANCE: "12 weeks since the last test: keep the max honest.",
    TRIGGER_EARLY: "Two measured sessions above your tested max: time to raise it.",
    TRIGGER_POSTPONED: "You postponed this test to {until}.",
}

#: A320 — declines (see the comment block above). Top-level state key, owned
#: by POST/DELETE /api/retest/decline (not writable through PUT /api/state).
DECLINES_KEY = "retest_declines"
DECLINE_KIND_DECLINE = "decline"
DECLINE_KIND_POSTPONE = "postpone"
DECLINE_KINDS = (DECLINE_KIND_DECLINE, DECLINE_KIND_POSTPONE)
#: Closed sets of a stored record: the reason CODE is all the decisions, the
#: snapshot, retest_status and the coach ever see of a decline (the free-text
#: note stays in the record), and who asked.
DECLINE_REASONS = ("fatigue", "injury", "illness", "travel", "schedule", "not_needed", "other")
DECLINE_SOURCES = ("app", "coach", "cli")
#: ``source`` of an implicit decline: the athlete removed / replaced the test
#: in the week's plan (never stored; the stored sources are app | coach | cli).
DECLINE_SOURCE_PLAN_EDIT = "plan_edit"
#: skip_reason / next_test_reason of a declined / postponed axis.
SKIP_DECLINED = "declined"
SKIP_POSTPONED = "postponed"
_DECLINE_SKIPS = (SKIP_DECLINED, SKIP_POSTPONED)
#: Triggers tied to one week of one macrocycle: a decline matches them only in
#: the macrocycle it was declined in.
_WEEK_BOUND_TRIGGERS = (TRIGGER_END_OF_PHASE, TRIGGER_CYCLE_START)
#: The triggers a record can carry (the pending test's, normalized).
_DECLINE_TRIGGERS = (TRIGGER_END_OF_PHASE, TRIGGER_CYCLE_START, TRIGGER_MAINTENANCE, TRIGGER_EARLY,
                     TRIGGER_POSTPONED)
#: B369's flag on a cached week the next GET /api/week regenerates
#: (``deps.STALE_KEY``; the engine never imports the API layer).
_STALE_KEY = "_stale"

_DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def retest_gap_days(confidence: Optional[str]) -> int:
    """Days before a test of the same axis may be repeated: HIGH_CONF_RETEST_D
    after any test.

    A319 (decision of 2026-10-18): the confidence of the last test is still
    computed and shown, it no longer moves any date — a low-confidence test
    used to be repeatable after LOW_CONF_RETEST_D, which put two tests of an
    axis four weeks apart. Only the early retest keeps that floor (measured
    evidence, ``_axis_week_decision``). The parameter stays for the callers."""
    return HIGH_CONF_RETEST_D


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


#: A295 review (R4 hand-off): pain ≥ 2 on the axis zone in the PAIN_BLOCK_D
#: days before a test — or a pain block still running on the test day — keeps
#: the test of that axis off the day. Same zones as the anchored read side.
PAIN_BLOCK_D = 7
PAIN_AXIS_SITES: Dict[str, Tuple[str, ...]] = {
    AXIS_FINGER: ("fingers", "other"), AXIS_PULLING: ("elbow", "shoulder", "other"),
}


def pain_blocked(state: Mapping[str, Any], axis: str, d: date) -> Optional[Dict[str, Any]]:
    """The pain block that keeps a test of ``axis`` off day ``d``, or None."""
    blocks = ((state.get("progression_counters") or {}).get("pain_blocks") or {})
    if not isinstance(blocks, Mapping):
        return None
    for site in PAIN_AXIS_SITES.get(axis, ()):
        b = blocks.get(site)
        if not isinstance(b, Mapping):
            continue
        start, until = _parse_date(b.get("from")), _parse_date(b.get("until"))
        score = _num(b.get("score")) or 0
        if start is None or score < 2:
            continue
        end = max(until or start, start + timedelta(days=PAIN_BLOCK_D))
        if start <= d <= end:
            return {"site": site, "score": int(score), "from": start.isoformat(), "until": end.isoformat()}
    return None


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
    generated week (A289 review): the old plan's preserved sessions take
    their slot, and today is copied wholesale when it holds a done session.
    A test placed there would be silently overwritten after generation.
    B369: preserved = done/skipped or user-owned (``user_owned.is_preservable``),
    the same predicate the merge uses. B369 review: the merge also drops the
    engine sessions the user took out — every slot of a date replaced wholesale
    (``whole_day_override_dates``) and the slots of the recorded removals
    (``removed_refs``) — so a test placed there would vanish just the same.
    B379: the dates replaced wholesale are ``engine_free_dates`` — the
    whole-day overrides plus every outdoor day declared on the plan (the merge
    copies those back as they were: a test is never placed on a crag day)."""
    from backend.engine.user_owned import engine_free_dates, is_preservable, removed_refs

    slots: List[Dict[str, Any]] = []
    dates: List[str] = []
    plan = _hot_plan(state, ws.isoformat())
    test_ids = {sid for sids in AXIS_TEST_SESSIONS_ALL.values() for sid in sids}

    def _future(d_iso: str) -> bool:
        d = _parse_date(d_iso)
        return d is not None and (today is None or d >= today)

    for d_iso in engine_free_dates(plan or {}):
        if _future(d_iso[:10]) and d_iso[:10] not in dates:
            dates.append(d_iso[:10])
    for d_iso, ref, slot in removed_refs(plan or {}):
        d_iso = d_iso[:10]
        if not _future(d_iso):
            continue
        if slot:
            slots.append({"date": d_iso, "slot": slot})
        elif ref in test_ids and d_iso not in dates:
            # A test the user removed by id: the same id is dropped there again.
            dates.append(d_iso)
    for day in _plan_days(plan):
        d_iso = str(day.get("date") or "")[:10]
        d = _parse_date(d_iso)
        if d is None or (today is not None and d < today):
            continue
        sessions = [x for x in (day.get("sessions") or []) if isinstance(x, Mapping)]
        if today is not None and d == today and (
            any(x.get("status") == "done" for x in sessions)
            or day.get("outdoor_session_status") == "done"
        ):
            if d_iso not in dates:
                dates.append(d_iso)
            continue
        for x in sessions:
            if is_preservable(x) and x.get("slot"):
                slots.append({"date": d_iso, "slot": x.get("slot")})
    return {"locked_slots": slots, "locked_dates": dates}


def _merge_wholesale_dates(plan: Optional[Mapping[str, Any]], today: Optional[date]) -> set:
    """B400: the days of *plan* the B369 merge (``_merge_user_content``) copies
    back wholesale over a regenerated week, whatever the planner generates
    there: the days the user owns wholesale (``engine_free_dates``: an outdoor
    day declared on the plan, a whole-day override) and ``today`` when it holds
    a done session or a done outdoor day. The days before ``today`` are copied
    too, but they are past: no caller asks about them."""
    from backend.engine.user_owned import engine_free_dates

    out = {str(d)[:10] for d in engine_free_dates(plan or {})}
    if today is None:
        return out
    for day in _plan_days(plan):
        if str(day.get("date") or "")[:10] != today.isoformat():
            continue
        sessions = [x for x in (day.get("sessions") or []) if isinstance(x, Mapping)]
        if any(x.get("status") == "done" for x in sessions) or day.get("outdoor_session_status") == "done":
            out.add(today.isoformat())
    return out


def _planned_axis_tests(
    state: Mapping[str, Any],
    axis: str,
    *,
    since: date,
    exclude_week: Optional[str] = None,
    today: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Not-yet-done, not-skipped tests of ``axis`` dated ≥ ``since`` in the hot
    week plans.

    ``exclude_week`` = the week being regenerated: the regeneration replaces
    the engine's tests of that week, so they do not count — except the ones the
    B369 merge puts back (B400): a test the user owns (moved, forced, re-
    scheduled…: ``user_owned.is_user_owned``) and a test on a day the merge
    copies wholesale (``_merge_wholesale_dates``: ``today`` with a done session,
    a day the user owns wholesale). Before B400 those were dropped too, and
    PASS 3a placed a second test next to the one the merge kept."""
    from backend.engine.stimulus import iter_plan_days
    from backend.engine.user_owned import is_user_owned

    sids = AXIS_TEST_SESSIONS_ALL[axis]
    kept_days = _merge_wholesale_dates(_hot_plan(state, exclude_week), today) if exclude_week else set()
    rows = []
    for d, day, _src in iter_plan_days(state):
        if d < since.isoformat():
            continue
        regenerated = bool(exclude_week) and _monday(_as_date(d)).isoformat() == exclude_week
        for session in day.get("sessions") or []:
            if not isinstance(session, dict) or session.get("session_id") not in sids:
                continue
            if session.get("status") in ("done", "skipped"):
                continue
            if regenerated and not (is_user_owned(session) or d in kept_days):
                continue
            rows.append({"date": d, "session_id": session.get("session_id"), "slot": session.get("slot")})
    return sorted(rows, key=lambda r: (r["date"], str(r["slot"] or "")))


def _early_retest_day(signals: Mapping[str, Any], we: date) -> Optional[date]:
    """The early retest's own first day — the day after the last of
    EARLY_RETEST_SIGNALS measured signals — when it comes by ``we``, else None
    (the gap since the last test is the caller's)."""
    if signals.get("count", 0) >= EARLY_RETEST_SIGNALS and signals.get("last_date"):
        t_e = _as_date(signals["last_date"]) + timedelta(days=1)
        if t_e <= we:
            return t_e
    return None


# ---------------------------------------------------------------------------
# A320 — declines (record management: ``backend.engine.retest_declines``)
# ---------------------------------------------------------------------------

def normalize_trigger(trigger: Any) -> Optional[str]:
    """The trigger a decline is keyed on: the legacy ``end_of_phase_slipped``
    (pre-A319 snapshots) is the end-of-phase test."""
    if not trigger:
        return None
    trigger = str(trigger)
    return TRIGGER_END_OF_PHASE if trigger == TRIGGER_END_OF_PHASE_SLIPPED else trigger


def axis_declines(state: Mapping[str, Any], axis: str, om: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    """The ACTIVE stored declines of ``axis``: same axis, ``official_date`` the
    official max ``om`` the policy reads (a newer test makes a record inert)."""
    out: List[Mapping[str, Any]] = []
    for rec in state.get(DECLINES_KEY) or []:
        if (isinstance(rec, Mapping) and rec.get("axis") == axis and rec.get("kind") in DECLINE_KINDS
                and str(rec.get("official_date") or "")[:10] == str(om.get("date"))):
            out.append(rec)
    return out


def decline_view(rec: Mapping[str, Any]) -> Dict[str, Any]:
    """What the decisions, the snapshot and retest_status show of a decline: the
    reason CODE only — never the free-text note (it would land in persisted
    snapshots and in the coach prompt). A reason or source outside its closed
    set (a record carried in by an import, which only checks the list) reads
    ``other`` / None, and so does (None) a trigger, axis or kind outside
    theirs or a date that is not an ISO date (A320 review): no free text goes
    out through any field."""
    reason, source = rec.get("reason"), rec.get("source")
    trigger = normalize_trigger(rec.get("trigger"))
    declined_at, until = _parse_date(rec.get("declined_at")), _parse_date(rec.get("until"))
    return {
        "axis": rec.get("axis") if rec.get("axis") in RETEST_AXES else None,
        "kind": rec.get("kind") if rec.get("kind") in DECLINE_KINDS else None,
        "trigger": trigger if trigger in _DECLINE_TRIGGERS else None,
        "reason": reason if reason in DECLINE_REASONS else "other",
        "declined_at": declined_at.isoformat() if declined_at else None,
        "until": until.isoformat() if until else None,
        "source": source if source in DECLINE_SOURCES else None,
    }


def _active_postpone(declines: Sequence[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    """The active postpone with the latest ``until`` (the athlete's last "not
    before"), or None."""
    best: Optional[Mapping[str, Any]] = None
    for rec in declines:
        if rec.get("kind") != DECLINE_KIND_POSTPONE or _parse_date(rec.get("until")) is None:
            continue
        if best is None or _as_date(rec["until"]) > _as_date(best["until"]):
            best = rec
    return best


def _matching_decline(
    declines: Sequence[Mapping[str, Any]],
    trigger: str,
    macrocycle: Mapping[str, Any],
    signals: Mapping[str, Any],
) -> Optional[Mapping[str, Any]]:
    """The active ``decline`` record that suppresses ``trigger``, or None.

    Same kind; a week-bound kind (end_of_phase, cycle_start) only in the
    macrocycle it was declined in. The early retest is suppressed by any
    active decline until EARLY_RETEST_SIGNALS measured signals are dated
    after its ``declined_at``."""
    for rec in declines:
        if rec.get("kind") != DECLINE_KIND_DECLINE:
            continue
        if trigger == TRIGGER_EARLY:
            at = str(rec.get("declined_at") or "")[:10]
            fresh = [d for d in signals.get("dates") or [] if str(d)[:10] > at]
            if len(fresh) < EARLY_RETEST_SIGNALS:
                return rec
            continue
        if normalize_trigger(rec.get("trigger")) != trigger:
            continue
        if trigger in _WEEK_BOUND_TRIGGERS and rec.get("macrocycle_start") != macrocycle.get("start_date"):
            continue
        return rec
    return None


def is_policy_test(session: Any) -> bool:
    """A320: a test this policy placed — PASS 3a stamps its entry's ``explain``
    with ``retest:<trigger>`` (``retest:<axis>:<trigger>`` on the combined
    session), and nothing else does. A test of an axis the policy does not
    cover (the historical PASS 3, ``test_queue``, ``inject_tests``, a
    quick-add) is not one: an untested athlete's plans stay as they were."""
    if not isinstance(session, Mapping):
        return False
    return any(isinstance(e, str) and e.startswith("retest:") for e in session.get("explain") or [])


def plan_edit_removal(
    plan: Optional[Mapping[str, Any]],
    axis: str,
    *,
    today: Optional[date] = None,
) -> Optional[Dict[str, Any]]:
    """A320: the first record of *plan* where the USER removed or replaced a
    test of ``axis`` — ``{date, slot, session_id}`` — or None.

    Read from the plan's own removal records (``user_owned.removal_records``):
    a ``remove_session``, a day override that replaced it, an
    ``add_planned_session`` key re-schedule in its place, a move that
    overwrote it at the target. NOT the source side of a move (the test still
    exists: B400 counts it where it landed) and NOT an automatic A315
    re-schedule (``auto``: the engine's action, not the athlete's). The combined
    test counts for both axes. A record that names only a slot (a whole-day
    override, a removal by slot) matches the test PASS 3a placed there
    (snapshot ``placed_date`` / ``placed_slot``) — or, once the week was
    regenerated without it, the plan-edit decline that regeneration recorded
    for that date (snapshot ``skipped``). None as well when the athlete put a
    test of the axis back in the week (an explicit add, a forced or moved
    test, still to do from ``today`` on — a past one never done is no way
    back): that is the way back, and B400 counts that test where it is.

    A320 review: the removal of the athlete's OWN test (``removed_owned``: an
    extra test they had added) declines the axis only when no test of the axis
    is left to do in the week — taking back an extra test is not declining the
    policy's one; the policy's test that the athlete moved and then removed
    still is. ``today`` None reads every day of the week."""
    from backend.engine.user_owned import is_user_owned, removal_records

    if not isinstance(plan, Mapping):
        return None
    sids = AXIS_TEST_SESSIONS_ALL[axis]
    floor = today.isoformat() if today is not None else ""
    left = False  # a test of the axis still to do in the week (the engine's)
    for day in _plan_days(plan):
        if str(day.get("date") or "")[:10] < floor:
            continue
        for s in day.get("sessions") or []:
            if not isinstance(s, Mapping) or s.get("session_id") not in sids \
                    or s.get("status") in ("done", "skipped"):
                continue
            if is_user_owned(s):
                return None
            left = True
    snap = (plan.get("profile_snapshot") or {}).get("retest_decisions") or {}
    placed: Dict[Tuple[str, Any], Any] = {}
    for row in snap.get("required_sessions") or []:
        if isinstance(row, Mapping) and row.get("axis") == axis and row.get("status") == "placed":
            placed[(str(row.get("placed_date") or "")[:10], row.get("placed_slot"))] = row.get("session_id")
    carried = set()
    for row in snap.get("skipped") or []:
        if not isinstance(row, Mapping) or row.get("axis") != axis or row.get("skip_reason") != SKIP_DECLINED:
            continue
        view = row.get("declined")
        if isinstance(view, Mapping) and view.get("source") == DECLINE_SOURCE_PLAN_EDIT:
            carried.add(str(view.get("declined_at") or "")[:10])
    auto = set()
    for a in plan.get("adaptations") or []:
        ev = a.get("event") if isinstance(a, Mapping) and a.get("type") == "event" else None
        if isinstance(ev, Mapping) and ev.get("event_type") == "add_planned_session" and ev.get("auto"):
            auto.add((str(ev.get("target_date") or "")[:10], ev.get("replaced_slot") or ev.get("slot"),
                      ev.get("replaced_session_id")))
    for rec in removal_records(plan):
        if rec.get("kind") not in ("removed", "replaced"):
            continue
        d = str(rec.get("date") or "")[:10]
        if rec["kind"] == "replaced" and (d, rec.get("slot"), rec.get("ref")) in auto:
            continue
        if rec.get("owned") and left:
            continue  # an extra test of the athlete's taken back: the policy's is still there
        if rec.get("ref"):
            sid = rec["ref"] if rec["ref"] in sids else None
        else:
            sid = placed.get((d, rec.get("slot")))
            if sid is None and d in carried:
                sid = AXIS_TEST_SESSION[axis]
        if sid is not None:
            return {"date": d, "slot": rec.get("slot"), "session_id": sid}
    return None


def _plan_edit_view(axis: str, trigger: Optional[str], removal: Mapping[str, Any]) -> Dict[str, Any]:
    return {"axis": axis, "kind": DECLINE_KIND_DECLINE, "trigger": trigger, "reason": None,
            "declined_at": removal.get("date") or None, "until": None, "source": DECLINE_SOURCE_PLAN_EDIT}


def _trigger_reason(trigger: str, postpone: Optional[Mapping[str, Any]] = None) -> str:
    until = _parse_date((postpone or {}).get("until"))
    return _TRIGGER_TEXT[trigger].format(until=until.isoformat() if until else None)


def _trigger_for_week(
    macrocycle: Mapping[str, Any],
    ws: date,
    last: date,
    signals: Mapping[str, Any],
    skip: Sequence[str] = (),
) -> Tuple[Optional[str], Optional[date]]:
    """(trigger, trigger_earliest) for the week starting ``ws``, or (None, None).

    ``trigger_earliest`` is the first day the trigger itself allows (the
    early retest waits for the day after its last signal); the gap since the
    last test is applied by the caller. A319: no slip — the week after the
    end-of-phase week is never a trigger of its own. A320: the kinds in
    ``skip`` (declined by the athlete) are passed over; the default is the
    pre-A320 reading.
    """
    from backend.engine.macro_position import position_on

    we = ws + timedelta(days=6)
    pos = position_on(dict(macrocycle), ws.isoformat())
    if not pos or pos["before_start"] or pos["after_end"]:
        return None, None
    if TRIGGER_END_OF_PHASE not in skip and pos["phase_id"] == "strength_power" \
            and pos["is_last_week_of_phase"] and last < ws:
        return TRIGGER_END_OF_PHASE, ws
    if TRIGGER_CYCLE_START not in skip and pos["abs_week"] == 1 and last < ws:
        return TRIGGER_CYCLE_START, ws
    t_e = _early_retest_day(signals, we) if TRIGGER_EARLY not in skip else None
    if t_e is not None:
        return TRIGGER_EARLY, t_e
    maint = last + timedelta(days=MAINTENANCE_RETEST_D)
    if TRIGGER_MAINTENANCE not in skip and maint <= we:
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
    depend on which week the athlete opens first (A289 review).

    A320: a declined / postponed axis is ``skipped`` (``declined`` /
    ``postponed``, with the ``declined`` view), decided before the phase, gap
    and already-scheduled checks — never ``None``: the axis stays covered."""
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
    we = ws + timedelta(days=6)
    # A320: the athlete's active declines of this test (the trigger comment
    # block above). A week entirely before a postponed date has no test.
    declines = axis_declines(state, axis, om)
    postpone = _active_postpone(declines)
    held = postpone is not None and _as_date(postpone["until"]) > we
    skip: List[str] = []
    suppressed: Optional[Tuple[str, Mapping[str, Any]]] = None
    # Each pass skips one more kind, so it ends within the number of kinds; the
    # bound only guards a request against a kind that would ignore ``skip``.
    for _ in range(len(_TRIGGER_TEXT)):
        trigger, t_earliest = _trigger_for_week(macrocycle, ws, last, signals, skip=skip)
        rec = _matching_decline(declines, trigger, macrocycle, signals) if trigger else None
        if rec is None:
            break
        suppressed = suppressed or (trigger, rec)
        skip.append(trigger)
    else:
        trigger, t_earliest = None, None
    if trigger is None and postpone is not None and not held:
        trigger, t_earliest = TRIGGER_POSTPONED, _as_date(postpone["until"])
    if trigger is not None or suppressed is not None or held:
        # A320: the athlete took the policy's test out of this week's plan. Read
        # before the stored declines (A320 review): the plan-edit view is the
        # one the regenerated snapshot carries, which keeps a slot-only removal
        # (a whole-day override) matching after the regeneration — and a DELETE
        # of the stored record never reopens the week.
        edit = plan_edit_removal(_hot_plan(state, ws.isoformat()), axis, today=today)
        if edit is not None:
            trig = trigger or (suppressed[0] if suppressed is not None else TRIGGER_POSTPONED)
            return {**base, "trigger": trig, "reason": _trigger_reason(trig, postpone), "status": "skipped",
                    "skip_reason": SKIP_DECLINED, "declined": _plan_edit_view(axis, trig, edit)}
    if held:
        return {**base, "trigger": TRIGGER_POSTPONED, "reason": _trigger_reason(TRIGGER_POSTPONED, postpone),
                "status": "skipped", "skip_reason": SKIP_POSTPONED, "declined": decline_view(postpone)}
    if trigger is None and suppressed is not None:
        return {**base, "trigger": suppressed[0], "reason": _trigger_reason(suppressed[0]), "status": "skipped",
                "skip_reason": SKIP_DECLINED, "declined": decline_view(suppressed[1])}
    if trigger is None:
        return {**base, "status": "not_due"}
    if trigger != TRIGGER_EARLY and max(earliest, t_earliest or ws, ws) > we:
        # A319 review: the gap keeps this week's trigger (end of phase, cycle
        # start) out of reach, but the measured evidence of an early retest
        # has its own floor: when that floor falls in the week, the early
        # retest takes the week. Before, it came the week after — the end of
        # the strength phase lost one week to a trigger that could not run.
        # A320: not an early retest the athlete declined.
        t_e = _early_retest_day(signals, we)
        if t_e is not None and max(last + timedelta(days=LOW_CONF_RETEST_D), t_e, ws) <= we \
                and _matching_decline(declines, TRIGGER_EARLY, macrocycle, signals) is None:
            trigger, t_earliest = TRIGGER_EARLY, t_e
    if trigger == TRIGGER_EARLY:
        # Measured evidence says the max is too low: only the early retest's
        # own floor applies (A319: the row says so, gap_days included).
        earliest = last + timedelta(days=LOW_CONF_RETEST_D)
        base["earliest_date"] = earliest.isoformat()
        base["gap_days"] = LOW_CONF_RETEST_D
    first = max(earliest, t_earliest or ws, ws)
    if postpone is not None:
        # A320: never before the day the athlete postponed the test to.
        first = max(first, _as_date(postpone["until"]))
    out = {**base, "trigger": trigger, "reason": _trigger_reason(trigger, postpone)}
    pos = position_on(dict(macrocycle), ws.isoformat()) or {}
    if pos.get("phase_id") in RETEST_BLOCKED_PHASES:
        return {**out, "status": "skipped", "skip_reason": "blocked:phase"}
    if first > we:
        # A319: the gap keeps the whole week out of reach — skipped, also at
        # the end of the strength phase (no slip to the week after).
        return {**out, "status": "skipped", "skip_reason": "blocked:gap"}
    if check_already_scheduled:
        planned = _planned_axis_tests(state, axis, since=today or ws, exclude_week=ws.isoformat(),
                                      today=today)
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
        elif pain_blocked(state, axis, d) is not None:
            last_block = "blocked:pain"
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
    mid-week regeneration preserves done sessions after generating). B400: the
    rest of the week — the user's planned sessions the merge puts back — PASS
    3a reads itself, on the merge preview of the week."""
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
                                    # A320: + ``declined`` {axis, kind, trigger, reason,
                                    # declined_at, until, source} on a declined /
                                    # postponed axis (skip_reason declined | postponed)
          "already_scheduled": [{axis, date, trigger}],  # B400: + tests the merge keeps
          "axes": {axis: <week-level decision>},
          "finger_hard_dates": [...], "heavy_pull_dates": [...],
          "locked_slots": [{date, slot}], "locked_dates": [...],
          "block_hours": {"hang": 72, "pull": 48},
          "as_of": today,                # B400 review: PASS 3a's lived-day boundary
        }

    Pure: everything derives from the state (macrocycle, tests, trips,
    feedback_log, progression_counters, week plans, A320 ``retest_declines``),
    the archived weeks and outdoor rows passed in, and ``today`` — never
    ``date.today()``. A320: PASS 3a copies a ``skipped`` row as it is into the
    week's snapshot (``declined`` view included) and its ``skip_reason`` /
    ``trigger`` into ``skipped_tests`` — planner_v2 unchanged.
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
        # A319: one day always — PASS 3a falls back to the combined session
        # (COMBINED_TEST_SESSION) when no day has two ordered slots.
        required[0]["paired_with"] = required[1]["session_id"]
        required[1]["paired_with"] = required[0]["session_id"]
    skipped = [
        {k: dec.get(k) for k in ("axis", "session_id", "trigger", "reason", "skip_reason",
                                 "earliest_date", "deferred_to_week", "declined")
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
        # B400 review: the day these decisions were taken on. PASS 3a counts
        # the days before it as lived; the planner's own ``today`` can be a
        # later regeneration floor ("regenerate from tomorrow"). Not stored
        # in the week's profile_snapshot.
        "as_of": td.isoformat() if td else None,
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
    pain = pain_blocked(state, axis, d)
    if pain is not None:
        out.append({"code": "pain", "date": pain["from"], "detail": f"pain {pain['score']}/3 on {pain['site']}"})
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
         tested_until,           # B400: last day the max counts as tested
         confidence, confidence_exposures, trend, delta_pct, previous_date,
         earliest_retest, signals: {count, needed}, fatigue,
         next_test: {date, session_id, source: planned|projected, trigger,
                     reason, blockers: [...]} | None,
         next_test_reason,       # why there is no next test, when None
         declines,               # A320 (covered axes): the active stored declines
         plan_edit_declines}     # A320 (covered axes): weeks the athlete took the test out of

    ``covered`` False → the axis is scheduled by the legacy planner rules
    (untested, test older than 90 days, loading pin); ``tested_until`` None.
    ``earliest_retest`` (A319): the first day any test of the axis may come
    (test + HIGH_CONF_RETEST_D, or the early retest's first day when that comes
    sooner).
    ``next_test_reason`` is the last skip the projection met — else
    ``not_tested_recently`` when it reaches the 90-day expiry (B400: a real
    skip is no longer overwritten there), ``not_due_within_horizon`` when it
    runs out of weeks. A320: a ``declined`` / ``postponed`` skip met before any
    due week takes precedence over the others.
    ``declines`` (A320): ``decline_view`` of each active stored record (reason
    code, never the note). ``plan_edit_declines``: ``{week_start, declined_at,
    session_id, source: plan_edit}`` for each hot week from this one on whose
    decision is the implicit decline (the athlete removed or replaced the
    test of a week where one was due).
    A320: a stale week (``_stale``, regenerated on its next read) is projected
    like a week not generated yet — the decision there is the policy's again,
    so a decline (or its undo) shows before the week is reopened.
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
        # B400: the last day the official max still counts as tested (fresh
        # for TEST_FRESH_DAYS days, the test day included); None once expired.
        row["tested_until"] = ((_as_date(om["date"]) + timedelta(days=TEST_FRESH_DAYS - 1)).isoformat()
                               if row["covered"] else None)
        conf = axis_confidence(state, om, archived_weeks=archived_weeks)
        row.update({"confidence": conf["confidence"], "confidence_exposures": conf["exposures"],
                    "confidence_min_exposures": conf["min_required"]})
        row.update(axis_trend(state, om))
        sig = axis_signals(state, axis, om)
        # A319: the first day ANY test may come — the gap after the test, or,
        # with the measured evidence of an early retest, the first day
        # `_axis_week_decision` lets that one in (LOW_CONF_RETEST_D floor, the
        # day after the last signal) when it comes sooner. The card and
        # athlete_context's "not before" never contradict a projected test.
        test_d = _as_date(om["date"])
        earliest = test_d + timedelta(days=retest_gap_days(conf["confidence"]))
        if sig["count"] >= EARLY_RETEST_SIGNALS and sig["last_date"]:
            early = max(test_d + timedelta(days=LOW_CONF_RETEST_D),
                        _as_date(sig["last_date"]) + timedelta(days=1))
            earliest = min(earliest, early)
        row["earliest_retest"] = earliest.isoformat()
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
        # A320: what the athlete declined — the stored records still active and
        # the weeks they took the policy's test out of.
        row["declines"] = [decline_view(r) for r in axis_declines(state, axis, om)]
        row["plan_edit_declines"] = _plan_edit_weeks(state, axis, td, finger_device=finger_device,
                                                     archived_weeks=archived_weeks)
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
        declined_skip = None  # A320: the first decline the projection meets
        for k in range(max(1, horizon_weeks)):
            wk = ws + timedelta(days=7 * k)
            dec = _axis_week_decision(state, axis, wk, today=td, finger_device=finger_device,
                                      archived_weeks=archived_weeks, check_already_scheduled=False)
            if dec is None:
                # The official max reaches its 90-day expiry inside the horizon.
                # B400: a real skip met on the way (no_placement_slot, a trip…)
                # stays the reason — it used to be overwritten here, and the
                # card said "not due yet" about a test the plan had dropped.
                last_skip = last_skip or "not_tested_recently"
                break
            hot = _hot_plan(state, wk.isoformat())
            if dec["status"] == "due" and hot is not None and not hot.get(_STALE_KEY):
                # The week is already generated and holds no planned test of
                # this axis: cached weeks are never regenerated, so projecting
                # it there would promise a test that never comes (A289 review).
                # A320: a stale week IS regenerated on its next read — projected.
                last_skip = _generated_week_skip(state, axis, wk, td)
                if last_skip in _DECLINE_SKIPS:
                    declined_skip = declined_skip or last_skip
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
                if last_skip in _DECLINE_SKIPS:
                    declined_skip = declined_skip or last_skip
        if row["next_test"] is None:
            row["next_test_reason"] = declined_skip or last_skip or "not_due_within_horizon"
        out_axes[axis] = row
    return {
        "as_of": td.isoformat(),
        "stable_band_pct": TREND_STABLE_PCT,
        "axes": out_axes,
        "covered_axes": [a for a in RETEST_AXES if out_axes.get(a, {}).get("covered")],
    }


def _plan_edit_weeks(
    state: Mapping[str, Any],
    axis: str,
    today: date,
    *,
    finger_device: Optional[str],
    archived_weeks: Any,
) -> List[Dict[str, Any]]:
    """A320: the hot weeks from the Monday of ``today`` on that the policy
    reads as declined by a plan edit — the athlete removed or replaced the
    test of a week where one was due (``plan_edit_removal``; A320 review: a
    week where nothing was due is a plan fact, not a decline, and is not
    listed)."""
    since = _monday(today)
    plans: Dict[str, Mapping[str, Any]] = {}
    for key, plan in (state.get("week_plans") or {}).items():
        if isinstance(plan, Mapping):
            plans[str(key)] = plan
    cur = state.get("current_week_plan")
    if isinstance(cur, Mapping) and cur.get("start_date") and str(cur["start_date"]) not in plans:
        plans[str(cur["start_date"])] = cur
    out: List[Dict[str, Any]] = []
    for key in sorted(plans):
        if key < since.isoformat():
            continue
        removal = plan_edit_removal(plans[key], axis, today=today)
        wk = _parse_date(key)
        if removal is None or wk is None:
            continue
        dec = _axis_week_decision(state, axis, wk, today=today, finger_device=finger_device,
                                  archived_weeks=archived_weeks, check_already_scheduled=False) or {}
        view = dec.get("declined") or {}
        if dec.get("skip_reason") == SKIP_DECLINED and view.get("source") == DECLINE_SOURCE_PLAN_EDIT:
            out.append({"week_start": key, "declined_at": view.get("declined_at"),
                        "session_id": removal["session_id"], "source": DECLINE_SOURCE_PLAN_EDIT})
    return out


def _generated_week_skip(state: Mapping[str, Any], axis: str, wk: date, today: date) -> str:
    """Why a generated week has no upcoming test of ``axis`` although the
    policy would call it due: what PASS 3a recorded, else ``not_in_plan``
    (week generated before A289, or the slot was lost to a regeneration).
    A320: ``declined`` when the athlete removed or replaced the test of that
    week (it used to read ``not_in_plan``, then ``missed``)."""
    if plan_edit_removal(_hot_plan(state, wk.isoformat()), axis, today=today) is not None:
        return SKIP_DECLINED
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
    "trip_blocked", "pain_blocked", "retest_decisions", "test_day_blockers", "retest_status",
    # A319
    "COMBINED_TEST_SESSION",
    # A320
    "TRIGGER_POSTPONED", "DECLINES_KEY", "DECLINE_KIND_DECLINE", "DECLINE_KIND_POSTPONE", "DECLINE_KINDS",
    "DECLINE_REASONS", "DECLINE_SOURCES", "DECLINE_SOURCE_PLAN_EDIT", "SKIP_DECLINED", "SKIP_POSTPONED",
    "normalize_trigger", "axis_declines", "decline_view", "plan_edit_removal", "is_policy_test",
]
