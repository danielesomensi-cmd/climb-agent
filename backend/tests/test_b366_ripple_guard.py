"""B366 → A301 — after a hard load nothing rewrites the following days.

B366 made the three recovery ripples (quick-add day+1, hard override day+1 /
day+2, high-load outdoor day+1) spare the user's sessions and report what they
eased. A301 (guards are alerts, Daniele 2026-10-05: "se voglio fare
sovrallenamento lo faccio, decisione mia, tu solo segnala alert") removes the
ripples altogether, and the reconcile / neighbour-guard downshifts after a user
action with them: the following days stay byte-identical — engine sessions,
custom, forced, done and skipped alike — and ``guards_v1`` says what the guards
object to.
"""
from __future__ import annotations

import copy
from datetime import date, timedelta

from backend.engine import guards_v1
from backend.engine.replanner_v1 import apply_day_add, apply_day_override, apply_events

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MONDAY = "2026-01-05"


def _d(i: int) -> str:
    return (date.fromisoformat(MONDAY) + timedelta(days=i)).isoformat()


def _plan(hard_cap: int = 4) -> dict:
    days = [
        {"date": _d(i), "weekday": WEEKDAYS[i], "sessions": []}
        for i in range(7)
    ]
    return {
        "start_date": MONDAY,
        "profile_snapshot": {
            "phase_id": "strength_power",
            "discipline": "lead",
            "hard_cap_per_week": hard_cap,
            "recovery_multiplier": 1.0,
        },
        "weeks": [{"phase": "strength_power", "days": days}],
        "adaptations": [],
    }


def _catalog(session_id: str, slot: str, *, hard: bool, finger: bool, intensity: str) -> dict:
    return {
        "session_id": session_id,
        "slot": slot,
        "location": "gym",
        "gym_id": "g1",
        "phase_id": "strength_power",
        "intensity": intensity,
        "tags": {"hard": hard, "finger": finger},
    }


def _custom(slot: str = "evening", *, finger: bool = False) -> dict:
    """A user-built hard session (custom sessions carry derived hard tags, B345)."""
    return {
        "session_id": "custom_cs_4abc6aed",
        "slot": slot,
        "location": "gym",
        "gym_id": "g1",
        "is_custom": True,
        "custom_session_id": "cs_4abc6aed",
        "intensity": "high",
        "tags": {"hard": True, "finger": finger},
        "exercises": [{"exercise_id": "weighted_pullup", "sets": 4, "reps": 3, "load_kg": 28}],
    }


def _day(plan: dict, i: int) -> dict:
    return plan["weeks"][0]["days"][i]


def _put(plan: dict, i: int, *sessions: dict) -> None:
    _day(plan, i)["sessions"] = [copy.deepcopy(s) for s in sessions]


def _mixed_next_day(plan: dict, i: int = 2) -> list:
    """Every kind of session on day *i*: engine hard, forced, custom; done and
    skipped on day *i*+1 — none of them may move."""
    forced = {**_catalog("limit_boulder_gym", "lunch", hard=True, finger=True, intensity="max"),
              "forced": True, "constraints_applied": ["quick_add", "user_forced"]}
    _put(plan, i,
         _catalog("power_endurance_gym", "morning", hard=True, finger=False, intensity="high"),
         forced,
         _custom("evening", finger=True))
    _put(plan, i + 1,
         {**_catalog("limit_boulder_gym", "morning", hard=True, finger=True, intensity="max"), "status": "done"},
         {**_catalog("technique_focus_gym", "evening", hard=False, finger=False, intensity="medium"),
          "status": "skipped"})
    _put(plan, i + 2, _catalog("technique_focus_gym", "evening", hard=False, finger=False, intensity="medium"))
    return copy.deepcopy(plan["weeks"][0]["days"])


def _only_day_changed(before_days: list, after: dict, i: int) -> None:
    for k, (b, a) in enumerate(zip(before_days, after["weeks"][0]["days"])):
        if k != i:
            assert a == b, f"day {k} was rewritten"


# ── quick-add ────────────────────────────────────────────────────────────────

class TestQuickAdd:
    def test_following_days_byte_identical(self):
        plan = _plan()
        before = _mixed_next_day(plan)
        updated, warnings, adjustments = apply_day_add(
            plan, session_id="finger_strength_home", target_date=_d(1),
            slot="evening", location="home",
        )
        assert _day(updated, 1)["sessions"][0]["session_id"] == "finger_strength_home"
        _only_day_changed(before, updated, 1)
        assert adjustments == []
        assert warnings, "the finger gap with the next day is said"
        entry = next(a for a in updated["adaptations"] if a["type"] == "quick_add")
        assert entry["adjustments"] == []

    def test_finger_gap_alert_names_both_sides(self):
        plan = _plan()
        custom = _custom("evening", finger=True)
        _put(plan, 2, custom)
        updated, _w, _adj = apply_day_add(
            plan, session_id="finger_strength_home", target_date=_d(1),
            slot="evening", location="home",
        )
        assert _day(updated, 2)["sessions"] == [custom]
        alerts = [w for w in guards_v1.evaluate(updated) if w["code"] == "finger_gap"]
        assert alerts and alerts[0]["date"] == _d(2) and alerts[0]["with"][0]["date"] == _d(1)
        assert alerts[0]["user_owned"] is True

    def test_deterministic(self):
        plan = _plan()
        _mixed_next_day(plan)
        a = apply_day_add(plan, session_id="power_endurance_gym", target_date=_d(1),
                          slot="evening", location="gym")
        b = apply_day_add(plan, session_id="power_endurance_gym", target_date=_d(1),
                          slot="evening", location="gym")
        assert a == b


# ── override ─────────────────────────────────────────────────────────────────

class TestOverride:
    def test_following_two_days_byte_identical(self):
        plan = _plan()
        before = _mixed_next_day(plan)
        updated = apply_day_override(
            plan, intent="strength", location="home",
            reference_date=_d(0), target_date=_d(1), phase_id="strength_power",
        )
        _only_day_changed(before, updated, 1)
        entry = next(a for a in updated["adaptations"] if a["type"] == "day_override")
        assert entry["adjustments"] == [] and "ripple_days" not in entry

    def test_override_itself_not_downshifted_next_to_a_finger_custom(self):
        plan = _plan()
        _put(plan, 2, _custom("evening", finger=True))
        updated = apply_day_override(
            plan, intent="strength", location="home",
            reference_date=_d(0), target_date=_d(1), phase_id="strength_power",
        )
        tue = _day(updated, 1)["sessions"][0]
        assert tue["session_id"] != "regeneration_easy"
        assert tue["constraints_applied"] == ["manual_override"]
        assert any(w["code"] == "finger_gap" for w in guards_v1.evaluate(updated))


# ── outdoor ──────────────────────────────────────────────────────────────────

class TestOutdoor:
    def _complete(self, plan: dict, load: int = 80) -> dict:
        _day(plan, 1)["outdoor_spot_name"] = "Berdorf"
        _day(plan, 1)["outdoor_session_status"] = "planned"
        return apply_events(plan, [{
            "event_type": "complete_outdoor", "date": _d(1), "outdoor_load_score": load,
        }])

    def test_big_outdoor_day_rewrites_nothing_and_alerts(self):
        plan = _plan()
        before = _mixed_next_day(plan)
        updated = self._complete(plan)
        _only_day_changed(before, updated, 1)
        assert not [a for a in updated["adaptations"] if a["type"] == "outdoor_ripple"]
        alerts = [w for w in guards_v1.evaluate(updated) if w["code"] == "post_outdoor"]
        assert {(w["slot"], w["session_id"]) for w in alerts} == {
            ("morning", "power_endurance_gym"), ("lunch", "limit_boulder_gym"),
            ("evening", "custom_cs_4abc6aed"),
        }

    def test_low_load_alert_depends_on_the_route_log(self):
        # B372: the load alone no longer clears a crag day (it never reached
        # the threshold in 37 real days) — the route log does.
        plan = _plan()
        _put(plan, 2, _catalog("limit_boulder_gym", "morning", hard=True, finger=True, intensity="max"))
        updated = self._complete(plan, load=30)
        assert [w for w in guards_v1.evaluate(updated) if w["code"] == "post_outdoor"]
        easy = {"outdoor_log": [{"date": _d(1), "discipline": "lead",
                                 "routes": [{"name": "Easy", "grade": "6a"}]}],
                "performance": {"current_level": {"sport": {"worked": {"grade": "8a"}}}}}
        assert not [w for w in guards_v1.evaluate(updated, None, None, easy) if w["code"] == "post_outdoor"]
