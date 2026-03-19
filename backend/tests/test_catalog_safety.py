"""Catalog safety and data integrity tests."""

import json
import os
import pytest


EXERCISES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "catalog", "exercises", "v1", "exercises.json"
)


def _load_exercises():
    with open(EXERCISES_PATH) as f:
        data = json.load(f)
    return data["exercises"]


def _load_exercise_ids():
    return [e["id"] for e in _load_exercises()]


def test_no_blacklisted_exercises_in_catalog():
    """D55: exercises known to be unsafe or contraindicated must not be in catalog."""
    BLACKLIST_PATTERNS = [
        "crunch",
        "sit_up",
        "situp",
        "russian_twist",
        "behind_neck",
        "upright_row",
        "kipping",
    ]

    ids = _load_exercise_ids()
    violations = [eid for eid in ids if any(p in eid for p in BLACKLIST_PATTERNS)]

    assert violations == [], f"Blacklisted exercises found in catalog: {violations}"


def test_no_duplicate_exercise_ids():
    """Every exercise ID must be unique."""
    ids = _load_exercise_ids()
    seen = set()
    dupes = []
    for eid in ids:
        if eid in seen:
            dupes.append(eid)
        seen.add(eid)

    assert dupes == [], f"Duplicate exercise IDs: {dupes}"


def test_timed_reps_require_rest_between_reps():
    """D133: if work_seconds > 0 AND reps > 1, rest_between_reps_seconds must exist and be > 0.

    Without this, the guided session timer plays consecutive countdowns with no pause,
    giving the user zero time to reset position between reps.
    """
    exercises = _load_exercises()
    violations = []
    for e in exercises:
        pd = e.get("prescription_defaults", {})
        reps = pd.get("reps")
        work_s = pd.get("work_seconds")
        rest_r = pd.get("rest_between_reps_seconds")
        if (
            isinstance(reps, int)
            and reps > 1
            and work_s
            and work_s > 0
            and not rest_r
        ):
            violations.append(
                f"{e['id']}: reps={reps}, work_seconds={work_s}, "
                f"rest_between_reps_seconds={rest_r}"
            )

    assert violations == [], (
        "Timer violations (consecutive countdowns with no pause):\n"
        + "\n".join(violations)
    )
