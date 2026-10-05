"""B372 — outdoor days count in the fatigue ALERTS.

B-OUTDOOR-FATIGUE-BLIND: a day at the crag was invisible to every guard. The
only outdoor alert (``post_outdoor``) needed a completed day with a load of 65,
and in 37 real sessions the load never got past 53. Daniele (2026-10-05):
guards are alerts only, nothing is rewritten.

Covered here:

- ``stimulus.outdoor_fatigue_days``: which outdoor days count (planned, logged
  hard, big load, completed without a route log) and which do not (a measured
  easy day); a bare ``outdoor_slot`` (availability, not a crag day); a past
  planned day never completed; an ungradable route; a multi-crag load sum; a
  logged day without a plan block; no redpoint;
- ``guards_v1``: ``post_outdoor`` (Saturday at Berdorf → Sunday finger session,
  planned or logged, across the week boundary), ``finger_gap`` both ways and
  with a 2-day spacing, ``finger_test_72h``, ``hiit_near_max``, ``hard_cap`` —
  one alert per pair, the crag day never flagged itself, history not flagged;
  a weekend crag past the cap; a hard session the day before a crag; a Monday
  crag of the next week; a planner week with an outdoor-only day unchanged;
- ``check_insertion`` reads the route log for ``added_guard_warnings``;
- determinism, no mutation, nothing rewritten after an outdoor override;
- weeks without outdoor: no new alert;
- ``athlete_context`` guards: the day after / before a planned crag day, HIIT,
  hard-day count;
- ``build_guard_warnings`` reads the outdoor route log when given the user;
- B-OUTDOOR-LOAD-FIELD-DROP: ``outdoor_load_score`` survives the per-field merge.
"""
from __future__ import annotations

import copy
import json
from datetime import date, timedelta

from backend.engine import guards_v1
from backend.engine import athlete_context as ac
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.replanner_v1 import _merge_user_content, apply_day_override
from backend.engine.stimulus import (
    OUTDOOR_REASON_HARD,
    OUTDOOR_REASON_LOAD,
    OUTDOOR_REASON_PLANNED,
    OUTDOOR_REASON_UNLOGGED,
    outdoor_fatigue_days,
)

MON = "2026-10-05"
FINGER = "strength_long"          # hard + finger + pulling (max)
LIMIT = "limit_boulder_gym"       # hard + finger
HARD = "power_endurance_gym"      # hard, not finger
EASY = "technique_focus_gym"      # medium
HIIT = "treadmill_hiit_4x4"       # HIIT, not hard
TEST = "test_max_hang_7s"

ATHLETE = {"performance": {"current_level": {"sport": {"worked": {"grade": "8a"}}}}}


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


def _plan(days: dict, *, start: str = MON, hard_cap: int = 3, recovery_multiplier: float = 1.0) -> dict:
    d0 = date.fromisoformat(start)
    out_days = [{"date": (d0 + timedelta(i)).isoformat(), "sessions": copy.deepcopy(days.get(i, []))}
                for i in range(7)]
    return {"start_date": start, "plan_revision": 1,
            "profile_snapshot": {"phase_id": "strength_power", "hard_cap_per_week": hard_cap,
                                 "recovery_multiplier": recovery_multiplier},
            "weeks": [{"week_index": 1, "days": out_days}], "adaptations": []}


def _day(plan: dict, i: int) -> dict:
    return plan["weeks"][0]["days"][i]


def _crag(plan: dict, i: int, status: str = "planned", **kw) -> None:
    _day(plan, i).update({"outdoor_spot_name": "Berdorf", "outdoor_spot_id": "spot_0_berdorf",
                          "outdoor_discipline": "lead", "outdoor_session_status": status, **kw})


def _log(d: str, *grades: str, load=None) -> dict:
    e = {"date": d, "spot_name": "Berdorf", "discipline": "lead",
         "routes": [{"name": f"R{i}", "grade": g, "attempts": [{"result": "fell"}]} for i, g in enumerate(grades)]}
    if load is not None:
        e["load_score"] = load
    return {"entry": e}


def _codes(alerts):
    return [(w["code"], w["date"], w["session_id"]) for w in alerts]


# ---------------------------------------------------------------------------
# stimulus.outdoor_fatigue_days
# ---------------------------------------------------------------------------

class TestOutdoorFatigueDays:
    def _days(self, plan):
        return plan["weeks"][0]["days"]

    def test_planned_counts(self):
        plan = _plan({})
        _crag(plan, 5)
        out = outdoor_fatigue_days({}, self._days(plan), load_threshold=65)
        assert list(out) == [_d(5)]
        assert out[_d(5)]["reason"] == OUTDOOR_REASON_PLANNED and out[_d(5)]["status"] == "planned"
        assert out[_d(5)]["spot"] == "Berdorf"

    def test_bare_outdoor_slot_is_availability_not_a_crag_day(self):
        # Review: the planner's outdoor_slot is never marked done and nothing
        # clears it — counting it gave permanent alerts on planner weeks.
        plan = _plan({})
        _day(plan, 5)["outdoor_slot"] = True
        assert outdoor_fatigue_days({}, self._days(plan), load_threshold=65) == {}
        # Used for the gym instead (converted slot): still nothing.
        _day(plan, 5)["sessions"] = [_sess(EASY)]
        assert outdoor_fatigue_days({}, self._days(plan), load_threshold=65) == {}

    def test_bare_outdoor_slot_counts_through_its_log(self):
        plan = _plan({})
        _day(plan, 5)["outdoor_slot"] = True
        out = outdoor_fatigue_days(ATHLETE, self._days(plan), load_threshold=65,
                                   outdoor_rows=[_log(_d(5), "8a")])
        assert out[_d(5)]["reason"] == OUTDOOR_REASON_HARD

    def test_past_declared_day_never_completed_does_not_count(self):
        plan = _plan({})
        _crag(plan, 5)  # planned, never done, never logged
        assert outdoor_fatigue_days({}, self._days(plan), load_threshold=65, today=_d(6)) == {}
        # Today and later: still planned, still counts.
        assert _d(5) in outdoor_fatigue_days({}, self._days(plan), load_threshold=65, today=_d(5))
        assert _d(5) in outdoor_fatigue_days({}, self._days(plan), load_threshold=65)

    def test_ungradable_route_is_unknown_not_easy(self):
        plan = _plan({})
        _crag(plan, 5, "done")
        out = outdoor_fatigue_days(ATHLETE, self._days(plan), load_threshold=65,
                                   outdoor_rows=[_log(_d(5), "6a", "???")])
        assert out[_d(5)]["reason"] == OUTDOOR_REASON_UNLOGGED

    def test_multi_crag_day_load_is_the_sum(self):
        rows = [_log(_d(5), load=40), _log(_d(5), load=30)]
        rows[1]["entry"]["spot_name"] = "Freyr"
        # Same entry twice (rows + state copy) counts once.
        state = {"outdoor_log": [dict(rows[0]["entry"])]}
        out = outdoor_fatigue_days(state, [], load_threshold=65, outdoor_rows=rows)
        assert out[_d(5)]["reason"] == OUTDOOR_REASON_LOAD and out[_d(5)]["load"] == 70

    def test_done_without_log_counts_conservatively(self):
        plan = _plan({})
        _crag(plan, 5, "done", outdoor_load_score=30)
        out = outdoor_fatigue_days(ATHLETE, self._days(plan), load_threshold=65)
        assert out[_d(5)]["reason"] == OUTDOOR_REASON_UNLOGGED and out[_d(5)]["load"] == 30

    def test_done_logged_hard(self):
        # Daniele's 2026-10-03 Berdorf: load 30, an 8a tried → hard.
        plan = _plan({})
        _crag(plan, 5, "done", outdoor_load_score=30)
        out = outdoor_fatigue_days(ATHLETE, self._days(plan), load_threshold=65,
                                   outdoor_rows=[_log(_d(5), "6b", "7b", "8a")])
        assert out[_d(5)]["reason"] == OUTDOOR_REASON_HARD and out[_d(5)]["grade"] == "8a"

    def test_done_logged_easy_does_not_count(self):
        plan = _plan({})
        _crag(plan, 5, "done", outdoor_load_score=30)
        out = outdoor_fatigue_days(ATHLETE, self._days(plan), load_threshold=65,
                                   outdoor_rows=[_log(_d(5), "6b+", "6c")])
        assert out == {}

    def test_big_load_counts_even_when_easy(self):
        plan = _plan({})
        _crag(plan, 5, "done", outdoor_load_score=80)
        out = outdoor_fatigue_days(ATHLETE, self._days(plan), load_threshold=65,
                                   outdoor_rows=[_log(_d(5), "6b+", "6c")])
        assert out[_d(5)]["reason"] == OUTDOOR_REASON_LOAD

    def test_logged_day_without_plan_block(self):
        rows = [_log(_d(2), "7c+"), _log(_d(3), "6a", load=70), _log(_d(4), "6a")]
        out = outdoor_fatigue_days(ATHLETE, [], load_threshold=65, outdoor_rows=rows,
                                   since=_d(0), until=_d(6))
        assert {d: o["reason"] for d, o in out.items()} == {
            _d(2): OUTDOOR_REASON_HARD, _d(3): OUTDOOR_REASON_LOAD}

    def test_no_redpoint_means_unknown_not_easy(self):
        plan = _plan({})
        _crag(plan, 5, "done")
        out = outdoor_fatigue_days({}, self._days(plan), load_threshold=65,
                                   outdoor_rows=[_log(_d(5), "6b+")])
        assert out[_d(5)]["reason"] == OUTDOOR_REASON_UNLOGGED

    def test_window(self):
        plan = _plan({})
        _crag(plan, 1)
        _crag(plan, 5)
        out = outdoor_fatigue_days({}, self._days(plan), load_threshold=65, since=_d(2), until=_d(6))
        assert list(out) == [_d(5)]


# ---------------------------------------------------------------------------
# guards_v1
# ---------------------------------------------------------------------------

class TestGuards:
    def test_saturday_crag_then_sunday_finger_session(self):
        """The brief's example: Saturday at Berdorf, Sunday finger session."""
        plan = _plan({6: [_sess(LIMIT)]})
        _crag(plan, 5)
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts) == [("post_outdoor", _d(6), LIMIT)]  # one alert, not finger_gap too
        w = alerts[0]
        assert w["with"] == [{"date": _d(5), "slot": None, "session_id": None}]
        assert w["outdoor"]["reason"] == OUTDOOR_REASON_PLANNED and w["outdoor"]["spot"] == "Berdorf"
        assert "Berdorf" in w["message"]

    def test_logged_hard_day_via_outdoor_rows(self):
        plan = _plan({6: [_sess(LIMIT)]})
        _crag(plan, 5, "done", outdoor_load_score=30)
        alerts = guards_v1.evaluate(plan, None, None, ATHLETE, outdoor_rows=[_log(_d(5), "8a")])
        assert _codes(alerts) == [("post_outdoor", _d(6), LIMIT)]
        assert alerts[0]["outdoor"]["reason"] == OUTDOOR_REASON_HARD
        assert "8a" in alerts[0]["message"]
        easy = guards_v1.evaluate(plan, None, None, ATHLETE, outdoor_rows=[_log(_d(5), "6a")])
        assert easy == []

    def test_easy_session_after_crag_is_fine(self):
        plan = _plan({6: [_sess(EASY)]})
        _crag(plan, 5)
        assert guards_v1.evaluate(plan) == []

    def test_prev_week_sunday_crag(self):
        prev = _plan({}, start=_d(-7))
        _crag(prev, 6)
        plan = _plan({0: [_sess(FINGER)]})
        alerts = guards_v1.evaluate(plan, prev["weeks"][0]["days"])
        assert _codes(alerts) == [("post_outdoor", _d(0), FINGER)]

    def test_logged_day_without_plan_block_in_prev_week(self):
        plan = _plan({0: [_sess(FINGER)]})
        prev_days = [{"date": _d(-1), "sessions": []}]
        state = {**ATHLETE, "outdoor_log": [_log(_d(-1), "7c+")["entry"]]}
        assert _codes(guards_v1.evaluate(plan, prev_days, None, state)) == [("post_outdoor", _d(0), FINGER)]

    def test_finger_session_the_day_before_a_crag_day(self):
        plan = _plan({4: [_sess(FINGER)]})
        _crag(plan, 5)
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts) == [("finger_gap", _d(4), FINGER)]
        assert alerts[0]["with"] == [{"date": _d(5), "slot": None, "session_id": None}]
        assert "before the outdoor day at Berdorf" in alerts[0]["message"]

    def test_two_day_spacing(self):
        plan = _plan({2: [_sess(LIMIT)]}, recovery_multiplier=2.0)
        _crag(plan, 0, "done")
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts) == [("finger_gap", _d(2), LIMIT)]
        assert alerts[0]["outdoor"]["date"] == _d(0)

    def test_finger_test_after_crag(self):
        plan = _plan({3: [_sess(TEST)]})
        _crag(plan, 1)
        alerts = [w for w in guards_v1.evaluate(plan) if w["code"] == "finger_test_72h"]
        assert _codes(alerts) == [("finger_test_72h", _d(3), TEST)]
        assert alerts[0]["outdoor"]["date"] == _d(1)

    def test_hiit_before_crag(self):
        plan = _plan({4: [_sess(HIIT, slot="lunch")]})
        _crag(plan, 5)
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts) == [("hiit_near_max", _d(4), HIIT)]
        assert alerts[0]["with"] == [{"date": _d(5), "slot": None, "session_id": None}]

    def test_hiit_near_a_max_and_a_crag_is_one_alert(self):
        plan = _plan({4: [_sess(HIIT, slot="lunch"), _sess(FINGER)]})
        _crag(plan, 5)
        hiit = [w for w in guards_v1.evaluate(plan) if w["code"] == "hiit_near_max"]
        assert len(hiit) == 1 and len(hiit[0]["with"]) == 2

    def test_crag_day_is_a_hard_day_of_the_week(self):
        plan = _plan({0: [_sess(HARD)], 4: [_sess(HARD)]}, hard_cap=2)
        assert guards_v1.evaluate(plan) == []
        _crag(plan, 2)
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts) == [("hard_cap", _d(4), HARD)]
        assert alerts[0]["count"] == 3
        assert {"date": _d(2), "slot": None, "session_id": None} in alerts[0]["with"]

    def test_crag_day_past_the_cap_at_the_end_of_the_week(self):
        # Review: the weekend crag day is the common case — it has no session
        # to flag, so the latest hard session is flagged instead.
        plan = _plan({0: [_sess(HARD)], 2: [_sess(HARD)]}, hard_cap=2)
        _crag(plan, 5)
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts) == [("hard_cap", _d(2), HARD)]
        assert alerts[0]["count"] == 3
        assert {"date": _d(5), "slot": None, "session_id": None} in alerts[0]["with"]

    def test_finger_test_the_day_after_a_crag_is_one_alert(self):
        plan = _plan({6: [_sess(TEST)]})
        _crag(plan, 5)
        assert _codes(guards_v1.evaluate(plan)) == [("post_outdoor", _d(6), TEST)]

    def test_finger_gap_session_and_crag_is_one_alert(self):
        plan = _plan({2: [_sess(FINGER)], 3: [_sess(LIMIT)]}, recovery_multiplier=2.0)
        _crag(plan, 5)
        gaps = [w for w in guards_v1.evaluate(plan) if w["code"] == "finger_gap" and w["date"] == _d(3)]
        assert len(gaps) == 1
        assert {"date": _d(5), "slot": None, "session_id": None} in gaps[0]["with"]
        assert any(w["session_id"] == FINGER for w in gaps[0]["with"])

    def test_hard_session_the_day_before_a_crag_day(self):
        plan = _plan({4: [_sess(HARD)]})
        _crag(plan, 5)
        alerts = guards_v1.evaluate(plan)
        assert _codes(alerts) == [("hard_back_to_back", _d(4), HARD)]
        assert alerts[0]["outdoor"]["date"] == _d(5)

    def test_sunday_finger_before_next_monday_crag(self):
        plan = _plan({6: [_sess(FINGER)]})
        nxt = _plan({}, start=_d(7))
        _crag(nxt, 0)
        assert guards_v1.evaluate(plan) == []
        alerts = guards_v1.evaluate(plan, next_days=nxt["weeks"][0]["days"])
        assert _codes(alerts) == [("finger_gap", _d(6), FINGER)]
        # Next week's sessions are never read.
        nxt2 = _plan({0: [_sess(LIMIT)]}, start=_d(7))
        assert guards_v1.evaluate(plan, next_days=nxt2["weeks"][0]["days"]) == []

    def test_past_planned_crag_day_does_not_alert(self):
        plan = _plan({6: [_sess(LIMIT)]})
        _crag(plan, 5)  # planned, the athlete did not go
        assert guards_v1.evaluate(plan, None, _d(6)) == []

    def test_planner_week_with_outdoor_only_day_gets_no_outdoor_alert(self):
        """Review: a week the planner generated on its own (outdoor-only
        availability day → bare outdoor_slot) gets exactly the alerts it had
        without the slot — the planner's spacing ignores the slot."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent))
        from test_a300_complementary_slots import daniele_availability, days_of, plan as gen

        for dn in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            av = daniele_availability()
            av[dn]["evening"] = {"available": True, "locations": ["outdoor"], "preferred_location": "outdoor",
                                 "role": "primary"}
            wp = gen("strength_power", availability=av)
            assert any(d.get("outdoor_slot") for d in days_of(wp))
            stripped = copy.deepcopy(wp)
            for d in days_of(stripped):
                d.pop("outdoor_slot", None)
            got = guards_v1.evaluate(wp, None, "2026-10-12", {})
            assert got == guards_v1.evaluate(stripped, None, "2026-10-12", {})
            assert all("outdoor" not in w for w in got)

    def test_history_is_not_flagged(self):
        plan = _plan({6: [_sess(LIMIT, status="done")]})
        _crag(plan, 5, "done")
        assert guards_v1.evaluate(plan) == []
        plan = _plan({6: [_sess(LIMIT)]})
        _crag(plan, 5, "done")
        assert guards_v1.evaluate(plan, None, _d(7)) == []

    def test_no_outdoor_no_new_alert(self):
        plan = _plan({0: [_sess(HARD)], 2: [_sess(EASY)], 4: [_sess(LIMIT)], 6: [_sess(EASY)]})
        assert guards_v1.evaluate(plan) == []
        assert guards_v1.evaluate(plan, None, None, ATHLETE, outdoor_rows=[]) == []
        assert all("outdoor" not in w for w in guards_v1.evaluate(_plan({0: [_sess(FINGER)], 1: [_sess(LIMIT)]})))

    def test_deterministic_and_pure(self):
        plan = _plan({4: [_sess(FINGER), _sess(HIIT, slot="lunch")], 6: [_sess(LIMIT)], 0: [_sess(HARD)]},
                     hard_cap=2)
        _crag(plan, 5)
        _crag(plan, 1, "done", outdoor_load_score=30)
        rows = [_log(_d(1), "8a")]
        before = copy.deepcopy(plan)
        a = guards_v1.evaluate(plan, None, MON, ATHLETE, outdoor_rows=rows)
        b = guards_v1.evaluate(copy.deepcopy(plan), None, MON, copy.deepcopy(ATHLETE),
                               outdoor_rows=copy.deepcopy(rows))
        assert a == b and plan == before
        json.dumps(a)

    def test_outdoor_override_rewrites_nothing_and_alerts(self):
        plan = _plan({5: [_sess(EASY)], 6: [_sess(LIMIT)]})
        out = apply_day_override(plan, intent="outdoor_projecting", location="outdoor", reference_date=_d(5),
                                 target_date=_d(5), spot_name="Berdorf", spot_id="spot_0_berdorf")
        assert _day(out, 6) == _day(plan, 6)  # Sunday untouched
        assert ("post_outdoor", _d(6), LIMIT) in _codes(guards_v1.evaluate(out))


# ---------------------------------------------------------------------------
# athlete_context guards
# ---------------------------------------------------------------------------

def _state_with(plan: dict) -> dict:
    return {**copy.deepcopy(ATHLETE), "week_plans": {plan["start_date"]: plan},
            "planning_prefs": {"hard_day_cap_per_week": 3}}


class TestAthleteContextGuards:
    def _rows(self, state, rows=None):
        g = ac._guards(state, date.fromisoformat(MON), None, rows)
        return {r["date"]: r for r in g["days"]}, g

    def test_planned_crag_blocks_finger_max_around_it(self):
        plan = _plan({})
        _crag(plan, 5)
        rows, _g = self._rows(_state_with(plan))
        assert rows[_d(5)]["finger_hard_today"] and rows[_d(5)]["finger_hard_today_sessions"] == ["outdoor_planned"]
        for d in (_d(4), _d(6)):
            assert not rows[d]["finger_max_ok"]
            assert any(c["code"] == "finger_hard_adjacent" and _d(5) in c["detail"] for c in rows[d]["finger_codes"])
        assert rows[_d(2)]["finger_max_ok"]

    def test_hiit_and_hard_days(self):
        plan = _plan({0: [_sess(HARD)]})
        _crag(plan, 5)
        rows, g = self._rows(_state_with(plan))
        assert not rows[_d(4)]["hiit_ok"] and not rows[_d(5)]["hiit_ok"]
        assert rows[_d(2)]["hiit_ok"]
        assert g["hard_cap"]["hard_days"] == [_d(0), _d(5)]

    def test_logged_easy_day_does_not_count(self):
        plan = _plan({})
        _crag(plan, 0, "done", outdoor_load_score=20)
        rows, _g = self._rows(_state_with(plan), [_log(_d(0), "6a")])
        assert rows[_d(1)]["finger_max_ok"]
        rows, _g = self._rows(_state_with(plan), [_log(_d(0), "8a")])
        assert not rows[_d(1)]["finger_max_ok"]
        assert rows[_d(0)]["finger_hard_today_sessions"] == ["outdoor_hard"]  # not listed twice

    def test_without_outdoor_unchanged(self):
        plan = _plan({0: [_sess(HARD)], 3: [_sess(LIMIT)]})
        rows, g = self._rows(_state_with(plan))
        assert all("outdoor" not in " ".join(r["finger_hard_today_sessions"]) for r in rows.values())
        assert g["hard_cap"]["hard_days"] == [_d(0), _d(3)]


# ---------------------------------------------------------------------------
# API plumbing + B-OUTDOOR-LOAD-FIELD-DROP
# ---------------------------------------------------------------------------

def test_build_guard_warnings_reads_the_route_log(monkeypatch):
    from backend.api import guard_status, key_status

    plan = _plan({6: [_sess(LIMIT)]})
    _crag(plan, 5, "done", outdoor_load_score=30)
    calls = []

    def fake_rows(user_id, since, until):
        calls.append((user_id, since.isoformat(), until.isoformat()))
        return [_log(_d(5), "6a")]

    monkeypatch.setattr(key_status, "_outdoor_rows", fake_rows)
    # Without the user: no route log read → the completed day counts.
    assert [w["code"] for w in guard_status.build_guard_warnings(ATHLETE, plan, MON)] == ["post_outdoor"]
    assert calls == []
    # With the user: the log says it was an easy day.
    assert guard_status.build_guard_warnings(ATHLETE, plan, MON, user_id="u1") == []
    assert calls == [("u1", _d(-7), _d(6))]


def test_check_insertion_reads_the_route_log():
    """Review: added_guard_warnings must judge an easy-logged crag day like the
    week's guard_warnings do (outdoor_rows passed to both evaluate calls)."""
    from backend.engine import key_sessions_v1 as ks

    plan = _plan({})
    _crag(plan, 5, "done", outdoor_load_score=30)
    st = {**copy.deepcopy(ATHLETE), "week_plans": {MON: plan}}
    cs = {"id": "cs_hang", "name": "Hangs", "exercises": [
        {"exercise_id": "max_hang_7s", "sets": 5, "work_seconds": 7, "load_mode": "anchored"}]}
    ev = [{"event_type": "add_custom_session", "custom_session_id": "cs_hang",
           "target_date": _d(6), "slot": "evening", "location": "home"}]
    res = ks.check_insertion(st, MON, plan=plan, events=ev, custom_sessions=[cs],
                             outdoor_rows=[_log(_d(5), "6a")])
    assert res["added_guard_warnings"] == []
    res = ks.check_insertion(st, MON, plan=plan, events=ev, custom_sessions=[cs])
    assert [(w["code"], w["date"]) for w in res["added_guard_warnings"]] == [("post_outdoor", _d(6))]


def test_outdoor_load_score_survives_the_field_merge():
    old = _plan({})
    _crag(old, 5, "done", outdoor_load_score=42)
    new = _plan({5: [_sess(EASY)]})
    merged = _merge_user_content(old, new)
    day = merged["weeks"][0]["days"][5]
    assert day["outdoor_load_score"] == 42 and day["outdoor_session_status"] == "done"
