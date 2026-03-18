"""
A121 — Tests for phase-aware intra-session exercise ordering.

Covers: infer_sort_category, sort_exercises_by_phase, enforce_ordering_constraints.
P0 invariant: sort NEVER loses exercises.
"""

import json
import os

import pytest

from backend.engine.exercise_ordering import (
    PHASE_SORT_ORDER,
    SORT_CATEGORIES,
    enforce_ordering_constraints,
    infer_sort_category,
    sort_exercises_by_phase,
)

EXERCISES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "catalog", "exercises", "v1", "exercises.json"
)


def _load_catalog():
    with open(EXERCISES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["exercises"] if isinstance(data, dict) else data


# =====================================================================
# 3.1 — Unit tests for infer_sort_category
# =====================================================================

class TestInferSortCategory:

    def test_warmup(self):
        assert infer_sort_category({"role": "warmup", "domain": "mobility"}) == "warmup"

    def test_warmup_accessory_multi_role(self):
        """Multi-role warmup+accessory → warmup (warmup wins when main not present)."""
        assert infer_sort_category({"role": ["warmup", "accessory"], "domain": "core"}) == "warmup"

    def test_prehab_over_finger_strength(self):
        """active_finger_curls fix: role=prehab + domain=finger_strength → antagonist_prehab."""
        assert infer_sort_category({"role": "prehab", "domain": "finger_strength", "pattern": "wrist_flexion"}) == "antagonist_prehab"

    def test_prehab_shoulder(self):
        assert infer_sort_category({"role": "prehab", "domain": "prehab_shoulder"}) == "antagonist_prehab"

    def test_arc_training(self):
        assert infer_sort_category({"role": "main", "domain": "aerobic_capacity", "pattern": "climbing_continuous"}) == "aerobic_pure"

    def test_max_hang(self):
        assert infer_sort_category({"role": "main", "domain": "finger_max_strength", "pattern": "isometric_hang"}) == "strength_neural"

    def test_finger_strength_isometric(self):
        """finger_strength (legacy) + isometric_hang → strength_neural."""
        assert infer_sort_category({"role": "main", "domain": "finger_strength", "pattern": "isometric_hang"}) == "strength_neural"

    def test_finger_strength_repeater(self):
        """finger_strength (legacy) + repeater_hang → finger_endurance."""
        assert infer_sort_category({"role": "main", "domain": "finger_strength", "pattern": "repeater_hang"}) == "finger_endurance"

    def test_threshold(self):
        assert infer_sort_category({"role": "main", "domain": "endurance", "pattern": "climbing_continuous"}) == "threshold"

    def test_technique(self):
        assert infer_sort_category({"role": "technique", "domain": "technique_footwork", "pattern": "technique_drill"}) == "technique"

    def test_technique_domain_only(self):
        """technique_ domain prefix triggers technique even without role=technique."""
        assert infer_sort_category({"role": "main", "domain": "technique_boulder"}) == "technique"

    def test_power(self):
        assert infer_sort_category({"role": "main", "domain": "power"}) == "power"

    def test_pe_intervals(self):
        assert infer_sort_category({"role": "main", "domain": "power_endurance"}) == "pe_intervals"

    def test_cooldown(self):
        assert infer_sort_category({"role": "cooldown", "domain": "flexibility"}) == "cooldown"

    def test_core(self):
        assert infer_sort_category({"role": "accessory", "domain": "core"}) == "core"

    def test_pulling_supplementary(self):
        assert infer_sort_category({"role": "main", "domain": "strength_general", "pattern": "pull_vertical"}) == "pulling_supplementary"

    def test_antagonist_push(self):
        assert infer_sort_category({"role": "accessory", "domain": "strength_general", "pattern": "push"}) == "antagonist_prehab"

    def test_lock_off_endurance(self):
        assert infer_sort_category({"role": "accessory", "domain": "lock_off_endurance"}) == "pulling_supplementary"

    def test_handstand(self):
        assert infer_sort_category({"role": "accessory", "domain": "handstand_skill"}) == "core"

    def test_fallback_unknown_domain(self):
        """Unknown domain → main_unclassified (never None, never error)."""
        assert infer_sort_category({"role": "main", "domain": "some_future_domain"}) == "main_unclassified"

    def test_empty_dict(self):
        assert infer_sort_category({}) == "main_unclassified"


# =====================================================================
# 3.2 — Full catalog coverage
# =====================================================================

class TestCatalogCoverage:

    def test_all_exercises_have_valid_sort_category(self):
        """Every exercise in catalog maps to a valid sort category."""
        exercises = _load_catalog()
        assert len(exercises) > 0
        for ex in exercises:
            cat = infer_sort_category(ex)
            assert cat in SORT_CATEGORIES, (
                f"Exercise '{ex.get('id')}' mapped to unknown category '{cat}'"
            )

    def test_zero_unclassified(self):
        """Currently 0 exercises fall to main_unclassified — keep it that way."""
        exercises = _load_catalog()
        unclassified = [
            ex.get("id") for ex in exercises
            if infer_sort_category(ex) == "main_unclassified"
        ]
        assert unclassified == [], f"Unclassified exercises: {unclassified}"

    def test_active_finger_curls_is_prehab(self):
        """Regression: active_finger_curls must be antagonist_prehab, not strength_neural."""
        exercises = _load_catalog()
        afc = next((e for e in exercises if e.get("id") == "active_finger_curls"), None)
        if afc:
            assert infer_sort_category(afc) == "antagonist_prehab"


# =====================================================================
# 3.3 — Anti-loss test (P0 invariant)
# =====================================================================

class TestAntiLoss:

    SAMPLE_EXERCISES = [
        {"exercise_id": "arc_training", "role": "main", "domain": "aerobic_capacity"},
        {"exercise_id": "max_hang_7s", "role": "main", "domain": "finger_max_strength", "pattern": "isometric_hang"},
        {"exercise_id": "pushup", "role": "accessory", "domain": "strength_general", "pattern": "push"},
        {"exercise_id": "dynamic_mobility_flow", "role": "warmup", "domain": "mobility"},
        {"exercise_id": "cooldown_forearm", "role": "cooldown", "domain": "flexibility"},
    ]

    def test_sort_never_loses_exercises_any_phase(self):
        """P0: sort produces same set of exercise_ids, for every phase."""
        ids_before = set(ex["exercise_id"] for ex in self.SAMPLE_EXERCISES)
        for phase in PHASE_SORT_ORDER:
            sorted_ex = sort_exercises_by_phase(self.SAMPLE_EXERCISES, phase)
            constrained_ex = enforce_ordering_constraints(sorted_ex, phase)
            ids_after = set(ex["exercise_id"] for ex in constrained_ex)
            assert ids_before == ids_after, f"Exercise loss in phase {phase}!"
            assert len(constrained_ex) == len(self.SAMPLE_EXERCISES), f"Count mismatch in phase {phase}!"

    def test_sort_preserves_count_with_duplicates(self):
        """If two exercises share the same exercise_id (edge case), count is preserved."""
        exercises = [
            {"exercise_id": "a", "role": "main", "domain": "core"},
            {"exercise_id": "a", "role": "main", "domain": "core"},
            {"exercise_id": "b", "role": "warmup", "domain": "mobility"},
        ]
        result = sort_exercises_by_phase(exercises, "endurance_base")
        assert len(result) == 3


# =====================================================================
# 3.4 — Phase-specific ordering
# =====================================================================

class TestPhaseOrdering:

    def test_base_arc_before_threshold(self):
        """Base phase: ARC (aerobic_pure) MUST come before Threshold Climbing."""
        exercises = [
            {"exercise_id": "warmup", "role": "warmup", "domain": "mobility"},
            {"exercise_id": "threshold_climbing", "role": "main", "domain": "endurance", "pattern": "climbing_continuous"},
            {"exercise_id": "arc_training", "role": "main", "domain": "aerobic_capacity", "pattern": "climbing_continuous"},
            {"exercise_id": "core_plank", "role": "accessory", "domain": "core"},
            {"exercise_id": "pushup", "role": "accessory", "domain": "strength_general", "pattern": "push"},
        ]
        result = sort_exercises_by_phase(exercises, "endurance_base")
        result = enforce_ordering_constraints(result, "endurance_base")
        ids = [ex["exercise_id"] for ex in result]

        assert ids[0] == "warmup"
        assert ids.index("arc_training") < ids.index("threshold_climbing")
        assert ids.index("threshold_climbing") < ids.index("core_plank")

    def test_sp_neural_before_pulling(self):
        """S&P phase: Max hangs (strength_neural) MUST come before pulling supplementary."""
        exercises = [
            {"exercise_id": "warmup", "role": "warmup", "domain": "mobility"},
            {"exercise_id": "weighted_pullup", "role": "main", "domain": "strength_general", "pattern": "pull_vertical"},
            {"exercise_id": "max_hang_7s", "role": "main", "domain": "finger_max_strength", "pattern": "isometric_hang"},
            {"exercise_id": "core_plank", "role": "accessory", "domain": "core"},
        ]
        result = sort_exercises_by_phase(exercises, "strength_power")
        result = enforce_ordering_constraints(result, "strength_power")
        ids = [ex["exercise_id"] for ex in result]

        assert ids[0] == "warmup"
        assert ids.index("max_hang_7s") < ids.index("weighted_pullup")

    def test_pe_intervals_first(self):
        """PE phase: PE intervals MUST come before threshold/volume."""
        exercises = [
            {"exercise_id": "warmup", "role": "warmup", "domain": "mobility"},
            {"exercise_id": "threshold_climbing", "role": "main", "domain": "endurance"},
            {"exercise_id": "four_by_four", "role": "main", "domain": "power_endurance"},
            {"exercise_id": "repeater_lopez", "role": "main", "domain": "finger_strength_endurance", "pattern": "repeater_hang"},
        ]
        result = sort_exercises_by_phase(exercises, "power_endurance")
        result = enforce_ordering_constraints(result, "power_endurance")
        ids = [ex["exercise_id"] for ex in result]

        assert ids[0] == "warmup"
        assert ids.index("four_by_four") < ids.index("repeater_lopez")
        assert ids.index("repeater_lopez") < ids.index("threshold_climbing")

    def test_performance_power_first(self):
        """Performance phase: power/climbing at limit before accessories."""
        exercises = [
            {"exercise_id": "warmup", "role": "warmup", "domain": "mobility"},
            {"exercise_id": "core_plank", "role": "accessory", "domain": "core"},
            {"exercise_id": "limit_boulder", "role": "main", "domain": "power", "pattern": "climbing_limit_boulder"},
        ]
        result = sort_exercises_by_phase(exercises, "performance")
        result = enforce_ordering_constraints(result, "performance")
        ids = [ex["exercise_id"] for ex in result]

        assert ids[0] == "warmup"
        assert ids.index("limit_boulder") < ids.index("core_plank")

    def test_deload_easy_first(self):
        """Deload phase: easy climbing before accessories."""
        exercises = [
            {"exercise_id": "warmup", "role": "warmup", "domain": "mobility"},
            {"exercise_id": "core_plank", "role": "accessory", "domain": "core"},
            {"exercise_id": "easy_laps", "role": "main", "domain": "aerobic_capacity"},
        ]
        result = sort_exercises_by_phase(exercises, "deload")
        result = enforce_ordering_constraints(result, "deload")
        ids = [ex["exercise_id"] for ex in result]

        assert ids[0] == "warmup"
        assert ids.index("easy_laps") < ids.index("core_plank")


# =====================================================================
# 3.5 — Constraint enforcement
# =====================================================================

class TestConstraints:

    def test_warmup_always_first(self):
        exercises = [
            {"exercise_id": "arc", "role": "main", "domain": "aerobic_capacity"},
            {"exercise_id": "warmup", "role": "warmup", "domain": "mobility"},
        ]
        result = enforce_ordering_constraints(exercises, "endurance_base")
        assert result[0]["exercise_id"] == "warmup"

    def test_cooldown_always_last(self):
        exercises = [
            {"exercise_id": "warmup", "role": "warmup", "domain": "mobility"},
            {"exercise_id": "stretch", "role": "cooldown", "domain": "flexibility"},
            {"exercise_id": "core", "role": "accessory", "domain": "core"},
        ]
        result = enforce_ordering_constraints(exercises, "endurance_base")
        assert result[-1]["exercise_id"] == "stretch"

    def test_arc_before_threshold(self):
        exercises = [
            {"exercise_id": "warmup", "role": "warmup", "domain": "mobility"},
            {"exercise_id": "threshold", "role": "main", "domain": "endurance"},
            {"exercise_id": "arc", "role": "main", "domain": "aerobic_capacity"},
        ]
        result = enforce_ordering_constraints(exercises, "endurance_base")
        ids = [ex["exercise_id"] for ex in result]
        assert ids.index("arc") < ids.index("threshold")

    def test_neural_before_pulling(self):
        exercises = [
            {"exercise_id": "pullup", "role": "main", "domain": "strength_general", "pattern": "pull_vertical"},
            {"exercise_id": "max_hang", "role": "main", "domain": "finger_max_strength"},
        ]
        result = enforce_ordering_constraints(exercises, "strength_power")
        ids = [ex["exercise_id"] for ex in result]
        assert ids.index("max_hang") < ids.index("pullup")

    def test_accessories_after_main(self):
        exercises = [
            {"exercise_id": "warmup", "role": "warmup", "domain": "mobility"},
            {"exercise_id": "core", "role": "accessory", "domain": "core"},
            {"exercise_id": "arc", "role": "main", "domain": "aerobic_capacity"},
        ]
        result = enforce_ordering_constraints(exercises, "endurance_base")
        ids = [ex["exercise_id"] for ex in result]
        assert ids.index("arc") < ids.index("core")

    def test_constraints_never_lose_exercises(self):
        """P0: constraint enforcement preserves all exercises."""
        exercises = [
            {"exercise_id": "a", "role": "cooldown", "domain": "flexibility"},
            {"exercise_id": "b", "role": "warmup", "domain": "mobility"},
            {"exercise_id": "c", "role": "main", "domain": "core"},
            {"exercise_id": "d", "role": "main", "domain": "aerobic_capacity"},
            {"exercise_id": "e", "role": "main", "domain": "endurance"},
        ]
        for phase in PHASE_SORT_ORDER:
            result = enforce_ordering_constraints(exercises, phase)
            assert set(ex["exercise_id"] for ex in result) == {"a", "b", "c", "d", "e"}


# =====================================================================
# 3.6 — Edge cases
# =====================================================================

class TestEdgeCases:

    def test_empty_list(self):
        assert sort_exercises_by_phase([], "endurance_base") == []
        assert enforce_ordering_constraints([], "endurance_base") == []

    def test_single_exercise(self):
        ex = [{"exercise_id": "arc", "role": "main", "domain": "aerobic_capacity"}]
        result = sort_exercises_by_phase(ex, "endurance_base")
        assert len(result) == 1 and result[0]["exercise_id"] == "arc"

    def test_unknown_phase_returns_unsorted(self):
        exercises = [
            {"exercise_id": "a", "role": "main", "domain": "core"},
            {"exercise_id": "b", "role": "warmup", "domain": "mobility"},
        ]
        result = sort_exercises_by_phase(exercises, "nonexistent_phase")
        assert result[0]["exercise_id"] == "a"  # unchanged order

    def test_no_crash_on_minimal_exercise(self):
        for ex in [{}, {"exercise_id": "x"}, {"role": "main"}]:
            cat = infer_sort_category(ex)
            assert cat in SORT_CATEGORIES
