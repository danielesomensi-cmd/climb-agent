"""D35: Hangboard experience gates.

Users with < 2 years climbing experience are blocked from advanced hangboard
training exercises (MaxHangs, MED, one-arm hang). Repeaters, density hangs,
and warmup hangs remain available. Test sessions are NEVER blocked.
"""

import pytest
from backend.engine.resolve_session import pick_best_exercise_p0

# Minimal exercise stubs matching catalog structure
_EXERCISES = [
    {"id": "max_hang_7s", "role": ["main"], "domain": ["finger_max_strength"],
     "pattern": "isometric_hang", "equipment_required": ["hangboard"],
     "location_allowed": ["home", "gym"], "contraindications": ["elbow_sensitive", "finger_sensitive"]},
    {"id": "max_hang_5s", "role": ["main"], "domain": ["finger_max_strength"],
     "pattern": "isometric_hang", "equipment_required": ["hangboard"],
     "location_allowed": ["home", "gym"], "contraindications": ["elbow_sensitive", "finger_sensitive"]},
    {"id": "max_hang_10s", "role": ["main"], "domain": ["finger_strength"],
     "pattern": "isometric_hang", "equipment_required": ["hangboard"],
     "location_allowed": ["home", "gym"], "contraindications": ["finger_sensitive"]},
    {"id": "max_hang_ladder", "role": ["main"], "domain": ["finger_max_strength"],
     "pattern": "isometric_hang", "equipment_required": ["hangboard"],
     "location_allowed": ["home", "gym"], "contraindications": ["elbow_sensitive", "finger_sensitive"]},
    {"id": "min_edge_hang", "role": ["main"], "domain": ["finger_max_strength"],
     "pattern": "isometric_hang", "equipment_required": ["hangboard"],
     "location_allowed": ["home", "gym"], "contraindications": ["elbow_sensitive", "finger_sensitive"]},
    {"id": "one_arm_hang_assisted", "role": ["main"], "domain": ["finger_max_strength"],
     "pattern": "isometric_hang", "equipment_required": ["hangboard", "band"],
     "location_allowed": ["home", "gym"], "contraindications": ["elbow_sensitive", "finger_sensitive"]},
    {"id": "repeater_hang_7_3", "role": ["main"], "domain": ["finger_strength_endurance"],
     "pattern": "repeater_hang", "equipment_required": ["hangboard"],
     "location_allowed": ["home", "gym"], "contraindications": []},
    {"id": "density_hangs", "role": ["main"], "domain": ["finger_strength_endurance"],
     "pattern": "isometric_hang", "equipment_required": ["hangboard"],
     "location_allowed": ["home", "gym"], "contraindications": ["elbow_sensitive"]},
    {"id": "dead_hang_easy", "role": ["warmup"], "domain": ["finger_strength"],
     "pattern": "isometric_hang", "equipment_required": ["hangboard"],
     "location_allowed": ["home", "gym"], "contraindications": []},
    {"id": "max_hang_7s_test", "role": ["main", "test"], "domain": ["finger_max_strength"],
     "pattern": "isometric_hang", "equipment_required": ["hangboard"],
     "location_allowed": ["home", "gym"], "contraindications": []},
]

_BLOCKED_IDS = {"max_hang_5s", "max_hang_7s", "max_hang_10s", "max_hang_ladder", "min_edge_hang", "one_arm_hang_assisted"}


def _pick(experience_years, role_req="main", domain_req=None):
    """Run P0 with given experience and return selected exercise id (or None)."""
    selected, _trace = pick_best_exercise_p0(
        exercises=_EXERCISES,
        location="home",
        available_equipment=["hangboard", "band"],
        role_req=role_req,
        domain_req=domain_req or "finger_max_strength",
        experience_years=experience_years,
    )
    return selected["id"] if selected else None


class TestHangboardExperienceGate:
    """D35: experience gate blocks advanced hangboard for < 2 years."""

    def test_beginner_blocked_from_max_hangs(self):
        """1 year experience → no MaxHangs/MED/one-arm available."""
        result = _pick(experience_years=1)
        assert result is None or result not in _BLOCKED_IDS, (
            f"Beginner (1yr) should NOT get {result}"
        )

    def test_experienced_gets_max_hangs(self):
        """3 years experience → full catalog."""
        result = _pick(experience_years=3)
        assert result is not None
        # Should pick first alphabetically among finger_max_strength main exercises
        assert result in _BLOCKED_IDS or result in {"repeater_hang_7_3", "density_hangs"}, (
            f"Experienced user should get advanced exercises, got {result}"
        )

    def test_exactly_2_years_gets_full_catalog(self):
        """Gate is strictly < 2, so exactly 2 years → allowed."""
        result = _pick(experience_years=2)
        assert result is not None
        # max_hang_5s should be available (alphabetically first among finger_max_strength)
        assert result in _BLOCKED_IDS, f"2yr user should get advanced exercises, got {result}"

    def test_zero_experience_only_gets_basic(self):
        """0 years → only warmup/repeaters/density from hangboard pool."""
        result = _pick(experience_years=0, domain_req="finger_strength_endurance")
        assert result is not None
        assert result not in _BLOCKED_IDS, f"Zero-experience user should NOT get {result}"
        assert result in {"repeater_hang_7_3", "density_hangs"}, f"Expected basic exercise, got {result}"

    def test_beginner_repeaters_available(self):
        """Beginners can still do repeaters."""
        result = _pick(experience_years=1, domain_req="finger_strength_endurance")
        assert result in {"repeater_hang_7_3", "density_hangs"}, f"Repeaters should be available, got {result}"

    def test_test_exercises_never_blocked(self):
        """Test-role exercises are NEVER blocked by experience gate."""
        # Use a stub exercise that has both "main" and "test" roles
        selected, _ = pick_best_exercise_p0(
            exercises=_EXERCISES,
            location="home",
            available_equipment=["hangboard", "band"],
            role_req="test",
            domain_req="finger_max_strength",
            experience_years=0,  # absolute beginner
        )
        # max_hang_7s_test has role=["main", "test"] — should pass gate
        assert selected is not None, "Test exercises must never be blocked by experience gate"
        assert selected["id"] == "max_hang_7s_test"

    def test_none_experience_no_filtering(self):
        """If experience_years is None, no gate filtering applies."""
        result = _pick(experience_years=None)
        assert result is not None, "None experience should mean no filtering"
