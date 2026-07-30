"""B312 — the load a session credits must drop when exercises are skipped.

Before B312 `session_load_score` (prescribed, from fatigue_cost) was the only
number in play: skipping six exercises out of eight and marking the session done
still credited the full load to the weekly report and the monthly heatmap.

Two things are covered here:
  1. `compute_actual_load_score` — derives the earned load from the per-exercise
     `completed` flags the guided player already sends.
  2. `effective_session_load` — the single reader for the report consumers. It
     also fixes a latent bug: the prescribed score lives on the *resolved*
     payload (`slot["resolved"]["session_load_score"]`), not on the slot, so the
     old inline lookups always fell through to `estimated_load_score`.
"""

import os
import unittest

from backend.engine.load_score import (
    LOAD_CAP,
    compute_actual_load_score,
    effective_session_load,
    fatigue_map_from_catalog,
    load_score_from_ids,
)
from backend.engine.report_engine import _build_load, _heatmap_day_cell
from backend.engine.resolve_session import resolve_session

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Deliberately coarse numbers so the arithmetic stays checkable by hand.
FATIGUE = {"a": 10, "b": 10, "c": 4, "instr": 2}


def _items(*pairs):
    """Build exercise_feedback_v1 items: _items(("a", True), ("b", False))."""
    return [{"exercise_id": ex_id, "completed": done} for ex_id, done in pairs]


def _instances(*ex_ids):
    return [{"exercise_id": ex_id} for ex_id in ex_ids]


class TestComputeActualLoadScore(unittest.TestCase):
    def test_skipping_exercises_lowers_the_load(self):
        """The headline invariant: fewer exercises done → strictly less load."""
        instances = _instances("a", "b", "c")
        full = compute_actual_load_score(
            _items(("a", True), ("b", True), ("c", True)), instances, FATIGUE
        )
        partial = compute_actual_load_score(
            _items(("a", True), ("b", False), ("c", False)), instances, FATIGUE
        )
        self.assertEqual(full, round(24 * 1.5))
        self.assertEqual(partial, round(10 * 1.5))
        self.assertLess(partial, full)

    def test_full_completion_equals_prescribed_score(self):
        """A fully done session must land exactly on its prescribed load."""
        instances = _instances("a", "b", "c")
        prescribed = load_score_from_ids([i["exercise_id"] for i in instances], FATIGUE)
        actual = compute_actual_load_score(
            _items(("a", True), ("b", True), ("c", True)), instances, FATIGUE
        )
        self.assertEqual(actual, prescribed)

    def test_everything_skipped_is_zero_not_none(self):
        """Zero is a real answer — it must not be confused with "no signal"."""
        actual = compute_actual_load_score(
            _items(("a", False), ("b", False)), _instances("a", "b"), FATIGUE
        )
        self.assertEqual(actual, 0)

    def test_unilateral_hands_count_once(self):
        """Unilateral exercises send two items sharing one exercise_id."""
        actual = compute_actual_load_score(
            [
                {"exercise_id": "a", "completed": True, "hand": "right"},
                {"exercise_id": "a", "completed": True, "hand": "left"},
            ],
            _instances("a"),
            FATIGUE,
        )
        self.assertEqual(actual, round(10 * 1.5))

    def test_unilateral_one_hand_done_counts_as_done(self):
        actual = compute_actual_load_score(
            [
                {"exercise_id": "a", "completed": False, "hand": "right"},
                {"exercise_id": "a", "completed": True, "hand": "left"},
            ],
            _instances("a"),
            FATIGUE,
        )
        self.assertEqual(actual, round(10 * 1.5))

    def test_unreported_exercise_counts_as_done(self):
        """Instruction-only steps never reach the payload but do carry fatigue.

        Conservative by design: load is only ever subtracted on an explicit
        `completed: false`, never on absence.
        """
        actual = compute_actual_load_score(
            _items(("a", True), ("b", True)),
            _instances("a", "b", "instr"),
            FATIGUE,
        )
        self.assertEqual(actual, round(22 * 1.5))

    def test_payload_without_completed_flag_returns_none(self):
        """The /today dialog reports no per-exercise skip signal → keep prescribed."""
        actual = compute_actual_load_score(
            [{"exercise_id": "a", "used_external_load_kg": 20}],
            _instances("a", "b"),
            FATIGUE,
        )
        self.assertIsNone(actual)

    def test_empty_inputs_return_none(self):
        self.assertIsNone(compute_actual_load_score([], _instances("a"), FATIGUE))
        self.assertIsNone(compute_actual_load_score(_items(("a", True)), [], FATIGUE))
        self.assertIsNone(compute_actual_load_score(None, None, FATIGUE))

    def test_cap_still_applies(self):
        heavy = {f"e{i}": 30 for i in range(10)}
        actual = compute_actual_load_score(
            [{"exercise_id": k, "completed": True} for k in heavy],
            _instances(*heavy.keys()),
            heavy,
        )
        self.assertEqual(actual, LOAD_CAP)


class TestEffectiveSessionLoad(unittest.TestCase):
    def test_prefers_actual_over_prescribed(self):
        session = {
            "session_load_actual": 12,
            "resolved": {"session_load_score": 60},
            "estimated_load_score": 65,
        }
        self.assertEqual(effective_session_load(session), 12.0)

    def test_zero_actual_is_not_overridden_by_prescribed(self):
        session = {
            "session_load_actual": 0,
            "resolved": {"session_load_score": 60},
            "estimated_load_score": 65,
        }
        self.assertEqual(effective_session_load(session), 0.0)

    def test_reads_prescribed_score_from_resolved_payload(self):
        """Pre-B312 this fell through to estimated_load_score (65)."""
        session = {
            "resolved": {"session_load_score": 60},
            "estimated_load_score": 65,
        }
        self.assertEqual(effective_session_load(session), 60.0)

    def test_prescribed_zero_still_falls_back_to_estimated(self):
        """D151 semantics preserved: a prescribed 0 means "resolver produced
        nothing", not "no load" — only an *actual* 0 is a real zero."""
        session = {
            "resolved": {"session_load_score": 0},
            "estimated_load_score": 40,
        }
        self.assertEqual(effective_session_load(session), 40.0)

    def test_falls_back_to_estimated_when_unresolved(self):
        self.assertEqual(effective_session_load({"estimated_load_score": 40}), 40.0)

    def test_no_load_information_is_zero(self):
        self.assertEqual(effective_session_load({}), 0.0)
        self.assertEqual(effective_session_load(None), 0.0)

    def test_tolerates_non_dict_resolved(self):
        self.assertEqual(
            effective_session_load({"resolved": None, "estimated_load_score": 30}), 30.0
        )


class TestReportReflectsSkippedExercises(unittest.TestCase):
    """The user-visible payoff: report + heatmap must show the lower load."""

    def _week_plan(self, session_extra):
        session = {
            "session_id": "strength_long",
            "status": "done",
            "estimated_load_score": 65,
            "resolved": {"session_load_score": 60},
        }
        session.update(session_extra)
        return {
            "start_date": "2026-07-27",
            "weekly_load_summary": {"planned_load": 120},
            "weeks": [{"days": [{"date": "2026-07-27", "sessions": [session]}]}],
        }

    def test_weekly_report_load_drops_when_exercises_skipped(self):
        full = _build_load(self._week_plan({}), [], [], [], "2026-07-27")
        partial = _build_load(
            self._week_plan({"session_load_actual": 15}), [], [], [], "2026-07-27"
        )
        self.assertEqual(full["actual_total"], 60)
        self.assertEqual(partial["actual_total"], 15)
        self.assertLess(partial["load_ratio"], full["load_ratio"])

    def test_heatmap_load_drops_when_exercises_skipped(self):
        def _cell(extra):
            session = {"status": "done", "estimated_load_score": 65,
                       "resolved": {"session_load_score": 60}}
            session.update(extra)
            return _heatmap_day_cell(
                {"sessions": [session]}, "2026-07-27", "2026-07-30", 0.0, None
            )

        self.assertLess(_cell({"session_load_actual": 15})["load"],
                        _cell({})["load"])

    def test_day_still_counts_as_done_with_zero_actual_load(self):
        """Showing up and doing nothing still marks the day done (rest-positive)."""
        cell = _heatmap_day_cell(
            {"sessions": [{"status": "done", "session_load_actual": 0,
                           "resolved": {"session_load_score": 60}}]},
            "2026-07-27", "2026-07-30", 0.0, None,
        )
        self.assertEqual(cell["status"], "done")
        self.assertEqual(cell["load"], 0)


class TestRealSessionEndToEnd(unittest.TestCase):
    """Same check against a real catalog session, not hand-built fatigue values."""

    def test_skipping_half_a_real_session_lowers_its_load(self):
        resolved = resolve_session(
            repo_root=REPO_ROOT,
            session_path="backend/catalog/sessions/v1/strength_long.json",
            templates_dir="backend/catalog/templates/v1",
            exercises_path="backend/catalog/exercises/v1/exercises.json",
            out_path="",
            write_output=False,
        )
        instances = resolved["resolved_session"]["exercise_instances"]
        self.assertGreater(len(instances), 2, "need a few exercises to skip half")

        import json

        with open(
            os.path.join(REPO_ROOT, "backend/catalog/exercises/v1/exercises.json"),
            encoding="utf-8",
        ) as fh:
            catalog = json.load(fh)
        fatigue = fatigue_map_from_catalog(
            catalog if isinstance(catalog, list) else catalog.get("exercises", [])
        )

        half = len(instances) // 2
        items = [
            {"exercise_id": inst["exercise_id"], "completed": idx < half}
            for idx, inst in enumerate(instances)
        ]
        actual = compute_actual_load_score(items, instances, fatigue)

        self.assertIsNotNone(actual)
        self.assertLess(
            actual,
            resolved["session_load_score"],
            "half a session must credit less load than the whole prescription",
        )

        all_done = compute_actual_load_score(
            [{"exercise_id": i["exercise_id"], "completed": True} for i in instances],
            instances,
            fatigue,
        )
        self.assertEqual(all_done, resolved["session_load_score"])


if __name__ == "__main__":
    unittest.main()
