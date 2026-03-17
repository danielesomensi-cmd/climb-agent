"""B119: start_date must always be a Monday — invariant tests."""

from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import date, datetime, timedelta

from backend.api.deps import ensure_monday, this_monday
from backend.engine.macrocycle_v1 import generate_macrocycle


class TestEnsureMonday(unittest.TestCase):
    """Unit tests for ensure_monday()."""

    def test_monday_returns_same(self):
        self.assertEqual(ensure_monday("2026-03-09"), "2026-03-09")  # Monday

    def test_tuesday_returns_previous_monday(self):
        self.assertEqual(ensure_monday("2026-03-10"), "2026-03-09")

    def test_wednesday(self):
        self.assertEqual(ensure_monday("2026-03-11"), "2026-03-09")

    def test_thursday(self):
        self.assertEqual(ensure_monday("2026-03-12"), "2026-03-09")

    def test_friday(self):
        self.assertEqual(ensure_monday("2026-03-13"), "2026-03-09")

    def test_saturday(self):
        self.assertEqual(ensure_monday("2026-03-14"), "2026-03-09")

    def test_sunday(self):
        self.assertEqual(ensure_monday("2026-03-15"), "2026-03-09")

    def test_another_week(self):
        # 2026-02-24 is Tuesday → Monday 2026-02-23
        self.assertEqual(ensure_monday("2026-02-24"), "2026-02-23")


class TestGenerateMacrocycleMonday(unittest.TestCase):
    """generate_macrocycle() must always produce a Monday start_date."""

    def _base_state(self) -> dict:
        return {
            "goal": {
                "goal_type": "grade_push",
                "discipline": "lead",
                "target_grade": "7a",
                "current_grade": "6b+",
            },
            "assessment": {
                "profile": {
                    "finger_strength": 50,
                    "pulling_strength": 50,
                    "power_endurance": 50,
                    "technique": 50,
                    "endurance": 50,
                }
            },
            "trips": [],
        }

    def test_full_regen_monday_input(self):
        state = self._base_state()
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, "2026-03-02", 12,
        )
        self.assertEqual(mc["start_date"], "2026-03-02")
        d = datetime.strptime(mc["start_date"], "%Y-%m-%d").date()
        self.assertEqual(d.weekday(), 0, "start_date must be Monday")

    def test_full_regen_non_monday_auto_corrected(self):
        """Passing a non-Monday start_date gets corrected to previous Monday."""
        state = self._base_state()
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, "2026-03-05", 12,  # Thursday
        )
        self.assertEqual(mc["start_date"], "2026-03-02")
        d = datetime.strptime(mc["start_date"], "%Y-%m-%d").date()
        self.assertEqual(d.weekday(), 0, "start_date must be Monday")

    def test_incremental_regen_preserves_start_date(self):
        """from_phase regen must keep the original start_date, not recalculate."""
        state = self._base_state()
        original_start = "2026-02-23"  # Monday
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, original_start, 12,
        )
        state["macrocycle"] = mc
        new_mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, original_start, 12,
            from_phase="strength_power",
        )
        self.assertEqual(new_mc["start_date"], original_start)


class TestStatePutAutoCorrect(unittest.TestCase):
    """PUT /api/state auto-corrects macrocycle.start_date to Monday."""

    def test_non_monday_corrected(self):
        from fastapi.testclient import TestClient
        from backend.api.main import app

        client = TestClient(app)
        # First ensure there's a macrocycle in state
        state = client.get("/api/state").json()
        if not state.get("macrocycle"):
            self.skipTest("No macrocycle in local state")

        # Patch with a Tuesday
        r = client.put("/api/state", json={"macrocycle": {"start_date": "2026-03-10"}})
        self.assertEqual(r.status_code, 200)
        mc = r.json().get("macrocycle", {})
        self.assertEqual(mc.get("start_date"), "2026-03-09",
                         "Non-Monday should be auto-corrected to previous Monday")

        # Restore original
        client.put("/api/state", json={"macrocycle": {"start_date": state["macrocycle"]["start_date"]}})


class TestMacrocycleEndpointMonday(unittest.TestCase):
    """POST /api/macrocycle/generate enforces Monday on explicit start_date."""

    def test_explicit_non_monday_corrected(self):
        from fastapi.testclient import TestClient
        from backend.api.main import app

        client = TestClient(app)
        state = client.get("/api/state").json()
        if not state.get("goal") or not (state.get("assessment") or {}).get("profile"):
            self.skipTest("No goal/assessment in local state")

        r = client.post("/api/macrocycle/generate", json={
            "start_date": "2026-03-05",  # Thursday
            "total_weeks": 12,
        })
        self.assertEqual(r.status_code, 200)
        mc = r.json()["macrocycle"]
        self.assertEqual(mc["start_date"], "2026-03-02",
                         "Thursday should be corrected to Monday")

        # Restore
        client.put("/api/state", json={"macrocycle": state.get("macrocycle")})


class TestEquipmentRegenPreservesMonday(unittest.TestCase):
    """Equipment change → incremental regen → start_date still a Monday."""

    def test_equipment_regen_monday_preserved(self):
        state = {
            "goal": {
                "goal_type": "grade_push",
                "discipline": "lead",
                "target_grade": "7a",
                "current_grade": "6b+",
            },
            "assessment": {
                "profile": {
                    "finger_strength": 50,
                    "pulling_strength": 50,
                    "power_endurance": 50,
                    "technique": 50,
                    "endurance": 50,
                }
            },
            "trips": [],
        }
        original_start = "2026-02-23"  # Monday
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, original_start, 12,
        )
        state["macrocycle"] = mc

        # Simulate equipment change → incremental regen from current phase
        new_mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, original_start, 12,
            from_phase="base",
        )
        self.assertEqual(new_mc["start_date"], original_start)
        d = datetime.strptime(new_mc["start_date"], "%Y-%m-%d").date()
        self.assertEqual(d.weekday(), 0)


class TestDangerZoneFullRestart(unittest.TestCase):
    """Danger Zone full restart → new start_date is a Monday."""

    def test_full_restart_is_monday(self):
        state = {
            "goal": {
                "goal_type": "grade_push",
                "discipline": "lead",
                "target_grade": "7a",
                "current_grade": "6b+",
            },
            "assessment": {
                "profile": {
                    "finger_strength": 50,
                    "pulling_strength": 50,
                    "power_endurance": 50,
                    "technique": 50,
                    "endurance": 50,
                }
            },
            "trips": [],
        }
        start = this_monday()
        mc = generate_macrocycle(
            state["goal"], state["assessment"]["profile"],
            state, start, 12,
        )
        d = datetime.strptime(mc["start_date"], "%Y-%m-%d").date()
        self.assertEqual(d.weekday(), 0, "Full restart start_date must be Monday")


if __name__ == "__main__":
    unittest.main()
