"""B409 — "easy" raises the load, and dumbbells move on a 2 kg grid.

Daniele (2026-10-30): dumbbell bench press 26/10 and overhead press 30/10,
3×8 rated easy with the last set at or above the target. The double
progression (A295) answered +1 rep a session up to the top of the range
(8 → 10) and only then +2.5 % — about three sessions before the first kilo,
and +2.5 % of 34 kg is a 35.5 kg dumbbell that does not exist.
«Preferisco aumentare anche il peso», «manubri va bene passo 2»,
«ok prehab rimane».

What is pinned here:

1. a measured success rated easy / very_easy raises the load by the label step
   (+5 % / +10 %) and sends the target back to the bottom of the range;
2. "ok", a miss, missing sets, pain: unchanged (A295);
3. prehab work keeps the slow path (reps first);
4. dumbbell exercises land on the 2 kg grid, always on a different dumbbell
   in the direction of the change; barbells, cables and plates keep 0.5 kg.
"""

from __future__ import annotations

import pytest

from backend.engine import measured_feedback as mf
from backend.engine.progression_v1 import _dp_step_load, apply_feedback
from backend.tests.test_a295_measured_feedback import _entry, _log, _plain_state


def _feedback(eid, *, used, reps=8, last=8, target=None, label=None, done=3, sets=3, day="2026-10-30",
              sid="custom_cs_x", state=None):
    item = {"exercise_id": eid, "completed": True, "used_external_load_kg": used,
            "prescribed_reps": reps, "prescribed_sets": sets, "completed_sets": done,
            "last_set_reps": last, "target_reps": target if target is not None else reps}
    if label:
        item["feedback_label"] = label
    st = state if state is not None else _plain_state()
    return _entry(apply_feedback(_log(day, [item], session_id=sid), st), eid)


# --- (1) easy measured → load now ------------------------------------------------

def test_daniele_dumbbell_bench_easy_goes_to_the_next_dumbbell():
    e = _feedback("dumbbell_bench_press", used=34.0, label="easy")
    assert e["next_external_load_kg"] == 36.0
    assert e["dp_target_reps"] == 8 and e["dp_last_outcome"] == "label_load_up"


def test_daniele_overhead_press_easy_with_a_rep_over_the_target():
    e = _feedback("overhead_press", used=16.0, last=9, label="easy")
    assert e["next_external_load_kg"] == 18.0 and e["dp_target_reps"] == 8


def test_very_easy_is_the_bigger_step():
    assert _feedback("dumbbell_bench_press", used=34.0, label="very_easy")["next_external_load_kg"] == 38.0


def test_barbell_keeps_half_kilo_rounding():
    e = _feedback("bench_press", used=70.0, reps=4, last=4, label="easy")
    assert e["next_external_load_kg"] == 73.5 and e["dp_target_reps"] == 4


def test_easy_from_the_middle_of_the_range_goes_back_to_the_bottom():
    st = _plain_state()
    st["working_loads"]["entries"].append({"key": "dumbbell_bench_press", "exercise_id": "dumbbell_bench_press",
                                           "setup": {}, "dp_range": [8, 10], "dp_target_reps": 9,
                                           "next_external_load_kg": 34.0, "last_external_load_kg": 34.0})
    e = _feedback("dumbbell_bench_press", used=34.0, last=9, target=9, label="easy", state=st)
    assert (e["next_external_load_kg"], e["dp_target_reps"]) == (36.0, 8)


# --- (2) what does not change ---------------------------------------------------

def test_ok_still_climbs_one_rep():
    e = _feedback("dumbbell_bench_press", used=34.0, label="ok")
    assert (e["next_external_load_kg"], e["dp_target_reps"], e["dp_last_outcome"]) == (34.0, 9, "reps_up")


def test_unrated_still_climbs_one_rep():
    e = _feedback("dumbbell_bench_press", used=34.0)
    assert (e["next_external_load_kg"], e["dp_target_reps"]) == (34.0, 9)


def test_easy_with_a_missed_target_holds():
    e = _feedback("dumbbell_bench_press", used=34.0, last=7, label="easy")
    assert (e["next_external_load_kg"], e["dp_last_outcome"]) == (34.0, "hold")


def test_easy_with_a_missing_set_holds():
    e = _feedback("dumbbell_bench_press", used=34.0, done=2, label="easy")
    assert (e["next_external_load_kg"], e["dp_last_outcome"]) == (34.0, "hold")


def test_easy_with_pain_does_not_jump():
    st = _plain_state()
    item = {"exercise_id": "dumbbell_bench_press", "completed": True, "used_external_load_kg": 34.0,
            "prescribed_reps": 8, "prescribed_sets": 3, "completed_sets": 3, "last_set_reps": 8,
            "target_reps": 8, "feedback_label": "easy"}
    out = apply_feedback(_log("2026-10-30", [item], pain={"score": 2, "site": "shoulder"}), st)
    assert _entry(out, "dumbbell_bench_press")["dp_last_outcome"] != "label_load_up"


def test_replay_of_the_same_session_is_idempotent():
    st = _plain_state()
    item = {"exercise_id": "dumbbell_bench_press", "completed": True, "used_external_load_kg": 34.0,
            "prescribed_reps": 8, "prescribed_sets": 3, "completed_sets": 3, "last_set_reps": 8,
            "target_reps": 8, "feedback_label": "easy"}
    once = apply_feedback(_log("2026-10-30", [item], session_id="s1"), st)
    twice = apply_feedback(_log("2026-10-30", [item], session_id="s1"), once)
    assert _entry(twice, "dumbbell_bench_press")["next_external_load_kg"] == 36.0
    assert _entry(twice, "dumbbell_bench_press")["dp_target_reps"] == 8


# --- (3) prehab keeps the slow path ---------------------------------------------

def test_prehab_easy_measured_climbs_reps_not_load():
    e = _feedback("wrist_curl", used=3.0, reps=15, last=15, label="easy")
    assert (e["next_external_load_kg"], e["dp_target_reps"], e["dp_last_outcome"]) == (3.0, 16, "reps_up")


def test_prehab_classification():
    assert mf.is_prehab("wrist_curl") and mf.is_prehab("elbow_eccentric_curl") and mf.is_prehab("face_pull")
    assert not mf.is_prehab("dumbbell_bench_press") and not mf.is_prehab("goblet_squat")


# --- (4) the dumbbell grid ------------------------------------------------------

def test_dumbbell_classification():
    for eid in ("dumbbell_bench_press", "overhead_press", "lateral_raise", "hammer_curl", "bicep_curl",
                "dumbbell_fly", "bulgarian_split_squat", "overhead_tricep_extension"):
        assert mf.dumbbell_step_kg(eid) == 2.0, eid
    for eid in ("bench_press", "romanian_deadlift", "triceps_cable_pushdown", "goblet_squat", "wrist_curl",
                "weighted_dip", "nonexistent"):
        assert mf.dumbbell_step_kg(eid) is None, eid


@pytest.mark.parametrize("base,pct,expected", [
    (34.0, 0.05, 36.0),    # 35.7 → nearest dumbbell 36
    (34.0, 0.10, 38.0),    # 37.4 → 38
    (34.0, 0.025, 36.0),   # 34.85 rounds back to 34: never a non-change
    (16.0, 0.05, 18.0),    # 16.8 → 16: the next dumbbell up
    (6.0, 0.05, 8.0),      # the only step there is
    (16.5, 0.05, 18.0),    # a logged load off the grid moves onto it
    (17.0, 0.05, 18.0),
    (34.0, -0.025, 32.0),  # hard: the next dumbbell down
    (34.0, -0.10, 30.0),   # 30.6 → 30
    (2.0, -0.10, 2.0),     # 1.8 rounds back to 2.0: B344, a decrease is never forced
])
def test_dumbbell_grid(base, pct, expected):
    assert _dp_step_load(base, pct, 2.0) == expected


def test_no_grid_is_the_old_half_kilo_rule():
    assert _dp_step_load(34.0, 0.05, None) == 35.5
    assert _dp_step_load(70.0, 0.05, None) == 73.5


def test_top_of_range_ok_on_a_dumbbell_moves_a_whole_dumbbell():
    st = _plain_state()
    st["working_loads"]["entries"].append({"key": "dumbbell_bench_press", "exercise_id": "dumbbell_bench_press",
                                           "setup": {}, "dp_range": [8, 10], "dp_target_reps": 10,
                                           "next_external_load_kg": 34.0, "last_external_load_kg": 34.0})
    e = _feedback("dumbbell_bench_press", used=34.0, last=10, target=10, label="ok", state=st)
    assert (e["next_external_load_kg"], e["dp_target_reps"], e["dp_last_outcome"]) == (36.0, 8, "load_up")


def test_label_without_a_measure_also_lands_on_the_grid():
    st = _plain_state()
    item = {"exercise_id": "lateral_raise", "completed": True, "used_external_load_kg": 6.0,
            "prescribed_reps": 12, "prescribed_sets": 4, "completed_sets": 4, "feedback_label": "easy"}
    out = apply_feedback(_log("2026-10-30", [item]), st)
    assert _entry(out, "lateral_raise")["next_external_load_kg"] == 8.0
