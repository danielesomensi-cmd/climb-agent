"""A312 — a deload week really drops the set of the strength-lunch lifts.

Before A312 only the bodyweight ladder (core, ring push-up) lost a set in a
deload; goblet squat, RDL, bench, triceps and curl kept their full sets and
the "drop one set" lived in the notes alone. A catalog block now declares
``deload_sets`` in its ``prescription_overrides``; the resolver applies it when
the macrocycle phase of the session's date is ``deload``.

Pinned here:

1. in a deload week the declared lifts get ``deload_sets``, the catalog value
   moves to ``stored_sets`` and the row carries ``deload_sets_applied``;
2. outside a deload nothing changes, and the ``deload_sets`` key never
   reaches the output;
3. the ladder rows (core) keep the ladder's own deload dose — no second cut;
4. the phase is read on the session's date, not on today's.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from backend.engine.resolve_session import _apply_deload_sets
from backend.tests.test_c275_lunch_harder import EQUIPMENT_SETS, _by_block, _module, _resolve, _tested_state

DELOAD_SETS = {
    "legs_maintenance_lunch": {"squat_main": (4, 3), "hinge": (3, 2)},
    "upper_push_arms_lunch": {"chest_press": (4, 3), "triceps": (3, 2), "biceps": (3, 2)},
}


def _state_in(phase: str, date: str = "2026-10-14", equipment=None) -> dict:
    st = _tested_state(date) if equipment is None else _tested_state(date, equipment)
    st["macrocycle"] = {"start_date": "2026-10-12",
                        "phases": [{"phase_id": phase, "duration_weeks": 1},
                                   {"phase_id": "base", "duration_weeks": 4}]}
    return st


class TestCatalog:
    @pytest.mark.parametrize("sid", list(DELOAD_SETS))
    def test_lifts_declare_one_set_less(self, sid):
        for block_id, (sets, deload) in DELOAD_SETS[sid].items():
            ov = _module(sid, block_id)["selection"]["primary"]["prescription_overrides"]
            assert (ov["sets"], ov["deload_sets"]) == (sets, deload), block_id


class TestResolve:
    @pytest.mark.parametrize("sid", list(DELOAD_SETS))
    def test_deload_drops_the_set(self, sid):
        rows = _by_block(_resolve(sid, _state_in("deload"), "deload"))
        for block_id, (sets, deload) in DELOAD_SETS[sid].items():
            rx = rows[block_id]["prescription"]
            assert rx["sets"] == deload, block_id
            assert rx["stored_sets"] == sets
            assert rx["deload_sets_applied"] is True
            assert "deload_sets" not in rx

    @pytest.mark.parametrize("sid", list(DELOAD_SETS))
    def test_outside_deload_nothing_changes(self, sid):
        rows = _by_block(_resolve(sid, _state_in("strength_power"), "strength_power"))
        for block_id, (sets, _) in DELOAD_SETS[sid].items():
            rx = rows[block_id]["prescription"]
            assert rx["sets"] == sets, block_id
            assert not {"deload_sets", "stored_sets", "deload_sets_applied"} & set(rx)

    @pytest.mark.parametrize("sid", list(DELOAD_SETS))
    def test_ladder_core_is_not_cut_twice(self, sid):
        core_deload = _by_block(_resolve(sid, _state_in("deload"), "deload"))["core_rotation"]
        assert not {"deload_sets_applied", "stored_sets"} & set(core_deload["prescription"])

    def test_phase_is_read_on_the_session_date(self):
        st = _state_in("deload")  # deload 12-18/10, base after
        assert _apply_deload_sets({"sets": 4, "deload_sets": 3}, user_state=st,
                                  target_date="2026-10-14")["sets"] == 3
        assert _apply_deload_sets({"sets": 4, "deload_sets": 3}, user_state=st,
                                  target_date="2026-10-20")["sets"] == 4

    def test_without_state_or_date_only_the_key_is_dropped(self):
        assert _apply_deload_sets({"sets": 4, "deload_sets": 3}, user_state=None, target_date=None) == {"sets": 4}

    def test_input_is_not_mutated(self):
        rx = {"sets": 4, "deload_sets": 3}
        _apply_deload_sets(deepcopy(rx), user_state=_state_in("deload"), target_date="2026-10-14")
        _apply_deload_sets(rx, user_state=_state_in("deload"), target_date="2026-10-14")
        assert rx == {"sets": 4, "deload_sets": 3}

    def test_deterministic(self):
        a = _resolve("legs_maintenance_lunch", _state_in("deload"), "deload")
        b = _resolve("legs_maintenance_lunch", _state_in("deload"), "deload")
        assert a == b


class TestPushBlock:
    """A313: the push block declares ``deload_sets`` too. Without rings its
    substitute (dumbbell fly) loses the set; a row the ladder takes over keeps
    the ladder's own deload dose and never carries the A312 flags."""

    def test_catalog_declares_it(self):
        ov = _module("upper_push_arms_lunch", "push_bodyweight")["selection"]["primary"]["prescription_overrides"]
        assert (ov["sets"], ov["deload_sets"]) == (3, 2)

    @pytest.mark.parametrize("eq", ["c274_work", "dumbbell_cable"])
    def test_without_rings_the_substitute_loses_the_set(self, eq):
        st = _state_in("deload", equipment=EQUIPMENT_SETS[eq])
        push = _by_block(_resolve("upper_push_arms_lunch", st, "deload"))["push_bodyweight"]
        rx = push["prescription"]
        assert rx.get("source") != "bw_ladder", push["exercise_id"]
        assert (rx["sets"], rx["stored_sets"], rx["deload_sets_applied"]) == (2, 3, True)

    def test_without_rings_outside_deload_three_sets(self):
        st = _state_in("strength_power", equipment=EQUIPMENT_SETS["c274_work"])
        rx = _by_block(_resolve("upper_push_arms_lunch", st, "strength_power"))["push_bodyweight"]["prescription"]
        assert rx["sets"] == 3 and not {"deload_sets", "stored_sets", "deload_sets_applied"} & set(rx)

    def test_ladder_row_keeps_the_ladder_dose(self):
        from backend.engine import bw_progression

        st = _state_in("deload")
        bw_progression.set_level(st, "push_horizontal", 3, "2026-10-14", confirm=True)
        rx = _by_block(_resolve("upper_push_arms_lunch", st, "deload"))["push_bodyweight"]["prescription"]
        assert rx["source"] == "bw_ladder"
        assert not {"deload_sets", "stored_sets", "deload_sets_applied"} & set(rx)
