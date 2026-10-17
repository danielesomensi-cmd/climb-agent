"""B388 — the ad-hoc builder reads the macrocycle phase on the SESSION day.

``compose_adhoc_session(..., today=D)`` took loads and guards on ``D`` but the
phase on the wall clock (``adhoc_builder._current_phase`` →
``current_phase_and_week`` → ``date.today()``). The C272 golden pins the
builder on 2026-10-07 (strength_power of the a290 macrocycle, which starts on
2026-09-07: base 2 w + strength_power 4 w → power_endurance from 2026-10-19),
so ``test_adhoc_builder_and_composer_pool_unchanged_vs_main`` turned red on
every run from 2026-10-19 on. These tests freeze the wall clock in that window
and fail without the fix.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from backend.api import deps
from backend.engine import adhoc_builder
from backend.tests import c272_golden_cases as golden
from backend.tests.test_c272_bw_ladders_catalog import FIXTURE


class _FrozenDate(date):
    frozen = date(2026, 10, 19)

    @classmethod
    def today(cls):  # type: ignore[override]
        return cls.frozen


@pytest.fixture
def clock_in_power_endurance(monkeypatch):
    monkeypatch.setattr(deps, "date", _FrozenDate)
    monkeypatch.setattr(adhoc_builder, "_date", _FrozenDate)
    yield


def test_phase_is_read_on_the_session_day(clock_in_power_endurance):
    state = golden.profiles()["advanced"]
    assert adhoc_builder._current_phase(state) == "power_endurance"  # wall clock
    assert adhoc_builder._current_phase(state, "2026-10-07") == "strength_power"
    assert adhoc_builder._current_phase(state, "2026-09-08") == "base"
    assert adhoc_builder._current_phase(state, "not-a-date") == "power_endurance"


def test_c272_other_engines_golden_holds_after_the_phase_boundary(clock_in_power_endurance):
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["other_engines"]
    now = golden.compute_other_engines()
    assert [k for k in expected if expected[k] != now[k]] == []
