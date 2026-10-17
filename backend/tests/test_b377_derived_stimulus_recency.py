"""B377 — the weekly report derives «days since last» from the completion log.

The stored ``stimulus_recency`` counters were written only by the
``mark_done``/``mark_skipped`` events (the guided player completes through
``/api/feedback``), so they froze on 2026-10-01 for the main user. The report
now ignores them and reads ``session_completion_log`` + the catalog categories
(A291) at read time.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

import pytest

from backend.engine.report_engine import (
    _build_stimulus_balance,
    _derived_last_done,
    generate_weekly_report,
)

WEEK_START = "2026-03-16"


@pytest.fixture
def tmp_log_dir(tmp_path, monkeypatch):
    from backend.engine import storage
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    yield str(tmp_path / "logs")


def _row(date: str, sid: str, status: str = "done") -> Dict[str, Any]:
    return {"date": date, "session_id": sid, "status": status}


def _state(scl: List[Dict[str, Any]], **overrides) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "planning_prefs": {"target_training_days_per_week": 4},
        "current_week_plan": {"weeks": [{"days": []}]},
        "week_plans": {},
        "feedback_log": [],
        # Stale on purpose: a legacy counter frozen long ago.
        "stimulus_recency": {
            "finger_strength": {"last_done_date": "2025-01-01", "done_count": 1},
            "boulder_power": {"last_done_date": None, "done_count": 0},
        },
        "session_completion_log": scl,
        "working_loads": {"entries": [], "rules": {}},
        "macrocycle": None,
        "goal": {},
        "assessment": {},
    }
    base.update(overrides)
    return base


def _sb(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return generate_weekly_report(state, None, WEEK_START)["stimulus_balance"]


def test_last_done_comes_from_completion_log_not_stale_counter(tmp_log_dir):
    sb = _sb(_state([_row("2026-03-12", "strength_long")]))
    assert sb["finger_strength"]["last_done_date"] == "2026-03-12"
    assert sb["finger_strength"]["days_since_last"] == 4
    # Never derived from the stored (stale) counters.
    assert sb["boulder_power"]["days_since_last"] is None


def test_catalog_categories_multi(tmp_log_dir):
    sb = _sb(_state([
        _row("2026-03-10", "limit_boulder_gym"),
        _row("2026-03-14", "route_endurance_gym"),
        _row("2026-03-15", "core_training"),
    ]))
    assert sb["boulder_power"]["days_since_last"] == 6
    assert sb["finger_strength"]["days_since_last"] == 6
    assert sb["endurance"]["days_since_last"] == 2
    assert sb["complementaries"]["days_since_last"] == 1


def test_undo_falls_back_to_previous_date(tmp_log_dir):
    scl = [_row("2026-03-05", "finger_strength_home"), _row("2026-03-13", "strength_long")]
    assert _sb(_state(scl))["finger_strength"]["last_done_date"] == "2026-03-13"
    # mark_planned removes the row → the derived view falls back.
    sb = _sb(_state(scl[:1]))
    assert sb["finger_strength"]["last_done_date"] == "2026-03-05"
    assert sb["finger_strength"]["days_since_last"] == 11


def test_double_mark_done_changes_nothing(tmp_log_dir):
    once = _sb(_state([_row("2026-03-13", "strength_long")]))
    twice = _sb(_state([_row("2026-03-13", "strength_long")] * 2))
    assert once == twice


def test_skipped_is_not_done(tmp_log_dir):
    sb = _sb(_state([
        _row("2026-03-02", "strength_long"),
        _row("2026-03-14", "strength_long", "skipped"),
    ]))
    assert sb["finger_strength"]["last_done_date"] == "2026-03-02"


def test_custom_and_generated_without_content_do_not_count(tmp_log_dir):
    # B383: customs count by their CONTENT; with no definition in
    # state.custom_sessions and no plan copy there is nothing to categorise.
    sb = _sb(_state([
        _row("2026-03-14", "custom_cs_abc"),
        _row("2026-03-14", "generated_hiit_2026-03-14_lunch"),
        _row("2026-03-14", ""),
    ]))
    for cat in sb:
        assert sb[cat]["days_since_last"] is None


def test_custom_done_this_week_without_exercises_not_counted(tmp_log_dir):
    # B383: a custom counts by its exercises, never by its id or its tags.
    plan = {"weeks": [{"days": [{"date": "2026-03-17", "sessions": [
        {"session_id": "custom_cs_abc", "status": "done", "is_custom": True,
         "tags": {"finger": True, "hard": True}},
        {"session_id": "strength_long", "status": "done", "tags": {}},
    ]}]}]}
    sb = _build_stimulus_balance(plan, [], WEEK_START)
    assert sb["finger_strength"]["sessions_this_week"] == 1
    assert sb["complementaries"]["sessions_this_week"] == 0


def test_rows_in_or_after_the_week_are_not_before_it(tmp_log_dir):
    # A report week reads «days since the last one before the week»: a done
    # session inside the week (or later) never yields a 0/negative gap.
    sb = _sb(_state([
        _row("2026-03-08", "strength_long"),
        _row("2026-03-17", "strength_long"),
        _row("2026-04-01", "strength_long"),
    ]))
    assert sb["finger_strength"]["last_done_date"] == "2026-03-08"
    assert sb["finger_strength"]["days_since_last"] == 8


def test_malformed_rows_ignored():
    last = _derived_last_done([
        {"date": "garbage", "session_id": "strength_long", "status": "done"},
        "not a dict",
        {"session_id": "strength_long", "status": "done"},
    ], WEEK_START)
    assert last == {}


def test_deterministic_and_read_only(tmp_log_dir):
    state = _state([
        _row("2026-03-12", "strength_long"),
        _row("2026-03-02", "power_contact_gym"),
        _row("2026-03-09", "regeneration_easy", "skipped"),
    ])
    snapshot = copy.deepcopy(state)
    a = generate_weekly_report(state, None, WEEK_START)
    b = generate_weekly_report(state, None, WEEK_START)
    assert a["stimulus_balance"] == b["stimulus_balance"]
    assert a["highlights"] == b["highlights"]
    # No write: completion log, legacy counters, past data all untouched.
    assert state == snapshot


def test_gap_highlight_uses_derived_value(tmp_log_dir):
    report = generate_weekly_report(
        _state([_row("2026-03-01", "strength_long")]), None, WEEK_START,
    )
    keys = {h["key"] for h in report["highlights"]}
    assert "stimulus_gap_finger_strength" in keys
    # The stale counter (2025-01-01) would have said 439 days.
    text = next(h["text"] for h in report["highlights"] if h["key"] == "stimulus_gap_finger_strength")
    assert "15 days" in text
