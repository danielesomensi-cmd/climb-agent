"""B388 — no test may straddle a midnight (conftest ``_no_test_straddles_midnight``).

The suite has ~55 tests that read "today" in a fixture and again (through the
API) in the body. Across Sunday->Monday midnight the two reads land in different
weeks and the test fails on correct product code. These tests pin the guard on a
fake clock, so they are deterministic at any hour.
"""
import importlib.util
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "b388_conftest", Path(__file__).with_name("conftest.py"))
cf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cf)

# Sunday 2026-10-18 23:59:59.5 UTC — half a second before the week changes.
SUN_LATE = datetime(2026, 10, 19, tzinfo=timezone.utc).timestamp() - 0.5


class FakeClock:
    def __init__(self, ts):
        self.ts = ts

    def now(self):
        return self.ts

    def sleep(self, s):
        self.ts += s

    def utc_date(self):
        return datetime.fromtimestamp(self.ts, timezone.utc).date()


def _simulated_test(clock, duration_s=0.5):
    """The failing shape: 'today' read in the fixture, then again in the body."""
    in_fixture = clock.utc_date()
    clock.sleep(duration_s)
    in_body = clock.utc_date()
    return in_fixture, in_body


def test_without_guard_a_test_straddles_the_week_boundary():
    clock = FakeClock(SUN_LATE)
    in_fixture, in_body = _simulated_test(clock)
    assert (in_fixture, in_body) == (date(2026, 10, 18), date(2026, 10, 19))


def test_guard_waits_out_the_boundary_so_both_reads_agree():
    clock = FakeClock(SUN_LATE)
    waited = cf._wait_out_midnight(clock.now, clock.sleep)
    assert 0.5 < waited <= 1.0
    in_fixture, in_body = _simulated_test(clock)
    assert in_fixture == in_body == date(2026, 10, 19)


@pytest.mark.parametrize("before_s", [0.001, 1.0, cf._MIDNIGHT_GUARD_S])
def test_guard_triggers_inside_the_window(before_s):
    ts = datetime(2026, 10, 19, tzinfo=timezone.utc).timestamp() - before_s
    assert cf._midnight_wait_s(ts) > 0


@pytest.mark.parametrize("hour", [0, 6, 12, 18, 23])
def test_guard_is_a_no_op_away_from_midnight(hour):
    ts = datetime(2026, 10, 18, hour, 0, 30, tzinfo=timezone.utc).timestamp()
    clock = FakeClock(ts)
    assert cf._wait_out_midnight(clock.now, clock.sleep) == 0.0
    assert clock.ts == ts


def test_live_guard_holds_for_this_test():
    import time

    assert cf._seconds_until_next_midnight(time.time()) > 0
