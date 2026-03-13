"""Tests for loading pin integration: resolver device preference, LP load suggestions,
LP feedback handling, LP test scheduling, and LP baselines.
"""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.engine.progression_v1 import (
    LOADING_PIN_EXERCISES,
    _loading_pin_suggested,
    _round_half_step,
    apply_feedback,
    inject_targets,
)
from backend.engine.resolve_session import (
    ensure_exercise_list,
    load_json,
    pick_best_exercise_p0,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXERCISES_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"
ALL_EXERCISES = ensure_exercise_list(load_json(str(EXERCISES_PATH)))

LP_EXERCISE_IDS = {e["id"] for e in ALL_EXERCISES if e["id"].startswith("lp_")}
HB_EXERCISE_IDS = {"max_hang_5s", "max_hang_7s", "max_hang_10s", "density_hangs"}


def _base_state(**overrides):
    state = {
        "bodyweight_kg": 77.0,
        "body": {"weight_kg": 77.0},
        "preferences": {"finger_training_device": "hangboard"},
        "baselines": {},
        "working_loads": {"entries": [], "rules": {}},
        "assessment": {"grades": {"lead_max_rp": "7a"}, "tests": {}},
        "equipment": {
            "home": ["hangboard", "pullup_bar"],
            "gyms": [{"gym_id": "g1", "name": "TestGym", "equipment": ["hangboard", "pullup_bar"]}],
        },
    }
    state.update(overrides)
    return state


def _lp_state(**overrides):
    """State for a loading_pin user."""
    state = _base_state()
    state["preferences"] = {"finger_training_device": "loading_pin"}
    state["equipment"] = {
        "home": ["loading_pin", "pullup_bar"],
        "gyms": [{"gym_id": "g1", "name": "TestGym", "equipment": ["loading_pin", "pullup_bar"]}],
    }
    state["baselines"] = {
        "loading_pin": [
            {"max_load_kg": 45.0, "hand": "right", "edge_mm": 20, "grip": "half_crimp", "lift_seconds": 5},
            {"max_load_kg": 40.0, "hand": "left", "edge_mm": 20, "grip": "half_crimp", "lift_seconds": 5},
        ]
    }
    state.update(overrides)
    return state


# ── Resolver: device preference filter ───────────────────────────────────────


class TestResolverDevicePreference:
    """When user has BOTH hangboard and loading_pin, finger_device selects correct exercises."""

    def _both_equipment(self):
        return ["hangboard", "loading_pin", "pullup_bar"]

    def test_finger_device_hangboard_prefers_hangboard(self):
        """With finger_device=hangboard, prefer hangboard exercises over lp_*."""
        selected, _ = pick_best_exercise_p0(
            exercises=ALL_EXERCISES,
            location="home",
            available_equipment=self._both_equipment(),
            role_req=["main"],
            domain_req=["finger_max_strength"],
            finger_device="hangboard",
        )
        assert selected is not None
        assert selected["id"] not in LP_EXERCISE_IDS

    def test_finger_device_loading_pin_prefers_lp(self):
        """With finger_device=loading_pin, prefer lp_* exercises over hangboard."""
        selected, _ = pick_best_exercise_p0(
            exercises=ALL_EXERCISES,
            location="home",
            available_equipment=self._both_equipment(),
            role_req=["main"],
            domain_req=["finger_max_strength"],
            finger_device="loading_pin",
        )
        assert selected is not None
        assert selected["id"] in LP_EXERCISE_IDS

    def test_no_finger_device_falls_back_to_equipment(self):
        """Without finger_device, equipment filter alone decides."""
        selected, _ = pick_best_exercise_p0(
            exercises=ALL_EXERCISES,
            location="home",
            available_equipment=["loading_pin", "pullup_bar"],
            role_req=["main"],
            domain_req=["finger_max_strength"],
            finger_device=None,
        )
        assert selected is not None
        # Only loading_pin in equipment → must pick LP exercise
        assert selected["id"] in LP_EXERCISE_IDS

    def test_hangboard_only_equipment_picks_hangboard(self):
        """When user only has hangboard, device filter doesn't matter."""
        selected, _ = pick_best_exercise_p0(
            exercises=ALL_EXERCISES,
            location="home",
            available_equipment=["hangboard", "pullup_bar"],
            role_req=["main"],
            domain_req=["finger_max_strength"],
            finger_device="hangboard",
        )
        assert selected is not None
        assert selected["id"] not in LP_EXERCISE_IDS

    def test_lp_test_exercise_selected_for_test_role(self):
        """lp_max_test_5s should be selectable with role=test and device=loading_pin."""
        selected, _ = pick_best_exercise_p0(
            exercises=ALL_EXERCISES,
            location="home",
            available_equipment=["loading_pin"],
            role_req=["test"],
            domain_req=["finger_max_strength"],
            finger_device="loading_pin",
        )
        assert selected is not None
        assert selected["id"] == "lp_max_test_5s"


# ── LP load suggestions ─────────────────────────────────────────────────────


class TestLPLoadSuggestion:
    """_loading_pin_suggested computes per-hand loads from baselines."""

    def test_basic_suggestion(self):
        state = _lp_state()
        result = _loading_pin_suggested(state, "lp_max_lift_5s", {"sets": 5, "work_seconds": 5})
        assert "right_hand" in result
        assert "left_hand" in result
        # 45 * 0.92 = 41.4 → rounded to 41.5
        assert result["right_hand"]["suggested_external_load_kg"] == _round_half_step(45.0 * 0.92)
        # 40 * 0.92 = 36.8 → rounded to 37.0
        assert result["left_hand"]["suggested_external_load_kg"] == _round_half_step(40.0 * 0.92)

    def test_fallback_from_hangboard_baseline(self):
        """When no LP baselines exist, estimate from hangboard via conversion."""
        state = _base_state()
        state["baselines"] = {"hangboard": [{"max_total_load_kg": 100.0}]}
        result = _loading_pin_suggested(state, "lp_max_lift_5s", {"sets": 5, "work_seconds": 5})
        # HB 100 → LP per hand = (100/2)*0.90 = 45.0 → × 0.92 = 41.4 → 41.5
        assert result["right_hand"]["suggested_external_load_kg"] == _round_half_step(45.0 * 0.92)
        assert result["left_hand"]["suggested_external_load_kg"] == _round_half_step(45.0 * 0.92)

    def test_no_baselines_returns_zero(self):
        """When no baselines at all, loads should be 0."""
        state = _base_state()
        state["baselines"] = {}
        result = _loading_pin_suggested(state, "lp_max_lift_5s", {"sets": 5, "work_seconds": 5})
        assert result["right_hand"]["suggested_external_load_kg"] == 0.0
        assert result["left_hand"]["suggested_external_load_kg"] == 0.0

    def test_density_lifts_intensity(self):
        """lp_density_lifts should use 0.75 intensity."""
        state = _lp_state()
        result = _loading_pin_suggested(state, "lp_density_lifts", {"sets": 3, "work_seconds": 30})
        assert result["right_hand"]["suggested_external_load_kg"] == _round_half_step(45.0 * 0.75)


# ── LP inject_targets integration ────────────────────────────────────────────


class TestLPInjectTargets:
    """inject_targets populates LP exercises with per-hand suggestions."""

    def _resolved_day_with_lp(self, exercise_id="lp_max_lift_5s"):
        return {
            "date": "2026-03-15",
            "sessions": [{
                "session_id": "test_session",
                "intent": "strength",
                "tags": {"hard": True},
                "exercise_instances": [{
                    "exercise_id": exercise_id,
                    "prescription": {"sets": 5, "work_seconds": 5},
                    "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.92},
                }],
            }],
        }

    def test_inject_targets_adds_per_hand_loads(self):
        state = _lp_state()
        result = inject_targets(self._resolved_day_with_lp(), state)
        inst = result["sessions"][0]["exercise_instances"][0]
        assert "right_hand" in inst["suggested"]
        assert "left_hand" in inst["suggested"]
        assert inst["suggested"]["right_hand"]["suggested_external_load_kg"] > 0
        assert inst["suggested"]["left_hand"]["suggested_external_load_kg"] > 0

    def test_working_loads_override_baseline(self):
        """Working loads per-hand should override baseline suggestions."""
        state = _lp_state()
        state["working_loads"]["entries"] = [
            {"exercise_id": "lp_max_lift_5s", "key": "lp_max_lift_5s:right", "hand": "right",
             "next_external_load_kg": 48.0, "updated_at": "2026-03-14"},
            {"exercise_id": "lp_max_lift_5s", "key": "lp_max_lift_5s:left", "hand": "left",
             "next_external_load_kg": 43.0, "updated_at": "2026-03-14"},
        ]
        result = inject_targets(self._resolved_day_with_lp(), state)
        inst = result["sessions"][0]["exercise_instances"][0]
        assert inst["suggested"]["right_hand"]["suggested_external_load_kg"] == 48.0
        assert inst["suggested"]["left_hand"]["suggested_external_load_kg"] == 43.0

    def test_hangboard_exercises_unaffected(self):
        """Existing hangboard exercises should still work identically."""
        state = _base_state()
        state["baselines"] = {"hangboard": [{"max_total_load_kg": 100.0}]}
        resolved = {
            "date": "2026-03-15",
            "sessions": [{
                "session_id": "test_session",
                "intent": "strength",
                "tags": {"hard": True},
                "exercise_instances": [{
                    "exercise_id": "max_hang_5s",
                    "prescription": {"sets": 5, "work_seconds": 5},
                    "attributes": {"edge_mm": 20, "grip": "half_crimp", "intensity_pct": 0.92},
                }],
            }],
        }
        result = inject_targets(resolved, state)
        inst = result["sessions"][0]["exercise_instances"][0]
        assert "suggested_total_load_kg" in inst["suggested"]
        # No per-hand keys
        assert "right_hand" not in inst["suggested"]


# ── LP feedback handling ─────────────────────────────────────────────────────


class TestLPFeedback:
    """apply_feedback handles LP exercises with per-hand working loads."""

    def test_feedback_creates_per_hand_entry(self):
        state = _lp_state()
        log = {
            "date": "2026-03-15",
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "lp_max_lift_5s", "hand": "right",
                     "completed": True, "feedback_label": "ok", "used_external_load_kg": 42.0},
                    {"exercise_id": "lp_max_lift_5s", "hand": "left",
                     "completed": True, "feedback_label": "ok", "used_external_load_kg": 38.0},
                ]
            },
        }
        updated = apply_feedback(log, state)
        entries = updated["working_loads"]["entries"]
        right = next(e for e in entries if e["key"] == "lp_max_lift_5s:right")
        left = next(e for e in entries if e["key"] == "lp_max_lift_5s:left")
        assert right["hand"] == "right"
        assert left["hand"] == "left"
        assert right["last_external_load_kg"] == 42.0
        assert left["last_external_load_kg"] == 38.0
        # "ok" feedback → slight increase
        assert right["next_external_load_kg"] > 42.0
        assert left["next_external_load_kg"] > 38.0

    def test_feedback_hard_decreases_load(self):
        state = _lp_state()
        log = {
            "date": "2026-03-15",
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "lp_max_lift_5s", "hand": "right",
                     "completed": True, "feedback_label": "very_hard", "used_external_load_kg": 42.0},
                ]
            },
        }
        updated = apply_feedback(log, state)
        entries = updated["working_loads"]["entries"]
        right = next(e for e in entries if e["key"] == "lp_max_lift_5s:right")
        assert right["next_external_load_kg"] < 42.0


# ── LP test handling ─────────────────────────────────────────────────────────


class TestLPTestHandling:
    """_update_test_from_log handles lp_max_test_5s correctly."""

    def test_lp_test_updates_baselines(self):
        state = _lp_state()
        log = {
            "date": "2026-03-15",
            "session_id": "test_finger",
            "planned": [{"session_id": "test_finger", "tags": {"test": True}, "exercise_instances": []}],
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "lp_max_test_5s", "hand": "right", "used_external_load_kg": 50.0},
                    {"exercise_id": "lp_max_test_5s", "hand": "left", "used_external_load_kg": 44.0},
                ]
            },
        }
        updated = apply_feedback(log, state)
        lp_bl = updated["baselines"]["loading_pin"]
        right_bl = next(b for b in lp_bl if b["hand"] == "right")
        left_bl = next(b for b in lp_bl if b["hand"] == "left")
        assert right_bl["max_load_kg"] == 50.0
        assert right_bl["source"] == "test"
        assert left_bl["max_load_kg"] == 44.0
        assert left_bl["source"] == "test"

    def test_lp_test_writes_assessment_scalars(self):
        state = _lp_state()
        log = {
            "date": "2026-03-15",
            "session_id": "test_finger",
            "planned": [{"session_id": "test_finger", "tags": {"test": True}, "exercise_instances": []}],
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "lp_max_test_5s", "hand": "right", "used_external_load_kg": 50.0},
                    {"exercise_id": "lp_max_test_5s", "hand": "left", "used_external_load_kg": 44.0},
                ]
            },
        }
        updated = apply_feedback(log, state)
        at = updated["assessment"]["tests"]
        assert at["lp_max_lift_5s_right_kg"] == 50.0
        assert at["lp_max_lift_5s_left_kg"] == 44.0


# ── Test scheduling based on device ──────────────────────────────────────────


class TestLPTestScheduling:
    """Test queue uses correct test_id based on finger_training_device."""

    def test_hangboard_user_enqueues_hangboard_test(self):
        state = _base_state()
        state["baselines"] = {"hangboard": [{"max_total_load_kg": 100.0}]}
        # Simulate 2 consecutive "hard" feedbacks on max_hang_5s
        for i in range(2):
            log = {
                "date": f"2026-03-{15+i}",
                "actual": {
                    "exercise_feedback_v1": [
                        {"exercise_id": "max_hang_5s", "completed": True,
                         "feedback_label": "hard", "used_total_load_kg": 92.0},
                    ]
                },
            }
            state = apply_feedback(log, state)
        queue = state.get("test_queue", [])
        assert any(q["test_id"] == "max_hang_5s_total_load" for q in queue)

    def test_lp_user_enqueues_lp_test(self):
        state = _lp_state()
        # Simulate 2 consecutive "hard" feedbacks on max_hang_5s
        # (streak counter is still based on max_hang_5s for both devices)
        for i in range(2):
            log = {
                "date": f"2026-03-{15+i}",
                "actual": {
                    "exercise_feedback_v1": [
                        {"exercise_id": "max_hang_5s", "completed": True,
                         "feedback_label": "hard", "used_total_load_kg": 92.0},
                    ]
                },
            }
            state = apply_feedback(log, state)
        queue = state.get("test_queue", [])
        assert any(q["test_id"] == "lp_max_test_5s" for q in queue)


# ── Equipment filter: LP exercises need loading_pin ──────────────────────────


class TestLPEquipmentFilter:
    """LP exercises should only be available when loading_pin is in equipment."""

    def test_lp_exercises_not_available_without_loading_pin(self):
        """Without loading_pin in equipment, no LP exercises should be selected."""
        selected, _ = pick_best_exercise_p0(
            exercises=ALL_EXERCISES,
            location="home",
            available_equipment=["hangboard", "pullup_bar"],
            role_req=["main"],
            domain_req=["finger_max_strength"],
        )
        if selected:
            assert selected["id"] not in LP_EXERCISE_IDS

    def test_lp_exercises_available_with_loading_pin(self):
        """With loading_pin in equipment, LP exercises should be selectable."""
        selected, _ = pick_best_exercise_p0(
            exercises=ALL_EXERCISES,
            location="home",
            available_equipment=["loading_pin"],
            role_req=["main"],
            domain_req=["finger_max_strength"],
            finger_device="loading_pin",
        )
        assert selected is not None
        assert selected["id"] in LP_EXERCISE_IDS


# ── Planner Pass 3: finger test session selection ──────────────────────────


class TestLPPlannerPass3:
    """Planner Pass 3 should use test_lp_max_5s when finger_device=loading_pin."""

    @pytest.fixture()
    def _base_avail(self):
        """Availability with 5 days, enough for tests to be placed."""
        return {
            day: {"evening": {"available": True, "preferred_location": "home"}}
            for day in ["mon", "tue", "wed", "thu", "fri"]
        }

    def test_pass3_uses_lp_test_when_loading_pin(self, _base_avail):
        from backend.engine.planner_v2 import generate_phase_week
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"finger_strength": 0.4, "pulling_strength": 0.2,
                            "power_endurance": 0.2, "technique": 0.1, "endurance": 0.1},
            session_pool=["strength_long", "finger_strength_home", "prehab_maintenance",
                          "flexibility_full", "complementary_conditioning"],
            start_date="2026-03-16",
            availability=_base_avail,
            home_equipment=["loading_pin", "pullup_bar", "resistance_band"],
            inject_tests=True,
            finger_device="loading_pin",
            is_last_week_of_phase=True,
        )
        all_sids = [
            s["session_id"]
            for d in plan["weeks"][0]["days"]
            for s in d.get("sessions", [])
        ]
        assert "test_lp_max_5s" in all_sids, f"Expected test_lp_max_5s in {all_sids}"
        assert "test_max_hang_5s" not in all_sids, f"Should NOT have test_max_hang_5s in {all_sids}"

    def test_pass3_uses_hb_test_when_hangboard(self, _base_avail):
        from backend.engine.planner_v2 import generate_phase_week
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"finger_strength": 0.4, "pulling_strength": 0.2,
                            "power_endurance": 0.2, "technique": 0.1, "endurance": 0.1},
            session_pool=["strength_long", "finger_strength_home", "prehab_maintenance",
                          "flexibility_full", "complementary_conditioning"],
            start_date="2026-03-16",
            availability=_base_avail,
            home_equipment=["hangboard", "pullup_bar", "resistance_band"],
            inject_tests=True,
            finger_device="hangboard",
            is_last_week_of_phase=True,
        )
        all_sids = [
            s["session_id"]
            for d in plan["weeks"][0]["days"]
            for s in d.get("sessions", [])
        ]
        assert "test_max_hang_5s" in all_sids, f"Expected test_max_hang_5s in {all_sids}"
        assert "test_lp_max_5s" not in all_sids

    def test_pass3_default_none_uses_hangboard(self, _base_avail):
        from backend.engine.planner_v2 import generate_phase_week
        plan = generate_phase_week(
            phase_id="base",
            domain_weights={"finger_strength": 0.4, "pulling_strength": 0.2,
                            "power_endurance": 0.2, "technique": 0.1, "endurance": 0.1},
            session_pool=["strength_long", "finger_strength_home", "prehab_maintenance",
                          "flexibility_full", "complementary_conditioning"],
            start_date="2026-03-16",
            availability=_base_avail,
            home_equipment=["hangboard", "pullup_bar", "resistance_band"],
            inject_tests=True,
            is_last_week_of_phase=True,
        )
        all_sids = [
            s["session_id"]
            for d in plan["weeks"][0]["days"]
            for s in d.get("sessions", [])
        ]
        assert "test_max_hang_5s" in all_sids
