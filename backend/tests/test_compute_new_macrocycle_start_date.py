"""Tests for compute_new_macrocycle_start_date.

A-NEW-MACRO introduced this helper using max(end+1, today) → Monday on/after
semantics. B-NEWMACRO-STARTDATE-FIX flipped the rule: the new cycle now
ALWAYS starts the next Monday strictly after today, regardless of the current
macrocycle's end_date. The state.macrocycle is no longer consulted.
"""

from __future__ import annotations

from datetime import date, timedelta

from backend.engine.macrocycle_v1 import compute_new_macrocycle_start_date


def _make_state(end_date: str | None) -> dict:
    if end_date is None:
        return {}
    return {"macrocycle": {"end_date": end_date}}


# ── State should NOT influence the result ──────────────────────────────────


class TestStateIgnored:
    def test_no_macrocycle_today_is_wednesday(self):
        # 2026-05-06 is a Wednesday → next Monday is 2026-05-11.
        result = compute_new_macrocycle_start_date({}, date(2026, 5, 6))
        assert result == date(2026, 5, 11)

    def test_no_macrocycle_today_is_sunday(self):
        # 2026-05-10 is a Sunday → next Monday is 2026-05-11.
        result = compute_new_macrocycle_start_date({}, date(2026, 5, 10))
        assert result == date(2026, 5, 11)

    def test_no_macrocycle_today_is_monday_returns_today_plus_7(self):
        # 2026-05-04 is a Monday → strict next Monday = 2026-05-11.
        result = compute_new_macrocycle_start_date({}, date(2026, 5, 4))
        assert result == date(2026, 5, 11)

    def test_current_macrocycle_ended_is_ignored(self):
        # Cycle ended last week; result driven entirely by today.
        state = _make_state("2026-04-30")
        result = compute_new_macrocycle_start_date(state, date(2026, 5, 6))
        assert result == date(2026, 5, 11)

    def test_current_macrocycle_ongoing_is_ignored(self):
        """Regression for B-NEWMACRO-STARTDATE-FIX: a cycle ending in 2099
        used to push the new start_date to 2099. After the fix, the new
        cycle starts the Monday after today."""
        state = _make_state("2099-06-30")
        result = compute_new_macrocycle_start_date(state, date(2026, 5, 6))
        assert result == date(2026, 5, 11)

    def test_current_macrocycle_ending_tomorrow_is_ignored(self):
        state = _make_state("2026-05-07")
        result = compute_new_macrocycle_start_date(state, date(2026, 5, 6))
        assert result == date(2026, 5, 11)

    def test_malformed_end_date_is_ignored(self):
        state = {"macrocycle": {"end_date": "not-a-date"}}
        result = compute_new_macrocycle_start_date(state, date(2026, 5, 6))
        assert result == date(2026, 5, 11)


# ── Always Monday, always strictly after today ─────────────────────────────


class TestStrictNextMondayInvariant:
    def test_result_is_always_monday_strictly_after_today(self):
        """Sweep 14 days starting from a Monday; every result must be Monday
        AND strictly greater than today."""
        for offset in range(14):
            today = date(2026, 5, 4) + timedelta(days=offset)
            result = compute_new_macrocycle_start_date({}, today)
            assert result.weekday() == 0, f"Non-Monday: {result} from today={today}"
            assert result > today, (
                f"Result not strictly > today: {result} <= {today}"
            )
            # And it's at most 7 days away.
            assert (result - today).days <= 7

    def test_today_is_monday_returns_exactly_today_plus_7(self):
        # Pin the strict semantics: Monday → +7, never same day.
        for monday_offset in (0, 7, 14, 21):
            today = date(2026, 5, 4) + timedelta(days=monday_offset)
            assert today.weekday() == 0
            result = compute_new_macrocycle_start_date({}, today)
            assert result == today + timedelta(days=7)
