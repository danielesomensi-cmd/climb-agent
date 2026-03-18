"""Tests for B121 — baselines.pulling: weighted pullup 1RM → resolver load prescription."""

from __future__ import annotations

from copy import deepcopy

from backend.engine.progression_v1 import (
    PULLING_1RM_PCT,
    PULLING_EXTERNAL_SCALING,
    apply_feedback,
    estimate_missing_baselines,
    inject_targets,
)


def _user_state_with_pullup_1rm(
    bodyweight: float = 77.0,
    pullup_1rm_total: float = 130.0,
) -> dict:
    """User with weighted_pullup 1RM in assessment tests, no working_loads."""
    return {
        "schema_version": "1.5",
        "bodyweight_kg": bodyweight,
        "assessment": {
            "tests": {"weighted_pullup_1rm_total_kg": pullup_1rm_total},
            "grades": {"lead_max_rp": "8a+"},
        },
        "baselines": {},
        "working_loads": {"entries": [], "rules": {}},
        "macrocycle": {
            "start_date": "2026-01-05",
            "phases": [
                {"phase_id": "base", "duration_weeks": 3},
                {"phase_id": "strength_power", "duration_weeks": 3},
                {"phase_id": "power_endurance", "duration_weeks": 3},
                {"phase_id": "performance", "duration_weeks": 2},
                {"phase_id": "deload", "duration_weeks": 1},
            ],
        },
        "equipment": {"home": ["pullup_bar"], "gyms": []},
        "performance": {"current_level": {}},
    }


def _resolved_day_with_weighted_pullup(date: str = "2026-01-05", intent: str = "strength") -> dict:
    return {
        "date": date,
        "sessions": [
            {
                "session_id": "pulling_strength_gym",
                "intent": intent,
                "location": "gym",
                "tags": {},
                "exercise_instances": [
                    {
                        "exercise_id": "weighted_pullup",
                        "prescription": {"sets": 4, "reps": 5},
                    },
                ],
            }
        ],
    }


def _resolved_day_with_external_load(date: str = "2026-01-05") -> dict:
    return {
        "date": date,
        "sessions": [
            {
                "session_id": "pulling_strength_gym",
                "intent": "strength",
                "location": "gym",
                "tags": {},
                "exercise_instances": [
                    {
                        "exercise_id": "barbell_row",
                        "prescription": {"sets": 3, "reps": 8},
                    },
                    {
                        "exercise_id": "face_pull",
                        "prescription": {"sets": 3, "reps": 12},
                    },
                ],
            }
        ],
    }


# ── Phase 1: baselines.pulling creation ──


class TestPullingBaselineCreation:
    """Unit: baselines.pulling creation from assessment test results."""

    def test_pulling_baseline_created_from_1rm(self):
        """Onboarding with pullup 1RM → baselines.pulling is populated."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=130.0)
        estimate_missing_baselines(state)

        pulling = state["baselines"]["pulling"]
        assert pulling["weighted_pullup_1rm_total_kg"] == 130.0
        assert pulling["bodyweight_kg"] == 77.0
        assert pulling["max_external_load_kg"] == 53.0
        assert pulling["source"] == "assessment"
        assert "updated_at" in pulling

    def test_pulling_baseline_not_created_without_1rm(self):
        """Onboarding without pullup 1RM → baselines.pulling not created."""
        state = _user_state_with_pullup_1rm()
        state["assessment"]["tests"] = {}
        estimate_missing_baselines(state)

        assert "pulling" not in state.get("baselines", {})

    def test_pulling_baseline_preserves_test_source(self):
        """Never overwrite a baselines.pulling with source == 'test'."""
        state = _user_state_with_pullup_1rm(pullup_1rm_total=130.0)
        state["baselines"]["pulling"] = {
            "weighted_pullup_1rm_total_kg": 120.0,
            "bodyweight_kg": 77.0,
            "max_external_load_kg": 43.0,
            "source": "test",
            "updated_at": "2026-01-01",
        }
        estimate_missing_baselines(state)

        assert state["baselines"]["pulling"]["weighted_pullup_1rm_total_kg"] == 120.0

    def test_pulling_baseline_preserves_test_session_source(self):
        """Never overwrite source == 'test_session'."""
        state = _user_state_with_pullup_1rm(pullup_1rm_total=130.0)
        state["baselines"]["pulling"] = {
            "weighted_pullup_1rm_total_kg": 125.0,
            "bodyweight_kg": 77.0,
            "max_external_load_kg": 48.0,
            "source": "test_session",
            "updated_at": "2026-01-01",
        }
        estimate_missing_baselines(state)

        assert state["baselines"]["pulling"]["weighted_pullup_1rm_total_kg"] == 125.0

    def test_hangboard_baseline_still_estimated(self):
        """Hangboard estimation is not affected by pulling baseline changes."""
        state = _user_state_with_pullup_1rm()
        estimate_missing_baselines(state)

        assert "hangboard" in state["baselines"]
        assert state["baselines"]["hangboard"][0]["max_total_load_kg"] > 0

    def test_key_mismatch_fix_hangboard_from_pullup(self):
        """B121 key fix: hangboard Priority 2 uses weighted_pullup_1rm_total_kg (not max_weighted_pullup_kg)."""
        state = {
            "bodyweight_kg": 77.0,
            "assessment": {
                "tests": {"weighted_pullup_1rm_total_kg": 130.0},
                "grades": {},  # no grade → forces Priority 2
            },
            "baselines": {},
        }
        estimate_missing_baselines(state)

        hb = state["baselines"].get("hangboard", [])
        assert len(hb) == 1
        # 130 * 0.85 = 110.5
        assert hb[0]["max_total_load_kg"] == 110.5
        assert hb[0]["source"] == "estimated_from_pullup"


# ── Phase 2: resolver total_load with pulling baseline ──


class TestWeightedPullupWithBaseline:
    """Unit: resolver total_load exercises use baselines.pulling."""

    def test_baseline_used_when_no_working_loads(self):
        """weighted_pullup gets load from baselines.pulling when no working_loads entry."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=130.0)
        # Date in strength_power phase (week 4-6): 2026-01-26
        day = _resolved_day_with_weighted_pullup(date="2026-01-26", intent="strength")
        result = inject_targets(day, state)

        wp = result["sessions"][0]["exercise_instances"][0]
        sug = wp["suggested"]

        # strength_power + "hard" intensity → 82.5% of 130 = 107.25 → 107.0
        # external = 107.0 - 77 = 30.0
        assert sug["suggested_total_load_kg"] > 77.0, "Should be more than bodyweight"
        assert sug["suggested_external_load_kg"] > 0, "Should have added weight"
        assert sug["load_source"] == "baselines.pulling"

    def test_phase_aware_load_base_vs_strength_power(self):
        """Load is lower in base phase than in strength_power."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=130.0)

        day_base = _resolved_day_with_weighted_pullup(date="2026-01-05", intent="strength")
        day_sp = _resolved_day_with_weighted_pullup(date="2026-01-26", intent="strength")

        result_base = inject_targets(day_base, state)
        result_sp = inject_targets(day_sp, state)

        load_base = result_base["sessions"][0]["exercise_instances"][0]["suggested"]["suggested_total_load_kg"]
        load_sp = result_sp["sessions"][0]["exercise_instances"][0]["suggested"]["suggested_total_load_kg"]

        assert load_sp > load_base, f"strength_power ({load_sp}) should be heavier than base ({load_base})"

    def test_deload_phase_near_bodyweight(self):
        """Deload phase: load should be low, possibly near bodyweight."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=130.0)
        # Week 12 = deload phase (weeks 12+)
        day = _resolved_day_with_weighted_pullup(date="2026-03-23", intent="strength")
        result = inject_targets(day, state)

        wp = result["sessions"][0]["exercise_instances"][0]
        total = wp["suggested"]["suggested_total_load_kg"]

        # deload + "hard" → 52.5% of 130 = 68.25 → external = max(0, 68.5-77) = 0
        # total = 77.0 (BW only is fine for deload)
        assert total <= 77.0, "Deload should be at or below bodyweight"

    def test_working_loads_override_baseline(self):
        """When working_loads entry exists, baseline is ignored."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=130.0)
        state["working_loads"]["entries"] = [
            {"exercise_id": "weighted_pullup", "next_external_load_kg": 15.0, "updated_at": "2026-01-04"}
        ]
        day = _resolved_day_with_weighted_pullup(date="2026-01-05", intent="strength")
        result = inject_targets(day, state)

        wp = result["sessions"][0]["exercise_instances"][0]
        assert wp["suggested"]["suggested_external_load_kg"] == 15.0
        assert "load_source" not in wp["suggested"]

    def test_no_baseline_no_1rm_bodyweight_fallback(self):
        """No 1RM provided → graceful fallback to bodyweight only (no regression)."""
        state = _user_state_with_pullup_1rm()
        state["assessment"]["tests"] = {}
        day = _resolved_day_with_weighted_pullup()
        result = inject_targets(day, state)

        wp = result["sessions"][0]["exercise_instances"][0]
        assert wp["suggested"]["suggested_external_load_kg"] == 0.0
        assert wp["suggested"]["suggested_total_load_kg"] == 77.0


# ── Phase 2b: resolver external_load with pulling anchor ──


class TestExternalLoadPullingAnchor:
    """Unit: external_load pulling exercises use baselines.pulling."""

    def test_barbell_row_uses_pulling_baseline(self):
        """barbell_row gets load from baselines.pulling × scaling when no working_loads."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=130.0)
        day = _resolved_day_with_external_load()
        result = inject_targets(day, state)

        row = next(i for i in result["sessions"][0]["exercise_instances"] if i["exercise_id"] == "barbell_row")
        # max_external = 53.0, scaling = 0.60 → 31.8 → 32.0
        assert row["suggested"]["suggested_external_load_kg"] == 32.0
        assert row["suggested"]["load_source"] == "baselines.pulling"

    def test_face_pull_uses_pulling_baseline(self):
        """face_pull gets load from baselines.pulling × scaling."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=130.0)
        day = _resolved_day_with_external_load()
        result = inject_targets(day, state)

        fp = next(i for i in result["sessions"][0]["exercise_instances"] if i["exercise_id"] == "face_pull")
        # max_external = 53.0, scaling = 0.15 → 7.95 → 8.0
        assert fp["suggested"]["suggested_external_load_kg"] == 8.0
        assert fp["suggested"]["load_source"] == "baselines.pulling"

    def test_external_load_no_baseline_bw_fallback(self):
        """Without baselines.pulling, BW% fallback still works."""
        state = _user_state_with_pullup_1rm()
        state["assessment"]["tests"] = {}
        day = _resolved_day_with_external_load()
        result = inject_targets(day, state)

        row = next(i for i in result["sessions"][0]["exercise_instances"] if i["exercise_id"] == "barbell_row")
        # BW% fallback: 77 × 0.30 = 23.1 → 23.0
        assert row["suggested"]["suggested_external_load_kg"] == 23.0
        assert "load_source" not in row["suggested"]

    def test_working_loads_override_pulling_baseline(self):
        """When working_loads exists for barbell_row, baseline is ignored."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=130.0)
        state["working_loads"]["entries"] = [
            {"exercise_id": "barbell_row", "next_external_load_kg": 40.0, "updated_at": "2026-01-04"}
        ]
        day = _resolved_day_with_external_load()
        result = inject_targets(day, state)

        row = next(i for i in result["sessions"][0]["exercise_instances"] if i["exercise_id"] == "barbell_row")
        assert row["suggested"]["suggested_external_load_kg"] == 40.0

    def test_non_pulling_external_load_unaffected(self):
        """bench_press (not in PULLING_EXTERNAL_SCALING) uses BW% fallback, not pulling baseline."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=130.0)
        day = {
            "date": "2026-01-05",
            "sessions": [{
                "session_id": "push_session",
                "intent": "strength",
                "location": "gym",
                "tags": {},
                "exercise_instances": [
                    {"exercise_id": "bench_press", "prescription": {"sets": 3, "reps": 8}},
                ],
            }],
        }
        result = inject_targets(day, state)

        bp = result["sessions"][0]["exercise_instances"][0]
        # BW% fallback: 77 × 0.40 = 30.8 → 31.0
        assert bp["suggested"]["suggested_external_load_kg"] == 31.0
        assert "load_source" not in bp["suggested"]


# ── Regression: hangboard unaffected ──


class TestHangboardUnaffected:
    """Regression: hangboard exercises still use baselines.hangboard, not pulling."""

    def test_max_hang_uses_hangboard_baseline(self):
        """max_hang_5s still uses baselines.hangboard."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=130.0)
        state["baselines"]["hangboard"] = [{"max_total_load_kg": 102.0}]
        day = {
            "date": "2026-01-05",
            "sessions": [{
                "session_id": "finger_strength_home",
                "intent": "strength",
                "location": "home",
                "tags": {},
                "exercise_instances": [
                    {
                        "exercise_id": "max_hang_5s",
                        "prescription": {"sets": 6, "work_seconds": 5, "edge_mm": 20, "grip": "half_crimp", "load_method": "added_weight"},
                        "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.9},
                    },
                ],
            }],
        }
        result = inject_targets(day, state)

        mh = result["sessions"][0]["exercise_instances"][0]
        # 102 × 0.9 = 91.8 → 92.0 total, external = 92.0 - 77 = 15.0
        assert mh["suggested"]["suggested_total_load_kg"] == 92.0
        assert mh["suggested"]["suggested_external_load_kg"] == 15.0


# ── Test feedback updates baselines.pulling ──


class TestFeedbackUpdatesPulling:
    """Test that weighted_pullup test feedback updates baselines.pulling."""

    def test_weighted_pullup_test_creates_pulling_baseline(self):
        """Weighted pullup 2RM test feedback → baselines.pulling with source='test_session' (D84)."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=120.0)

        log_entry = {
            "date": "2026-02-01",
            "session_id": "test_pulling",
            "planned": [{"session_id": "test_pulling", "tags": {"test": True}, "exercise_instances": []}],
            "actual": {
                "exercise_feedback_v1": [
                    {
                        "exercise_id": "weighted_pullup",
                        "used_total_load_kg": 135.0,
                        "feedback_label": "ok",
                    }
                ]
            },
        }
        updated = apply_feedback(log_entry, state)

        pulling = updated["baselines"]["pulling"]
        # D84: 2RM = 135.0 → estimated 1RM via Epley/Brzycki average
        from backend.engine.progression_v1 import estimate_1rm_from_2rm
        expected_1rm = estimate_1rm_from_2rm(135.0)
        assert pulling["weighted_pullup_2rm_total_kg"] == 135.0
        assert pulling["weighted_pullup_1rm_estimated_kg"] == expected_1rm
        assert pulling["weighted_pullup_1rm_total_kg"] == expected_1rm  # legacy compat
        assert pulling["bodyweight_kg"] == 77.0
        assert pulling["source"] == "test_session"
        assert pulling["updated_at"] == "2026-02-01"

    def test_weighted_pullup_test_from_external_load(self):
        """Feedback with used_external_load_kg (no total) → correct 2RM derivation (D84)."""
        state = _user_state_with_pullup_1rm(bodyweight=77.0, pullup_1rm_total=120.0)

        log_entry = {
            "date": "2026-02-01",
            "session_id": "test_pulling",
            "planned": [{"session_id": "test_pulling", "tags": {"test": True}, "exercise_instances": []}],
            "actual": {
                "exercise_feedback_v1": [
                    {
                        "exercise_id": "weighted_pullup",
                        "used_external_load_kg": 58.0,
                        "feedback_label": "ok",
                    }
                ]
            },
        }
        updated = apply_feedback(log_entry, state)

        pulling = updated["baselines"]["pulling"]
        # total 2RM = 77 + 58 = 135
        from backend.engine.progression_v1 import estimate_1rm_from_2rm
        expected_1rm = estimate_1rm_from_2rm(135.0)
        assert pulling["weighted_pullup_2rm_total_kg"] == 135.0
        assert pulling["weighted_pullup_1rm_total_kg"] == expected_1rm


# ── Similarity group "pull" ──


class TestPullSimilarityGroup:
    """Transfer loads between barbell_row and face_pull."""

    def test_face_pull_from_barbell_row_transfer(self):
        """When barbell_row has working_loads, face_pull can be estimated via transfer."""
        state = _user_state_with_pullup_1rm()
        state["assessment"]["tests"] = {}  # No pulling baseline
        state["working_loads"]["entries"] = [
            {"exercise_id": "barbell_row", "next_external_load_kg": 40.0, "updated_at": "2026-01-04"}
        ]
        day = _resolved_day_with_external_load()
        result = inject_targets(day, state)

        fp = next(i for i in result["sessions"][0]["exercise_instances"] if i["exercise_id"] == "face_pull")
        # Transfer: 40.0 × (0.25 / 1.0) = 10.0
        assert fp["suggested"]["suggested_external_load_kg"] == 10.0
        assert fp["suggested"]["load_source"] == "transferred"
