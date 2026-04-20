"""B215 — pulling baseline symmetry with hangboard Priority 0.

Ensures _estimate_pulling_baseline gates on assessment.tests_source so the
baseline reflects whether the scalar came from a real measurement or an
estimate. Mirrors the hangboard fallback chain introduced in D214.
"""
from __future__ import annotations

from datetime import datetime

from backend.engine.progression_v1 import _estimate_pulling_baseline


def _state_with_1rm(value: float, *, measured: bool, bodyweight: float = 70.0) -> dict:
    src: dict = {}
    if measured:
        # Onboarding writer marks the canonical key (and the 1rm_total alias).
        src["weighted_pullup_1rm_total_kg"] = "measured"
    return {
        "bodyweight_kg": bodyweight,
        "assessment": {
            "tests": {"weighted_pullup_1rm_total_kg": value},
            "tests_source": src,
        },
        "baselines": {},
    }


class TestMeasuredPullup1rmPriority0:
    def test_measured_stamps_source_test_and_updated_at(self) -> None:
        state = _state_with_1rm(130.0, measured=True)
        _estimate_pulling_baseline(state)
        pulling = state["baselines"]["pulling"]
        assert pulling["source"] == "test"
        assert "updated_at" in pulling
        assert "estimated_at" not in pulling
        assert pulling["weighted_pullup_1rm_total_kg"] == 130.0
        assert pulling["max_external_load_kg"] == 60.0

    def test_measured_via_2rm_sibling_also_promotes(self) -> None:
        """If only the 2RM key is marked measured, the baseline still promotes."""
        state = _state_with_1rm(130.0, measured=False)
        state["assessment"]["tests_source"]["weighted_pullup_2rm_total_kg"] = "measured"
        _estimate_pulling_baseline(state)
        assert state["baselines"]["pulling"]["source"] == "test"

    def test_measured_via_1rm_estimated_key_also_promotes(self) -> None:
        """Post-test-session writer marks weighted_pullup_1rm_estimated_kg."""
        state = _state_with_1rm(130.0, measured=False)
        state["assessment"]["tests_source"]["weighted_pullup_1rm_estimated_kg"] = "measured"
        _estimate_pulling_baseline(state)
        assert state["baselines"]["pulling"]["source"] == "test"


class TestEstimatedPullup1rm:
    def test_no_source_key_stamps_estimated(self) -> None:
        """Legacy state (no tests_source) → baseline stays estimated."""
        state = _state_with_1rm(120.0, measured=False)
        _estimate_pulling_baseline(state)
        pulling = state["baselines"]["pulling"]
        assert pulling["source"] == "estimated_from_assessment"
        assert "estimated_at" in pulling
        assert "updated_at" not in pulling

    def test_explicit_estimated_still_estimated(self) -> None:
        state = _state_with_1rm(120.0, measured=False)
        state["assessment"]["tests_source"]["weighted_pullup_1rm_total_kg"] = "estimated"
        _estimate_pulling_baseline(state)
        assert state["baselines"]["pulling"]["source"] == "estimated_from_assessment"


class TestGuards:
    def test_existing_test_session_source_protected(self) -> None:
        """Baseline with source='test_session' must NOT be overwritten."""
        state = _state_with_1rm(120.0, measured=True)
        state["baselines"]["pulling"] = {
            "source": "test_session",
            "weighted_pullup_1rm_total_kg": 100.0,
            "updated_at": "2026-04-01",
        }
        _estimate_pulling_baseline(state)
        # Unchanged: the earlier in-app test result wins over an onboarding value.
        pulling = state["baselines"]["pulling"]
        assert pulling["source"] == "test_session"
        assert pulling["weighted_pullup_1rm_total_kg"] == 100.0
        assert pulling["updated_at"] == "2026-04-01"

    def test_existing_test_source_protected(self) -> None:
        state = _state_with_1rm(120.0, measured=True)
        state["baselines"]["pulling"] = {
            "source": "test",
            "weighted_pullup_1rm_total_kg": 110.0,
            "updated_at": "2026-04-10",
        }
        _estimate_pulling_baseline(state)
        assert state["baselines"]["pulling"]["source"] == "test"
        assert state["baselines"]["pulling"]["weighted_pullup_1rm_total_kg"] == 110.0

    def test_no_1rm_scalar_no_baseline(self) -> None:
        state: dict = {
            "bodyweight_kg": 70.0,
            "assessment": {"tests": {}, "tests_source": {}},
            "baselines": {},
        }
        _estimate_pulling_baseline(state)
        assert state["baselines"].get("pulling") in (None, {})

    def test_zero_bodyweight_short_circuits(self) -> None:
        state = _state_with_1rm(120.0, measured=True, bodyweight=0.0)
        _estimate_pulling_baseline(state)
        assert state["baselines"].get("pulling") in (None, {})


class TestF3FreshnessRegression:
    """Belt-and-braces: B215 changes the baseline source but doesn't change
    week.py freshness gate logic. Replay the gate inline to prove estimated
    pulling still triggers a retest (F3 closure from D214).
    """

    def test_estimated_pulling_still_triggers_retest(self) -> None:
        """With tests_source missing for pulling → freshness map empty → retest fires."""
        state = _state_with_1rm(120.0, measured=False)
        _estimate_pulling_baseline(state)
        assert state["baselines"]["pulling"]["source"] == "estimated_from_assessment"

        # Replay of week.py freshness logic (simplified).
        tests_src = state["assessment"].get("tests_source") or {}
        pulling_measured = tests_src.get("weighted_pullup_1rm_total_kg") == "measured"
        pulling_baseline = state["baselines"].get("pulling") or {}
        # Gate: only treat as fresh if source-marked measured AND baseline has updated_at
        treat_as_fresh = pulling_measured and "updated_at" in pulling_baseline
        assert treat_as_fresh is False, (
            "Estimated pulling must not be treated as fresh — F3 would re-open"
        )

    def test_measured_pulling_is_fresh(self) -> None:
        state = _state_with_1rm(120.0, measured=True)
        _estimate_pulling_baseline(state)
        tests_src = state["assessment"].get("tests_source") or {}
        pulling_measured = tests_src.get("weighted_pullup_1rm_total_kg") == "measured"
        pulling_baseline = state["baselines"].get("pulling") or {}
        treat_as_fresh = pulling_measured and "updated_at" in pulling_baseline
        assert treat_as_fresh is True
