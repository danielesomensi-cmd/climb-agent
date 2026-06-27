"""B268 — planned-but-not-done sessions feed recency across DIFFERENT days.

Bug: ``_auto_resolve`` resolved every session with the same recency snapshot
(completed sessions only), so the same session scheduled on consecutive days —
or twice — produced byte-identical exercises. The engine "only looked at the
past".

Fix: the week/replanner auto-resolve loops accumulate each day's resolved
exercise_ids and feed them, as recency, into the resolution of LATER days
(``resolve_session(extra_recent_ex_ids=...)``). Same-day siblings are NOT
cross-pollinated (decision: keep it simple — two identical sessions on one day
stay identical; only different days vary).
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.api.routers.week import _auto_resolve

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FIXTURE = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


def _state_with_band_gym():
    s = json.loads(STATE_FIXTURE.read_text(encoding="utf-8"))
    eq = s.setdefault("equipment", {})
    gyms = eq.setdefault("gyms", [])
    if not gyms:
        gyms.append({"gym_id": "g1", "name": "G", "equipment": []})
    g = gyms[0]
    g.setdefault("equipment", [])
    for e in ("resistance_band", "pullup_bar", "dumbbell"):
        if e not in g["equipment"]:
            g["equipment"].append(e)
    return s, g["gym_id"]


def _core_day(date: str, weekday: str, gym_id: str, n: int = 1):
    return {"date": date, "weekday": weekday, "sessions": [
        {"session_id": "core_training", "slot": "evening", "location": "gym", "gym_id": gym_id}
        for _ in range(n)
    ]}


def _anti_rotation(session_entry) -> str | None:
    rs = (session_entry.get("resolved") or {}).get("resolved_session", {})
    for i in rs.get("exercise_instances", []):
        if "anti_rotation" in str(i.get("block_uid", "")):
            return i.get("exercise_id")
    return None


def _mains(session_entry):
    rs = (session_entry.get("resolved") or {}).get("resolved_session", {})
    return [i.get("exercise_id") for i in rs.get("exercise_instances", [])
            if "inline" in str(i.get("block_uid", ""))]


# 1 — same session on DIFFERENT days varies
def test_core_varies_across_different_days():
    state, gid = _state_with_band_gym()
    wp = {"start_date": "2026-06-22", "weeks": [{"phase": "base", "days": [
        _core_day("2026-06-22", "mon", gid),
        _core_day("2026-06-24", "wed", gid),
    ]}]}
    _auto_resolve(wp, state, user_id=None, phase="base")
    days = wp["weeks"][0]["days"]
    mon = _anti_rotation(days[0]["sessions"][0])
    wed = _anti_rotation(days[1]["sessions"][0])
    assert mon is not None and wed is not None
    assert mon != wed, f"different days should vary, both picked {mon}"


# 2 — same session TWICE on the SAME day stays identical (decision: don't vary same-day)
def test_core_same_day_stays_identical():
    state, gid = _state_with_band_gym()
    wp = {"start_date": "2026-06-22", "weeks": [{"phase": "base", "days": [
        _core_day("2026-06-22", "mon", gid, n=2),
    ]}]}
    _auto_resolve(wp, state, user_id=None, phase="base")
    sessions = wp["weeks"][0]["days"][0]["sessions"]
    assert _mains(sessions[0]) == _mains(sessions[1])  # byte-identical, same day


# 3 — determinism: same state + same plan → same resolution on a re-run
def test_determinism_same_inputs():
    state, gid = _state_with_band_gym()
    base = {"start_date": "2026-06-22", "weeks": [{"phase": "base", "days": [
        _core_day("2026-06-22", "mon", gid),
        _core_day("2026-06-24", "wed", gid),
    ]}]}
    a = deepcopy(base); b = deepcopy(base)
    _auto_resolve(a, deepcopy(state), user_id=None, phase="base")
    _auto_resolve(b, deepcopy(state), user_id=None, phase="base")
    for da, db in zip(a["weeks"][0]["days"], b["weeks"][0]["days"]):
        assert _mains(da["sessions"][0]) == _mains(db["sessions"][0])


# 4 — completed sessions are never re-resolved (B120) and keep their exercises
def test_done_session_not_re_resolved():
    state, gid = _state_with_band_gym()
    cached = {"resolved_session": {"exercise_instances": [
        {"exercise_id": "sentinel_locked", "block_uid": "inline.anti_rotation"}]}}
    wp = {"start_date": "2026-06-22", "weeks": [{"phase": "base", "days": [
        {"date": "2026-06-22", "weekday": "mon", "sessions": [
            {"session_id": "core_training", "slot": "evening", "location": "gym",
             "gym_id": gid, "status": "done", "resolved": deepcopy(cached)}]},
        _core_day("2026-06-24", "wed", gid),
    ]}]}
    _auto_resolve(wp, state, user_id=None, phase="base")
    done_sess = wp["weeks"][0]["days"][0]["sessions"][0]
    assert done_sess["resolved"] == cached  # untouched (immutable)
