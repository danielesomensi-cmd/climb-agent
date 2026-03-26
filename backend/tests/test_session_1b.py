"""Tests for Session 1b: Test Protocol Revision (D84-D91).

D85: Finger strength test 5s → 7s (MVC-7)
D84: Pulling test 1RM → 2RM + 1RM estimation
D84b: New exercise test_max_pullup_bw
D86: Benchmark for BW hang duration test
D88: Benchmark for L-sit test
D90: Removed med_test from catalog
"""
import json
from pathlib import Path

import pytest

from backend.engine.progression_v1 import estimate_1rm_from_2rm, apply_feedback

EXERCISES_PATH = Path("backend/catalog/exercises/v1/exercises.json")
TEMPLATES_PATH = Path("backend/catalog/templates/v1")
SESSIONS_PATH = Path("backend/catalog/sessions/v1")


@pytest.fixture(scope="module")
def exercises():
    with open(EXERCISES_PATH) as f:
        data = json.load(f)
        return {e["id"]: e for e in data["exercises"]}


@pytest.fixture(scope="module")
def templates():
    result = {}
    for p in TEMPLATES_PATH.glob("*.json"):
        with open(p) as f:
            t = json.load(f)
            result[t["id"]] = t
    return result


@pytest.fixture(scope="module")
def sessions():
    result = {}
    for p in SESSIONS_PATH.glob("*.json"):
        with open(p) as f:
            s = json.load(f)
            result[s["id"]] = s
    return result


# ---------------------------------------------------------------------------
# D85: max_hang 5s → 7s
# ---------------------------------------------------------------------------


class TestD85_MaxHang7s:
    def test_max_hang_7s_is_test_primary_in_template(self, templates):
        t = templates["finger_max_strength_test"]
        main_block = next(b for b in t["blocks"] if b["block_id"] == "main")
        assert main_block["exercise_id"] == "max_hang_7s"
        assert main_block["prescription"]["work_seconds"] == 7

    def test_max_hang_7s_has_test_role(self, exercises):
        e = exercises["max_hang_7s"]
        assert "test" in e["role"]

    def test_max_hang_5s_still_exists_no_test_role(self, exercises):
        e = exercises["max_hang_5s"]
        assert "test" not in e["role"]
        assert "main" in e["role"]

    def test_session_test_id_is_7s(self, sessions):
        # The legacy session file (test_max_hang_5s) should now have 7s test_id
        s = sessions["test_max_hang_5s"]
        assert s["test_id"] == "max_hang_7s_total_load"

    def test_max_hang_7s_sets_5(self, exercises):
        e = exercises["max_hang_7s"]
        assert e["prescription_defaults"]["sets"] == 5

    def test_max_hang_7s_rest_180(self, exercises):
        e = exercises["max_hang_7s"]
        assert e["prescription_defaults"]["rest_between_sets_seconds"] == 180


# ---------------------------------------------------------------------------
# D84: Pulling test 1RM → 2RM
# ---------------------------------------------------------------------------


class TestD84_2RM:
    def test_estimate_1rm_from_2rm_100kg(self):
        result = estimate_1rm_from_2rm(100.0)
        # Epley: 100 * (1 + 2/30) ≈ 106.667
        # Brzycki: 100 * (36/35) ≈ 102.857
        # Average ≈ 104.8
        assert 104.5 < result < 105.0

    def test_estimate_1rm_from_2rm_80kg(self):
        result = estimate_1rm_from_2rm(80.0)
        # Should be about 3.8% more than 2RM
        assert result > 80.0
        assert result < 85.0

    def test_pulling_template_uses_2rm(self, templates):
        t = templates["pulling_strength_test"]
        main_block = next(b for b in t["blocks"] if b["block_id"] == "main")
        assert main_block["prescription"]["reps"] == 2
        assert main_block["prescription"]["rest_between_sets_seconds"] == 180
        assert main_block["prescription"]["test_protocol"] == "2RM"

    def test_pulling_template_no_gate_block(self, templates):
        """B128: gate_bw_pullup removed — BW test is now a separate session."""
        t = templates["pulling_strength_test"]
        block_ids = [b["block_id"] for b in t["blocks"]]
        assert "gate_bw_pullup" not in block_ids

    def test_pulling_template_main_no_gate(self, templates):
        """B128: main block no longer has gate — routing is handled by planner."""
        t = templates["pulling_strength_test"]
        main_block = next(b for b in t["blocks"] if b["block_id"] == "main")
        assert "gate" not in main_block

    def test_session_test_id_is_2rm(self, sessions):
        s = sessions["test_max_weighted_pullup"]
        assert s["test_id"] == "weighted_pullup_2rm"


# ---------------------------------------------------------------------------
# D84b: test_max_pullup_bw
# ---------------------------------------------------------------------------


class TestD84b_MaxPullupBW:
    def test_exercise_exists_in_catalog(self, exercises):
        assert "test_max_pullup_bw" in exercises

    def test_exercise_has_test_role(self, exercises):
        e = exercises["test_max_pullup_bw"]
        assert "test" in e["role"]

    def test_exercise_requires_pullup_bar(self, exercises):
        e = exercises["test_max_pullup_bw"]
        assert "pullup_bar" in e["equipment_required"]

    def test_feedback_writes_assessment_tests(self):
        state = {
            "bodyweight_kg": 75.0,
            "assessment": {"tests": {}},
        }
        log = {
            "date": "2026-03-18",
            "planned": [{"session_id": "test_max_weighted_pullup", "tags": {"test": True}}],
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "test_max_pullup_bw", "max_pullups_bw": 20},
                ]
            },
        }
        result = apply_feedback(log, state)
        assert result["assessment"]["tests"]["max_pullups_bw"] == 20


# ---------------------------------------------------------------------------
# D86: Benchmark for BW hang duration test
# ---------------------------------------------------------------------------


class TestD86_HangDurationBenchmark:
    def test_benchmark_note_present(self, exercises):
        e = exercises["test_max_hang_duration_20mm"]
        assert "benchmark_note" in e
        assert e["benchmarks"] is None

    def test_benchmark_note_mentions_90s(self, exercises):
        e = exercises["test_max_hang_duration_20mm"]
        assert "90s" in e["benchmark_note"]


# ---------------------------------------------------------------------------
# D88: Benchmark for L-sit test
# ---------------------------------------------------------------------------


class TestD88_LSitBenchmark:
    def test_benchmarks_present(self, exercises):
        e = exercises["test_l_sit_hold"]
        assert "benchmarks" in e
        assert e["benchmarks"]["scale"] is not None

    def test_benchmarks_has_4_levels(self, exercises):
        e = exercises["test_l_sit_hold"]
        assert len(e["benchmarks"]["scale"]) == 4

    def test_benchmarks_labels(self, exercises):
        e = exercises["test_l_sit_hold"]
        labels = [s["label"] for s in e["benchmarks"]["scale"]]
        assert labels == ["Scarso", "Intermedio", "Avanzato", "Elite"]


# ---------------------------------------------------------------------------
# D90: med_test removed
# ---------------------------------------------------------------------------


class TestD90_MedTestRemoved:
    def test_med_test_not_in_catalog(self, exercises):
        assert "med_test" not in exercises

    def test_critical_force_test_removed(self, exercises):
        """B157: critical_force_test removed (orphan leak, deferred to v2/D89)."""
        assert "critical_force_test" not in exercises


# ---------------------------------------------------------------------------
# B128: Pull-up gate separation
# ---------------------------------------------------------------------------


class TestB128_PullupGateSeparation:
    """BW pull-up test and weighted 2RM are NEVER in the same session."""

    def test_bw_session_exists(self, sessions):
        s = sessions["test_pullup_bw"]
        assert s["test_id"] == "max_pullups_bw"

    def test_bw_template_exists(self, templates):
        t = templates["pulling_strength_test_bw"]
        main = next(b for b in t["blocks"] if b["block_id"] == "main")
        assert main["exercise_id"] == "test_max_pullup_bw"

    def test_weighted_session_has_no_bw_block(self, templates):
        """The weighted template must NOT contain max reps BW as a block."""
        t = templates["pulling_strength_test"]
        ex_ids = [b.get("exercise_id") for b in t["blocks"]]
        assert "test_max_pullup_bw" not in ex_ids

    def test_routing_with_pulling_baseline(self):
        from backend.engine.planner_v2 import _pick_pulling_test_session
        result = _pick_pulling_test_session({"max_total_load_kg": 100}, None)
        assert result == "test_max_weighted_pullup"

    def test_routing_no_baseline_no_bw(self):
        from backend.engine.planner_v2 import _pick_pulling_test_session
        result = _pick_pulling_test_session(None, None)
        assert result == "test_pullup_bw"

    def test_routing_no_baseline_bw_above_15(self):
        from backend.engine.planner_v2 import _pick_pulling_test_session
        result = _pick_pulling_test_session(None, 20)
        assert result == "test_max_weighted_pullup"

    def test_routing_no_baseline_bw_below_15(self):
        from backend.engine.planner_v2 import _pick_pulling_test_session
        result = _pick_pulling_test_session(None, 10)
        assert result == "test_pullup_bw"

    def test_routing_no_baseline_bw_exactly_15(self):
        from backend.engine.planner_v2 import _pick_pulling_test_session
        result = _pick_pulling_test_session(None, 15)
        assert result == "test_max_weighted_pullup"
