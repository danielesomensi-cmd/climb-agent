"""A288 (F0) — macro_position is the single pause-aware position helper.

Parity: ``deps.current_phase_and_week`` / ``deps._effective_anchor`` now
delegate to ``backend.engine.macro_position``; the result must be identical
to the pre-A288 implementation (kept verbatim below as the reference) on
every date, with and without an A223 pause.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime, timedelta

import pytest

from backend.api import deps
from backend.engine import macro_position as mp

PHASES = [
    {"phase_id": "base", "duration_weeks": 2},
    {"phase_id": "strength_power", "duration_weeks": 4},
    {"phase_id": "power_endurance", "duration_weeks": 3},
    {"phase_id": "performance", "duration_weeks": 3},
    {"phase_id": "deload", "duration_weeks": 1},
]
START = "2026-09-07"


def _mc(pause=None, phases=PHASES, start=START):
    mc = {"start_date": start, "phases": [dict(p) for p in phases]}
    if pause is not None:
        mc["pause"] = pause
    return mc


# --- pre-A288 reference, verbatim except that "today" is a parameter --------

def _ref_effective_anchor(macrocycle, today):
    mc_start = datetime.strptime(macrocycle["start_date"], "%Y-%m-%d").date()
    pause = macrocycle.get("pause") or {}
    offset_days = int(pause.get("offset_days") or 0)
    effective_start = mc_start + timedelta(days=offset_days)
    eff_today = today
    active_since = pause.get("active_since")
    if active_since:
        try:
            frozen = datetime.strptime(active_since, "%Y-%m-%d").date()
            eff_today = min(frozen, eff_today)
        except ValueError:
            pass
    return effective_start, eff_today


def _ref_current_phase_and_week(macrocycle, today):
    phases = macrocycle.get("phases") or []
    if not phases:
        return (0, 0)
    mc_start, today = _ref_effective_anchor(macrocycle, today)
    cumulative_week = 0
    for pi, phase in enumerate(phases):
        duration = phase.get("duration_weeks", 1)
        phase_start = mc_start + timedelta(weeks=cumulative_week)
        phase_end = phase_start + timedelta(weeks=duration)
        if today < phase_end:
            weeks_into = max(0, (today - phase_start).days // 7)
            return (pi, min(weeks_into, duration - 1))
        cumulative_week += duration
    last = phases[-1]
    return (len(phases) - 1, last.get("duration_weeks", 1) - 1)


PAUSES = {
    "no_pause": None,
    "empty_pause": {"active_since": None, "offset_days": 0, "log": []},
    "closed_offset_14": {"active_since": None, "offset_days": 14,
                         "log": [{"from": "2026-09-28", "to": "2026-10-12"}]},
    "active_pause": {"active_since": "2026-10-01", "offset_days": 0, "log": []},
    "active_plus_offset": {"active_since": "2026-11-02", "offset_days": 7,
                           "log": [{"from": "2026-09-21", "to": "2026-09-28"}]},
    "bad_active_since": {"active_since": "not-a-date", "offset_days": 0, "log": []},
}


@pytest.mark.parametrize("pause_key", sorted(PAUSES))
def test_parity_with_pre_a288_reference_on_every_day(pause_key):
    mc = _mc(PAUSES[pause_key])
    d0 = date(2026, 8, 1)
    for i in range(0, 200):
        d = d0 + timedelta(days=i)
        ref = _ref_current_phase_and_week(mc, d)
        assert mp.phase_and_week_on(mc, d) == ref, (pause_key, d)
        assert mp.phase_and_week_on(mc, d.isoformat()) == ref, (pause_key, d)
        assert deps.current_phase_and_week(mc, d) == ref, (pause_key, d)
        assert deps._effective_anchor(mc, d) == _ref_effective_anchor(mc, d)


@pytest.mark.parametrize("pause_key", sorted(PAUSES))
def test_deps_default_today_unchanged(pause_key):
    mc = _mc(PAUSES[pause_key])
    today = date.today()
    assert deps.current_phase_and_week(mc) == _ref_current_phase_and_week(mc, today)
    assert deps._effective_anchor(mc) == _ref_effective_anchor(mc, today)


def test_no_phases_returns_zero_zero_without_start_date():
    assert mp.phase_and_week_on({"phases": []}, date(2026, 1, 1)) == (0, 0)
    assert deps.current_phase_and_week({}, date(2026, 1, 1)) == (0, 0)


def test_active_pause_freezes_position():
    mc = _mc(PAUSES["active_pause"])
    frozen = mp.phase_and_week_on(mc, "2026-10-01")
    assert mp.phase_and_week_on(mc, "2026-11-30") == frozen


def test_position_on_daniele_like_calendar():
    pos = mp.position_on(_mc(), "2026-10-04")
    assert pos == {
        "phase_index": 1,
        "phase_id": "strength_power",
        "week_in_phase": 1,
        "phase_weeks": 4,
        "abs_week": 4,
        "total_weeks": 13,
        "phase_start": "2026-09-21",
        "phase_end": "2026-10-19",
        "is_last_week_of_phase": False,
        "next_phase_id": "power_endurance",
        "before_start": False,
        "after_end": False,
        "paused": False,
    }


def test_position_on_last_week_and_edges():
    mc = _mc()
    last_sp = mp.position_on(mc, "2026-10-12")
    assert last_sp["is_last_week_of_phase"] is True
    assert mp.position_on(mc, "2026-08-01")["before_start"] is True
    assert mp.position_on(mc, "2026-08-01")["phase_index"] == 0
    end = mp.position_on(mc, "2027-03-01")
    assert end["after_end"] is True and end["phase_id"] == "deload"
    assert end["next_phase_id"] is None


def test_position_on_honours_pause_offset():
    pos = mp.position_on(_mc(PAUSES["closed_offset_14"]), "2026-10-04")
    # 14 days of offset → two weeks earlier in the plan: base wk… → SP week 0
    assert (pos["phase_id"], pos["week_in_phase"]) == ("base", 1)
    assert pos["phase_start"] == "2026-09-21"
    assert mp.position_on(_mc(PAUSES["active_pause"]), "2026-10-04")["paused"] is True


def test_position_on_without_macrocycle():
    assert mp.position_on(None, "2026-10-04") is None
    assert mp.position_on({}, "2026-10-04") is None
    assert mp.position_on({"start_date": START, "phases": []}, "2026-10-04") is None


def test_module_is_pure():
    code = inspect.getsource(mp).replace(mp.__doc__, "")
    assert "date.today" not in code
    assert "backend.api" not in code
