"""A254 — quick-add `force`: keep the hard session at the user's own risk.

`force=True` pins the just-added session so the reconcile enforcers skip
downshifting IT — but ONLY it: the rest of the week still reconciles, and a
forced finger session still anchors the following days' 48h spacing (the injury
clock runs whether or not the session was forced). Default `force=False` is
byte-identical to today (the 102 existing replanner tests prove that).
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


def test_baseline_finger_downshifts_without_force():
    """Contrast: the Tuesday finger session is eased when NOT forced."""
    updated, _w, adj = _add(_plan(finger_on=(0,)), FINGER, 1, force=False)
    assert _sess(updated, 1)["session_id"] == EASY
    assert any(a["reason"] == "finger_spacing_downshift" for a in adj)


def test_force_keeps_the_finger_session():
    updated, _w, adj = _add(_plan(finger_on=(0,)), FINGER, 1, force=True)
    tue = _sess(updated, 1)
    assert tue["session_id"] == FINGER, "forced finger session must survive"
    assert tue.get("forced") is True
    assert "user_forced" in tue["constraints_applied"]
    assert not any(a["date"] == tue and a["reason"] == "finger_spacing_downshift" for a in adj)


def test_forced_finger_still_anchors_following_days():
    """SAFETY: a forced finger session still constrains later days — the tendons
    don't care that it was forced.

    Uses recovery_multiplier=2 (gap=2 days) and a Thursday finger session, which
    the day+1 ripple never touches (ripple only hits Wednesday). So the ONLY thing
    that can ease Thursday is the forced Tuesday acting as the spacing anchor."""
    plan = _plan(finger_on=(0, 3), recovery_multiplier=2.0)  # Monday + Thursday finger
    updated, _w, adj = _add(plan, FINGER, 1, force=True)      # force Tuesday
    assert _sess(updated, 1)["session_id"] == FINGER, "Tuesday forced survives"
    assert _sess(updated, 3)["session_id"] == EASY, \
        "Thursday must still be eased — forced Tuesday anchors the 48h gap"
    thu = updated["weeks"][0]["days"][3]["date"]
    assert any(a["date"] == thu and a["reason"] == "finger_spacing_downshift" for a in adj)


def test_forced_session_anchors_even_when_a_sibling_is_downshifted():
    """The anchor-guard edit: on a day where a NON-forced finger session IS
    downshifted, a forced sibling must still make the day a spacing anchor.
    Without the `or forced` guard the day stops anchoring and a later finger
    session (Thursday) would wrongly sail through the gap."""
    plan = _plan(finger_on=(0, 1, 3), recovery_multiplier=2.0)  # Mon, Tue(evening), Thu
    # Force-add a second finger session on Tuesday MORNING (sibling of the
    # planned Tuesday-evening one, which will be downshifted off the Monday gap).
    updated, _w, _adj = _add(plan, FINGER, 1, force=True, slot="morning")
    assert _sess(updated, 1, slot="morning")["session_id"] == FINGER, "forced Tue-morning survives"
    assert _sess(updated, 1, slot="evening")["session_id"] == EASY, "planned Tue-evening eased off Monday"
    assert _sess(updated, 3)["session_id"] == EASY, \
        "Thursday must still be eased — the forced Tuesday keeps the day an anchor"


# ── Hard cap ─────────────────────────────────────────────────────────────


def test_baseline_cap_downshifts_without_force():
    updated, _w, adj = _add(_plan(hard_on=(0, 1), hard_cap=2), HARD, 3, force=False, location="gym")
    assert _sess(updated, 3)["session_id"] == EASY
    assert any(a["reason"] == "hard_cap_downshift" for a in adj)


def test_force_keeps_hard_session_past_cap():
    updated, _w, adj = _add(_plan(hard_on=(0, 1), hard_cap=2), HARD, 3, force=True, location="gym")
    thu = _sess(updated, 3)
    assert thu["session_id"] == HARD, "forced hard session survives past the cap"
    assert thu.get("forced") is True
    assert not any(a["reason"] == "hard_cap_downshift" for a in adj)


def test_force_protects_only_the_forced_session():
    """A forced hard session on an over-cap day is kept, but OTHER over-cap hard
    days the user did not force still get reconciled."""
    # cap=1; Monday + Wednesday already hard, then force a Friday hard session.
    plan = _plan(hard_on=(0, 2), hard_cap=1)
    updated, _w, _adj = _add(plan, HARD, 4, force=True, location="gym")
    assert _sess(updated, 4)["session_id"] == HARD, "forced Friday survives"
    # At least one of the non-forced over-cap hard days was downshifted.
    non_forced_ids = [_sess(updated, i)["session_id"] for i in (0, 2)]
    assert EASY in non_forced_ids, "a non-forced over-cap hard day must still be eased"


# ── No-op safety ─────────────────────────────────────────────────────────


def test_force_false_is_unmarked():
    updated, _w, _adj = _add(_plan(), "prehab_maintenance", 2, force=False, slot="morning")
    sess = _sess(updated, 2, slot="morning")
    assert sess.get("forced") is None
    assert "user_forced" not in sess["constraints_applied"]
