"""A328 (b) — D288 R3-b: the reduced week on a trigger is an ALERT only.

Triggers: >= 2 sessions rated very_hard in the 7 days up to today, an active
pain block (score >= 2, any site), or the athlete asks (coach only). Silent
after a trip taper in the previous 5 weeks and when this or the suggested week
is the terminal deload. Never writes, never applies (A301 / B369).
"""
from __future__ import annotations

import copy
import json
from datetime import date, timedelta

import pytest

from backend.engine import athlete_context as ac
from backend.engine import reduced_week as rw

MC = {"start_date": "2026-09-07", "end_date": "2026-12-06", "phases": [
    {"phase_id": "base", "start_week": 1, "end_week": 2, "duration_weeks": 2},
    {"phase_id": "strength_power", "start_week": 3, "end_week": 6, "duration_weeks": 4},
    {"phase_id": "power_endurance", "start_week": 7, "end_week": 9, "duration_weeks": 3},
    {"phase_id": "performance", "start_week": 10, "end_week": 12, "duration_weeks": 3},
    {"phase_id": "deload", "start_week": 13, "end_week": 13, "duration_weeks": 1}]}
TODAY = "2026-10-22"  # Thursday, power endurance week 7


def _state(**extra):
    st = {"macrocycle": copy.deepcopy(MC), "session_completion_log": [], "trips": []}
    st.update(extra)
    return st


def _row(d, sid="limit_boulder_gym", difficulty="very_hard", status="done"):
    return {"date": d, "session_id": sid, "status": status, "difficulty": difficulty}


class TestTriggers:
    def test_quiet_by_default(self):
        s = rw.suggestion(_state(), TODAY)
        assert (s["suggested"], s["reasons"], s["skipped"]) == (False, [], None)
        assert s["week_start"] == "2026-10-26"

    def test_two_very_hard_in_seven_days(self):
        st = _state(session_completion_log=[_row("2026-10-16"), _row("2026-10-21", "power_endurance_gym")])
        s = rw.suggestion(st, TODAY)
        assert s["suggested"] and s["reasons"] == ["very_hard_7d"]
        assert [r["date"] for r in s["detail"]["very_hard"]] == ["2026-10-16", "2026-10-21"]

    def test_one_is_not_enough_and_the_window_is_seven_days(self):
        assert not rw.suggestion(_state(session_completion_log=[_row("2026-10-21")]), TODAY)["suggested"]
        st = _state(session_completion_log=[_row("2026-10-15"), _row("2026-10-21")])  # 15/10 is day 8
        assert not rw.suggestion(st, TODAY)["suggested"]
        st = _state(session_completion_log=[_row("2026-10-21"), _row("2026-10-21")])  # same session twice
        assert not rw.suggestion(st, TODAY)["suggested"]
        st = _state(session_completion_log=[_row("2026-10-20", status="skipped"), _row("2026-10-21"),
                                            _row("2026-10-19", difficulty="hard")])
        assert not rw.suggestion(st, TODAY)["suggested"]
        st = _state(session_completion_log=[_row("2026-10-20"), _row("2026-10-23")])  # the future does not count
        assert not rw.suggestion(st, TODAY)["suggested"]

    def test_active_pain_block(self):
        st = _state(progression_counters={"pain_blocks": {"elbow": {"from": "2026-10-20", "until": "2026-10-27",
                                                                    "score": 2}}})
        s = rw.suggestion(st, TODAY)
        assert s["suggested"] and s["reasons"] == ["pain_block"]
        assert s["detail"]["pain_blocks"] == [{"site": "elbow", "score": 2, "from": "2026-10-20",
                                               "until": "2026-10-27"}]

    @pytest.mark.parametrize("block", [
        {"from": "2026-10-20", "until": "2026-10-27", "score": 1},   # score 1
        {"from": "2026-10-10", "until": "2026-10-17", "score": 3},   # ended
        {"from": "2026-10-23", "until": "2026-10-30", "score": 3},   # not started
    ])
    def test_inactive_pain_block(self, block):
        st = _state(progression_counters={"pain_blocks": {"fingers": block}})
        assert not rw.suggestion(st, TODAY)["suggested"]

    def test_the_athlete_asks(self):
        s = rw.suggestion(_state(), TODAY, requested=True)
        assert s["suggested"] and s["reasons"] == ["athlete_request"]


class TestSilent:
    def _triggered(self, **extra):
        return _state(session_completion_log=[_row("2026-10-20"), _row("2026-10-21")], **extra)

    def test_after_a_trip_taper_in_the_previous_five_weeks(self):
        # Trip 2026-10-01: taper 17/09 → 30/09, inside the 35 days before 22/10.
        st = self._triggered(trips=[{"name": "Kalymnos", "start_date": "2026-10-01", "end_date": "2026-10-10"}])
        s = rw.suggestion(st, TODAY)
        assert (s["suggested"], s["skipped"]) == (False, "recent_taper")
        assert s["reasons"] == ["very_hard_7d"]
        # A request is subject to the same rule.
        assert rw.suggestion(st, TODAY, requested=True)["skipped"] == "recent_taper"

    def test_a_taper_older_than_five_weeks_or_in_the_future_does_not_silence(self):
        old = self._triggered(trips=[{"name": "old", "start_date": "2026-09-01"}])  # taper ends 31/08
        assert rw.suggestion(old, TODAY)["suggested"]
        future = self._triggered(trips=[{"name": "next", "start_date": "2026-11-20"}])  # taper from 06/11
        assert rw.suggestion(future, TODAY)["suggested"]

    def test_a_running_taper_silences(self):
        st = self._triggered(trips=[{"name": "soon", "start_date": "2026-10-30"}])  # taper from 16/10
        assert rw.suggestion(st, TODAY)["skipped"] == "recent_taper"

    def test_the_week_before_the_deload_and_the_deload(self):
        # 2026-11-26 (performance, last week): the suggested week is the deload.
        st = _state(session_completion_log=[_row("2026-11-24"), _row("2026-11-25")])
        s = rw.suggestion(st, "2026-11-26")
        assert (s["suggested"], s["skipped"], s["week_start"]) == (False, "deload_soon", "2026-11-30")
        st = _state(session_completion_log=[_row("2026-11-30"), _row("2026-12-01")])
        assert rw.suggestion(st, "2026-12-02")["skipped"] == "deload_soon"

    def test_on_a_monday_the_week_is_this_one(self):
        assert rw.suggestion(_state(), "2026-10-19")["week_start"] == "2026-10-19"


class TestPureAndText:
    def test_never_writes_and_is_deterministic(self):
        st = _state(session_completion_log=[_row("2026-10-20"), _row("2026-10-21")],
                    progression_counters={"pain_blocks": {"fingers": {"from": "2026-10-21", "until": "2026-10-28",
                                                                      "score": 3}}})
        before = copy.deepcopy(st)
        a = rw.suggestion(st, TODAY)
        b = rw.suggestion(st, date(2026, 10, 22))
        assert st == before
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        assert a["reasons"] == ["very_hard_7d", "pain_block"]

    def test_alert_text(self):
        st = _state(session_completion_log=[_row("2026-10-20"), _row("2026-10-21")])
        text = rw.alert_text(rw.suggestion(st, TODAY))
        assert text.startswith("Consider a reduced week from 2026-10-26 (two sessions rated very hard")
        assert "Nothing changes in your plan unless you decide it." in text
        assert rw.alert_text(rw.suggestion(_state(), TODAY)) is None

    def test_invalid_today(self):
        with pytest.raises(ValueError):
            rw.suggestion(_state(), "not a date")


class TestAthleteContext:
    def test_warning_and_render(self):
        st = _state(session_completion_log=[_row("2026-10-20"), _row("2026-10-21")])
        ctx = ac.build_athlete_context(st, TODAY, include_next_week=False, with_proposals=False)
        assert ctx["reduced_week"]["suggested"] is True
        w = [x for x in ctx["warnings"] if x["code"] == "REDUCED_WEEK_SUGGESTED"]
        assert len(w) == 1 and w[0]["week_start"] == "2026-10-26" and w[0]["reasons"] == ["very_hard_7d"]
        assert "il motore non la applica" in w[0]["message"]
        assert "[REDUCED_WEEK_SUGGESTED]" in ac.render_text(ctx)
        assert "Reduced week (suggestion only, the athlete decides)" in ac.render_coach_block(ctx)

    def test_request_from_the_coach_and_skip_warning(self):
        ctx = ac.build_athlete_context(_state(), TODAY, include_next_week=False, with_proposals=False,
                                       reduced_week_request=True)
        assert ctx["reduced_week"]["reasons"] == ["athlete_request"]
        st = _state(session_completion_log=[_row("2026-11-24"), _row("2026-11-25")])
        ctx = ac.build_athlete_context(st, "2026-11-26", include_next_week=False, with_proposals=False)
        codes = [x["code"] for x in ctx["warnings"]]
        assert "REDUCED_WEEK_SKIPPED" in codes and "REDUCED_WEEK_SUGGESTED" not in codes

    def test_quiet_context_has_no_warning(self):
        ctx = ac.build_athlete_context(_state(), TODAY, include_next_week=False, with_proposals=False)
        assert ctx["reduced_week"]["suggested"] is False
        assert not [x for x in ctx["warnings"] if x["code"].startswith("REDUCED_WEEK")]
        assert "Reduced week" not in ac.render_coach_block(ctx)


class TestWeekEndpoint:
    """GET /api/week: a sibling field, current week only, never persisted."""

    def _run(self, monkeypatch, log):
        from backend.api.routers import week as week_router
        from backend.engine import storage

        today = date.today()
        monday = today - timedelta(days=today.weekday())
        start = monday - timedelta(weeks=7)  # current week = week 8 (strength_power)
        mc = copy.deepcopy(MC)
        mc["start_date"], mc["end_date"] = start.isoformat(), (start + timedelta(weeks=13, days=-1)).isoformat()
        for p in mc["phases"]:
            p.update({"session_pool": ["technique_focus_gym", "prehab_maintenance"], "intensity_cap": "max",
                      "domain_weights": {"technique": 0.5, "core_prehab": 0.5}})
        state = {"macrocycle": mc, "session_completion_log": log, "trips": [],
                 "availability": {d: {"evening": {"available": True, "locations": ["gym"]}}
                                  for d in ("mon", "wed", "fri")},
                 "planning_prefs": {"target_training_days_per_week": 3},
                 "equipment": {"gyms": [{"gym_id": "g", "equipment": ["gym_boulder", "hangboard"]}],
                               "home": [], "home_enabled": False}}
        mem = {"state": state, "writes": []}
        monkeypatch.setattr(storage, "read_state", lambda uid=None: copy.deepcopy(mem["state"]))
        monkeypatch.setattr(storage, "write_state", lambda st, uid=None: mem["writes"].append(copy.deepcopy(st)))
        res = week_router.get_week(week_num=0, force=False, preserve_before=None, today=today.isoformat(),
                                   user_id="a328b-test")
        return res, mem

    def test_sibling_when_suggested_and_never_persisted(self, monkeypatch):
        today = date.today()
        log = [_row((today - timedelta(days=1)).isoformat()), _row(today.isoformat(), "power_endurance_gym")]
        res, mem = self._run(monkeypatch, log)
        assert res["reduced_week"]["suggested"] is True and res["reduced_week"]["reasons"] == ["very_hard_7d"]
        assert res["reduced_week"]["message"].startswith("Consider a reduced week")
        assert "reduced_week" not in res["week_plan"]
        assert all("reduced_week" not in json.dumps(w.get("week_plans") or {}) for w in mem["writes"])

    def test_absent_when_quiet(self, monkeypatch):
        res, _mem = self._run(monkeypatch, [])
        assert "reduced_week" not in res
