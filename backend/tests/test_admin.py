"""Tests for B75a — GET /api/admin/users (protected admin endpoint)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.routers import admin
from backend.api.main import app

client = TestClient(app)

SECRET = "test-admin-secret-42"


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    """Isolated data dir + admin secret for each test."""
    monkeypatch.setattr(deps, "STATE_PATH", tmp_path / "user_state.json")
    monkeypatch.setattr(deps, "DATA_DIR", tmp_path)
    monkeypatch.setattr(deps, "USERS_DIR", tmp_path / "users")
    monkeypatch.setattr(admin, "ADMIN_SECRET", SECRET)
    yield tmp_path


def _create_user(tmp_path: Path, user_id: str, state: dict) -> None:
    """Write a user_state.json for the given user."""
    user_dir = tmp_path / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "user_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Auth tests ─────────────────────────────────────────────────────────


class TestAdminAuth:
    def test_no_header_returns_403(self):
        r = client.get("/api/admin/users")
        assert r.status_code == 403

    def test_wrong_key_returns_403(self):
        r = client.get("/api/admin/users", headers={"X-Admin-Key": "wrong"})
        assert r.status_code == 403

    def test_correct_key_returns_200(self, isolate):
        r = client.get("/api/admin/users", headers={"X-Admin-Key": SECRET})
        assert r.status_code == 200

    def test_empty_secret_rejects_all(self, monkeypatch):
        """If ADMIN_SECRET is empty string, all requests are rejected."""
        monkeypatch.setattr(admin, "ADMIN_SECRET", "")
        r = client.get("/api/admin/users", headers={"X-Admin-Key": ""})
        assert r.status_code == 403


# ── Data extraction tests ──────────────────────────────────────────────


class TestAdminUsers:
    def test_empty_users_dir(self):
        """No users directory → empty list."""
        r = client.get("/api/admin/users", headers={"X-Admin-Key": SECRET})
        assert r.status_code == 200
        data = r.json()
        assert data["users"] == []
        assert data["total"] == 0

    def test_single_user_full_data(self, isolate):
        """User with complete state returns all fields."""
        state = deepcopy(deps.EMPTY_TEMPLATE)
        state["goal"] = {
            "current_grade": "7a+",
            "discipline": "lead",
            "created_at": "2026-01-15",
        }
        state["feedback_log"] = [
            {"date": "2026-02-28", "session_id": "s1", "difficulty": "ok"},
            {"date": "2026-02-25", "session_id": "s2", "difficulty": "hard"},
        ]
        _create_user(isolate, "aaa-111", state)

        r = client.get("/api/admin/users", headers={"X-Admin-Key": SECRET})
        data = r.json()
        assert data["total"] == 1
        u = data["users"][0]
        assert u["uuid"] == "aaa-111"
        assert u["last_access"] == "2026-02-28"
        assert u["grade"] == "7a+"
        assert u["sessions_completed"] == 2
        assert u["onboarding_date"] == "2026-01-15"

    def test_user_without_goal(self, isolate):
        """User who hasn't completed onboarding → nulls for grade/onboarding."""
        state = deepcopy(deps.EMPTY_TEMPLATE)
        _create_user(isolate, "bbb-222", state)

        r = client.get("/api/admin/users", headers={"X-Admin-Key": SECRET})
        u = r.json()["users"][0]
        assert u["grade"] is None
        assert u["onboarding_date"] is None
        assert u["sessions_completed"] == 0

    def test_multiple_users(self, isolate):
        """Multiple users returned sorted by directory name."""
        for uid in ("ccc-333", "aaa-111", "bbb-222"):
            state = deepcopy(deps.EMPTY_TEMPLATE)
            state["goal"] = {"current_grade": "6b", "created_at": "2026-02-01"}
            _create_user(isolate, uid, state)

        r = client.get("/api/admin/users", headers={"X-Admin-Key": SECRET})
        data = r.json()
        assert data["total"] == 3
        uuids = [u["uuid"] for u in data["users"]]
        assert uuids == sorted(uuids)

    def test_last_access_fallback_macrocycle(self, isolate):
        """Without feedback_log, falls back to macrocycle.generated_at."""
        state = deepcopy(deps.EMPTY_TEMPLATE)
        state["macrocycle"] = {"generated_at": "2026-02-20T14:30:00", "phases": []}
        _create_user(isolate, "ddd-444", state)

        r = client.get("/api/admin/users", headers={"X-Admin-Key": SECRET})
        u = r.json()["users"][0]
        assert u["last_access"] == "2026-02-20"

    def test_grade_fallback_assessment(self, isolate):
        """Without goal.current_grade, falls back to assessment.grades."""
        state = deepcopy(deps.EMPTY_TEMPLATE)
        state["goal"] = {"discipline": "lead"}
        state["assessment"] = {"grades": {"lead_max_rp": "7c+"}}
        _create_user(isolate, "eee-555", state)

        r = client.get("/api/admin/users", headers={"X-Admin-Key": SECRET})
        u = r.json()["users"][0]
        assert u["grade"] == "7c+"

    def test_corrupt_state_skipped(self, isolate):
        """Corrupt JSON file is silently skipped."""
        user_dir = isolate / "users" / "bad-user"
        user_dir.mkdir(parents=True)
        (user_dir / "user_state.json").write_text("{invalid json", encoding="utf-8")

        _create_user(isolate, "good-user", deepcopy(deps.EMPTY_TEMPLATE))

        r = client.get("/api/admin/users", headers={"X-Admin-Key": SECRET})
        assert r.json()["total"] == 1
        assert r.json()["users"][0]["uuid"] == "good-user"
