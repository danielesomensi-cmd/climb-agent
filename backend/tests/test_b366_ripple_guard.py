"""B366 — the recovery ripples never rewrite what the user owns.

Three paths ease the days after a hard load: quick-add (day+1), hard day
override (day+1 proportional, day+2 forced recovery) and a high-load completed
outdoor day (day+1). Before B366 each one checked only ``done/skipped``:

* a user-authored custom session (``is_custom``) or a user-forced one (A254)
  on the following day was silently replaced by complementary_conditioning /
  regeneration_easy — the same incoherent hybrid B345 removed from the
  reconcile enforcers;
* the quick-add / override ripple ran BEFORE ``_reconcile``, so when reconcile
  then downshifted the very session that triggered it (48h finger gap, hard
  cap) the following days had already been eased for a load no longer on the
  plan;
* nothing was reported: the rewrite was invisible to the caller.

Now: ``_is_rewritable`` guards every ripple, the ripple is kept only if the
triggering session survived reconciliation, and every rewrite is reported
(quick-add ``adjustments``; ``day_override`` / ``outdoor_ripple`` adaptations).
"""
from __future__ import annotations

import copy
from datetime import date, timedelta

from backend.engine.replanner_v1 import apply_day_add, apply_day_override, apply_events

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MONDAY = "2026-01-05"


def _d(i: int) -> str:
    return (date.fromisoformat(MONDAY) + timedelta(days=i)).isoformat()


def _plan(hard_cap: int = 4) -> dict:
    days = [
        {"date": _d(i), "weekday": WEEKDAYS[i], "sessions": []}
        for i in range(7)
    ]
    return {
        "start_date": MONDAY,
        "profile_snapshot": {
            "phase_id": "strength_power",
            "discipline": "lead",
            "hard_cap_per_week": hard_cap,
            "recovery_multiplier": 1.0,
        },
        "weeks": [{"phase": "strength_power", "days": days}],
        "adaptations": [],
    }


def _catalog(session_id: str, slot: str, *, hard: bool, finger: bool, intensity: str) -> dict:
    return {
        "session_id": session_id,
        "slot": slot,
        "location": "gym",
        "gym_id": "g1",
        "phase_id": "strength_power",
        "intensity": intensity,
        "tags": {"hard": hard, "finger": finger},
    }


def _custom(slot: str = "evening") -> dict:
    """A user-built hard session (custom sessions carry derived hard tags, B345)."""
    return {
        "session_id": "custom_cs_4abc6aed",
        "slot": slot,
        "location": "gym",
        "gym_id": "g1",
        "is_custom": True,
        "custom_session_id": "cs_4abc6aed",
        "intensity": "high",
        "tags": {"hard": True, "finger": False},
        "exercises": [{"exercise_id": "weighted_pullup", "sets": 4, "reps": 3, "load_kg": 28}],
    }


def _day(plan: dict, i: int) -> dict:
    return plan["weeks"][0]["days"][i]


def _put(plan: dict, i: int, *sessions: dict) -> None:
    _day(plan, i)["sessions"] = [copy.deepcopy(s) for s in sessions]


# ── quick-add ────────────────────────────────────────────────────────────────

class TestQuickAddRipple:
    def test_custom_on_next_day_is_never_rewritten(self):
        plan = _plan()
        _put(plan, 2, _custom("evening"),
             _catalog("technique_focus_gym", "morning", hard=False, finger=False, intensity="medium"))
        custom_before = copy.deepcopy(_custom("evening"))

        updated, _w, adjustments = apply_day_add(
            plan, session_id="power_endurance_gym", target_date=_d(1),
            slot="evening", location="gym",
        )

        wed = _day(updated, 2)["sessions"]
        custom_after = next(s for s in wed if s["slot"] == "evening")
        assert custom_after == custom_before, "custom session must stay byte-identical"
        assert custom_after["is_custom"] is True
        # The engine's own session on the same day is still eased …
        morning = next(s for s in wed if s["slot"] == "morning")
        assert morning["session_id"] == "regeneration_easy"
        # … and the rewrite is reported, never silent.
        ripple = [a for a in adjustments if a["reason"] == "quick_add_ripple"]
        assert ripple == [{
            "date": _d(2),
            "slot": "morning",
            "action": "downgraded",
            "reason": "quick_add_ripple",
            "previous_session_id": "technique_focus_gym",
            "session_id": "regeneration_easy",
        }]

    def test_forced_session_on_next_day_is_kept(self):
        plan = _plan()
        forced = {**_catalog("limit_boulder_gym", "evening", hard=True, finger=True, intensity="max"),
                  "forced": True, "constraints_applied": ["quick_add", "user_forced"]}
        _put(plan, 2, forced)

        updated, _w, adjustments = apply_day_add(
            plan, session_id="power_endurance_gym", target_date=_d(1),
            slot="evening", location="gym",
        )
        assert _day(updated, 2)["sessions"] == [forced]
        assert not [a for a in adjustments if a["reason"] == "quick_add_ripple"]

    def test_done_and_skipped_next_day_byte_identical(self):
        plan = _plan()
        done = {**_catalog("limit_boulder_gym", "morning", hard=True, finger=True, intensity="max"),
                "status": "done", "feedback": [{"exercise_id": "x", "difficulty": "ok"}]}
        skipped = {**_catalog("technique_focus_gym", "evening", hard=False, finger=False, intensity="medium"),
                   "status": "skipped"}
        _put(plan, 2, done, skipped)
        before = copy.deepcopy(_day(plan, 2)["sessions"])

        updated, _w, _adj = apply_day_add(
            plan, session_id="power_endurance_gym", target_date=_d(1),
            slot="evening", location="gym",
        )
        assert _day(updated, 2)["sessions"] == before

    def test_no_ripple_when_added_session_is_downshifted(self):
        """Finger Mon + finger quick-add Tue → Tue eased by reconcile, Wed untouched."""
        plan = _plan()
        _put(plan, 0, _catalog("finger_strength_home", "evening", hard=True, finger=True, intensity="high"))
        wed = _catalog("power_endurance_gym", "evening", hard=True, finger=False, intensity="high")
        _put(plan, 2, wed)

        updated, _w, adjustments = apply_day_add(
            plan, session_id="finger_strength_home", target_date=_d(1),
            slot="evening", location="home",
        )
        tue = _day(updated, 1)["sessions"][0]
        assert tue["session_id"] == "regeneration_easy"
        assert _day(updated, 2)["sessions"] == [wed], \
            "day+1 must not be eased for a session reconcile already removed"
        assert [a["reason"] for a in adjustments] == ["finger_spacing_downshift"]

    def test_ripple_still_relieves_the_hard_cap(self):
        """The ripple is applied before reconcile on the kept branch, so easing a
        hard day+1 still frees a cap slot — no extra downshift elsewhere."""
        plan = _plan(hard_cap=3)
        thu = _catalog("pulling_strength_gym", "evening", hard=True, finger=False, intensity="high")
        sat = _catalog("power_endurance_gym", "evening", hard=True, finger=False, intensity="high")
        sun = _catalog("pulling_strength_gym", "morning", hard=True, finger=False, intensity="high")
        _put(plan, 3, thu)
        _put(plan, 5, sat)
        _put(plan, 6, sun)

        updated, _w, adjustments = apply_day_add(
            plan, session_id="power_endurance_gym", target_date=_d(2),
            slot="evening", location="gym",
        )
        assert _day(updated, 2)["sessions"][0]["session_id"] == "power_endurance_gym"
        assert _day(updated, 3)["sessions"][0]["session_id"] == "complementary_conditioning"
        assert _day(updated, 5)["sessions"] == [sat]
        assert _day(updated, 6)["sessions"] == [sun]
        assert [a["reason"] for a in adjustments] == ["quick_add_ripple"]

    def test_adaptation_carries_ripple(self):
        plan = _plan()
        _put(plan, 2, _catalog("technique_focus_gym", "evening", hard=False, finger=False, intensity="medium"))
        updated, _w, adjustments = apply_day_add(
            plan, session_id="power_endurance_gym", target_date=_d(1),
            slot="morning", location="gym",
        )
        entry = next(a for a in updated["adaptations"] if a["type"] == "quick_add")
        assert entry["adjustments"] == adjustments
        assert adjustments and adjustments[-1]["reason"] == "quick_add_ripple"

    def test_deterministic(self):
        plan = _plan()
        _put(plan, 2, _custom("evening"),
             _catalog("technique_focus_gym", "morning", hard=False, finger=False, intensity="medium"))
        a = apply_day_add(plan, session_id="power_endurance_gym", target_date=_d(1),
                          slot="evening", location="gym")
        b = apply_day_add(plan, session_id="power_endurance_gym", target_date=_d(1),
                          slot="evening", location="gym")
        assert a == b


# ── day override ─────────────────────────────────────────────────────────────

class TestOverrideRipple:
    def _override(self, plan: dict, target_i: int = 1) -> dict:
        return apply_day_override(
            plan, intent="strength", location="home",
            reference_date=_d(target_i - 1), target_date=_d(target_i),
            phase_id="strength_power",
        )

    def test_custom_and_forced_kept_on_both_ripple_days(self):
        plan = _plan()
        forced = {**_catalog("power_endurance_gym", "evening", hard=True, finger=False, intensity="high"),
                  "forced": True}
        catalog_d2 = _catalog("technique_focus_gym", "morning", hard=False, finger=False, intensity="medium")
        _put(plan, 2, _custom("evening"))
        _put(plan, 3, forced, catalog_d2)

        updated = self._override(plan)
        assert "manual_override" in _day(updated, 1)["sessions"][0]["constraints_applied"]
        assert _day(updated, 2)["sessions"] == [_custom("evening")]
        thu = _day(updated, 3)["sessions"]
        assert next(s for s in thu if s["slot"] == "evening") == forced
        assert next(s for s in thu if s["slot"] == "morning")["session_id"] == "regeneration_easy"

        entry = next(a for a in updated["adaptations"] if a["type"] == "day_override")
        assert entry["adjustments"] == [{
            "date": _d(3),
            "slot": "morning",
            "action": "downgraded",
            "reason": "recovery_ripple",
            "previous_session_id": "technique_focus_gym",
            "session_id": "regeneration_easy",
        }]

    def test_no_ripple_when_override_is_downshifted(self):
        plan = _plan()
        _put(plan, 0, _catalog("finger_strength_home", "morning", hard=True, finger=True, intensity="high"))
        wed = _catalog("limit_boulder_gym", "evening", hard=True, finger=True, intensity="max")
        _put(plan, 2, wed)

        updated = self._override(plan)
        assert _day(updated, 1)["sessions"][0]["session_id"] == "regeneration_easy"
        assert _day(updated, 2)["sessions"] == [wed]
        entry = next(a for a in updated["adaptations"] if a["type"] == "day_override")
        assert entry["adjustments"] == []

    def test_done_ripple_days_byte_identical(self):
        plan = _plan()
        done = {**_catalog("limit_boulder_gym", "evening", hard=True, finger=True, intensity="max"),
                "status": "done", "completed_at": "2026-01-07T19:00:00"}
        _put(plan, 2, done)
        before = copy.deepcopy(_day(plan, 2)["sessions"])
        updated = self._override(plan)
        assert _day(updated, 2)["sessions"] == before


# ── outdoor ──────────────────────────────────────────────────────────────────

class TestOutdoorRipple:
    def _complete(self, plan: dict, load: int = 80) -> dict:
        _day(plan, 1)["outdoor_spot_name"] = "Berdorf"
        _day(plan, 1)["outdoor_session_status"] = "planned"
        return apply_events(plan, [{
            "event_type": "complete_outdoor", "date": _d(1), "outdoor_load_score": load,
        }])

    def test_custom_and_forced_kept_catalog_eased_and_reported(self):
        plan = _plan()
        forced = {**_catalog("technique_focus_gym", "lunch", hard=False, finger=False, intensity="medium"),
                  "forced": True}
        catalog = _catalog("limit_boulder_gym", "morning", hard=True, finger=True, intensity="max")
        _put(plan, 2, catalog, forced, _custom("evening"))

        updated = self._complete(plan)
        wed = {s["slot"]: s for s in _day(updated, 2)["sessions"]}
        assert wed["evening"] == _custom("evening")
        assert wed["lunch"] == forced
        assert wed["morning"]["session_id"] == "complementary_conditioning"

        entry = next(a for a in updated["adaptations"] if a["type"] == "outdoor_ripple")
        assert entry["date"] == _d(1)
        assert entry["adjustments"] == [{
            "date": _d(2),
            "slot": "morning",
            "action": "downgraded",
            "reason": "outdoor_ripple",
            "previous_session_id": "limit_boulder_gym",
            "session_id": "complementary_conditioning",
        }]

    def test_low_load_no_ripple_no_adaptation(self):
        plan = _plan()
        catalog = _catalog("limit_boulder_gym", "morning", hard=True, finger=True, intensity="max")
        _put(plan, 2, catalog)
        updated = self._complete(plan, load=30)
        assert _day(updated, 2)["sessions"] == [catalog]
        assert not [a for a in updated["adaptations"] if a["type"] == "outdoor_ripple"]

    def test_done_next_day_byte_identical(self):
        plan = _plan()
        done = {**_catalog("limit_boulder_gym", "evening", hard=True, finger=True, intensity="max"),
                "status": "done"}
        _put(plan, 2, done)
        before = copy.deepcopy(_day(plan, 2)["sessions"])
        updated = self._complete(plan)
        assert _day(updated, 2)["sessions"] == before
