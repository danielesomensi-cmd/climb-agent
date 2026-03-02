"""Tests for B75b — GET /api/user/export and POST /api/user/import."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """Isolated state directory for each test."""
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "DATA_DIR", tmp_path)
    monkeypatch.setattr(deps, "USERS_DIR", tmp_path / "users")
    yield tmp_path


class TestExport:
    def test_export_returns_json(self):
        r = client.get("/api/user/export")
        assert r.status_code == 200
        data = r.json()
        assert "schema_version" in data
        assert data["schema_version"] == "1.5"

    def test_export_content_disposition(self):
        r = client.get("/api/user/export")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "climb-agent-backup-" in cd
        assert ".json" in cd

    def test_export_matches_state(self):
        """Exported data matches what GET /api/state returns."""
        state_r = client.get("/api/state")
        export_r = client.get("/api/user/export")
        assert state_r.json() == export_r.json()


class TestImport:
    def test_import_valid_state(self):
        """Import a valid state — overwrites current."""
        new_state = dict(deps.EMPTY_TEMPLATE)
        new_state["user"] = {"name": "Imported User"}
        r = client.post("/api/user/import", json=new_state)
        assert r.status_code == 200
        assert r.json()["status"] == "imported"

        # Verify the state was overwritten
        check = client.get("/api/state")
        assert check.json()["user"]["name"] == "Imported User"

    def test_import_missing_schema_version(self):
        """Import without schema_version → 422."""
        r = client.post("/api/user/import", json={"user": {}})
        assert r.status_code == 422
        assert "schema_version" in r.json()["detail"]

    def test_import_wrong_schema_version(self):
        """Import with unsupported schema_version → 422."""
        r = client.post("/api/user/import", json={"schema_version": "99.0"})
        assert r.status_code == 422
        assert "schema_version" in r.json()["detail"]

    def test_import_not_a_dict(self):
        """Import a non-dict JSON → 422 (FastAPI validation)."""
        r = client.post("/api/user/import", content="[]",
                        headers={"Content-Type": "application/json"})
        assert r.status_code == 422

    def test_import_appends_event_log(self, isolate_state):
        """Import writes append-only event log entry."""
        new_state = dict(deps.EMPTY_TEMPLATE)
        client.post("/api/user/import", json=new_state)

        # Find the events.jsonl in the logs dir
        log_file = isolate_state / "logs" / "events.jsonl"
        assert log_file.exists()
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry["event"] == "state_imported"
        assert "timestamp" in entry

    def test_import_then_export_roundtrip(self):
        """Import → export returns identical data."""
        new_state = dict(deps.EMPTY_TEMPLATE)
        new_state["user"] = {"name": "Roundtrip"}
        new_state["goal"] = {"goal_type": "grade", "discipline": "boulder"}
        client.post("/api/user/import", json=new_state)

        export_r = client.get("/api/user/export")
        exported = export_r.json()
        assert exported["user"]["name"] == "Roundtrip"
        assert exported["goal"]["discipline"] == "boulder"
