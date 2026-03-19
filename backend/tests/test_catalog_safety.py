"""D55: Safety blacklist — exercises that must NEVER appear in catalog."""

import json
import os
import pytest


EXERCISES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "catalog", "exercises", "v1", "exercises.json"
)


def _load_exercise_ids():
    with open(EXERCISES_PATH) as f:
        data = json.load(f)
    return [e["id"] for e in data["exercises"]]


def test_no_blacklisted_exercises_in_catalog():
    """Exercises known to be unsafe or contraindicated must not be in catalog."""
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
