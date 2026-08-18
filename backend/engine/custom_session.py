"""Custom session helpers — load score and duration estimation (A205)."""

from __future__ import annotations

from typing import Any, Dict, List


def compute_custom_session_load(exercise_ids: List[str], catalog: Dict[str, Any]) -> int:
    """Sum fatigue_cost x 1.5, capped at 85 — same formula as resolve_session."""
    raw = sum(catalog.get(eid, {}).get("fatigue_cost", 0) for eid in exercise_ids)
    return round(min(85, raw * 1.5))


# B337: a rep with no duration of its own. Deliberately crude and deliberately
# kept: turning it into something better needs a per-exercise rep duration, which
# only the catalog knows and this function never receives. It is an approximation
# of WORK, not an ignored field — unlike the two defects fixed below.
SECONDS_PER_REP = 4

# Used only when the entry says nothing about set rest. An explicit 0 means zero.
DEFAULT_SET_REST_S = 60

# Fallback for an entry with neither work_seconds nor reps.
DEFAULT_WORK_S = 30

# B338: walking to the next station, re-chalking, changing a load, reading the
# next exercise. B337 left this out on the grounds that it is not in the data —
# which is true, and is exactly why it is a flat constant here rather than
# something pretended to be derived. Charged BETWEEN exercises, so n entries pay
# n−1 transitions: the same shape as set rest, which is never charged after the
# last set. Decided by Daniele on 2026-08-18.
TRANSITION_BETWEEN_EXERCISES_S = 60


def estimate_custom_session_duration(exercises: List[Dict[str, Any]]) -> int:
    """Estimate duration in minutes from exercise params.

    Counts, per exercise: work × sets, the rest BETWEEN REPS inside each set, and
    the rest BETWEEN SETS (never after the last one). Plus, once per gap between
    consecutive exercises, ``TRANSITION_BETWEEN_EXERCISES_S`` (B338).

    **B337 — two things this used to leave out, both of them written down in the
    entry it was reading:**

    1. ``rest_between_reps_seconds`` was ignored **entirely**. On anything whose
       reps are separated by real rest, that is most of the session: a limit
       boulder block of 5 problems × 3 attempts with 3 min between attempts lost
       ``5 × 2 × 180s = 30 minutes``, and the session was announced as 45 min when
       it was 72.
    2. ``rest_between_sets_seconds or 60`` turned an **explicit 0 into 60**. A
       4-set stretch written as back-to-back was billed 3 phantom minutes.

    Both consumers that BUDGET on this function (``session_composer``,
    ``adhoc_builder``) were therefore over-filling: asked for 30 minutes, they
    packed a session that took longer. A larger, truer estimate makes them pack
    less, which is the point.

    **B338 supersedes one of B337's exclusions.** B337 left the walk between
    exercises out because it is not in the data. It is still not in the data —
    but a flat, named, documented minute is a better answer than a silent zero,
    because zero is also a guess and it is the one guess we know is wrong. The
    remaining approximation, ``SECONDS_PER_REP``, is a different thing and stays.
    """
    total_seconds = 0
    for ex in exercises:
        sets = ex.get("sets", 1) or 1
        # B324: an alt_sides exercise is run once per side — 3x20s Copenhagen is
        # six work bouts, not three. The players double the set count the same way.
        if ex.get("alt_sides"):
            sets = sets * 2

        reps = ex.get("reps")
        # Work time per set
        if ex.get("work_seconds"):
            work_per_set = ex["work_seconds"]
        elif reps:
            work_per_set = reps * SECONDS_PER_REP
        else:
            work_per_set = DEFAULT_WORK_S

        # B337 (1): rest between reps, inside every set. n reps → n−1 gaps.
        inter_rep_rest = 0
        if reps and reps > 1:
            inter_rep_rest = (reps - 1) * (ex.get("rest_between_reps_seconds") or 0)

        # B337 (2): honour an explicit 0; default only when the field is absent.
        rest_per_set = ex.get("rest_between_sets_seconds")
        if rest_per_set is None:
            rest_per_set = DEFAULT_SET_REST_S

        total_seconds += sets * (work_per_set + inter_rep_rest) + max(0, sets - 1) * rest_per_set

    # B338: one transition per GAP, so n exercises pay n−1.
    total_seconds += max(0, len(exercises) - 1) * TRANSITION_BETWEEN_EXERCISES_S
    return max(1, round(total_seconds / 60))
