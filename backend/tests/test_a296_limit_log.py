"""A296 (R6c) — limit log + problem logger, source of the limit_power exposure.

Fixture: the B365 Kilter/gym state (Daniele's real limit memory on 04/10,
boulder RP 7C). On 05/10 the Kilter target is 7A+ (re-entry from 7B), so
most progression cases run after a re-entry is closed, or on a fresh surface.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import limit_log
from backend.engine.key_sessions_v1 import phase_requirements, session_dose
from backend.engine.progression_v1 import (
    apply_feedback,
    inject_targets,
    limit_grade_target,
    limit_target_on_surface,
)
from backend.engine.stimulus import FAMILY_LIMIT_POWER, exposures, finger_hard_days

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"

KILTER_GYM = "16710e5a"
WALL_GYM = "wall_only"


def _state():
    return {
        "user": {"id": "daniele"},
        "bodyweight_kg": 76.0,
        "assessment": {"grades": {"boulder_max_rp": "7C", "boulder_max_os": "7A",
                                   "lead_max_rp": "8a+", "lead_max_os": "7a+"}},
        "performance": {"current_level": {"boulder": {"worked": {"grade": "7C"}}}},
        "equipment": {"gyms": [
            {"gym_id": KILTER_GYM, "equipment": ["spraywall", "board_kilter", "gym_routes", "hangboard"]},
            {"gym_id": WALL_GYM, "equipment": ["gym_boulder"]},
        ]},
        "working_loads": {"rules": {}, "entries": [
            {"key": "spray_wall_limit|surface=board_kilter", "setup": {"surface": "board_kilter"},
             "updated_at": "2026-07-30", "exercise_id": "spray_wall_limit", "last_used_grade": "7B",
             "surface_selected": "board_kilter", "next_target_grade": "7B", "last_feedback_label": "ok"},
        ]},
    }


def _fresh_kilter_state(grade="7B", updated="2026-10-01"):
    """Kilter memory 4 days old: no re-entry, target = memory."""
    st = _state()
    st["working_loads"]["entries"][0].update({"updated_at": updated, "next_target_grade": grade, "last_used_grade": grade})
    return st


def _day(date_value, gym_id=KILTER_GYM, exercise_id="limit_bouldering", session_id="limit_boulder_gym"):
    return {"date": date_value, "sessions": [{
        "session_id": session_id, "intent": "power", "gym_id": gym_id,
        "tags": {"hard": True, "finger": True},
        "exercise_instances": [{"exercise_id": exercise_id,
                                "prescription": {"grade_ref": "boulder_max_rp", "grade_offset": 0}}],
    }]}


def _target(state, date_value, gym_id=KILTER_GYM):
    out = inject_targets(_day(date_value, gym_id), deepcopy(state))
    return out["sessions"][0]["exercise_instances"][0]["suggested"]["suggested_boulder_target"]


def _feedback(state, date_value, problems=None, *, label=None, used_grade=None, surface="board_kilter",
              gym_id=KILTER_GYM, session_id="limit_boulder_gym", planned=True):
    item = {"exercise_id": "limit_bouldering", "completed": True, "surface_selected": surface}
    if label:
        item["feedback_label"] = label
    if used_grade:
        item["used_grade"] = used_grade
    if problems is not None:
        item["problems"] = problems
    log = {"date": date_value, "session_id": session_id, "feedback_contract": 2,
           "actual": {"exercise_feedback_v1": [item]}}
    if planned:
        log["planned"] = inject_targets(_day(date_value, gym_id, session_id=session_id), deepcopy(state))["sessions"]
    return apply_feedback(log, state)


def _wl(state, surface="board_kilter"):
    return next(e for e in state["working_loads"]["entries"]
                if e["key"] == f"limit_bouldering|surface={surface}")


def P(grade, outcome, attempts=3, **kw):
    return {"grade": grade, "outcome": outcome, "attempts": attempts, **kw}


# ─── sanitising ──────────────────────────────────────────────────────────


def test_invalid_rows_dropped_one_by_one():
    clean, warnings = limit_log.sanitize_problems([
        P("7b", "sent"),                 # lowercase → 7B
        P("9Z", "sent"),                 # not a Font grade
        P("7A", "sent", attempts=0),     # attempts below 1
        P("7A", "sent", attempts=11),    # above 10
        P("7A", "flash"),                # unknown outcome
        "garbage",
        P("7A+", "high_point", attempts=10, crux_moves=2, name="  Il tetto  "),
    ])
    assert clean == [
        {"grade": "7B", "attempts": 3, "outcome": "sent"},
        {"grade": "7A+", "attempts": 10, "outcome": "high_point", "crux_moves": 2, "name": "Il tetto"},
    ]
    assert len(warnings) == 5


def test_at_most_eight_rows():
    clean, warnings = limit_log.sanitize_problems([P("7A", "sent")] * 12)
    assert len(clean) == limit_log.MAX_PROBLEMS
    assert warnings


def test_sent_on_attempt_kept_only_when_coherent():
    clean, _ = limit_log.sanitize_problems([P("7A", "sent", attempts=3, sent_on_attempt=2),
                                            P("7A", "sent", attempts=3, sent_on_attempt=5),
                                            P("7A", "no_progress", attempts=3, sent_on_attempt=1)])
    assert clean[0]["sent_on_attempt"] == 2
    assert "sent_on_attempt" not in clean[1]
    assert "sent_on_attempt" not in clean[2]


# ─── classification ──────────────────────────────────────────────────────


@pytest.mark.parametrize("problems,delta,reason", [
    ([P("7B+", "sent")], 1, "sent_above_target"),
    ([P("7B", "sent"), P("7B", "sent")], 1, "two_sends_at_target"),
    ([P("7B", "sent")], 0, "progress_at_target"),
    ([P("7B", "high_point")], 0, "progress_at_target"),
    ([P("7B", "no_progress", crux_moves=2)], 0, "progress_at_target"),
    ([P("7A+", "sent")], 0, "progress_at_target"),   # send at T − 1 half: progress, hold
    ([P("7B", "no_progress"), P("7A", "sent")], 0, "first_session_without_progress"),
])
def test_classify_single_session(problems, delta, reason):
    c = limit_log.classify_session(problems, "7B", previous=None)
    assert (c["delta"], c["reason"]) == (delta, reason)


def test_one_bad_session_never_lowers_two_in_a_row_do():
    bad = [P("7B", "no_progress"), P("6C", "sent")]
    prev_bad = {"target_grade": "7B", "problems": bad}
    prev_good = {"target_grade": "7B", "problems": [P("7B", "high_point")]}
    assert limit_log.classify_session(bad, "7B", previous=prev_good)["delta"] == 0
    assert limit_log.classify_session(bad, "7B", previous=None)["delta"] == 0
    assert limit_log.classify_session(bad, "7B", previous=prev_bad)["delta"] == -1
    # A label-only previous session: hard = no progress, not rated = progress.
    assert limit_log.classify_session(bad, "7B", previous={"target_grade": "7B", "problems": [],
                                                           "feedback_label": "hard"})["delta"] == -1
    assert limit_log.classify_session(bad, "7B", previous={"target_grade": "7B", "problems": [],
                                                           "feedback_label": None})["delta"] == 0


def test_never_more_than_one_half_grade():
    c = limit_log.classify_session([P("8A", "sent"), P("8A", "sent"), P("7C+", "sent")], "7B", previous=None)
    assert c["delta"] == 1


def test_hard_attempts_guard_blocks_the_step_up():
    problems = [P("7B", "sent", attempts=10), P("7B", "sent", attempts=10), P("7A+", "no_progress", attempts=5)]
    c = limit_log.classify_session(problems, "7B", previous=None)
    assert c["hard_attempts"] == 25
    assert c["guard"] is True
    assert c["delta"] == 0 and c["reason"] == "hard_attempts_guard"
    # Easy problems do not count as hard attempts.
    easy = [P("6C", "sent", attempts=10)] * 3
    assert limit_log.classify_session(easy, "7B", previous=None)["hard_attempts"] == 0


def test_qualifies_needs_two_problems_at_target():
    assert limit_log.qualifies([P("7B", "sent"), P("7B", "high_point")], "7B")
    assert not limit_log.qualifies([P("7B", "sent"), P("7A+", "sent")], "7B")
    assert not limit_log.qualifies([P("7B", "sent"), P("7B", "no_progress")], "7B")


# ─── apply_feedback ──────────────────────────────────────────────────────


def test_problems_move_the_target_up_and_write_the_log():
    st = _fresh_kilter_state("7B")
    assert _target(st, "2026-10-05")["target_grade"] == "7B"
    out = _feedback(st, "2026-10-05", [P("7B", "sent"), P("7B", "sent", attempts=4), P("7B+", "no_progress")])
    assert _wl(out)["next_target_grade"] == "7B+"
    assert _wl(out)["last_used_grade"] == "7B"
    assert _target(out, "2026-10-08")["target_grade"] == "7B+"
    [entry] = out["limit_log"]
    assert entry["date"] == "2026-10-05"
    assert entry["session_id"] == "limit_boulder_gym"
    assert entry["exercise_id"] == "limit_bouldering"
    assert entry["surface"] == "board_kilter"
    assert entry["target_grade"] == "7B"
    assert entry["source"] == "planned"
    assert entry["step"] == 1 and entry["step_reason"] == "two_sends_at_target"
    assert entry["qualifies"] is True
    assert len(entry["problems"]) == 3


def test_problems_win_over_the_label():
    st = _fresh_kilter_state("7B")
    out = _feedback(st, "2026-10-05", [P("7B", "high_point")], label="very_hard", used_grade="7B")
    assert _wl(out)["next_target_grade"] == "7B"  # label alone would have said 6C+ (−2 half)
    assert out["limit_log"][0]["feedback_label"] == "very_hard"


def test_a_session_working_a_problem_without_topping_it_holds():
    st = _fresh_kilter_state("7B")
    out = _feedback(st, "2026-10-05", [P("7B", "no_progress", attempts=6, crux_moves=3)])
    assert _wl(out)["next_target_grade"] == "7B"
    # The band reads last_used_grade: nothing sent → the previous value stays.
    assert _wl(out).get("last_used_grade") in (None, "7B")


def test_two_sessions_without_progress_step_down_once():
    st = _fresh_kilter_state("7B")
    bad = [P("7B", "no_progress", attempts=4), P("6C+", "sent")]
    s1 = _feedback(st, "2026-10-05", bad)
    assert _wl(s1)["next_target_grade"] == "7B"
    assert s1["limit_log"][-1]["step_reason"] == "first_session_without_progress"
    s2 = _feedback(s1, "2026-10-08", bad)
    assert _wl(s2)["next_target_grade"] == "7A+"
    assert s2["limit_log"][-1]["step_reason"] == "two_sessions_without_progress"


def test_label_path_unchanged_without_problems():
    st = _fresh_kilter_state("7B")
    out = _feedback(st, "2026-10-05", label="easy", used_grade="7B")
    assert _wl(out)["next_target_grade"] == "7B+"
    [entry] = out["limit_log"]
    assert entry["problems"] == [] and "step" not in entry
    assert entry["feedback_label"] == "easy"


def test_resubmission_replaces_the_entry_and_does_not_restep():
    st = _fresh_kilter_state("7B")
    problems = [P("7B", "sent"), P("7B", "sent")]
    s1 = _feedback(st, "2026-10-05", problems)
    s2 = _feedback(s1, "2026-10-05", problems, planned=False)
    assert len(s2["limit_log"]) == 1
    assert s2["limit_log"][0]["target_grade"] == "7B"
    assert _wl(s2)["next_target_grade"] == "7B+"


def test_reentry_problems_keep_the_base_until_closed():
    st = _state()  # Kilter 7B on 30/07 → re-entry on 05/10 (target 7A+)
    bt = _target(st, "2026-10-05")
    assert bt["target_grade"] == "7A+" and bt["target_source"] == "reentry"
    s1 = _feedback(st, "2026-10-05", [P("7B+", "sent"), P("7B", "sent")])
    e1 = next(e for e in s1["working_loads"]["entries"] if e["key"] == "limit_bouldering|surface=board_kilter")
    assert e1["next_target_grade"] == "7B"            # the base, never stepped during re-entry
    assert e1["reentry_exposures"] == 1
    assert s1["limit_log"][0]["step_reason"] == "reentry"
    assert _target(s1, "2026-10-08")["target_grade"] == "7A+"
    # Second session closes the re-entry: judged against the BASE (7B).
    s2 = _feedback(s1, "2026-10-08", [P("7B+", "sent")])
    assert _wl(s2)["next_target_grade"] == "7B+"
    assert s2["limit_log"][-1]["reference_grade"] == "7B"


def test_send_above_boulder_rp_is_only_proposed():
    st = _state()
    st["working_loads"]["entries"] = []
    out = _feedback(st, "2026-10-05", [P("7C+", "sent")], surface="gym_boulder", gym_id=WALL_GYM)
    assert out["assessment"]["grades"]["boulder_max_rp"] == "7C"
    assert out["limit_log"][0]["rp_proposal"] == {"grade": "7C+", "current": "7C"}
    # Board grades are never an RP proposal.
    st2 = _fresh_kilter_state("7B")
    out2 = _feedback(st2, "2026-10-05", [P("8A", "sent")])
    assert "rp_proposal" not in out2["limit_log"][0]


def test_custom_session_gets_the_plan_target_and_source_custom():
    st = _fresh_kilter_state("7B")
    t = limit_grade_target(st, "limit_bouldering", "2026-10-05")
    assert t["target_grade"] == "7B" and t["surface_selected"] == "board_kilter" and t["log_problems"] is True
    assert limit_grade_target(st, "max_hang_7s", "2026-10-05") is None
    out = _feedback(st, "2026-10-05", [P("7B+", "sent")], session_id="custom_cs_1", planned=False)
    entry = out["limit_log"][0]
    assert entry["source"] == "custom" and entry["target_grade"] == "7B"
    assert _wl(out)["next_target_grade"] == "7B+"
    gen = _feedback(st, "2026-10-05", [P("7B", "sent")], session_id="generated_body_parts_2026-10-05_evening", planned=False)
    assert gen["limit_log"][0]["source"] == "adhoc"


def test_inject_targets_flags_the_problem_logger():
    assert _target(_fresh_kilter_state(), "2026-10-05")["log_problems"] is True


def test_log_capped_and_ordered():
    st = {"limit_log": [{"date": f"2026-01-{(i % 28) + 1:02d}", "session_id": f"s{i}", "exercise_id": "x"} for i in range(205)]}
    limit_log.upsert_entry(st, {"date": "2026-10-05", "session_id": "new", "exercise_id": "x"})
    assert len(st["limit_log"]) == limit_log.LIMIT_LOG_CAP
    assert st["limit_log"][-1]["session_id"] == "new"


# ─── exposures + key-session dose ────────────────────────────────────────


def _custom_week_state(problems, target="7B"):
    st = _fresh_kilter_state(target)
    st["week_plans"] = {"2026-10-05": {"start_date": "2026-10-05", "weeks": [{"days": [
        {"date": "2026-10-06", "sessions": [{"session_id": "custom_cs_1", "is_custom": True, "status": "done",
                                             "exercises": [{"exercise_id": "limit_bouldering", "sets": 1}],
                                             "actual_exercises": [{"exercise_id": "limit_bouldering", "completed": True,
                                                                   "completed_sets": 1}]}]},
    ]}]}}
    st["limit_log"] = [{"date": "2026-10-06", "session_id": "custom_cs_1", "exercise_id": "limit_bouldering",
                        "surface": "board_kilter", "target_grade": target, "problems": problems, "source": "custom"}]
    return st


def _limit_req():
    return next(r for r in phase_requirements("strength_power") if r["key"] == "limit_power")


def test_custom_limit_counts_full_only_at_target():
    req = _limit_req()
    assert req["dose"] == "limit_log"
    good = _custom_week_state([P("7B", "sent"), P("7B+", "high_point")])
    s = good["week_plans"]["2026-10-05"]["weeks"][0]["days"][0]["sessions"][0]
    assert session_dose(good, s, "2026-10-06", req)["dose"] == "full"
    weak = _custom_week_state([P("6C", "sent"), P("7A", "sent")])
    s = weak["week_plans"]["2026-10-05"]["weeks"][0]["days"][0]["sessions"][0]
    d = session_dose(weak, s, "2026-10-06", req)
    assert d["dose"] == "partial" and d["reason"] == "limit_log_below_target"
    none = _custom_week_state([])
    s = none["week_plans"]["2026-10-05"]["weeks"][0]["days"][0]["sessions"][0]
    assert session_dose(none, s, "2026-10-06", req)["reason"] == "presence"


def test_catalog_limit_session_stays_full_on_presence():
    req = _limit_req()
    st = _custom_week_state([P("6C", "sent")])
    catalog_session = {"session_id": "limit_boulder_gym", "status": "done"}
    assert session_dose(st, catalog_session, "2026-10-06", req)["dose"] == "full"


def test_limit_log_is_a_fallback_exposure_source():
    st = _custom_week_state([P("7B", "sent")])
    st.pop("week_plans")
    rows = exposures(st, since="2026-10-01", until="2026-10-10", families=[FAMILY_LIMIT_POWER])
    assert [(r["date"], r["source"]) for r in rows] == [("2026-10-06", "limit_log")]
    # With the week plan present the derived row wins (no double count).
    st2 = _custom_week_state([P("7B", "sent")])
    rows2 = exposures(st2, since="2026-10-01", until="2026-10-10", families=[FAMILY_LIMIT_POWER])
    assert [r["source"] for r in rows2] == ["week_plan"]


def test_legacy_free_session_keeps_the_threshold_rule():
    """A free session finished before A296 (no ``limit_session`` stamp) is
    classified exactly as before: ≥ 2 climbs at RP − 2 steps."""
    st = _state()
    st["free_sessions"] = [{"id": "free_1", "date": "2026-10-03", "surface": "gym_boulder", "finished_at": "x",
                            "climbs": [{"grade": "7B", "status": "attempted", "attempts": 3},
                                       {"grade": "7B+", "status": "sent", "attempts": 2}]}]
    rows = exposures(st, since="2026-10-01", until="2026-10-10", families=[FAMILY_LIMIT_POWER])
    assert [(r["date"], r["source"]) for r in rows] == [("2026-10-03", "free")]


def test_stamped_free_session_counts_only_through_the_log():
    st = _state()
    fs = {"id": "free_1", "date": "2026-10-03", "surface": "gym_boulder", "finished_at": "x",
          "climbs": [{"grade": "7B", "status": "attempted", "attempts": 3},
                     {"grade": "7B+", "status": "sent", "attempts": 2}],
          "limit_session": {"counted": False, "reason": "below_threshold", "target_grade": "7C"}}
    st["free_sessions"] = [fs]
    assert exposures(st, since="2026-10-01", until="2026-10-10", families=[FAMILY_LIMIT_POWER]) == []
    # Still a finger-hard day (fatigue ≠ limit stimulus).
    assert [r["reason"] for r in finger_hard_days(st, since="2026-10-01", until="2026-10-10")] == ["free_limit"]
    st["limit_log"] = [{"date": "2026-10-03", "session_id": "free_1", "exercise_id": None, "surface": "gym_boulder",
                        "target_grade": "7C", "problems": [], "source": "free", "qualifying": 0}]
    rows = exposures(st, since="2026-10-01", until="2026-10-10", families=[FAMILY_LIMIT_POWER])
    assert [(r["date"], r["source"], r["session_id"]) for r in rows] == [("2026-10-03", "free", "free_1")]
    st["free_sessions"] = []  # deleted session: its log entry no longer counts
    assert exposures(st, since="2026-10-01", until="2026-10-10", families=[FAMILY_LIMIT_POWER]) == []


def test_free_session_decision():
    climbs = [{"grade": "7B", "status": "sent", "attempts": 3}, {"grade": "7B", "status": "attempted", "attempts": 4},
              {"grade": "6C", "status": "flash", "attempts": 1}]
    d = limit_log.free_session_decision(climbs, "board_kilter", "7B", toggled=False)
    assert d["counted"] and d["reason"] == "threshold" and d["qualifying"] == 2
    d2 = limit_log.free_session_decision(climbs, "board_kilter", "7B+", toggled=False)
    assert not d2["counted"] and d2["reason"] == "below_threshold"
    d3 = limit_log.free_session_decision(climbs, "board_kilter", "7B+", toggled=True)
    assert d3["counted"] and d3["reason"] == "toggle"


def test_limit_target_on_surface_matches_the_plan():
    st = _fresh_kilter_state("7B")
    assert limit_target_on_surface(st, "board_kilter", "2026-10-05") == _target(st, "2026-10-05")["target_grade"]
    assert limit_target_on_surface(st, "gym_routes", "2026-10-05") is None


# ─── API ─────────────────────────────────────────────────────────────────


@pytest.fixture
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage, storage_file
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
    yield tmp_state


def _seed_api(extra=None):
    state = deps.load_state(None)
    base = _fresh_kilter_state("7B")
    for k in ("assessment", "performance", "equipment", "working_loads", "bodyweight_kg"):
        state[k] = deepcopy(base[k])
    state["free_sessions"] = []
    state["limit_log"] = []
    state["stimulus_recency"] = {"marker": True}
    state.update(extra or {})
    deps.save_state(state, None)
    return state


def _run_free(climbs, toggle=None, day="2026-10-05"):
    r = client.post("/api/free-session/start", json={"date": day, "surface": "board_kilter",
                                                     "session_mode": "free", "context": "standalone"})
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    for c in climbs:
        assert client.post(f"/api/free-session/{sid}/log-climb", json=c).status_code == 200
    body = {"overall_feel": "hard"}
    if toggle is not None:
        body["is_limit_session"] = toggle
    r = client.post(f"/api/free-session/{sid}/finish", json=body)
    assert r.status_code == 200, r.text
    return sid, r.json()


def test_free_session_finish_writes_a_free_entry_and_nothing_else(isolate_state):
    before = _seed_api()
    sid, res = _run_free([{"grade": "7B", "status": "sent", "attempts": 3},
                          {"grade": "7B+", "status": "attempted", "attempts": 4}])
    assert res["limit_session"]["counted"] is True
    st = deps.load_state(None)
    [entry] = st["limit_log"]
    assert entry["source"] == "free" and entry["session_id"] == sid and entry["target_grade"] == "7B"
    assert st["stimulus_recency"] == before["stimulus_recency"]
    assert st["working_loads"] == before["working_loads"]
    # Deleting the free session removes its entry.
    assert client.delete(f"/api/free-session/{sid}").status_code == 200
    assert deps.load_state(None)["limit_log"] == []


def test_free_session_below_target_is_decided_but_not_logged(isolate_state):
    _seed_api()
    sid, res = _run_free([{"grade": "7A", "status": "sent", "attempts": 3},
                          {"grade": "7B", "status": "attempted", "attempts": 2}])
    assert res["limit_session"] == {"counted": False, "reason": "below_threshold", "target_grade": "7B",
                                    "qualifying": 1, "toggled": False}
    assert deps.load_state(None)["limit_log"] == []
    sid2, res2 = _run_free([{"grade": "6C", "status": "flash", "attempts": 1}], toggle=True)
    assert res2["limit_session"]["counted"] is True and res2["limit_session"]["reason"] == "toggle"
    assert [e["session_id"] for e in deps.load_state(None)["limit_log"]] == [sid2]


def test_put_state_cannot_write_the_limit_log(isolate_state):
    _seed_api({"limit_log": [{"date": "2026-10-01", "session_id": "x", "exercise_id": "limit_bouldering"}]})
    r = client.put("/api/state", json={"limit_log": []})
    assert r.status_code in (200, 400, 422)
    assert len(deps.load_state(None)["limit_log"]) == 1


def test_feedback_response_carries_the_limit_summary(isolate_state):
    _seed_api()
    r = client.post("/api/feedback", json={
        "log_entry": {"date": "2026-10-05", "session_id": "custom_cs_9", "feedback_contract": 2,
                      "actual": {"exercise_feedback_v1": [{
                          "exercise_id": "limit_bouldering", "completed": True, "surface_selected": "board_kilter",
                          "problems": [P("7B", "sent"), P("7B", "sent"), P("9Z", "sent")]}]}},
        "status": "done",
    })
    assert r.status_code == 200, r.text
    [summary] = r.json()["limit_summary"]
    assert summary["target_grade"] == "7B" and summary["next_target_grade"] == "7B+" and summary["step"] == 1
    st = deps.load_state(None)
    assert len(st["limit_log"][0]["problems"]) == 2  # the invalid row was dropped


def test_custom_session_read_with_date_carries_the_limit_target(isolate_state):
    _seed_api({"custom_sessions": [{"id": "cs_l", "name": "Limit", "tags": [],
                                    "exercises": [{"exercise_id": "limit_bouldering", "sets": 1},
                                                  {"exercise_id": "max_hang_7s", "sets": 5, "work_seconds": 7}]}]})
    r = client.get("/api/custom-session/cs_l?date=2026-10-05")
    assert r.status_code == 200, r.text
    ex = r.json()["exercises"]
    assert ex[0]["target_grade"] == "7B" and ex[0]["log_problems"] is True
    assert ex[0]["surface_selected"] == "board_kilter"
    assert "target_grade" not in ex[1]
    # Without a date nothing is computed (the builder edits what was saved).
    assert "target_grade" not in client.get("/api/custom-session/cs_l").json()["exercises"][0]


def test_limit_log_survives_week_regeneration():
    st = _fresh_kilter_state()
    st["limit_log"] = [{"date": "2026-09-28", "session_id": "limit_boulder_gym", "exercise_id": "limit_bouldering",
                        "surface": "board_kilter", "target_grade": "7B", "problems": [P("7B", "sent")], "source": "planned"}]
    st["week_plans"] = {"2020-01-06": {"x": 1}, (date.today() + timedelta(days=14)).isoformat(): {"y": 2}}
    before = deepcopy(st["limit_log"])
    deps.invalidate_week_cache(st)
    assert st["limit_log"] == before


def test_planned_target_ignored_when_the_athlete_switches_surface():
    """Planned on the Kilter (7B memory), climbed on the gym wall: the wall's
    own target (re-entry from the stale 7C anchor rules) is the reference."""
    st = _fresh_kilter_state("7B")
    wall_target = limit_target_on_surface(st, "gym_boulder", "2026-10-05")
    out = _feedback(st, "2026-10-05", [P("7B", "sent")], surface="gym_boulder")
    entry = out["limit_log"][0]
    assert entry["surface"] == "gym_boulder"
    assert entry["target_grade"] == wall_target
