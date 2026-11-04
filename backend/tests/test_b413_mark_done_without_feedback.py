"""B413 (D3) — a session marked done with no feedback counts as "ok" on the ladders.

Before B413 a "done" with no feedback (the /today tick, or the dialog closed
without sending) never reached the closed loop: the ladder did not step and
its date did not move (19 of Daniele's ladder rows since July; the R11
re-entry clock kept running on a family he trained).

Now ``POST /api/replanner/events`` passes the ladder rows of the FROZEN
prescription (D2) through ``bw_progression.apply_bw_item`` as done, unrated
rows — an "ok" (A1). A later feedback of the same session replays from the
per-session ``_prev`` snapshot (no double count); the undo of the "done"
puts the ladder back when nothing moved it since. Loads, grades and measures
are untouched; an untested athlete is untouched.
"""

from __future__ import annotations

import copy
import json
from datetime import timedelta

from backend.api import deps
from backend.api.routers import replanner as replanner_router
from backend.engine import bw_progression as bp
from backend.tests.test_b413_freeze_prescription import (  # noqa: F401 (isolate: autouse fixture)
    HDR,
    MON,
    MON_ISO,
    PLANK_3X20,
    SID,
    UID,
    _core,
    _custom,
    _events,
    _get,
    _guided_feedback,
    _lateral_rows,
    _mark_done,
    _session,
    _state,
    _stored,
    _week,
    client,
    isolate,
)

KEY = f"{MON_ISO}|{SID}"


def _lateral(target: int, top_streak: int = 0) -> dict:
    return {"level_idx": 2, "target": target, "sets": 3, "top_streak": top_streak, "source": "feedback"}


def _seed(**kw) -> dict:
    st = _state(**kw)
    deps.save_state(st, UID)
    return st


def _entry(family: str = "lateral") -> dict:
    return deps.load_state(UID)["bw_progression"].get(family)


def _core_of(e: dict) -> tuple:
    return (e["exercise_id"], e["level_idx"], e["sets"], e["target"], e["top_streak"], e.get("last_session_date"))


def _undo(sid: str = SID):
    return _events(_get()["week_plan"], [{"event_type": "mark_planned", "date": MON_ISO, "session_ref": sid}])


def test_mark_done_applies_ladder_rows_as_unrated():
    # In the band: Copenhagen plank 3x15 s shown, frozen, then +1 step (ok).
    _seed(lateral=_lateral(15))
    assert _lateral_rows(_session(_get()["week_plan"])["resolved"]) == [("copenhagen_plank", 3, 15, None)]
    r = _mark_done(_get()["week_plan"])
    assert r.status_code == 200, r.text
    assert _lateral_rows(_stored()["resolved"]) == [("copenhagen_plank", 3, 15, None)]
    e = _entry()
    assert _core_of(e) == ("copenhagen_plank", 2, 3, 20, 0, MON_ISO)
    assert e["last_outcome"]["kind"] == "step_up" and e["_prev"]["session_key"] == KEY
    assert e["_prev"]["entry"]["target"] == 15

    # 03/11: at the top with one session there already — the record stays the
    # Copenhagen plank 3x20 s that was shown, the ladder promotes (engine row).
    _seed()
    r = _mark_done(_get()["week_plan"])
    assert r.status_code == 200, r.text
    assert _lateral_rows(_stored()["resolved"]) == PLANK_3X20
    e = _entry()
    assert (e["exercise_id"], e["level_idx"], e["last_outcome"]["kind"]) == ("copenhagen_dynamic", 3, "promoted")

    # A custom 'ladder' row: the dose shown, then +1 step.
    st = _state(this_week={0: [_custom()]})
    st["bw_progression"]["posterior_chain"] = {"level_idx": 1, "target": 10, "sets": 3, "source": "feedback",
                                               "last_session_date": (MON - timedelta(days=3)).isoformat()}
    deps.save_state(st, UID)
    assert _session(_get()["week_plan"], "custom_cs_core")["exercises"][0]["reps"] == 10
    r = _mark_done(_get()["week_plan"], sid="custom_cs_core")
    assert r.status_code == 200, r.text
    assert _stored("custom_cs_core")["exercises"][0]["reps"] == 10  # the frozen custom row
    e = _entry("posterior_chain")
    assert (e["target"], e["last_outcome"]["kind"], e["_prev"]["session_key"]) == (
        11, "step_up", f"{MON_ISO}|custom_cs_core")

    # Untested: the ladders are neither read nor written.
    st = _state(tested=False, this_week={0: [_core(), _custom()]})
    deps.save_state(st, UID)
    want = json.dumps(st["bw_progression"], sort_keys=True)
    plan = _get()["week_plan"]
    assert _lateral_rows(_session(plan)["resolved"]) == []
    r = _events(plan, [{"event_type": "mark_done", "date": MON_ISO, "session_ref": SID},
                       {"event_type": "mark_done", "date": MON_ISO, "session_ref": "custom_cs_core"}])
    assert r.status_code == 200, r.text
    assert json.dumps(deps.load_state(UID)["bw_progression"], sort_keys=True) == want


def test_mark_done_twice_counts_once():
    _seed(lateral=_lateral(10))
    assert _mark_done(_get()["week_plan"]).status_code == 200
    first = _entry()
    assert _mark_done(_get()["week_plan"]).status_code == 200  # already done: not a transition
    assert _entry() == first and first["target"] == 15


def test_feedback_after_mark_done_replays_from_prev():
    _seed(lateral=_lateral(10))
    assert _mark_done(_get()["week_plan"]).status_code == 200
    assert _entry()["target"] == 15
    row = {"exercise_id": "copenhagen_plank", "completed": True, "completed_sets": 3, "bw_ladder": "engine"}
    # An unrated feedback of the same session: still one "ok" (no double count).
    assert _guided_feedback([dict(row)]).status_code == 200
    assert _entry()["target"] == 15
    # "easy": +2 steps from the snapshot before the session (10), not from 15.
    assert _guided_feedback([dict(row, feedback_label="easy")]).status_code == 200
    e = _entry()
    assert (e["target"], e["_prev"]["entry"]["target"], e["last_outcome"]["kind"]) == (20, 10, "step_up")
    # The row was not done after all: back to the snapshot.
    r = _guided_feedback([{"exercise_id": "copenhagen_plank", "completed": False, "bw_ladder": "engine"}])
    assert r.status_code == 200, r.text
    e = _entry()
    assert _core_of(e) == ("copenhagen_plank", 2, 3, 10, 0, (MON - timedelta(days=5)).isoformat())
    assert "_prev" not in e


def test_undo_restores_the_ladder_if_unchanged():
    # A persisted entry: back to what it was.
    _seed(lateral=_lateral(10))
    before = _core_of(bp._normalize(dict(_state(lateral=_lateral(10))["bw_progression"]["lateral"]),
                                    bp.family_doc("lateral")))
    assert _mark_done(_get()["week_plan"]).status_code == 200
    assert _entry()["target"] == 15
    assert _undo().status_code == 200
    assert "status" not in _stored()
    assert _core_of(_entry()) == before

    # A read-time seed (no persisted entry): the entry goes, the seed is back.
    st = _state()
    st["bw_progression"] = {}
    prev = MON - timedelta(weeks=1)
    st["week_plans"][prev.isoformat()] = _week(prev, {2: [{
        "slot": "lunch", "session_id": "custom_cs_old", "is_custom": True, "status": "done",
        "exercises": [{"exercise_id": "copenhagen_plank", "sets": 3, "work_seconds": 10}],
        "actual_exercises": [{"exercise_id": "copenhagen_plank", "completed": True, "completed_sets": 3,
                              "feedback_label": "ok"}]}]})
    deps.save_state(st, UID)
    seeded = bp.entries_for(deps.load_state(UID), MON_ISO)["lateral"]
    assert (seeded["source"], seeded["target"]) == ("seed_history", 15)
    assert _mark_done(_get()["week_plan"]).status_code == 200
    assert _entry()["target"] == 20
    assert _undo().status_code == 200
    assert "lateral" not in deps.load_state(UID)["bw_progression"]
    assert bp.entries_for(deps.load_state(UID), MON_ISO)["lateral"] == seeded

    # Moved in the meantime (a settings edit): the undo leaves it alone.
    _seed(lateral=_lateral(10))
    assert _mark_done(_get()["week_plan"]).status_code == 200
    r = client.put("/api/bw-progression/lateral", headers=HDR, json={"level_idx": 1, "date": MON_ISO})
    assert r.status_code == 200, r.text
    edited = _entry()
    assert _undo().status_code == 200
    assert _entry() == edited and edited["source"] == "user_edit"

    # Undone and marked again in the same call: still done, counted once.
    _seed(lateral=_lateral(10))
    assert _mark_done(_get()["week_plan"]).status_code == 200
    r = _events(_get()["week_plan"], [{"event_type": "mark_planned", "date": MON_ISO, "session_ref": SID},
                                      {"event_type": "mark_done", "date": MON_ISO, "session_ref": SID}])
    assert r.status_code == 200, r.text
    assert _stored()["status"] == "done" and _entry()["target"] == 15


def test_loads_untouched_by_mark_done(monkeypatch):
    """The ladder step is the ONLY thing a "done" without feedback adds: the
    same request with the step switched off differs in ``bw_progression``
    alone — working loads, anchored memories, grades, exposures untouched."""
    st0 = _state(this_week={0: [_core(), _custom()]})
    st0["bw_progression"]["posterior_chain"] = {"level_idx": 1, "target": 10, "sets": 3, "source": "feedback",
                                                "last_session_date": (MON - timedelta(days=3)).isoformat()}
    st0["working_loads"] = {"entries": [
        {"exercise_id": "back_extension", "next_external_load_kg": 10.0, "updated_at": MON_ISO},
        {"exercise_id": "goblet_squat", "next_external_load_kg": 16.0, "updated_at": MON_ISO}], "rules": {}}
    events = [{"event_type": "mark_done", "date": MON_ISO, "session_ref": SID},
              {"event_type": "mark_done", "date": MON_ISO, "session_ref": "custom_cs_core"}]

    real = replanner_router._ladders_on_done_without_feedback

    def run(step: bool) -> dict:
        deps.save_state(copy.deepcopy(st0), UID)
        # (never monkeypatch.undo(): it would also undo the storage isolation)
        monkeypatch.setattr(replanner_router, "_ladders_on_done_without_feedback",
                            real if step else (lambda *a, **k: None))
        r = _events(_get()["week_plan"], copy.deepcopy(events))
        assert r.status_code == 200, r.text
        return deps.load_state(UID)

    with_step, without = run(True), run(False)

    def scrub(obj):
        if isinstance(obj, dict):
            return {k: scrub(v) for k, v in obj.items() if k != "bw_progression" and not k.endswith("_at")
                    and k != "generated_at"}
        if isinstance(obj, list):
            return [scrub(v) for v in obj]
        return obj

    assert scrub(with_step) == scrub(without)
    assert with_step["working_loads"] == st0["working_loads"]
    assert with_step["bw_progression"] != without["bw_progression"]
    assert with_step["bw_progression"]["lateral"]["level_idx"] == 3  # 03/11: promoted
    assert with_step["bw_progression"]["posterior_chain"]["target"] == 11
    assert without["bw_progression"] == st0["bw_progression"]
