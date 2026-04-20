"""B214 — regression tests for the scalar-write map consolidation.

Ensures the `_TEST_EXERCISE_SCALARS` registry stays in sync with the
`exercise_id` branches in `_update_test_from_log`, and that every mapped
key is a canonical `assessment.tests.*` scalar.
"""
from __future__ import annotations

import ast
import inspect
from typing import Set

from backend.engine import progression_v1
from backend.engine.progression_v1 import (
    _TEST_EXERCISE_PER_HAND,
    _TEST_EXERCISE_SCALARS,
    _update_test_from_log,
    apply_feedback,
)


# Canonical assessment.tests.* scalar keys. Kept as a hand-curated whitelist
# local to this test — the vocabulary doc does not enumerate assessment.tests
# keys in a machine-readable form. If you add a new key, add it here too.
_CANONICAL_ASSESSMENT_TEST_KEYS: Set[str] = {
    "max_hang_20mm_7s_total_kg",
    "max_hang_20mm_5s_total_kg",
    "repeater_7_3_max_sets_20mm",
    "max_hang_duration_20mm_seconds",
    "l_sit_hold_seconds",
    "hip_flexibility_cm",
    "weighted_pullup_2rm_total_kg",
    "weighted_pullup_1rm_estimated_kg",
    "weighted_pullup_1rm_total_kg",
    "pulling_ratio_pct",
    "max_pullups_bw",
    # per-hand keys (lp_duration_test_right_seconds, lp_max_lift_5s_left_kg, …)
    # are format-string generated and covered by _TEST_EXERCISE_PER_HAND.
}


def _collect_exercise_id_branches() -> Set[str]:
    """Walk the AST of _update_test_from_log and collect every exercise_id literal."""
    source = inspect.getsource(_update_test_from_log)
    tree = ast.parse(source)
    branches: Set[str] = set()

    class _Visitor(ast.NodeVisitor):
        def visit_Compare(self, node: ast.Compare) -> None:
            if (
                isinstance(node.left, ast.Name)
                and node.left.id == "exercise_id"
                and len(node.comparators) == 1
            ):
                op = node.ops[0]
                comparator = node.comparators[0]
                if isinstance(op, ast.Eq) and isinstance(comparator, ast.Constant):
                    if isinstance(comparator.value, str):
                        branches.add(comparator.value)
                elif isinstance(op, ast.In) and isinstance(comparator, ast.Tuple):
                    for elt in comparator.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            branches.add(elt.value)
            self.generic_visit(node)

    _Visitor().visit(tree)
    return branches


class TestScalarRegistryIntegrity:
    def test_registry_covers_every_branch_in_update_test_from_log(self) -> None:
        """Every exercise_id branch must be in _TEST_EXERCISE_SCALARS or _PER_HAND."""
        branches = _collect_exercise_id_branches()
        covered = set(_TEST_EXERCISE_SCALARS.keys()) | set(_TEST_EXERCISE_PER_HAND)
        missing = branches - covered
        assert not missing, (
            f"exercise_id branches missing from scalar registry: {sorted(missing)}. "
            f"Add to _TEST_EXERCISE_SCALARS (if static keys) or "
            f"_TEST_EXERCISE_PER_HAND (if per-hand dynamic keys)."
        )

    def test_registry_has_no_stale_entries(self) -> None:
        """Every entry in the registry must correspond to an active branch."""
        branches = _collect_exercise_id_branches()
        covered = set(_TEST_EXERCISE_SCALARS.keys()) | set(_TEST_EXERCISE_PER_HAND)
        stale = covered - branches
        assert not stale, (
            f"Registry entries without a matching branch in _update_test_from_log: "
            f"{sorted(stale)}. Remove or add the missing branch."
        )

    def test_every_mapped_key_is_canonical(self) -> None:
        """Every value in _TEST_EXERCISE_SCALARS must be a canonical tests.* key."""
        mapped: Set[str] = set()
        for keys in _TEST_EXERCISE_SCALARS.values():
            mapped.update(keys)
        unknown = mapped - _CANONICAL_ASSESSMENT_TEST_KEYS
        assert not unknown, (
            f"Unknown assessment.tests.* keys in _TEST_EXERCISE_SCALARS: "
            f"{sorted(unknown)}. Update _CANONICAL_ASSESSMENT_TEST_KEYS in the test "
            f"(and vocabulary_v1.md §2.10) if this is a genuine new key."
        )

    def test_per_hand_entries_have_no_static_scalars(self) -> None:
        """A branch is either static (in _SCALARS) or per-hand (in _PER_HAND), not both."""
        overlap = set(_TEST_EXERCISE_SCALARS.keys()) & set(_TEST_EXERCISE_PER_HAND)
        assert not overlap, (
            f"exercise_id in both _SCALARS and _PER_HAND: {sorted(overlap)}"
        )


def _fake_test_log(exercise_id: str, extra: dict | None = None) -> dict:
    """Build a minimal log entry that looks like a completed test session."""
    feedback = {"exercise_id": exercise_id}
    if extra:
        feedback.update(extra)
    return {
        "date": "2026-04-20",
        "session_id": f"test_{exercise_id}",
        "planned": [{"session_id": f"test_{exercise_id}", "tags": {"test": True}}],
        "actual": {"exercise_feedback_v1": [feedback]},
    }


class TestRegressionMarksMeasured:
    """Post-refactor, every branch must still populate tests_source correctly."""

    def test_max_hang_7s_still_marks_both_keys(self) -> None:
        updated: dict = {"assessment": {}}
        log = _fake_test_log("max_hang_7s", {"used_total_load_kg": 100.0})
        _update_test_from_log(log, updated, bodyweight=70.0)
        src = updated["assessment"]["tests_source"]
        assert src["max_hang_20mm_7s_total_kg"] == "measured"
        assert src["max_hang_20mm_5s_total_kg"] == "measured"

    def test_max_hang_5s_still_marks_both_keys(self) -> None:
        updated: dict = {"assessment": {}}
        log = _fake_test_log("max_hang_5s", {"used_total_load_kg": 90.0})
        _update_test_from_log(log, updated, bodyweight=70.0)
        src = updated["assessment"]["tests_source"]
        assert src["max_hang_20mm_5s_total_kg"] == "measured"
        assert src["max_hang_20mm_7s_total_kg"] == "measured"

    def test_weighted_pullup_still_marks_all_four(self) -> None:
        updated: dict = {"assessment": {}}
        log = _fake_test_log("weighted_pullup", {"used_total_load_kg": 90.0})
        _update_test_from_log(log, updated, bodyweight=70.0)
        src = updated["assessment"]["tests_source"]
        for key in (
            "weighted_pullup_2rm_total_kg",
            "weighted_pullup_1rm_estimated_kg",
            "pulling_ratio_pct",
            "weighted_pullup_1rm_total_kg",
        ):
            assert src[key] == "measured", f"missing {key}"

    def test_repeater_still_marks_key(self) -> None:
        updated: dict = {"assessment": {}}
        log = _fake_test_log("repeater_hang_7_3", {"completed_reps": 8})
        _update_test_from_log(log, updated, bodyweight=70.0)
        assert updated["assessment"]["tests_source"]["repeater_7_3_max_sets_20mm"] == "measured"

    def test_l_sit_hold_still_marks_key(self) -> None:
        updated: dict = {"assessment": {}}
        log = _fake_test_log("test_l_sit_hold", {"l_sit_hold_seconds": 30})
        _update_test_from_log(log, updated, bodyweight=70.0)
        assert updated["assessment"]["tests_source"]["l_sit_hold_seconds"] == "measured"

    def test_per_hand_branch_still_marks_dynamic_key(self) -> None:
        """Regression: lp_duration_test marks the right per-hand key inline."""
        updated: dict = {"assessment": {}}
        log = _fake_test_log(
            "lp_duration_test",
            {"lp_duration_test_seconds": 12.5, "hand": "right"},
        )
        _update_test_from_log(log, updated, bodyweight=70.0)
        src = updated["assessment"]["tests_source"]
        assert src["lp_duration_test_right_seconds"] == "measured"
        assert "lp_duration_test_left_seconds" not in src
