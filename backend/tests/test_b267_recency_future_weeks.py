"""B267 — recency window must look BACKWARD from the current week.

Bug: ``load_recent_exercise_ids`` took the N newest ``week_plans`` keys by date.
The hot store also holds PRE-GENERATED FUTURE weeks (status != done), so the
window saturated with future placeholders → recency came back empty → every
selection block fell to the alphabetical tie-break (e.g. anti_rotation always
``copenhagen_plank``, never ``pallof_press``). Silent variety-death.

Fix: drop weeks strictly after the current week (key > current_week_monday)
BEFORE selecting the top-N AND before deciding whether to consult the archive,
so the "< N hot weeks → read archive" decision counts PAST weeks only.

All tests pin an explicit ``reference_date`` so they are deterministic on every
calendar day (no reliance on date.today()).
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.engine import resolve_session
from backend.engine import storage
from backend.engine.resolve_session import (
    load_recent_exercise_ids,
    pick_best_exercise_p0,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXERCISES_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"
ALL_EXERCISES = json.loads(EXERCISES_PATH.read_text(encoding="utf-8"))["exercises"]

# Fixed reference: Friday 2026-06-26. Current week Monday = 2026-06-22.
REF = "2026-06-26"
CUR_MON = "2026-06-22"


def wk(offset_weeks: int) -> str:
    """ISO Monday `offset_weeks` from the current reference week (+ = future)."""
    d = date.fromisoformat(CUR_MON) + timedelta(weeks=offset_weeks)
    return d.isoformat()


def _week_plan(start_monday: str, exercise_id: str, status: str | None = "done") -> dict:
    """One-week plan with a single session on Monday carrying `exercise_id`."""
    sess = {
        "session_id": "core_training",
        "slot": "evening",
        "resolved": {"resolved_session": {"exercise_instances": [{"exercise_id": exercise_id}]}},
    }
    if status:
        sess["status"] = status
    return {"start_date": start_monday, "weeks": [{"phase": "base", "days": [
        {"date": start_monday, "weekday": "mon", "sessions": [sess]},
    ]}]}


# 1 — window selects recent PAST weeks, excludes pre-generated future weeks
def test_window_excludes_future_includes_recent_past():
    week_plans = {
        wk(+3): _week_plan(wk(+3), "future_ex"),   # future, even though status=done
        wk(+2): _week_plan(wk(+2), "future_ex"),
        wk(+1): _week_plan(wk(+1), "future_ex"),
        wk(0):  _week_plan(wk(0),  "ex_cur"),      # current week
        wk(-1): _week_plan(wk(-1), "ex_prev"),
        wk(-2): _week_plan(wk(-2), "ex_old"),
    }
    recent = load_recent_exercise_ids(None, user_state={"week_plans": week_plans}, reference_date=REF)
    assert recent == ["ex_old", "ex_prev", "ex_cur"]   # oldest → newest, 3-week window
    assert "future_ex" not in recent                   # future placeholders dropped


# 2 — future-saturation (Daniele's case): recency now non-empty → anti_rotation rotates
def test_future_saturation_rotates_copenhagen_to_pallof():
    # Many pre-generated future weeks + the just-completed core with copenhagen_plank.
    week_plans = {
        wk(+5): _week_plan(wk(+5), "front_lever"),
        wk(+4): _week_plan(wk(+4), "front_lever"),
        wk(+3): _week_plan(wk(+3), "front_lever"),
        wk(+2): _week_plan(wk(+2), "front_lever"),
        wk(+1): _week_plan(wk(+1), "front_lever"),
        wk(0):  _week_plan(wk(0),  "copenhagen_plank"),   # last completed anti_rotation
    }
    recent = load_recent_exercise_ids(None, user_state={"week_plans": week_plans}, reference_date=REF)
    assert "copenhagen_plank" in recent   # recency is alive despite 5 future weeks

    rgroups = set()
    by_id = {e["id"]: e for e in ALL_EXERCISES}
    for rid in recent:
        rg = (by_id.get(rid) or {}).get("recency_group")
        if rg:
            rgroups.add(rg)

    band_gym = ["resistance_band", "pullup_bar", "dumbbell"]
    picked, _ = pick_best_exercise_p0(
        exercises=ALL_EXERCISES, location="gym", available_equipment=band_gym,
        role_req=["accessory"], domain_req=["core"], pattern_req=["anti_rotation"],
        recent_ex_ids=recent, recent_recency_groups=rgroups,
    )
    # copenhagen is now recency-penalised → the block rotates to pallof_press.
    assert (picked or {}).get("id") == "pallof_press"


# 3 — determinism: same state + same reference_date → byte-identical list
def test_determinism_same_inputs_same_output():
    week_plans = {
        wk(+1): _week_plan(wk(+1), "future_ex"),
        wk(0):  _week_plan(wk(0),  "ex_cur"),
        wk(-1): _week_plan(wk(-1), "ex_prev"),
    }
    state = {"week_plans": week_plans}
    a = load_recent_exercise_ids(None, user_state=state, reference_date=REF)
    b = load_recent_exercise_ids(None, user_state=state, reference_date=REF)
    assert a == b
    assert a == ["ex_prev", "ex_cur"]


# 4 — immutability: reading recency never mutates the input state
def test_recency_load_does_not_mutate_state():
    state = {"week_plans": {
        wk(+1): _week_plan(wk(+1), "future_ex"),
        wk(0):  _week_plan(wk(0),  "ex_cur"),
        wk(-1): _week_plan(wk(-1), "ex_prev"),
    }}
    snapshot = json.dumps(state, sort_keys=True)
    load_recent_exercise_ids(None, user_state=state, reference_date=REF)
    assert json.dumps(state, sort_keys=True) == snapshot


# 5 — archive decision counts PAST weeks only (req #1): few past + many future → archive read
def test_archive_consulted_counts_past_weeks_only(monkeypatch):
    # Only ONE past week in hot; FOUR future placeholders would have saturated
    # the old top-N window and skipped the archive.
    week_plans = {
        wk(+4): _week_plan(wk(+4), "future_ex"),
        wk(+3): _week_plan(wk(+3), "future_ex"),
        wk(+2): _week_plan(wk(+2), "future_ex"),
        wk(+1): _week_plan(wk(+1), "future_ex"),
        wk(0):  _week_plan(wk(0),  "ex_cur"),
    }
    archive = {
        wk(-1): _week_plan(wk(-1), "ex_prev"),
        wk(-2): _week_plan(wk(-2), "ex_old"),
    }
    monkeypatch.setattr(storage, "list_archived_keys", lambda uid: list(archive.keys()))
    monkeypatch.setattr(storage, "read_archived_week", lambda uid, k: archive.get(k))

    recent = load_recent_exercise_ids("user-x", user_state={"week_plans": week_plans}, reference_date=REF)
    # window filled from archive (past only), future placeholders excluded
    assert recent == ["ex_old", "ex_prev", "ex_cur"]
    assert "future_ex" not in recent


# 6 — byte-identity: completed past sessions are not rewritten by the recency read (req #2)
def test_completed_sessions_byte_identical_after_recency_read():
    completed = {
        wk(0):  _week_plan(wk(0),  "copenhagen_plank"),
        wk(-1): _week_plan(wk(-1), "pallof_press"),
    }
    state = {"week_plans": {
        wk(+1): _week_plan(wk(+1), "future_ex"),
        **completed,
    }}
    before = {k: json.dumps(state["week_plans"][k], sort_keys=True) for k in completed}
    load_recent_exercise_ids(None, user_state=state, reference_date=REF)
    after = {k: json.dumps(state["week_plans"][k], sort_keys=True) for k in completed}
    for k in completed:
        assert after[k] == before[k], f"completed week {k} was mutated (zero-diff invariant broken)"
