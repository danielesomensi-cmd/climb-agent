"""B375: GET /api/week persists the resolution of played sessions — once.

Before B375 ``_cache_completed_resolved`` compared the plan with itself: on a
cache hit ``week_plan`` IS ``state['week_plans'][key]``, ``_auto_resolve`` had
already filled ``resolved`` into that same object, so "cached lacks resolved"
was always false and nothing was ever saved. Every done/skipped session without
a stored ``resolved`` was re-resolved against TODAY's state on every read
(against B120) and paid extra storage reads each time.
"""

from __future__ import annotations

from copy import deepcopy

from backend.api import deps
from backend.api.routers import week as week_router
from backend.tests.test_week_rollover_B216 import (  # noqa: F401 (fixture)
    _prev_monday,
    _seed_rollover_state,
    _this_monday,
    client,
    isolate_state,
)

_STUB_RESOLVED = {"resolved_session": {"exercise_instances": [
    {"exercise_id": "pullup_weighted", "prescription": {"load_kg": 20}},
]}}


def _plan(start: str) -> dict:
    from datetime import date, timedelta

    days = []
    d0 = date.fromisoformat(start)
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    for i in range(7):
        days.append({"date": (d0 + timedelta(days=i)).isoformat(), "weekday": names[i], "sessions": []})
    # done, never resolved in storage, with feedback + timestamps
    days[0]["sessions"].append({
        "session_id": "prehab_maintenance", "slot": "evening", "location": "home",
        "status": "done", "completed_at": f"{days[0]['date']}T19:30:00",
        "feedback_summary": "ok", "exercise_feedback": [{"exercise_id": "x", "rating": "ok"}],
    })
    # skipped, never resolved in storage
    days[1]["sessions"].append({
        "session_id": "finger_maintenance_home", "slot": "evening", "location": "home",
        "status": "skipped", "skipped_at": f"{days[1]['date']}T08:00:00",
    })
    # done WITH a stored resolution: must stay byte-identical
    days[2]["sessions"].append({
        "session_id": "strength_long", "slot": "evening", "location": "home",
        "status": "done", "resolved": deepcopy(_STUB_RESOLVED),
    })
    # planned: resolved at read, never persisted by this path
    days[3]["sessions"].append({
        "session_id": "prehab_maintenance", "slot": "evening", "location": "home",
    })
    return {"start_date": start, "weeks": [{"phase": "base", "days": days}]}


def _seed() -> str:
    this_mon = _this_monday()
    _seed_rollover_state(
        legacy_start=this_mon,
        week_plans={this_mon: _plan(this_mon)},
        mc_start=_prev_monday(),
    )
    return this_mon


def _sessions(plan: dict) -> list:
    return [s for d in plan["weeks"][0]["days"] for s in d.get("sessions", [])]


def _spy_resolve(monkeypatch) -> list:
    calls: list = []
    orig = week_router.resolve_session

    def spy(*a, **k):
        calls.append(k.get("session_path"))
        return orig(*a, **k)

    monkeypatch.setattr(week_router, "resolve_session", spy)
    return calls


def test_first_get_persists_resolved_of_played_sessions():
    this_mon = _seed()
    r = client.get("/api/week/0")
    assert r.status_code == 200, r.text

    stored = deps.load_state(None)
    for plan in (stored["week_plans"][this_mon], stored["current_week_plan"]):
        done, skipped, done_cached, planned = _sessions(plan)
        assert done.get("resolved"), "done session resolution not persisted"
        assert skipped.get("resolved"), "skipped session resolution not persisted"
        assert done_cached["resolved"] == _STUB_RESOLVED
        # planned sessions are resolved at read only — never stored by B375
        assert "resolved" not in planned

    served = _sessions(r.json()["week_plan"])
    stored_done = _sessions(stored["week_plans"][this_mon])[0]
    assert served[0]["resolved"] == stored_done["resolved"]


def test_second_get_does_not_re_resolve_played_sessions(monkeypatch):
    _seed()
    calls = _spy_resolve(monkeypatch)
    assert client.get("/api/week/0").status_code == 200
    first = list(calls)
    # done + skipped (unresolved) + planned → 3 resolutions on the first read
    assert len(first) == 3, first

    calls.clear()
    saves: list = []
    orig_save = week_router.save_state
    monkeypatch.setattr(week_router, "save_state", lambda *a, **k: saves.append(1) or orig_save(*a, **k))
    assert client.get("/api/week/0").status_code == 200
    # only the planned session is resolved again; nothing is saved
    assert calls == ["backend/catalog/sessions/v1/prehab_maintenance.json"], calls
    assert saves == []


def test_played_sessions_otherwise_unchanged():
    this_mon = _seed()
    before = _sessions(deepcopy(deps.load_state(None)["week_plans"][this_mon]))
    client.get("/api/week/0")
    after = _sessions(deps.load_state(None)["week_plans"][this_mon])

    for b, a in zip(before[:3], after[:3]):
        a = {k: v for k, v in a.items() if k != "resolved"}
        b = {k: v for k, v in b.items() if k != "resolved"}
        assert a == b, "B375 may only add `resolved` to a played session"
    assert after[2]["resolved"] == _STUB_RESOLVED

    # A later state change (device switch) never rewrites the stored resolution.
    snap = deepcopy(after[0]["resolved"])
    state = deps.load_state(None)
    state.setdefault("preferences", {})["finger_training_device"] = "loading_pin"
    deps.save_state(state, None)
    client.get("/api/week/0")
    assert _sessions(deps.load_state(None)["week_plans"][this_mon])[0]["resolved"] == snap


def test_planned_sessions_resolved_every_read():
    _seed()
    for _ in range(2):
        r = client.get("/api/week/0")
        planned = _sessions(r.json()["week_plan"])[3]
        assert planned.get("resolved"), "planned session must still be resolved inline"


def test_concurrent_write_is_not_lost(monkeypatch):
    """The persist reloads the state under the user lock: a write landing while
    the GET resolves survives."""
    this_mon = _seed()
    orig = week_router._auto_resolve

    def racing(*a, **k):
        st = deps.load_state(None)
        st["_b375_marker"] = "written-meanwhile"
        deps.save_state(st, None)
        return orig(*a, **k)

    monkeypatch.setattr(week_router, "_auto_resolve", racing)
    assert client.get("/api/week/0").status_code == 200
    stored = deps.load_state(None)
    assert stored.get("_b375_marker") == "written-meanwhile"
    assert _sessions(stored["week_plans"][this_mon])[0].get("resolved")


def test_session_changed_meanwhile_is_not_patched(monkeypatch):
    """A session undone (back to planned) while the GET was resolving must not
    receive the played resolution."""
    this_mon = _seed()
    orig = week_router._auto_resolve

    def racing(*a, **k):
        st = deps.load_state(None)
        _sessions(st["week_plans"][this_mon])[0].pop("status")
        deps.save_state(st, None)
        return orig(*a, **k)

    monkeypatch.setattr(week_router, "_auto_resolve", racing)
    assert client.get("/api/week/0").status_code == 200
    stored = _sessions(deps.load_state(None)["week_plans"][this_mon])
    assert "resolved" not in stored[0]
    assert stored[1].get("resolved")  # the skipped one is still patched


def test_persist_failure_still_serves_plan(monkeypatch):
    _seed()

    def boom(*a, **k):
        raise RuntimeError("statement timeout")

    monkeypatch.setattr(week_router, "save_state", boom)
    r = client.get("/api/week/0")
    assert r.status_code == 200, r.text
    assert _sessions(r.json()["week_plan"])[0].get("resolved")
