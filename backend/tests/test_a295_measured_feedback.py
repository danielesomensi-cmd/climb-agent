"""A295 (R4) — measured feedback.

feedback contract 2 (an untouched exercise is NOT RATED, a legacy 'ok' too),
last-set reps / hang margin / timed overhold, double progression on reps
accessories, pain 0-3 by zone, session difficulty only from what was rated,
router sanitisation. Daniele's numbers come from the B364 fixture (BW 78,
pull-up 1RM 128.9, hang 7 s 116 kg, tested 2026-09-24).
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.api.routers.week import _attach_feedback
from backend.engine import measured_feedback as mf
from backend.engine.adaptive_replan import (
    _derive_session_difficulty,
    append_feedback_log,
    check_adaptive_replan,
    load_exercises_by_id,
)
from backend.engine.progression_v1 import apply_feedback, inject_targets
from backend.tests.test_b364_official_max_vs_working_load import _daniele

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


def _log(day, items, *, contract=2, session_id="custom_cs_x", pain=None, planned=None):
    entry = {"date": day, "session_id": session_id, "actual": {"exercise_feedback_v1": items}}
    if contract is not None:
        entry["feedback_contract"] = contract
    if pain is not None:
        entry["pain"] = pain
    if planned is not None:
        entry["planned"] = planned
    return entry


def _entry(state, key):
    return next(e for e in state["working_loads"]["entries"] if e.get("key") == key)


def _plain_state():
    return {"bodyweight_kg": 78.0, "working_loads": {"entries": [], "rules": {}}, "progression_counters": {}}


def _day(ex_id, prescription, date="2026-10-12", **session):
    s = {"session_id": "strength_long", "intent": "strength",
         "exercise_instances": [{"exercise_id": ex_id, "prescription": prescription}]}
    s.update(session)
    return {"date": date, "sessions": [s]}


def _suggested(state, ex_id, prescription, date="2026-10-12", **session):
    out = inject_targets(_day(ex_id, prescription, date, **session), state)
    return out["sessions"][0]["exercise_instances"][0].get("suggested") or {}


# --- (1) rating ---------------------------------------------------------------

def test_rating_contract_2():
    assert mf.feedback_rating({"exercise_id": "x"}, 2) is None
    assert mf.feedback_rating({"feedback_label": "ok"}, 2) == "ok"
    assert mf.feedback_rating({"feedback_label": "hard"}, 2) == "hard"
    assert mf.feedback_rating({"feedback_label": "skipped"}, 2) is None


def test_rating_legacy_ok_is_not_rated():
    assert mf.feedback_rating({"feedback_label": "ok"}, 0) is None
    assert mf.feedback_rating({}, 0) is None
    assert mf.feedback_rating({"feedback_label": "hard"}, 0) == "hard"
    assert mf.feedback_rating({"difficulty": "too_hard"}, 0) == "very_hard"
    assert mf.feedback_rating({"fail": True}, 0) == "very_hard"


# --- (2) measure kind: explicit allowlists ---------------------------------

@pytest.mark.parametrize("ex,kind", [
    ("weighted_pullup", "last_set_reps"),
    ("weighted_chinup", "last_set_reps"),
    ("max_hang_5s", "hang_margin"), ("max_hang_7s", "hang_margin"),
    ("max_hang_10s", "hang_margin"), ("horst_7_53", "hang_margin"),
    ("max_hang_ladder", None), ("pinch_block_training", None), ("one_arm_hang_assisted", None),
    ("repeater_hang_7_3", None), ("lp_max_lift_7s", None), ("test_max_hang_duration_20mm", None),
    ("bench_press", "dp_reps"), ("goblet_squat", "dp_reps"), ("weighted_dip", "dp_reps"),
    ("wrist_roller", "dp_reps"), ("farmers_carry", None), ("limit_bouldering", None),
])
def test_measure_kind(ex, kind):
    assert mf.measure_kind(ex) == kind


def test_no_hang_or_pull_measure_in_a_test_session():
    assert mf.measure_kind("max_hang_7s", is_test=True) is None
    assert mf.measure_kind("weighted_pullup", is_test=True) is None


def test_inject_targets_exposes_measure_and_dp_target():
    st = _plain_state()
    sug = _suggested(st, "bench_press", {"sets": 3, "reps": 4})
    assert sug["measure"] == "dp_reps"
    assert sug["target_reps"] == 4 and sug["dp_range"] == [4, 6]
    test_sug = _suggested(_daniele(), "max_hang_7s", {"sets": 1, "work_seconds": 7},
                          session_id="test_max_hang_7s", tags={"test": True})
    assert "measure" not in test_sug


# --- (3) pull-up: last-set reps (anchored, Daniele) -------------------------

def _pull(day, *, label=None, last=None, sets=4, done=4, ext=30.0, contract=2, pain=None):
    item = {"exercise_id": "weighted_pullup", "completed": True, "used_external_load_kg": ext,
            "prescribed_reps": 3, "prescribed_sets": sets, "completed_sets": done}
    if label:
        item["feedback_label"] = label
    if last is not None:
        item["last_set_reps"] = last
    return apply_feedback(_log(day, [item], contract=contract, pain=pain), _daniele())


def test_pull_untouched_holds_the_load_used():
    out = _entry(_pull("2026-10-09"), "weighted_pullup")
    assert out["next_external_load_kg"] == 30.0
    assert out["last_feedback_label"] is None and out["last_rated"] is False


def test_pull_measured_reps_move_the_load():
    assert _entry(_pull("2026-10-09", last=4), "weighted_pullup")["next_external_load_kg"] == 32.5
    # +5 kg asked, clamped at the (r+2)RM of the official 1RM: 128.9 / f(5) → 112 total.
    assert _entry(_pull("2026-10-09", last=6), "weighted_pullup")["next_external_load_kg"] == 34.0
    assert _entry(_pull("2026-10-09", last=2), "weighted_pullup")["next_external_load_kg"] < 30.0


def test_pull_fewer_sets_than_prescribed_never_raise():
    out = _entry(_pull("2026-10-09", last=6, done=3), "weighted_pullup")
    assert out["next_external_load_kg"] == 30.0
    counters = _pull("2026-10-09", last=7, done=3)["progression_counters"]
    assert "weighted_pullup" not in (counters.get("retest_signals") or {})


def test_pull_retest_signal_needs_e1rm_above_the_official_max():
    # 108 kg total: e1RM at 6 reps + 1 in reserve = 108 × f(7) ≈ 131 > 128.9 → signal.
    counters = _pull("2026-10-09", last=6)["progression_counters"]
    assert counters["retest_signals"]["weighted_pullup"]["count"] == 1
    no = _pull("2026-10-09", last=4)["progression_counters"]
    assert "weighted_pullup" not in (no.get("retest_signals") or {})


def test_pain_freezes_the_pull_signal_and_the_rise():
    st = _pull("2026-10-09", last=6, pain={"score": 2, "site": "elbow"})
    assert _entry(st, "weighted_pullup")["next_external_load_kg"] == 30.0
    assert "weighted_pullup" not in (st["progression_counters"].get("retest_signals") or {})


# --- (4) hang margin -------------------------------------------------------

def test_untested_hang_margin_moves_the_working_load():
    st = _plain_state()
    item = {"exercise_id": "max_hang_10s", "completed": True, "used_total_load_kg": 100.0, "hang_margin": ">5"}
    out = _entry(apply_feedback(_log("2026-10-09", [item]), st), "max_hang_10s")
    assert out["next_total_load_kg"] == 104.0
    assert out["last_hang_margin"] == ">5"
    item["hang_margin"] = "3-5"
    assert _entry(apply_feedback(_log("2026-10-09", [item]), st), "max_hang_10s")["next_total_load_kg"] == 102.0
    item["hang_margin"] = "failed"
    assert _entry(apply_feedback(_log("2026-10-09", [item]), st), "max_hang_10s")["next_total_load_kg"] == 98.0


def test_untested_hang_rise_capped_at_5pct_per_week():
    st = _plain_state()
    for day in ("2026-10-05", "2026-10-07", "2026-10-09"):
        total = (st["working_loads"]["entries"] and _entry(st, "max_hang_10s")["next_total_load_kg"]) or 100.0
        item = {"exercise_id": "max_hang_10s", "completed": True, "used_total_load_kg": total, "hang_margin": ">5"}
        st = apply_feedback(_log(day, [item]), st)
    assert _entry(st, "max_hang_10s")["next_total_load_kg"] <= 105.0


def test_hang_chip_never_feeds_the_retest_signal():
    item = {"exercise_id": "max_hang_7s", "completed": True, "used_total_load_kg": 104.5,
            "hang_margin": ">5", "edge_mm": 20, "grip": "half_crimp"}
    st = apply_feedback(_log("2026-10-09", [item]), _daniele())
    assert "max_hang_7s" not in (st["progression_counters"].get("retest_signals") or {})


# --- (5) double progression -------------------------------------------------

def _bench(st, day, *, last=None, target=None, label=None, done=3, ext=34.5, sid="custom_cs_x", contract=2):
    item = {"exercise_id": "bench_press", "completed": True, "used_external_load_kg": ext,
            "prescribed_reps": 4, "prescribed_sets": 3, "completed_sets": done}
    if last is not None:
        item["last_set_reps"] = last
    if target is not None:
        item["target_reps"] = target
    if label:
        item["feedback_label"] = label
    return apply_feedback(_log(day, [item], session_id=sid, contract=contract), st)


def test_double_progression_reps_then_load():
    st = _plain_state()
    st = _bench(st, "2026-10-01", last=4, target=4)
    assert _entry(st, "bench_press")["dp_target_reps"] == 5
    assert _entry(st, "bench_press")["next_external_load_kg"] == 34.5
    st = _bench(st, "2026-10-03", last=5, target=5)
    assert _entry(st, "bench_press")["dp_target_reps"] == 6
    st = _bench(st, "2026-10-05", last=6, target=6)
    e = _entry(st, "bench_press")
    assert e["next_external_load_kg"] == 35.5 and e["dp_target_reps"] == 4
    # The next prescription shows the new target.
    sug = _suggested(st, "bench_press", {"sets": 3, "reps": 4}, date="2026-10-07")
    assert sug["target_reps"] == 4 and sug["suggested_external_load_kg"] == 35.5


def test_double_progression_target_shown_in_scheme():
    st = _bench(_plain_state(), "2026-10-01", last=4, target=4)
    sug = _suggested(st, "bench_press", {"sets": 3, "reps": 4}, date="2026-10-03")
    assert sug["target_reps"] == 5 and sug["suggested_rep_scheme"] == "3x5"


def test_double_progression_miss_hard_or_missing_sets_hold():
    st = _plain_state()
    assert _entry(_bench(st, "2026-10-01", last=3, target=4), "bench_press")["dp_target_reps"] == 4
    hard = _entry(_bench(st, "2026-10-01", last=6, target=4, label="hard"), "bench_press")
    assert hard["dp_target_reps"] == 4 and hard["next_external_load_kg"] < 34.5
    short = _entry(_bench(st, "2026-10-01", last=6, target=4, done=2), "bench_press")
    assert short["dp_target_reps"] == 4 and short["next_external_load_kg"] == 34.5


def test_double_progression_labels_without_measure():
    st = _plain_state()
    assert _entry(_bench(st, "2026-10-01", label="easy"), "bench_press")["next_external_load_kg"] == 36.0
    assert _entry(_bench(st, "2026-10-01", label="very_easy"), "bench_press")["next_external_load_kg"] == 38.0
    assert _entry(_bench(st, "2026-10-01"), "bench_press")["next_external_load_kg"] == 34.5


def test_double_progression_pain_freezes():
    st = _plain_state()
    item = {"exercise_id": "bench_press", "completed": True, "used_external_load_kg": 34.5,
            "prescribed_reps": 4, "last_set_reps": 6, "target_reps": 4}
    out = apply_feedback(_log("2026-10-01", [item], pain={"score": 2, "site": "elbow"}), st)
    assert _entry(out, "bench_press")["dp_target_reps"] == 4


def test_double_progression_per_hand_reads_the_weaker_hand():
    st = _plain_state()
    items = [
        {"exercise_id": "bulgarian_split_squat", "completed": True, "used_external_load_kg": 20.0,
         "prescribed_reps": 8, "hand": "right", "last_set_reps": 9, "target_reps": 8},
        {"exercise_id": "bulgarian_split_squat", "completed": True, "used_external_load_kg": 20.0,
         "prescribed_reps": 8, "hand": "left", "last_set_reps": 7, "target_reps": 8},
    ]
    out = apply_feedback(_log("2026-10-01", items), st)
    e = _entry(out, "bulgarian_split_squat")
    assert e["dp_target_reps"] == 8 and e["last_set_reps"] == 7


def test_double_progression_replay_is_idempotent_and_pencil_correction_applies():
    st = _plain_state()
    once = _bench(st, "2026-10-01", last=4, target=4, sid="s1")
    twice = _bench(once, "2026-10-01", last=4, target=4, sid="s1")
    assert _entry(twice, "bench_press")["dp_target_reps"] == 5
    corrected = _bench(once, "2026-10-01", last=2, target=4, sid="s1")
    assert _entry(corrected, "bench_press")["dp_target_reps"] == 4


def test_out_of_order_log_never_rewrites_a_newer_entry():
    st = _bench(_plain_state(), "2026-10-05", last=4, target=4)
    newer = deepcopy(_entry(st, "bench_press"))
    older = _bench(st, "2026-10-01", last=6, target=4)
    assert _entry(older, "bench_press") == newer


# --- (6) pain ----------------------------------------------------------------

def test_pain_blocks_written_by_score():
    st = apply_feedback(_log("2026-10-05", [], pain={"score": 2, "site": "fingers"}), _plain_state())
    assert st["progression_counters"]["pain_blocks"]["fingers"] == {
        "score": 2, "from": "2026-10-05", "until": "2026-10-11", "source": "2026-10-05|custom_cs_x"}
    st3 = apply_feedback(_log("2026-10-05", [], pain={"score": 3, "site": None}), _plain_state())
    assert st3["progression_counters"]["pain_blocks"]["other"]["until"] == "2026-10-18"
    st1 = apply_feedback(_log("2026-10-05", [], pain={"score": 1, "site": "fingers"}), _plain_state())
    assert "pain_blocks" not in st1["progression_counters"]


def test_milder_pain_never_shortens_a_block():
    st = apply_feedback(_log("2026-10-05", [], pain={"score": 3, "site": "fingers"}), _plain_state())
    st = apply_feedback(_log("2026-10-06", [], pain={"score": 2, "site": "fingers"}), st)
    assert st["progression_counters"]["pain_blocks"]["fingers"]["score"] == 3


def test_pain_read_side_cuts_the_zone_only():
    st = _plain_state()
    st["working_loads"]["entries"] = [
        {"exercise_id": "bench_press", "key": "bench_press", "setup": {}, "next_external_load_kg": 40.0,
         "updated_at": "2026-10-01"},
        {"exercise_id": "goblet_squat", "key": "goblet_squat", "setup": {}, "next_external_load_kg": 30.0,
         "updated_at": "2026-10-01"},
    ]
    st["progression_counters"]["pain_blocks"] = {"elbow": {"score": 2, "from": "2026-10-05", "until": "2026-10-11"}}
    bench = _suggested(st, "bench_press", {"sets": 3, "reps": 4}, date="2026-10-06")
    assert bench["suggested_external_load_kg"] == 36.0 and bench["pain_flag"] is True
    goblet = _suggested(st, "goblet_squat", {"sets": 3, "reps": 8}, date="2026-10-06")
    assert goblet["suggested_external_load_kg"] == 30.0 and "pain_flag" not in goblet
    after = _suggested(st, "bench_press", {"sets": 3, "reps": 4}, date="2026-10-12")
    assert after["suggested_external_load_kg"] == 40.0


def test_finger_pain_caps_anchored_hang_and_flags_it():
    st = _daniele()
    st["progression_counters"]["pain_blocks"] = {"fingers": {"score": 3, "from": "2026-10-05", "until": "2026-10-18"}}
    sug = _suggested(st, "max_hang_7s", {"sets": 5, "work_seconds": 7}, date="2026-10-06")
    assert sug["pain_flag"] is True
    assert sug["suggested_total_load_kg"] <= 0.80 * 116.0


def test_limit_boulder_flagged_under_finger_pain():
    st = _plain_state()
    st["progression_counters"]["pain_blocks"] = {"fingers": {"score": 2, "from": "2026-10-05", "until": "2026-10-11"}}
    sug = _suggested(st, "limit_bouldering", {"sets": 1}, date="2026-10-06")
    assert sug.get("pain_flag") is True


def test_pain_never_touches_past_logs():
    st = _plain_state()
    st["feedback_log"] = [{"date": "2026-10-01", "session_id": "a", "difficulty": "hard"}]
    before = deepcopy(st["feedback_log"])
    out = apply_feedback(_log("2026-10-05", [], pain={"score": 3, "site": "fingers"}), st)
    assert out["feedback_log"] == before


# --- (7) unrated is inert ----------------------------------------------------

def test_difficulty_needs_half_the_fatigue_cost_rated():
    ex = load_exercises_by_id()
    one_warmup = _log("2026-10-05", [
        {"exercise_id": "general_pulse_raise", "completed": True, "feedback_label": "very_hard"},
        {"exercise_id": "max_hang_7s", "completed": True},
        {"exercise_id": "weighted_pullup", "completed": True},
    ])
    assert _derive_session_difficulty(one_warmup, ex) is None
    rated = deepcopy(one_warmup)
    rated["actual"]["exercise_feedback_v1"][1]["feedback_label"] = "hard"
    assert _derive_session_difficulty(rated, ex) in ("hard", "very_hard")
    assert _derive_session_difficulty(_log("2026-10-05", []), ex) is None


def test_single_very_hard_warmup_does_not_trigger_recovery():
    state = {"feedback_log": []}
    ex = load_exercises_by_id()
    for day in ("2026-10-04", "2026-10-05"):
        append_feedback_log(state, _log(day, [
            {"exercise_id": "general_pulse_raise", "completed": True, "feedback_label": "very_hard"},
            {"exercise_id": "max_hang_7s", "completed": True},
        ], session_id=f"s{day}"), None, ex)
    assert all("difficulty" not in e for e in state["feedback_log"])
    plan = {"weeks": [{"days": [{"date": "2026-10-06", "sessions": [{"session_id": "x", "tags": {"hard": True}}]}]}]}
    assert check_adaptive_replan(plan, state["feedback_log"], "2026-10-05")["actions"] == []


def test_resubmit_without_rating_keeps_the_rated_difficulty():
    state = {"feedback_log": []}
    ex = load_exercises_by_id()
    append_feedback_log(state, _log("2026-10-05", [
        {"exercise_id": "max_hang_7s", "completed": True, "feedback_label": "hard"}], session_id="s"), None, ex)
    append_feedback_log(state, _log("2026-10-05", [
        {"exercise_id": "max_hang_7s", "completed": True}], session_id="s"), None, ex)
    assert state["feedback_log"][0]["difficulty"] == "hard"
    assert state["feedback_log"][0]["exercise_feedback"] == {"max_hang_7s": "hard"}


def test_week_attach_feedback_without_difficulty_does_not_crash():
    plan = {"weeks": [{"days": [{"date": "2026-10-05", "sessions": [{"session_id": "s", "status": "done"}]}]}]}
    _attach_feedback(plan, [{"date": "2026-10-05", "session_id": "s", "session_duration_seconds": 60}])
    sess = plan["weeks"][0]["days"][0]["sessions"][0]
    assert "feedback_summary" not in sess and sess["session_duration_seconds"] == 60


# --- (8) router --------------------------------------------------------------

def test_sanitize_drops_bad_fields_with_warnings():
    entry = _log("2026-10-05", [{
        "exercise_id": "weighted_pullup", "completed": True, "feedback_label": None,
        "last_set_reps": 99, "hang_margin": "x", "hang_held_s": -1, "target_reps": 0,
    }, {"exercise_id": "bench_press", "completed": True, "feedback_label": "meh", "last_set_reps": 5}],
        pain={"score": 7})
    warnings = mf.sanitize_log_entry(entry)
    a, b = entry["actual"]["exercise_feedback_v1"]
    assert set(a) == {"exercise_id", "completed"}
    assert b == {"exercise_id": "bench_press", "completed": True, "last_set_reps": 5}
    assert "pain" not in entry
    assert len(warnings) == 6


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


def _seed_plan(date, sid, exercises):
    wp = {"start_date": date, "weeks": [{"phase": "base", "days": [{"date": date, "weekday": "mon", "sessions": [{
        "session_id": sid, "slot": "evening",
        "resolved": {"resolved_session": {"exercise_instances": exercises}},
    }]}]}]}
    state = deps.load_state(None)
    state["current_week_plan"] = deepcopy(wp)
    state["week_plans"] = {date: deepcopy(wp)}
    state["session_completion_log"] = []
    state["feedback_log"] = []
    deps.save_state(state, None)


def test_endpoint_sanitizes_attaches_prescription_and_suggests_limitation(isolated_state):
    date, sid = "2026-03-16", "strength_long"
    _seed_plan(date, sid, [
        {"exercise_id": "bench_press", "prescription": {"sets": 3, "reps": 4}},
        {"exercise_id": "max_hang_10s", "prescription": {"sets": 4, "work_seconds": 10}},
    ])
    r = client.post("/api/feedback", json={"log_entry": {
        "date": date, "session_id": sid, "feedback_contract": 2,
        "pain": {"score": 3, "site": "fingers"},
        "actual": {"exercise_feedback_v1": [
            {"exercise_id": "bench_press", "completed": True, "used_external_load_kg": 30.0,
             "last_set_reps": 99, "feedback_label": None},
            {"exercise_id": "max_hang_10s", "completed": True, "used_total_load_kg": 90.0, "hang_margin": "3-5"},
        ]},
    }, "status": "done"})
    assert r.status_code == 200, r.text
    sugg = r.json().get("limitation_suggestions") or []
    assert any(s.get("source") == "pain" and s["zone"] == "finger" for s in sugg)
    state = deps.load_state(None)
    bench = next(e for e in state["working_loads"]["entries"] if e["exercise_id"] == "bench_press")
    assert bench["next_external_load_kg"] == 30.0 and bench["last_rated"] is False
    assert "last_set_reps" not in bench
    hang = next(e for e in state["working_loads"]["entries"] if e["exercise_id"] == "max_hang_10s")
    # A295 review: pain 3 on fingers reported by this session freezes the
    # '3-5' step (+2 kg without pain): the load used is held.
    assert hang["last_work_seconds"] == 10.0 and hang["next_total_load_kg"] == 90.0
    assert state["progression_counters"]["pain_blocks"]["fingers"]["score"] == 3
    log = next(e for e in state["session_completion_log"] if e["session_id"] == sid)
    assert log["pain"] == {"score": 3, "site": "fingers"}
    assert "difficulty" not in log  # nothing rated
