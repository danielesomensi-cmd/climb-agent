"""B338 — one minute of transition between consecutive exercises.

B337 deliberately left this out: the walk to the next station is not in the
data. Daniele's call (2026-08-18) is that a flat, named, documented minute beats
a silent zero — zero is also a guess, and it is the one guess we know is wrong.

Charged per GAP, not per exercise: n entries pay n−1 transitions, the same shape
as set rest, which is never charged after the last set. These tests pin that
boundary, because "per exercise" is the easy thing to write by accident and it
would silently inflate every single-exercise estimate by a minute.
"""

from __future__ import annotations

from backend.engine.custom_session import (
    TRANSITION_BETWEEN_EXERCISES_S,
    estimate_custom_session_duration,
)

ONE_MIN_OF_WORK = {"sets": 1, "work_seconds": 60, "rest_between_sets_seconds": 0}


def test_a_single_exercise_pays_no_transition():
    # The boundary that matters: nothing to walk to.
    assert estimate_custom_session_duration([ONE_MIN_OF_WORK]) == 1


def test_two_exercises_pay_one_transition():
    assert estimate_custom_session_duration([ONE_MIN_OF_WORK, ONE_MIN_OF_WORK]) == 3


def test_n_exercises_pay_n_minus_one():
    for n in range(1, 8):
        expected = n + (n - 1)  # n minutes of work + (n-1) transitions
        assert estimate_custom_session_duration([ONE_MIN_OF_WORK] * n) == expected


def test_empty_session_pays_nothing():
    # max(0, -1) must not charge a negative transition.
    assert estimate_custom_session_duration([]) == 1  # floored, not negative


def test_transition_is_a_flat_constant_not_scaled_by_sets():
    heavy = {"sets": 6, "work_seconds": 10, "rest_between_sets_seconds": 0}
    light = {"sets": 1, "work_seconds": 60, "rest_between_sets_seconds": 0}
    # Both are 60s of work; the transition added between them is the same.
    pair = estimate_custom_session_duration([heavy, light])
    solo = estimate_custom_session_duration([heavy]) + estimate_custom_session_duration([light])
    assert (pair * 60) - (solo * 60) == TRANSITION_BETWEEN_EXERCISES_S


def test_adding_an_exercise_never_shortens_a_session():
    base = [ONE_MIN_OF_WORK, ONE_MIN_OF_WORK]
    longer = base + [{"sets": 1, "work_seconds": 1, "rest_between_sets_seconds": 0}]
    assert estimate_custom_session_duration(longer) > estimate_custom_session_duration(base)
