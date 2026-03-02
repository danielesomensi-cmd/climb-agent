"""Tests for report engine — weekly and monthly reports."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any, Dict

import pytest

from backend.engine.report_engine import generate_monthly_report, generate_weekly_report


@pytest.fixture
def tmp_log_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def _write_indoor_log(log_dir: str, entries: list):
    """Write indoor session log entries to a JSONL file."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, "sessions_2026.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _write_outdoor_log(log_dir: str, entries: list):
    """Write outdoor session log entries to a JSONL file."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, "outdoor_sessions_2026.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


WEEK_START = "2026-03-16"


def _make_plan_day(date: str, sessions: list, **kwargs) -> Dict[str, Any]:
    """Build a day entry for a week plan."""
    day: Dict[str, Any] = {"date": date, "weekday": "mon", "sessions": sessions}
    day.update(kwargs)
    return day


def _make_session(sid: str, status: str = "planned", load: int = 40, **kwargs) -> Dict[str, Any]:
    s: Dict[str, Any] = {
        "session_id": sid,
        "status": status,
        "slot": "evening",
        "estimated_load_score": load,
        "tags": {},
    }
    s.update(kwargs)
    return s


def _make_week_plan(days: list) -> Dict[str, Any]:
    return {"weeks": [{"days": days}]}


def _make_state(**overrides) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "planning_prefs": {"target_training_days_per_week": 4},
        "current_week_plan": _make_week_plan([
            _make_plan_day("2026-03-16", [_make_session("s1", "planned")]),
            _make_plan_day("2026-03-17", [_make_session("s2", "planned")]),
            _make_plan_day("2026-03-18", [_make_session("s3", "planned")]),
            _make_plan_day("2026-03-19", []),
            _make_plan_day("2026-03-20", [_make_session("s4", "planned")]),
            _make_plan_day("2026-03-21", []),
            _make_plan_day("2026-03-22", []),
        ]),
        "week_plans": {},
        "feedback_log": [],
        "stimulus_recency": {},
        "working_loads": {"entries": [], "rules": {}},
        "macrocycle": None,
        "goal": {},
        "assessment": {},
    }
    base.update(overrides)
    return base


# ── Top-level structure ────────────────────────────────────────────────


class TestWeeklyReportStructure:
    def test_report_type_and_dates(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["report_type"] == "weekly"
        assert report["week_start"] == "2026-03-16"
        assert report["week_end"] == "2026-03-22"

    def test_all_sections_present(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        for key in ("context", "adherence", "load", "difficulty",
                     "stimulus_balance", "progression", "outdoor",
                     "days", "highlights"):
            assert key in report, f"Missing section: {key}"


# ── Context section ────────────────────────────────────────────────────


class TestContext:
    def test_no_macrocycle(self, tmp_log_dir):
        state = _make_state(macrocycle=None)
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        ctx = report["context"]
        assert ctx["phase_id"] is None
        assert ctx["macrocycle_week"] is None

    def test_with_macrocycle(self, tmp_log_dir):
        state = _make_state(macrocycle={
            "start_date": "2026-03-09",
            "total_weeks": 10,
            "phases": [
                {"phase_id": "base", "duration_weeks": 4},
                {"phase_id": "strength_power", "duration_weeks": 3},
                {"phase_id": "deload", "duration_weeks": 3},
            ],
        })
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        ctx = report["context"]
        assert ctx["phase_id"] == "base"
        assert ctx["phase_week"] == 2  # second week of base
        assert ctx["phase_total_weeks"] == 4
        assert ctx["macrocycle_week"] == 2
        assert ctx["macrocycle_total_weeks"] == 10

    def test_with_goal(self, tmp_log_dir):
        state = _make_state(goal={"target_grade": "7a", "discipline": "lead"})
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["context"]["goal"]["target_grade"] == "7a"

    def test_with_profile(self, tmp_log_dir):
        state = _make_state(assessment={
            "profile": {"finger_strength": 60, "endurance": 45}
        })
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["context"]["assessment_profile"]["finger_strength"] == 60

    def test_empty_goal_and_profile(self, tmp_log_dir):
        state = _make_state(goal={}, assessment={})
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["context"]["goal"] is None
        assert report["context"]["assessment_profile"] is None


# ── Adherence section ──────────────────────────────────────────────────


class TestAdherence:
    def test_all_planned_no_done(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        adh = report["adherence"]
        assert adh["planned"] == 4
        assert adh["completed"] == 0
        assert adh["pct"] == 0.0

    def test_full_adherence(self, tmp_log_dir):
        state = _make_state(current_week_plan=_make_week_plan([
            _make_plan_day("2026-03-16", [_make_session("s1", "done")]),
            _make_plan_day("2026-03-17", [_make_session("s2", "done")]),
            _make_plan_day("2026-03-18", [_make_session("s3", "done")]),
            _make_plan_day("2026-03-19", []),
            _make_plan_day("2026-03-20", [_make_session("s4", "done")]),
            _make_plan_day("2026-03-21", []),
            _make_plan_day("2026-03-22", []),
        ]))
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["adherence"]["pct"] == 100.0
        assert report["adherence"]["completed"] == 4

    def test_mixed_done_skipped(self, tmp_log_dir):
        state = _make_state(current_week_plan=_make_week_plan([
            _make_plan_day("2026-03-16", [_make_session("s1", "done")]),
            _make_plan_day("2026-03-17", [_make_session("s2", "skipped")]),
            _make_plan_day("2026-03-18", [_make_session("s3", "done")]),
            _make_plan_day("2026-03-19", []),
            _make_plan_day("2026-03-20", [_make_session("s4", "planned")]),
            _make_plan_day("2026-03-21", []),
            _make_plan_day("2026-03-22", []),
        ]))
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        adh = report["adherence"]
        assert adh["completed"] == 2
        assert adh["skipped"] == 1
        assert adh["pct"] == 50.0
        assert len(adh["skipped_sessions"]) == 1
        assert adh["skipped_sessions"][0]["session_id"] == "s2"

    def test_no_plan(self, tmp_log_dir):
        state = _make_state(current_week_plan=None)
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["adherence"]["planned"] == 0
        assert report["adherence"]["pct"] == 0.0

    def test_added_sessions_counted(self, tmp_log_dir):
        state = _make_state(current_week_plan=_make_week_plan([
            _make_plan_day("2026-03-16", [
                _make_session("s1", "done"),
                _make_session("s_extra", "done", tags={"added": True}),
            ]),
        ]))
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["adherence"]["added"] == 1


# ── Load section ───────────────────────────────────────────────────────


class TestLoad:
    def test_planned_total(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        # 4 sessions × 40 load each
        assert report["load"]["planned_total"] == 160

    def test_actual_total_with_done(self, tmp_log_dir):
        state = _make_state(current_week_plan=_make_week_plan([
            _make_plan_day("2026-03-16", [_make_session("s1", "done", load=50)]),
            _make_plan_day("2026-03-17", [_make_session("s2", "planned", load=30)]),
        ]))
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["load"]["planned_total"] == 80
        assert report["load"]["actual_total"] == 50

    def test_load_ratio(self, tmp_log_dir):
        state = _make_state(current_week_plan=_make_week_plan([
            _make_plan_day("2026-03-16", [_make_session("s1", "done", load=40)]),
            _make_plan_day("2026-03-17", [_make_session("s2", "done", load=40)]),
        ]))
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["load"]["load_ratio"] == 1.0

    def test_hard_and_recovery_days(self, tmp_log_dir):
        state = _make_state(current_week_plan=_make_week_plan([
            _make_plan_day("2026-03-16", [_make_session("s1", tags={"hard": True})]),
            _make_plan_day("2026-03-17", []),
            _make_plan_day("2026-03-18", [_make_session("s2", tags={"hard": True})]),
            _make_plan_day("2026-03-19", []),
            _make_plan_day("2026-03-20", [_make_session("s3")]),
            _make_plan_day("2026-03-21", []),
            _make_plan_day("2026-03-22", []),
        ]))
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["load"]["hard_days"] == 2
        assert report["load"]["recovery_days"] == 4

    def test_indoor_and_outdoor_minutes(self, tmp_log_dir):
        _write_indoor_log(tmp_log_dir, [
            {"date": "2026-03-16", "session_id": "s1", "duration_minutes": 90},
        ])
        _write_outdoor_log(tmp_log_dir, [{
            "log_version": "outdoor.v1",
            "date": "2026-03-21",
            "spot_name": "Spot",
            "discipline": "boulder",
            "duration_minutes": 180,
            "routes": [],
        }])
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["load"]["indoor_minutes"] == 90
        assert report["load"]["outdoor_minutes"] == 180


# ── Difficulty section ─────────────────────────────────────────────────


class TestDifficulty:
    def test_no_feedback(self, tmp_log_dir):
        state = _make_state(feedback_log=[])
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        diff = report["difficulty"]
        assert diff["distribution"] == {}
        assert diff["avg_label"] == "ok"  # default
        assert diff["hardest_session"] is None
        assert diff["easiest_session"] is None

    def test_with_feedback(self, tmp_log_dir):
        state = _make_state(feedback_log=[
            {"date": "2026-03-16", "session_id": "s1", "difficulty": "hard"},
            {"date": "2026-03-18", "session_id": "s3", "difficulty": "easy"},
        ])
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        diff = report["difficulty"]
        assert diff["distribution"]["hard"] == 1
        assert diff["distribution"]["easy"] == 1
        assert diff["hardest_session"]["session_id"] == "s1"
        assert diff["easiest_session"]["session_id"] == "s3"

    def test_avg_label(self, tmp_log_dir):
        state = _make_state(feedback_log=[
            {"date": "2026-03-16", "session_id": "s1", "difficulty": "very_hard"},
            {"date": "2026-03-17", "session_id": "s2", "difficulty": "hard"},
            {"date": "2026-03-18", "session_id": "s3", "difficulty": "hard"},
        ])
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["difficulty"]["avg_label"] in ("hard", "very_hard")

    def test_feedback_outside_week_ignored(self, tmp_log_dir):
        state = _make_state(feedback_log=[
            {"date": "2026-03-10", "session_id": "old", "difficulty": "very_hard"},
            {"date": "2026-03-16", "session_id": "s1", "difficulty": "ok"},
        ])
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert "old" not in str(report["difficulty"]["distribution"])
        assert report["difficulty"]["distribution"].get("ok") == 1


# ── Stimulus balance section ──────────────────────────────────────────


class TestStimulusBalance:
    def test_categories_present(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        sb = report["stimulus_balance"]
        assert "finger_strength" in sb
        assert "boulder_power" in sb
        assert "endurance" in sb
        assert "complementaries" in sb

    def test_done_sessions_counted(self, tmp_log_dir):
        state = _make_state(current_week_plan=_make_week_plan([
            _make_plan_day("2026-03-16", [
                _make_session("finger_strength_home", "done",
                              tags={"finger": True}),
            ]),
            _make_plan_day("2026-03-17", [
                _make_session("endurance_aerobic_gym", "done"),
            ]),
        ]))
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        sb = report["stimulus_balance"]
        assert sb["finger_strength"]["sessions_this_week"] == 1
        assert sb["endurance"]["sessions_this_week"] == 1

    def test_days_since_last(self, tmp_log_dir):
        state = _make_state(stimulus_recency={
            "finger_strength": {"last_done_date": "2026-03-10", "done_count": 5},
        })
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        sb = report["stimulus_balance"]
        assert sb["finger_strength"]["days_since_last"] == 6  # Mar 16 - Mar 10

    def test_no_recency_data(self, tmp_log_dir):
        state = _make_state(stimulus_recency={})
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        sb = report["stimulus_balance"]
        assert sb["finger_strength"]["days_since_last"] is None


# ── Progression section ───────────────────────────────────────────────


class TestProgression:
    def test_no_updates(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["progression"] == []

    def test_load_increase(self, tmp_log_dir):
        state = _make_state(working_loads={
            "entries": [{
                "exercise_id": "max_hang_5s",
                "last_external_load_kg": 15.0,
                "next_external_load_kg": 16.5,
                "updated_at": "2026-03-17",
            }],
            "rules": {},
        })
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        prog = report["progression"]
        assert len(prog) == 1
        assert prog[0]["exercise_id"] == "max_hang_5s"
        assert prog[0]["direction"] == "up"
        assert prog[0]["change_pct"] == 10.0

    def test_load_decrease(self, tmp_log_dir):
        state = _make_state(working_loads={
            "entries": [{
                "exercise_id": "weighted_pullup",
                "last_external_load_kg": 20.0,
                "next_external_load_kg": 18.0,
                "updated_at": "2026-03-18",
            }],
            "rules": {},
        })
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        prog = report["progression"]
        assert len(prog) == 1
        assert prog[0]["direction"] == "down"

    def test_grade_based_progression(self, tmp_log_dir):
        state = _make_state(working_loads={
            "entries": [{
                "exercise_id": "limit_bouldering",
                "last_used_grade": "7A",
                "next_target_grade": "7B",
                "updated_at": "2026-03-19",
            }],
            "rules": {},
        })
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        prog = report["progression"]
        assert len(prog) == 1
        assert prog[0]["direction"] == "grade_change"
        assert prog[0]["previous_load"] == "7A"
        assert prog[0]["current_load"] == "7B"

    def test_updates_outside_week_ignored(self, tmp_log_dir):
        state = _make_state(working_loads={
            "entries": [{
                "exercise_id": "max_hang_5s",
                "last_external_load_kg": 15.0,
                "next_external_load_kg": 16.5,
                "updated_at": "2026-03-10",  # before the week
            }],
            "rules": {},
        })
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["progression"] == []


# ── Outdoor section ───────────────────────────────────────────────────


class TestOutdoor:
    def test_no_outdoor(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        out = report["outdoor"]
        assert out["sessions"] == 0
        assert out["total_routes"] == 0
        assert out["top_grade_sent"] is None

    def test_with_outdoor_sessions(self, tmp_log_dir):
        _write_outdoor_log(tmp_log_dir, [{
            "log_version": "outdoor.v1",
            "date": "2026-03-21",
            "spot_name": "Berdorf",
            "discipline": "boulder",
            "duration_minutes": 180,
            "routes": [
                {
                    "name": "Problem A",
                    "grade": "6C",
                    "style": "onsight",
                    "attempts": [{"result": "sent"}],
                },
                {
                    "name": "Problem B",
                    "grade": "7A",
                    "style": "redpoint",
                    "attempts": [{"result": "fell"}, {"result": "sent"}],
                },
                {
                    "name": "Problem C",
                    "grade": "7B",
                    "style": "project",
                    "attempts": [{"result": "fell"}],
                },
            ],
        }])
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        out = report["outdoor"]
        assert out["sessions"] == 1
        assert out["total_routes"] == 3
        assert out["sends"] == 2
        assert out["top_grade_sent"] == "7A"
        assert "Berdorf" in out["spots"]

    def test_onsight_percentage(self, tmp_log_dir):
        _write_outdoor_log(tmp_log_dir, [{
            "log_version": "outdoor.v1",
            "date": "2026-03-21",
            "spot_name": "Crag",
            "discipline": "lead",
            "duration_minutes": 120,
            "routes": [
                {"name": "R1", "grade": "6a", "style": "onsight",
                 "attempts": [{"result": "sent"}]},
                {"name": "R2", "grade": "6b", "style": "redpoint",
                 "attempts": [{"result": "sent"}]},
            ],
        }])
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["outdoor"]["onsight_pct"] == 50.0


# ── Days section ──────────────────────────────────────────────────────


class TestDays:
    def test_seven_entries(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert len(report["days"]) == 7

    def test_dates_correct(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        dates = [d["date"] for d in report["days"]]
        assert dates[0] == "2026-03-16"
        assert dates[6] == "2026-03-22"

    def test_weekday_labels(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["days"][0]["weekday"] == "mon"
        assert report["days"][6]["weekday"] == "sun"

    def test_rest_day_detection(self, tmp_log_dir):
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        # Day 4 (index 3, Thursday) has no sessions
        assert report["days"][3]["is_rest_day"] is True
        # Day 1 (index 0, Monday) has sessions
        assert report["days"][0]["is_rest_day"] is False

    def test_session_details_in_days(self, tmp_log_dir):
        state = _make_state(current_week_plan=_make_week_plan([
            _make_plan_day("2026-03-16", [_make_session("s1", "done", load=50)]),
        ]))
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        day = report["days"][0]
        assert len(day["sessions"]) == 1
        assert day["sessions"][0]["session_id"] == "s1"
        assert day["sessions"][0]["status"] == "done"
        assert day["sessions"][0]["estimated_load_score"] == 50

    def test_outdoor_info_in_day(self, tmp_log_dir):
        state = _make_state(current_week_plan=_make_week_plan([
            _make_plan_day("2026-03-21", [],
                           outdoor_slot=True,
                           outdoor_spot_name="Berdorf",
                           outdoor_discipline="boulder",
                           outdoor_session_status="done"),
        ]))
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        # Saturday
        day = [d for d in report["days"] if d["date"] == "2026-03-21"][0]
        assert day["outdoor"] is not None
        assert day["outdoor"]["spot_name"] == "Berdorf"
        assert day["outdoor"]["status"] == "done"
        assert day["is_rest_day"] is False


# ── Highlights section ────────────────────────────────────────────────


class TestHighlights:
    def _get_highlight_keys(self, highlights):
        return [h["key"] for h in highlights]

    def test_high_adherence_positive(self, tmp_log_dir):
        state = _make_state(current_week_plan=_make_week_plan([
            _make_plan_day(f"2026-03-{16+i}", [_make_session(f"s{i+1}", "done")])
            for i in range(4)
        ] + [
            _make_plan_day(f"2026-03-{20+i}", [])
            for i in range(3)
        ]))
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        keys = self._get_highlight_keys(report["highlights"])
        assert "adherence_high" in keys

    def test_low_adherence_warning(self, tmp_log_dir):
        state = _make_state()  # all planned, none done
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        keys = self._get_highlight_keys(report["highlights"])
        assert "adherence_low" in keys

    def test_progression_highlight(self, tmp_log_dir):
        state = _make_state(working_loads={
            "entries": [{
                "exercise_id": "max_hang_5s",
                "last_external_load_kg": 15.0,
                "next_external_load_kg": 17.0,
                "updated_at": "2026-03-17",
            }],
            "rules": {},
        })
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        keys = self._get_highlight_keys(report["highlights"])
        assert "progression" in keys

    def test_stimulus_gap_warning(self, tmp_log_dir):
        state = _make_state(stimulus_recency={
            "finger_strength": {"last_done_date": "2026-03-01", "done_count": 3},
        })
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        keys = self._get_highlight_keys(report["highlights"])
        assert "stimulus_gap_finger_strength" in keys

    def test_outdoor_summary_highlight(self, tmp_log_dir):
        _write_outdoor_log(tmp_log_dir, [{
            "log_version": "outdoor.v1",
            "date": "2026-03-21",
            "spot_name": "Spot",
            "discipline": "boulder",
            "duration_minutes": 120,
            "routes": [{"name": "R1", "grade": "6A", "style": "onsight",
                         "attempts": [{"result": "sent"}]}],
        }])
        state = _make_state()
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        keys = self._get_highlight_keys(report["highlights"])
        assert "outdoor_summary" in keys

    def test_difficulty_high_warning(self, tmp_log_dir):
        state = _make_state(feedback_log=[
            {"date": "2026-03-16", "session_id": "s1", "difficulty": "very_hard"},
            {"date": "2026-03-17", "session_id": "s2", "difficulty": "very_hard"},
        ])
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        keys = self._get_highlight_keys(report["highlights"])
        assert "difficulty_high" in keys

    def test_phase_last_week_info(self, tmp_log_dir):
        state = _make_state(macrocycle={
            "start_date": "2026-03-02",
            "total_weeks": 10,
            "phases": [
                {"phase_id": "base", "duration_weeks": 2},
                {"phase_id": "strength_power", "duration_weeks": 3},
            ],
        })
        # week_start is 2026-03-16 = week 3 of macrocycle = week 1 of strength_power (first week of 3)
        # Let's make it the last week of base instead
        report = generate_weekly_report(state, tmp_log_dir, "2026-03-09")
        keys = self._get_highlight_keys(report["highlights"])
        assert "phase_last_week" in keys

    def test_highlight_types_are_valid(self, tmp_log_dir):
        state = _make_state(feedback_log=[
            {"date": "2026-03-16", "session_id": "s1", "difficulty": "hard"},
        ])
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        valid_types = {"positive", "progress", "warning", "info"}
        for h in report["highlights"]:
            assert h["type"] in valid_types
            assert "key" in h
            assert "text" in h


# ── Week plan lookup ──────────────────────────────────────────────────


class TestWeekPlanLookup:
    def test_uses_week_plans_cache(self, tmp_log_dir):
        cached = _make_week_plan([
            _make_plan_day("2026-03-16", [_make_session("cached_s1", "done")]),
        ])
        state = _make_state(
            week_plans={"2026-03-16": cached},
            current_week_plan=_make_week_plan([
                _make_plan_day("2026-03-16", [_make_session("current_s1")]),
            ]),
        )
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        # Should use cached plan, not current_week_plan
        assert report["adherence"]["completed"] == 1

    def test_falls_back_to_current_week_plan(self, tmp_log_dir):
        state = _make_state(week_plans={})
        report = generate_weekly_report(state, tmp_log_dir, WEEK_START)
        assert report["adherence"]["planned"] == 4


# ── Monthly reports (unchanged) ───────────────────────────────────────


class TestMonthlyReport:
    def test_empty_month(self, tmp_log_dir):
        state = _make_state()
        report = generate_monthly_report(state, tmp_log_dir, "2026-03")
        assert report["report_type"] == "monthly"
        assert report["total_indoor_sessions"] == 0
        assert report["total_outdoor_sessions"] == 0

    def test_with_sessions(self, tmp_log_dir):
        _write_indoor_log(tmp_log_dir, [
            {"date": "2026-03-02", "session_id": "strength_long", "duration_minutes": 120},
            {"date": "2026-03-05", "session_id": "technique_focus_gym", "duration_minutes": 90},
            {"date": "2026-03-10", "session_id": "strength_long", "duration_minutes": 120},
            {"date": "2026-03-15", "session_id": "power_endurance_gym", "duration_minutes": 90},
        ])
        state = _make_state()
        report = generate_monthly_report(state, tmp_log_dir, "2026-03")
        assert report["total_indoor_sessions"] == 4
        assert report["total_indoor_minutes"] == 420
        assert len(report["weekly_session_counts"]) > 0

    def test_suggestion_no_outdoor(self, tmp_log_dir):
        _write_indoor_log(tmp_log_dir, [
            {"date": "2026-03-02", "session_id": "strength_long", "duration_minutes": 120},
        ])
        state = _make_state()
        report = generate_monthly_report(state, tmp_log_dir, "2026-03")
        assert any("outdoor" in s.lower() for s in report["suggestions"])

    def test_suggestion_no_technique(self, tmp_log_dir):
        _write_indoor_log(tmp_log_dir, [
            {"date": f"2026-03-{i+1:02d}", "session_id": "strength_long", "duration_minutes": 90}
            for i in range(5)
        ])
        state = _make_state()
        report = generate_monthly_report(state, tmp_log_dir, "2026-03")
        assert any("technique" in s.lower() for s in report["suggestions"])

    def test_max_three_suggestions(self, tmp_log_dir):
        state = _make_state(planning_prefs={"target_training_days_per_week": 10})
        report = generate_monthly_report(state, tmp_log_dir, "2026-03")
        assert len(report["suggestions"]) <= 3


# ── API integration ─────────────────────────────────────────────────────


class TestReportsAPI:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        from backend.api import deps
        from backend.api.routers import reports as reports_router

        state_path = tmp_path / "user_state.json"
        state_path.write_text(json.dumps({
            "schema_version": "1.5",
            "planning_prefs": {"target_training_days_per_week": 4},
            "current_week_plan": None,
            "week_plans": {},
            "feedback_log": [],
            "stimulus_recency": {},
            "working_loads": {"entries": [], "rules": {}},
            "macrocycle": None,
            "goal": {},
            "assessment": {},
        }))
        monkeypatch.setattr(deps, "STATE_PATH", state_path)

        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr(reports_router, "_FALLBACK_LOG_DIR", log_dir)

        from fastapi.testclient import TestClient
        from backend.api.main import app
        self.client = TestClient(app)

    def test_weekly_report_structure(self):
        r = self.client.get("/api/reports/weekly?week_start=2026-03-16")
        assert r.status_code == 200
        data = r.json()
        assert data["report_type"] == "weekly"
        assert "context" in data
        assert "adherence" in data
        assert "load" in data
        assert "highlights" in data

    def test_monthly_report(self):
        r = self.client.get("/api/reports/monthly?month=2026-03")
        assert r.status_code == 200
        data = r.json()
        assert data["report_type"] == "monthly"
