"""A327 step C (D288 R1) — finger-load tiers and the 6 h spacing.

- ``stimulus.finger_load_of``: ONE reading of a session's tier (stored tier →
  catalog meta by id → old ``finger`` tags = high → stale tags with finger-hard
  work = high → None).
- ``session_tags.derive_finger_load``: the tier of a custom's exercises, stored
  once at insertion (``tags.finger_load``) when the session loads the fingers.
- high–high: the 48 h calendar rule, unchanged (``finger_gap``). low–high
  (either order) and low–low: ``FINGER_LOW_GAP_H`` (6 h) × recovery_multiplier
  on the slot clock, at most ``FINGER_LOW_MAX_PER_DAY`` (2) low a day
  (``finger_low_gap``). A crag day is high 08:00-18:00.
- The planner places by the same rules (one clock gate) and PASS 2 no longer
  places finger sessions without any gap (D288 §1.3-1).
"""
from __future__ import annotations

import copy
from datetime import date, timedelta

import pytest

from backend.engine import athlete_context as ac
from backend.engine import guards_v1
from backend.engine import retest_policy as rp
from backend.engine.planner_v2 import _SESSION_META, generate_phase_week
from backend.engine.replanner_v1 import apply_events, suggest_sessions
from backend.engine.session_tags import derive_finger_load, derive_session_tags
from backend.engine.stimulus import finger_load_of, is_finger_hard_session

MON = "2026-10-05"
LIMIT = "limit_boulder_gym"
STRENGTH = "strength_long"
MAINT = "finger_maintenance_gym"
AEROBIC = "finger_aerobic_base"
EASY = "technique_focus_gym"
HARD = "power_endurance_gym"
LOW_EX = ("sub_max_capacity_hang", "bar_dead_hang")


def _d(i: int, start: str = MON) -> str:
    return (date.fromisoformat(start) + timedelta(days=i)).isoformat()


def _sess(sid: str, slot: str = "evening", **kw) -> dict:
    m = _SESSION_META[sid]
    s = {"slot": slot, "session_id": sid, "location": "gym", "gym_id": "g1", "phase_id": "base",
         "intensity": m["intensity"], "tags": {"hard": m["hard"], "finger": m["finger"]},
         "constraints_applied": []}
    if m.get("test"):
        s["tags"]["test"] = True
    s.update(kw)
    return s


def _custom(sid: str, *ids: str, slot: str = "evening", store_tier: bool = True) -> dict:
    ex = [{"exercise_id": e, "sets": 3} for e in ids]
    tags, intensity = derive_session_tags(ex)
    if store_tier and tags["finger"]:
        tags["finger_load"] = derive_finger_load(ex)
    return {"slot": slot, "session_id": sid, "custom_session_id": sid[7:], "is_custom": True, "name": sid,
            "location": "home", "status": "planned", "intensity": intensity, "tags": tags,
            "constraints_applied": ["custom_add"], "exercises": ex}


def _plan(days: dict, *, start: str = MON, hard_cap: int = 5, recovery_multiplier: float = 1.0) -> dict:
    d0 = date.fromisoformat(start)
    out = [{"date": (d0 + timedelta(i)).isoformat(), "sessions": copy.deepcopy(days.get(i, []))} for i in range(7)]
    return {"start_date": start, "plan_revision": 1,
            "profile_snapshot": {"phase_id": "base", "hard_cap_per_week": hard_cap,
                                 "recovery_multiplier": recovery_multiplier},
            "weeks": [{"week_index": 1, "days": out}], "adaptations": []}


def _day(plan, i):
    return plan["weeks"][0]["days"][i]


def _crag(day):
    day.update({"outdoor_spot_name": "Berdorf", "outdoor_spot_id": "spot_0_berdorf",
                "outdoor_discipline": "lead", "outdoor_session_status": "planned"})


def _codes(alerts, *codes):
    return [(w["code"], w["date"], w["session_id"]) for w in alerts if not codes or w["code"] in codes]


FINGER = ("finger_gap", "finger_low_gap")


# ---------------------------------------------------------------------------
# The reading
# ---------------------------------------------------------------------------

class TestFingerLoadOf:
    def test_catalog_by_id(self):
        assert finger_load_of(_sess(AEROBIC)) == "low"
        for sid in (STRENGTH, LIMIT, MAINT, "finger_endurance_short", "route_projecting_gym", "test_max_hang_7s"):
            assert finger_load_of(_sess(sid)) == "high", sid
        assert finger_load_of(_sess(EASY)) is None and finger_load_of(_sess(HARD)) is None

    def test_stored_tier_wins(self):
        s = _custom("custom_low", *LOW_EX)
        assert s["tags"]["finger_load"] == "low" and finger_load_of(s) == "low"
        s["tags"]["finger_load"] = "high"
        assert finger_load_of(s) == "high"

    def test_old_tags_read_high(self):
        """A custom stored before A327 (finger True, no tier) keeps its gap."""
        s = _custom("custom_old", *LOW_EX, store_tier=False)
        assert "finger_load" not in s["tags"] and finger_load_of(s) == "high"

    def test_explicit_false_skips_the_meta_and_stale_tags_with_hard_work_read_high(self):
        s = _sess(AEROBIC)
        s["tags"]["finger"] = False
        assert finger_load_of(s) is None
        stale = _custom("custom_comp", "three_attempt_comp", store_tier=False)
        stale["tags"] = {"hard": False, "finger": False}  # the 26/10 shape
        assert finger_load_of(stale) == "high"

    def test_meta_pin(self):
        """finger ⇔ finger_load on every catalog entry; only the aerobic base is low."""
        for sid, m in _SESSION_META.items():
            assert bool(m.get("finger")) == (m.get("finger_load") is not None), sid
            assert m.get("finger_load") in (None, "high", "low"), sid
        assert {sid for sid, m in _SESSION_META.items() if m.get("finger_load") == "low"} == {AEROBIC}


class TestDeriveFingerLoad:
    @pytest.mark.parametrize("ids,tier", [
        (LOW_EX, "low"),
        (("hang_rampup_progressive", "weighted_pullup"), None),          # B392: warm-up ignored
        (("pocket_rampup_hangboard", "weighted_pullup"), "low"),
        (("sub_max_capacity_hang", "max_hang_7s"), "high"),
        (("bar_dead_hang", "intermittent_dead_hangs"), "high"),          # answer 2: high for the gap
        (("route_redpoint_attempt",), "high"),                           # answer 4
        (("four_by_four_bouldering", "sub_max_capacity_hang"), None),    # B414 E2
        (("four_by_four_bouldering", "sub_max_capacity_hang", "bar_dead_hang"), None),
        (("four_by_four_bouldering", "sub_max_capacity_hang", "active_finger_curls"), "low"),
        (("four_by_four_bouldering", "intermittent_dead_hangs", "max_hang_7s"), "high"),
        (("dip", "core_l_sit"), None),
    ])
    def test_cases(self, ids, tier):
        assert derive_finger_load([{"exercise_id": i} for i in ids]) == tier

    def test_none_exactly_when_not_finger(self):
        from backend.engine.session_tags import _catalog

        finger_ids = sorted(eid for eid, e in _catalog().items() if e.get("finger_load"))
        others = ["four_by_four_bouldering", "weighted_pullup", "dip", "warmup_easy_boulders"]
        for a in finger_ids:
            for b in others + finger_ids[:5]:
                ex = [{"exercise_id": a}, {"exercise_id": b}]
                assert (derive_finger_load(ex) is None) == (not derive_session_tags(ex)[0]["finger"]), (a, b)

    def test_mixed_custom_is_not_finger_hard(self):
        """D288 §1.3-2: ramp-up + weighted pulls used to block the 72 h test."""
        s = _custom("custom_mixed", "pocket_rampup_hangboard", "weighted_pullup", "one_arm_pullup_assisted")
        assert s["tags"]["finger"] is True and s["tags"]["finger_load"] == "low"
        s["tags"]["hard"] = True
        assert not is_finger_hard_session(s)
        old = copy.deepcopy(s)
        del old["tags"]["finger_load"]  # stored before A327: read high, as before
        assert is_finger_hard_session(old)


class TestInsertion:
    def _week(self):
        return _plan({})

    def test_custom_stores_the_tier_only_when_finger(self):
        css = [{"id": "lo", "name": "Light", "exercises": [{"exercise_id": e} for e in LOW_EX]},
               {"id": "core", "name": "Core", "exercises": [{"exercise_id": "core_l_sit"}]}]
        out = apply_events(self._week(), [
            {"event_type": "add_custom_session", "custom_session_id": "lo", "target_date": _d(1), "slot": "lunch"},
            {"event_type": "add_custom_session", "custom_session_id": "core", "target_date": _d(2), "slot": "lunch"},
        ], custom_sessions=css)
        lo = _day(out, 1)["sessions"][0]
        core = _day(out, 2)["sessions"][0]
        assert lo["tags"] == {"hard": False, "finger": True, "finger_load": "low"}
        assert "finger_load" not in core["tags"]

    def test_generated_declared_finger_without_exercises_is_high_and_declared_tier_only_raises(self):
        out = apply_events(self._week(), [{
            "event_type": "add_generated_session", "target_date": _d(1), "slot": "evening",
            "session_payload": {"name": "Fingers", "tags": {"finger": True},
                                "exercises": [{"exercise_id": "core_l_sit"}]}}])
        assert _day(out, 1)["sessions"][0]["tags"]["finger_load"] == "high"
        out = apply_events(self._week(), [{
            "event_type": "add_generated_session", "target_date": _d(1), "slot": "evening",
            "session_payload": {"name": "Hangs", "tags": {"finger": True, "finger_load": "low"},
                                "exercises": [{"exercise_id": "max_hang_7s"}]}}])
        assert _day(out, 1)["sessions"][0]["tags"]["finger_load"] == "high"


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

class TestGuards:
    def test_constants(self):
        assert rp.FINGER_LOW_GAP_H == 6 and rp.FINGER_LOW_MAX_PER_DAY == 2
        assert "finger_low_gap" in guards_v1.CODES

    def test_low_next_day_is_not_a_finger_gap(self):
        plan = _plan({0: [_sess(STRENGTH)], 1: [_sess(AEROBIC, slot="morning", location="home")],
                      2: [_sess(LIMIT)]})
        assert _codes(guards_v1.evaluate(plan), *FINGER) == []

    def test_high_high_is_still_the_calendar_rule(self):
        plan = _plan({0: [_sess(STRENGTH)], 1: [_sess(MAINT)]})
        assert _codes(guards_v1.evaluate(plan), *FINGER) == [("finger_gap", _d(1), MAINT)]

    def test_low_lunch_high_evening_is_fine_morning_lunch_is_not(self):
        """Phase 1: «low a pranzo + high la sera» is legal (6 h); morning + lunch (5 h) is not."""
        ok = _plan({2: [_custom("custom_lo", *LOW_EX, slot="lunch"), _sess(LIMIT)]})
        assert _codes(guards_v1.evaluate(ok), *FINGER) == []
        bad = _plan({2: [_custom("custom_lo", *LOW_EX, slot="morning"), _sess(LIMIT, slot="lunch")]})
        alerts = guards_v1.evaluate(bad)
        assert _codes(alerts, *FINGER) == [("finger_low_gap", _d(2), LIMIT)]
        w = next(a for a in alerts if a["code"] == "finger_low_gap")
        assert w["detail"] == "gap" and w["gap_h"] == 6 and w["with"] == [
            {"date": _d(2), "slot": "morning", "session_id": "custom_lo"}]

    def test_high_then_low_either_order(self):
        bad = _plan({2: [_sess(LIMIT, slot="morning"), _custom("custom_lo", *LOW_EX, slot="lunch")]})
        assert _codes(guards_v1.evaluate(bad), *FINGER) == [("finger_low_gap", _d(2), "custom_lo")]

    def test_low_low_and_two_a_day(self):
        two = _plan({2: [_custom("custom_a", *LOW_EX, slot="morning"), _custom("custom_b", *LOW_EX, slot="evening")]})
        assert _codes(guards_v1.evaluate(two), *FINGER) == []
        close = _plan({2: [_custom("custom_a", *LOW_EX, slot="morning"), _custom("custom_b", *LOW_EX, slot="lunch")]})
        assert _codes(guards_v1.evaluate(close), *FINGER) == [("finger_low_gap", _d(2), "custom_b")]
        three = _plan({2: [_custom("custom_a", *LOW_EX, slot="morning"), _custom("custom_b", *LOW_EX, slot="lunch"),
                           _custom("custom_c", *LOW_EX, slot="evening")]})
        alerts = [w for w in guards_v1.evaluate(three) if w["code"] == "finger_low_gap"]
        third = next(w for w in alerts if w["session_id"] == "custom_c")
        assert third["detail"] == "per_day" and third["low_count"] == 3

    def test_recovery_multiplier_stretches_the_six_hours(self):
        plan = _plan({2: [_custom("custom_lo", *LOW_EX, slot="lunch"), _sess(LIMIT)]}, recovery_multiplier=1.5)
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts, "finger_low_gap") == [("finger_low_gap", _d(2), LIMIT)]
        assert next(a for a in alerts if a["code"] == "finger_low_gap")["gap_h"] == 9

    def test_crag_day_is_high_eight_to_eighteen(self):
        """Phase 1: no finger session on the crag day; the evening before and
        the morning after are fine for a low."""
        plan = _plan({2: [_custom("custom_ev", *LOW_EX, slot="evening")], 3: [],
                      4: [_custom("custom_mo", *LOW_EX, slot="morning")]})
        _crag(_day(plan, 3))
        assert _codes(guards_v1.evaluate(plan), *FINGER, "post_outdoor") == []
        plan = _plan({3: [_custom("custom_same", *LOW_EX, slot="evening")]})
        _crag(_day(plan, 3))
        assert _codes(guards_v1.evaluate(plan), *FINGER) == [("finger_low_gap", _d(3), "custom_same")]

    def test_post_outdoor_and_back_to_back_read_the_tier(self):
        plan = _plan({4: [_custom("custom_lo", *LOW_EX, slot="evening")]})
        _crag(_day(plan, 3))
        assert _codes(guards_v1.evaluate(plan), "post_outdoor") == []
        plan = _plan({4: [_sess(MAINT)]})
        _crag(_day(plan, 3))
        assert _codes(guards_v1.evaluate(plan), "post_outdoor") == [("post_outdoor", _d(4), MAINT)]
        # A hard session with light finger work the day before a crag day:
        # finger_gap no longer sees it, hard_back_to_back does.
        hard_low = _custom("custom_pull", "pocket_rampup_hangboard", "weighted_pullup", "one_arm_pullup_assisted")
        hard_low["tags"]["hard"] = True
        plan = _plan({2: [hard_low]})
        _crag(_day(plan, 3))
        assert _codes(guards_v1.evaluate(plan), "finger_gap", "hard_back_to_back") == [
            ("hard_back_to_back", _d(2), "custom_pull")]

    def test_crag_block_72h_is_for_high_only(self):
        prev = _plan({}, start="2026-09-28")
        for i in (5, 6):
            _crag(_day(prev, i))
        plan = _plan({2: [_custom("custom_lo", *LOW_EX, slot="lunch")]})
        assert _codes(guards_v1.evaluate(plan, prev["weeks"][0]["days"]), "crag_block") == []


# ---------------------------------------------------------------------------
# Athlete context, suggestions
# ---------------------------------------------------------------------------

class TestAthleteContextAndReplanner:
    def test_low_session_does_not_block_the_next_day(self):
        from backend.tests.test_a293_athlete_context import _outdoor, _set_day, _state

        st = _state()
        _set_day(st, "2026-10-05", "2026-10-11", [_custom("custom_lo", *LOW_EX)])
        ctx = ac.build_athlete_context(st, "2026-10-04", outdoor_rows=_outdoor())
        sat = next(r for r in ctx["guards"]["days"] if r["date"] == "2026-10-10")
        assert not any(c["code"] == "finger_spacing" and "custom_lo" in c["detail"] for c in sat["finger_codes"])
        view = next(u for u in ctx["upcoming"] if u["session_id"] == "custom_lo")
        assert view["finger_load"] == "low" and view["finger"] is True

    def test_stale_tier_is_reported(self):
        from backend.tests.test_a293_athlete_context import _outdoor, _set_day, _state

        st = _state()
        old = _custom("custom_lo", *LOW_EX, store_tier=False)  # stored before A327 → read high
        _set_day(st, "2026-10-05", "2026-10-08", [old])
        rows = ac.build_athlete_context(st, "2026-10-04", outdoor_rows=_outdoor())["stale_custom_tags"]
        [row] = [r for r in rows if r["session_id"] == "custom_lo"]
        assert row["stored"]["finger_load"] == "high" and row["current"]["finger_load"] == "low"

    def test_high_custom_without_tier_is_not_stale(self):
        from backend.tests.test_a293_athlete_context import _outdoor, _set_day, _state

        st = _state()
        _set_day(st, "2026-10-05", "2026-10-08", [_custom("custom_mh", "max_hang_7s", store_tier=False)])
        rows = ac.build_athlete_context(st, "2026-10-04", outdoor_rows=_outdoor())["stale_custom_tags"]
        assert [r for r in rows if r["session_id"] == "custom_mh"] == []

    def test_suggestions_penalise_high_next_to_high_only(self):
        """A low session the day after a high one is not pushed down (−1000)."""
        plan = _plan({0: [_sess(STRENGTH)]})
        pool = ["finger_strength_home", AEROBIC, "flexibility_full"]
        order = [s["session_id"] for s in suggest_sessions(plan, _d(1), "home", session_pool=pool,
                                                           max_suggestions=10)]
        assert order.index(AEROBIC) < order.index("finger_strength_home")


# ---------------------------------------------------------------------------
# Planner: one clock gate, PASS 2 fixed
# ---------------------------------------------------------------------------

def _home_week(phase: str, days: int, start: str, disc: str = "lead") -> dict:
    from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _adjust_domain_weights, _build_session_pool

    slot = {"available": True, "locations": ["home"], "preferred_location": "home"}
    avail = {d: {"morning": dict(slot), "lunch": {"available": False}, "evening": dict(slot)}
             for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    profile = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45, "technique": 50,
               "endurance": 40}
    return generate_phase_week(
        phase_id=phase, domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[phase], profile),
        session_pool=_build_session_pool(phase, disc), start_date=start, availability=avail,
        allowed_locations=["home"], hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": days, "hard_day_cap_per_week": 3},
        home_equipment=["hangboard", "pullup_bar"],
    )


class TestPlanner:
    @pytest.mark.parametrize("phase", ["base", "strength_power", "power_endurance"])
    @pytest.mark.parametrize("days", [5, 6, 7])
    @pytest.mark.parametrize("start", ["2026-01-05", "2026-03-02", "2026-11-16"])
    def test_home_weeks_raise_no_finger_alert(self, phase, days, start):
        """D288 §1.3-1: home-only base weeks used to put finger_aerobic_base on
        Friday and finger_endurance_short on Saturday from PASS 2."""
        week = _home_week(phase, days, start)
        assert _codes(guards_v1.evaluate(week), *FINGER) == []
        for d in week["weeks"][0]["days"]:
            assert sum(1 for s in d["sessions"] if finger_load_of(s) == "low") <= rp.FINGER_LOW_MAX_PER_DAY

    def test_pass2_books_what_it_places(self):
        """Every finger session the planner places sits outside the 48 h of
        another high one."""
        for start in ("2026-01-05", "2026-02-02", "2026-03-02"):
            for days in (6, 7):
                week = _home_week("base", days, start)
                highs = [i for i, d in enumerate(week["weeks"][0]["days"])
                         if any(finger_load_of(s) == "high" for s in d["sessions"])]
                assert all(b - a > 1 for a, b in zip(highs, highs[1:])), (start, days, highs)

    def test_finger_days_summary_counts_low_too(self):
        week = _home_week("base", 7, "2026-01-05")
        n = sum(1 for d in week["weeks"][0]["days"] if any(finger_load_of(s) for s in d["sessions"]))
        targets = week.get("targets") or {}
        if "finger_days" in targets:
            assert targets["finger_days"] >= n - 1


def test_a300_moved_case_is_a_legal_low_placement():
    """The one a300 digest A327 moved (``split|1|base|lead|None``): PASS 2.2
    now puts finger_aerobic_base (low) on Thursday morning — 13 h after
    Wednesday evening's finger_maintenance_gym, 24 h before Friday morning's
    7/3 test. The 48 h calendar gap used to keep it out (flexibility_full took
    the slot). No finger alert on the engine's week."""
    import logging

    from backend.tests.test_a300_complementary_slots import _identity_matrix

    logging.disable(logging.WARNING)
    try:
        kw = dict(_identity_matrix())["split|1|base|lead|None"]
        week = generate_phase_week(**kw)
    finally:
        logging.disable(logging.NOTSET)
    thu = next(d for d in week["weeks"][0]["days"] if d["date"] == "2026-10-15")
    assert ("morning", AEROBIC) in [(s["slot"], s["session_id"]) for s in thu["sessions"]]
    assert _codes(guards_v1.evaluate(week), *FINGER) == []
