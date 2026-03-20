"""Tests for A136 — Free climbing session backend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.engine.free_session import (
    FONT_GRADES,
    SURFACES,
    SURFACE_IDS,
    compute_free_session_load,
    compute_summary,
    font_to_index,
    get_phase_for_date,
    get_user_gyms,
    get_user_max_grade,
    index_to_font,
    is_lead_surface,
    normalize_grade,
    offset_grade,
    validate_climb,
)


# ── Grade utilities ──────────────────────────────────────────────────────


class TestFontToIndex:
    def test_first_grade(self):
        assert font_to_index("4A") == 0

    def test_last_grade(self):
        assert font_to_index("8C+") == len(FONT_GRADES) - 1

    def test_mid_grade(self):
        assert font_to_index("6A") == 9

    def test_case_insensitive(self):
        assert font_to_index("6a") == font_to_index("6A")
        assert font_to_index("7b+") == font_to_index("7B+")

    def test_invalid_grade(self):
        assert font_to_index("9A") is None
        assert font_to_index("") is None
        assert font_to_index("garbage") is None

    def test_with_spaces(self):
        assert font_to_index(" 6a ") == font_to_index("6A")


class TestIndexToFont:
    def test_valid_indices(self):
        assert index_to_font(0) == "4A"
        assert index_to_font(9) == "6A"

    def test_out_of_range(self):
        assert index_to_font(-1) is None
        assert index_to_font(100) is None


class TestOffsetGrade:
    def test_positive_offset(self):
        # 6A = index 9, +2 = index 11 = 6B
        assert offset_grade("6A", 2) == "6B"

    def test_negative_offset(self):
        # 7A = index 15, -3 = index 12 = 6B+
        assert offset_grade("7A", -3) == "6B+"

    def test_zero_offset(self):
        assert offset_grade("7B", 0) == "7B"

    def test_clamp_low(self):
        assert offset_grade("4A", -5) == "4A"  # can't go below 4A

    def test_clamp_high(self):
        assert offset_grade("8C+", 5) == "8C+"  # can't go above 8C+

    def test_invalid_base(self):
        assert offset_grade("9A", 0) is None


class TestNormalizeGrade:
    def test_lowercase(self):
        assert normalize_grade("6a") == "6A"
        assert normalize_grade("7b+") == "7B+"

    def test_already_uppercase(self):
        assert normalize_grade("6A") == "6A"

    def test_invalid(self):
        assert normalize_grade("banana") is None


# ── Validation ───────────────────────────────────────────────────────────


class TestValidateClimb:
    def test_valid_flash(self):
        climb = {"grade": "6A", "status": "flash", "attempts": 1}
        assert validate_climb(climb, "gym_boulder") is None

    def test_valid_sent(self):
        climb = {"grade": "6B", "status": "sent", "attempts": 3}
        assert validate_climb(climb, "gym_boulder") is None

    def test_valid_attempted(self):
        climb = {"grade": "7A", "status": "attempted", "attempts": 5}
        assert validate_climb(climb, "gym_boulder") is None

    def test_flash_must_have_1_attempt(self):
        climb = {"grade": "6A", "status": "flash", "attempts": 2}
        assert validate_climb(climb, "gym_boulder") is not None

    def test_sent_needs_2_plus_attempts(self):
        climb = {"grade": "6A", "status": "sent", "attempts": 1}
        assert validate_climb(climb, "gym_boulder") is not None

    def test_invalid_grade(self):
        climb = {"grade": "99Z", "status": "flash", "attempts": 1}
        assert validate_climb(climb, "gym_boulder") is not None

    def test_invalid_status(self):
        climb = {"grade": "6A", "status": "topped", "attempts": 1}
        assert validate_climb(climb, "gym_boulder") is not None

    def test_missing_attempts(self):
        climb = {"grade": "6A", "status": "flash"}
        assert validate_climb(climb, "gym_boulder") is not None

    def test_lead_valid_style(self):
        climb = {"grade": "6a", "status": "flash", "attempts": 1, "style": "onsight", "topped": True}
        assert validate_climb(climb, "gym_routes") is None

    def test_lead_invalid_style(self):
        climb = {"grade": "6a", "status": "flash", "attempts": 1, "style": "invalid"}
        assert validate_climb(climb, "gym_routes") is not None

    def test_boulder_ignores_style(self):
        # Style on boulder surface is just ignored (not validated)
        climb = {"grade": "6A", "status": "flash", "attempts": 1}
        assert validate_climb(climb, "board_kilter") is None


# ── Summary ──────────────────────────────────────────────────────────────


class TestComputeSummary:
    def test_empty_climbs(self):
        s = compute_summary([])
        assert s["total_climbs"] == 0
        assert s["send_rate"] == 0.0
        assert s["max_grade_sent"] is None

    def test_all_flash(self):
        climbs = [
            {"grade": "6A", "status": "flash", "attempts": 1},
            {"grade": "6B", "status": "flash", "attempts": 1},
        ]
        s = compute_summary(climbs)
        assert s["total_climbs"] == 2
        assert s["flashed"] == 2
        assert s["sent"] == 0
        assert s["send_rate"] == 1.0
        assert s["max_grade_sent"] == "6B"

    def test_mixed_statuses(self):
        climbs = [
            {"grade": "6A", "status": "flash", "attempts": 1},
            {"grade": "6B", "status": "sent", "attempts": 3},
            {"grade": "6C", "status": "attempted", "attempts": 5},
        ]
        s = compute_summary(climbs)
        assert s["total_climbs"] == 3
        assert s["flashed"] == 1
        assert s["sent"] == 1
        assert s["attempted"] == 1
        assert s["max_grade_sent"] == "6B"
        assert s["max_grade_attempted"] == "6C"
        assert s["send_rate"] == round(2 / 3, 2)

    def test_all_attempted(self):
        climbs = [
            {"grade": "7A", "status": "attempted", "attempts": 3},
        ]
        s = compute_summary(climbs)
        assert s["send_rate"] == 0.0
        assert s["max_grade_sent"] is None
        assert s["max_grade_attempted"] == "7A"


# ── Load calculation ─────────────────────────────────────────────────────


class TestComputeLoad:
    def test_empty_climbs(self):
        assert compute_free_session_load([], "7A") == 0.0

    def test_single_flash_at_max(self):
        climbs = [{"grade": "7A", "status": "flash", "attempts": 1}]
        load = compute_free_session_load(climbs, "7A")
        # relative = 1.0, status = 0.8, mod = 1.0 → 0.8 × SCALE(4.0) = 3.2
        assert load == 3.2

    def test_single_sent_below_max(self):
        climbs = [{"grade": "6A", "status": "sent", "attempts": 2}]
        load = compute_free_session_load(climbs, "7A")
        # 7A index = 15, 6A index = 9
        # relative = 9/15 = 0.6, status = 1.0, mod = 1.1 → 0.66 × 4.0 = 2.64 → round = 2.6
        assert load == 2.6

    def test_multiple_climbs(self):
        climbs = [
            {"grade": "6A", "status": "flash", "attempts": 1},
            {"grade": "6B", "status": "sent", "attempts": 3},
            {"grade": "7A", "status": "attempted", "attempts": 4},
        ]
        load = compute_free_session_load(climbs, "7A")
        assert load > 0
        assert isinstance(load, float)

    def test_invalid_max_grade(self):
        climbs = [{"grade": "6A", "status": "flash", "attempts": 1}]
        assert compute_free_session_load(climbs, "banana") == 0.0

    def test_attempt_modifier_3plus(self):
        climbs = [{"grade": "7A", "status": "attempted", "attempts": 5}]
        load = compute_free_session_load(climbs, "7A")
        # relative = 1.0, status = 0.6, mod = 1.3 → 0.78 × 4.0 = 3.12
        assert load == 3.1


# ── Phase lookup ─────────────────────────────────────────────────────────


class TestGetPhaseForDate:
    def test_no_macrocycle(self):
        assert get_phase_for_date({}, "2026-03-20") == "base"

    def test_first_phase(self):
        state = {
            "macrocycle": {
                "start_date": "2026-03-16",
                "phases": [
                    {"phase_id": "base", "duration_weeks": 4},
                    {"phase_id": "strength_power", "duration_weeks": 3},
                ],
            }
        }
        assert get_phase_for_date(state, "2026-03-20") == "base"

    def test_second_phase(self):
        state = {
            "macrocycle": {
                "start_date": "2026-01-05",
                "phases": [
                    {"phase_id": "base", "duration_weeks": 4},
                    {"phase_id": "strength_power", "duration_weeks": 3},
                ],
            }
        }
        assert get_phase_for_date(state, "2026-02-10") == "strength_power"

    def test_past_end(self):
        state = {
            "macrocycle": {
                "start_date": "2026-01-05",
                "phases": [
                    {"phase_id": "base", "duration_weeks": 2},
                ],
            }
        }
        assert get_phase_for_date(state, "2026-12-01") == "base"


# ── Helper functions ─────────────────────────────────────────────────────


class TestHelpers:
    def test_is_lead_surface(self):
        assert is_lead_surface("gym_routes") is True
        assert is_lead_surface("gym_boulder") is False
        assert is_lead_surface("board_kilter") is False

    def test_get_user_max_grade_boulder(self):
        state = {"assessment": {"grades": {"boulder_max_rp": "7C", "lead_max_rp": "7a+"}}}
        assert get_user_max_grade(state, "gym_boulder") == "7C"
        assert get_user_max_grade(state, "board_kilter") == "7C"

    def test_get_user_max_grade_lead(self):
        state = {"assessment": {"grades": {"boulder_max_rp": "7C", "lead_max_rp": "7a+"}}}
        assert get_user_max_grade(state, "gym_routes") == "7a+"

    def test_get_user_max_grade_missing(self):
        assert get_user_max_grade({}, "gym_boulder") is None

    def test_get_user_gyms(self):
        state = {"equipment": {"gyms": [{"gym_id": "bkl", "name": "BKL", "equipment": []}]}}
        gyms = get_user_gyms(state)
        assert len(gyms) == 1
        assert gyms[0]["name"] == "BKL"

    def test_get_user_gyms_empty(self):
        assert get_user_gyms({}) == []


# ── API integration tests ────────────────────────────────────────────────


@pytest.fixture
def client():
    from backend.api.main import app
    return TestClient(app)


@pytest.fixture
def _seed_state():
    """Seed user_state with assessment grades + macrocycle for API tests."""
    from backend.api.deps import load_state, save_state

    state = load_state(None)
    state.setdefault("assessment", {})["grades"] = {
        "boulder_max_rp": "7A",
        "boulder_max_os": "6C",
        "lead_max_rp": "7a+",
        "lead_max_os": "6c+",
    }
    state["macrocycle"] = {
        "start_date": "2026-03-02",
        "phases": [
            {"phase_id": "base", "duration_weeks": 4},
            {"phase_id": "strength_power", "duration_weeks": 3},
        ],
    }
    state["equipment"] = {
        "home": [],
        "gyms": [
            {"gym_id": "bkl", "name": "BKL", "equipment": ["gym_boulder", "board_kilter"]},
        ],
    }
    state["free_sessions"] = []
    save_state(state, None)
    yield
    # Cleanup
    state = load_state(None)
    state.pop("free_sessions", None)
    save_state(state, None)


class TestSurfacesEndpoint:
    def test_returns_all_surfaces(self, client, _seed_state):
        r = client.get("/api/free-session/surfaces")
        assert r.status_code == 200
        data = r.json()
        assert len(data["surfaces"]) == 5
        ids = {s["id"] for s in data["surfaces"]}
        assert ids == SURFACE_IDS

    def test_returns_gyms(self, client, _seed_state):
        r = client.get("/api/free-session/surfaces")
        data = r.json()
        assert len(data["gyms"]) == 1
        assert data["gyms"][0]["name"] == "BKL"


class TestPresetsEndpoint:
    def test_boulder_presets(self, client, _seed_state):
        r = client.get("/api/free-session/presets?surface=gym_boulder")
        assert r.status_code == 200
        data = r.json()
        assert len(data["presets"]) == 4
        ids = {p["id"] for p in data["presets"]}
        assert "free_volume" in ids
        assert "free_projecting" in ids

    def test_lead_presets(self, client, _seed_state):
        r = client.get("/api/free-session/presets?surface=gym_routes")
        assert r.status_code == 200
        data = r.json()
        assert len(data["presets"]) == 3
        ids = {p["id"] for p in data["presets"]}
        assert "free_lead_volume" in ids

    def test_presets_have_target_grade(self, client, _seed_state):
        r = client.get("/api/free-session/presets?surface=gym_boulder")
        data = r.json()
        # Volume has offset -3, user max 7A (index 12) → index 9 = 6A+
        volume = next(p for p in data["presets"] if p["id"] == "free_volume")
        assert volume["target_grade"] is not None

    def test_presets_have_phase_tip(self, client, _seed_state):
        r = client.get("/api/free-session/presets?surface=gym_boulder")
        data = r.json()
        assert data["free_mode_tip"]  # not empty
        for p in data["presets"]:
            assert p["phase_tip"]  # each preset has a tip

    def test_invalid_surface(self, client, _seed_state):
        r = client.get("/api/free-session/presets?surface=invalid")
        assert r.status_code == 400


class TestStartEndpoint:
    def test_start_template_session(self, client, _seed_state):
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "board_kilter",
            "gym_name": "BKL",
            "session_mode": "template",
            "preset_id": "free_volume",
            "context": "standalone",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == "free_20260320_1"
        assert data["phase_at_time"] in ("base", "strength_power", "power_endurance", "performance", "deload")
        assert data["tip"]
        assert data["target_grade"] is not None

    def test_start_free_mode(self, client, _seed_state):
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "gym_boulder",
            "session_mode": "free",
            "context": "standalone",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["target_grade"] is None
        assert data["rest_seconds"] is None

    def test_start_template_without_preset(self, client, _seed_state):
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "gym_boulder",
            "session_mode": "template",
            "context": "standalone",
        })
        assert r.status_code == 400

    def test_start_invalid_surface(self, client, _seed_state):
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "outdoor_crag",
            "session_mode": "free",
            "context": "standalone",
        })
        assert r.status_code == 400

    def test_start_invalid_context(self, client, _seed_state):
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "gym_boulder",
            "session_mode": "free",
            "context": "banana",
        })
        assert r.status_code == 400

    def test_multiple_sessions_same_day(self, client, _seed_state):
        # First session
        r1 = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "gym_boulder",
            "session_mode": "free",
            "context": "standalone",
        })
        assert r1.json()["session_id"] == "free_20260320_1"

        # Second session
        r2 = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "board_kilter",
            "session_mode": "free",
            "context": "add_on",
        })
        assert r2.json()["session_id"] == "free_20260320_2"

    def test_gym_name_optional(self, client, _seed_state):
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "gym_boulder",
            "session_mode": "free",
            "context": "standalone",
        })
        assert r.status_code == 200


class TestLogClimbEndpoint:
    def _start_session(self, client):
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "gym_boulder",
            "session_mode": "free",
            "context": "standalone",
        })
        return r.json()["session_id"]

    def test_log_valid_climb(self, client, _seed_state):
        sid = self._start_session(client)
        r = client.post(f"/api/free-session/{sid}/log-climb", json={
            "grade": "6a",
            "status": "flash",
            "attempts": 1,
        })
        assert r.status_code == 200
        assert r.json()["index"] == 1

    def test_log_multiple_climbs(self, client, _seed_state):
        sid = self._start_session(client)
        r1 = client.post(f"/api/free-session/{sid}/log-climb", json={
            "grade": "6A", "status": "flash", "attempts": 1,
        })
        r2 = client.post(f"/api/free-session/{sid}/log-climb", json={
            "grade": "6B", "status": "sent", "attempts": 3,
        })
        assert r1.json()["index"] == 1
        assert r2.json()["index"] == 2

    def test_log_invalid_grade(self, client, _seed_state):
        sid = self._start_session(client)
        r = client.post(f"/api/free-session/{sid}/log-climb", json={
            "grade": "banana", "status": "flash", "attempts": 1,
        })
        assert r.status_code == 422

    def test_log_flash_wrong_attempts(self, client, _seed_state):
        sid = self._start_session(client)
        r = client.post(f"/api/free-session/{sid}/log-climb", json={
            "grade": "6A", "status": "flash", "attempts": 3,
        })
        assert r.status_code == 422

    def test_log_to_nonexistent_session(self, client, _seed_state):
        r = client.post("/api/free-session/free_99999999_1/log-climb", json={
            "grade": "6A", "status": "flash", "attempts": 1,
        })
        assert r.status_code == 404

    def test_log_to_finished_session(self, client, _seed_state):
        sid = self._start_session(client)
        # Finish it
        client.post(f"/api/free-session/{sid}/finish", json={})
        # Try logging
        r = client.post(f"/api/free-session/{sid}/log-climb", json={
            "grade": "6A", "status": "flash", "attempts": 1,
        })
        assert r.status_code == 400


class TestFinishEndpoint:
    def _start_and_log(self, client):
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "gym_boulder",
            "gym_name": "BKL",
            "session_mode": "template",
            "preset_id": "free_volume",
            "context": "standalone",
        })
        sid = r.json()["session_id"]
        # Log some climbs
        for grade, status, att in [("6A", "flash", 1), ("6B", "sent", 2), ("6C", "attempted", 3)]:
            client.post(f"/api/free-session/{sid}/log-climb", json={
                "grade": grade, "status": status, "attempts": att,
            })
        return sid

    def test_finish_with_climbs(self, client, _seed_state):
        sid = self._start_and_log(client)
        r = client.post(f"/api/free-session/{sid}/finish", json={
            "overall_feel": "good",
            "notes": "Great session",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["summary"]["total_climbs"] == 3
        assert data["summary"]["flashed"] == 1
        assert data["summary"]["sent"] == 1
        assert data["summary"]["attempted"] == 1
        assert data["summary"]["send_rate"] == round(2 / 3, 2)
        assert data["duration_minutes"] is not None
        assert data["load_score"] > 0

    def test_finish_empty_session(self, client, _seed_state):
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "gym_boulder",
            "session_mode": "free",
            "context": "standalone",
        })
        sid = r.json()["session_id"]
        r = client.post(f"/api/free-session/{sid}/finish", json={})
        assert r.status_code == 200
        assert r.json()["summary"]["total_climbs"] == 0

    def test_finish_invalid_feel(self, client, _seed_state):
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "gym_boulder",
            "session_mode": "free",
            "context": "standalone",
        })
        sid = r.json()["session_id"]
        r = client.post(f"/api/free-session/{sid}/finish", json={
            "overall_feel": "terrible",
        })
        assert r.status_code == 400

    def test_double_finish_rejected(self, client, _seed_state):
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "gym_boulder",
            "session_mode": "free",
            "context": "standalone",
        })
        sid = r.json()["session_id"]
        client.post(f"/api/free-session/{sid}/finish", json={})
        r2 = client.post(f"/api/free-session/{sid}/finish", json={})
        assert r2.status_code == 400


class TestHistoryEndpoint:
    def test_history_returns_sessions(self, client, _seed_state):
        # Start and finish a session
        r = client.post("/api/free-session/start", json={
            "date": "2026-03-20",
            "surface": "gym_boulder",
            "session_mode": "free",
            "context": "standalone",
        })
        sid = r.json()["session_id"]
        client.post(f"/api/free-session/{sid}/finish", json={"overall_feel": "good"})

        r = client.get("/api/free-session/history?date=2026-03-20")
        assert r.status_code == 200
        data = r.json()
        assert len(data["sessions"]) >= 1

    def test_history_empty_date(self, client, _seed_state):
        r = client.get("/api/free-session/history?date=2099-01-01")
        assert r.status_code == 200
        assert len(r.json()["sessions"]) == 0
