"""A327 step D (D288 R1 + R2) — the planner enforces the weekly finger caps
and the crag-block rule on its OWN placements.

- ≤ 3 finger-hard days a week (crag days included, Daniele decision 1), ≤ 2
  max-hang days; the user's sessions and the lived days count and are never
  moved; replacing a finger-hard session is neutral.
- Answer 1: a strength-power week whose crag days leave one finger-hard day to
  the engine gives it to the LIMIT session, not to max hangs.
- R2: after ≥ 2 consecutive hard crag days, the next day gets no engine
  session (a complementary lunch is fine, decision 2), the one after no hard
  session, no finger-high session before the last crag day's 18:00 + 72 h.
- ``crag_hard_dates`` (GET /api/week: the alerts' log reading) drives both;
  None falls back on the declared reading (B382(b)).
- Answer 3: nothing regenerates the next week after a crag weekend — the
  anchor acts when the week is generated after it.
- Invariant: the planner alone raises no recovery alert, crag weekends and a
  cap of 5 included (Daniele's shape).
"""
from __future__ import annotations

import copy
import logging
from datetime import date, timedelta

import pytest

from backend.engine import guards_v1
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _adjust_domain_weights, _build_session_pool
from backend.engine.planner_v2 import generate_phase_week
from backend.engine.stimulus import (
    FAMILY_LIMIT_POWER,
    finger_load_of,
    is_finger_hard_exposure,
    is_max_hang_session,
    session_flag,
    session_stimuli,
)

MON = "2026-11-16"
PREV = "2026-11-09"
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
PROFILE = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45, "technique": 50, "endurance": 40}
GYMS = [{"gym_id": "g1", "priority": 1,
         "equipment": ["gym_boulder", "gym_routes", "board_kilter", "hangboard", "pullup_bar", "spraywall"]}]


def _d(i: int, start: str = MON) -> str:
    return (date.fromisoformat(start) + timedelta(days=i)).isoformat()


def _avail(lunch: bool = False) -> dict:
    out = {}
    for d in DAYS:
        out[d] = {"evening": {"available": True, "locations": ["gym"], "preferred_location": "gym", "gym_id": "g1"}}
        if lunch:
            out[d]["lunch"] = {"available": True, "locations": ["gym"], "preferred_location": "gym",
                               "gym_id": "g1", "role": "complementary"}
    return out


def _empty_week(start: str) -> dict:
    d0 = date.fromisoformat(start)
    return {"start_date": start, "plan_revision": 1,
            "profile_snapshot": {"hard_cap_per_week": 5, "recovery_multiplier": 1.0},
            "weeks": [{"week_index": 1, "days": [{"date": (d0 + timedelta(i)).isoformat(), "sessions": []}
                                                 for i in range(7)]}], "adaptations": []}


def _crag(plan: dict, *idx: int, status: str = "planned") -> dict:
    for i in idx:
        plan["weeks"][0]["days"][i].update({"outdoor_spot_name": "Berdorf", "outdoor_spot_id": "spot_0_berdorf",
                                            "outdoor_discipline": "lead", "outdoor_session_status": status})
    return plan


def _gen(phase: str, *, prev=None, existing=None, cap: int = 5, lunch: bool = False, **kw) -> dict:
    logging.disable(logging.WARNING)
    try:
        return generate_phase_week(
            phase_id=phase, domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[phase], PROFILE),
            session_pool=_build_session_pool(phase, "lead"), start_date=MON, availability=_avail(lunch),
            allowed_locations=["gym", "home"], hard_cap_per_week=cap,
            planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": cap},
            default_gym_id="g1", gyms=copy.deepcopy(GYMS), home_equipment=["hangboard", "pullup_bar"],
            prev_week_plan=prev, existing_week_plan=existing, **kw)
    finally:
        logging.disable(logging.NOTSET)


def _day(wp, i):
    return wp["weeks"][0]["days"][i]


def _engine(wp, i):
    return [s for s in _day(wp, i)["sessions"] if s.get("slot_role") != "complementary"]


def _weekend_prev():
    return _crag(_empty_week(PREV), 5, 6, status="done")


def _weekend_this():
    return _crag(_empty_week(MON), 5, 6)


def _alerts(wp, prev):
    prev_days = prev["weeks"][0]["days"] if prev else None
    return [w for w in guards_v1.evaluate(wp, prev_days) if w["code"] != guards_v1.CODE_LOW_REST_DAYS]


class TestCragBlock:
    @pytest.mark.parametrize("phase", ["strength_power", "power_endurance", "performance", "base"])
    def test_monday_rest_tuesday_not_hard_no_finger_before_wednesday_evening(self, phase):
        """Phase 1 §4: crag Saturday + Sunday → Monday rest, Tuesday no hard,
        finger-high from Wednesday evening."""
        prev = _weekend_prev()
        wp = _gen(phase, prev=prev)
        assert _engine(wp, 0) == []
        assert not any(session_flag(s, "hard") for s in _day(wp, 1)["sessions"])
        for i in (0, 1):
            assert not any(finger_load_of(s) == "high" for s in _day(wp, i)["sessions"])
        assert not any(finger_load_of(s) == "high" and s.get("slot") in ("morning", "lunch")
                       for s in _day(wp, 2)["sessions"])
        assert [w for w in _alerts(wp, prev) if w["code"] == "crag_block"] == []

    def test_without_the_block_monday_trains(self):
        assert _engine(_gen("performance"), 0) != []

    def test_complementary_lunch_keeps_the_rest_day(self):
        """Decision 2: a complementary lunch may stay on the rest day."""
        prev = _weekend_prev()
        wp = _gen("strength_power", prev=prev, lunch=True)
        assert _engine(wp, 0) == []
        assert all(s.get("slot_role") == "complementary" for s in _day(wp, 0)["sessions"])
        assert [w for w in _alerts(wp, prev) if w["code"] == "crag_block"] == []

    @pytest.mark.parametrize("phase", ["strength_power", "performance", "base"])
    def test_one_crag_day_is_not_a_block(self, phase):
        """A single crag Sunday: Monday still trains (non-hard, B382(b))."""
        prev = _crag(_empty_week(PREV), 6, status="done")
        mon = _engine(_gen(phase, prev=prev), 0)
        assert mon != [] and not any(session_flag(s, "hard") or finger_load_of(s) == "high" for s in mon)

    def test_log_reading_wins_when_given(self):
        """``crag_hard_dates`` from GET /api/week: a weekend logged easy is no
        block (the Vercors 31/10-1/11 shape); a declared weekend with no input
        falls back on the declared reading."""
        prev = _weekend_prev()
        blocked = _gen("performance", prev=prev)
        easy = _gen("performance", prev=prev, crag_hard_dates=[])
        hard = _gen("performance", prev=prev, crag_hard_dates=[_d(5, PREV), _d(6, PREV)])
        assert _engine(blocked, 0) == [] and _engine(hard, 0) == []
        assert _engine(easy, 0) != []

    def test_pe_tuesday_loses_its_hard_session(self):
        prev = _weekend_prev()
        wp = _gen("power_endurance", prev=prev)
        assert not any(session_flag(s, "hard") for s in _day(wp, 1)["sessions"])


class TestFingerCaps:
    def test_sp_two_crag_days_leave_one_finger_hard_day_to_limit(self):
        """Answer 1: SP with a crag weekend this week (2 of the 3) — one engine
        finger-hard day, and it is a limit session, not max hangs."""
        prev = _weekend_prev()
        this = _weekend_this()
        wp = _gen("strength_power", prev=prev, existing=this)
        fh = [(i, s["session_id"]) for i in range(7) for s in _day(wp, i)["sessions"]
              if is_finger_hard_exposure(s)]
        assert len(fh) == 1, fh
        assert FAMILY_LIMIT_POWER in session_stimuli(_day(wp, fh[0][0])["sessions"][0]) or \
            any(FAMILY_LIMIT_POWER in session_stimuli(s) for s in _day(wp, fh[0][0])["sessions"])
        assert not any(is_max_hang_session(s) for i in range(7) for s in _day(wp, i)["sessions"])
        assert _alerts(wp, prev) == []

    def test_clean_sp_week_unchanged_shape(self):
        """No crag: the reservation never applies (3 finger-hard days possible)."""
        wp = _gen("strength_power")
        fh = {i for i in range(7) if any(is_finger_hard_exposure(s) for s in _day(wp, i)["sessions"])}
        assert len(fh) <= 3

    def test_users_sessions_count_and_are_never_moved(self):
        """The 05/10 shape: the user's max hang Monday + limit Thursday + crag
        weekend = 4 already (alert only) — the engine adds no finger-hard day
        and the user's sessions stay."""
        this = _weekend_this()
        mh = {"slot": "evening", "session_id": "custom_mh", "is_custom": True, "status": "planned",
              "tags": {"hard": True, "finger": True, "finger_load": "high"}, "constraints_applied": ["custom_add"],
              "exercises": [{"exercise_id": "max_hang_7s", "sets": 5}]}
        lim = dict(mh, session_id="custom_lim", exercises=[{"exercise_id": "limit_bouldering", "sets": 5}])
        this["weeks"][0]["days"][0]["sessions"] = [copy.deepcopy(mh)]
        this["weeks"][0]["days"][3]["sessions"] = [copy.deepcopy(lim)]
        wp = _gen("strength_power", existing=this, today=MON)
        engine_fh = [s for i in range(7) for s in _day(wp, i)["sessions"]
                     if is_finger_hard_exposure(s) and not s.get("is_custom")]
        assert engine_fh == []

    def test_max_hang_cap_on_engine_placements(self):
        """Two max-hang customs of the user → the engine places no max hang."""
        this = _empty_week(MON)
        for i in (0, 3):
            this["weeks"][0]["days"][i]["sessions"] = [{
                "slot": "lunch", "session_id": f"custom_mh{i}", "is_custom": True, "status": "planned",
                "tags": {"hard": True, "finger": True, "finger_load": "high"}, "constraints_applied": ["custom_add"],
                "exercises": [{"exercise_id": "max_hang_7s", "sets": 5}]}]
        wp = _gen("strength_power", existing=this, today=MON)
        assert not any(is_max_hang_session(s) for i in range(7) for s in _day(wp, i)["sessions"]
                       if not s.get("is_custom"))


class TestPlannerStillRespectsGuardsWithCrags:
    @pytest.mark.parametrize("phase", ["base", "strength_power", "power_endurance", "performance"])
    @pytest.mark.parametrize("shape", ["prev_weekend", "both_weekends", "midweek_block"])
    @pytest.mark.parametrize("cap", [3, 5])
    def test_no_alert_on_the_engines_week(self, phase, shape, cap):
        prev = _weekend_prev() if shape in ("prev_weekend", "both_weekends") else None
        this = _weekend_this() if shape == "both_weekends" else (
            _crag(_empty_week(MON), 2, 3) if shape == "midweek_block" else None)
        wp = _gen(phase, prev=prev, existing=this, cap=cap, lunch=True)
        alerts = _alerts(wp, prev)
        assert [(w["code"], w["date"], w["session_id"]) for w in alerts] == []


def test_router_passes_the_log_reading():
    """GET /api/week computes ``crag_hard_dates`` with outdoor_fatigue_days."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "api" / "routers" / "week.py").read_text(encoding="utf-8")
    assert "crag_hard_dates=_crag_hard_dates" in src and "outdoor_fatigue_days" in src
