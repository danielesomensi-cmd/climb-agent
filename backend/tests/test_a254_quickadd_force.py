"""A254 → A301 — quick-add `force` is a no-op compatibility flag.

A254 introduced `force=True` to keep a hard quick-add the reconcile would have
downshifted. A301 (guards are alerts, Daniele 2026-10-05): every quick-add is
applied as asked and NOTHING else in the week moves — not the added session,
not the engine's sessions next to it. What the guards object to comes back as
warnings. So `force` changes nothing: with or without it the plan is the same.
"""

from __future__ import annotations

from datetime import date, timedelta

from backend.engine.replanner_v1 import apply_day_add

FINGER = "finger_strength_home"        # hard + finger
HARD = "power_endurance_gym"           # hard, NOT finger
EASY = "regeneration_easy"
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _monday() -> str:
    d = date.today()
    return (d - timedelta(days=d.weekday())).isoformat()


def _plan(*, finger_on=(), hard_on=(), hard_cap=3, recovery_multiplier=1.0) -> dict:
    start = date.fromisoformat(_monday())
    days = []
    for i in range(7):
        entry = {"date": (start + timedelta(days=i)).isoformat(), "weekday": WEEKDAYS[i], "sessions": []}
        if i in finger_on:
            entry["sessions"].append({
                "session_id": FINGER, "slot": "evening", "location": "home",
                "phase_id": "base", "tags": {"hard": True, "finger": True},
            })
        if i in hard_on:
            entry["sessions"].append({
                "session_id": HARD, "slot": "evening", "location": "gym",
                "phase_id": "base", "tags": {"hard": True, "finger": False},
            })
        days.append(entry)
    return {
        "start_date": _monday(),
        "profile_snapshot": {"phase_id": "base", "discipline": "lead", "hard_cap_per_week": hard_cap, "recovery_multiplier": recovery_multiplier},
        "weeks": [{"phase": "base", "days": days}],
    }


def _sess(plan, day_index, slot="evening"):
    day = plan["weeks"][0]["days"][day_index]
    return next((s for s in day.get("sessions", []) if s.get("slot") == slot), None)


def _add(plan, session_id, day_index, *, force, slot="evening", location="home", prev_days=None):
    target = plan["weeks"][0]["days"][day_index]["date"]
    return apply_day_add(plan, session_id=session_id, target_date=target, slot=slot,
                         location=location, force=force, prev_days=prev_days)


# ── Finger gap ───────────────────────────────────────────────────────────


def _others_untouched(before: dict, after: dict, day_index: int, slot: str) -> None:
    """Every day but the target is byte-identical; on the target day only the
    added slot is new."""
    for i, (b, a) in enumerate(zip(before["weeks"][0]["days"], after["weeks"][0]["days"])):
        if i != day_index:
            assert a == b, f"day {i} was rewritten"
        else:
            assert [s for s in a["sessions"] if s.get("slot") != slot] == b["sessions"]


def test_finger_gap_is_an_alert_not_a_downshift():
    plan = _plan(finger_on=(0,))
    updated, warnings, adj = _add(plan, FINGER, 1, force=False)
    assert _sess(updated, 1)["session_id"] == FINGER
    assert adj == []
    assert any("finger" in w.lower() for w in warnings)
    _others_untouched(plan, updated, 1, "evening")


def test_force_is_a_noop():
    plan = _plan(finger_on=(0,))
    a, wa, adja = _add(plan, FINGER, 1, force=False)
    b, wb, adjb = _add(plan, FINGER, 1, force=True)
    assert a == b and wa == wb and adja == adjb == []
    tue = _sess(b, 1)
    assert tue.get("forced") is None
    assert "user_forced" not in tue["constraints_applied"]


def test_engine_finger_session_after_the_add_is_not_downshifted():
    """A Thursday finger session the engine planned stays finger even though the
    Tuesday add sits within its spacing gap (gap = 2 days): an alert, no rewrite."""
    plan = _plan(finger_on=(0, 3), recovery_multiplier=2.0)
    updated, warnings, adj = _add(plan, FINGER, 1, force=False)
    assert _sess(updated, 1)["session_id"] == FINGER
    assert _sess(updated, 3)["session_id"] == FINGER
    assert adj == []
    assert warnings
    _others_untouched(plan, updated, 1, "evening")


# ── Hard cap ─────────────────────────────────────────────────────────────


def test_hard_cap_is_an_alert_not_a_downshift():
    plan = _plan(hard_on=(0, 1), hard_cap=2)
    updated, warnings, adj = _add(plan, HARD, 3, force=False, location="gym")
    assert _sess(updated, 3)["session_id"] == HARD
    assert adj == []
    assert any("exceeds weekly cap" in w for w in warnings)
    _others_untouched(plan, updated, 3, "evening")


def test_over_cap_engine_days_are_not_eased_either():
    plan = _plan(hard_on=(0, 2), hard_cap=1)
    updated, _w, adj = _add(plan, HARD, 4, force=True, location="gym")
    assert [_sess(updated, i)["session_id"] for i in (0, 2, 4)] == [HARD, HARD, HARD]
    assert adj == []


# ── No-op safety ─────────────────────────────────────────────────────────


def test_unmarked_session():
    updated, _w, _adj = _add(_plan(), "prehab_maintenance", 2, force=False, slot="morning")
    sess = _sess(updated, 2, slot="morning")
    assert sess.get("forced") is None
    assert sess["constraints_applied"] == ["quick_add"]
