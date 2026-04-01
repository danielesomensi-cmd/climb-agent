"""Guard test: equipment ID consistency across all sources.

Prevents B181-class bugs where an equipment ID is offered to users
(onboarding, catalog) but missing from KNOWN_EQUIPMENT_KEYS, causing
validation failures at runtime.

Every equipment ID used anywhere in the system must be registered in
KNOWN_EQUIPMENT_KEYS.  This test catches drift automatically.
"""

import json
import glob
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.engine.equipment_utils import KNOWN_EQUIPMENT_KEYS
from backend.api.routers.onboarding import EQUIPMENT_HOME, EQUIPMENT_GYM

REPO_ROOT = os.path.join(os.path.dirname(__file__), "../..")


def _load_exercises():
    path = os.path.join(REPO_ROOT, "backend/catalog/exercises/v1/exercises.json")
    with open(path) as f:
        return json.load(f)["exercises"]


def _load_session_files():
    pattern = os.path.join(REPO_ROOT, "backend/catalog/sessions/v1/*.json")
    sessions = []
    for fpath in glob.glob(pattern):
        with open(fpath) as f:
            sessions.append(json.load(f))
    return sessions


# ── Onboarding → KNOWN_EQUIPMENT_KEYS ──────────────────────────────

def test_onboarding_home_ids_in_known_keys():
    """Every equipment ID offered in EQUIPMENT_HOME must be in KNOWN_EQUIPMENT_KEYS (B181)."""
    for item in EQUIPMENT_HOME:
        assert item["id"] in KNOWN_EQUIPMENT_KEYS, (
            f"Equipment ID {item['id']!r} is offered in EQUIPMENT_HOME "
            f"but missing from KNOWN_EQUIPMENT_KEYS — see B181"
        )


def test_onboarding_gym_ids_in_known_keys():
    """Every equipment ID offered in EQUIPMENT_GYM must be in KNOWN_EQUIPMENT_KEYS (B181)."""
    for item in EQUIPMENT_GYM:
        assert item["id"] in KNOWN_EQUIPMENT_KEYS, (
            f"Equipment ID {item['id']!r} is offered in EQUIPMENT_GYM "
            f"but missing from KNOWN_EQUIPMENT_KEYS — see B181"
        )


# ── Catalog exercises → KNOWN_EQUIPMENT_KEYS ───────────────────────

def test_catalog_equipment_required_in_known_keys():
    """Every equipment_required value in exercises must be in KNOWN_EQUIPMENT_KEYS."""
    exercises = _load_exercises()
    for ex in exercises:
        for eq_id in ex.get("equipment_required", []):
            assert eq_id in KNOWN_EQUIPMENT_KEYS, (
                f"Exercise {ex['id']!r} has equipment_required={eq_id!r} "
                f"not in KNOWN_EQUIPMENT_KEYS"
            )


def test_catalog_equipment_required_any_in_known_keys():
    """Every equipment_required_any value in exercises must be in KNOWN_EQUIPMENT_KEYS."""
    exercises = _load_exercises()
    for ex in exercises:
        for eq_id in ex.get("equipment_required_any", []):
            assert eq_id in KNOWN_EQUIPMENT_KEYS, (
                f"Exercise {ex['id']!r} has equipment_required_any={eq_id!r} "
                f"not in KNOWN_EQUIPMENT_KEYS"
            )


# ── Session JSONs → KNOWN_EQUIPMENT_KEYS ───────────────────────────

def test_session_required_equipment_in_known_keys():
    """Every required_equipment in session JSONs must be in KNOWN_EQUIPMENT_KEYS."""
    sessions = _load_session_files()
    for session in sessions:
        for eq_id in (session.get("required_equipment") or []):
            assert eq_id in KNOWN_EQUIPMENT_KEYS, (
                f"Session {session.get('id', '?')!r} has required_equipment={eq_id!r} "
                f"not in KNOWN_EQUIPMENT_KEYS"
            )


# ── No orphaned onboarding IDs ─────────────────────────────────────

def test_no_duplicate_onboarding_ids():
    """No duplicate IDs within each onboarding equipment list."""
    home_ids = [item["id"] for item in EQUIPMENT_HOME]
    assert len(home_ids) == len(set(home_ids)), f"Duplicate IDs in EQUIPMENT_HOME: {home_ids}"

    gym_ids = [item["id"] for item in EQUIPMENT_GYM]
    assert len(gym_ids) == len(set(gym_ids)), f"Duplicate IDs in EQUIPMENT_GYM: {gym_ids}"
