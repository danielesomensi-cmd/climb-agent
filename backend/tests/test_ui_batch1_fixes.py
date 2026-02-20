"""Tests for UI-test batch 1 fixes: planner slot/location, resolver dedup,
technique session rewrite, and target_days cap."""

import json
import os
import unittest
from copy import deepcopy

from backend.engine.planner_v2 import generate_phase_week, _normalize_availability, SLOTS
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _build_session_pool, _adjust_domain_weights
from backend.engine.resolve_session import resolve_session, pick_best_exercise_p0, norm_str, get_ex_id

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _profile():
    return {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
            "technique": 50, "endurance": 40, "body_composition": 65}


def _make_kwargs(phase_id="base", **overrides):
    base_weights = _BASE_WEIGHTS[phase_id]
    domain_weights = _adjust_domain_weights(base_weights, _profile())
    session_pool = _build_session_pool(phase_id)
    defaults = dict(
        phase_id=phase_id,
        domain_weights=domain_weights,
        session_pool=session_pool,
        start_date="2026-03-02",
        availability=None,
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3},
        default_gym_id="blocx",
        gyms=[{"gym_id": "blocx", "equipment": ["spraywall", "board_kilter", "hangboard"]}],
    )
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Bug 1: Planner respects slot + preferred_location
# ---------------------------------------------------------------------------

class TestBug1PlannerSlotAndLocation(unittest.TestCase):

    def test_planner_respects_slot_from_availability(self):
        """When only morning is available, session must be in morning slot."""
        avail = {
            "mon": {"morning": {"available": True, "locations": ["home"]}},
            "tue": {"available": False},
            "wed": {"available": False},
            "thu": {"available": False},
            "fri": {"available": False},
            "sat": {"available": False},
            "sun": {"available": False},
        }
        plan = generate_phase_week(**_make_kwargs("base", availability=avail))
        mon = next(d for d in plan["weeks"][0]["days"] if d["weekday"] == "mon")
        self.assertTrue(len(mon["sessions"]) > 0, "No session placed on Monday")
        for s in mon["sessions"]:
            self.assertEqual(s["slot"], "morning",
                             f"Expected morning slot, got {s['slot']}")

    def test_planner_respects_preferred_location(self):
        """When preferred_location is home and both locations are viable,
        session should pick home over gym."""
        avail = {
            "mon": {
                "morning": {
                    "available": True,
                    "locations": ["home", "gym"],
                    "preferred_location": "home",
                },
            },
            "tue": {"available": False},
            "wed": {"available": False},
            "thu": {"available": False},
            "fri": {"available": False},
            "sat": {"available": False},
            "sun": {"available": False},
        }
        # Use allowed_locations=["home"] so only home-compatible sessions are placed
        plan = generate_phase_week(**_make_kwargs("base",
            availability=avail,
            allowed_locations=["home"]))
        mon = next(d for d in plan["weeks"][0]["days"] if d["weekday"] == "mon")
        self.assertTrue(len(mon["sessions"]) > 0, "No session on Monday")
        for s in mon["sessions"]:
            self.assertEqual(s["location"], "home",
                             f"Expected home, got {s['location']}")

    def test_planner_passes_gym_id(self):
        """When slot has gym_id, session.gym_id should match."""
        avail = {
            "mon": {
                "evening": {
                    "available": True,
                    "locations": ["gym"],
                    "preferred_location": "gym",
                    "gym_id": "bkl",
                },
            },
            "tue": {"available": False},
            "wed": {"available": False},
            "thu": {"available": False},
            "fri": {"available": False},
            "sat": {"available": False},
            "sun": {"available": False},
        }
        plan = generate_phase_week(**_make_kwargs("base",
            availability=avail,
            allowed_locations=["gym"]))
        mon = next(d for d in plan["weeks"][0]["days"] if d["weekday"] == "mon")
        self.assertTrue(len(mon["sessions"]) > 0, "No session on Monday")
        gym_sessions = [s for s in mon["sessions"] if s["location"] == "gym"]
        self.assertTrue(len(gym_sessions) > 0, "No gym session on Monday")
        for s in gym_sessions:
            self.assertEqual(s["gym_id"], "bkl",
                             f"Expected gym_id=bkl, got {s['gym_id']}")

    def test_normalize_explicit_slots_default_false(self):
        """When a day has explicit slot keys, unmentioned slots default to available=False."""
        avail = {"mon": {"morning": {"available": True}}}
        normalized = _normalize_availability(avail, ["home", "gym"])
        self.assertTrue(normalized["mon"]["morning"]["available"])
        self.assertFalse(normalized["mon"]["lunch"]["available"])
        self.assertFalse(normalized["mon"]["evening"]["available"])

    def test_normalize_no_explicit_slots_default_true(self):
        """When a day has no explicit slot keys (empty dict), all default to True."""
        avail = {"mon": {}}
        normalized = _normalize_availability(avail, ["home", "gym"])
        for slot in SLOTS:
            self.assertTrue(normalized["mon"][slot]["available"],
                            f"Expected {slot} available=True for empty day dict")

    def test_normalize_day_available_false(self):
        """Day with available=False should make all slots unavailable."""
        avail = {"mon": {"available": False}}
        normalized = _normalize_availability(avail, ["home", "gym"])
        for slot in SLOTS:
            self.assertFalse(normalized["mon"][slot]["available"])


# ---------------------------------------------------------------------------
# Bug 2: Resolver no duplicate exercises in session
# ---------------------------------------------------------------------------

class TestBug2ResolverDedup(unittest.TestCase):

    def test_resolver_no_duplicate_exercises_in_session(self):
        """Resolving endurance_aerobic_gym should produce no duplicate exercise_ids."""
        base_us = _load_json(os.path.join(REPO_ROOT, "backend", "tests", "fixtures", "test_user_state.json"))
        us = deepcopy(base_us)
        us.setdefault("context", {})
        us["context"]["location"] = "gym"
        us["context"]["gym_id"] = "blocx"

        out = resolve_session(
            repo_root=REPO_ROOT,
            session_path="backend/catalog/sessions/v1/endurance_aerobic_gym.json",
            templates_dir="backend/catalog/templates",
            exercises_path="backend/catalog/exercises/v1/exercises.json",
            out_path="output/__test_dedup.json",
            user_state_override=us,
            write_output=False,
        )
        ids = [e["exercise_id"] for e in out["resolved_session"]["exercise_instances"]]
        self.assertEqual(len(ids), len(set(ids)),
                         f"Duplicate exercise_ids found: {ids}")


# ---------------------------------------------------------------------------
# Bug 3: Technique session structure
# ---------------------------------------------------------------------------

class TestBug3TechniqueSession(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base_us = _load_json(os.path.join(REPO_ROOT, "backend", "tests", "fixtures", "test_user_state.json"))

    def _resolve_technique(self):
        us = deepcopy(self.base_us)
        us.setdefault("context", {})
        us["context"]["location"] = "gym"
        us["context"]["gym_id"] = "blocx"
        return resolve_session(
            repo_root=REPO_ROOT,
            session_path="backend/catalog/sessions/v1/technique_focus_gym.json",
            templates_dir="backend/catalog/templates",
            exercises_path="backend/catalog/exercises/v1/exercises.json",
            out_path="output/__test_technique.json",
            user_state_override=us,
            write_output=False,
        )

    def test_technique_session_includes_technique_exercises(self):
        """Technique session should have at least 2 exercises with role containing 'technique'."""
        out = self._resolve_technique()
        self.assertEqual(out["resolution_status"], "success")

        exercises_raw = _load_json(os.path.join(REPO_ROOT, "backend", "catalog", "exercises", "v1", "exercises.json"))
        if isinstance(exercises_raw, dict):
            exercises_raw = exercises_raw.get("exercises") or exercises_raw.get("items") or exercises_raw.get("data") or []
        ex_lookup = {norm_str(get_ex_id(e)): e for e in exercises_raw}

        technique_count = 0
        for inst in out["resolved_session"]["exercise_instances"]:
            ex = ex_lookup.get(norm_str(inst["exercise_id"]))
            if ex:
                roles = [norm_str(r) for r in (ex.get("role") if isinstance(ex.get("role"), list) else [ex.get("role", "")])]
                if "technique" in roles:
                    technique_count += 1
        self.assertGreaterEqual(technique_count, 2,
                                f"Expected >=2 technique exercises, got {technique_count}")

    def test_technique_session_has_core_and_cooldown(self):
        """Technique session should resolve warmup, core, and cooldown templates."""
        out = self._resolve_technique()
        block_uids = [b["block_uid"] for b in out["resolved_session"]["blocks"]]
        # warmup_climbing template
        has_warmup = any("warmup_climbing" in uid for uid in block_uids)
        self.assertTrue(has_warmup, f"No warmup_climbing block found in {block_uids}")
        # Check for core or cooldown blocks
        has_core_or_cooldown = any(
            "core_standard" in uid or "cooldown_stretch" in uid
            for uid in block_uids
        )
        self.assertTrue(has_core_or_cooldown,
                        f"No core_standard or cooldown_stretch block in {block_uids}")


# ---------------------------------------------------------------------------
# Bug 4: Planner respects target_training_days_per_week
# ---------------------------------------------------------------------------

class TestBug4TargetTrainingDays(unittest.TestCase):

    def test_planner_respects_target_training_days(self):
        """With 6 available slots and target=5, exactly 5 days should have sessions."""
        avail = {
            "mon": {"evening": {"available": True, "locations": ["gym"]},
                    "morning": {"available": True, "locations": ["home"]}},
            "tue": {"evening": {"available": True, "locations": ["gym"]},
                    "morning": {"available": True, "locations": ["home"]}},
            "wed": {"evening": {"available": True, "locations": ["gym"]},
                    "morning": {"available": True, "locations": ["home"]}},
            "thu": {"evening": {"available": True, "locations": ["gym"]},
                    "morning": {"available": True, "locations": ["home"]}},
            "fri": {"evening": {"available": True, "locations": ["gym"]},
                    "morning": {"available": True, "locations": ["home"]}},
            "sat": {"evening": {"available": True, "locations": ["gym"]},
                    "morning": {"available": True, "locations": ["home"]}},
            "sun": {"available": False},
        }
        plan = generate_phase_week(**_make_kwargs("base",
            availability=avail,
            planning_prefs={"target_training_days_per_week": 5, "hard_day_cap_per_week": 3}))
        days = plan["weeks"][0]["days"]
        days_with_sessions = sum(1 for d in days if d["sessions"])
        self.assertLessEqual(days_with_sessions, 5,
                             f"Expected <=5 days with sessions, got {days_with_sessions}")

    def test_planner_target_days_no_overcap(self):
        """Even with many available days, planner should not exceed target_days."""
        # All 7 days available, target=3
        plan = generate_phase_week(**_make_kwargs("base",
            planning_prefs={"target_training_days_per_week": 3, "hard_day_cap_per_week": 2}))
        days = plan["weeks"][0]["days"]
        days_with_sessions = sum(1 for d in days if d["sessions"])
        self.assertLessEqual(days_with_sessions, 3,
                             f"Expected <=3 days with sessions, got {days_with_sessions}")




# ---------------------------------------------------------------------------
# Batch 1b: Planner preferred_location + technique resolution
# ---------------------------------------------------------------------------

class TestBatch1bLocationPreference(unittest.TestCase):
    """UI-6b / UI-19b: planner must respect preferred_location on slots."""

    def _avail_all_prefer(self, preferred, days=("mon", "tue", "wed", "thu")):
        """Build availability where every day has an evening slot preferring *preferred*."""
        avail = {}
        for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            if wd in days:
                avail[wd] = {
                    "evening": {
                        "available": True,
                        "locations": ["home", "gym"],
                        "preferred_location": preferred,
                    },
                }
            else:
                avail[wd] = {"available": False}
        return avail

    def test_planner_home_preferred_no_gym_session(self):
        """All slots prefer home → every placed session must have location='home'."""
        avail = self._avail_all_prefer("home")
        plan = generate_phase_week(**_make_kwargs("base", availability=avail))
        for day in plan["weeks"][0]["days"]:
            for s in day["sessions"]:
                self.assertEqual(
                    s["location"], "home",
                    f"Session {s['session_id']} on {day['weekday']} has location "
                    f"'{s['location']}', expected 'home'",
                )

    def test_planner_gym_preferred_gets_gym_session(self):
        """All slots prefer gym → at least some sessions are gym."""
        avail = self._avail_all_prefer("gym")
        plan = generate_phase_week(**_make_kwargs("base", availability=avail))
        gym_count = sum(
            1 for day in plan["weeks"][0]["days"]
            for s in day["sessions"] if s["location"] == "gym"
        )
        self.assertGreater(gym_count, 0, "No gym sessions placed despite gym preference")

    def test_planner_mixed_locations_respected(self):
        """Mon/Wed prefer gym, Tue/Thu prefer home → each day's session matches."""
        avail = {}
        gym_days = {"mon", "wed"}
        home_days = {"tue", "thu"}
        for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            if wd in gym_days:
                avail[wd] = {"evening": {"available": True, "locations": ["home", "gym"],
                                          "preferred_location": "gym"}}
            elif wd in home_days:
                avail[wd] = {"evening": {"available": True, "locations": ["home", "gym"],
                                          "preferred_location": "home"}}
            else:
                avail[wd] = {"available": False}
        plan = generate_phase_week(**_make_kwargs("base", availability=avail))
        for day in plan["weeks"][0]["days"]:
            wd = day["weekday"]
            for s in day["sessions"]:
                if wd in gym_days:
                    self.assertEqual(s["location"], "gym",
                                     f"{wd}: expected gym, got {s['location']}")
                elif wd in home_days:
                    self.assertEqual(s["location"], "home",
                                     f"{wd}: expected home, got {s['location']}")

    def test_technique_resolves_zero_at_gym_without_climbing_surfaces(self):
        """technique_focus_gym at a gym with no climbing surfaces (e.g. work_gym
        with only dumbbell/bench/barbell) should yield 0 surface-requiring
        technique exercises. Bodyweight drills (equipment_required=[]) may still appear."""
        base_us = _load_json(os.path.join(REPO_ROOT, "backend", "tests", "fixtures", "test_user_state.json"))
        us = deepcopy(base_us)
        us.setdefault("context", {})
        us["context"]["gym_id"] = "work_gym"

        out = resolve_session(
            repo_root=REPO_ROOT,
            session_path="backend/catalog/sessions/v1/technique_focus_gym.json",
            templates_dir="backend/catalog/templates",
            exercises_path="backend/catalog/exercises/v1/exercises.json",
            out_path="output/__test_technique_no_surfaces.json",
            user_state_override=us,
            write_output=False,
        )

        exercises_raw = _load_json(os.path.join(REPO_ROOT, "backend", "catalog", "exercises", "v1", "exercises.json"))
        if isinstance(exercises_raw, dict):
            exercises_raw = exercises_raw.get("exercises") or exercises_raw.get("items") or exercises_raw.get("data") or []
        ex_lookup = {norm_str(get_ex_id(e)): e for e in exercises_raw}

        climbing_surfaces = {"gym_boulder", "spraywall", "board_kilter", "board_moonboard"}
        surface_technique_count = 0
        for inst in out["resolved_session"]["exercise_instances"]:
            ex = ex_lookup.get(norm_str(inst["exercise_id"]))
            if ex:
                roles = [norm_str(r) for r in (ex.get("role") if isinstance(ex.get("role"), list) else [ex.get("role", "")])]
                equip = set(ex.get("equipment_required", []) + ex.get("equipment_required_any", []))
                if "technique" in roles and equip & climbing_surfaces:
                    surface_technique_count += 1
        self.assertEqual(surface_technique_count, 0,
                         f"Expected 0 surface-requiring technique exercises at gym without climbing surfaces, got {surface_technique_count}")

    def test_technique_resolves_with_default_gym_fallback(self):
        """When no gym_id is set, resolver falls back to first gym by priority
        and technique exercises should still resolve (UI-19 deep fix)."""
        base_us = _load_json(os.path.join(REPO_ROOT, "backend", "tests", "fixtures", "test_user_state.json"))
        us = deepcopy(base_us)
        # Remove context entirely — simulates real user_state without context
        us.pop("context", None)

        out = resolve_session(
            repo_root=REPO_ROOT,
            session_path="backend/catalog/sessions/v1/technique_focus_gym.json",
            templates_dir="backend/catalog/templates",
            exercises_path="backend/catalog/exercises/v1/exercises.json",
            out_path="output/__test_technique_fallback.json",
            user_state_override=us,
            write_output=False,
        )

        exercises_raw = _load_json(os.path.join(REPO_ROOT, "backend", "catalog", "exercises", "v1", "exercises.json"))
        if isinstance(exercises_raw, dict):
            exercises_raw = exercises_raw.get("exercises") or exercises_raw.get("items") or exercises_raw.get("data") or []
        ex_lookup = {norm_str(get_ex_id(e)): e for e in exercises_raw}

        technique_count = 0
        for inst in out["resolved_session"]["exercise_instances"]:
            ex = ex_lookup.get(norm_str(inst["exercise_id"]))
            if ex:
                roles = [norm_str(r) for r in (ex.get("role") if isinstance(ex.get("role"), list) else [ex.get("role", "")])]
                if "technique" in roles:
                    technique_count += 1
        self.assertGreaterEqual(technique_count, 2,
                                f"Expected >=2 technique exercises with gym fallback, got {technique_count}")

    def test_technique_exercises_exist_and_match_session_spec(self):
        """Verify technique exercises have fields that match technique_focus_gym inline blocks."""
        import glob

        with open(os.path.join(REPO_ROOT, 'backend', 'catalog', 'sessions', 'v1', 'technique_focus_gym.json')) as f:
            session = json.load(f)

        technique_specs = []
        for mod in session.get('modules', []):
            sel = mod.get('selection', {})
            primary = sel.get('primary', {})
            filters = primary.get('filters', {})
            if filters.get('role') and 'technique' in filters['role']:
                technique_specs.append(filters)

        self.assertGreaterEqual(len(technique_specs), 2,
                                f"Expected >=2 technique blocks in session, found {len(technique_specs)}")

        exercises_raw = _load_json(os.path.join(REPO_ROOT, 'backend', 'catalog', 'exercises', 'v1', 'exercises.json'))
        if isinstance(exercises_raw, dict):
            exercises_raw = exercises_raw.get('exercises') or exercises_raw.get('items') or exercises_raw.get('data') or []

        for spec in technique_specs:
            role_filter = spec.get('role', [])
            pattern_filter = spec.get('pattern', [])

            matching = [
                e for e in exercises_raw
                if (not role_filter or any(r in (e.get('role') or []) for r in role_filter))
                and (not pattern_filter or (e.get('pattern', '') in pattern_filter
                                            or (isinstance(e.get('pattern'), list)
                                                and any(p in pattern_filter for p in e['pattern']))))
            ]

            self.assertGreater(len(matching), 0,
                f"No exercises match technique block spec: "
                f"role={role_filter}, pattern={pattern_filter}. "
                f"Available technique exercises: "
                f"{[(e['id'], e.get('role'), e.get('pattern')) for e in exercises_raw if 'technique' in str(e.get('role', [])).lower()]}")


# ---------------------------------------------------------------------------
# UI-23: Planner prioritises gym slots for climbing sessions
# ---------------------------------------------------------------------------

class TestUI23GymSlotPriority(unittest.TestCase):
    """UI-23: Planner prioritizes gym slots for climbing sessions."""

    def _avail_mixed(self, gym_days, home_days):
        """Build availability with specific gym and home days."""
        avail = {}
        for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            if wd in gym_days:
                avail[wd] = {"evening": {"available": True, "locations": ["gym"],
                             "preferred_location": "gym", "gym_id": "blocx"}}
            elif wd in home_days:
                avail[wd] = {"morning": {"available": True, "locations": ["home"],
                             "preferred_location": "home"}}
            else:
                avail[wd] = {"available": False}
        return avail

    def test_gym_days_kept_over_home_when_capped(self):
        """With 3 gym + 3 home days and target=4, all 3 gym days should be kept."""
        avail = self._avail_mixed(
            gym_days=("mon", "wed", "fri"),
            home_days=("tue", "thu", "sat"),
        )
        plan = generate_phase_week(**_make_kwargs("base",
            availability=avail,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3}))
        days = plan["weeks"][0]["days"]
        gym_days_with_sessions = [
            d for d in days
            if d["sessions"] and any(s["location"] == "gym" for s in d["sessions"])
        ]
        self.assertGreaterEqual(len(gym_days_with_sessions), 3,
            f"Expected >=3 gym days kept, got {len(gym_days_with_sessions)}")

    def test_climbing_sessions_placed_on_gym_days(self):
        """Gym-only climbing sessions should be placed on gym days, not dropped."""
        avail = self._avail_mixed(
            gym_days=("tue", "thu"),
            home_days=("mon", "wed", "fri", "sat"),
        )
        plan = generate_phase_week(**_make_kwargs("base",
            availability=avail,
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3}))
        days = plan["weeks"][0]["days"]
        gym_sessions = [
            s for d in days for s in d["sessions"]
            if s["location"] == "gym"
        ]
        self.assertGreater(len(gym_sessions), 0,
            "No gym sessions placed — gym days were dropped by target_days cap")

    def test_all_home_slots_still_works(self):
        """When user only has home slots, planner should still fill target_days."""
        avail = self._avail_mixed(
            gym_days=(),
            home_days=("mon", "tue", "wed", "thu", "fri"),
        )
        plan = generate_phase_week(**_make_kwargs("base",
            availability=avail,
            allowed_locations=["home"],
            planning_prefs={"target_training_days_per_week": 4, "hard_day_cap_per_week": 3}))
        days = plan["weeks"][0]["days"]
        days_with_sessions = sum(1 for d in days if d["sessions"])
        self.assertGreaterEqual(days_with_sessions, 3,
            f"Expected >=3 training days with home-only, got {days_with_sessions}")


if __name__ == "__main__":
    unittest.main()
