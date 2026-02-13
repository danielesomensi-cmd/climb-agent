import json

from backend.engine.resolve_session import resolve_session


def _build_session(tmp_path, *, load_kg):
    templates_dir = tmp_path / "templates" / "v1"
    templates_dir.mkdir(parents=True, exist_ok=True)
    template_id = "override_template"
    template = {
        "template_id": template_id,
        "blocks": [
            {
                "block_id": "main",
                "type": "main",
                "exercise_id": "test_exercise",
                "prescription": {"load_kg": load_kg},
            }
        ],
    }
    (templates_dir / f"{template_id}.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    exercises = {"exercises": [{"id": "test_exercise", "name": "Test Exercise"}]}
    (tmp_path / "exercises.json").write_text(
        json.dumps(exercises, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    session = {
        "session_id": "override_session",
        "modules": [{"template_id": template_id, "version": "v1"}],
        "context": {},
    }
    (tmp_path / "session.json").write_text(
        json.dumps(session, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "repo_root": str(tmp_path),
        "session_path": "session.json",
        "templates_dir": "templates",
        "exercises_path": "exercises.json",
        "out_path": "out.json",
    }


def _resolve_instance(tmp_path, *, load_kg, user_state):
    paths = _build_session(tmp_path, load_kg=load_kg)
    resolved = resolve_session(
        **paths,
        user_state_override=user_state,
        write_output=False,
    )
    instances = resolved.get("resolved_session", {}).get("exercise_instances", [])
    assert instances, "Expected at least one exercise instance."
    return instances[0]


def test_absolute_override_sets_load_exactly(tmp_path):
    user_state = {
        "overrides": {
            "per_exercise": {
                "test_exercise": {
                    "mode": "absolute_load_kg",
                    "value": 42.0,
                    "expires": {"type": "occurrences", "n": 1},
                }
            }
        }
    }
    instance = _resolve_instance(tmp_path, load_kg=10.0, user_state=user_state)
    assert instance["prescription"]["load_kg"] == 42.0


def test_delta_override_shifts_load(tmp_path):
    user_state = {
        "overrides": {
            "per_exercise": {
                "test_exercise": {
                    "mode": "delta_kg",
                    "value": 2.0,
                    "expires": {"type": "occurrences", "n": 1},
                }
            }
        }
    }
    instance = _resolve_instance(tmp_path, load_kg=10.0, user_state=user_state)
    assert instance["prescription"]["load_kg"] == 12.0


def test_override_expires_after_single_use(tmp_path):
    user_state = {
        "overrides": {
            "per_exercise": {
                "test_exercise": {
                    "mode": "absolute_load_kg",
                    "value": 30.0,
                    "expires": {"type": "occurrences", "n": 1},
                }
            }
        }
    }
    _resolve_instance(tmp_path, load_kg=10.0, user_state=user_state)
    assert "test_exercise" not in user_state.get("overrides", {}).get("per_exercise", {})
