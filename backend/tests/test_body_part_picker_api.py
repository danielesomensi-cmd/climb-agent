"""A213 — Body Part Picker API integration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def _reset():
    client.delete("/api/state")


def _seed_week_plan(start_date: str = "2026-04-20"):
    """Seed a minimal week plan starting on the given Monday."""
    dates = [f"2026-04-{20 + i:02d}" for i in range(7)]
    weekdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    week_plan = {
        "start_date": start_date,
        "weeks": [{
            "days": [
                {"date": dates[i], "weekday": weekdays[i], "sessions": []}
                for i in range(7)
            ],
        }],
    }
    client.put("/api/state", json={"current_week_plan": week_plan})
    return week_plan


# ── /options ──────────────────────────────────────────────────────────────


class TestOptions:
    def setup_method(self):
        _reset()

    def test_options_shape(self):
        r = client.get("/api/body-part-picker/options")
        assert r.status_code == 200
        data = r.json()
        assert "body_parts" in data
        assert "equipment_options" in data
        assert len(data["body_parts"]) == 11
        # Always-present modes
        modes = [o["mode"] for o in data["equipment_options"]]
        assert "bodyweight" in modes
        assert "all" in modes

    def test_options_includes_home_when_configured(self):
        client.put("/api/state", json={
            "equipment": {"home": ["dumbbell", "pullup_bar"], "gyms": []},
        })
        r = client.get("/api/body-part-picker/options")
        modes = [o["mode"] for o in r.json()["equipment_options"]]
        assert "home" in modes

    def test_options_includes_gym_when_configured(self):
        client.put("/api/state", json={
            "equipment": {
                "home": [],
                "gyms": [{
                    "gym_id": "g1",
                    "name": "CoreClimb",
                    "equipment": ["gym_boulder", "hangboard"],
                }],
            },
        })
        r = client.get("/api/body-part-picker/options")
        gyms = [o for o in r.json()["equipment_options"] if o["mode"] == "gym"]
        assert len(gyms) == 1
        assert gyms[0]["gym_id"] == "g1"
        assert "CoreClimb" in gyms[0]["label"]


# ── /estimate ─────────────────────────────────────────────────────────────


class TestEstimate:
    def test_estimate_basic(self):
        r = client.get("/api/body-part-picker/estimate?body_parts=core,legs")
        assert r.status_code == 200
        assert r.json()["estimated_duration_min"] > 0

    def test_estimate_cooldown_toggle(self):
        r_with = client.get("/api/body-part-picker/estimate?body_parts=core&include_cooldown=true")
        r_without = client.get("/api/body-part-picker/estimate?body_parts=core&include_cooldown=false")
        assert r_with.json()["estimated_duration_min"] > r_without.json()["estimated_duration_min"]

    def test_estimate_unknown_body_part_422(self):
        r = client.get("/api/body-part-picker/estimate?body_parts=nonexistent")
        assert r.status_code == 422


# ── /preview ──────────────────────────────────────────────────────────────


class TestPreview:
    def setup_method(self):
        _reset()

    def test_preview_success(self):
        r = client.post("/api/body-part-picker/preview", json={
            "body_parts": ["core", "legs"],
            "equipment_mode": "bodyweight",
            "seed": 42,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["session_mode"] == "custom_build"
        assert data["build_kind"] == "body_parts"
        assert data["is_custom"] is True
        assert len(data["exercises"]) > 0
        body_parts = {e["body_part"] for e in data["exercises"]}
        assert body_parts == {"core", "legs"}

    def test_preview_deterministic(self):
        payload = {
            "body_parts": ["core"],
            "equipment_mode": "bodyweight",
            "seed": 7,
        }
        r1 = client.post("/api/body-part-picker/preview", json=payload)
        r2 = client.post("/api/body-part-picker/preview", json=payload)
        ids1 = [e["exercise_id"] for e in r1.json()["exercises"]]
        ids2 = [e["exercise_id"] for e in r2.json()["exercises"]]
        assert ids1 == ids2

    def test_preview_empty_body_parts_422(self):
        r = client.post("/api/body-part-picker/preview", json={
            "body_parts": [],
            "equipment_mode": "bodyweight",
        })
        assert r.status_code == 422

    def test_preview_unknown_body_part_422(self):
        r = client.post("/api/body-part-picker/preview", json={
            "body_parts": ["nonexistent"],
            "equipment_mode": "bodyweight",
        })
        assert r.status_code == 422

    def test_preview_include_cooldown_default_true(self):
        r = client.post("/api/body-part-picker/preview", json={
            "body_parts": ["core"],
            "equipment_mode": "bodyweight",
            "seed": 1,
        })
        assert r.json()["include_cooldown"] is True


# ── /start ────────────────────────────────────────────────────────────────


class TestStart:
    def setup_method(self):
        _reset()

    def test_start_inserts_into_week_plan(self):
        _seed_week_plan("2026-04-20")
        r = client.post("/api/body-part-picker/start", json={
            "body_parts": ["core"],
            "equipment_mode": "bodyweight",
            "target_date": "2026-04-22",
            "slot": "evening",
            "location": "home",
            "seed": 1,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["session"] is not None
        assert data["session"]["build_kind"] == "body_parts"
        assert data["session"]["is_custom"] is True
        # Verify week_plan contains the new session
        wed = data["week_plan"]["weeks"][0]["days"][2]
        assert wed["date"] == "2026-04-22"
        assert any(s.get("build_kind") == "body_parts" for s in wed["sessions"])

    def test_start_without_week_plan_422(self):
        # No current_week_plan seeded
        r = client.post("/api/body-part-picker/start", json={
            "body_parts": ["core"],
            "equipment_mode": "bodyweight",
            "target_date": "2026-04-22",
            "slot": "evening",
            "seed": 1,
        })
        assert r.status_code == 422
        assert "week plan" in r.json()["detail"].lower()

    def test_start_invalid_target_date_422(self):
        _seed_week_plan("2026-04-20")
        r = client.post("/api/body-part-picker/start", json={
            "body_parts": ["core"],
            "equipment_mode": "bodyweight",
            "target_date": "not-a-date",
            "slot": "evening",
            "seed": 1,
        })
        assert r.status_code == 422

    def test_start_persists_state(self):
        _seed_week_plan("2026-04-20")
        client.post("/api/body-part-picker/start", json={
            "body_parts": ["core"],
            "equipment_mode": "bodyweight",
            "target_date": "2026-04-22",
            "slot": "evening",
            "seed": 1,
        })
        # Re-read state and confirm session persisted
        state = client.get("/api/state").json()
        plan = state["current_week_plan"]
        wed = plan["weeks"][0]["days"][2]
        assert any(s.get("build_kind") == "body_parts" for s in wed["sessions"])
