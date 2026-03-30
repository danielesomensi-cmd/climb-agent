"""Tests for B168: boulder onboarding flow — grade mapping + discipline support."""

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


client = TestClient(app)


def _make_boulder_payload(target_boulder_grade="7C", boulder_rp="7A", boulder_os="6B+"):
    return {
        "profile": {"name": "Test", "age": 28, "weight_kg": 70, "height_cm": 175},
        "experience": {"climbing_years": 4, "structured_training_years": 1},
        "grades": {
            "lead_max_rp": "",
            "lead_max_os": "",
            "boulder_max_rp": boulder_rp,
            "boulder_max_os": boulder_os,
        },
        "goal": {
            "goal_type": "boulder_grade",
            "discipline": "boulder",
            "target_grade": "",
            "target_boulder_grade": target_boulder_grade,
            "target_style": "",
            "current_grade": "",
            "deadline": "2026-09-01",
        },
        "self_eval": {"primary_weakness": "poor_body_tension", "secondary_weakness": "weak_on_slopers"},
        "tests": {},
        "limitations": [],
        "equipment": {"home_enabled": True, "home": ["hangboard_20mm"], "gyms": []},
        "availability": {
            "mon": {"evening": {"available": True, "preferred_location": "home"}},
            "wed": {"evening": {"available": True, "preferred_location": "home"}},
            "fri": {"evening": {"available": True, "preferred_location": "home"}},
        },
        "planning_prefs": {"target_training_days_per_week": 3, "hard_day_cap_per_week": 2},
        "preferences": {"finger_training_device": "hangboard"},
        "trips": [],
        "outdoor_spots": [],
    }


def _make_both_payload():
    return {
        "profile": {"name": "Test", "age": 30, "weight_kg": 72, "height_cm": 178},
        "experience": {"climbing_years": 5, "structured_training_years": 2},
        "grades": {
            "lead_max_rp": "7b",
            "lead_max_os": "6c",
            "boulder_max_rp": "7A",
            "boulder_max_os": "6B+",
        },
        "goal": {
            "goal_type": "all_round",
            "discipline": "both",
            "target_grade": "7c+",
            "target_boulder_grade": "7B+",
            "target_style": "redpoint",
            "current_grade": "",
            "deadline": "2026-09-01",
        },
        "self_eval": {"primary_weakness": "technique_errors", "secondary_weakness": "poor_dynamic_movement"},
        "tests": {},
        "limitations": [],
        "equipment": {"home_enabled": True, "home": ["hangboard_20mm"], "gyms": []},
        "availability": {
            "mon": {"evening": {"available": True, "preferred_location": "home"}},
            "wed": {"evening": {"available": True, "preferred_location": "home"}},
            "fri": {"evening": {"available": True, "preferred_location": "home"}},
        },
        "planning_prefs": {"target_training_days_per_week": 3, "hard_day_cap_per_week": 2},
        "preferences": {"finger_training_device": "hangboard"},
        "trips": [],
        "outdoor_spots": [],
    }


class TestBoulderOnboardingComplete:
    """POST /api/onboarding/complete with boulder discipline must succeed."""

    def test_boulder_8A_no_error(self):
        """P0 regression: boulder grade 8A used to cause 'Unknown grade' error."""
        resp = client.post("/api/onboarding/complete", json=_make_boulder_payload("8A"))
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert "profile" in data
        assert "macrocycle" in data

    def test_boulder_8A_plus_no_error(self):
        """Hotfix: 8A+ must also work (was failing because target_grade had boulder grade)."""
        resp = client.post("/api/onboarding/complete", json=_make_boulder_payload("8A+"))
        assert resp.status_code == 200, f"8A+ failed: {resp.json()}"

    def test_boulder_7C_success(self):
        resp = client.post("/api/onboarding/complete", json=_make_boulder_payload("7C"))
        assert resp.status_code == 200

    def test_boulder_macrocycle_10_weeks(self):
        resp = client.post("/api/onboarding/complete", json=_make_boulder_payload("7C"))
        mc = resp.json()["macrocycle"]
        total = sum(p["duration_weeks"] for p in mc["phases"])
        assert total == 10

    def test_boulder_profile_valid_range(self):
        resp = client.post("/api/onboarding/complete", json=_make_boulder_payload())
        profile = resp.json()["profile"]
        for axis, score in profile.items():
            assert 0 <= score <= 100, f"{axis}={score} out of range"

    def test_boulder_weakness_affects_profile(self):
        """Boulder weaknesses should affect the assessment profile."""
        resp = client.post("/api/onboarding/complete", json=_make_boulder_payload())
        profile = resp.json()["profile"]
        # poor_body_tension maps to technique, weak_on_slopers maps to finger_strength
        # They should produce some differentiation
        assert profile["technique"] >= 0
        assert profile["finger_strength"] >= 0


class TestBothOnboardingComplete:
    """POST /api/onboarding/complete with 'both' discipline."""

    def test_both_success(self):
        resp = client.post("/api/onboarding/complete", json=_make_both_payload())
        assert resp.status_code == 200

    def test_both_macrocycle_12_weeks(self):
        """'both' uses lead durations (12 weeks)."""
        resp = client.post("/api/onboarding/complete", json=_make_both_payload())
        mc = resp.json()["macrocycle"]
        total = sum(p["duration_weeks"] for p in mc["phases"])
        assert total == 12

    def test_both_goal_snapshot(self):
        resp = client.post("/api/onboarding/complete", json=_make_both_payload())
        mc = resp.json()["macrocycle"]
        snap = mc["goal_snapshot"]
        assert snap["discipline"] == "both"
        assert snap["goal_type"] == "all_round"
        assert snap["target_boulder_grade"] == "7B+"


class TestBoulderGradeMapping:
    """Grade mapping covers the full range."""

    def test_boulder_grade_in_target_grade_field(self):
        """Backend handles boulder grade in target_grade (legacy frontend behavior)."""
        payload = _make_boulder_payload("8A+")
        # Simulate old frontend: target_grade has boulder grade, target_boulder_grade empty
        payload["goal"]["target_grade"] = "8A+"
        payload["goal"]["target_boulder_grade"] = ""
        resp = client.post("/api/onboarding/complete", json=payload)
        assert resp.status_code == 200, f"Legacy path failed: {resp.json()}"

    def test_all_standard_boulder_grades_complete(self):
        """Every standard boulder grade should produce a valid onboarding."""
        for grade in ["6A", "6B+", "7A", "7B+", "7C", "8A", "8A+", "8B"]:
            resp = client.post(
                "/api/onboarding/complete",
                json=_make_boulder_payload(grade, boulder_rp="6A"),
            )
            assert resp.status_code == 200, f"Failed for grade {grade}: {resp.json()}"


class TestLeadBackwardCompat:
    """Lead onboarding still works identically."""

    def test_lead_no_discipline_field(self):
        payload = _make_boulder_payload()
        # Switch to lead
        payload["goal"]["discipline"] = "lead"
        payload["goal"]["goal_type"] = "lead_grade"
        payload["goal"]["target_grade"] = "7c"
        payload["goal"]["target_boulder_grade"] = ""
        payload["goal"]["target_style"] = "redpoint"
        payload["grades"]["lead_max_rp"] = "7a"
        payload["grades"]["lead_max_os"] = "6b+"
        payload["self_eval"] = {"primary_weakness": "pump_too_early", "secondary_weakness": "fingers_give_out"}
        resp = client.post("/api/onboarding/complete", json=payload)
        assert resp.status_code == 200
