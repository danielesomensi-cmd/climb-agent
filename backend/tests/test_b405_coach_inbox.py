"""B405 — three engine items of the coach's bug inbox (2026-10-20 → 10-26).

1. Tags: a custom built on ``three_attempt_comp`` (or a 10 s max hang) came out
   ``{hard: False, finger: False}`` although ``is_finger_hard_session`` counts it
   as finger-hard — invisible to the 48 h finger gap. Seen in prod on 26/10
   («Bkl — try-hard MoonBoard»).
2. HIIT before a max: hours, not calendar days, and power endurance is not a
   max session (Panissa 2016: no strength decline reported past 1 h).
3. The PE anchor is covered by ``test_a292_pe_anchor``.
"""

from __future__ import annotations

from datetime import date

import pytest

from backend.engine import complementary_v1 as cv
from backend.engine.session_tags import derive_session_tags
from backend.engine.stimulus import (
    FINGER_FATIGUE_EXTRA_IDS,
    FINGER_HARD_LIBRARY_IDS,
    is_finger_hard_session,
    is_max_for_hiit,
)


# ── 1. tags ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("eid", FINGER_FATIGUE_EXTRA_IDS + FINGER_HARD_LIBRARY_IDS)
def test_finger_hard_ids_make_the_session_finger_and_hard(eid):
    tags, intensity = derive_session_tags([{"exercise_id": eid}])
    assert tags == {"hard": True, "finger": True}
    assert intensity in ("high", "max")  # hard ⇔ intensity in {high, max}


def test_try_hard_custom_of_26_10():
    """warm-up + three_attempt_comp: the stored tags now agree with athlete_context."""
    exercises = [{"exercise_id": "warmup_easy_boulders"}, {"exercise_id": "three_attempt_comp"}]
    tags, _ = derive_session_tags(exercises)
    assert tags == {"hard": True, "finger": True}
    session = {"session_id": "custom_cs_x", "tags": tags, "exercises": exercises}
    assert is_finger_hard_session(session)


def test_a_single_high_finger_drill_stays_not_hard():
    """Not every finger-loading drill: one high-intensity limit drill keeps the
    _HIGH_COUNT_FOR_HARD heuristic (finger yes, hard no)."""
    assert derive_session_tags([{"exercise_id": "vertical_small_feet_limit"}])[0] == {"hard": False, "finger": True}


# ── 2. HIIT before a max ─────────────────────────────────────────────────

def _t(day: int, slot: str) -> int:
    return day * 24 + cv.SLOT_HOUR[slot]


@pytest.mark.parametrize("hiit,event,close", [
    ((0, "lunch"), (0, "evening"), True),    # ~6 h
    ((0, "evening"), (1, "morning"), True),  # ~13 h
    ((0, "lunch"), (1, "morning"), True),    # ~19 h
    ((0, "evening"), (1, "evening"), False),  # 24 h
    ((0, "lunch"), (1, "evening"), False),   # ~30 h: the coach's 4x4 Wed lunch → Thu evening
    ((0, "lunch"), (0, "morning"), False),   # the max is already behind the HIIT
])
def test_hiit_window_in_hours(hiit, event, close):
    assert cv.hiit_too_close(_t(*hiit), _t(*event)) is close


def test_a_crag_day_counts_for_its_whole_day():
    crag = 1 * 24 + cv.OUTDOOR_START_HOUR
    assert cv.hiit_too_close(_t(1, "evening"), crag, outdoor=True)   # on the crag day
    assert cv.hiit_too_close(_t(0, "lunch"), crag, outdoor=True)     # ~19 h before
    assert not cv.hiit_too_close(_t(0, "morning"), crag, outdoor=True)  # 24 h before


def test_power_endurance_is_not_a_max_session_for_hiit():
    assert not is_max_for_hiit({"session_id": "power_endurance_gym"})
    for sid in ("limit_boulder_gym", "strength_long", "pulling_strength_gym", "route_projecting_gym"):
        assert is_max_for_hiit({"session_id": sid}), sid


def test_athlete_context_guard_follows_the_window():
    """The coach's week of 26/10: a lunch HIIT is free the day of a
    power-endurance evening and the day before an evening max; not the day of a max."""
    from backend.engine import athlete_context as ac
    from backend.tests.test_b372_outdoor_fatigue_alerts import EASY, HARD, LIMIT, MON, _d, _plan, _sess, _state_with

    state = _state_with(_plan({1: [_sess(HARD)], 2: [_sess(EASY)], 3: [_sess(LIMIT)]}))
    rows = {r["date"]: r for r in ac._guards(state, date.fromisoformat(MON), None, None)["days"]}
    assert rows[_d(1)]["hiit_ok"], rows[_d(1)]["hiit_reasons"]   # PE the same evening
    assert rows[_d(2)]["hiit_ok"], rows[_d(2)]["hiit_reasons"]   # limit ~30 h later
    assert not rows[_d(3)]["hiit_ok"]                             # limit ~6 h later
    assert rows[_d(3)]["hiit_codes"] == [{"code": "max_session_adjacent", "detail": f"{_d(3)} {LIMIT}"}]
