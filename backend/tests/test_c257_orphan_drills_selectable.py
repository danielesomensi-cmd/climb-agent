"""C257 — the 3 C256 selector-orphan drills become selectable.

`tech_green_light_red_light` (climbing_intervals), `tech_pogo` and
`tech_throwing_the_shoe` (explosive_touch) carry role=technique, but every
block filtering those patterns required role=main → no session could ever
select them. C257 extends the three technique_drill_* blocks of
technique_focus_gym to accept the two extra patterns (role=technique kept,
so exactly these 3 exercises join the pool — locked by the invariant below).
"""
from __future__ import annotations

import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from backend.engine.resolve_session import resolve_session  # noqa: E402

EXERCISES_PATH = os.path.join(REPO_ROOT, "backend/catalog/exercises/v1/exercises.json")
SESSION_PATH = "backend/catalog/sessions/v1/technique_focus_gym.json"
TEMPLATES_DIR = "backend/catalog/templates/v1"

ORPHANS = {"tech_green_light_red_light", "tech_pogo", "tech_throwing_the_shoe"}
WALL_GYM = ["pullup_bar", "gym_boulder", "gym_routes", "hangboard"]


def _resolve(extra_recent):
    state = {
        "context": {"location": "gym", "gym_id": "g1"},
        "equipment": {
            "gyms": [{"gym_id": "g1", "priority": 1, "equipment": WALL_GYM}],
            "home": [],
        },
        "assessment": {"grades": {"boulder_max_rp": "7C", "boulder_max_os": "7A"}},
        "defaults": {"location": "gym"},
    }
    return resolve_session(
        REPO_ROOT,
        SESSION_PATH,
        TEMPLATES_DIR,
        EXERCISES_PATH,
        "",
        user_state_override=state,
        write_output=False,
        user_id=None,
        extra_recent_ex_ids=list(extra_recent),
    )


def _drill_ids(resolved):
    return [
        se.get("exercise_id")
        for blk in resolved["resolved_session"]["blocks"]
        if str(blk.get("block_id", "")).startswith("technique_drill")
        for se in blk.get("selected_exercises", [])
    ]


class TestC257OrphanDrillsSelectable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(EXERCISES_PATH, "r", encoding="utf-8") as f:
            cls.catalog = json.load(f)["exercises"]

    def test_session_blocks_accept_the_extra_patterns(self):
        with open(os.path.join(REPO_ROOT, SESSION_PATH), encoding="utf-8") as f:
            session = json.load(f)
        blocks = [
            m for m in session["modules"]
            if str(m.get("block_id", "")).startswith("technique_drill")
        ]
        self.assertEqual(len(blocks), 3)
        for m in blocks:
            pat = m["selection"]["primary"]["filters"]["pattern"]
            self.assertEqual(
                pat, ["technique_drill", "climbing_intervals", "explosive_touch"],
                f"{m['block_id']} pattern filter not extended",
            )

    def test_pattern_extension_admits_exactly_the_three_orphans(self):
        # Guard: role=technique + the two extra patterns must match ONLY the
        # 3 ex-orphans — if a future exercise joins this set unintentionally,
        # this test surfaces it for review.
        extra = {
            e["id"]
            for e in self.catalog
            if "technique" in (e.get("role") or [])
            and e.get("pattern") in ("climbing_intervals", "explosive_touch")
        }
        self.assertEqual(extra, ORPHANS)

    def test_orphans_get_selected_under_recency_pressure(self):
        # Mark every pattern=technique_drill exercise as recently used: the
        # only unpenalized candidates left in the pool are the 3 ex-orphans.
        classic = [
            e["id"] for e in self.catalog
            if e.get("pattern") == "technique_drill"
            and "technique" in (e.get("role") or [])
        ]
        resolved = _resolve(classic)
        self.assertEqual(resolved.get("resolution_status"), "success")
        picked = set(_drill_ids(resolved))
        self.assertTrue(
            picked & ORPHANS,
            f"expected at least one ex-orphan drill selected, got {sorted(picked)}",
        )


if __name__ == "__main__":
    unittest.main()
