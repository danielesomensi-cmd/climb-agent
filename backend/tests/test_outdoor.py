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
    compute_outdoor_load_score,
    compute_outdoor_stats,
    load_outdoor_sessions,
    remove_outdoor_session,
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


# ── Load score ─────────────────────────────────────────────────────────


class TestOutdoorLoadScore:
    def test_empty_routes_returns_zero(self):
        entry = _make_entry(routes=[])
        assert compute_outdoor_load_score(entry) == 0

    def test_single_route(self):
        entry = _make_entry(
            duration_minutes=120,
            routes=[{"name": "R1", "grade": "6a", "style": "redpoint",
                     "attempts": [{"result": "sent"}]}],
        )
        score = compute_outdoor_load_score(entry)
        assert score > 0

    def test_multiple_routes_sum(self):
        single = _make_entry(
            duration_minutes=120,
            routes=[{"name": "R1", "grade": "6a", "style": "redpoint",
                     "attempts": [{"result": "sent"}]}],
        )
        double = _make_entry(
            duration_minutes=120,
            routes=[
                {"name": "R1", "grade": "6a", "style": "redpoint",
                 "attempts": [{"result": "sent"}]},
                {"name": "R2", "grade": "6a", "style": "redpoint",
                 "attempts": [{"result": "sent"}]},
            ],
        )
        assert compute_outdoor_load_score(double) > compute_outdoor_load_score(single)

    def test_style_modifiers_ordering(self):
        """onsight > flash > redpoint > project > repeat."""
        def _score(style):
            return compute_outdoor_load_score(_make_entry(
                duration_minutes=120,
                routes=[{"name": "R", "grade": "7a", "style": style,
                         "attempts": [{"result": "sent"}]}],
            ))

        assert _score("onsight") > _score("flash") > _score("redpoint") > _score("project") > _score("repeat")

    def test_duration_clamping_low(self):
        """Duration 30 min → factor clamped to 0.5."""
        short = _make_entry(
            duration_minutes=30,
            routes=[{"name": "R", "grade": "6a", "style": "redpoint",
                     "attempts": [{"result": "sent"}]}],
        )
        very_short = _make_entry(
            duration_minutes=10,
            routes=[{"name": "R", "grade": "6a", "style": "redpoint",
                     "attempts": [{"result": "sent"}]}],
        )
        # Both clamped to 0.5 → same score
        assert compute_outdoor_load_score(short) == compute_outdoor_load_score(very_short)

    def test_duration_clamping_high(self):
        """Duration 300 min → factor clamped to 1.5."""
        long = _make_entry(
            duration_minutes=300,
            routes=[{"name": "R", "grade": "6a", "style": "redpoint",
                     "attempts": [{"result": "sent"}]}],
        )
        very_long = _make_entry(
            duration_minutes=500,
            routes=[{"name": "R", "grade": "6a", "style": "redpoint",
                     "attempts": [{"result": "sent"}]}],
        )
        assert compute_outdoor_load_score(long) == compute_outdoor_load_score(very_long)

    def test_unknown_grade_fallback(self):
        """Unknown grade uses fallback weight of 10."""
        entry = _make_entry(
            duration_minutes=120,
            routes=[{"name": "R", "grade": "V5", "style": "redpoint",
                     "attempts": [{"result": "sent"}]}],
        )
        score = compute_outdoor_load_score(entry)
        assert score == 10  # 10 * 1.0 * 1.0

    def test_determinism(self):
        entry = _make_entry(
            duration_minutes=120,
            routes=[
                {"name": "R1", "grade": "6a", "style": "onsight",
                 "attempts": [{"result": "sent"}]},
                {"name": "R2", "grade": "7a", "style": "redpoint",
                 "attempts": [{"result": "sent"}]},
            ],
        )
        s1 = compute_outdoor_load_score(entry)
        s2 = compute_outdoor_load_score(entry)
        assert s1 == s2

    def test_stats_include_load(self):
        """compute_outdoor_stats should include total_load and avg_load_per_session."""
        sessions = [
            _make_entry(
                duration_minutes=120,
                routes=[{"name": "R1", "grade": "6a", "style": "redpoint",
                         "attempts": [{"result": "sent"}]}],
            ),
        ]
        stats = compute_outdoor_stats(sessions)
        assert "total_load" in stats
        assert "avg_load_per_session" in stats
        assert stats["total_load"] > 0
        assert stats["avg_load_per_session"] == stats["total_load"]

    def test_stats_empty_sessions_load(self):
        stats = compute_outdoor_stats([])
        assert stats["total_load"] == 0
        assert stats["avg_load_per_session"] == 0.0


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


# ── Outdoor ripple ─────────────────────────────────────────────────────


class TestOutdoorRipple:
    """Ripple effect after completing a high-load outdoor session."""

    def _make_week_plan(self, day1_sessions, day2_sessions):
        return {
            "start_date": "2026-03-16",
            "weeks": [{
                "days": [
                    {"date": "2026-03-16", "weekday": "mon", "sessions": day1_sessions,
                     "outdoor_spot_name": "Berdorf", "outdoor_session_status": "planned"},
                    {"date": "2026-03-17", "weekday": "tue", "sessions": day2_sessions},
                    {"date": "2026-03-18", "weekday": "wed", "sessions": []},
                    {"date": "2026-03-19", "weekday": "thu", "sessions": []},
                    {"date": "2026-03-20", "weekday": "fri", "sessions": []},
                    {"date": "2026-03-21", "weekday": "sat", "sessions": []},
                    {"date": "2026-03-22", "weekday": "sun", "sessions": []},
                ],
            }],
        }

    def _make_session(self, sid, **kwargs):
        s = {
            "session_id": sid,
            "slot": "evening",
            "location": "gym",
            "status": "planned",
            "estimated_load_score": 40,
            "intensity": "medium",
            "tags": {},
        }
        s.update(kwargs)
        return s

    def test_high_load_triggers_ripple(self):
        from backend.engine.replanner_v1 import apply_events
        plan = self._make_week_plan(
            [],
            [self._make_session("strength_long", intensity="max", tags={"hard": True, "finger": True})],
        )
        updated = apply_events(plan, [
            {"event_type": "complete_outdoor", "date": "2026-03-16", "outdoor_load_score": 70},
        ])
        day2 = updated["weeks"][0]["days"][1]
        assert day2["sessions"][0]["session_id"] == "complementary_conditioning"
        assert "outdoor_ripple" in day2["sessions"][0].get("constraints_applied", [])

    def test_low_load_no_ripple(self):
        from backend.engine.replanner_v1 import apply_events
        plan = self._make_week_plan(
            [],
            [self._make_session("strength_long", intensity="max", tags={"hard": True, "finger": True})],
        )
        updated = apply_events(plan, [
            {"event_type": "complete_outdoor", "date": "2026-03-16", "outdoor_load_score": 30},
        ])
        day2 = updated["weeks"][0]["days"][1]
        assert day2["sessions"][0]["session_id"] == "strength_long"

    def test_replaces_hard_to_complementary(self):
        from backend.engine.replanner_v1 import apply_events
        plan = self._make_week_plan(
            [],
            [self._make_session("power_contact_gym", intensity="max", tags={"hard": True})],
        )
        updated = apply_events(plan, [
            {"event_type": "complete_outdoor", "date": "2026-03-16", "outdoor_load_score": 80},
        ])
        day2 = updated["weeks"][0]["days"][1]
        assert day2["sessions"][0]["session_id"] == "complementary_conditioning"

    def test_replaces_medium_to_recovery(self):
        from backend.engine.replanner_v1 import apply_events
        plan = self._make_week_plan(
            [],
            [self._make_session("endurance_aerobic_gym", intensity="medium", tags={"hard": False})],
        )
        updated = apply_events(plan, [
            {"event_type": "complete_outdoor", "date": "2026-03-16", "outdoor_load_score": 75},
        ])
        day2 = updated["weeks"][0]["days"][1]
        assert day2["sessions"][0]["session_id"] == "deload_recovery"

    def test_keeps_low_sessions(self):
        from backend.engine.replanner_v1 import apply_events
        plan = self._make_week_plan(
            [],
            [self._make_session("prehab_maintenance", intensity="low", tags={"hard": False})],
        )
        updated = apply_events(plan, [
            {"event_type": "complete_outdoor", "date": "2026-03-16", "outdoor_load_score": 80},
        ])
        day2 = updated["weeks"][0]["days"][1]
        assert day2["sessions"][0]["session_id"] == "prehab_maintenance"


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


# ── Onboarding outdoor spots ───────────────────────────────────────────


class TestOnboardingOutdoorSpots:
    """Outdoor spots saved via onboarding flow."""

    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.api.routers import outdoor as outdoor_router

        state_path = tmp_path / "user_state.json"
        state_path.write_text(json.dumps({"schema_version": "1.5"}))
        monkeypatch.setattr(deps, "STATE_PATH", state_path)

        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr(outdoor_router, "_FALLBACK_LOG_DIR", log_dir)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)
        self.state_path = state_path

    def _onboarding_data(self, spots=None):
        return {
            "profile": {"name": "Test", "age": 30, "weight_kg": 70, "height_cm": 175},
            "experience": {"climbing_years": 5, "structured_training_years": 2},
            "grades": {"lead_max_rp": "6c", "lead_max_os": "6a"},
            "goal": {"goal_type": "lead_grade", "discipline": "lead",
                     "target_grade": "7a", "target_style": "redpoint",
                     "current_grade": "6c", "deadline": "2026-12-31"},
            "self_eval": {"primary_weakness": "finger_strength", "secondary_weakness": "endurance"},
            "tests": {},
            "limitations": [],
            "equipment": {"home_enabled": True, "home": ["hangboard"], "gyms": [{"name": "MyGym", "equipment": ["gym_boulder"]}]},
            "availability": {"mon": {"evening": {"available": True, "preferred_location": "gym"}}},
            "planning_prefs": {"target_training_days_per_week": 3, "hard_day_cap_per_week": 2},
            "trips": [],
            "outdoor_spots": spots or [],
        }

    def test_onboarding_saves_spots(self):
        data = self._onboarding_data(spots=[
            {"name": "Berdorf", "discipline": "boulder"},
            {"name": "Freyr", "discipline": "lead"},
        ])
        r = self.client.post("/api/onboarding/complete", json=data)
        assert r.status_code == 200

        state = json.loads(self.state_path.read_text())
        spots = state.get("outdoor_spots", [])
        assert len(spots) == 2
        assert spots[0]["name"] == "Berdorf"
        assert spots[0]["discipline"] == "boulder"
        assert spots[0]["id"].startswith("spot_")
        assert spots[1]["name"] == "Freyr"

    def test_onboarding_empty_spots_ok(self):
        data = self._onboarding_data(spots=[])
        r = self.client.post("/api/onboarding/complete", json=data)
        assert r.status_code == 200

        state = json.loads(self.state_path.read_text())
        assert state.get("outdoor_spots") == []


class TestRemoveOutdoorSession:
    """Tests for remove_outdoor_session (undo support)."""

    def test_remove_deletes_matching_date(self, tmp_path):
        log_dir = str(tmp_path / "logs")
        entry = {
            "log_version": "outdoor.v1",
            "date": "2026-03-02",
            "spot_name": "Berdorf",
            "discipline": "lead",
            "duration_minutes": 90,
            "routes": [{"name": "R1", "grade": "6a", "attempts": [{"result": "sent"}]}],
        }
        append_outdoor_session(entry, log_dir)
        assert len(load_outdoor_sessions(log_dir)) == 1

        removed = remove_outdoor_session(log_dir, "2026-03-02")
        assert removed == 1
        assert len(load_outdoor_sessions(log_dir)) == 0

    def test_remove_keeps_other_dates(self, tmp_path):
        log_dir = str(tmp_path / "logs")
        for d in ["2026-03-01", "2026-03-02", "2026-03-03"]:
            append_outdoor_session({
                "log_version": "outdoor.v1", "date": d,
                "spot_name": "Spot", "discipline": "boulder",
                "duration_minutes": 60,
                "routes": [{"name": "R", "grade": "5a", "attempts": [{"result": "sent"}]}],
            }, log_dir)
        assert len(load_outdoor_sessions(log_dir)) == 3

        removed = remove_outdoor_session(log_dir, "2026-03-02")
        assert removed == 1
        remaining = load_outdoor_sessions(log_dir)
        assert len(remaining) == 2
        assert {e["date"] for e in remaining} == {"2026-03-01", "2026-03-03"}

    def test_remove_nonexistent_date_returns_zero(self, tmp_path):
        log_dir = str(tmp_path / "logs")
        removed = remove_outdoor_session(log_dir, "2026-03-02")
        assert removed == 0

    def test_undo_redo_no_duplicates(self, tmp_path):
        """Simulate: log → undo (remove) → re-log → only 1 entry."""
        log_dir = str(tmp_path / "logs")
        entry = {
            "log_version": "outdoor.v1",
            "date": "2026-03-02",
            "spot_name": "Berdorf",
            "discipline": "lead",
            "duration_minutes": 90,
            "routes": [{"name": "R1", "grade": "6a", "attempts": [{"result": "sent"}]}],
        }
        # Log
        append_outdoor_session(entry, log_dir)
        assert len(load_outdoor_sessions(log_dir)) == 1

        # Undo
        remove_outdoor_session(log_dir, "2026-03-02")
        assert len(load_outdoor_sessions(log_dir)) == 0

        # Re-log with different routes
        entry2 = {**entry, "routes": [
            {"name": "R2", "grade": "6b", "attempts": [{"result": "sent"}]},
            {"name": "R3", "grade": "6a+", "attempts": [{"result": "sent"}]},
        ]}
        append_outdoor_session(entry2, log_dir)
        sessions = load_outdoor_sessions(log_dir)
        assert len(sessions) == 1
        assert len(sessions[0]["routes"]) == 2
        assert sessions[0]["routes"][0]["name"] == "R2"
