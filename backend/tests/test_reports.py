"""Tests for report engine — weekly and monthly reports."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any, Dict

import pytest

from backend.engine.report_engine import generate_monthly_report, generate_weekly_report


@pytest.fixture
def tmp_log_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def _write_indoor_log(log_dir: str, entries: list):
    """Write indoor session log entries to a JSONL file."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, "sessions_2026.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _write_outdoor_log(log_dir: str, entries: list):
    """Write outdoor session log entries to a JSONL file."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, "outdoor_sessions_2026.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _make_state(**overrides) -> Dict[str, Any]:
    base = {
        "planning_prefs": {"target_training_days_per_week": 4},
        "current_week_plan": {
            "weeks": [{
                "days": [
                    {"date": "2026-03-16", "sessions": [{"session_id": "s1"}]},
                    {"date": "2026-03-17", "sessions": [{"session_id": "s2"}]},
                    {"date": "2026-03-18", "sessions": [{"session_id": "s3"}]},
                    {"date": "2026-03-19", "sessions": []},
                    {"date": "2026-03-20", "sessions": [{"session_id": "s4"}]},
                    {"date": "2026-03-21", "sessions": []},
                    {"date": "2026-03-22", "sessions": []},
                ]
            }]
        },
    }
    base.update(overrides)
    return base


# ── Weekly reports ──────────────────────────────────────────────────────

class TestWeeklyReport:
    def test_empty_log(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, "2026-03-16")
        assert report["report_type"] == "weekly"
        assert report["completed_sessions"] == 0
        assert report["planned_sessions"] == 4
        assert report["adherence_pct"] == 0.0

    def test_with_indoor_sessions(self, tmp_log_dir):
        _write_indoor_log(tmp_log_dir, [
            {"date": "2026-03-16", "session_id": "s1", "duration_minutes": 90},
            {"date": "2026-03-17", "session_id": "s2", "duration_minutes": 60},
            {"date": "2026-03-18", "session_id": "s3", "duration_minutes": 90},
        ])
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, "2026-03-16")
        assert report["completed_sessions"] == 3
        assert report["adherence_pct"] == 75.0
        assert report["total_indoor_minutes"] == 240

    def test_with_outdoor_sessions(self, tmp_log_dir):
        _write_outdoor_log(tmp_log_dir, [{
            "log_version": "outdoor.v1",
            "date": "2026-03-21",
            "spot_name": "Berdorf",
            "discipline": "boulder",
            "duration_minutes": 180,
            "routes": [],
        }])
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, "2026-03-16")
        assert report["outdoor_sessions"] == 1
        assert report["total_outdoor_minutes"] == 180

    def test_full_adherence_highlight(self, tmp_log_dir):
        _write_indoor_log(tmp_log_dir, [
            {"date": f"2026-03-{16+i}", "session_id": f"s{i+1}", "duration_minutes": 60}
            for i in range(4)
        ])
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, "2026-03-16")
        assert report["adherence_pct"] == 100.0
        assert any("Excellent" in h for h in report["highlights"])

    def test_no_plan_zero_adherence(self, tmp_log_dir):
        state = _make_state(current_week_plan=None)
        report = generate_weekly_report(state, tmp_log_dir, "2026-03-16")
        assert report["planned_sessions"] == 0
        assert report["adherence_pct"] == 0.0


# ── Monthly reports ─────────────────────────────────────────────────────

class TestMonthlyReport:
    def test_empty_month(self, tmp_log_dir):
        state = _make_state()
        report = generate_monthly_report(state, tmp_log_dir, "2026-03")
        assert report["report_type"] == "monthly"
        assert report["total_indoor_sessions"] == 0
        assert report["total_outdoor_sessions"] == 0

    def test_with_sessions(self, tmp_log_dir):
        _write_indoor_log(tmp_log_dir, [
            {"date": "2026-03-02", "session_id": "strength_long", "duration_minutes": 120},
            {"date": "2026-03-05", "session_id": "technique_focus_gym", "duration_minutes": 90},
            {"date": "2026-03-10", "session_id": "strength_long", "duration_minutes": 120},
            {"date": "2026-03-15", "session_id": "power_endurance_gym", "duration_minutes": 90},
        ])
        state = _make_state()
        report = generate_monthly_report(state, tmp_log_dir, "2026-03")
        assert report["total_indoor_sessions"] == 4
        assert report["total_indoor_minutes"] == 420
        assert len(report["weekly_session_counts"]) > 0

    def test_suggestion_no_outdoor(self, tmp_log_dir):
        _write_indoor_log(tmp_log_dir, [
            {"date": "2026-03-02", "session_id": "strength_long", "duration_minutes": 120},
        ])
        state = _make_state()
        report = generate_monthly_report(state, tmp_log_dir, "2026-03")
        assert any("outdoor" in s.lower() for s in report["suggestions"])

    def test_suggestion_no_technique(self, tmp_log_dir):
        _write_indoor_log(tmp_log_dir, [
            {"date": f"2026-03-{i+1:02d}", "session_id": "strength_long", "duration_minutes": 90}
            for i in range(5)
        ])
        state = _make_state()
        report = generate_monthly_report(state, tmp_log_dir, "2026-03")
        assert any("technique" in s.lower() for s in report["suggestions"])

    def test_max_three_suggestions(self, tmp_log_dir):
        state = _make_state(planning_prefs={"target_training_days_per_week": 10})
        report = generate_monthly_report(state, tmp_log_dir, "2026-03")
        assert len(report["suggestions"]) <= 3


# ── API integration ─────────────────────────────────────────────────────

class TestReportsAPI:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.api.routers import reports as reports_router

        state_path = tmp_path / "user_state.json"
        state_path.write_text(json.dumps({
            "schema_version": "1.5",
            "planning_prefs": {"target_training_days_per_week": 4},
            "current_week_plan": None,
        }))
        monkeypatch.setattr(deps, "STATE_PATH", state_path)

        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr(reports_router, "LOG_DIR", log_dir)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def test_weekly_report(self):
        r = self.client.get("/api/reports/weekly?week_start=2026-03-16")
        assert r.status_code == 200
        data = r.json()
        assert data["report_type"] == "weekly"

    def test_monthly_report(self):
        r = self.client.get("/api/reports/monthly?month=2026-03")
        assert r.status_code == 200
        data = r.json()
        assert data["report_type"] == "monthly"
