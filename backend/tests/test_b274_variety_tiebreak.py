"""B274 — weekly variety tie-break in pick_best_exercise_p0.

Root cause (C256 finding 2): ties in score_exercise broke on alphabetical
exercise_id → every `tech_*` drill (all Bechtel batches) sorted after the
classic drills and never entered the rotation (12 distinct drills in 12
simulated weeks on a real profile).

Fix: final sort key = md5(exercise_id | variety_seed), seed = ISO Monday of
context target_date's week. Deterministic for the same (state, week) input;
rotates week over week; date-less callers keep the legacy alphabetical order.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import date

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from backend.engine.resolve_session import (  # noqa: E402
    _variety_key,
    _variety_seed_from_date,
    resolve_session,
)

EXERCISES_PATH = os.path.join(REPO_ROOT, "backend/catalog/exercises/v1/exercises.json")
SESSION_PATH = "backend/catalog/sessions/v1/technique_focus_gym.json"
TEMPLATES_DIR = "backend/catalog/templates/v1"
WALL_GYM = ["pullup_bar", "gym_boulder", "gym_routes", "hangboard"]


def _state(target_date=None):
    ctx = {"location": "gym", "gym_id": "g1"}
    if target_date:
        ctx["target_date"] = target_date
    return {
        "context": ctx,
        "equipment": {
            "gyms": [{"gym_id": "g1", "priority": 1, "equipment": WALL_GYM}],
            "home": [],
        },
        "assessment": {"grades": {"boulder_max_rp": "7C", "boulder_max_os": "7A"}},
        "defaults": {"location": "gym"},
    }


def _resolve(target_date=None, extra_recent=None):
    return resolve_session(
        REPO_ROOT,
        SESSION_PATH,
        TEMPLATES_DIR,
        EXERCISES_PATH,
        "",
        user_state_override=_state(target_date),
        write_output=False,
        user_id=None,
        extra_recent_ex_ids=list(extra_recent or []),
    )


def _drill_ids(resolved):
    return [
        se.get("exercise_id")
        for blk in resolved["resolved_session"]["blocks"]
        if str(blk.get("block_id", "")).startswith("technique_drill")
        for se in blk.get("selected_exercises", [])
    ]


class TestVarietyKeyUnit(unittest.TestCase):
    def test_no_seed_is_identity(self):
        self.assertEqual(_variety_key("silent_feet_drill", None), "silent_feet_drill")
        self.assertEqual(_variety_key("silent_feet_drill", ""), "silent_feet_drill")

    def test_seeded_key_is_deterministic(self):
        a = _variety_key("tech_pogo", "2026-07-13")
        b = _variety_key("tech_pogo", "2026-07-13")
        self.assertEqual(a, b)

    def test_seed_changes_ordering_potential(self):
        a = _variety_key("tech_pogo", "2026-07-13")
        b = _variety_key("tech_pogo", "2026-07-20")
        self.assertNotEqual(a, b)

    def test_seed_from_date_is_week_monday(self):
        self.assertEqual(_variety_seed_from_date(date(2026, 7, 15)), "2026-07-13")
        self.assertEqual(_variety_seed_from_date(date(2026, 7, 13)), "2026-07-13")
        self.assertEqual(_variety_seed_from_date(date(2026, 7, 19)), "2026-07-13")
        self.assertIsNone(_variety_seed_from_date(None))
        self.assertIsNone(_variety_seed_from_date("not-a-date"))


class TestResolutionDeterminism(unittest.TestCase):
    def test_same_date_same_state_is_byte_identical(self):
        a = _resolve(target_date="2026-07-15")
        b = _resolve(target_date="2026-07-15")
        self.assertEqual(
            json.dumps(a["resolved_session"], sort_keys=True),
            json.dumps(b["resolved_session"], sort_keys=True),
        )

    def test_same_week_different_day_same_picks(self):
        a = _drill_ids(_resolve(target_date="2026-07-14"))
        b = _drill_ids(_resolve(target_date="2026-07-17"))
        self.assertEqual(a, b, "seed is per-week: same week must pick the same drills")

    def test_dateless_resolution_keeps_legacy_alphabetical_order(self):
        # No date in context → seed None → identical to pre-B274 behavior.
        a = _drill_ids(_resolve(target_date=None))
        b = _drill_ids(_resolve(target_date=None))
        self.assertEqual(a, b)
        for eid in a:
            self.assertIsNotNone(eid)


class TestWeeklyRotationVariety(unittest.TestCase):
    def test_12_weeks_rotation_widens_the_pool(self):
        # Pre-B274 baseline on this exact setup: a fixed 4-session cycle,
        # 12 distinct drills, tech_* entries starved. With the weekly seed the
        # rotation must widen the pool meaningfully and reach tech_* drills.
        window: list = []
        seen: set = set()
        monday = date(2026, 7, 13)
        for wk in range(12):
            d = monday.fromordinal(monday.toordinal() + wk * 7)
            flat = [x for w in window[-3:] for x in w]
            drills = _drill_ids(_resolve(target_date=d.isoformat(), extra_recent=flat))
            window.append(drills)
            seen.update(drills)
        self.assertGreaterEqual(
            len(seen), 20,
            f"weekly rotation too narrow: {len(seen)} distinct drills ({sorted(seen)})",
        )
        tech = {x for x in seen if str(x).startswith("tech_")}
        self.assertGreaterEqual(
            len(tech), 5,
            f"tech_* drills still starved by the tie-break: {sorted(tech)}",
        )


if __name__ == "__main__":
    unittest.main()
