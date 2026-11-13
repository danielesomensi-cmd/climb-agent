"""A327 step A (D288 R1 + R2, Daniele's OK of 2026-11-13) — the weekly finger
caps and the multi-day crag rule, as ALERTS.

- ``finger_hard_cap``: more than ``FINGER_HARD_WEEKLY_MAX`` (3) finger-hard
  days in the calendar week, a hard crag day included (decision 1). The unit
  is ``stimulus.is_finger_hard_exposure``: repeaters / intermittent hangs at
  60-80 % are high for the 48 h spacing only, never in the cap (answer 2);
  indoor rope redpoint attempts in a custom are finger-high (answer 4).
- ``max_hang_cap``: more than ``MAX_HANG_WEEKLY_MAX`` (2) max-hang days.
- ``crag_block``: after ≥ 2 consecutive crag days that count, the next day a
  true rest day (a HIIT or legs lunch does not break it, decision 2), the one
  after non-hard, no finger session before 72 h after the last crag day ends
  (18:00). ``post_outdoor`` leaves the rest day to it.
- ``athlete_context``: the same rules as ``day_warnings`` — never a reason of
  ``finger_max_ok``, so the composer pool loses nothing for them (decision 3).

Nothing here is rewritten: alerts only (A301), and after a crag weekend the
following week is not regenerated (answer 3).
"""
from __future__ import annotations

import copy
from datetime import date, timedelta

from backend.engine import athlete_context as ac
from backend.engine import guards_v1
from backend.engine import retest_policy as rp
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.session_tags import derive_session_tags
from backend.engine.stimulus import (
    FINGER_HARD_CLIMB_IDS,
    is_finger_hard_exposure,
    is_finger_hard_session,
    is_max_hang_session,
)
from backend.tests.test_a293_athlete_context import _day as _ctx_day
from backend.tests.test_a293_athlete_context import _outdoor, _sess as _raw_sess, _set_day, _state

MON = "2026-10-05"
LIMIT = "limit_boulder_gym"
CONTACT = "power_contact_gym"
STRENGTH = "strength_long"
HOME = "finger_strength_home"
MAINT = "finger_maintenance_gym"
EASY = "technique_focus_gym"
HARD = "power_endurance_gym"
HIIT = "treadmill_hiit_4x4"
LEGS = "legs_maintenance_lunch"
TEST = "test_max_hang_7s"


def _d(i: int, start: str = MON) -> str:
    return (date.fromisoformat(start) + timedelta(days=i)).isoformat()


def _sess(sid: str, slot: str = "evening", **kw) -> dict:
    m = _SESSION_META[sid]
    s = {"slot": slot, "session_id": sid, "location": "gym", "gym_id": "g1", "phase_id": "strength_power",
         "intensity": m["intensity"], "tags": {"hard": m["hard"], "finger": m["finger"]},
         "constraints_applied": []}
    if m.get("test"):
        s["tags"]["test"] = True
    s.update(kw)
    return s


def _custom(sid: str, *exercise_ids: str, slot: str = "evening", **kw) -> dict:
    exercises = [{"exercise_id": e, "sets": 3} for e in exercise_ids]
    tags, intensity = derive_session_tags(exercises)
    s = {"slot": slot, "session_id": sid, "custom_session_id": sid[7:], "is_custom": True, "name": sid,
         "location": "gym", "status": "planned", "intensity": intensity, "tags": tags,
         "constraints_applied": ["custom_add"], "exercises": exercises}
    s.update(kw)
    return s


def _plan(days: dict, *, start: str = MON, hard_cap: int = 5, recovery_multiplier: float = 1.0) -> dict:
    d0 = date.fromisoformat(start)
    out_days = [{"date": (d0 + timedelta(i)).isoformat(), "sessions": copy.deepcopy(days.get(i, []))}
                for i in range(7)]
    return {"start_date": start, "plan_revision": 1,
            "profile_snapshot": {"phase_id": "strength_power", "hard_cap_per_week": hard_cap,
                                 "recovery_multiplier": recovery_multiplier},
            "weeks": [{"week_index": 1, "days": out_days}], "adaptations": []}


def _day(plan: dict, i: int) -> dict:
    return plan["weeks"][0]["days"][i]


def _crag(day: dict, status: str = "planned") -> dict:
    day.update({"outdoor_spot_name": "Berdorf", "outdoor_spot_id": "spot_0_berdorf",
                "outdoor_discipline": "lead", "outdoor_session_status": status})
    return day


def _prev_week(crag_days=(5, 6), sessions=None, status="planned") -> list:
    """The previous week's days (2026-09-28 .. 10-04), crag on the given indexes."""
    p = _plan(sessions or {}, start="2026-09-28")
    for i in crag_days:
        _crag(_day(p, i), status)
    return p["weeks"][0]["days"]


def _codes(alerts, *codes):
    return [(w["code"], w["date"], w["session_id"]) for w in alerts if not codes or w["code"] in codes]


NEW = (guards_v1.CODE_FINGER_HARD_CAP, guards_v1.CODE_MAX_HANG_CAP, guards_v1.CODE_CRAG_BLOCK)


# ---------------------------------------------------------------------------
# Constants and predicates
# ---------------------------------------------------------------------------

class TestConstants:
    def test_engineering_constants(self):
        assert rp.FINGER_HARD_WEEKLY_MAX == 3 and rp.MAX_HANG_WEEKLY_MAX == 2
        assert rp.CRAG_BLOCK_MIN_DAYS == 2 and rp.CRAG_BLOCK_FINGER_H == 72
        from backend.engine.complementary_v1 import OUTDOOR_END_HOUR, OUTDOOR_START_HOUR
        assert (OUTDOOR_START_HOUR, OUTDOOR_END_HOUR) == (8, 18)
        assert ac.FINGER_HARD_WEEKLY_MAX == 3 and ac.MAX_HANG_WEEKLY_MAX == 2 and ac.CRAG_BLOCK_FINGER_H == 72

    def test_new_codes_registered(self):
        for code in NEW:
            assert code in guards_v1.CODES
        assert guards_v1.CODE_FINGER_HARD_CAP in guards_v1._COUNT_CODES
        assert guards_v1.CODE_MAX_HANG_CAP in guards_v1._COUNT_CODES
        assert guards_v1.CODE_CRAG_BLOCK not in guards_v1._COUNT_CODES


class TestExposurePredicate:
    def test_catalog_slots_by_flags(self):
        for sid in (STRENGTH, LIMIT, CONTACT, HOME, "route_projecting_gym", TEST):
            assert is_finger_hard_exposure(_sess(sid)), sid
        for sid in (MAINT, "finger_maintenance_home", "finger_endurance_short", "finger_aerobic_base", HARD, EASY):
            assert not is_finger_hard_exposure(_sess(sid)), sid

    def test_repeaters_to_failure_are_not_an_exposure(self):
        """Answer 2: high for the 48 h spacing, not in the cap of 3 — even when
        the custom is tagged finger + hard."""
        rep = _custom("custom_rep", "repeater_hang_7_3", "intermittent_dead_hangs", "weighted_pullup")
        rep["tags"] = {"hard": True, "finger": True}
        assert is_finger_hard_session(rep)          # A288 reading, unchanged
        assert not is_finger_hard_exposure(rep)     # the cap's unit

    def test_max_limit_comp_redpoint_are_exposures(self):
        for ids in (("max_hang_7s",), ("limit_bouldering",), ("three_attempt_comp",), ("route_redpoint_attempt",),
                    ("min_edge_hang",), ("campus_bumps",)):
            assert is_finger_hard_exposure(_custom("custom_x", *ids)), ids

    def test_logged_work_decides_a_done_session(self):
        """A done strength_long whose hangs were skipped is no exposure."""
        s = _sess(STRENGTH, status="done", actual_exercises=[
            {"exercise_id": "max_hang_7s", "feedback_label": "skipped"},
            {"exercise_id": "weighted_pullup", "completed_sets": 4, "completed_reps": 3}])
        assert not is_finger_hard_exposure(s) and not is_max_hang_session(s)

    def test_max_hang_sessions(self):
        for sid in (STRENGTH, HOME, TEST, "test_max_hang_5s", "test_lp_max_5s", "test_max_hang_pullup"):
            assert is_max_hang_session(_sess(sid)), sid
        for sid in (LIMIT, CONTACT, MAINT, "test_repeater_7_3", "route_projecting_gym"):
            assert not is_max_hang_session(_sess(sid)), sid


class TestRedpointAttemptsAreFingerHigh:
    """Answer 4: indoor rope redpoint attempts in a custom count as finger-high
    (the D-Summit custom of 25/10 used to carry no finger load at all)."""

    def test_ids(self):
        assert FINGER_HARD_CLIMB_IDS == ("route_redpoint_attempt",)

    def test_derived_tags(self):
        tags, intensity = derive_session_tags([{"exercise_id": "warmup_easy_boulders"},
                                               {"exercise_id": "route_redpoint_attempt"}])
        assert tags == {"hard": True, "finger": True} and intensity == "high"

    def test_stale_tag_custom_still_counts(self):
        """A redpoint custom stored before A327 (finger False) counts through
        its exercises."""
        s = _custom("custom_summit", "route_redpoint_attempt")
        s["tags"] = {"hard": True, "finger": False}
        assert is_finger_hard_session(s) and is_finger_hard_exposure(s)

    def test_composer_pool_is_untouched(self):
        """A327 adds no restriction to the composer: its finger-hard pool list
        does not read FINGER_HARD_CLIMB_IDS."""
        assert "route_redpoint_attempt" not in ac._finger_hard_ids()


# ---------------------------------------------------------------------------
# finger_hard_cap / max_hang_cap
# ---------------------------------------------------------------------------

class TestFingerHardCap:
    def test_three_is_fine(self):
        plan = _plan({0: [_sess(STRENGTH)], 2: [_sess(LIMIT)], 4: [_sess(CONTACT)]})
        assert _codes(guards_v1.evaluate(plan), *NEW) == []

    def test_fourth_day_is_flagged(self):
        plan = _plan({0: [_sess(STRENGTH)], 2: [_sess(LIMIT)], 4: [_sess(CONTACT)], 6: [_sess(HOME)]})
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts, *NEW) == [("finger_hard_cap", _d(6), HOME)]
        w = next(a for a in alerts if a["code"] == "finger_hard_cap")
        assert w["count"] == 4 and w["cap"] == 3
        assert {x["date"] for x in w["with"]} == {_d(0), _d(2), _d(4)}
        assert "4 finger-hard days" in w["message"] and "cap is 3" in w["message"]

    def test_daniele_0510_custom_plus_crag_weekend(self):
        """Week of 05/10 (Phase 1 §4): custom max hang Mon, custom limit Thu,
        crag Sat + Sun = 4 — an alert on the latest session, nothing moved."""
        plan = _plan({0: [_custom("custom_mh", "max_hang_7s")], 3: [_custom("custom_lim", "limit_bouldering")]})
        _crag(_day(plan, 5))
        _crag(_day(plan, 6))
        before = copy.deepcopy(plan)
        alerts = guards_v1.evaluate(plan, today=MON)
        assert _codes(alerts, *NEW) == [("finger_hard_cap", _d(3), "custom_lim")]
        w = next(a for a in alerts if a["code"] == "finger_hard_cap")
        assert {"date": _d(5), "slot": None, "session_id": None} in w["with"]
        assert w["user_owned"] is True
        assert plan == before

    def test_repeaters_do_not_count(self):
        """Answer 2: finger_maintenance / endurance_short and a repeater custom
        on top of three exposures — no cap alert."""
        rep = _custom("custom_rep", "repeater_hang_7_3", "weighted_pullup", "intermittent_dead_hangs")
        rep["tags"] = {"hard": True, "finger": True}
        plan = _plan({0: [_sess(STRENGTH)], 2: [_sess(LIMIT)], 4: [_sess(CONTACT)], 6: [rep]})
        assert _codes(guards_v1.evaluate(plan), "finger_hard_cap") == []
        plan = _plan({0: [_sess(STRENGTH)], 2: [_sess(LIMIT)], 4: [_sess(CONTACT)], 6: [_sess(MAINT)]})
        assert _codes(guards_v1.evaluate(plan), "finger_hard_cap") == []

    def test_redpoint_custom_counts(self):
        """Answer 4: the week of 19/10 goes from 1 to 2 with D-Summit; here the
        redpoint custom is the 4th exposure."""
        plan = _plan({0: [_sess(STRENGTH)], 2: [_sess(LIMIT)], 4: [_sess(CONTACT)],
                      6: [_custom("custom_summit", "warmup_easy_boulders", "route_redpoint_attempt")]})
        assert _codes(guards_v1.evaluate(plan), "finger_hard_cap") == [("finger_hard_cap", _d(6), "custom_summit")]

    def test_skipped_does_not_count_done_counts_history_not_flagged(self):
        plan = _plan({0: [_sess(STRENGTH, status="done")], 2: [_sess(LIMIT, status="skipped")],
                      3: [_sess(CONTACT)], 5: [_sess(HOME)]})
        assert _codes(guards_v1.evaluate(plan), "finger_hard_cap") == []
        _day(plan, 2)["sessions"][0]["status"] = "done"
        assert _codes(guards_v1.evaluate(plan, today=_d(3)), "finger_hard_cap") == [
            ("finger_hard_cap", _d(5), HOME)]
        # Everything past today is history: nothing to flag.
        assert _codes(guards_v1.evaluate(plan, today=_d(6)), "finger_hard_cap") == []

    def test_count_code_is_not_new_when_a_session_is_added_elsewhere(self):
        plan = _plan({0: [_sess(STRENGTH)], 2: [_sess(LIMIT)], 4: [_sess(CONTACT)], 6: [_sess(HOME)]})
        after = copy.deepcopy(plan)
        _day(after, 1)["sessions"].append(_sess(EASY))
        assert [w for w in guards_v1.new_warnings(guards_v1.evaluate(plan), guards_v1.evaluate(after))
                if w["code"] == "finger_hard_cap"] == []


class TestMaxHangCap:
    def test_third_max_hang_day_is_flagged(self):
        plan = _plan({0: [_sess(STRENGTH)], 2: [_sess(HOME, location="home")], 4: [_sess(TEST)]})
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts, *NEW) == [("max_hang_cap", _d(4), TEST)]
        w = next(a for a in alerts if a["code"] == "max_hang_cap")
        assert (w["count"], w["cap"]) == (3, 2)

    def test_two_is_fine_and_limit_is_not_a_max_hang(self):
        plan = _plan({0: [_sess(STRENGTH)], 2: [_sess(LIMIT)], 4: [_sess(HOME)]})
        assert _codes(guards_v1.evaluate(plan), "max_hang_cap") == []


# ---------------------------------------------------------------------------
# crag_block
# ---------------------------------------------------------------------------

class TestCragBlock:
    def test_saturday_sunday_block(self):
        """Phase 1 shape: crag Sat + Sun → Monday rest, Tuesday no hard, finger
        from Wednesday evening (Sunday 18:00 + 72 h)."""
        plan = _plan({0: [_sess(EASY)], 1: [_sess(LIMIT)], 2: [_sess(MAINT, slot="lunch")],
                      4: [_sess(STRENGTH)]})
        alerts = guards_v1.evaluate(plan, _prev_week())
        got = [(w["date"], w["session_id"], w["detail"]) for w in alerts if w["code"] == "crag_block"]
        assert got == [(_d(0), EASY, "rest_day"), (_d(1), LIMIT, "no_hard"), (_d(2), MAINT, "finger_72h")]
        w = next(a for a in alerts if a["code"] == "crag_block")
        assert w["crag_days"] == ["2026-10-03", "2026-10-04"]
        assert w["finger_ok_from"] == "2026-10-07T18:00"
        assert [x["date"] for x in w["with"]] == ["2026-10-03", "2026-10-04"]
        # One alert per session: the Monday is crag_block's, not post_outdoor's.
        assert _codes(alerts, "post_outdoor") == []

    def test_wednesday_evening_is_fine_lunch_is_not(self):
        plan = _plan({2: [_sess(MAINT, slot="evening")]})
        assert _codes(guards_v1.evaluate(plan, _prev_week()), "crag_block") == []
        plan = _plan({2: [_sess(MAINT, slot="lunch")]})
        assert _codes(guards_v1.evaluate(plan, _prev_week()), "crag_block") == [("crag_block", _d(2), MAINT)]

    def test_hiit_and_legs_lunch_keep_the_rest_day(self):
        """Decision 2: a HIIT or legs lunch does not break the true rest day."""
        plan = _plan({0: [_sess(HIIT, slot="lunch", slot_role="complementary")],
                      1: [_sess(LEGS, slot="lunch", slot_role="complementary")]})
        assert _codes(guards_v1.evaluate(plan, _prev_week()), "crag_block") == []
        plan = _plan({0: [_sess("prehab_maintenance", slot="lunch")]})
        assert _codes(guards_v1.evaluate(plan, _prev_week()), "crag_block") == []

    def test_non_hard_finger_on_day_two(self):
        plan = _plan({1: [_sess(EASY)], 3: [_sess(LIMIT, slot="morning")]})
        assert _codes(guards_v1.evaluate(plan, _prev_week()), "crag_block") == []
        plan = _plan({1: [_sess(MAINT)]})
        [w] = [w for w in guards_v1.evaluate(plan, _prev_week()) if w["code"] == "crag_block"]
        assert w["detail"] == "finger_72h" and w["date"] == _d(1)

    def test_one_crag_day_is_not_a_block(self):
        plan = _plan({0: [_sess(EASY)], 1: [_sess(LIMIT)]})
        alerts = guards_v1.evaluate(plan, _prev_week(crag_days=(6,)))
        assert _codes(alerts, "crag_block") == []
        assert _codes(alerts, "post_outdoor") == []  # technique is neither hard nor finger
        plan = _plan({0: [_sess(LIMIT)]})
        assert _codes(guards_v1.evaluate(plan, _prev_week(crag_days=(6,))), "post_outdoor") == [
            ("post_outdoor", _d(0), LIMIT)]

    def test_easy_logged_crag_days_are_not_a_block(self):
        state = {"performance": {"current_level": {"sport": {"worked": {"grade": "8a"}}}}}
        rows = [{"entry": {"date": d, "spot_name": "Vercors", "discipline": "lead",
                           "routes": [{"name": "R", "grade": "7a", "attempts": [{"result": "sent"}]}]}}
                for d in ("2026-10-03", "2026-10-04")]
        prev = _prev_week()
        for day in prev:
            if day.get("outdoor_spot_name"):
                day["outdoor_session_status"] = "done"
        plan = _plan({0: [_sess(EASY)]})
        assert _codes(guards_v1.evaluate(plan, prev, None, state, outdoor_rows=rows), "crag_block") == []
        hard_rows = copy.deepcopy(rows)
        for r in hard_rows:
            r["entry"]["routes"][0]["grade"] = "8a"
        assert _codes(guards_v1.evaluate(plan, prev, None, state, outdoor_rows=hard_rows), "crag_block") == [
            ("crag_block", _d(0), EASY)]

    def test_block_inside_the_week(self):
        """Tue + Wed → Thu rest, Fri non-hard, finger from Saturday 18:00."""
        plan = _plan({3: [_sess(EASY)], 4: [_sess(HARD)], 5: [_sess(MAINT, slot="lunch")],
                      6: [_sess(LIMIT)]})
        _crag(_day(plan, 1))
        _crag(_day(plan, 2))
        got = [(w["date"], w["detail"]) for w in guards_v1.evaluate(plan) if w["code"] == "crag_block"]
        assert got == [(_d(3), "rest_day"), (_d(4), "no_hard"), (_d(5), "finger_72h")]

    def test_three_day_block_counts_from_the_last(self):
        plan = _plan({0: [_sess(EASY)], 1: [_sess(LIMIT)]})
        got = [(w["date"], w["detail"], tuple(w["crag_days"]))
               for w in guards_v1.evaluate(plan, _prev_week(crag_days=(4, 5, 6))) if w["code"] == "crag_block"]
        assert got == [(_d(0), "rest_day", ("2026-10-02", "2026-10-03", "2026-10-04")),
                       (_d(1), "no_hard", ("2026-10-02", "2026-10-03", "2026-10-04"))]

    def test_history_is_not_flagged_and_nothing_is_rewritten(self):
        plan = _plan({0: [_sess(EASY, status="done")], 1: [_sess(LIMIT)]})
        prev = _prev_week(status="done")  # done, no route log: counts (B372 outdoor_unlogged)
        before = copy.deepcopy((plan, prev))
        alerts = guards_v1.evaluate(plan, prev, today=_d(1))
        assert [(w["date"], w["detail"]) for w in alerts if w["code"] == "crag_block"] == [(_d(1), "no_hard")]
        assert (plan, prev) == before

    def test_deterministic(self):
        plan = _plan({0: [_sess(EASY)], 1: [_sess(LIMIT)], 2: [_sess(MAINT, slot="lunch")]})
        assert guards_v1.evaluate(plan, _prev_week()) == guards_v1.evaluate(copy.deepcopy(plan), _prev_week())


class TestWeeksWithoutTheNewShapesAreUnchanged:
    def test_clean_plans(self):
        assert guards_v1.evaluate(_plan({0: [_sess(STRENGTH)], 2: [_sess(LIMIT)], 4: [_sess(EASY)]})) == []


# ---------------------------------------------------------------------------
# athlete_context: advisories, never a restriction
# ---------------------------------------------------------------------------

TODAY = "2026-10-04"
NEXT = "2026-10-05"


def _actx(st):
    return ac.build_athlete_context(st, TODAY, outdoor_rows=_outdoor())


class TestAthleteContext:
    def test_finger_cap_is_an_advisory(self):
        """Next week: limit Mon, power_contact Wed, strength_long Fri = 3. The
        Sunday has no finger reason: finger_max_ok stays True, the cap is a
        day warning."""
        ctx = _actx(_state())
        sun = _ctx_day(ctx, "2026-10-11")
        assert sun["finger_max_ok"] is True and sun["finger_codes"] == []
        [code] = [c for c in sun["day_warning_codes"] if c["code"] == "finger_hard_cap"]
        assert code["detail"] == "3/3: 2026-10-05, 2026-10-07, 2026-10-09"
        assert any("tetto dita-hard" in w and "solo avviso" in w for w in sun["day_warnings"])
        # Not on a day that is already finger-hard.
        assert not any(c["code"] == "finger_hard_cap" for c in _ctx_day(ctx, "2026-10-09")["day_warning_codes"])

    def test_composer_loses_nothing_for_an_advisory(self):
        st = _state()
        ctx = _actx(st)
        view = ac.composer_guard_view(st, ctx, "2026-10-11", ac.load_exercise_catalog())
        assert view["finger_max_ok"] is True
        assert not (set(view["exclude_ids"]) & ac._finger_hard_ids())

    def test_max_hang_cap_advisory(self):
        st = _state()
        _set_day(st, NEXT, "2026-10-07", [_raw_sess("evening", "finger_strength_home", tags={"hard": True, "finger": True})])
        ctx = _actx(st)
        sat = _ctx_day(ctx, "2026-10-10")
        # The finger-hard count is 3 (Mon, Wed, Fri) as well: both caps advise.
        assert {c["code"] for c in sat["day_warning_codes"]} >= {"max_hang_cap", "finger_hard_cap"}
        fc = ctx["guards"]["finger_cap"]
        assert fc["week_start"] == "2026-09-28"  # the current week (TODAY is a Sunday)

    def test_crag_block_advisories(self):
        st = _state()
        wk = st["week_plans"][NEXT]["weeks"][0]["days"]
        _set_day(st, NEXT, "2026-10-09", [])
        for day in wk:
            if day["date"] in ("2026-10-07", "2026-10-08"):
                day["sessions"] = []
                _crag(day)
        ctx = _actx(st)
        fri, sat, sun = (_ctx_day(ctx, d) for d in ("2026-10-09", "2026-10-10", "2026-10-11"))
        assert {"code": "crag_block", "detail": "rest_day 2026-10-07..2026-10-08"} in fri["day_warning_codes"]
        assert {"code": "crag_block", "detail": "no_hard 2026-10-07..2026-10-08"} in sat["day_warning_codes"]
        assert any(c["detail"].startswith("finger_72h") for c in sun["day_warning_codes"])
        assert any("oggi solo dalle 18:00" in w for w in sun["day_warnings"])
        [b] = ctx["guards"]["crag_blocks"]
        assert b == {"crag_days": ["2026-10-07", "2026-10-08"], "rest_day": "2026-10-09",
                     "no_hard_day": "2026-10-10", "finger_ok_from": "2026-10-11T18:00"}
        # The crag-block codes never enter a verdict list.
        for row in ctx["guards"]["days"]:
            for key in ("finger_codes", "pull_codes", "hiit_codes"):
                assert not any(c["code"] in ("crag_block", "finger_hard_cap", "max_hang_cap") for c in row[key])

    def test_renderers(self):
        st = _state()
        ctx = _actx(st)
        txt = ac.render_text(ctx, state=st, outdoor_rows=_outdoor())
        guards = txt[txt.index("## Guardie"):txt.index("## Prossimi")]
        assert "Giorni dita-hard settimana (falesia compresa):" in guards
        assert "AVVISO: tetto dita-hard" in guards
        coach = ac.render_coach_block(ctx, max_chars=20000)
        assert "advisory, alert only (the week's finger-hard cap is reached" in coach
        comp = ac.render_composer_block(ctx, state=st, day="2026-10-11", max_chars=20000)
        assert "Advisory (an alert the athlete will see, not a restriction)" in comp
        assert "NO max finger work" not in comp
