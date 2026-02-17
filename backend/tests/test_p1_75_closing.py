"""Tests for Phase 1.75 closure items."""

import unittest

from backend.engine.resolve_session import resolve_session


class TestResolvedSessionLoadScore(unittest.TestCase):
    """B4: resolved session output must have session_load_score from fatigue_cost."""

    def _resolve(self, session_id):
        return resolve_session(
            repo_root=".",
            session_path=f"backend/catalog/sessions/v1/{session_id}.json",
            templates_dir="backend/catalog/templates/v1",
            exercises_path="backend/catalog/exercises/v1/exercises.json",
            out_path="",
            write_output=False,
        )

    def test_resolved_session_has_load_score(self):
        """Resolved session must have session_load_score field."""
        result = self._resolve("strength_long")
        self.assertIn("session_load_score", result)
        self.assertIsInstance(result["session_load_score"], int)
        self.assertGreater(result["session_load_score"], 0,
                           "Load score should be positive for a real session")

    def test_load_score_varies_by_session(self):
        """Different sessions should have different load scores."""
        strength = self._resolve("strength_long")
        recovery = self._resolve("regeneration_easy")
        self.assertGreater(strength["session_load_score"], recovery["session_load_score"],
                           "Strength session should have higher load than recovery")

    def test_test_session_has_load_score(self):
        """Test sessions must also have session_load_score."""
        result = self._resolve("test_max_hang_5s")
        self.assertIn("session_load_score", result)
        self.assertIsInstance(result["session_load_score"], int)


if __name__ == "__main__":
    unittest.main()
