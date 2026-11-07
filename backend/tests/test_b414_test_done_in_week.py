"""B414 step 5 — A289-TEST-DONE-IN-WEEK: a test done inside its week closes it.

Before B414 ``_axis_week_decision`` read the official max on the Monday of the
week only: a test logged from Tuesday on did not move ``last``, so the week
stayed ``due`` until Sunday — a mid-week regeneration put the test back in the
days left (or wrote ``no_placement_slot``) and ``retest_status`` said
``missed`` / ``not_in_plan``.

Part 1: a real test dated in the week → ``not_due`` + ``done_in_week``.
Part 2: a test session of the axis marked done with no values logged → the
same, + ``result_missing`` (the max stays the old one until the values are
entered). A skipped test session does not count.

Fixture: ``_due_1019`` of test_a289 (both axes due 22-25/10, end of the
strength phase). Pure engine reads, no clock.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta

import pytest

from backend.engine import retest_policy as rp
from backend.engine.planner_v2 import generate_phase_week
from backend.engine.replanner_v1 import regenerate_preserving_completed
from backend.tests.test_a289_retest_policy import _daniele, _due_1019, _kwargs, _test_days

WS = "2026-10-19"
_WEEK = [(date(2026, 10, 19) + timedelta(days=i)).isoformat() for i in range(7)]
_TEST_IDS = {"test_max_hang_7s", "test_max_weighted_pullup", "test_max_hang_pullup"}


def _plan(day: str = "2026-10-23", status: str = "done", sid: str = "test_max_hang_pullup") -> dict:
    days = []
    for d in _WEEK:
        sessions = [{"session_id": sid, "slot": "evening", "status": status}] if d == day else []
        days.append({"date": d, "sessions": sessions})
    reqs = [{"axis": a, "status": "placed", "placed_date": day, "session_id": sid, "trigger": "end_of_phase"}
            for a in ("finger", "pulling")]
    return {"start_date": WS, "weeks": [{"days": days}],
            "profile_snapshot": {"retest_decisions": {"required_sessions": reqs}}}


def _log_hang(state: dict, day: str, total: float = 118.0) -> None:
    state["tests"]["max_strength"].append({"date": day, "test_id": "max_hang_7s_total_load",
                                           "total_load_kg": total, "bodyweight_kg": 76.0})


def _log_pull(state: dict, day: str, total: float = 124.0) -> None:
    state["tests"]["pulling_strength"].append({"date": day, "test_id": "weighted_pullup_2rm",
                                               "total_load_2rm_kg": total, "estimated_1rm_kg": 130.0,
                                               "bodyweight_kg": 76.0})


def _logged(day: str = "2026-10-23", status: str = "done") -> dict:
    st = _due_1019()
    st["week_plans"] = {WS: _plan(day, status)}
    _log_hang(st, day)
    _log_pull(st, day)
    return st


def _dec(state, today):
    return rp.retest_decisions(state, WS, today=today, finger_device="hangboard")


def _axes(dec):
    return {a: (d["status"], d.get("done_in_week"), d.get("result_missing")) for a, d in dec["axes"].items()}


class TestPart1LoggedTest:
    def test_combined_logged_thursday_closes_both_axes(self):
        dec = _dec(_logged(), "2026-10-24")
        assert _axes(dec) == {"finger": ("not_due", "2026-10-23", None),
                              "pulling": ("not_due", "2026-10-23", None)}
        assert dec["required_sessions"] == [] and dec["skipped"] == []
        # The coverage and the rest of the row are still read on Monday.
        assert dec["axes"]["finger"]["last_test_date"] == "2026-09-10"

    def test_before_the_test_the_week_is_due(self):
        # Control: the same state the day before, with nothing logged yet.
        st = _due_1019()
        st["week_plans"] = {WS: _plan(status="planned")}
        dec = _dec(st, "2026-10-21")
        assert {a: d["status"] for a, d in dec["axes"].items()} == {"finger": "due", "pulling": "due"}
        assert all("done_in_week" not in d for d in dec["axes"].values())

    def test_retest_status_on_the_day_and_the_day_after(self):
        st = _logged()
        for td in ("2026-10-23", "2026-10-24"):
            for axis, row in rp.retest_status(st, td, finger_device="hangboard")["axes"].items():
                assert row["next_test_reason"] not in ("missed", "not_in_plan"), (td, axis)
                assert row["test_date"] == "2026-10-23"
                assert row["earliest_retest"] == (date(2026, 10, 23) + timedelta(days=42)).isoformat()

    def test_monday_test_still_not_due(self):
        st = _logged(day="2026-10-19")
        dec = _dec(st, "2026-10-20")
        assert {a: d["status"] for a, d in dec["axes"].items()} == {"finger": "not_due", "pulling": "not_due"}
        assert dec["required_sessions"] == []

    def test_hang_alone_closes_only_the_finger_axis(self):
        st = _due_1019()
        st["week_plans"] = {WS: _plan(sid="test_max_hang_7s")}
        _log_hang(st, "2026-10-23")
        dec = _dec(st, "2026-10-24")
        assert dec["axes"]["finger"]["status"] == "not_due"
        assert dec["axes"]["pulling"]["status"] == "due"
        assert [r["axis"] for r in dec["required_sessions"]] == ["pulling"]

    def test_tests_outside_the_week_do_not_close_it(self):
        st = _due_1019()
        _log_hang(st, "2026-10-26")  # next Monday: that week's, not this one's
        dec = _dec(st, "2026-10-21")
        assert dec["axes"]["finger"]["status"] == "due"
        assert "done_in_week" not in dec["axes"]["finger"]

    def test_test_done_in_week_wins_over_a_postpone(self):
        postpone = [{"axis": "finger", "kind": "postpone", "trigger": "end_of_phase", "reason": "schedule",
                     "declined_at": "2026-10-20", "until": "2026-11-20", "source": "app",
                     "official_date": "2026-09-10", "macrocycle_start": "2026-09-14"}]
        held = _due_1019()
        held[rp.DECLINES_KEY] = deepcopy(postpone)
        assert _dec(held, "2026-10-21")["axes"]["finger"]["skip_reason"] == "postponed"  # control
        st = _logged()
        st[rp.DECLINES_KEY] = deepcopy(postpone)
        dec = _dec(st, "2026-10-24")
        assert dec["axes"]["finger"]["status"] == "not_due"
        assert dec["axes"]["finger"]["done_in_week"] == "2026-10-23"


class TestPart2SessionDoneWithoutValues:
    def test_done_without_values_closes_the_week(self):
        st = _due_1019()
        st["week_plans"] = {WS: _plan()}
        dec = _dec(st, "2026-10-24")
        assert _axes(dec) == {"finger": ("not_due", "2026-10-23", True),
                              "pulling": ("not_due", "2026-10-23", True)}
        assert dec["required_sessions"] == []
        # The max stays the old one until the values are entered.
        assert rp.axis_official(st, "finger", "2026-10-24")["date"] == "2026-09-10"

    def test_skipped_test_session_does_not_count(self):
        st = _due_1019()
        st["week_plans"] = {WS: _plan(status="skipped")}
        dec = _dec(st, "2026-10-24")
        assert {a: d["status"] for a, d in dec["axes"].items()} == {"finger": "due", "pulling": "due"}

    def test_combined_with_only_the_hang_logged(self):
        st = _due_1019()
        st["week_plans"] = {WS: _plan()}
        _log_hang(st, "2026-10-23")
        dec = _dec(st, "2026-10-24")
        assert _axes(dec) == {"finger": ("not_due", "2026-10-23", None),
                              "pulling": ("not_due", "2026-10-23", True)}

    def test_single_axis_session_does_not_close_the_other_axis(self):
        st = _due_1019()
        st["week_plans"] = {WS: _plan(sid="test_max_weighted_pullup")}
        dec = _dec(st, "2026-10-24")
        assert dec["axes"]["pulling"]["status"] == "not_due"
        assert dec["axes"]["finger"]["status"] == "due"


class TestInvariants:
    def test_untested_athlete_still_none(self):
        st = _daniele(tests={"max_strength": [], "pulling_strength": []})
        st["week_plans"] = {WS: _plan()}
        assert _dec(st, "2026-10-24") is None

    def test_deterministic(self):
        st = _logged()
        assert _dec(st, "2026-10-24") == _dec(deepcopy(st), "2026-10-24")

    @pytest.mark.parametrize("logged", [True, False], ids=["values_logged", "done_without_values"])
    def test_mid_week_regeneration_adds_no_test_and_keeps_the_done_one(self, logged):
        """Review B414 step 5: the test is done on WEDNESDAY 22/10 (the policy
        alone puts the pair on Sunday 25/10, the last day of the week, which
        left no day to regenerate and made this test pass on the old code too).
        Regenerating on Thursday must not place the test again in 23-25/10 nor
        record a placement failure, and every past day stays byte for byte."""
        st = _due_1019()
        old = generate_phase_week(**_kwargs("power_endurance", WS), retest_decisions=_dec(st, "2026-10-19"))
        tests = [s for d in old["weeks"][0]["days"] for s in d["sessions"] if s["session_id"] in _TEST_IDS]
        assert tests, "the policy placed the test in the original week"
        test_day, today = "2026-10-22", "2026-10-23"
        for day in old["weeks"][0]["days"]:
            day["sessions"] = [s for s in day["sessions"] if s["session_id"] not in _TEST_IDS]
            if day["date"] == test_day:
                day["sessions"] = [{**deepcopy(s), "status": "done"} for s in tests]
        st["week_plans"] = {WS: old}
        if logged:
            _log_hang(st, test_day)
            _log_pull(st, test_day)
        dec = _dec(st, today)
        assert {a: (d["status"], d["done_in_week"]) for a, d in dec["axes"].items()} == \
            {"finger": ("not_due", test_day), "pulling": ("not_due", test_day)}
        assert dec["required_sessions"] == [] and dec["skipped"] == []
        fresh = generate_phase_week(**_kwargs("power_endurance", WS, today=today), retest_decisions=dec)
        assert not set(_test_days(fresh)) & _TEST_IDS
        assert not (fresh.get("skipped_tests") or [])
        before = deepcopy(old)
        merged = regenerate_preserving_completed(old, fresh, preserve_before=today)
        assert old == before
        days_before = {d["date"]: d for d in before["weeks"][0]["days"]}
        for day in merged["weeks"][0]["days"]:
            if day["date"] < today:
                assert day == days_before[day["date"]], day["date"]  # byte for byte
        later = [s["session_id"] for d in merged["weeks"][0]["days"] if d["date"] >= today
                 for s in d["sessions"]]
        assert not set(later) & _TEST_IDS
