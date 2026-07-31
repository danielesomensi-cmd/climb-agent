"""A259 — negative constraints, focus priority, and the LLM session composer.

Three things are pinned here, in order of how badly they burned:

1. **Refusals reach the pool.** "bloccaggi ma niente trazioni" composed a
   session containing `l_sit_pullup`, because nothing in the intent could carry
   a refusal. The subtlety worth a test of its own: excluding pull-ups must NOT
   exclude lock-offs — both are `pull_vertical`, and the naive filter would
   have deleted exactly what was asked for.
2. **A precise focus outranks a named muscle.** A252 let `body_parts` supersede
   `focus`; with `focus=lock_off, body_parts=[core]` that produced a core
   session with zero lock-offs.
3. **The LLM never gets to be trusted.** It picks from an engine-built pool and
   every line is validated before the user sees it.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

from backend.coach import session_composer
from backend.engine.adhoc_builder import (
    ADHOC_EXCLUSIONS,
    EXCLUSION_PREDICATES,
    compose_adhoc_session,
    excluded_ids,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"


def _catalog():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("exercises", [])
    return {str(e["id"]): e for e in items}


def _state():
    """A home setup with a bar — the configuration behind the real report."""
    return {
        "equipment": {"home": ["pullup_bar", "hangboard", "dumbbell", "band"], "home_enabled": True},
        "context": {"location": "home"},
    }


class TestExclusions(unittest.TestCase):
    def setUp(self):
        self.catalog = _catalog()

    def test_no_dead_predicates(self):
        """A label that matches nothing is a promise the engine cannot keep."""
        for label in ADHOC_EXCLUSIONS:
            with self.subTest(label=label):
                self.assertTrue(
                    excluded_ids(self.catalog, [label]),
                    f"exclusion '{label}' matches no exercise in the catalog",
                )

    def test_excluding_pullups_keeps_lock_offs(self):
        """The distinction the whole feature turns on."""
        banned = excluded_ids(self.catalog, ["pullups"])
        self.assertIn("l_sit_pullup", banned)
        self.assertIn("pullup", banned)
        self.assertNotIn("lock_off_isometric", banned)

    def test_every_vertical_pull_is_consciously_classified(self):
        """Guard against the failure the first live test found.

        `frenchies` slipped through a `recency_group == pullup_variants` rule
        because the catalog groups it with lock-offs — it trains lock-offs, but
        every rep opens with a full pull to the chin, and it landed in a session
        that had banned pull-ups. Any new `pull_vertical` exercise must be put on
        one side of the line here, deliberately.
        """
        banned = excluded_ids(self.catalog, ["pullups"])
        # Exercises that are vertical pulls but require NO concentric pull-up.
        no_concentric = {
            "lock_off_isometric",          # hold only, entered by step or jump
            "finger_recruitment_pulls",    # finger recruitment, feet supported
            "pangullich_ladders_easy",     # campus work (covered by 'campus')
            "test_max_pullup_bw",          # test protocol, never pooled
        }
        for eid, ex in self.catalog.items():
            pattern = ex.get("pattern")
            pattern = pattern[0] if isinstance(pattern, list) else pattern
            if pattern != "pull_vertical":
                continue
            with self.subTest(exercise=eid):
                if eid in no_concentric:
                    self.assertNotIn(eid, banned)
                else:
                    self.assertIn(
                        eid, banned,
                        f"{eid} is a vertical pull that survives a 'no pull-ups' "
                        "request — classify it in CONCENTRIC_PULL_* or in this "
                        "test's no_concentric set",
                    )

    def test_excluding_stretching_keeps_dynamic_mobility(self):
        """"No stretching" is not "turn up cold": dynamic flows survive."""
        banned = excluded_ids(self.catalog, ["stretching"])
        self.assertNotIn("dynamic_mobility_flow", banned)
        self.assertIn("cooldown_forearm_wrist_stretch", banned)

    def test_unknown_label_is_ignored_not_fatal(self):
        self.assertEqual(excluded_ids(self.catalog, ["banana"]), set())

    def test_malformed_entry_does_not_break_the_filter(self):
        catalog = dict(self.catalog)
        catalog["broken"] = {"id": "broken", "equipment_required": 42}
        excluded_ids(catalog, list(ADHOC_EXCLUSIONS))  # must not raise


class TestFocusPriority(unittest.TestCase):
    """The A252 override, narrowed to the case it was designed for."""

    def setUp(self):
        self.catalog = _catalog()

    def _ids(self, intent):
        s = compose_adhoc_session(intent, _state(), self.catalog)
        return [e["exercise_id"] for e in s["exercises"]]

    def test_specific_focus_survives_a_named_muscle(self):
        ids = self._ids({
            "equipment_set": "home", "focus": "lock_off",
            "body_parts": ["core"], "minutes": 60, "energy": "medium",
        })
        pool = {e for e in ids if self.catalog[e].get("recency_group") == "pullup_lock_off"
                or "lock_off_endurance" in (self.catalog[e].get("domain") or [])}
        self.assertTrue(pool, f"a lock_off request produced no lock-off work: {ids}")

    def test_named_muscle_still_gets_a_block(self):
        """Demoted to secondary, not dropped."""
        ids = self._ids({
            "equipment_set": "home", "focus": "lock_off",
            "body_parts": ["core"], "minutes": 60, "energy": "medium",
        })
        core = [e for e in ids if "core" in (self.catalog[e].get("domain") or [])
                or self.catalog[e].get("category") == "core"]
        self.assertTrue(core, f"the requested muscle got no block at all: {ids}")

    def test_generic_focus_still_yields_to_body_parts(self):
        """A252's original case must keep working."""
        ids = self._ids({
            "equipment_set": "home", "focus": "general_strength",
            "body_parts": ["core"], "minutes": 45, "energy": "medium",
        })
        core = [e for e in ids if "core" in (self.catalog[e].get("domain") or [])
                or self.catalog[e].get("category") == "core"]
        self.assertTrue(core)

    def test_exclusion_reaches_the_deterministic_builder(self):
        ids = self._ids({
            "equipment_set": "home", "focus": "pull",
            "exclude": ["pullups"], "minutes": 45, "energy": "medium",
        })
        banned = excluded_ids(self.catalog, ["pullups"])
        self.assertFalse(set(ids) & banned, f"refused exercises present: {set(ids) & banned}")


class TestPool(unittest.TestCase):
    def setUp(self):
        self.catalog = _catalog()

    def test_pool_respects_equipment_and_refusals(self):
        pool = session_composer.build_pool(
            {"equipment_set": "home", "exclude": ["pullups"]}, _state(), self.catalog
        )
        ids = {str(e["id"]) for e in pool}
        self.assertTrue(ids)
        self.assertNotIn("l_sit_pullup", ids)
        # Nothing requiring a wall the athlete does not have at home.
        self.assertNotIn("limit_boulder_problems", ids)

    def test_tests_are_never_in_the_pool(self):
        pool = session_composer.build_pool({"equipment_set": "home"}, _state(), self.catalog)
        for ex in pool:
            roles = ex.get("role") or []
            roles = [roles] if isinstance(roles, str) else roles
            self.assertNotIn("test", roles)


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.catalog = _catalog()
        self.pool = session_composer.build_pool(
            {"equipment_set": "home"}, _state(), self.catalog
        )
        self.valid_id = str(self.pool[0]["id"])

    def test_invented_exercise_is_dropped(self):
        kept, dropped = session_composer.validate(
            {"exercises": [
                {"exercise_id": "unicorn_press", "sets": 3, "reps": 8},
                {"exercise_id": self.valid_id, "sets": 3, "reps": 8},
            ]}, self.pool, 60,
        )
        self.assertEqual([e["exercise_id"] for e in kept], [self.valid_id])
        self.assertTrue(any("not in pool" in d for d in dropped))

    def test_entry_without_reps_or_seconds_is_dropped(self):
        kept, dropped = session_composer.validate(
            {"exercises": [{"exercise_id": self.valid_id, "sets": 3}]}, self.pool, 60,
        )
        self.assertEqual(kept, [])
        self.assertTrue(any("neither reps nor work_seconds" in d for d in dropped))

    def test_out_of_range_values_are_clamped(self):
        # Huge budget on purpose: this asserts the clamp, and 20 sets x 600s of
        # rest would otherwise be trimmed by the time check before we can see it.
        kept, _ = session_composer.validate(
            {"exercises": [{"exercise_id": self.valid_id, "sets": 999, "reps": 8,
                            "rest_between_sets_seconds": 9999}]}, self.pool, 100_000,
        )
        self.assertEqual(kept[0]["sets"], session_composer.MAX_SETS)
        self.assertEqual(kept[0]["rest_between_sets_seconds"], session_composer.MAX_REST_SECONDS)

    def test_duplicates_are_dropped(self):
        kept, dropped = session_composer.validate(
            {"exercises": [
                {"exercise_id": self.valid_id, "sets": 3, "reps": 8},
                {"exercise_id": self.valid_id, "sets": 2, "reps": 8},
            ]}, self.pool, 60,
        )
        self.assertEqual(len(kept), 1)
        self.assertTrue(any("duplicate" in d for d in dropped))

    def test_time_budget_trims_the_tail(self):
        ids = [str(e["id"]) for e in self.pool[:12]]
        proposal = {"exercises": [
            {"exercise_id": i, "sets": 5, "work_seconds": 60,
             "rest_between_sets_seconds": 180} for i in ids
        ]}
        kept, dropped = session_composer.validate(proposal, self.pool, 30)
        self.assertLess(len(kept), len(ids))
        self.assertTrue(any("over time budget" in d for d in dropped))


class TestComposeAndFallback(unittest.TestCase):
    def setUp(self):
        self.catalog = _catalog()
        self.intent = {"equipment_set": "home", "focus": "lock_off",
                       "minutes": 60, "energy": "medium", "exclude": ["pullups"]}

    def _fake_proposal(self, pool):
        ids = [str(e["id"]) for e in pool[:5]]
        return {
            "name": "Sessione test",
            "rationale": "Due righe di spiegazione.",
            "exercises": [
                {"exercise_id": i, "sets": 3, "reps": 8, "rest_between_sets_seconds": 60}
                for i in ids
            ],
        }

    def test_compose_returns_a_session_shaped_payload(self):
        pool = session_composer.build_pool(self.intent, _state(), self.catalog)
        with mock.patch.object(session_composer.llm_client, "extract",
                               return_value=self._fake_proposal(pool)):
            s = session_composer.compose("prova", self.intent, _state(), self.catalog)
        self.assertIsNotNone(s)
        for key in ("adhoc", "name", "exercises", "estimated_load_score",
                    "estimated_duration_minutes", "explanation", "phase", "intent"):
            self.assertIn(key, s)
        self.assertEqual(s["composed_by"], "llm")
        self.assertEqual(s["explanation"], "Due righe di spiegazione.")

    def test_too_few_valid_exercises_falls_back(self):
        with mock.patch.object(session_composer.llm_client, "extract",
                               return_value={"name": "x", "exercises": [
                                   {"exercise_id": "nope", "sets": 3, "reps": 5}]}):
            self.assertIsNone(
                session_composer.compose("prova", self.intent, _state(), self.catalog)
            )

    def test_provider_error_falls_back_rather_than_raising(self):
        with mock.patch.object(session_composer.llm_client, "extract",
                               side_effect=RuntimeError("provider down")):
            self.assertIsNone(
                session_composer.compose("prova", self.intent, _state(), self.catalog)
            )

    def test_kill_switch_disables_the_llm_path(self):
        with mock.patch.object(session_composer, "ENABLED", False):
            with mock.patch.object(session_composer.llm_client, "extract") as called:
                self.assertIsNone(
                    session_composer.compose("prova", self.intent, _state(), self.catalog)
                )
                called.assert_not_called()

    def test_missing_api_key_still_propagates(self):
        """A misconfigured coach must fail loud, not degrade silently (A-COACH-V1a)."""
        with mock.patch.object(session_composer.llm_client, "extract",
                               side_effect=session_composer.llm_client.CoachConfigError("no key")):
            with self.assertRaises(session_composer.llm_client.CoachConfigError):
                session_composer.compose("prova", self.intent, _state(), self.catalog)


if __name__ == "__main__":
    unittest.main()
