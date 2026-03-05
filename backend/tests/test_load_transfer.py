"""Tests for cross-exercise load transfer and coherence check (B90)."""

import pytest

from backend.engine.progression_v1 import (
    _SIMILARITY_GROUPS,
    _EXERCISE_TO_GROUP,
    _transfer_load,
    check_load_coherence,
    _best_entry,
    _round_half_step,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_with_entry(exercise_id: str, load_kg: float, date: str = "2026-03-01") -> dict:
    """Create a minimal user_state with a single working_loads entry."""
    return {
        "working_loads": {
            "entries": [
                {
                    "exercise_id": exercise_id,
                    "key": exercise_id,
                    "setup": {},
                    "next_external_load_kg": load_kg,
                    "last_external_load_kg": load_kg,
                    "last_feedback_label": "ok",
                    "updated_at": date,
                }
            ],
            "rules": {},
        },
        "bodyweight_kg": 75,
    }


def _state_with_entries(entries: list) -> dict:
    """Create user_state with multiple working_loads entries."""
    return {
        "working_loads": {
            "entries": [
                {
                    "exercise_id": e["id"],
                    "key": e["id"],
                    "setup": {},
                    "next_external_load_kg": e["load"],
                    "last_external_load_kg": e["load"],
                    "last_feedback_label": "ok",
                    "updated_at": e.get("date", "2026-03-01"),
                }
                for e in entries
            ],
            "rules": {},
        },
        "bodyweight_kg": 75,
    }


# ---------------------------------------------------------------------------
# Transfer tests
# ---------------------------------------------------------------------------


class TestLoadTransfer:
    """Cross-exercise load transfer via similarity groups."""

    def test_transfer_bench_to_dumbbell(self):
        """bench_press 40kg → dumbbell_bench_press should be ~34kg (0.85×)."""
        state = _state_with_entry("bench_press", 40.0)
        result = _transfer_load(state, "dumbbell_bench_press", "2026-03-05")
        assert result is not None
        assert result == _round_half_step(40.0 * 0.85)

    def test_transfer_dumbbell_to_bench(self):
        """dumbbell_bench_press 34kg → bench_press should be ~40kg (1/0.85×)."""
        state = _state_with_entry("dumbbell_bench_press", 34.0)
        result = _transfer_load(state, "bench_press", "2026-03-05")
        assert result is not None
        assert result == _round_half_step(34.0 * (1.0 / 0.85))

    def test_transfer_split_squat_to_goblet(self):
        """split_squat 15kg → goblet_squat should be ~12kg (0.80×)."""
        state = _state_with_entry("split_squat", 15.0)
        result = _transfer_load(state, "goblet_squat", "2026-03-05")
        assert result is not None
        assert result == _round_half_step(15.0 * 0.80)

    def test_no_transfer_across_groups(self):
        """bench_press should not transfer to split_squat (different group)."""
        state = _state_with_entry("bench_press", 40.0)
        result = _transfer_load(state, "split_squat", "2026-03-05")
        assert result is None

    def test_no_transfer_for_ungrouped(self):
        """barbell_row has no similarity group → no transfer."""
        state = _state_with_entry("bench_press", 40.0)
        result = _transfer_load(state, "barbell_row", "2026-03-05")
        assert result is None

    def test_no_transfer_when_stale(self):
        """Entries older than 60 days should not be used for transfer."""
        state = _state_with_entry("bench_press", 40.0, date="2025-12-01")
        result = _transfer_load(state, "dumbbell_bench_press", "2026-03-05")
        assert result is None

    def test_direct_entry_preferred_over_transfer(self):
        """When exercise has its own entry, transfer should not be needed."""
        state = _state_with_entries([
            {"id": "bench_press", "load": 40.0},
            {"id": "dumbbell_bench_press", "load": 30.0},
        ])
        # Direct entry exists, so _best_entry should find it
        entry = _best_entry(state, "dumbbell_bench_press", {}, "2026-03-05")
        assert entry is not None
        assert entry["next_external_load_kg"] == 30.0


# ---------------------------------------------------------------------------
# Coherence tests
# ---------------------------------------------------------------------------


class TestLoadCoherence:
    """Check for outlier load ratios within similarity groups."""

    def test_no_warning_when_coherent(self):
        """Loads matching expected ratio should produce no warnings."""
        state = _state_with_entries([
            {"id": "bench_press", "load": 40.0},
            {"id": "dumbbell_bench_press", "load": 34.0},
        ])
        warnings = check_load_coherence(state, "2026-03-05")
        assert len(warnings) == 0

    def test_warning_when_outlier(self):
        """bench_press 60kg but dumbbell_bench_press 15kg → ratio way off."""
        state = _state_with_entries([
            {"id": "bench_press", "load": 60.0},
            {"id": "dumbbell_bench_press", "load": 15.0},
        ])
        warnings = check_load_coherence(state, "2026-03-05")
        assert len(warnings) == 1
        assert warnings[0]["group"] == "push"

    def test_no_warning_single_entry(self):
        """Only one entry in group → no comparison possible."""
        state = _state_with_entry("bench_press", 40.0)
        warnings = check_load_coherence(state, "2026-03-05")
        assert len(warnings) == 0
