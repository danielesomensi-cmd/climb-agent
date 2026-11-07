"""B413 (D3 on loads and grades, Daniele's A1 and A4).

- A1: a DONE exercise with no label and no measure counts as an ``ok``. On a
  load or grade memory it also never rewrites the memory LOWER than what that
  memory proposed for the session without the temporary cuts (guards, fatigue
  floor): the entry stays as it was (escalation anchor included) and only its
  date is refreshed. A rated ``ok`` keeps following the load used; a measure
  without a label is data and can lower; not done / skipped keep their own
  behaviour; the pain block keeps its own hold.
- A4 (Daniele, 2026-11-02 and 2026-11-04, «togli anche le due regole»): no
  re-entry factor on the anchored cap (×0.90 / ×0.95 after a ≥14-day gap) and
  no −½ grade on the limit target after a gap, for everyone.

Numbers are Daniele's (B364 fixture): BW 78, max hang 7 s 116 kg and pull-up
2RM 123 (1RM 128.9), both tested 2026-09-24; macrocycle from 2026-09-07
(power_endurance 19/10-08/11, performance from 09/11).
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from backend.engine.anchored_load import anchored_load
from backend.engine.progression_v1 import apply_feedback, inject_targets

BW = 78.0


def _daniele(*, entries=None, registry=None, hard_labels=None) -> dict:
    return {
        "bodyweight_kg": BW,
        "assessment": {"grades": {"boulder_max_rp": "7C", "boulder_max_os": "7A",
                                   "lead_max_rp": "8a+", "lead_max_os": "7a+"}},
        "equipment": {"gyms": [{"gym_id": "kilter", "equipment": ["board_kilter", "hangboard"]}]},
        "macrocycle": {
            "start_date": "2026-09-07",
            "phases": [
                {"phase_id": "base", "duration_weeks": 2},
                {"phase_id": "strength_power", "duration_weeks": 4},
                {"phase_id": "power_endurance", "duration_weeks": 3},
                {"phase_id": "performance", "duration_weeks": 3},
                {"phase_id": "deload", "duration_weeks": 1},
            ],
        },
        "tests": {
            "max_strength": [
                {"test_id": "max_hang_7s_total_load", "date": "2026-09-24", "total_load_kg": 116.0, "bodyweight_kg": 76.0},
            ],
            "pulling_strength": [
                {"test_id": "weighted_pullup_2rm", "date": "2026-09-24", "total_load_2rm_kg": 123.0,
                 "estimated_1rm_kg": 128.9, "bodyweight_kg": 78.0},
            ],
        },
        "baselines": {
            "pulling": {"weighted_pullup_2rm_total_kg": 123.0, "weighted_pullup_1rm_estimated_kg": 128.9,
                        "weighted_pullup_1rm_total_kg": 128.9, "source": "test_session", "updated_at": "2026-09-24",
                        "bodyweight_kg": 78.0, "max_external_load_kg": 51.0},
            "hangboard": [{"max_total_load_kg": 116.0, "source": "test", "updated_at": "2026-09-24",
                           "hang_seconds": 7, "edge_mm": 20, "grip": "half_crimp"}],
        },
        "working_loads": {"entries": deepcopy(entries or []), "rules": {}},
        "progression_counters": {
            "stimulus_exposures": deepcopy(registry if registry is not None else {}),
            "hard_labels": deepcopy(hard_labels or {}),
        },
    }


def _hang_memory(**over) -> dict:
    """The 02/11 memory: 3/3 at +25 (103) with > 5 s left → next 107."""
    e = {"exercise_id": "max_hang_7s", "key": "max_hang_7s", "setup": {}, "anchored": True,
         "last_total_load_kg": 103.0, "last_external_load_kg": 25.0, "last_work_seconds": 7.0,
         "next_total_load_kg": 107.0, "next_external_load_kg": 29.0, "last_feedback_label": None,
         "last_rated": True, "last_completed": True, "phase_id_at_log": "power_endurance",
         "intensity_at_log": "hard", "escalation_anchor": {"date": "2026-11-02", "total_kg": 103.0},
         "updated_at": "2026-11-02"}
    e.update(over)
    return e


def _log(day, items, session_id="custom_cs_x", contract=2, planned=None) -> dict:
    out = {"date": day, "session_id": session_id, "actual": {"exercise_feedback_v1": items}}
    if contract is not None:
        out["feedback_contract"] = contract
    if planned is not None:
        out["planned"] = planned
    return out


def _entry(state, key):
    return next(e for e in state["working_loads"]["entries"] if e.get("key") == key)


def _hang_item(total, **over) -> dict:
    item = {"exercise_id": "max_hang_7s", "completed": True, "completed_sets": 5, "prescribed_sets": 5,
            "used_total_load_kg": total, "work_seconds": 7}
    item.update(over)
    return item


# Three hard finger days in the 14 before 03/11 → fatigue floor on 03/11.
_FATIGUE = {"finger": ["2026-10-25", "2026-10-28", "2026-10-31"]}


# ---------------------------------------------------------------------------
# A4 — no re-entry ramp, no −½ grade
# ---------------------------------------------------------------------------

def test_no_reentry_ramp_after_gap():
    """02/11: first finger exposure after 18 days (last 15/10). B413: the full
    power_endurance cap (0.90 × 116 = 104.4 → 104.0), not × 0.90 (93.5, +15.5:
    what the app prescribed that day)."""
    st = _daniele(registry={"finger_max": [{"date": "2026-10-15", "exercise_id": "max_hang_7s"}]})
    anch = anchored_load(st, "max_hang_7s", date="2026-11-02", intensity="hard", sets=6)
    assert anch["phase_id"] == "power_endurance"
    assert "ramp" not in anch  # B414: no re-entry reading at all
    assert (anch["total"], anch["cap"], anch["clamped"], anch["external"]) == (104.0, 104.0, "cap", 26.0)
    # B414 (Daniele, 2026-11-07 «togli il tetto»): no 5-set cap after a gap.
    assert (anch["sets"], anch["rep_scheme"], anch["guards"]) == (6, "6x7s", [])
    # The same day with a trained run prescribes the same load and sets.
    run = _daniele(registry={"finger_max": [{"date": d, "exercise_id": "max_hang_7s"}
                                            for d in ("2026-10-27", "2026-10-29", "2026-10-31")]})
    full = anchored_load(run, "max_hang_7s", date="2026-11-02", intensity="hard", sets=6)
    assert {k: full[k] for k in ("total", "cap", "sets", "rep_scheme", "guards")} == \
        {k: anch[k] for k in ("total", "cap", "sets", "rep_scheme", "guards")}


def test_no_reentry_ramp_on_the_memory_after_the_02_11_session():
    """03/11: athlete_context still said cap 99 (n=2 × 0.95) under a 107 memory.
    B413: the second exposure reads the full cap, 104.0."""
    st = _daniele(entries=[_hang_memory()],
                  registry={"finger_max": [{"date": "2026-11-02", "exercise_id": "max_hang_7s"}]})
    anch = anchored_load(st, "max_hang_7s", date="2026-11-04", intensity="hard")
    assert "ramp" not in anch
    assert (anch["source"], anch["total"], anch["cap"]) == ("working_load", 104.0, 104.0)


def _limit_state(updated_at="2026-10-15", grade="7B"):
    st = _daniele()
    st["working_loads"]["entries"] = [{
        "key": "board_limit_boulders|surface=board_kilter", "setup": {"surface": "board_kilter"},
        "exercise_id": "board_limit_boulders", "surface_selected": "board_kilter",
        "last_used_grade": grade, "next_target_grade": grade, "last_feedback_label": "ok",
        "updated_at": updated_at,
    }]
    return st


def _limit_day(day):
    return {"date": day, "sessions": [{
        "session_id": "limit_boulder_gym", "intent": "power", "gym_id": "kilter", "tags": {"hard": True},
        "exercise_instances": [{"exercise_id": "board_limit_boulders",
                                "prescription": {"grade_ref": "boulder_max_rp", "grade_offset": 0}}],
    }]}


def _limit_target(st, day):
    out = inject_targets(_limit_day(day), deepcopy(st))
    return out["sessions"][0]["exercise_instances"][0]["suggested"]["suggested_boulder_target"]


def test_limit_after_gap_is_base_grade():
    """05/11: Kilter 7B, last limit 21 days earlier. B365 resolved 7A+
    (target_source 'reentry', base 7B, 0/2 exposures); Daniele wants the base."""
    bt = _limit_target(_limit_state(), "2026-11-05")
    assert (bt["target_grade"], bt["target_grade_low"], bt["target_source"]) == ("7B", "7A", "memory")
    assert "reentry" not in bt
    # Any gap length inside the 180-day trust reads the same grade.
    for gap_start in ("2026-11-03", "2026-10-22", "2026-09-01", "2026-05-20"):
        assert _limit_target(_limit_state(gap_start), "2026-11-05")["target_grade"] == "7B", gap_start


# ---------------------------------------------------------------------------
# Anchored loads (hang, pull)
# ---------------------------------------------------------------------------

def test_anchored_hang_ramp_capped_unrated_keeps_memory():
    """The D3 case (it was the ramp: memory 107 → 99, read of 10/11 = 105). With
    the ramp gone the remaining temporary cut is the fatigue floor: on 03/11
    three hard finger days put the hang at the power_endurance floor (87). Done
    at 87 with no label → the memory stays 107 (it would have become 87), only
    its date moves, and the 10/11 performance read is 110."""
    st = _daniele(entries=[_hang_memory()], hard_labels=_FATIGUE)
    shown = anchored_load(st, "max_hang_7s", date="2026-11-03", intensity="hard")
    assert (shown["total"], shown["clamped"]) == (87.0, "fatigue_floor")
    out = apply_feedback(_log("2026-11-03", [_hang_item(87.0)]), st)
    e = _entry(out, "max_hang_7s")
    assert e == {**_hang_memory(), "updated_at": "2026-11-03"}
    nxt = anchored_load(out, "max_hang_7s", date="2026-11-10", intensity="hard")
    assert (nxt["phase_id"], nxt["total"]) == ("performance", 110.0)
    # The same session RATED ok follows the load used (unchanged rule).
    rated = apply_feedback(_log("2026-11-03", [_hang_item(87.0, feedback_label="ok")]), st)
    assert _entry(rated, "max_hang_7s")["next_total_load_kg"] == 87.0


def test_anchored_pull_guard_capped_unrated_keeps_memory():
    """Heavy-pull week guard (2 sessions ≥ 85 % of 1RM in 7 days → cap 0.80 ×
    1RM = 103.0): done at the cut 103 with no label, the 108 memory stays."""
    mem = {"exercise_id": "weighted_pullup", "key": "weighted_pullup", "setup": {}, "anchored": True,
           "last_reps": 3, "last_total_load_kg": 108.0, "next_total_load_kg": 108.0,
           "next_external_load_kg": 30.0, "phase_id_at_log": "strength_power", "intensity_at_log": "hard",
           "updated_at": "2026-10-04"}
    heavy = {"pulling_max": [{"date": d, "exercise_id": "weighted_pullup", "total_kg": 110.0}
                             for d in ("2026-10-05", "2026-10-07")]}
    st = _daniele(entries=[mem], registry=heavy)
    shown = anchored_load(st, "weighted_pullup", date="2026-10-09", intensity="hard", sets=4, reps=3)
    assert shown["total"] == 103.0 and [g["guard"] for g in shown["guards"]] == ["heavy_pull_week"]
    item = {"exercise_id": "weighted_pullup", "completed": True, "completed_sets": 4, "prescribed_sets": 4,
            "used_total_load_kg": 103.0, "reps": 3}
    out = apply_feedback(_log("2026-10-09", [item]), st)
    assert _entry(out, "weighted_pullup") == {**mem, "updated_at": "2026-10-09"}
    # Above the uncut proposal (108) an unrated session writes as an ok.
    up = apply_feedback(_log("2026-10-09", [dict(item, used_total_load_kg=109.0)]), _daniele(entries=[mem]))
    assert _entry(up, "weighted_pullup")["next_total_load_kg"] == 109.0


def test_kept_entry_keeps_escalation_anchor_then_rated_ok_never_drops():
    st = _daniele(entries=[_hang_memory()], hard_labels=_FATIGUE)
    kept = apply_feedback(_log("2026-11-03", [_hang_item(87.0)]), st)
    assert _entry(kept, "max_hang_7s")["escalation_anchor"] == {"date": "2026-11-02", "total_kg": 103.0}
    # Replay of the same log (mark done, then feedback): same result.
    assert apply_feedback(_log("2026-11-03", [_hang_item(87.0)]), kept)["working_loads"] == kept["working_loads"]
    # 10/11, performance, the prescription is 110: a rated ok there stores 110.
    out = apply_feedback(_log("2026-11-10", [_hang_item(110.0, feedback_label="ok")]), kept)
    e = _entry(out, "max_hang_7s")
    assert e["next_total_load_kg"] == 110.0 >= 107.0
    assert e["escalation_anchor"] == {"date": "2026-11-10", "total_kg": 110.0}


def test_pain_block_unchanged():
    """Under a pain block the A295 hold decides, not the B413 keep."""
    st = _daniele(entries=[_hang_memory()])
    st["progression_counters"]["pain_blocks"] = {"fingers": {"score": 2, "from": "2026-11-03", "until": "2026-11-17"}}
    out = apply_feedback(_log("2026-11-04", [_hang_item(94.0)]), st)
    e = _entry(out, "max_hang_7s")
    assert e["updated_at"] == "2026-11-04" and "pain_hold" in e
    assert e["last_total_load_kg"] == 94.0  # the entry is rewritten (pain path), not kept


def test_unrated_not_done_or_skipped_keeps_its_own_behaviour():
    st = _daniele(entries=[_hang_memory()], hard_labels=_FATIGUE)
    for item in (_hang_item(87.0, completed=False, completed_sets=2),
                 _hang_item(87.0, feedback_label="skipped")):
        e = _entry(apply_feedback(_log("2026-11-03", [item]), st), "max_hang_7s")
        assert e["next_total_load_kg"] == 87.0, item  # follows the load used, as before B413
    # completed:false with every set logged is done (bug-inbox 04/11): kept.
    done = _hang_item(87.0, completed=False, completed_sets=5)
    assert _entry(apply_feedback(_log("2026-11-03", [done]), st), "max_hang_7s")["next_total_load_kg"] == 107.0
    # A player row with no counted set is not done.
    player = {k: v for k, v in _hang_item(87.0).items() if k != "completed_sets"}
    assert _entry(apply_feedback(_log("2026-11-03", [player]), st), "max_hang_7s")["next_total_load_kg"] == 87.0


# ---------------------------------------------------------------------------
# Generic loads (total, external, loading pin, double progression)
# ---------------------------------------------------------------------------

_GENERIC = [
    # (exercise, entry key, memory field, memory, used field, lower used)
    ("suitcase_carry", "suitcase_carry", "next_total_load_kg", 110.0, "used_total_load_kg", 100.0),
    ("farmers_carry", "farmers_carry", "next_external_load_kg", 32.0, "used_external_load_kg", 28.0),
    ("lp_max_lift_5s", "lp_max_lift_5s:right", "next_external_load_kg", 30.0, "used_external_load_kg", 26.0),
    ("wrist_curl", "wrist_curl", "next_external_load_kg", 12.0, "used_external_load_kg", 10.0),
    ("weighted_dip", "weighted_dip", "next_total_load_kg", 98.0, "used_total_load_kg", 93.0),
]


def _generic_state(ex, key, field, memory):
    entry = {"exercise_id": ex, "key": key, "setup": {}, field: memory, "last_feedback_label": "easy",
             "updated_at": "2026-10-20"}
    if field == "next_total_load_kg":
        entry["next_external_load_kg"] = memory - BW
    if key.endswith(":right"):
        entry["hand"] = "right"
    return _daniele(entries=[entry])


def _generic_item(ex, used_field, used, **over):
    item = {"exercise_id": ex, "completed": True, "completed_sets": 3, "prescribed_sets": 3, used_field: used}
    if ex == "lp_max_lift_5s":
        item["hand"] = "right"
    item.update(over)
    return item


@pytest.mark.parametrize("ex,key,field,memory,used_field,lower", _GENERIC)
def test_generic_loads_unrated_never_lower(ex, key, field, memory, used_field, lower):
    st = _generic_state(ex, key, field, memory)
    before = deepcopy(_entry(st, key))
    out = apply_feedback(_log("2026-10-27", [_generic_item(ex, used_field, lower)]), st)
    assert _entry(out, key) == {**before, "updated_at": "2026-10-27"}, ex
    # The same item from the dialog (no counted sets, completed: true) is done too.
    dialog = {k: v for k, v in _generic_item(ex, used_field, lower).items() if k not in ("completed_sets", "prescribed_sets")}
    out2 = apply_feedback(_log("2026-10-27", [dialog], session_id="pulling_strength_home"), st)
    assert _entry(out2, key)[field] == memory, ex
    # Done at or above the memory: written like an ok (next = used).
    up = apply_feedback(_log("2026-10-27", [_generic_item(ex, used_field, memory + 2.0)]), st)
    assert (_entry(up, key)[field], _entry(up, key)["updated_at"]) == (memory + 2.0, "2026-10-27"), ex


@pytest.mark.parametrize("ex,key,field,memory,used_field,lower", _GENERIC)
def test_rated_ok_with_lower_used_still_follows_used(ex, key, field, memory, used_field, lower):
    st = _generic_state(ex, key, field, memory)
    out = apply_feedback(_log("2026-10-27", [_generic_item(ex, used_field, lower, feedback_label="ok")]), st)
    assert _entry(out, key)[field] == lower, ex
    # A legacy 'ok' (no contract) is not rated: it keeps the memory.
    legacy = apply_feedback(_log("2026-10-27", [_generic_item(ex, used_field, lower, feedback_label="ok")],
                                 contract=None), st)
    assert _entry(legacy, key)[field] == memory, ex


def test_stale_memory_is_not_kept():
    """A memory the read would not use (older than its freshness window) is
    not protected: the unrated session writes as an ok."""
    st = _generic_state("suitcase_carry", "suitcase_carry", "next_total_load_kg", 110.0)
    _entry(st, "suitcase_carry")["updated_at"] = "2026-07-01"  # > 60 days before 27/10
    out = apply_feedback(_log("2026-10-27", [_generic_item("suitcase_carry", "used_total_load_kg", 100.0)]), st)
    assert _entry(out, "suitcase_carry")["next_total_load_kg"] == 100.0


# ---------------------------------------------------------------------------
# Grades (limit, endurance)
# ---------------------------------------------------------------------------

def _endurance_state(grade="6C", updated_at="2026-10-20"):
    st = _daniele()
    st["working_loads"]["entries"] = [{
        "exercise_id": "four_by_four_bouldering", "key": "four_by_four_bouldering", "setup": {},
        "last_used_grade": grade, "next_target_grade": grade, "grade_streak_direction": 1,
        "grade_streak_count": 1, "last_feedback_label": "easy", "last_rated": True, "updated_at": updated_at,
    }]
    return st


def _endurance_item(grade, **over):
    item = {"exercise_id": "four_by_four_bouldering", "completed": True, "used_grade": grade}
    item.update(over)
    return item


def test_grades_unrated_never_lower():
    # Endurance: 6B below the 6C memory, no label → the entry stays (date only).
    st = _endurance_state()
    before = deepcopy(st["working_loads"]["entries"][0])
    out = apply_feedback(_log("2026-10-27", [_endurance_item("6B")], session_id="pe_gym"), st)
    assert out["working_loads"]["entries"][0] == {**before, "updated_at": "2026-10-27"}
    # A rated ok at 6B re-anchors to the grade climbed (unchanged rule).
    rated = apply_feedback(_log("2026-10-27", [_endurance_item("6B", feedback_label="ok")], session_id="pe_gym"), st)
    assert rated["working_loads"]["entries"][0]["next_target_grade"] == "6B"
    # Limit: a 7A+ typed under the 7B memory with no label keeps 7B.
    lim = _limit_state("2026-10-30")
    planned = inject_targets(_limit_day("2026-11-05"), deepcopy(lim))["sessions"]
    item = {"exercise_id": "board_limit_boulders", "completed": True, "used_grade": "7A+",
            "surface_selected": "board_kilter"}
    out = apply_feedback(_log("2026-11-05", [item], session_id="limit_boulder_gym", planned=planned), lim)
    e = out["working_loads"]["entries"][0]
    assert (e["next_target_grade"], e["last_used_grade"], e["updated_at"]) == ("7B", "7B", "2026-11-05")
    assert out["limit_log"][0]["next_target_grade"] == "7B"
    assert _limit_target(out, "2026-11-08")["target_grade"] == "7B"


def test_measure_without_label_can_lower():
    # Anchored hang: a failed hang margin with no label steps down from the
    # load used (−2 kg): a measure is data.
    st = _daniele(entries=[_hang_memory()], hard_labels=_FATIGUE)
    out = apply_feedback(_log("2026-11-03", [_hang_item(87.0, hang_margin="failed")]), st)
    assert _entry(out, "max_hang_7s")["next_total_load_kg"] == 85.0
    # Limit: a problem log with no label is a measure too — it is never kept.
    # Two sessions in a row without progress step the target down (A296).
    problems = [{"grade": "7B", "attempts": 6, "outcome": "no_progress"},
                {"grade": "7B", "attempts": 6, "outcome": "no_progress"}]
    item = {"exercise_id": "board_limit_boulders", "completed": True, "surface_selected": "board_kilter",
            "problems": problems}
    st = _limit_state("2026-10-30")
    for day in ("2026-11-02", "2026-11-05"):
        planned = inject_targets(_limit_day(day), deepcopy(st))["sessions"]
        st = apply_feedback(_log(day, [deepcopy(item)], session_id="limit_boulder_gym", planned=planned), st)
    e = st["working_loads"]["entries"][0]
    row = st["limit_log"][-1]
    assert row["step"] == -1 and e["updated_at"] == "2026-11-05"
    assert e["next_target_grade"] == row["next_target_grade"] == "7A+"


def test_determinism():
    st = _daniele(entries=[_hang_memory()], hard_labels=_FATIGUE)
    log = _log("2026-11-03", [_hang_item(87.0)])
    runs = {repr(apply_feedback(deepcopy(log), deepcopy(st))["working_loads"]) for _ in range(20)}
    assert len(runs) == 1
