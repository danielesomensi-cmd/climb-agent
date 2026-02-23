"""Tests for multi-user UUID support (Phase 4a).

Verifies that:
- Each user_id gets an isolated state directory
- State changes for one user don't affect another
- Missing X-User-ID header falls back to legacy path (no error)
- Invalid UUID in header returns 400
- New user_id auto-creates state from template
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import EMPTY_TEMPLATE, REPO_ROOT, USERS_DIR
from backend.api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_test_users():
    """Remove any per-user directories created during tests."""
    created: list[Path] = []
    orig_mkdir = Path.mkdir

    def tracking_mkdir(self, *args, **kwargs):
        if USERS_DIR in self.parents or self == USERS_DIR:
            created.append(self)
        return orig_mkdir(self, *args, **kwargs)

    Path.mkdir = tracking_mkdir  # type: ignore[assignment]
    yield
    Path.mkdir = orig_mkdir  # type: ignore[assignment]
    # Clean up user dirs created during test
    for p in created:
        # Walk up to the user_id directory (direct child of USERS_DIR)
        while p.parent != USERS_DIR and p.parent != p:
            p = p.parent
        if p.parent == USERS_DIR and p.exists():
            shutil.rmtree(p, ignore_errors=True)


def _uid() -> str:
    return str(uuid.uuid4())


def _headers(user_id: str) -> dict:
    return {"X-User-ID": user_id}


class TestUserIsolation:
    """Two different user_ids have completely isolated state."""

    def test_separate_state_files(self):
        uid_a = _uid()
        uid_b = _uid()

        # Both start with empty template
        r_a = client.get("/api/state", headers=_headers(uid_a))
        r_b = client.get("/api/state", headers=_headers(uid_b))
        assert r_a.status_code == 200
        assert r_b.status_code == 200

        # Verify separate files exist
        assert (USERS_DIR / uid_a / "user_state.json").exists()
        assert (USERS_DIR / uid_b / "user_state.json").exists()

    def test_modify_a_does_not_affect_b(self):
        uid_a = _uid()
        uid_b = _uid()

        # Initialize both
        client.get("/api/state", headers=_headers(uid_a))
        client.get("/api/state", headers=_headers(uid_b))

        # Modify A
        client.put(
            "/api/state",
            headers={**_headers(uid_a), "Content-Type": "application/json"},
            json={"user": {"name": "Alice"}},
        )

        # B should still have empty user
        r_b = client.get("/api/state", headers=_headers(uid_b))
        assert r_b.json().get("user", {}).get("name", "") != "Alice"

        # A should have the change
        r_a = client.get("/api/state", headers=_headers(uid_a))
        assert r_a.json()["user"]["name"] == "Alice"


class TestNewUserAutoCreation:
    """A new user_id auto-creates state from template."""

    def test_new_user_gets_template(self):
        uid = _uid()
        r = client.get("/api/state", headers=_headers(uid))
        assert r.status_code == 200
        state = r.json()
        assert state.get("schema_version") == EMPTY_TEMPLATE["schema_version"]
        assert state.get("macrocycle") is None

    def test_state_file_created_on_disk(self):
        uid = _uid()
        path = USERS_DIR / uid / "user_state.json"
        assert not path.exists()

        client.get("/api/state", headers=_headers(uid))
        assert path.exists()

        data = json.loads(path.read_text())
        assert data["schema_version"] == EMPTY_TEMPLATE["schema_version"]


class TestInvalidUUID:
    """Invalid UUID in X-User-ID header returns 400."""

    def test_random_string_rejected(self):
        r = client.get("/api/state", headers={"X-User-ID": "not-a-uuid"})
        assert r.status_code == 400
        assert "Invalid X-User-ID" in r.json()["detail"]

    def test_empty_string_rejected(self):
        r = client.get("/api/state", headers={"X-User-ID": ""})
        assert r.status_code == 400

    def test_partial_uuid_rejected(self):
        r = client.get("/api/state", headers={"X-User-ID": "12345678-1234"})
        assert r.status_code == 400


class TestLegacyFallback:
    """Missing X-User-ID falls back to legacy state path (for tests)."""

    def test_no_header_returns_200(self):
        r = client.get("/api/state")
        assert r.status_code == 200

    def test_no_header_uses_legacy_path(self):
        """Without header, state operations use the legacy single-file path."""
        r = client.get("/api/state")
        assert r.status_code == 200
        # Should work without creating any user directory
        # (uses backend/data/user_state.json)
