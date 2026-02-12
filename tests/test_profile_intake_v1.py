import json
from pathlib import Path

import pytest

from scripts.apply_profile_intake import IntakeError, apply_profile_intake

FIXT = Path(__file__).parent / "fixtures"


def _load_fixture(name: str):
    return json.loads((FIXT / name).read_text(encoding="utf-8"))


def _deterministic_dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _base_user_state() -> dict:
    return {
        "equipment": {
            "home": ["hangboard"],
            "gyms": [{"gym_id": "old", "name": "Old", "equipment": ["hangboard"]}],
        },
        "availability": {
            "mon": {"morning": {"available": True, "preferred_location": "home", "gym_id": None}}
        },
        "planning_prefs": {"target_training_days_per_week": 2},
        "defaults": {"location": "home"},
        "context": {"location": "home", "gym_id": None},
        "baselines": {"hangboard": [{"baseline_id": "keep_me"}]},
        "tests": {"queue": ["keep_me"]},
        "history_index": {"session_log_paths": ["data/logs/sessions_2026.jsonl"]},
        "untouched": {"x": 1},
    }


def test_idempotent_apply_profile_intake_is_byte_identical():
    intake = _load_fixture("profile_intake_valid.json")
    state = _base_user_state()

    first = apply_profile_intake(intake, state)
    second = apply_profile_intake(intake, first)

    assert _deterministic_dump(first) == _deterministic_dump(second)


def test_baselines_tests_history_index_are_not_overwritten():
    intake = _load_fixture("profile_intake_valid.json")
    state = _base_user_state()

    result = apply_profile_intake(intake, state)

    assert result["baselines"] == state["baselines"]
    assert result["tests"] == state["tests"]
    assert result["history_index"] == state["history_index"]


def test_profile_intake_schema_validation_fails_for_invalid_payload():
    intake = _load_fixture("profile_intake_invalid.json")

    with pytest.raises(IntakeError, match="Schema validation failed"):
        apply_profile_intake(intake, _base_user_state())


def test_profile_intake_rejects_equipment_outside_vocabulary():
    intake = _load_fixture("profile_intake_invalid_equipment.json")

    with pytest.raises(IntakeError, match="Schema validation failed"):
        apply_profile_intake(intake, _base_user_state())
