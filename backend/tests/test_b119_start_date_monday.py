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
        # Seed a macrocycle so the test runs regardless of test ordering.
        seed_goal = {
            "goal_type": "grade_push",
            "discipline": "lead",
            "target_grade": "7a",
            "current_grade": "6b+",
        }
        seed_profile = {
            "finger_strength": 50, "pulling_strength": 50,
            "power_endurance": 50, "technique": 50, "endurance": 50,
        }
        seed_mc = generate_macrocycle(
            seed_goal, seed_profile, {"trips": []}, "2026-02-23", 12,
        )
        original_state = client.get("/api/state").json()
        client.put("/api/state", json={"macrocycle": seed_mc})

        try:
            # Patch with a Tuesday
            r = client.put("/api/state", json={"macrocycle": {"start_date": "2026-03-10"}})
            self.assertEqual(r.status_code, 200)
            mc = r.json().get("macrocycle", {})
            self.assertEqual(mc.get("start_date"), "2026-03-09",
                             "Non-Monday should be auto-corrected to previous Monday")
        finally:
            # Restore original macrocycle (or None if it was missing)
            client.put("/api/state", json={"macrocycle": original_state.get("macrocycle")})


class TestMacrocycleEndpointMonday(unittest.TestCase):
    """POST /api/macrocycle/generate enforces Monday on explicit start_date."""

    def test_explicit_non_monday_corrected(self):
        from fastapi.testclient import TestClient
        from backend.api.main import app

        client = TestClient(app)
        # Seed goal + assessment.profile so the macrocycle endpoint has inputs
        # regardless of test ordering.
        original_state = client.get("/api/state").json()
        # B347: every date here is derived from today.
        #
        # This test used to hardcode `start_date: "2026-03-05"` and inherit the
        # goal deadline from the shared `backend/data/user_state.json` fixture
        # (PUT deep-merges, so a goal without `deadline` keeps the stored one).
        # That fixture carries `deadline: 2026-09-01`, and the endpoint rejects a
        # goal whose deadline is in the past with a 400 — so the test was always
        # going to start failing on 2026-09-02, and did. The invariant under
        # test (a non-Monday start_date is snapped back to Monday) has nothing
        # to do with the calendar; nothing here should.
        today = date.today()
        # Next Thursday strictly in the future — deliberately NOT a Monday.
        thursday = today + timedelta(days=((3 - today.weekday()) % 7) or 7)
        expected_monday = thursday - timedelta(days=thursday.weekday())
        self.assertEqual(thursday.weekday(), 3, "fixture must be a Thursday")

        client.put("/api/state", json={
            "goal": {
                "goal_type": "grade_push",
                "discipline": "lead",
                "target_grade": "7a",
                "current_grade": "6b+",
                # Explicit and comfortably ahead of the per-discipline minimum,
                # so the test never depends on what the fixture happens to hold.
                "deadline": (today + timedelta(weeks=20)).isoformat(),
            },
            "assessment": {
                "profile": {
                    "finger_strength": 50, "pulling_strength": 50,
                    "power_endurance": 50, "technique": 50, "endurance": 50,
                }
            },
        })

        try:
            r = client.post("/api/macrocycle/generate", json={
                "start_date": thursday.isoformat(),
                "total_weeks": 12,
            })
            self.assertEqual(r.status_code, 200, r.text)
            mc = r.json()["macrocycle"]
            self.assertEqual(mc["start_date"], expected_monday.isoformat(),
                             "Thursday should be corrected to Monday")
        finally:
            # Restore macrocycle (PUT deep-merges so goal/assessment stay as seeded,
            # but the original state is recovered on next test-suite setup since
            # these tests run against the shared local user_state.json.)
            client.put("/api/state", json={"macrocycle": original_state.get("macrocycle")})


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
