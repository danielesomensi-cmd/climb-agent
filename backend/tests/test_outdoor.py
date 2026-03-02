"""Tests for outdoor features: spots CRUD, session logging, stats, planner integration."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from backend.engine.outdoor_log import (
    append_outdoor_session,
    compute_outdoor_stats,
    load_outdoor_sessions,
    validate_outdoor_entry,
)
from backend.engine.planner_v2 import generate_phase_week


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_log_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def _make_entry(**overrides) -> Dict[str, Any]:
    base = {
        "log_version": "outdoor.v1",
        "date": "2026-03-15",
        "spot_name": "Berdorf",
        "discipline": "boulder",
        "duration_minutes": 180,
        "routes": [
            {
                "name": "La Marie Rose",
                "grade": "6a",
                "discipline": "boulder",
                "style": "onsight",
                "attempts": [{"result": "sent"}],
            }
        ],
    }
    base.update(overrides)
    return base


# ── Validation ──────────────────────────────────────────────────────────

class TestValidation:
    def test_valid_entry(self):
        assert validate_outdoor_entry(_make_entry()) == []

    def test_missing_required_fields(self):
        entry = {"log_version": "outdoor.v1"}
        errors = validate_outdoor_entry(entry)
        assert len(errors) == 1
        assert "Missing required fields" in errors[0]

    def test_invalid_discipline(self):
        errors = validate_outdoor_entry(_make_entry(discipline="trad"))
        assert any("discipline" in e for e in errors)

    def test_invalid_date(self):
        errors = validate_outdoor_entry(_make_entry(date="not-a-date"))
        assert any("date" in e.lower() for e in errors)

    def test_invalid_duration(self):
        errors = validate_outdoor_entry(_make_entry(duration_minutes=-1))
        assert any("duration" in e for e in errors)

    def test_invalid_routes_not_list(self):
        errors = validate_outdoor_entry(_make_entry(routes="not a list"))
        assert any("routes" in e for e in errors)

    def test_route_missing_name(self):
        entry = _make_entry(routes=[{"grade": "6a", "attempts": [{"result": "sent"}]}])
        errors = validate_outdoor_entry(entry)
        assert any("name" in e for e in errors)


# ── Append + Load round-trip ────────────────────────────────────────────

class TestAppendLoad:
    def test_append_and_load(self, tmp_log_dir):
        entry = _make_entry()
        path = append_outdoor_session(entry, tmp_log_dir)
        assert "outdoor_sessions_2026.jsonl" in path

        loaded = load_outdoor_sessions(tmp_log_dir)
        assert len(loaded) == 1
        assert loaded[0]["spot_name"] == "Berdorf"

    def test_append_multiple(self, tmp_log_dir):
        for i in range(3):
            append_outdoor_session(
                _make_entry(date=f"2026-03-{15 + i:02d}"),
                tmp_log_dir,
            )
        loaded = load_outdoor_sessions(tmp_log_dir)
        assert len(loaded) == 3

    def test_load_with_since_filter(self, tmp_log_dir):
        append_outdoor_session(_make_entry(date="2026-03-10"), tmp_log_dir)
        append_outdoor_session(_make_entry(date="2026-03-20"), tmp_log_dir)

        loaded = load_outdoor_sessions(tmp_log_dir, since_date="2026-03-15")
        assert len(loaded) == 1
        assert loaded[0]["date"] == "2026-03-20"

    def test_append_invalid_raises(self, tmp_log_dir):
        with pytest.raises(ValueError):
            append_outdoor_session({"bad": "entry"}, tmp_log_dir)

    def test_load_empty_dir(self, tmp_log_dir):
        assert load_outdoor_sessions(tmp_log_dir) == []

    def test_load_nonexistent_dir(self):
        assert load_outdoor_sessions("/nonexistent/dir") == []


# ── Stats ───────────────────────────────────────────────────────────────

class TestStats:
    def test_empty_sessions(self):
        stats = compute_outdoor_stats([])
        assert stats["total_sessions"] == 0
        assert stats["total_routes"] == 0
        assert stats["top_grade_sent"] is None

    def test_basic_stats(self):
        sessions = [
            _make_entry(routes=[
                {"name": "R1", "grade": "6a", "style": "onsight",
                 "attempts": [{"result": "sent"}]},
                {"name": "R2", "grade": "6b", "style": "flash",
                 "attempts": [{"result": "fell"}, {"result": "sent"}]},
                {"name": "R3", "grade": "7a",
                 "attempts": [{"result": "fell"}, {"result": "fell"}]},
            ]),
        ]
        stats = compute_outdoor_stats(sessions)
        assert stats["total_sessions"] == 1
        assert stats["total_routes"] == 3
        assert stats["sent_pct"] == pytest.approx(66.7, abs=0.1)
        assert stats["onsight_pct"] == pytest.approx(33.3, abs=0.1)
        assert stats["flash_pct"] == pytest.approx(33.3, abs=0.1)
        assert stats["top_grade_sent"] == "6b"

    def test_grade_histogram(self):
        sessions = [
            _make_entry(routes=[
                {"name": "R1", "grade": "6a", "attempts": [{"result": "sent"}]},
                {"name": "R2", "grade": "6a", "attempts": [{"result": "fell"}]},
                {"name": "R3", "grade": "6b", "attempts": [{"result": "sent"}]},
            ]),
        ]
        stats = compute_outdoor_stats(sessions)
        assert stats["grade_histogram"] == {"6a": 2, "6b": 1}


# ── Planner: Outdoor slots ─────────────────────────────────────────────

class TestPlannerOutdoorSlots:
    def test_outdoor_slot_gets_no_session(self):
        """A day with outdoor-only availability should be marked outdoor_slot=True with no sessions."""
        avail = {
            "mon": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
            "tue": {"evening": {"available": True, "locations": ["outdoor"], "preferred_location": "outdoor"}},
            "wed": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
        }
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"finger_strength": 0.2, "volume_climbing": 0.3},
            session_pool=["endurance_aerobic_gym", "technique_focus_gym", "prehab_maintenance"],
            start_date="2026-03-16",  # Monday
            availability=avail,
            allowed_locations=["gym", "home", "outdoor"],
            planning_prefs={"target_training_days_per_week": 3},
        )
        days = plan["weeks"][0]["days"]
        tue = days[1]  # Tuesday
        assert tue.get("outdoor_slot") is True
        assert tue["sessions"] == []

    def test_outdoor_slot_not_counted_in_budget(self):
        """Outdoor slots don't consume training day budget."""
        avail = {
            "mon": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
            "tue": {"evening": {"available": True, "locations": ["outdoor"], "preferred_location": "outdoor"}},
            "wed": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
            "thu": {"evening": {"available": True, "locations": ["home"], "preferred_location": "home"}},
        }
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"finger_strength": 0.2, "volume_climbing": 0.3},
            session_pool=["endurance_aerobic_gym", "technique_focus_gym", "prehab_maintenance", "flexibility_full"],
            start_date="2026-03-16",
            availability=avail,
            allowed_locations=["gym", "home", "outdoor"],
            planning_prefs={"target_training_days_per_week": 3},
        )
        days = plan["weeks"][0]["days"]
        # Tuesday is outdoor → not counted → Mon, Wed, Thu should all get sessions
        sessions_count = sum(1 for d in days if d["sessions"])
        assert sessions_count == 3  # Mon, Wed, Thu


# ── API integration (via TestClient) ────────────────────────────────────

class TestOutdoorAPI:
    """Spot CRUD + logging via FastAPI TestClient."""

    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        """Patch state and log paths for isolated tests."""
        from backend.api import deps
        from backend.api.routers import outdoor as outdoor_router

        state_path = tmp_path / "user_state.json"
        state_path.write_text(json.dumps({
            "schema_version": "1.5",
            "outdoor_spots": [],
        }))
        monkeypatch.setattr(deps, "STATE_PATH", state_path)

        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr(outdoor_router, "_FALLBACK_LOG_DIR", log_dir)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def test_get_spots_empty(self):
        r = self.client.get("/api/outdoor/spots")
        assert r.status_code == 200
        assert r.json()["spots"] == []

    def test_add_and_get_spot(self):
        r = self.client.post("/api/outdoor/spots", json={
            "name": "Berdorf",
            "discipline": "boulder",
            "typical_days": ["sat", "sun"],
        })
        assert r.status_code == 200
        spot = r.json()["spot"]
        assert spot["name"] == "Berdorf"
        assert spot["discipline"] == "boulder"

        r2 = self.client.get("/api/outdoor/spots")
        assert len(r2.json()["spots"]) == 1

    def test_delete_spot(self):
        r = self.client.post("/api/outdoor/spots", json={
            "id": "berdorf",
            "name": "Berdorf",
            "discipline": "boulder",
        })
        assert r.status_code == 200

        r2 = self.client.delete("/api/outdoor/spots/berdorf")
        assert r2.status_code == 200

        r3 = self.client.get("/api/outdoor/spots")
        assert len(r3.json()["spots"]) == 0

    def test_delete_nonexistent_spot(self):
        r = self.client.delete("/api/outdoor/spots/nonexistent")
        assert r.status_code == 404

    def test_duplicate_spot_id(self):
        self.client.post("/api/outdoor/spots", json={
            "id": "berdorf",
            "name": "Berdorf",
            "discipline": "boulder",
        })
        r = self.client.post("/api/outdoor/spots", json={
            "id": "berdorf",
            "name": "Berdorf 2",
            "discipline": "lead",
        })
        assert r.status_code == 409

    def test_log_outdoor_session(self):
        r = self.client.post("/api/outdoor/log", json={
            "date": "2026-03-15",
            "spot_name": "Berdorf",
            "discipline": "boulder",
            "duration_minutes": 180,
            "routes": [
                {
                    "name": "La Marie Rose",
                    "grade": "6a",
                    "attempts": [{"result": "sent"}],
                }
            ],
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_get_sessions_and_stats(self):
        self.client.post("/api/outdoor/log", json={
            "date": "2026-03-15",
            "spot_name": "Berdorf",
            "discipline": "boulder",
            "duration_minutes": 120,
            "routes": [
                {"name": "R1", "grade": "6a", "style": "onsight",
                 "attempts": [{"result": "sent"}]},
            ],
        })
        r = self.client.get("/api/outdoor/sessions")
        assert r.status_code == 200
        assert r.json()["count"] == 1

        r2 = self.client.get("/api/outdoor/stats")
        assert r2.status_code == 200
        assert r2.json()["total_sessions"] == 1


# ── E2E: outdoor cross-week integration ───────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_STATE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


class TestOutdoorE2ECrossWeek:
    """Full flow: add_outdoor → log routes → complete → JSONL on disk → regen → preserve."""

    @pytest.fixture(autouse=True)
    def setup_e2e(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.api.routers import outdoor as outdoor_router

        # Isolated state from test fixture (has assessment + goal for macrocycle)
        state_path = tmp_path / "user_state.json"
        shutil.copy2(_FIXTURE_STATE, state_path)
        monkeypatch.setattr(deps, "STATE_PATH", state_path)

        # Isolated log directory (simulates per-user logs dir)
        log_dir = tmp_path / "logs"
        monkeypatch.setattr(outdoor_router, "_FALLBACK_LOG_DIR", str(log_dir))

        from fastapi.testclient import TestClient
        from backend.api.main import app

        self.client = TestClient(app)
        self.tmp_path = tmp_path
        self.log_dir = log_dir
        self.state_path = state_path

    def _setup_macrocycle(self):
        """assessment → macrocycle → current week plan."""
        self.client.post("/api/assessment/compute", json={})
        self.client.post("/api/macrocycle/generate", json={"total_weeks": 12})
        r = self.client.get("/api/week/0")
        assert r.status_code == 200
        return r.json()

    def test_outdoor_log_persists_to_jsonl(self):
        """POST /api/outdoor/log must create a JSONL file on disk."""
        r = self.client.post("/api/outdoor/log", json={
            "date": "2026-03-01",
            "spot_name": "Berdorf",
            "discipline": "lead",
            "duration_minutes": 180,
            "routes": [
                {"name": "Roche aux Corbeaux", "grade": "6b+",
                 "style": "redpoint", "attempts": [{"result": "sent"}]},
            ],
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        jsonl = self.log_dir / "outdoor_sessions_2026.jsonl"
        assert jsonl.exists(), f"JSONL not found at {jsonl}"
        entry = json.loads(jsonl.read_text().strip())
        assert entry["spot_name"] == "Berdorf"
        assert entry["discipline"] == "lead"
        assert len(entry["routes"]) == 1

    def test_full_outdoor_flow_with_regen(self):
        """E2E: add → log → complete → regen macrocycle → outdoor fields preserved."""
        # 1. Setup macrocycle + get current week
        data = self._setup_macrocycle()
        week_plan = data["week_plan"]
        days = week_plan["weeks"][0]["days"]
        target_date = days[0]["date"]

        # 2. Add outdoor session to first day
        r = self.client.post("/api/replanner/events", json={
            "week_plan": week_plan,
            "events": [{
                "event_type": "add_outdoor",
                "date": target_date,
                "spot_name": "Berdorf",
                "discipline": "lead",
            }],
        })
        assert r.status_code == 200
        updated_plan = r.json()["week_plan"]
        target = next(d for d in updated_plan["weeks"][0]["days"]
                      if d["date"] == target_date)
        assert target["outdoor_spot_name"] == "Berdorf"
        assert target["outdoor_session_status"] == "planned"

        # 3. Log outdoor routes via POST
        r = self.client.post("/api/outdoor/log", json={
            "date": target_date,
            "spot_name": "Berdorf",
            "discipline": "lead",
            "duration_minutes": 180,
            "routes": [
                {"name": "Roche aux Corbeaux", "grade": "6b+",
                 "style": "redpoint", "attempts": [{"result": "fell"}, {"result": "sent"}]},
                {"name": "Hohllay Arete", "grade": "6a",
                 "style": "onsight", "attempts": [{"result": "sent"}]},
            ],
        })
        assert r.status_code == 200

        # 4. Verify JSONL on disk
        year = target_date[:4]
        jsonl = self.log_dir / f"outdoor_sessions_{year}.jsonl"
        assert jsonl.exists(), f"JSONL file missing at {jsonl}"
        entry = json.loads(jsonl.read_text().strip())
        assert entry["spot_name"] == "Berdorf"
        assert len(entry["routes"]) == 2

        # 5. Complete outdoor session
        r = self.client.post("/api/replanner/events", json={
            "week_plan": updated_plan,
            "events": [{
                "event_type": "complete_outdoor",
                "date": target_date,
            }],
        })
        assert r.status_code == 200
        completed_plan = r.json()["week_plan"]
        target = next(d for d in completed_plan["weeks"][0]["days"]
                      if d["date"] == target_date)
        assert target["outdoor_session_status"] == "done"

        # 6. Regenerate macrocycle (invalidates cache, stashes _prev_week_plan)
        r = self.client.post("/api/macrocycle/generate", json={"total_weeks": 12})
        assert r.status_code == 200

        # 7. Get current week again — merge_prev_week_sessions should restore outdoor
        r = self.client.get("/api/week/0")
        assert r.status_code == 200
        regen_plan = r.json()["week_plan"]
        regen_days = regen_plan["weeks"][0]["days"]

        # Match by weekday (macrocycle start may shift)
        from datetime import datetime
        target_wd = datetime.strptime(target_date, "%Y-%m-%d").weekday()
        regen_target = next(
            (d for d in regen_days
             if datetime.strptime(d["date"], "%Y-%m-%d").weekday() == target_wd),
            None,
        )
        assert regen_target is not None, "Target weekday not in regenerated plan"
        assert regen_target.get("outdoor_spot_name") == "Berdorf"
        assert regen_target.get("outdoor_discipline") == "lead"
        assert regen_target.get("outdoor_session_status") == "done"

        # 8. JSONL still readable after regen
        assert jsonl.exists()
        reloaded = json.loads(jsonl.read_text().strip())
        assert reloaded["spot_name"] == "Berdorf"

        # 9. GET /api/outdoor/sessions returns logged data
        r = self.client.get(f"/api/outdoor/sessions?since={target_date}")
        assert r.status_code == 200
        sessions = r.json()["sessions"]
        assert len(sessions) >= 1
        assert sessions[0]["spot_name"] == "Berdorf"
        assert len(sessions[0]["routes"]) == 2

    def test_outdoor_log_oserror_returns_500(self, monkeypatch):
        """OSError during JSONL write must return 500 with clear message."""
        from backend.api.routers import outdoor as outdoor_router

        def _boom(*args, **kwargs):
            raise OSError("Permission denied")

        monkeypatch.setattr(outdoor_router, "append_outdoor_session", _boom)

        r = self.client.post("/api/outdoor/log", json={
            "date": "2026-03-01",
            "spot_name": "Berdorf",
            "discipline": "lead",
            "duration_minutes": 60,
            "routes": [{"name": "R1", "grade": "5a",
                         "attempts": [{"result": "sent"}]}],
        })
        assert r.status_code == 500
        assert "Failed to write" in r.json()["detail"]
