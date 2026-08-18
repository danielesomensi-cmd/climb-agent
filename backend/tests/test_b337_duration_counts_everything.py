"""B337 — the duration estimate must count every rest the entry declares.

Found live on 2026-08-18: a limit-boulder evening (5 problems x 3 attempts, 3 min
between attempts, 5 min between problems, plus warm-up and cool-down) was
announced by the app as **45 minutes** for a session that really takes **72**.

Two fields were being dropped, both of them written down in the very entry the
function was reading:

  1. ``rest_between_reps_seconds`` — ignored entirely. On this session that is
     ``5 x 2 x 180s = 30 minutes``, i.e. most of the missing time.
  2. ``rest_between_sets_seconds`` — read as ``or 60``, so an explicit **0**
     became 60 and a back-to-back stretch was billed 3 phantom minutes.

The exact real-world session is pinned below in both its old and new form, so
the regression cannot come back as "roughly right".
"""

from __future__ import annotations

import pytest

from backend.engine.custom_session import (
    DEFAULT_SET_REST_S,
    SECONDS_PER_REP,
    estimate_custom_session_duration,
)


# The Arlon session, exactly as written onto the plan on 2026-08-18.
ARLON_EVENING = [
    {"exercise_id": "general_pulse_raise", "sets": 1, "work_seconds": 240,
     "rest_between_sets_seconds": 0},
    {"exercise_id": "dynamic_mobility_flow", "sets": 1, "work_seconds": 300,
     "rest_between_sets_seconds": 0},
    {"exercise_id": "warmup_easy_boulders", "sets": 1, "work_seconds": 600,
     "rest_between_sets_seconds": 0},
    {"exercise_id": "limit_bouldering", "sets": 5, "reps": 3,
     "rest_between_reps_seconds": 180, "rest_between_sets_seconds": 300},
    {"exercise_id": "cooldown_forearm_wrist_stretch", "sets": 4, "work_seconds": 30,
     "rest_between_sets_seconds": 0},
]


def test_the_session_that_exposed_this_is_72_minutes_not_45():
    # 240 + 300 + 600
    # + 5 x (3x4s work + 2x180s inter-rep) + 4 x 300s  = 1860 + 1200 = 3060
    # + 4 x 30s + 3 x 0s                                = 120
    # = 4320s = 72 min   (pre-B337 the same input returned 45)
    assert estimate_custom_session_duration(ARLON_EVENING) == 72


def test_limit_boulder_block_alone():
    block = [ARLON_EVENING[3]]
    assert estimate_custom_session_duration(block) == round(3060 / 60)  # 51


# --- defect 1: rest between reps ----------------------------------------------

def test_rest_between_reps_is_counted():
    ex = [{"sets": 2, "reps": 4, "rest_between_reps_seconds": 60,
           "rest_between_sets_seconds": 0}]
    # 2 x (4x4s + 3x60s) = 2 x 196 = 392s
    assert estimate_custom_session_duration(ex) == round(392 / 60)


def test_a_single_rep_has_no_gap_to_rest_in():
    ex = [{"sets": 3, "reps": 1, "rest_between_reps_seconds": 999,
           "rest_between_sets_seconds": 0}]
    # 3 x (1x4s + 0) = 12s → floored to 1 min, and crucially NOT 3 x 999s
    assert estimate_custom_session_duration(ex) == 1


def test_absent_rest_between_reps_adds_nothing():
    with_field = [{"sets": 1, "reps": 5, "rest_between_reps_seconds": 0}]
    without = [{"sets": 1, "reps": 5}]
    assert estimate_custom_session_duration(with_field) == estimate_custom_session_duration(without)


def test_inter_rep_rest_applies_inside_every_set():
    # Asserted in exact minutes, NOT as `3 x the one-set answer`: the function
    # returns rounded minutes, so 3 x round(4.2) != round(12.6) and such an
    # identity would fail on rounding while the logic is right.
    one = [{"sets": 1, "reps": 3, "rest_between_reps_seconds": 120,
            "rest_between_sets_seconds": 0}]
    three = [{"sets": 3, "reps": 3, "rest_between_reps_seconds": 120,
              "rest_between_sets_seconds": 0}]
    assert estimate_custom_session_duration(one) == round(252 / 60)     # 3x4 + 2x120
    assert estimate_custom_session_duration(three) == round(756 / 60)   # x3 sets, no set rest


# --- defect 2: an explicit zero is a zero -------------------------------------

def test_explicit_zero_set_rest_is_honoured():
    ex = [{"sets": 4, "work_seconds": 30, "rest_between_sets_seconds": 0}]
    # 4 x 30s = 120s = 2 min. Pre-B337: 120 + 3x60 = 300s = 5 min.
    assert estimate_custom_session_duration(ex) == 2


def test_missing_set_rest_still_defaults():
    ex = [{"sets": 4, "work_seconds": 30}]
    expected = (4 * 30 + 3 * DEFAULT_SET_REST_S) / 60
    assert estimate_custom_session_duration(ex) == round(expected)


def test_zero_and_missing_are_not_the_same_thing():
    explicit = [{"sets": 5, "work_seconds": 20, "rest_between_sets_seconds": 0}]
    absent = [{"sets": 5, "work_seconds": 20}]
    assert estimate_custom_session_duration(explicit) < estimate_custom_session_duration(absent)


# --- unchanged behaviour ------------------------------------------------------

def test_rest_after_the_last_set_is_never_charged():
    one_set = [{"sets": 1, "work_seconds": 60, "rest_between_sets_seconds": 300}]
    assert estimate_custom_session_duration(one_set) == 1


def test_alt_sides_still_doubles_and_pays_inter_rep_rest_per_side():
    # Same rounding caveat as above — exact minutes, not a x2 identity.
    one_side = [{"sets": 2, "reps": 3, "rest_between_reps_seconds": 30,
                 "rest_between_sets_seconds": 0}]
    both = [{"sets": 2, "reps": 3, "rest_between_reps_seconds": 30,
             "rest_between_sets_seconds": 0, "alt_sides": True}]
    assert estimate_custom_session_duration(one_side) == round(144 / 60)  # 2x(12+60)
    assert estimate_custom_session_duration(both) == round(288 / 60)      # 4 bouts
    assert estimate_custom_session_duration(both) > estimate_custom_session_duration(one_side)


def test_work_seconds_still_wins_over_reps():
    ex = [{"sets": 1, "work_seconds": 600, "reps": 2}]
    assert estimate_custom_session_duration(ex) == 10


def test_entry_with_neither_work_nor_reps_falls_back():
    assert estimate_custom_session_duration([{"sets": 2, "rest_between_sets_seconds": 0}]) == 1


@pytest.mark.parametrize("reps,expected_work", [(1, 4), (5, 20), (12, 48)])
def test_rep_work_estimate_is_the_documented_approximation(reps, expected_work):
    # Deliberately crude and deliberately kept: a better number needs a
    # per-exercise rep duration that only the catalog knows and this function
    # never receives. Pinned so a future change to it is a decision, not a drift.
    assert reps * SECONDS_PER_REP == expected_work


def test_more_declared_rest_never_shortens_a_session():
    base = {"sets": 3, "reps": 4, "rest_between_sets_seconds": 60}
    quiet = estimate_custom_session_duration([base])
    resty = estimate_custom_session_duration([{**base, "rest_between_reps_seconds": 90}])
    assert resty > quiet
