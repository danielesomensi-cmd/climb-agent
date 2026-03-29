"""Tests for B165a — POST /api/user/recovery-code and POST /api/user/recover."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

CODE_PATTERN = re.compile(r"^CLIMB-[23456789A-HJ-NP-Z]{4}-[23456789A-HJ-NP-Z]{4}$")

UUID_A = "00000000-0000-4000-a000-000000000001"
UUID_B = "00000000-0000-4000-a000-000000000002"
UUID_C = "00000000-0000-4000-a000-000000000003"
UUID_D = "00000000-0000-4000-a000-000000000004"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """Isolated state directory for each test."""
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "USERS_DIR", tmp_path / "users")
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "DATA_DIR", tmp_path)
    monkeypatch.setattr(deps, "USERS_DIR", tmp_path / "users")
    yield tmp_path


class TestRecoveryCode:
    def test_generate_returns_valid_code(self):
        """POST /api/user/recovery-code returns CLIMB-XXXX-XXXX format."""
        r = client.post("/api/user/recovery-code", headers={"X-User-ID": UUID_A})
        assert r.status_code == 200
        code = r.json()["recovery_code"]
        assert CODE_PATTERN.match(code), f"Invalid code format: {code}"

    def test_idempotent(self):
        """Repeated calls return the same code."""
        h = {"X-User-ID": UUID_B}
        r1 = client.post("/api/user/recovery-code", headers=h)
        r2 = client.post("/api/user/recovery-code", headers=h)
        assert r1.json()["recovery_code"] == r2.json()["recovery_code"]

    def test_different_users_get_different_codes(self):
        """Different UUIDs get different codes."""
        r1 = client.post("/api/user/recovery-code", headers={"X-User-ID": UUID_A})
        r2 = client.post("/api/user/recovery-code", headers={"X-User-ID": UUID_B})
        assert r1.json()["recovery_code"] != r2.json()["recovery_code"]

    def test_missing_user_id_returns_400(self):
        """Missing X-User-ID returns 400."""
        r = client.post("/api/user/recovery-code")
        assert r.status_code == 400


class TestRecover:
    def test_recover_valid_code(self):
        """POST /api/user/recover with valid code returns UUID."""
        r1 = client.post("/api/user/recovery-code", headers={"X-User-ID": UUID_C})
        code = r1.json()["recovery_code"]

        r2 = client.post("/api/user/recover", json={"recovery_code": code})
        assert r2.status_code == 200
        assert r2.json()["uuid"] == UUID_C

    def test_recover_case_insensitive(self):
        """Recovery code lookup is case-insensitive."""
        r1 = client.post("/api/user/recovery-code", headers={"X-User-ID": UUID_D})
        code = r1.json()["recovery_code"]

        r2 = client.post("/api/user/recover", json={"recovery_code": code.lower()})
        assert r2.status_code == 200
        assert r2.json()["uuid"] == UUID_D

    def test_recover_invalid_code_returns_404(self):
        """Invalid code returns 404."""
        r = client.post("/api/user/recover", json={"recovery_code": "CLIMB-ZZZZ-ZZZZ"})
        assert r.status_code == 404

    def test_recover_empty_code_returns_400(self):
        """Empty/missing code returns 400."""
        r = client.post("/api/user/recover", json={"recovery_code": ""})
        assert r.status_code == 400

    def test_recover_missing_field_returns_400(self):
        """Missing recovery_code field returns 400."""
        r = client.post("/api/user/recover", json={})
        assert r.status_code == 400
