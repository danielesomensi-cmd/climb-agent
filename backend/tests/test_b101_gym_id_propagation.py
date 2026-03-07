"""B101 — Verify gym_id propagation from availability to generated sessions.

Both generate_test_week() and generate_phase_week() must respect the gym_id
specified in each availability slot, not fall back to default or first-by-priority.
"""

from backend.engine.planner_v2 import generate_phase_week, generate_test_week


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GYM_BLOCX = {
    "gym_id": "blocx",
    "name": "Blocx",
    "priority": 1,
    "equipment": ["gym_boulder", "hangboard", "pullup_bar", "campus_board"],
}

GYM_DSUMMIT = {
    "gym_id": "dsummit",
    "name": "D-Summit",
    "priority": 2,
    "equipment": ["gym_boulder", "gym_routes", "hangboard", "pullup_bar", "bench"],
}


def _two_gym_availability():
    """Mon evening → Blocx, Thu evening → D-Summit. Other days off."""
    base = {}
    for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        base[wd] = {
            "evening": {"available": False, "preferred_location": "home"},
        }
    base["mon"]["evening"] = {
        "available": True,
        "preferred_location": "gym",
        "gym_id": "blocx",
    }
    base["thu"]["evening"] = {
        "available": True,
        "preferred_location": "gym",
        "gym_id": "dsummit",
    }
    return base


def _christie_like_availability():
    """5 days, 4 different gyms — mirrors Christie's real setup."""
    base = {}
    for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        base[wd] = {
            "evening": {"available": False, "preferred_location": "home"},
        }
    base["mon"]["evening"] = {"available": True, "preferred_location": "gym", "gym_id": "blocx"}
    base["wed"]["evening"] = {"available": True, "preferred_location": "gym", "gym_id": "blocx"}
    base["thu"]["evening"] = {"available": True, "preferred_location": "gym", "gym_id": "dsummit"}
    base["sat"]["evening"] = {"available": True, "preferred_location": "gym", "gym_id": "schoko"}
    base["sun"]["evening"] = {"available": True, "preferred_location": "gym", "gym_id": "eifel"}
    return base


FOUR_GYMS = [
    GYM_BLOCX,
    GYM_DSUMMIT,
    {"gym_id": "schoko", "name": "Blocshokolade", "priority": 3, "equipment": ["gym_boulder", "hangboard", "pullup_bar"]},
    {"gym_id": "eifel", "name": "Eifelblock", "priority": 4, "equipment": ["gym_boulder", "hangboard", "pullup_bar"]},
]


# ---------------------------------------------------------------------------
# generate_test_week — gym_id propagation
# ---------------------------------------------------------------------------

class TestTestWeekGymId:
    """generate_test_week() must assign the gym_id from the availability slot."""

    def test_two_gyms_correct_assignment(self):
        """Sessions on Mon get blocx, sessions on Thu get dsummit."""
        plan = generate_test_week(
            start_date="2026-03-02",  # Monday
            availability=_two_gym_availability(),
            allowed_locations=["gym"],
            gyms=[GYM_BLOCX, GYM_DSUMMIT],
            default_gym_id="blocx",
        )
        days = plan["weeks"][0]["days"]
        for day in days:
            for s in day["sessions"]:
                if day["weekday"] == "mon":
                    assert s["gym_id"] == "blocx", (
                        f"Mon session {s['session_id']} has gym_id={s['gym_id']}, expected blocx"
                    )
                elif day["weekday"] == "thu":
                    assert s["gym_id"] == "dsummit", (
                        f"Thu session {s['session_id']} has gym_id={s['gym_id']}, expected dsummit"
                    )

    def test_christie_like_multi_gym(self):
        """5 days, 4 gyms — each session must match the slot's gym_id."""
        expected_gym = {
            "mon": "blocx",
            "wed": "blocx",
            "thu": "dsummit",
            "sat": "schoko",
            "sun": "eifel",
        }
        plan = generate_test_week(
            start_date="2026-03-02",
            availability=_christie_like_availability(),
            allowed_locations=["gym"],
            gyms=FOUR_GYMS,
            default_gym_id="blocx",
        )
        days = plan["weeks"][0]["days"]
        for day in days:
            for s in day["sessions"]:
                wd = day["weekday"]
                assert wd in expected_gym, f"Unexpected session on {wd}"
                assert s["gym_id"] == expected_gym[wd], (
                    f"{wd} session {s['session_id']}: gym_id={s['gym_id']}, expected {expected_gym[wd]}"
                )

    def test_no_gym_id_in_slot_falls_back(self):
        """When slot has no gym_id, should fall back to default_gym_id."""
        avail = {
            wd: {"evening": {"available": wd == "mon", "preferred_location": "gym"}}
            for wd in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        }
        # No gym_id in slot — should use default
        plan = generate_test_week(
            start_date="2026-03-02",
            availability=avail,
            allowed_locations=["gym"],
            gyms=[GYM_BLOCX],
            default_gym_id="blocx",
        )
        days = plan["weeks"][0]["days"]
        mon_sessions = [s for d in days for s in d["sessions"] if d["weekday"] == "mon"]
        for s in mon_sessions:
            assert s["gym_id"] == "blocx", (
                f"Fallback failed: gym_id={s['gym_id']}, expected blocx"
            )


# ---------------------------------------------------------------------------
# generate_phase_week — gym_id propagation
# ---------------------------------------------------------------------------

class TestPhaseWeekGymId:
    """generate_phase_week() must propagate gym_id from availability slots."""

    def _base_domain_weights(self):
        return {
            "finger_strength": 0.3,
            "pulling_strength": 0.2,
            "power_endurance": 0.2,
            "technique": 0.15,
            "endurance": 0.1,
            "body_composition": 0.05,
        }

    def _base_session_pool(self):
        return [
            "strength_long", "strength_short", "power_endurance_gym",
            "technique_drills", "prehab_maintenance", "flexibility_full",
        ]

    def test_two_gyms_phase_week(self):
        """Each day's sessions must carry the gym_id from its availability slot."""
        plan = generate_phase_week(
            phase_id="base",
            domain_weights=self._base_domain_weights(),
            session_pool=self._base_session_pool(),
            start_date="2026-03-02",
            availability=_two_gym_availability(),
            hard_cap_per_week=3,
            default_gym_id="blocx",
            gyms=[GYM_BLOCX, GYM_DSUMMIT],
        )
        days = plan["weeks"][0]["days"]
        for day in days:
            for s in day["sessions"]:
                if s.get("location") != "gym":
                    continue
                if day["weekday"] == "mon":
                    assert s["gym_id"] == "blocx", (
                        f"Mon session {s['session_id']}: gym_id={s['gym_id']}, expected blocx"
                    )
                elif day["weekday"] == "thu":
                    assert s["gym_id"] == "dsummit", (
                        f"Thu session {s['session_id']}: gym_id={s['gym_id']}, expected dsummit"
                    )

    def test_christie_like_phase_week(self):
        """5 days, 4 gyms — phase week must respect per-slot gym_id."""
        expected_gym = {
            "mon": "blocx",
            "wed": "blocx",
            "thu": "dsummit",
            "sat": "schoko",
            "sun": "eifel",
        }
        plan = generate_phase_week(
            phase_id="base",
            domain_weights=self._base_domain_weights(),
            session_pool=self._base_session_pool(),
            start_date="2026-03-02",
            availability=_christie_like_availability(),
            hard_cap_per_week=3,
            default_gym_id="blocx",
            gyms=FOUR_GYMS,
        )
        days = plan["weeks"][0]["days"]
        for day in days:
            for s in day["sessions"]:
                if s.get("location") != "gym":
                    continue
                wd = day["weekday"]
                if wd in expected_gym:
                    assert s["gym_id"] == expected_gym[wd], (
                        f"{wd} session {s['session_id']}: gym_id={s['gym_id']}, expected {expected_gym[wd]}"
                    )
