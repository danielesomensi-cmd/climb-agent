"""A225 — Outdoor session backend (v2 shape + active lifecycle + resolver).

Phase 1: outdoor.v2 log-shape validation (backward-compatible with v1).
Phases 2-4 add their own test classes below as implemented.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.engine.outdoor_log import (
    CURRENT_LOG_VERSION,
    OUTDOOR_SESSION_MAX_MINUTES,
    derive_outdoor_duration,
    validate_outdoor_entry,
)
from backend.engine.outdoor_resolver import (
    OutdoorResolveError,
    resolve_nutrition,
    resolve_outdoor_day,
    resolve_strategy,
)

STRATEGY_BASE_FIELDS = [
    "warmup_protocol", "target_burns", "rest_between_attempts_min", "stop_criteria",
    "skin_tips", "time_of_day_advice", "hours_plan", "downgrade_rule",
]


def _base_v1_entry(**overrides):
    """A minimal valid outdoor.v1 entry (no v2 optional fields)."""
    entry = {
        "log_version": "outdoor.v1",
        "date": "2026-06-19",
        "spot_name": "Arco",
        "discipline": "lead",
        "duration_minutes": 120,
        "routes": [
            {"name": "Pillar", "grade": "7a", "attempts": [{"result": "sent"}]},
        ],
    }
    entry.update(overrides)
    return entry


# --------------------------------------------------------------------------- #
# Phase 1 — outdoor.v2 log shape
# --------------------------------------------------------------------------- #

class TestOutdoorV2Validation:
    def test_current_version_is_v2(self):
        assert CURRENT_LOG_VERSION == "outdoor.v2"

    def test_v1_log_still_valid(self):
        """A pre-A225 v1 log (no day_type/route_profile) stays valid."""
        assert validate_outdoor_entry(_base_v1_entry()) == []

    def test_v2_log_with_new_fields_valid(self):
        entry = _base_v1_entry(
            log_version="outdoor.v2",
            day_type="project",
            route_profile={
                "wall_angle": "overhang",
                "route_length": "long_endurance",
                "hold_style": "crimp",
                "target_grade_relative": "at_or_above_limit",
            },
            conditions={"temperature": 12.5, "condition_band": "prime"},
        )
        assert validate_outdoor_entry(entry) == []

    def test_v2_missing_optional_fields_valid(self):
        """v2 with NONE of the new fields → still valid (defaults clean)."""
        assert validate_outdoor_entry(_base_v1_entry(log_version="outdoor.v2")) == []

    def test_partial_route_profile_valid(self):
        """Graceful degradation — one dimension only is allowed."""
        entry = _base_v1_entry(
            log_version="outdoor.v2",
            route_profile={"wall_angle": "slab"},
        )
        assert validate_outdoor_entry(entry) == []

    def test_invalid_log_version_rejected(self):
        errors = validate_outdoor_entry(_base_v1_entry(log_version="outdoor.v3"))
        assert any("log_version" in e for e in errors)

    def test_invalid_day_type_rejected(self):
        errors = validate_outdoor_entry(
            _base_v1_entry(log_version="outdoor.v2", day_type="sending")
        )
        assert any("day_type" in e for e in errors)

    def test_invalid_route_profile_value_rejected(self):
        errors = validate_outdoor_entry(
            _base_v1_entry(log_version="outdoor.v2", route_profile={"wall_angle": "cave"})
        )
        assert any("wall_angle" in e for e in errors)

    def test_unknown_route_profile_key_rejected(self):
        errors = validate_outdoor_entry(
            _base_v1_entry(log_version="outdoor.v2", route_profile={"angle": "slab"})
        )
        assert any("route_profile" in e for e in errors)

    def test_invalid_condition_band_rejected(self):
        errors = validate_outdoor_entry(
            _base_v1_entry(log_version="outdoor.v2", conditions={"condition_band": "poor"})
        )
        assert any("condition_band" in e for e in errors)

    def test_invalid_temperature_rejected(self):
        errors = validate_outdoor_entry(
            _base_v1_entry(log_version="outdoor.v2", conditions={"temperature": "cold"})
        )
        assert any("temperature" in e for e in errors)

    def test_v1_with_legacy_conditions_dict_still_valid(self):
        """v1 logs that already used the free-form conditions dict are untouched."""
        entry = _base_v1_entry(conditions={"notes": "windy", "sky": "clear"})
        assert validate_outdoor_entry(entry) == []


# --------------------------------------------------------------------------- #
# Phase 2 — duration derivation (cap on stale timer)
# --------------------------------------------------------------------------- #

class TestDeriveDuration:
    NOW = datetime(2026, 6, 19, 18, 0, tzinfo=timezone.utc)

    def _started(self, minutes_ago):
        return (self.NOW - timedelta(minutes=minutes_ago)).isoformat()

    def test_timer_normal(self):
        out = derive_outdoor_duration(self._started(150), self.NOW)
        assert out["minutes"] == 150
        assert out["capped"] is False
        assert out["source"] == "timer"

    def test_floor_at_one_minute(self):
        out = derive_outdoor_duration(self._started(0), self.NOW)
        assert out["minutes"] == 1

    def test_manual_override_wins(self):
        out = derive_outdoor_duration(self._started(150), self.NOW, manual_override=90)
        assert out["minutes"] == 90
        assert out["source"] == "manual"
        assert out["capped"] is False

    def test_stale_timer_capped_and_flagged(self):
        """Started 25h ago, no manual value → cap + flag (never write 1500)."""
        out = derive_outdoor_duration(self._started(25 * 60), self.NOW)
        assert out["minutes"] == OUTDOOR_SESSION_MAX_MINUTES
        assert out["capped"] is True
        assert out["raw_minutes"] == 25 * 60
        assert out["source"] == "timer_capped"

    def test_stale_timer_with_manual_override_uses_manual(self):
        """A reasonable manual value must NOT be overwritten by a stale timer."""
        out = derive_outdoor_duration(self._started(25 * 60), self.NOW, manual_override=180)
        assert out["minutes"] == 180
        assert out["capped"] is False
        assert out["source"] == "manual"

    def test_missing_started_at_no_override_returns_none(self):
        out = derive_outdoor_duration(None, self.NOW)
        assert out["minutes"] is None
        assert out["source"] == "none"

    def test_invalid_started_at_returns_none(self):
        out = derive_outdoor_duration("not-a-date", self.NOW)
        assert out["minutes"] is None

    def test_bool_override_ignored(self):
        """A stray bool must not be treated as a manual minute value."""
        out = derive_outdoor_duration(self._started(120), self.NOW, manual_override=True)
        assert out["source"] == "timer"
        assert out["minutes"] == 120


# --------------------------------------------------------------------------- #
# Phase 2 — active session lifecycle (TestClient)
# --------------------------------------------------------------------------- #

class TestActiveSessionLifecycle:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.engine import storage

        self.state_path = tmp_path / "user_state.json"
        self.state_path.write_text(json.dumps({"schema_version": "1.5", "outdoor_spots": []}))
        monkeypatch.setattr(storage, "STATE_PATH", self.state_path)
        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        monkeypatch.setattr(deps, "STATE_PATH", self.state_path)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def _rewind_started_at(self, session_id, minutes_ago):
        """Reach into the persisted state and age an active session's timer."""
        state = json.loads(self.state_path.read_text())
        started = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
        for s in state["outdoor_active_sessions"]:
            if s["session_id"] == session_id:
                s["started_at"] = started
        self.state_path.write_text(json.dumps(state))

    def test_start_returns_active_session(self):
        r = self.client.post("/api/outdoor/session/start", json={
            "date": "2026-06-19", "spot_name": "Arco", "discipline": "lead", "day_type": "project",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "active"
        assert body["session_id"].startswith("outdoor_active_20260619")
        assert body["started_at"]

    def test_full_lifecycle_start_then_finish(self):
        start = self.client.post("/api/outdoor/session/start", json={
            "date": "2026-06-19", "spot_name": "Arco", "discipline": "lead", "day_type": "project",
        }).json()
        sid = start["session_id"]

        fin = self.client.post(f"/api/outdoor/session/{sid}/finish", json={
            "spot_name": "Arco",
            "discipline": "lead",
            "route_profile": {"wall_angle": "overhang"},
            "routes": [{"name": "Pillar", "grade": "7a", "attempts": [{"result": "sent"}]}],
        })
        assert fin.status_code == 200
        body = fin.json()
        assert body["status"] == "done"
        assert body["duration_source"] == "timer"
        assert body["duration_minutes"] >= 1

        # Log persisted to outdoor_logs (immutable record), with v2 fields + day_type carried.
        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        assert len(sessions) == 1
        assert sessions[0]["log_version"] == "outdoor.v2"
        assert sessions[0]["day_type"] == "project"
        assert sessions[0]["route_profile"] == {"wall_angle": "overhang"}

        # Active session consumed.
        state = json.loads(self.state_path.read_text())
        assert state.get("outdoor_active_sessions", []) == []

    def test_finish_caps_stale_timer(self):
        sid = self.client.post("/api/outdoor/session/start", json={
            "date": "2026-06-19", "spot_name": "Arco", "discipline": "lead",
        }).json()["session_id"]
        self._rewind_started_at(sid, 25 * 60)  # 25h ago

        fin = self.client.post(f"/api/outdoor/session/{sid}/finish", json={
            "spot_name": "Arco", "discipline": "lead",
            "routes": [{"name": "X", "grade": "6a", "attempts": [{"result": "sent"}]}],
        }).json()
        assert fin["duration_minutes"] == OUTDOOR_SESSION_MAX_MINUTES
        assert fin["duration_capped"] is True
        assert fin["duration_raw_minutes"] == 25 * 60

    def test_finish_manual_override_beats_stale_timer(self):
        sid = self.client.post("/api/outdoor/session/start", json={
            "date": "2026-06-19", "spot_name": "Arco", "discipline": "lead",
        }).json()["session_id"]
        self._rewind_started_at(sid, 25 * 60)

        fin = self.client.post(f"/api/outdoor/session/{sid}/finish", json={
            "spot_name": "Arco", "discipline": "lead", "duration_minutes": 200,
            "routes": [{"name": "X", "grade": "6a", "attempts": [{"result": "sent"}]}],
        }).json()
        assert fin["duration_minutes"] == 200
        assert fin["duration_capped"] is False
        assert fin["duration_source"] == "manual"

    def test_finish_nonexistent_session_404(self):
        r = self.client.post("/api/outdoor/session/nope/finish", json={
            "spot_name": "Arco", "discipline": "lead",
            "routes": [{"name": "X", "grade": "6a", "attempts": [{"result": "sent"}]}],
        })
        assert r.status_code == 404

    def test_cancel_active_session(self):
        sid = self.client.post("/api/outdoor/session/start", json={
            "date": "2026-06-19", "spot_name": "Arco", "discipline": "lead",
        }).json()["session_id"]
        r = self.client.delete(f"/api/outdoor/session/{sid}")
        assert r.status_code == 200
        state = json.loads(self.state_path.read_text())
        assert state.get("outdoor_active_sessions", []) == []
        # And no log was written.
        assert self.client.get("/api/outdoor/sessions").json()["sessions"] == []

    def test_finished_session_is_immutable_record(self):
        """Once logged, the done session lives in outdoor_logs; re-finishing the
        consumed active id 404s (no double-write / no mutation)."""
        sid = self.client.post("/api/outdoor/session/start", json={
            "date": "2026-06-19", "spot_name": "Arco", "discipline": "lead",
        }).json()["session_id"]
        self.client.post(f"/api/outdoor/session/{sid}/finish", json={
            "spot_name": "Arco", "discipline": "lead",
            "routes": [{"name": "X", "grade": "6a", "attempts": [{"result": "sent"}]}],
        })
        again = self.client.post(f"/api/outdoor/session/{sid}/finish", json={
            "spot_name": "Arco", "discipline": "lead",
            "routes": [{"name": "Y", "grade": "7a", "attempts": [{"result": "sent"}]}],
        })
        assert again.status_code == 404
        # Still exactly one immutable log entry, unchanged.
        sessions = self.client.get("/api/outdoor/sessions").json()["sessions"]
        assert len(sessions) == 1
        assert [r["name"] for r in sessions[0]["routes"]] == ["X"]


# --------------------------------------------------------------------------- #
# Phase 3 — deterministic resolver
# --------------------------------------------------------------------------- #

class TestResolver:
    def test_day_type_alone_returns_complete_entry(self):
        out = resolve_strategy("lead", "project")
        for field in STRATEGY_BASE_FIELDS:
            assert field in out["base"], f"missing {field}"
            assert out["base"][field]
        assert out["modifiers"] == []
        assert out["applied_dimensions"] == []

    def test_override_replaces_base_field(self):
        """route_length=long_endurance overrides rest_between_attempts_min."""
        out = resolve_strategy("lead", "project", {"route_length": "long_endurance"})
        assert out["base"]["rest_between_attempts_min"] == "~1:4 work:rest."
        # and a strategy_add note is layered, not replacing a base field
        assert any(m["key"] == "strategy_add" for m in out["modifiers"])

    def test_phase_yields_nudge_modifier_only(self):
        out = resolve_strategy("lead", "project", {"macrocycle_phase": "performance"})
        nudges = [m for m in out["modifiers"] if m["key"] == "nudge"]
        assert len(nudges) == 1
        assert "Performance phase" in nudges[0]["text"]
        # nudge must NOT have touched any base field
        assert "nudge" not in out["base"]

    def test_unknown_dimension_value_skipped_gracefully(self):
        out = resolve_strategy("lead", "volume", {"wall_angle": "cave"})
        assert "wall_angle=cave" in out["skipped_dimensions"]
        # base still complete
        assert out["base"]["warmup_protocol"]

    def test_missing_dimensions_skipped(self):
        out = resolve_strategy("lead", "scout_easy", {"wall_angle": None, "hold_style": None})
        assert out["applied_dimensions"] == []
        assert out["modifiers"] == []

    def test_unknown_day_type_raises(self):
        with pytest.raises(OutdoorResolveError):
            resolve_strategy("lead", "sending")

    def test_unknown_discipline_raises(self):
        with pytest.raises(OutdoorResolveError):
            resolve_strategy("boulder", "project")  # boulder not populated yet (C241)

    def test_resolver_does_not_mutate_catalog(self):
        """Resolving with an override must not leak into a later bare resolve."""
        resolve_strategy("lead", "project", {"route_length": "long_endurance"})
        clean = resolve_strategy("lead", "project")
        assert clean["base"]["rest_between_attempts_min"].startswith("20–45+ min")

    def test_nutrition_surfaces_day_type_nuance(self):
        assert resolve_nutrition("lead", "project")["day_type_nuance"] is not None
        assert resolve_nutrition("lead", "volume")["day_type_nuance"] is not None
        # scout_easy has no nuance entry → None (graceful)
        assert resolve_nutrition("lead", "scout_easy")["day_type_nuance"] is None

    def test_combined_resolve_outdoor_day(self):
        out = resolve_outdoor_day("lead", "project", {"wall_angle": "overhang"})
        assert "strategy" in out and "nutrition" in out and "safety" in out
        assert out["safety"]["no_cold_full_crimp"]


class TestResolverEndpoint:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.engine import storage
        state_path = tmp_path / "user_state.json"
        state_path.write_text(json.dumps({"schema_version": "1.5", "outdoor_spots": []}))
        monkeypatch.setattr(storage, "STATE_PATH", state_path)
        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        monkeypatch.setattr(deps, "STATE_PATH", state_path)
        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def test_endpoint_day_type_only(self):
        r = self.client.get("/api/outdoor/strategy", params={"day_type": "volume"})
        assert r.status_code == 200
        body = r.json()
        assert body["strategy"]["base"]["target_burns"]
        assert body["nutrition"]["pre_day"]
        assert body["safety"]

    def test_endpoint_with_dimensions(self):
        r = self.client.get("/api/outdoor/strategy", params={
            "day_type": "project", "wall_angle": "overhang",
            "route_length": "long_endurance", "macrocycle_phase": "performance",
        })
        assert r.status_code == 200
        strat = r.json()["strategy"]
        assert strat["base"]["rest_between_attempts_min"] == "~1:4 work:rest."
        assert "wall_angle=overhang" in strat["applied_dimensions"]

    def test_endpoint_bad_day_type_422(self):
        r = self.client.get("/api/outdoor/strategy", params={"day_type": "nope"})
        assert r.status_code == 422
