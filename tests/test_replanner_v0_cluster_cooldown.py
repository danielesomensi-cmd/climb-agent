import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from catalog.engine.cluster_utils import cluster_key_for_exercise  # noqa: E402
from catalog.engine.resolve_session import resolve_session  # noqa: E402


def write_json(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def make_minimal_exercises():
    return [
        {
            "exercise_id": "weighted_pullup",
            "domain": ["strength_general"],
            "role": ["main"],
            "equipment_required": ["pullup_bar", "weight"],
            "pattern": "pull",
            "location_allowed": ["home"],
        },
        {
            "exercise_id": "pullup",
            "domain": ["strength_general"],
            "role": ["assistant"],
            "equipment_required": ["pullup_bar", "weight"],
            "pattern": "pull",
            "location_allowed": ["home"],
        },
        {
            "exercise_id": "ring_row",
            "domain": ["strength_general"],
            "role": ["secondary"],
            "equipment_required": ["rings"],
            "pattern": "pull",
            "location_allowed": ["home"],
        },
    ]


def make_template():
    return {
        "id": "cluster_test",
        "blocks": [
            {
                "block_id": "main",
                "type": "main",
                "role": "main",
                "domain": ["strength_general"],
            }
        ],
    }


def make_session(target_date: str):
    return {
        "id": "cluster_session",
        "version": "1.0",
        "context": {"location": "home", "target_date": target_date},
        "modules": [{"template_id": "cluster_test", "version": "v1"}],
    }


def make_user_state(cluster_key: str, until_date: str):
    return {
        "context": {"location": "home"},
        "equipment": {"home": ["pullup_bar", "weight"]},
        "cooldowns": {"per_cluster": {cluster_key: {"until_date": until_date, "reason": "difficulty:hard"}}},
    }


def run_resolver(tmp_path, user_state: dict, target_date: str):
    repo_root = str(tmp_path)
    exercises_path = os.path.join(repo_root, "catalog", "exercises", "v1", "exercises.json")
    template_path = os.path.join(repo_root, "catalog", "templates", "v1", "cluster_test.json")
    session_path = os.path.join(repo_root, "catalog", "sessions", "v1", "cluster_session.json")

    exercises = make_minimal_exercises()
    write_json(exercises_path, exercises)
    write_json(template_path, make_template())
    write_json(session_path, make_session(target_date))

    return resolve_session(
        repo_root=repo_root,
        session_path="catalog/sessions/v1/cluster_session.json",
        templates_dir="catalog/templates",
        exercises_path="catalog/exercises/v1/exercises.json",
        out_path="output/cluster_session.json",
        user_state_override=user_state,
        write_output=False,
    )


def test_cluster_cooldown_fallback(tmp_path):
    exercises = make_minimal_exercises()
    cluster_key = cluster_key_for_exercise(exercises[0])
    user_state = make_user_state(cluster_key, "2026-01-11")

    out = run_resolver(tmp_path, user_state, "2026-01-10")
    exercises_out = out["resolved_session"]["exercise_instances"]
    assert exercises_out[0]["exercise_id"] == "pullup"


def test_cluster_cooldown_outside_window(tmp_path):
    exercises = make_minimal_exercises()
    cluster_key = cluster_key_for_exercise(exercises[0])
    user_state = make_user_state(cluster_key, "2026-01-11")

    out = run_resolver(tmp_path, user_state, "2026-01-12")
    exercises_out = out["resolved_session"]["exercise_instances"]
    assert exercises_out[0]["exercise_id"] == "weighted_pullup"


def test_cluster_cooldown_deterministic(tmp_path):
    exercises = make_minimal_exercises()
    cluster_key = cluster_key_for_exercise(exercises[0])
    user_state = make_user_state(cluster_key, "2026-01-11")

    out_a = run_resolver(tmp_path, user_state, "2026-01-10")
    out_b = run_resolver(tmp_path, user_state, "2026-01-10")
    assert out_a["resolved_session"]["exercise_instances"] == out_b["resolved_session"]["exercise_instances"]
