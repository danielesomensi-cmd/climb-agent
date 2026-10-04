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

Production callers since B364: ``anchored_load`` (official max, tested gate,
re-entry ramp) and ``progression_v1._update_test_from_log`` (confidence).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

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


__all__ = [
    "TEST_FRESH_DAYS", "LOW_CONF_MIN_EXPOSURES", "LOW_CONF_WINDOW_D", "LOW_CONF_RETEST_D",
    "REENTRY_GAP_D", "REENTRY_FACTORS", "REENTRY_FULL_FACTOR", "HANG_PCT_PER_S",
    "FINGER_GAP_H", "RETEST_BLOCK_H", "PULL_TEST_BLOCK_H", "HEAVY_PULL_PCT_1RM",
    "VERY_HARD_BLOCK_D", "PRE_TRIP_BLOCK_D", "RETEST_BLOCKED_PHASES",
    "PROTOCOL_HANG_7S", "PROTOCOL_HANG_5S", "PROTOCOL_PULLUP_2RM", "PROTOCOL_FAMILY",
    "EXERCISE_PROTOCOL", "convert_hang_seconds", "official_max", "is_tested",
    "test_confidence", "reentry_factor", "reentry_step", "is_heavy_pulling_session",
    "is_pulling_hard_session",
]
