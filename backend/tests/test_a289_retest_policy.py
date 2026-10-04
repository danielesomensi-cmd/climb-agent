"""A289 — retest policy in planner PASS 3 + live retest_status for the UI.

Covers:
- ``retest_policy.retest_decisions``: who is covered (tested axes only),
  triggers (end of SP, one-week slip, cycle start, maintenance, early retest
  from measured signals), week blockers (phase, gap by confidence) and day
  blockers (trip, very_hard), already-scheduled tests, determinism.
- ``planner_v2.generate_phase_week(retest_decisions=...)``: byte-identical with
  None, paired placement (hang before pull-up, same day), the unified blockers
  (finger-hard < 72 h, heavy pull < 48 h — 48 h exactly allowed), fallbacks,
  the legacy PASS 3 left to the uncovered axes, inject_tests wins.
- ``retest_status``: official max, confidence, ±5 % trend, next test (planned
  with reason, projected), live blockers on the planned day.
- GET /api/week: retest_status attached, manual 6-week reminder suppressed
  for covered athletes, nothing new for untested ones.
- Past sessions immutable through a regeneration with decisions.

Daniele's case (synthetic copy of the 2026-10-04 snapshot): both 24/09 tests
have LOW confidence (0 exposures in 03-23/09) → earliest 22/10; the
end-of-SP week 12-18/10 cannot reach it → slips once to 19-25/10.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import retest_policy as rp
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _adjust_domain_weights, _build_session_pool
from backend.engine.planner_v2 import generate_phase_week, should_show_test_reminder
from backend.engine.replanner_v1 import regenerate_preserving_completed

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_STATE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_GYM = {"gym_id": "g1", "equipment": ["spraywall", "board_kilter", "hangboard", "gym_boulder",
                                       "gym_routes", "dumbbell", "pullup_bar", "weights"]}
_HOME = ["hangboard", "pullup_bar", "weights", "dumbbell"]
_PROFILE = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
            "technique": 50, "endurance": 40}


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _macrocycle(start: str = "2026-09-07") -> dict:
    return {
        "start_date": start,
        "phases": [
            {"phase_id": "base", "duration_weeks": 2},
            {"phase_id": "strength_power", "duration_weeks": 4},
            {"phase_id": "power_endurance", "duration_weeks": 3},
            {"phase_id": "performance", "duration_weeks": 3},
            {"phase_id": "deload", "duration_weeks": 1},
        ],
    }


def _daniele(**over) -> dict:
    """Tests of 24/09 (hang 116, pull 2RM 123), earlier tests in May."""
    state = {
        "bodyweight_kg": 77,
        "macrocycle": _macrocycle(),
        "preferences": {"finger_training_device": "hangboard"},
        "tests": {
            "max_strength": [
                {"date": "2026-05-19", "test_id": "max_hang_7s_total_load", "total_load_kg": 122.0,
                 "bodyweight_kg": 77.0},
                {"date": "2026-09-24", "test_id": "max_hang_7s_total_load", "total_load_kg": 116.0,
                 "bodyweight_kg": 76.0, "confidence": "high"},
            ],
            "pulling_strength": [
                {"date": "2026-05-22", "test_id": "weighted_pullup_2rm", "total_load_2rm_kg": 122.0,
                 "estimated_1rm_kg": 127.8, "bodyweight_kg": 77.0},
                {"date": "2026-09-24", "test_id": "weighted_pullup_2rm", "total_load_2rm_kg": 123.0,
                 "estimated_1rm_kg": 128.9, "bodyweight_kg": 78.0, "confidence": "high"},
            ],
        },
        "trips": [],
        "feedback_log": [],
        "week_plans": {},
    }
    state.update(over)
    return state


def _with_exposures(state: dict, family_dates: dict) -> dict:
    state = deepcopy(state)
    state.setdefault("progression_counters", {})["stimulus_exposures"] = {
        fam: list(dates) for fam, dates in family_dates.items()
    }
    return state


def _avail(days=_DAYS, slots=("morning", "lunch", "evening")) -> dict:
    return {wd: {s: {"available": True, "locations": ["gym", "home"]} for s in slots} for wd in days}


def _kwargs(phase_id: str, start_date: str, **over) -> dict:
    kw = dict(
        phase_id=phase_id,
        domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[phase_id], _PROFILE),
        session_pool=_build_session_pool(phase_id),
        start_date=start_date,
        availability=_avail(),
        allowed_locations=["home", "gym"],
        hard_cap_per_week=4,
        planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 4},
        default_gym_id="g1",
        gyms=[_GYM],
        home_equipment=_HOME,
        finger_device="hangboard",
        pulling_baseline={"weighted_pullup_2rm_total_kg": 123.0},
    )
    kw.update(over)
    return kw


def _sessions(plan: dict):
    for d in plan["weeks"][0]["days"]:
        for s in d["sessions"]:
            yield d["date"], s


def _test_days(plan: dict) -> dict:
    return {s["session_id"]: (d, s["slot"]) for d, s in _sessions(plan)
            if str(s["session_id"]).startswith("test_")}


def _strip_volatile(plan: dict) -> dict:
    p = deepcopy(plan)
    p.pop("generated_at", None)
    return p


_SLOT_RANK = {"morning": 0, "lunch": 1, "evening": 2}


def _decision(state, ws, today="2026-10-04", **kw):
    return rp.retest_decisions(state, ws, today=today, finger_device="hangboard", **kw)


# ---------------------------------------------------------------------------
# retest_decisions — coverage and triggers
# ---------------------------------------------------------------------------

class TestCoverage:
    def test_untested_athlete_returns_none(self):
        st = _daniele(tests={})
        assert _decision(st, "2026-10-19") is None

    def test_onboarding_baseline_only_is_not_covered(self):
        st = _daniele(tests={})
        st["baselines"] = {
            "hangboard": [{"max_total_load_kg": 110, "updated_at": "2026-09-20", "source": "test"}],
            "pulling": {"weighted_pullup_2rm_total_kg": 115, "updated_at": "2026-09-20", "source": "test"},
        }
        assert _decision(st, "2026-10-19") is None

    def test_stale_test_is_not_covered(self):
        st = _daniele()
        # 2027-01-04 is > 90 days after 24/09 → untested → legacy PASS 3.
        assert _decision(st, "2027-01-04") is None

    def test_loading_pin_finger_axis_not_covered(self):
        st = _daniele()
        dec = rp.retest_decisions(st, "2026-10-19", today="2026-10-04", finger_device="loading_pin")
        assert dec["covered_axes"] == ["pulling"]


class TestTriggersDaniele:
    def test_confidence_low_earliest_22_10(self):
        st = _daniele()
        om = rp.axis_official(st, "finger", "2026-10-19")
        assert rp.axis_confidence(st, om)["confidence"] == "low"
        dec = _decision(st, "2026-10-19")
        assert {r["axis"] for r in dec["required_sessions"]} == {"finger", "pulling"}
        for r in dec["required_sessions"]:
            assert r["earliest_date"] == "2026-10-22"
            assert r["confidence"] == "low"
            assert r["gap_days"] == 28

    def test_end_of_sp_week_slips_once(self):
        st = _daniele()
        dec = _decision(st, "2026-10-12")
        assert dec["required_sessions"] == []
        reasons = {s["axis"]: s["skip_reason"] for s in dec["skipped"]}
        assert reasons == {"finger": "slipped:gap", "pulling": "slipped:gap"}
        assert all(s["slipped_to_week"] == "2026-10-19" for s in dec["skipped"])

    def test_slipped_week_is_paired_hang_first(self):
        dec = _decision(_daniele(), "2026-10-19")
        hang, pull = dec["required_sessions"]
        assert (hang["session_id"], pull["session_id"]) == ("test_max_hang_7s", "test_max_weighted_pullup")
        assert hang["order"] == 1 and pull["order"] == 2
        assert hang["paired_with"] == pull["session_id"] and pull["paired_with"] == hang["session_id"]
        assert hang["trigger"] == rp.TRIGGER_END_OF_PHASE_SLIPPED
        assert hang["allowed_dates"] == ["2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"]

    def test_following_weeks_not_due(self):
        st = _daniele()
        for ws in ("2026-10-26", "2026-11-02"):
            assert _decision(st, ws)["required_sessions"] == []

    def test_high_confidence_waits_42_days_and_cannot_slip(self):
        # Two exposures in the 21 days before the test → high → earliest 05/11:
        # the end-of-SP week and its one-week slip are both out of reach.
        st = _with_exposures(_daniele(), {"finger_max": ["2026-09-10", "2026-09-17"],
                                          "pulling_max": ["2026-09-10", "2026-09-17"]})
        dec12 = _decision(st, "2026-10-12")
        assert {s["skip_reason"] for s in dec12["skipped"]} == {"blocked:gap"}
        assert _decision(st, "2026-10-19")["required_sessions"] == []
        om = rp.axis_official(st, "finger", "2026-10-19")
        assert rp.axis_confidence(st, om)["confidence"] == "high"

    def test_stored_computed_confidence_wins(self):
        st = _daniele()
        st["tests"]["max_strength"][-1]["confidence"] = "high"
        st["tests"]["max_strength"][-1]["confidence_basis"] = {"exposures": 3, "min_required": 2}
        dec = _decision(st, "2026-10-19")
        axes = {r["axis"] for r in dec["required_sessions"]}
        assert axes == {"pulling"}  # finger: high → 42 days → not reachable


class TestOtherTriggers:
    def test_cycle_start(self):
        st = _daniele(macrocycle=_macrocycle("2026-11-02"))
        dec = _decision(st, "2026-11-02", today="2026-11-02")
        assert {r["trigger"] for r in dec["required_sessions"]} == {rp.TRIGGER_CYCLE_START}

    def test_maintenance_after_84_days(self):
        # A long PE phase so the 84-day mark is not in performance/deload.
        mc = {"start_date": "2026-09-07", "phases": [
            {"phase_id": "base", "duration_weeks": 2},
            {"phase_id": "strength_power", "duration_weeks": 2},
            {"phase_id": "power_endurance", "duration_weeks": 12},
        ]}
        st = _daniele(macrocycle=mc)
        # 24/09 + 84 = 17/12 → week of 14/12.
        assert _decision(st, "2026-12-07", today="2026-12-07")["required_sessions"] == []
        dec = _decision(st, "2026-12-14", today="2026-12-14")
        assert {r["trigger"] for r in dec["required_sessions"]} == {rp.TRIGGER_MAINTENANCE}
        assert all(r["allowed_dates"][0] == "2026-12-17" for r in dec["required_sessions"])

    def test_phase_blocker_performance(self):
        mc = {"start_date": "2026-09-07", "phases": [
            {"phase_id": "base", "duration_weeks": 2},
            {"phase_id": "strength_power", "duration_weeks": 2},
            {"phase_id": "performance", "duration_weeks": 12},
        ]}
        st = _daniele(macrocycle=mc)
        dec = _decision(st, "2026-12-14", today="2026-12-14")
        assert dec["required_sessions"] == []
        assert {s["skip_reason"] for s in dec["skipped"]} == {"blocked:phase"}

    def test_early_retest_from_two_measured_signals(self):
        st = _daniele()
        st["progression_counters"] = {"retest_signals": {
            "weighted_pullup": {"count": 2, "dates": ["2026-10-27", "2026-10-30"],
                                "last_date": "2026-10-30", "official_date": "2026-09-24"},
        }}
        # The current week (26/10) is already generated: the early retest whose
        # signals end on 30/10 is not deferred to it (A289 review).
        st["week_plans"] = {"2026-10-26": _plan_with_tests("2026-10-26")}
        st["week_plans"]["2026-10-26"]["weeks"][0]["days"][0]["sessions"] = []
        dec = _decision(st, "2026-11-02", today="2026-11-01")
        req = {r["axis"]: r for r in dec["required_sessions"]}
        assert set(req) == {"pulling"}
        assert req["pulling"]["trigger"] == rp.TRIGGER_EARLY
        assert req["pulling"]["earliest_date"] == "2026-11-02"

    def test_signals_against_an_older_test_do_not_count(self):
        st = _daniele()
        st["progression_counters"] = {"retest_signals": {
            "weighted_pullup": {"count": 2, "dates": ["2026-10-27", "2026-10-30"],
                                "last_date": "2026-10-30", "official_date": "2026-05-22"},
        }}
        assert _decision(st, "2026-11-02", today="2026-11-01")["required_sessions"] == []

    def test_one_signal_is_not_enough(self):
        st = _daniele()
        st["progression_counters"] = {"retest_signals": {
            "max_hang_7s": {"count": 1, "dates": ["2026-10-27"], "last_date": "2026-10-27",
                            "official_date": "2026-09-24"},
        }}
        assert _decision(st, "2026-11-02", today="2026-11-01")["required_sessions"] == []

    def test_labels_never_create_a_decision(self):
        st = _daniele()
        st["progression_counters"] = {"hard_labels": {"finger": ["2026-10-27", "2026-10-28", "2026-10-29"]},
                                      "max_hang_5s_hard_streak": 5}
        st["feedback_log"] = [{"date": "2026-10-28", "session_id": "finger_strength_home",
                               "difficulty": "hard", "exercise_feedback": {"max_hang_7s": "hard"}}]
        assert _decision(st, "2026-11-02", today="2026-11-01")["required_sessions"] == []


class TestDayBlockers:
    def test_trip_blocks_days(self):
        st = _daniele(trips=[{"name": "x", "start_date": "2026-11-03", "end_date": "2026-11-08"}])
        dec = _decision(st, "2026-10-19")
        # 24/10 + 10 = 03/11 → 24 and 25 blocked; 22 and 23 still allowed.
        assert dec["required_sessions"][0]["allowed_dates"] == ["2026-10-22", "2026-10-23"]

    def test_trip_blocks_whole_window(self):
        st = _daniele(trips=[{"name": "x", "start_date": "2026-10-30", "end_date": "2026-11-08"}])
        dec = _decision(st, "2026-10-19")
        assert dec["required_sessions"] == []
        assert {s["skip_reason"] for s in dec["skipped"]} == {"blocked:trip"}

    def test_very_hard_blocks_three_days(self):
        st = _daniele(feedback_log=[{"date": "2026-10-21", "difficulty": "very_hard",
                                     "session_id": "limit_boulder_gym"}])
        dec = _decision(st, "2026-10-19", today="2026-10-21")
        assert dec["required_sessions"][0]["allowed_dates"] == ["2026-10-25"]

    def test_external_blockers_include_custom_and_previous_week(self):
        st = _daniele()
        st["week_plans"] = {"2026-10-12": {"start_date": "2026-10-12", "weeks": [{"days": [
            {"date": "2026-10-18", "sessions": [
                {"session_id": "custom_cs_x", "status": "planned", "is_custom": True,
                 "exercises": [{"exercise_id": "max_hang_7s", "sets": 5}]},
                {"session_id": "pulling_strength_gym", "status": "planned"},
            ]},
        ]}]}}
        dec = _decision(st, "2026-10-19")
        assert dec is not None
        # Nothing due this week? (due: yes, slipped) — the blockers are computed
        # only when something is due, and here both tests are due.
        assert "2026-10-18" in dec["finger_hard_dates"]
        assert "2026-10-18" in dec["heavy_pull_dates"]

    def test_already_scheduled_in_another_week(self):
        st = _daniele()
        st["week_plans"] = {"2026-10-12": {"start_date": "2026-10-12", "weeks": [{"days": [
            {"date": "2026-10-17", "sessions": [{"session_id": "test_max_hang_7s"}]},
        ]}]}}
        dec = _decision(st, "2026-10-19")
        assert [r["axis"] for r in dec["required_sessions"]] == ["pulling"]
        assert dec["already_scheduled"] == [{"axis": "finger", "date": "2026-10-17",
                                             "trigger": rp.TRIGGER_END_OF_PHASE_SLIPPED}]

    def test_skipped_test_does_not_count_as_scheduled(self):
        st = _daniele()
        st["week_plans"] = {"2026-10-12": {"start_date": "2026-10-12", "weeks": [{"days": [
            {"date": "2026-10-17", "sessions": [{"session_id": "test_max_hang_7s", "status": "skipped"}]},
        ]}]}}
        assert len(_decision(st, "2026-10-19")["required_sessions"]) == 2

    def test_deterministic(self):
        st = _daniele()
        a = _decision(st, "2026-10-19")
        b = _decision(deepcopy(st), "2026-10-19")
        assert a == b
        json.dumps(a)  # serialisable (stored in profile_snapshot)


# ---------------------------------------------------------------------------
# Planner PASS 3a
# ---------------------------------------------------------------------------

def _pe_week(**over):
    return _kwargs("power_endurance", "2026-10-19", **over)


class TestPlanner:
    def test_none_is_byte_identical(self):
        for phase, ws, last in (("strength_power", "2026-10-12", True),
                                ("power_endurance", "2026-10-19", False),
                                ("base", "2026-09-07", True)):
            kw = _kwargs(phase, ws, is_last_week_of_phase=last)
            a = _strip_volatile(generate_phase_week(**kw))
            b = _strip_volatile(generate_phase_week(**kw, retest_decisions=None))
            assert a == b
            assert "retest_decisions" not in a["profile_snapshot"]

    def test_paired_placement_hang_before_pull(self):
        dec = _decision(_daniele(), "2026-10-19")
        plan = generate_phase_week(**_pe_week(retest_decisions=dec))
        tests = _test_days(plan)
        assert set(tests) >= {"test_max_hang_7s", "test_max_weighted_pullup"}
        (hd, hs), (pd, ps) = tests["test_max_hang_7s"], tests["test_max_weighted_pullup"]
        assert hd == pd and hd >= "2026-10-22"
        assert _SLOT_RANK[hs] < _SLOT_RANK[ps]
        snap = plan["profile_snapshot"]["retest_decisions"]
        assert snap["applied"] is True
        assert [r["status"] for r in snap["required_sessions"]] == ["placed", "placed"]
        assert all(r["placed_date"] == hd for r in snap["required_sessions"])
        entry = next(s for _d, s in _sessions(plan) if s["session_id"] == "test_max_hang_7s")
        assert "pass3:retest_policy" in entry["explain"]
        assert any(e.startswith("retest:end_of_phase_slipped") for e in entry["explain"])

    def test_finger_hard_day_before_blocks_hang_72h(self):
        # A finger-hard session on Wed 21/10 outside the planner's view (external)
        # → 22 and 23 blocked (< 3 days), 24 allowed.
        dec = _decision(_daniele(), "2026-10-19")
        dec = deepcopy(dec)
        dec["finger_hard_dates"] = ["2026-10-21"]
        plan = generate_phase_week(**_pe_week(retest_decisions=dec))
        hd, _ = _test_days(plan)["test_max_hang_7s"]
        assert hd >= "2026-10-24"

    def test_heavy_pull_two_days_before_is_allowed_one_day_blocks(self):
        dec = deepcopy(_decision(_daniele(), "2026-10-19"))
        # Restrict to Sun 25 so the outcome is readable (Sat 24 is inside the
        # 72 h hang block of the plan's own finger-hard Wednesday, A289 review).
        for r in dec["required_sessions"]:
            r["allowed_dates"] = ["2026-10-25"]
        dec["heavy_pull_dates"] = ["2026-10-23"]  # 48 h before Sunday: allowed
        plan = generate_phase_week(**_pe_week(retest_decisions=dec))
        assert _test_days(plan)["test_max_weighted_pullup"][0] == "2026-10-25"
        dec["heavy_pull_dates"] = ["2026-10-24"]  # 24 h before: blocked
        plan = generate_phase_week(**_pe_week(retest_decisions=dec))
        tests = _test_days(plan)
        assert tests["test_max_hang_7s"][0] == "2026-10-25"
        assert "test_max_weighted_pullup" not in tests
        skipped = {s["test_id"]: s["reason"] for s in plan["skipped_tests"]}
        assert skipped["test_max_weighted_pullup"] == "blocked:no_paired_slot"

    def test_hang_unplaced_skips_pull_with_same_reason(self):
        dec = deepcopy(_decision(_daniele(), "2026-10-19"))
        dec["finger_hard_dates"] = ["2026-10-24", "2026-10-25"]  # nothing left with < 72 h free
        for r in dec["required_sessions"]:
            r["allowed_dates"] = ["2026-10-25", "2026-10-26"]
        plan = generate_phase_week(**_pe_week(retest_decisions=dec))
        tests = _test_days(plan)
        assert "test_max_hang_7s" not in tests and "test_max_weighted_pullup" not in tests
        reasons = {s["test_id"]: (s["reason"], s.get("required")) for s in plan["skipped_tests"]}
        assert reasons["test_max_hang_7s"] == ("no_placement_slot", True)
        assert reasons["test_max_weighted_pullup"] == ("no_placement_slot", True)

    def test_slipped_week_legacy_does_not_place_covered_axes(self):
        # End-of-SP week: legacy PASS 3 would place the hang + pull-up tests;
        # with the policy they slipped, only the (uncovered) repeater remains.
        kw = _kwargs("strength_power", "2026-10-12", is_last_week_of_phase=True)
        legacy = _test_days(generate_phase_week(**kw))
        assert "test_max_hang_7s" in legacy
        dec = _decision(_daniele(), "2026-10-12")
        plan = generate_phase_week(**kw, retest_decisions=dec)
        tests = _test_days(plan)
        assert "test_max_hang_7s" not in tests and "test_max_weighted_pullup" not in tests
        reasons = {s["test_id"]: s["reason"] for s in plan["skipped_tests"] if s.get("source") == "retest_policy"}
        assert reasons == {"test_max_hang_7s": "slipped:gap", "test_max_weighted_pullup": "slipped:gap"}

    def test_inject_tests_wins_over_decisions(self):
        dec = _decision(_daniele(), "2026-10-12")
        kw = _kwargs("strength_power", "2026-10-12", is_last_week_of_phase=True, inject_tests=True)
        a = _strip_volatile(generate_phase_week(**kw))
        b = _strip_volatile(generate_phase_week(**kw, retest_decisions=dec))
        b["profile_snapshot"].pop("retest_decisions")
        assert a == b

    def test_hard_cap_respected(self):
        dec = _decision(_daniele(), "2026-10-19")
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, hard_cap_per_week=2,
                                              planning_prefs={"target_training_days_per_week": 6,
                                                              "hard_day_cap_per_week": 2}))
        hard_days = {d for d, s in _sessions(plan) if (s.get("tags") or {}).get("hard")}
        assert len(hard_days) <= 2

    def test_deterministic_plan(self):
        dec = _decision(_daniele(), "2026-10-19")
        a = _strip_volatile(generate_phase_week(**_pe_week(retest_decisions=dec)))
        b = _strip_volatile(generate_phase_week(**_pe_week(retest_decisions=deepcopy(dec))))
        assert a == b

    def test_past_sessions_immutable_after_regeneration(self):
        old = generate_phase_week(**_pe_week())
        mon = old["weeks"][0]["days"][0]
        done = {"slot": "evening", "session_id": "finger_strength_home", "status": "done",
                "actual_exercises": [{"exercise_id": "max_hang_7s", "used_total_load_kg": 104.5}],
                "feedback_summary": {"difficulty": "ok"}}
        mon["sessions"] = [deepcopy(done)]
        dec = _decision(_daniele(), "2026-10-19", today="2026-10-20")
        fresh = generate_phase_week(**_pe_week(retest_decisions=dec, today="2026-10-20"))
        merged = regenerate_preserving_completed(old, fresh, preserve_before="2026-10-20")
        mon_after = merged["weeks"][0]["days"][0]
        assert mon_after["sessions"] == [done]


# ---------------------------------------------------------------------------
# retest_status
# ---------------------------------------------------------------------------

def _plan_with_tests(day: str, extra_sessions=()) -> dict:
    ws = (date.fromisoformat(day) - timedelta(days=date.fromisoformat(day).weekday()))
    days = []
    for i in range(7):
        d = (ws + timedelta(days=i)).isoformat()
        sessions = [dict(s) for dd, s in extra_sessions if dd == d]
        if d == day:
            sessions += [{"session_id": "test_max_hang_7s", "slot": "lunch",
                          "tags": {"hard": True, "finger": True, "test": True}},
                         {"session_id": "test_max_weighted_pullup", "slot": "evening",
                          "tags": {"hard": True, "finger": False, "test": True}}]
        days.append({"date": d, "weekday": _DAYS[i], "sessions": sessions})
    return {"start_date": ws.isoformat(), "weeks": [{"days": days}], "profile_snapshot": {}}


class TestStatus:
    def test_trend_confidence_and_projection(self):
        st = retest = rp.retest_status(_daniele(), "2026-10-04", finger_device="hangboard")
        f, p = st["axes"]["finger"], st["axes"]["pulling"]
        assert st["covered_axes"] == ["finger", "pulling"]
        assert (f["official_total_kg"], f["test_date"], f["confidence"]) == (116.0, "2026-09-24", "low")
        assert (f["trend"], f["delta_pct"]) == ("stable", -4.9)
        assert (p["trend"], p["delta_pct"]) == ("stable", 0.8)
        assert f["earliest_retest"] == "2026-10-22"
        assert f["next_test"]["source"] == "projected"
        assert f["next_test"]["date"] == "2026-10-22"
        assert f["next_test"]["trigger"] == rp.TRIGGER_END_OF_PHASE_SLIPPED
        assert retest["stable_band_pct"] == 5.0

    def test_trend_outside_band(self):
        st = _daniele()
        st["tests"]["max_strength"][-1]["total_load_kg"] = 110.0  # −9.8 %
        f = rp.retest_status(st, "2026-10-04")["axes"]["finger"]
        assert f["trend"] == "down"

    def test_planned_test_reason_and_no_blockers_24_10(self):
        # Daniele's real layout: PE gym (pulling + hard) on Thu 22/10, the pair
        # on Sat 24/10 → 48 h exactly: allowed by the unified rule.
        st = _daniele()
        st["week_plans"] = {"2026-10-19": _plan_with_tests("2026-10-24", extra_sessions=[
            ("2026-10-20", {"session_id": "finger_strength_home", "slot": "evening",
                            "tags": {"hard": True, "finger": True}}),
            ("2026-10-22", {"session_id": "power_endurance_gym", "slot": "evening",
                            "tags": {"hard": True, "finger": False}}),
        ])}
        status = rp.retest_status(st, "2026-10-04")
        for axis in ("finger", "pulling"):
            nt = status["axes"][axis]["next_test"]
            assert nt["source"] == "planned" and nt["date"] == "2026-10-24"
            assert nt["trigger"] == rp.TRIGGER_END_OF_PHASE_SLIPPED
            assert nt["blockers"] == []

    def test_live_flags_custom_and_very_hard(self):
        st = _daniele()
        st["week_plans"] = {"2026-10-19": _plan_with_tests("2026-10-24", extra_sessions=[
            ("2026-10-23", {"session_id": "custom_cs_x", "slot": "lunch", "is_custom": True,
                            "exercises": [{"exercise_id": "max_hang_7s", "sets": 5},
                                          {"exercise_id": "weighted_pullup", "sets": 4}]}),
        ])}
        st["feedback_log"] = [{"date": "2026-10-22", "difficulty": "very_hard"}]
        status = rp.retest_status(st, "2026-10-22")
        f_codes = {b["code"] for b in status["axes"]["finger"]["next_test"]["blockers"]}
        p_codes = {b["code"] for b in status["axes"]["pulling"]["next_test"]["blockers"]}
        assert f_codes == {"recent_finger", "very_hard"}
        assert p_codes == {"heavy_pull", "very_hard"}

    def test_uncovered_axis_reported_without_next_test(self):
        st = _daniele()
        status = rp.retest_status(st, "2027-01-10")  # > 90 days
        f = status["axes"]["finger"]
        assert f["covered"] is False and f["next_test"] is None
        assert f["next_test_reason"] == "not_tested_recently"
        assert status["covered_axes"] == []

    def test_no_tests_no_axes(self):
        assert rp.retest_status(_daniele(tests={}), "2026-10-04")["axes"] == {}


# ---------------------------------------------------------------------------
# API: GET /api/week
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    shutil.copy2(FIXTURE_STATE, tmp_state)
    from backend.engine import storage, storage_file
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
    yield tmp_state


def _seed_current(tested: bool) -> None:
    state = deps.load_state(None)
    mc = deepcopy(state["macrocycle"])
    today = date.today()
    mon = today - timedelta(days=today.weekday())
    weeks_before = sum(int(p["duration_weeks"]) for p in mc["phases"][:1]) + 1
    start = mon - timedelta(weeks=weeks_before)
    mc["start_date"] = start.isoformat()
    total = sum(int(p["duration_weeks"]) for p in mc["phases"])
    mc["end_date"] = (start + timedelta(weeks=total) - timedelta(days=1)).isoformat()
    state["macrocycle"] = mc
    state["week_plans"] = {}
    state["current_week_plan"] = None
    state["preferences"] = {"finger_training_device": "hangboard"}
    if tested:
        t = (today - timedelta(days=10)).isoformat()
        state["tests"] = {
            "max_strength": [{"date": t, "test_id": "max_hang_7s_total_load", "total_load_kg": 110.0,
                              "bodyweight_kg": 77.0}],
            "pulling_strength": [{"date": t, "test_id": "weighted_pullup_2rm",
                                  "total_load_2rm_kg": 115.0, "estimated_1rm_kg": 120.5,
                                  "bodyweight_kg": 77.0}],
        }
    deps.save_state(state, None)


class TestApi:
    def test_tested_user_gets_retest_status(self, isolated_state):
        _seed_current(tested=True)
        r = client.get("/api/week/0")
        assert r.status_code == 200, r.text
        body = r.json()
        rs = body.get("retest_status")
        assert rs and rs["covered_axes"] == ["finger", "pulling"]
        assert rs["axes"]["finger"]["official_total_kg"] == 110.0
        assert "test_reminder" not in body
        snap = body["week_plan"]["profile_snapshot"]
        assert snap["retest_decisions"]["covered_axes"] == ["finger", "pulling"]

    def test_untested_user_unchanged(self, isolated_state):
        _seed_current(tested=False)
        r = client.get("/api/week/0")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "retest_status" not in body
        assert "retest_decisions" not in (body["week_plan"].get("profile_snapshot") or {})


class TestReminderDerivation:
    def test_legacy_reminder_function_unchanged(self):
        # The planner function keeps its contract; week.py suppresses it for
        # covered athletes (see TestApi).
        assert should_show_test_reminder({}, 5) is not None
        assert should_show_test_reminder({}, 4) is None


# ---------------------------------------------------------------------------
# A289 review fixes
# ---------------------------------------------------------------------------

def _estimated_baselines_state() -> dict:
    """Never tested: only the baselines estimated at onboarding."""
    return _daniele(tests={}, baselines={
        "hangboard": [{"max_total_load_kg": 90, "source": "estimated", "updated_at": "2026-09-01"}],
        "pulling": {"weighted_pullup_2rm_total_kg": 100, "source": "estimated",
                    "updated_at": "2026-09-01"},
    })


class TestReviewFixes:
    def test_estimated_baselines_never_shown_as_tested_maxes(self):
        st = _estimated_baselines_state()
        status = rp.retest_status(st, "2026-10-04")
        assert status["axes"] == {} and status["covered_axes"] == []
        from backend.api.routers.week import _compute_retest_status
        assert _compute_retest_status(st, None) is None

    def test_stale_real_test_still_reported(self):
        # A real test older than 90 days is still a tested max (uncovered).
        status = rp.retest_status(_daniele(), "2027-01-10")
        assert status["axes"]["finger"]["covered"] is False

    def test_hang_block_is_inclusive_three_days(self):
        # Finger-hard Wed 21 evening → Sat 24 morning is ~60 h < 72 h: blocked.
        dec = deepcopy(_decision(_daniele(), "2026-10-19"))
        dec["finger_hard_dates"] = ["2026-10-21"]
        for r in dec["required_sessions"]:
            r["allowed_dates"] = ["2026-10-24"]
        plan = generate_phase_week(**_pe_week(retest_decisions=dec))
        assert "test_max_hang_7s" not in _test_days(plan)
        live = rp.test_day_blockers(_daniele(week_plans={"2026-10-19": _plan_with_tests(
            "2026-10-24", extra_sessions=[("2026-10-21", {
                "session_id": "finger_strength_home", "slot": "evening",
                "tags": {"hard": True, "finger": True}})])}), "finger", "2026-10-24")
        assert {b["code"] for b in live} == {"recent_finger"}

    def test_no_finger_hard_session_planned_in_hang_test_window(self):
        # Plan-wide invariant: no finger-hard session in the 3 days before the hang test.
        from backend.engine.stimulus import is_finger_hard_session
        dec = _decision(_daniele(), "2026-10-19")
        plan = generate_phase_week(**_pe_week(retest_decisions=dec))
        hd = date.fromisoformat(_test_days(plan)["test_max_hang_7s"][0])
        for d, s in _sessions(plan):
            gap = (hd - date.fromisoformat(d)).days
            if 0 < gap <= 3:
                assert not is_finger_hard_session(s), (d, s["session_id"])

    def test_legacy_pass3_keeps_finger_tests_out_of_hang_window(self):
        st = _daniele()
        for k in ("max_strength", "pulling_strength"):
            st["tests"][k][-1]["date"] = "2026-08-20"
            st["tests"][k][-1].pop("confidence", None)
        dec = deepcopy(rp.retest_decisions(st, "2026-10-12", today="2026-10-12",
                                           finger_device="hangboard"))
        for r in dec["required_sessions"]:
            r["allowed_dates"] = ["2026-10-16"]
        days = [d for d in _DAYS if d not in ("thu", "sat")]
        kw = _kwargs("strength_power", "2026-10-12", is_last_week_of_phase=True,
                     availability=_avail(days=days))
        tests = _test_days(generate_phase_week(**kw, retest_decisions=dec))
        assert tests["test_max_hang_7s"][0] == "2026-10-16"
        rep = tests.get("test_repeater_7_3")
        if rep:
            gap = (date(2026, 10, 16) - date.fromisoformat(rep[0])).days
            assert not 0 < gap <= 3

    def test_locked_slots_of_old_plan_are_not_used(self):
        # The old plan has a session skipped in advance on Sun 25 morning: the
        # merge puts it back over that slot, so PASS 3a must not use it
        # (unlocked, the hang lands exactly there and is overwritten).
        st = _daniele()
        old = _plan_with_tests("2026-10-25")
        for d in old["weeks"][0]["days"]:
            d["sessions"] = []
            if d["date"] == "2026-10-25":
                d["sessions"] = [{"session_id": "finger_strength_home", "slot": "morning",
                                  "status": "skipped", "tags": {"hard": True, "finger": True}}]
        st["week_plans"] = {"2026-10-19": old}
        dec = deepcopy(_decision(st, "2026-10-19", today="2026-10-19"))
        assert dec["locked_slots"] == [{"date": "2026-10-25", "slot": "morning"}]
        for r in dec["required_sessions"]:
            r["allowed_dates"] = ["2026-10-25"]
        fresh = generate_phase_week(**_pe_week(retest_decisions=dec, today="2026-10-19"))
        merged = regenerate_preserving_completed(old, fresh, preserve_before="2026-10-19")
        rows = fresh["profile_snapshot"]["retest_decisions"]["required_sessions"]
        assert [r["status"] for r in rows] == ["placed", "placed"]
        merged_tests = _test_days(merged)
        for row in rows:
            assert merged_tests[row["session_id"]] == (row["placed_date"], row["placed_slot"])
        assert merged_tests["test_max_hang_7s"] == ("2026-10-25", "lunch")

    def test_today_with_done_session_is_locked(self):
        # Today (Thu 22) holds a done session: the merge copies the day
        # wholesale, so a test placed there would vanish.
        st = _daniele()
        old = _plan_with_tests("2026-10-25")
        for d in old["weeks"][0]["days"]:
            d["sessions"] = []
            if d["date"] == "2026-10-22":
                d["sessions"] = [{"session_id": "technique_focus_gym", "slot": "morning",
                                  "status": "done", "tags": {}}]
        st["week_plans"] = {"2026-10-19": old}
        dec = deepcopy(_decision(st, "2026-10-19", today="2026-10-22"))
        assert dec["locked_dates"] == ["2026-10-22"]
        for r in dec["required_sessions"]:
            r["allowed_dates"] = ["2026-10-22"]
        plan = generate_phase_week(**_pe_week(retest_decisions=dec, today="2026-10-22"))
        assert _test_days(plan) == {} or all(d != "2026-10-22" for d, _s in _test_days(plan).values())
        reasons = {s["test_id"]: s["reason"] for s in plan["skipped_tests"]
                   if s.get("source") == "retest_policy"}
        assert reasons["test_max_hang_7s"] == "no_placement_slot"

    def test_projection_skips_a_generated_week_without_the_test(self):
        # The slipped week 19/10 is already generated without tests (PASS 3a
        # skipped them): no "next test from 22/10" promise.
        st = _daniele()
        plan = _plan_with_tests("2026-10-25")
        for d in plan["weeks"][0]["days"]:
            d["sessions"] = []
        plan["profile_snapshot"] = {"retest_decisions": {"required_sessions": [
            {"axis": "finger", "status": "skipped", "skip_reason": "no_placement_slot"},
            {"axis": "pulling", "status": "skipped", "skip_reason": "no_placement_slot"},
        ]}}
        st["week_plans"] = {"2026-10-19": plan}
        status = rp.retest_status(st, "2026-10-19")
        for axis in ("finger", "pulling"):
            nt = status["axes"][axis]["next_test"]
            assert nt is None or nt["week_start"] > "2026-10-19"
        # Not generated → still projected there.
        st["week_plans"] = {}
        assert rp.retest_status(st, "2026-10-19")["axes"]["finger"]["next_test"]["date"] == "2026-10-22"

    def test_order_of_generation_does_not_move_the_test(self):
        # Maintenance (24/09 + 84 d = 17/12) with no phase trigger: a long PE phase.
        mc = {"start_date": "2026-09-07", "phases": [
            {"phase_id": "base", "duration_weeks": 2},
            {"phase_id": "strength_power", "duration_weeks": 2},
            {"phase_id": "power_endurance", "duration_weeks": 16},
        ]}
        st = _daniele(macrocycle=mc)
        w, w1 = "2026-12-14", "2026-12-21"
        # W+1 opened first while W is not generated: deferred to W.
        d1 = _decision(st, w1, today="2026-12-14")
        assert d1["required_sessions"] == []
        assert {s["skip_reason"] for s in d1["skipped"]} == {"deferred:earlier_week"}
        # W generated (empty) first, then W+1: W places; W+1 sees it scheduled.
        dw = _decision(st, w, today="2026-12-14")
        assert {r["trigger"] for r in dw["required_sessions"]} == {rp.TRIGGER_MAINTENANCE}


class TestReminderPartialCoverage:
    def test_reminder_kept_when_only_pulling_is_covered(self, isolated_state):
        _seed_current(tested=True)
        state = deps.load_state(None)
        state["preferences"] = {"finger_training_device": "loading_pin"}
        deps.save_state(state, None)
        body = client.get("/api/week/0").json()
        assert body["retest_status"]["covered_axes"] == ["pulling"]
        state = deps.load_state(None)
        state["test_reminder_postponed_to"] = body["week_num"]
        deps.save_state(state, None)
        body = client.get("/api/week/0").json()
        assert body.get("test_reminder") is not None

    def test_reminder_hidden_when_every_axis_is_covered(self, isolated_state):
        _seed_current(tested=True)
        body = client.get("/api/week/0").json()
        state = deps.load_state(None)
        state["test_reminder_postponed_to"] = body["week_num"]
        deps.save_state(state, None)
        body = client.get("/api/week/0").json()
        assert body["retest_status"]["covered_axes"] == ["finger", "pulling"]
        assert "test_reminder" not in body

    def test_untested_with_estimated_baselines_gets_no_status(self, isolated_state):
        _seed_current(tested=False)
        state = deps.load_state(None)
        state["baselines"] = _estimated_baselines_state()["baselines"]
        state["tests"] = {}
        deps.save_state(state, None)
        body = client.get("/api/week/0").json()
        assert "retest_status" not in body
