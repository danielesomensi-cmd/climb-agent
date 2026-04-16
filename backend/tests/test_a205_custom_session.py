"""Tests for A205 — Custom session builder backend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.engine.custom_session import compute_custom_session_load, estimate_custom_session_duration

client = TestClient(app)

# ── Helpers ──────────────────────────────────────────────────────────────

def _reset():
    client.delete("/api/state")


def _create_session(name="Test Session", exercises=None, tags=None):
    if exercises is None:
        exercises = [{"exercise_id": "weighted_pullup", "sets": 4, "reps": 5}]
    body = {"name": name, "exercises": exercises}
    if tags is not None:
        body["tags"] = tags
    return client.post("/api/custom-session", json=body)


# ── Engine unit tests ────────────────────────────────────────────────────


class TestComputeLoadScore:
    def test_known_exercises(self):
        catalog = {
            "a": {"fatigue_cost": 10},
            "b": {"fatigue_cost": 20},
        }
        assert compute_custom_session_load(["a", "b"], catalog) == round(min(85, 30 * 1.5))

    def test_empty_exercises(self):
        assert compute_custom_session_load([], {}) == 0

    def test_capped_at_85(self):
        catalog = {"a": {"fatigue_cost": 100}}
        assert compute_custom_session_load(["a"], catalog) == 85

    def test_unknown_exercise_treated_as_zero(self):
        catalog = {"a": {"fatigue_cost": 10}}
        assert compute_custom_session_load(["a", "unknown"], catalog) == round(10 * 1.5)


class TestEstimateDuration:
    def test_rep_based(self):
        exercises = [{"sets": 4, "reps": 5, "rest_between_sets_seconds": 120}]
        # 4 sets x (5 reps x 4s) + 3 rest x 120s = 80 + 360 = 440s ≈ 7 min
        result = estimate_custom_session_duration(exercises)
        assert result == round(440 / 60)

    def test_time_based(self):
        exercises = [{"sets": 3, "work_seconds": 10, "rest_between_sets_seconds": 180}]
        # 3 x 10 + 2 x 180 = 30 + 360 = 390s ≈ 7 min
        result = estimate_custom_session_duration(exercises)
        assert result == round(390 / 60)

    def test_mixed(self):
        exercises = [
            {"sets": 4, "reps": 5, "rest_between_sets_seconds": 120},
            {"sets": 3, "work_seconds": 10, "rest_between_sets_seconds": 180},
        ]
        result = estimate_custom_session_duration(exercises)
        assert result == round((440 + 390) / 60)

    def test_minimum_one_minute(self):
        exercises = [{"sets": 1, "reps": 1}]
        result = estimate_custom_session_duration(exercises)
        assert result >= 1


# ── CRUD API tests ───────────────────────────────────────────────────────


class TestCreateSession:
    def setup_method(self):
        _reset()

    def test_create_success(self):
        r = _create_session(name="My Session", tags=["finger"])
        assert r.status_code == 201
        data = r.json()
        assert data["id"].startswith("cs_")
        assert data["name"] == "My Session"
        assert data["tags"] == ["finger"]
        assert len(data["exercises"]) == 1
        assert data["estimated_load_score"] >= 0
        assert data["estimated_duration_minutes"] >= 1
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_invalid_exercise_id(self):
        r = _create_session(exercises=[{"exercise_id": "nonexistent_xyz", "sets": 3, "reps": 5}])
        assert r.status_code == 422

    def test_create_empty_exercises(self):
        r = client.post("/api/custom-session", json={"name": "Empty", "exercises": []})
        assert r.status_code == 422

    def test_create_too_many_exercises(self):
        exercises = [{"exercise_id": "weighted_pullup", "sets": 1, "reps": 1}] * 31
        r = _create_session(exercises=exercises)
        assert r.status_code == 422

    def test_create_name_stripped(self):
        r = _create_session(name="  Padded Name  ")
        assert r.status_code == 201
        assert r.json()["name"] == "Padded Name"

    def test_duplicate_exercise_ids_allowed(self):
        exercises = [
            {"exercise_id": "weighted_pullup", "sets": 4, "reps": 5},
            {"exercise_id": "weighted_pullup", "sets": 3, "reps": 8},
        ]
        r = _create_session(exercises=exercises)
        assert r.status_code == 201
        assert len(r.json()["exercises"]) == 2


class TestGetSession:
    def setup_method(self):
        _reset()

    def test_get_existing(self):
        created = _create_session().json()
        r = client.get(f"/api/custom-session/{created['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]
        assert "exercises" in r.json()

    def test_get_not_found(self):
        r = client.get("/api/custom-session/cs_nonexistent")
        assert r.status_code == 404


class TestListSessions:
    def setup_method(self):
        _reset()

    def test_list_empty(self):
        r = client.get("/api/custom-session/list")
        assert r.status_code == 200
        assert r.json() == {"sessions": [], "count": 0}

    def test_list_summary_format(self):
        _create_session(name="Session A")
        _create_session(name="Session B")
        r = client.get("/api/custom-session/list")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        summary = data["sessions"][0]
        assert "exercise_count" in summary
        assert "exercises" not in summary


class TestUpdateSession:
    def setup_method(self):
        _reset()

    def test_update_success(self):
        created = _create_session(name="Original").json()
        r = client.put(
            f"/api/custom-session/{created['id']}",
            json={
                "name": "Updated",
                "tags": ["new"],
                "exercises": [{"exercise_id": "weighted_pullup", "sets": 6, "reps": 3}],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Updated"
        assert data["exercises"][0]["sets"] == 6
        assert data["created_at"] == created["created_at"]
        assert data["updated_at"] >= created["updated_at"]

    def test_update_not_found(self):
        r = client.put(
            "/api/custom-session/cs_nonexistent",
            json={"name": "X", "exercises": [{"exercise_id": "weighted_pullup", "sets": 1, "reps": 1}]},
        )
        assert r.status_code == 404


class TestDeleteSession:
    def setup_method(self):
        _reset()

    def test_delete_success(self):
        created = _create_session().json()
        r = client.delete(f"/api/custom-session/{created['id']}")
        assert r.status_code == 200
        assert r.json()["deleted"] == created["id"]
        # Verify gone
        r2 = client.get(f"/api/custom-session/{created['id']}")
        assert r2.status_code == 404

    def test_delete_not_found(self):
        r = client.delete("/api/custom-session/cs_nonexistent")
        assert r.status_code == 404


# ── Exercise listing ─────────────────────────────────────────────────────


class TestExerciseListing:
    def test_list_all(self):
        r = client.get("/api/custom-session/exercises")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] > 0
        ex = data["exercises"][0]
        assert "id" in ex
        assert "name" in ex
        assert "prescription_defaults" in ex
        assert "fatigue_cost" in ex

    def test_search_by_name(self):
        r = client.get("/api/custom-session/exercises?q=pullup")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] > 0
        assert all("pullup" in e["name"].lower() or "pullup" in e["description"].lower() for e in data["exercises"])

    def test_search_no_results(self):
        r = client.get("/api/custom-session/exercises?q=zzz_nonexistent_zzz")
        assert r.status_code == 200
        assert r.json()["count"] == 0


# ── Warmup/cooldown blocks ──────────────────────────────────────────────


class TestBlocks:
    def test_blocks_returns_structure(self):
        r = client.get("/api/custom-session/blocks")
        assert r.status_code == 200
        data = r.json()
        assert "warmup" in data
        assert "cooldown" in data
        assert isinstance(data["warmup"], list)
        assert isinstance(data["cooldown"], list)

    def test_block_exercise_schema(self):
        r = client.get("/api/custom-session/blocks")
        data = r.json()
        # Check at least one block has exercises with expected fields
        all_blocks = data["warmup"] + data["cooldown"]
        if all_blocks:
            block = all_blocks[0]
            assert "template_id" in block
            assert "label" in block
            assert "exercises" in block
            if block["exercises"]:
                ex = block["exercises"][0]
                assert "exercise_id" in ex
                assert "sets" in ex
