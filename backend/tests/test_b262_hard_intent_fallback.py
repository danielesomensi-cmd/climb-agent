"""B262 — Intent "hard" fallback chain must have a non-climbing alternative.

Source: D248 audit, out-of-scope follow-up (flagged in B261). The intent "hard"
fallback chain was [strength_long, power_contact_gym, boulder_circuit_gym] — all
requiring hangboard/gym_boulder. At a commercial/fitness gym with no climbing
equipment, no fallback was compatible, so the resolver kept `strength_long`
(hangboard) — a session the user cannot perform there.

Fix: chain is now [strength_long, power_contact_gym, pulling_strength_gym], so a
no-wall gym degrades to a hard NON-climbing pulling-strength session. The override
also surfaces an `equipment_downgrade` / `no_compatible_hard_session` adaptation
so the UI can explain the change.
"""
from __future__ import annotations

import copy
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from backend.engine.replanner_v1 import (  # noqa: E402
    _resolve_intent_for_equipment,
    apply_day_override,
)
from backend.engine.equipment_utils import expand_equipment  # noqa: E402

FITNESS = {"pullup_bar", "dumbbell"}
BOULDERING = set(expand_equipment(["gym_boulder", "pullup_bar"]))
FULL_CLIMBING = set(expand_equipment(["hangboard", "gym_boulder", "pullup_bar"]))
BARE = {"dumbbell", "bench"}


def _plan():
    return {
        "start_date": "2026-06-15",
        "profile_snapshot": {"phase_id": "base"},
        "weeks": [{"days": [
            {"date": "2026-06-15", "sessions": []},
            {"date": "2026-06-16", "sessions": []},
            {"date": "2026-06-17", "sessions": []},
        ]}],
    }


def _override(gym_equipment, intent="hard", plan=None, target="2026-06-15"):
    gyms = [{"gym_id": "g", "priority": 1, "equipment": list(gym_equipment)}]
    return apply_day_override(
        plan or _plan(), intent=intent, location="gym",
        reference_date="2026-06-15", target_date=target, slot="evening",
        gym_id="g", gyms=gyms,
    )


def _session_id(updated, target="2026-06-15"):
    day = next(d for d in updated["weeks"][0]["days"] if d["date"] == target)
    return day["sessions"][0]["session_id"]


def _notices(updated):
    return [a for a in updated.get("adaptations", [])
            if a.get("type") in ("equipment_downgrade", "no_compatible_hard_session")]


class TestB262ChainResolution(unittest.TestCase):
    def test_fitness_gym_degrades_to_pulling_strength(self):
        self.assertEqual(_resolve_intent_for_equipment("hard", FITNESS), "pulling_strength_gym")

    def test_bouldering_gym_uses_power_contact(self):
        self.assertEqual(_resolve_intent_for_equipment("hard", BOULDERING), "power_contact_gym")

    def test_full_climbing_keeps_strength_long(self):
        self.assertEqual(_resolve_intent_for_equipment("hard", FULL_CLIMBING), "strength_long")

    def test_bare_gym_terminal_keeps_primary(self):
        # No compatible hard session at all → primary kept (terminal).
        self.assertEqual(_resolve_intent_for_equipment("hard", BARE), "strength_long")

    def test_deterministic(self):
        a = _resolve_intent_for_equipment("hard", FITNESS)
        b = _resolve_intent_for_equipment("hard", FITNESS)
        self.assertEqual(a, b)

    def test_no_dropped_session_in_chain_is_picked(self):
        # boulder_circuit_gym (hard=False) was removed — it must never be chosen
        # for intent "hard".
        for eq in (FITNESS, BOULDERING, FULL_CLIMBING, BARE):
            self.assertNotEqual(_resolve_intent_for_equipment("hard", eq), "boulder_circuit_gym")


class TestB262OverrideNotices(unittest.TestCase):
    def test_fitness_emits_equipment_downgrade(self):
        up = _override(FITNESS)
        self.assertEqual(_session_id(up), "pulling_strength_gym")
        notices = _notices(up)
        self.assertEqual(len(notices), 1)
        n = notices[0]
        self.assertEqual(n["type"], "equipment_downgrade")
        self.assertEqual(n["intent"], "hard")
        self.assertEqual(n["requested_session"], "strength_long")
        self.assertEqual(n["resolved_session"], "pulling_strength_gym")

    def test_full_climbing_emits_no_notice(self):
        up = _override(FULL_CLIMBING)
        self.assertEqual(_session_id(up), "strength_long")
        self.assertEqual(_notices(up), [])

    def test_bare_gym_emits_no_compatible_hard_session(self):
        up = _override(BARE)
        self.assertEqual(_session_id(up), "strength_long")
        notices = _notices(up)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["type"], "no_compatible_hard_session")
        self.assertEqual(notices[0]["session"], "strength_long")


class TestB262Immutability(unittest.TestCase):
    def test_override_cannot_mutate_completed_session(self):
        plan = _plan()
        plan["weeks"][0]["days"][0]["sessions"] = [{
            "slot": "evening", "session_id": "strength_long", "status": "done",
        }]
        before = copy.deepcopy(plan["weeks"][0]["days"][0]["sessions"])
        with self.assertRaises(ValueError):
            _override(FITNESS, plan=plan)
        # plan dict is deep-copied inside apply_day_override; the original is untouched
        self.assertEqual(plan["weeks"][0]["days"][0]["sessions"], before)


class TestB262NoRegressionOtherIntents(unittest.TestCase):
    def test_other_intent_fallback_still_works(self):
        # "power" intent still resolves and is unaffected by the "hard" change.
        sid = _resolve_intent_for_equipment("power", BOULDERING)
        self.assertEqual(sid, "power_contact_gym")


if __name__ == "__main__":
    unittest.main()
