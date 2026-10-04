"""A295 review fixes — pain block compounding, freeze, correction, loading-pin
cut, test-session flag and retest blocker, non-anchored hang cap, untested
pull-up measure.
"""

from __future__ import annotations

from datetime import date

from backend.engine import measured_feedback as mf
from backend.engine import retest_policy as rp
from backend.engine.progression_v1 import apply_feedback, inject_targets
from backend.tests.test_b364_official_max_vs_working_load import _daniele


def _log(day, items, *, session_id="strength_long", pain=None, contract=2):
    entry = {"date": day, "session_id": session_id, "feedback_contract": contract,
             "actual": {"exercise_feedback_v1": items}}
    if pain is not None:
        entry["pain"] = pain
    return entry


def _plain_state():
    return {"bodyweight_kg": 78.0, "working_loads": {"entries": [], "rules": {}}, "progression_counters": {}}


def _entry(state, key):
    return next(e for e in state["working_loads"]["entries"] if e.get("key") == key)


def _suggested(state, ex_id, prescription, day, session_id="strength_long", **session):
    s = {"session_id": session_id, "intent": "strength",
         "exercise_instances": [{"exercise_id": ex_id, "prescription": prescription}]}
    s.update(session)
    out = inject_targets({"date": day, "sessions": [s]}, state)
    return out["sessions"][0]["exercise_instances"][0].get("suggested") or {}


# --- (1) the pain cut never compounds -----------------------------------------

def test_bench_pain_cut_does_not_compound_and_ends_with_the_block():
    st = _plain_state()
    st["working_loads"]["entries"] = [{"exercise_id": "bench_press", "key": "bench_press", "setup": {},
                                       "next_external_load_kg": 40.0, "updated_at": "2026-09-30"}]
    st = apply_feedback(_log("2026-10-01", [], pain={"score": 2, "site": "elbow"}, session_id="s0"), st)
    seen = []
    for day in ("2026-10-02", "2026-10-04", "2026-10-06"):
        sug = _suggested(st, "bench_press", {"sets": 3, "reps": 4}, day)
        seen.append(sug["suggested_external_load_kg"])
        st = apply_feedback(_log(day, [{"exercise_id": "bench_press", "completed": True,
                                        "used_external_load_kg": sug["suggested_external_load_kg"]}]), st)
    assert seen == [36.0, 36.0, 36.0]
    assert _entry(st, "bench_press")["next_external_load_kg"] == 40.0
    after = _suggested(st, "bench_press", {"sets": 3, "reps": 4}, "2026-10-09")
    assert after["suggested_external_load_kg"] == 40.0 and "pain_flag" not in after


def test_hard_label_under_pain_steps_down_from_the_pre_block_load_once():
    st = _plain_state()
    st["working_loads"]["entries"] = [{"exercise_id": "bench_press", "key": "bench_press", "setup": {},
                                       "next_external_load_kg": 40.0, "updated_at": "2026-09-30"}]
    st = apply_feedback(_log("2026-10-01", [], pain={"score": 2, "site": "elbow"}, session_id="s0"), st)
    item = {"exercise_id": "bench_press", "completed": True, "used_external_load_kg": 36.0, "feedback_label": "hard"}
    st1 = apply_feedback(_log("2026-10-02", [item]), st)
    first = _entry(st1, "bench_press")["next_external_load_kg"]
    assert 38.0 <= first < 40.0
    # Replay of the same session: same result (snapshot), not a second step.
    st2 = apply_feedback(_log("2026-10-02", [item]), st1)
    assert _entry(st2, "bench_press")["next_external_load_kg"] == first


def test_anchored_hang_under_finger_pain_holds_the_working_load():
    st = _daniele(entries=[{"exercise_id": "max_hang_7s", "key": "max_hang_7s", "setup": {},
                            "next_total_load_kg": 104.5, "last_total_load_kg": 104.5, "last_work_seconds": 7,
                            "updated_at": "2026-10-03", "phase_id_at_log": "strength_power",
                            "intensity_at_log": "hard"}])
    st = apply_feedback(_log("2026-10-05", [], pain={"score": 2, "site": "fingers"}, session_id="s0"), st)
    totals = []
    for day in ("2026-10-06", "2026-10-08", "2026-10-10"):
        sug = _suggested(st, "max_hang_7s", {"sets": 5, "work_seconds": 7}, day)
        totals.append(sug["suggested_total_load_kg"])
        st = apply_feedback(_log(day, [{"exercise_id": "max_hang_7s", "completed": True,
                                        "used_total_load_kg": sug["suggested_total_load_kg"]}]), st)
    assert len(set(totals)) == 1, totals  # no compounding
    after = _suggested(st, "max_hang_7s", {"sets": 5, "work_seconds": 7}, "2026-10-13")
    assert after["suggested_total_load_kg"] > totals[0]
    assert "pain" not in (after.get("anchored") or {})


# --- (2) upward steps frozen outside the anchored four -------------------------

def test_non_anchored_hangs_and_labels_frozen_under_finger_pain():
    st = apply_feedback(_log("2026-10-01", [], pain={"score": 3, "site": "fingers"}, session_id="s0"), _plain_state())
    measured = apply_feedback(_log("2026-10-03", [{"exercise_id": "max_hang_10s", "completed": True,
                                                   "used_total_load_kg": 90.0, "hang_margin": ">5"}]), st)
    assert _entry(measured, "max_hang_10s")["next_total_load_kg"] == 90.0
    labelled = apply_feedback(_log("2026-10-03", [{"exercise_id": "horst_7_53", "completed": True,
                                                   "used_total_load_kg": 90.0, "feedback_label": "very_easy"}]), st)
    horst = next(e for e in labelled["working_loads"]["entries"] if e["exercise_id"] == "horst_7_53")
    assert horst["next_total_load_kg"] == 90.0
    # Without pain the same very_easy still raises it (untested behaviour kept).
    free = apply_feedback(_log("2026-10-03", [{"exercise_id": "horst_7_53", "completed": True,
                                               "used_total_load_kg": 90.0, "feedback_label": "very_easy"}]), _plain_state())
    assert next(e for e in free["working_loads"]["entries"]
                if e["exercise_id"] == "horst_7_53")["next_total_load_kg"] > 90.0


# --- (3) a pain block can be corrected by the session that wrote it ------------

def test_resubmit_of_same_session_with_lower_pain_removes_the_block():
    st = apply_feedback(_log("2026-10-05", [], pain={"score": 3, "site": "fingers"}), _plain_state())
    assert st["progression_counters"]["pain_blocks"]["fingers"]["score"] == 3
    fixed = apply_feedback(_log("2026-10-05", [], pain={"score": 0, "site": None}), st)
    assert "fingers" not in fixed["progression_counters"]["pain_blocks"]
    to_two = apply_feedback(_log("2026-10-05", [], pain={"score": 2, "site": "fingers"}), st)
    assert to_two["progression_counters"]["pain_blocks"]["fingers"]["score"] == 2
    # Not answered (no pain field) leaves it alone.
    same = apply_feedback(_log("2026-10-05", []), st)
    assert same["progression_counters"]["pain_blocks"]["fingers"]["score"] == 3


def test_correction_restores_the_block_another_session_wrote():
    st = apply_feedback(_log("2026-10-01", [], pain={"score": 2, "site": "fingers"}, session_id="a"), _plain_state())
    st = apply_feedback(_log("2026-10-05", [], pain={"score": 3, "site": "fingers"}, session_id="b"), st)
    st = apply_feedback(_log("2026-10-05", [], pain={"score": 0}, session_id="b"), st)
    assert st["progression_counters"]["pain_blocks"]["fingers"] == {
        "score": 2, "from": "2026-10-01", "until": "2026-10-07", "source": "2026-10-01|a"}
    # Another session's milder report still never shortens a block.
    st = apply_feedback(_log("2026-10-02", [], pain={"score": 1, "site": "fingers"}, session_id="c"), st)
    assert st["progression_counters"]["pain_blocks"]["fingers"]["score"] == 2


# --- (4) loading-pin per-hand cut ---------------------------------------------

def test_loading_pin_per_hand_loads_cut_and_capped():
    st = {"progression_counters": {"pain_blocks": {"fingers": {"score": 3, "from": "2026-10-05", "until": "2026-10-18"}}},
          "baselines": {"loading_pin": [{"hand": "right", "max_load_kg": 45.0}, {"hand": "left", "max_load_kg": 60.0}]}}
    sug = {"right_hand": {"suggested_external_load_kg": 40.0}, "left_hand": {"suggested_external_load_kg": 40.0}}
    mf.pain_adjust_suggested(sug, st, "lp_max_lift_7s", "2026-10-06", load_model="external_load", bodyweight=78.0)
    assert sug["pain_flag"] is True
    assert sug["right_hand"]["suggested_external_load_kg"] == 36.0  # 0.80 × 45
    assert sug["left_hand"]["suggested_external_load_kg"] == 36.0   # 0.90 × 40


# --- (5) test sessions: flag on the card, retest blocked -----------------------

def test_test_session_gets_the_pain_flag_without_a_cut():
    st = _daniele()
    st["progression_counters"]["pain_blocks"] = {"fingers": {"score": 3, "from": "2026-10-22", "until": "2026-11-04"}}
    plain = _daniele()
    # The anchored hang of the test template carries the flag (and its cut).
    hang = _suggested(st, "max_hang_7s", {"sets": 1, "work_seconds": 7}, "2026-10-24",
                      session_id="test_max_hang_7s", tags={"test": True})
    assert hang.get("pain_flag") is True
    # A non-anchored exercise of a test session: flag, never a cut load.
    args = ("test_max_hang_duration_20mm", {"sets": 1}, "2026-10-24")
    flagged = _suggested(st, *args, session_id="test_max_hang_7s", tags={"test": True})
    ref = _suggested(plain, *args, session_id="test_max_hang_7s", tags={"test": True})
    assert flagged.get("pain_flag") is True
    assert {k: v for k, v in flagged.items() if k not in ("pain_flag", "pain")} == ref


def test_retest_blocked_by_pain_on_the_axis():
    st = {"progression_counters": {"pain_blocks": {"fingers": {"score": 2, "from": "2026-10-20", "until": "2026-10-26"}}}}
    assert rp.pain_blocked(st, rp.AXIS_FINGER, date(2026, 10, 24)) is not None
    assert rp.pain_blocked(st, rp.AXIS_FINGER, date(2026, 10, 27)) is not None  # 7 days after
    assert rp.pain_blocked(st, rp.AXIS_FINGER, date(2026, 10, 28)) is None
    assert rp.pain_blocked(st, rp.AXIS_PULLING, date(2026, 10, 24)) is None
    codes = [b["code"] for b in rp.test_day_blockers(st, rp.AXIS_FINGER, "2026-10-24")]
    assert "pain" in codes


# --- (6) non-anchored hang cap for a tested athlete -----------------------------

def test_max_hang_10s_capped_by_official_max_of_tested_athlete():
    st = _daniele(entries=[])
    cap = None
    for i, day in enumerate(("2026-10-01", "2026-10-03", "2026-10-05", "2026-10-08", "2026-10-10",
                             "2026-10-12", "2026-10-15", "2026-10-17", "2026-10-19", "2026-10-22")):
        prev = next((e for e in st["working_loads"]["entries"] if e["exercise_id"] == "max_hang_10s"), None)
        used = prev["next_total_load_kg"] if prev else 100.0
        st = apply_feedback(_log(day, [{"exercise_id": "max_hang_10s", "completed": True,
                                        "used_total_load_kg": used, "hang_margin": ">5"}]), st)
    from backend.engine.anchored_load import hang_write_cap

    cap = hang_write_cap(st, 10, "2026-10-22")
    assert cap is not None
    assert next(e for e in st["working_loads"]["entries"]
                if e["exercise_id"] == "max_hang_10s")["next_total_load_kg"] <= cap
    assert hang_write_cap(_plain_state(), 10, "2026-10-22") is None  # untested: no cap


# --- (7) untested weighted pull-up: measure consumed, no fake 'ok' -------------

def test_untested_pullup_reads_last_set_reps_and_stores_no_fake_ok():
    st = _plain_state()
    item = {"exercise_id": "weighted_pullup", "completed": True, "used_external_load_kg": 20.0,
            "prescribed_reps": 3}
    unrated = apply_feedback(_log("2026-10-05", [item]), st)
    e = _entry(unrated, "weighted_pullup")
    assert e["last_feedback_label"] is None and e["last_rated"] is False
    measured = apply_feedback(_log("2026-10-05", [dict(item, last_set_reps=8)]), st)
    m = _entry(measured, "weighted_pullup")
    assert m["last_set_reps"] == 8 and m["last_rated"] is True
    assert m["e2rm_total_kg"] > e["e2rm_total_kg"]


def test_untested_chinup_last_set_reps_moves_the_load():
    st = _plain_state()
    item = {"exercise_id": "weighted_chinup", "completed": True, "used_total_load_kg": 98.0,
            "prescribed_reps": 4}
    plain = apply_feedback(_log("2026-10-05", [item]), st)
    assert _entry(plain, "weighted_chinup")["next_total_load_kg"] == 98.0
    up = apply_feedback(_log("2026-10-05", [dict(item, last_set_reps=7)]), st)
    assert _entry(up, "weighted_chinup")["next_total_load_kg"] == 103.0
    down = apply_feedback(_log("2026-10-05", [dict(item, last_set_reps=2)]), st)
    assert _entry(down, "weighted_chinup")["next_total_load_kg"] < 98.0
