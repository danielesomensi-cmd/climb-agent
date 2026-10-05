"""A302 — the ceiling follows what the athlete measures; custom rows follow the working load.

(1) The structural ceiling of the anchored four (3 s of reserve + phase cap on
hangs, Prilepin + (r+2)RM on pulls) is computed on max(official max, the max
implied by the latest clean measure). The official max never moves. A label
alone never lifts it; a measure counts 28 days, only against the current test,
only with every set done, no pain on the axis and no hard label.

(2) A non-anchored loaded row of a custom session (curl, RDL, wrist curl…)
carries the working load of its day, like a planned session; mode 'fixed'
keeps the user's kg.
"""

from __future__ import annotations

from copy import deepcopy

from backend.engine.anchored_load import (
    anchored_load,
    custom_working_load,
    hang_write_cap,
    measured_evidence,
    resolve_custom_exercises,
)
from backend.engine.progression_v1 import apply_feedback
from backend.tests.test_b364_official_max_vs_working_load import BW, _daniele, _entry, _log


def _hang(day, ext, *, margin=">5", label="easy", done=5, pain=None):
    item = {"exercise_id": "max_hang_7s", "completed": True, "used_external_load_kg": ext,
            "feedback_label": label, "prescribed_sets": 5, "completed_sets": done, "work_seconds": 7}
    if margin is not None:
        item["hang_margin"] = margin
    log = _log(day, [item])
    if pain is not None:
        log["pain"] = pain
    return log


def _al(state, day):
    return anchored_load(state, "max_hang_7s", date=day, intensity="hard")


def _two_clean_hangs():
    """Daniele's real week: 104.5 with >5 on 05/10, then 108.5 with >5 on 08/10."""
    st = apply_feedback(_hang("2026-10-05", 26.5), _daniele())
    return apply_feedback(_hang("2026-10-08", 30.5), st)


# --- (1) evidence ------------------------------------------------------------

def test_measured_evidence_formulas():
    assert measured_evidence({"hang_margin": ">5"}, "finger", 108.5, work_seconds=7) == {
        "total_kg": 116.6, "work_seconds": 7.0}
    # A timed hold is capped at +6 s; a failed hang implies nothing.
    assert measured_evidence({"hang_held_s": 20}, "finger", 100.0, work_seconds=7)["total_kg"] == 109.0
    assert measured_evidence({"hang_margin": "failed"}, "finger", 100.0, work_seconds=7) is None
    assert measured_evidence({}, "finger", 100.0, work_seconds=7) is None
    assert measured_evidence({"last_set_reps": 6}, "pulling", 108.0) == {"one_rm_kg": 131.4}


def test_evidence_below_the_official_max_changes_nothing():
    st = apply_feedback(_hang("2026-10-05", 26.5), _daniele())
    assert _entry(st, "max_hang_7s")["evidence"]["total_kg"] == 112.3  # < 116
    anch = _al(st, "2026-10-12")
    assert anch["cap"] == 110.0 and "evidence" not in anch
    assert anch["total"] == 108.5  # the label/margin step still moves the load


def test_evidence_above_the_official_max_lifts_the_ceiling():
    st = _two_clean_hangs()
    entry = _entry(st, "max_hang_7s")
    assert entry["evidence"] == {"total_kg": 116.6, "work_seconds": 7.0, "date": "2026-10-08",
                                 "official_date": "2026-09-24"}
    anch = _al(st, "2026-10-12")
    assert anch["cap"] > 110.0
    assert anch["evidence"] == {"total_at_duration": 116.6, "date": "2026-10-08"}
    # The official max is untouched.
    assert anch["official"]["total"] == 116.0
    assert st["tests"] == _daniele()["tests"]


def test_the_weekly_finger_rise_limit_still_binds():
    entry = _entry(_two_clean_hangs(), "max_hang_7s")
    # 108.5 + 4 asked; ≤ 104.5 (anchor 05/10) + 5 % of 116 → 110.0.
    assert entry["next_total_load_kg"] == 110.0


def test_a_label_alone_never_lifts_the_ceiling():
    st = apply_feedback(_hang("2026-10-05", 26.5, margin=None, label="very_easy"), _daniele())
    st = apply_feedback(_hang("2026-10-08", 30.5, margin=None, label="very_easy"), st)
    st = apply_feedback(_hang("2026-10-15", 32.0, margin=None, label="very_easy"), st)
    assert "evidence" not in _entry(st, "max_hang_7s")
    anch = _al(st, "2026-10-18")
    assert anch["cap"] == 110.0 and anch["clamped"] == "cap"
    assert "hang margin" in anch["ceiling_note"]


def test_dirty_measures_are_not_evidence():
    base = apply_feedback(_hang("2026-10-05", 26.5), _daniele())
    for log in (
        _hang("2026-10-08", 30.5, done=4),                      # a set missing
        _hang("2026-10-08", 30.5, label="hard"),                # contradicting label
        _hang("2026-10-08", 30.5, margin="failed"),             # failed
        _hang("2026-10-08", 30.5, pain={"score": 2, "site": "fingers"}),
    ):
        entry = _entry(apply_feedback(log, deepcopy(base)), "max_hang_7s")
        # The previous clean evidence (05/10, 112.3) is kept, never replaced.
        assert entry["evidence"]["date"] == "2026-10-05", log


def test_evidence_expires_after_28_days_and_with_a_new_test():
    st = _two_clean_hangs()
    assert "evidence" in _al(st, "2026-11-05")      # 28 days
    assert "evidence" not in _al(st, "2026-11-06")  # 29 days
    retested = deepcopy(st)
    retested["tests"]["max_strength"].append(
        {"test_id": "max_hang_7s_total_load", "date": "2026-10-10", "total_load_kg": 117.0, "bodyweight_kg": 78.0})
    retested["baselines"]["hangboard"][0].update({"max_total_load_kg": 117.0, "updated_at": "2026-10-10"})
    assert "evidence" not in (_al(retested, "2026-10-12") or {})


def test_feedback_is_idempotent():
    st = _two_clean_hangs()
    again = apply_feedback(_hang("2026-10-08", 30.5), deepcopy(st))
    assert _entry(again, "max_hang_7s") == _entry(st, "max_hang_7s")


def test_hang_write_cap_outside_the_anchored_four_follows_the_7s_evidence():
    st = _two_clean_hangs()
    assert hang_write_cap(_daniele(), 7, "2026-10-12") == 110.0
    assert hang_write_cap(st, 7, "2026-10-12") > 110.0


def test_untested_athlete_unchanged():
    st = _daniele()
    st["tests"] = {}
    st["baselines"] = {}
    assert anchored_load(st, "max_hang_7s", date="2026-10-12") is None


# --- (2) custom rows follow the working load ----------------------------------

def _with_entry(ex_id, next_ext, updated="2026-10-05"):
    st = _daniele()
    st["working_loads"]["entries"].append({
        "exercise_id": ex_id, "key": ex_id, "setup": {}, "last_external_load_kg": next_ext,
        "next_external_load_kg": next_ext, "updated_at": updated})
    return st


def test_custom_loaded_row_carries_the_working_load():
    st = _with_entry("reverse_wrist_curl", 6.0)
    row = {"exercise_id": "reverse_wrist_curl", "sets": 2, "reps": 15, "load_kg": 5.0}
    out = resolve_custom_exercises(st, [row], "2026-10-09")[0]
    assert (out["load_kg"], out["stored_load_kg"], out["load_source"]) == (6.0, 5.0, "working_load")
    assert out["working_load_from"] == "2026-10-05"
    assert row["load_kg"] == 5.0  # input never mutated


def test_custom_fixed_row_keeps_the_users_kg():
    st = _with_entry("reverse_wrist_curl", 6.0)
    row = {"exercise_id": "reverse_wrist_curl", "sets": 2, "reps": 15, "load_kg": 5.0, "load_mode": "fixed"}
    out = resolve_custom_exercises(st, [row], "2026-10-09")[0]
    assert (out["load_kg"], out["load_source"]) == (5.0, "user_fixed")


def test_custom_row_without_entry_or_without_load_is_untouched():
    st = _daniele()
    row = {"exercise_id": "reverse_wrist_curl", "sets": 2, "reps": 15, "load_kg": 5.0}
    assert resolve_custom_exercises(st, [row], "2026-10-09")[0] == row
    bw_row = {"exercise_id": "hollow_body_hold", "sets": 3, "work_seconds": 30, "load_kg": 0}
    assert resolve_custom_exercises(_with_entry("hollow_body_hold", 5.0), [bw_row], "2026-10-09")[0] == bw_row


def test_custom_ladder_row_and_future_entry_are_untouched():
    st = _with_entry("reverse_wrist_curl", 6.0, updated="2026-10-20")
    row = {"exercise_id": "reverse_wrist_curl", "sets": 2, "reps": 15, "load_kg": 5.0}
    assert custom_working_load(st, row, "2026-10-09") is None  # entry newer than the day
    ladder = {"exercise_id": "pallof_press", "sets": 3, "reps": 8, "load_kg": 0, "progress_mode": "ladder"}
    assert custom_working_load(_with_entry("pallof_press", 4.0), ladder, "2026-10-09") is None


def test_custom_feedback_round_trip_moves_the_next_read():
    """Feedback 'easy' on the custom row → the next read of the same custom is heavier."""
    st = _with_entry("reverse_wrist_curl", 5.0, updated="2026-09-23")
    log = _log("2026-10-05", [{"exercise_id": "reverse_wrist_curl", "completed": True,
                               "used_external_load_kg": 5.0, "feedback_label": "easy",
                               "prescribed_sets": 2, "completed_sets": 2}])
    st = apply_feedback(log, st)
    row = {"exercise_id": "reverse_wrist_curl", "sets": 2, "reps": 15, "load_kg": 5.0}
    assert resolve_custom_exercises(st, [row], "2026-10-09")[0]["load_kg"] > 5.0
