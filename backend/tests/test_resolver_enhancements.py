"""Tests for B28 recency, NEW-F8 deload climbing, NEW-F9 PE finger maintenance."""

from __future__ import annotations

import os
import json
from typing import Any, Dict, List

import pytest

from backend.engine.resolve_session import (
    pick_best_exercise_p0,
    score_exercise,
)
from backend.engine.planner_v2 import generate_phase_week, _SESSION_META
from backend.engine.macrocycle_v1 import _build_session_pool, DELOAD_SESSION_POOL


# ── B28: Cross-session recency ──────────────────────────────────────────

class TestCrossSessionRecency:
    """Test that score_exercise-based tie-breaking varies exercise selection."""

    @pytest.fixture
    def exercises(self):
        """Three exercises matching the same role/domain, different ids."""
        return [
            {
                "exercise_id": "alpha_ex",
                "name": "Alpha",
                "role": ["cooldown"],
                "domain": ["flexibility"],
                "location_allowed": ["home", "gym"],
                "equipment_required": [],
            },
            {
                "exercise_id": "beta_ex",
                "name": "Beta",
                "role": ["cooldown"],
                "domain": ["flexibility"],
                "location_allowed": ["home", "gym"],
                "equipment_required": [],
            },
            {
                "exercise_id": "gamma_ex",
                "name": "Gamma",
                "role": ["cooldown"],
                "domain": ["flexibility"],
                "location_allowed": ["home", "gym"],
                "equipment_required": [],
            },
        ]

    def test_empty_history_alphabetic_fallback(self, exercises):
        """With no recent history, selection is alphabetic (alpha first)."""
        ex, _ = pick_best_exercise_p0(
            exercises=exercises,
            location="home",
            available_equipment=[],
            role_req="cooldown",
            domain_req="flexibility",
            recent_ex_ids=[],
        )
        assert ex["exercise_id"] == "alpha_ex"

    def test_recency_penalizes_recent(self, exercises):
        """Recently used exercise gets penalized, different one selected."""
        ex, _ = pick_best_exercise_p0(
            exercises=exercises,
            location="home",
            available_equipment=[],
            role_req="cooldown",
            domain_req="flexibility",
            recent_ex_ids=["alpha_ex"],  # alpha was recent
        )
        # alpha_ex is in exclude_ids AND has recency penalty
        # With exclude_ids, alpha gets filtered. beta should be next.
        assert ex["exercise_id"] == "beta_ex"

    def test_heavy_recency_shifts_selection(self, exercises):
        """Heavy recency on both alpha and beta → gamma selected."""
        # alpha and beta both in last 5 → heavy penalty (-100)
        recent = ["alpha_ex", "beta_ex"]
        ex, _ = pick_best_exercise_p0(
            exercises=exercises,
            location="home",
            available_equipment=[],
            role_req="cooldown",
            domain_req="flexibility",
            recent_ex_ids=recent,
        )
        # exclude_ids filters alpha and beta, gamma is the only remaining
        assert ex["exercise_id"] == "gamma_ex"

    def test_determinism_same_history_same_result(self, exercises):
        """Same history always produces same selection."""
        recent = ["alpha_ex"]
        results = set()
        for _ in range(10):
            ex, _ = pick_best_exercise_p0(
                exercises=exercises,
                location="home",
                available_equipment=[],
                role_req="cooldown",
                domain_req="flexibility",
                recent_ex_ids=recent,
            )
            results.add(ex["exercise_id"])
        assert len(results) == 1  # Always the same


class TestScoreExercise:
    def test_no_recency_base_score(self):
        ex = {"exercise_id": "test_ex"}
        base = score_exercise(ex, {}, [])
        # Base score with empty prefs (no recency penalty)
        assert base >= 0.0

    def test_recent_heavy_penalty(self):
        ex = {"exercise_id": "test_ex"}
        base = score_exercise(ex, {}, [])
        penalized = score_exercise(ex, {}, ["test_ex"])
        # Heavy penalty: -100 from base
        assert penalized == base - 100.0

    def test_recent_medium_penalty(self):
        ex = {"exercise_id": "test_ex"}
        base = score_exercise(ex, {}, [])
        # In last 15 but not last 5: test_ex early, then 10 others
        recent = ["test_ex"] + ["other"] * 10
        penalized = score_exercise(ex, {}, recent)
        assert penalized == base - 25.0


# ── NEW-F8: Easy climbing in deload pool ────────────────────────────────

class TestDeloadEasyClimbing:
    def test_deload_pool_contains_easy_climbing(self):
        pool = _build_session_pool("deload")
        assert "easy_climbing_deload" in pool

    def test_deload_session_pool_constant(self):
        assert "easy_climbing_deload" in DELOAD_SESSION_POOL

    def test_easy_climbing_deload_meta(self):
        meta = _SESSION_META.get("easy_climbing_deload")
        assert meta is not None
        assert meta["hard"] is False
        assert meta["finger"] is False
        assert meta["intensity"] == "low"
        assert meta["climbing"] is True

    def test_easy_climbing_deload_session_file_exists(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(repo_root, "backend", "catalog", "sessions", "v1", "easy_climbing_deload.json")
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["id"] == "easy_climbing_deload"
        assert data["intensity"] == "low"


# ── NEW-F9: Finger maintenance in PE phase ──────────────────────────────

class TestPEFingerMaintenance:
    def _generate_pe_week(self, **kwargs):
        defaults = {
            "phase_id": "power_endurance",
            "domain_weights": {"power_endurance": 0.35, "finger_strength": 0.15},
            "session_pool": [
                "power_endurance_gym",
                "prehab_maintenance",
                "technique_focus_gym",
                "flexibility_full",
                "endurance_aerobic_gym",
                "finger_maintenance_home",
            ],
            "start_date": "2026-03-16",
            "availability": {
                "mon": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
                "tue": {"evening": {"available": True, "locations": ["home"], "preferred_location": "home"}},
                "wed": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
                "thu": {"evening": {"available": True, "locations": ["home"], "preferred_location": "home"}},
                "fri": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
            },
            "allowed_locations": ["gym", "home"],
            "planning_prefs": {"target_training_days_per_week": 5},
        }
        defaults.update(kwargs)
        return generate_phase_week(**defaults)

    def test_pe_week_has_finger_maintenance(self):
        """PE phase week should contain at least 1 finger maintenance session."""
        plan = self._generate_pe_week()
        days = plan["weeks"][0]["days"]
        all_sids = [
            s["session_id"]
            for d in days
            for s in d["sessions"]
        ]
        has_finger = any(sid.startswith("finger_maintenance") for sid in all_sids)
        assert has_finger, f"No finger_maintenance in PE week: {all_sids}"

    def test_non_pe_week_unaffected(self):
        """Non-PE phases should not have the forced finger maintenance injection."""
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"finger_strength": 0.2, "volume_climbing": 0.25},
            session_pool=["endurance_aerobic_gym", "technique_focus_gym", "prehab_maintenance", "flexibility_full"],
            start_date="2026-03-16",
            availability={
                "mon": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
                "wed": {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym"}},
                "fri": {"evening": {"available": True, "locations": ["home"], "preferred_location": "home"}},
            },
            allowed_locations=["gym", "home"],
            planning_prefs={"target_training_days_per_week": 3},
        )
        days = plan["weeks"][0]["days"]
        all_sids = [
            s["session_id"] for d in days for s in d["sessions"]
        ]
        # Base phase may or may not have finger maintenance — the point is pass2.5 doesn't inject it
        # We just verify no "pass2.5" in explain tags
        all_explains = [
            tag
            for d in days for s in d["sessions"]
            for tag in s.get("explain", [])
        ]
        assert not any("pass2.5" in tag for tag in all_explains)

    def test_finger_48h_gap_respected(self):
        """Injected finger maintenance should respect 48h gap."""
        plan = self._generate_pe_week()
        days = plan["weeks"][0]["days"]
        finger_offsets = []
        for i, d in enumerate(days):
            for s in d["sessions"]:
                meta = _SESSION_META.get(s["session_id"], {})
                if meta.get("finger"):
                    finger_offsets.append(i)

        # Check no consecutive finger days
        for i in range(len(finger_offsets) - 1):
            assert finger_offsets[i + 1] - finger_offsets[i] > 1, \
                f"Finger sessions too close: offsets {finger_offsets}"
