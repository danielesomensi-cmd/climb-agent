"""Tests for compute_new_macrocycle_start_date (A-NEW-MACRO)."""

from __future__ import annotations

from datetime import date

from backend.engine.macrocycle_v1 import compute_new_macrocycle_start_date


def _make_state(end_date: str | None) -> dict:
    if end_date is None:
        return {}
    return {"macrocycle": {"end_date": end_date}}


class TestNoCurrentMacrocycle:
    def test_today_is_monday_returns_today(self):
        # 2026-05-04 is a Monday.
        today = date(2026, 5, 4)
        result = compute_new_macrocycle_start_date({}, today)
        assert result == date(2026, 5, 4)

    def test_today_is_wednesday_returns_next_monday(self):
        # 2026-05-06 is a Wednesday → next Monday is 2026-05-11.
        today = date(2026, 5, 6)
        result = compute_new_macrocycle_start_date({}, today)
        assert result == date(2026, 5, 11)

    def test_today_is_sunday_returns_tomorrow(self):
        # 2026-05-10 is a Sunday → next Monday is 2026-05-11.
        today = date(2026, 5, 10)
        result = compute_new_macrocycle_start_date({}, today)
        assert result == date(2026, 5, 11)


class TestCurrentMacrocycleEnded:
    def test_ended_in_past_returns_monday_on_or_after_today(self):
        # Cycle ended last week, today is Wed → next Monday from today.
        state = _make_state("2026-04-30")
        today = date(2026, 5, 6)
        result = compute_new_macrocycle_start_date(state, today)
        # max(today, end+1=2026-05-01) == today; next Monday after Wed = 2026-05-11.
        assert result == date(2026, 5, 11)

    def test_ended_yesterday_today_is_monday_returns_today(self):
        state = _make_state("2026-05-03")  # Sunday end.
        today = date(2026, 5, 4)  # Monday.
        result = compute_new_macrocycle_start_date(state, today)
        assert result == date(2026, 5, 4)


class TestCurrentMacrocycleOngoing:
    def test_ends_in_future_returns_first_monday_after_end(self):
        # Cycle ends 2026-06-30 (Tuesday) → first Monday on or after 2026-07-01.
        state = _make_state("2026-06-30")
        today = date(2026, 5, 6)
        result = compute_new_macrocycle_start_date(state, today)
        # end+1 = 2026-07-01 (Wed) → Monday on or after = 2026-07-06.
        assert result == date(2026, 7, 6)
        assert result.weekday() == 0

    def test_ends_on_sunday_returns_next_monday(self):
        # Cycle ends 2026-07-05 (Sunday) → next Monday = 2026-07-06.
        state = _make_state("2026-07-05")
        today = date(2026, 5, 6)
        result = compute_new_macrocycle_start_date(state, today)
        assert result == date(2026, 7, 6)


class TestEdgeCases:
    def test_malformed_end_date_falls_back_to_today_logic(self):
        state = {"macrocycle": {"end_date": "not-a-date"}}
        today = date(2026, 5, 6)  # Wednesday.
        result = compute_new_macrocycle_start_date(state, today)
        # Falls back to today logic → next Monday.
        assert result == date(2026, 5, 11)

    def test_missing_end_date_falls_back_to_today_logic(self):
        state = {"macrocycle": {"start_date": "2026-04-06"}}  # No end_date.
        today = date(2026, 5, 4)  # Monday.
        result = compute_new_macrocycle_start_date(state, today)
        assert result == date(2026, 5, 4)

    def test_result_is_always_monday(self):
        for today_offset in range(0, 14):
            today = date(2026, 5, 4) + __import__("datetime").timedelta(days=today_offset)
            result = compute_new_macrocycle_start_date({}, today)
            assert result.weekday() == 0, f"Non-Monday: {result} from today={today}"
            assert result >= today, f"Result before today: {result} < {today}"
