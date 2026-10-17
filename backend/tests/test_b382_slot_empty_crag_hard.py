"""B382 — "I took a session out" = that slot stays empty; a declared crag day
is one of the week's hard, finger-loading days.

Decided by Daniele on 2026-10-17 (Phase 1 in the session scratchpad):

(a) The app's ``remove_session`` carries the session id only. Before B382 the
    merge dropped a removed engine session by id, so a regeneration that put a
    DIFFERENT id in the same slot filled the slot the user had emptied (prod
    mirror, week of 19/10: Thursday evening's max-hang test removed →
    ``lead_tryhard_gym`` there after the regeneration). ``apply_events`` now
    records the slot the session sat in (``removed_slot``) and whether it was
    the user's own (``removed_owned``); the planner treats an emptied slot as
    unavailable and the merge keeps it empty.
    - D1 (yes): the removed session may land on another day of the week.
    - D2 (yes): ``remove_outdoor`` gives the day back to the engine — the
      removals made before the outdoor was added are cancelled.
(b) The planner counts a declared crag day (this week, done or not past; the
    previous week's for the spacing) in the hard-day cap and in the hard /
    finger gaps, as the alerts (guards_v1, B372) already did.

Fixtures are synthetic (no real user state in the repo).
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, timedelta

from backend.engine import user_owned as uo
from backend.engine.replanner_v1 import apply_events, regenerate_preserving_completed
from backend.tests.test_a300_complementary_slots import PREFS, days_of, plan

START = "2026-10-12"  # Monday
MON, TUE, WED, THU, FRI, SAT, SUN = (
    (date.fromisoformat(START) + timedelta(days=i)).isoformat() for i in range(7)
)
PHASE = "strength_power"


def _day(wp, d_iso):
    return next(d for d in days_of(wp) if d["date"] == d_iso)


def _slot(wp, d_iso, slot):
    return next((s for s in _day(wp, d_iso).get("sessions") or [] if s.get("slot") == slot), None)


def _fp(wp):
    p = json.loads(json.dumps(wp))
    p.pop("generated_at", None)
    return json.dumps(p, sort_keys=True)


def _regen(old, today, *, prefs=None, **kw):
    """The GET /api/week force path: plan with existing_week_plan, then merge."""
    new = plan(PHASE, today=today, existing_week_plan=deepcopy(old), prefs=prefs, **kw)
    merged = regenerate_preserving_completed(deepcopy(old), deepcopy(new), preserve_before=today)
    return new, merged


def _hard(s):
    return bool((s.get("tags") or {}).get("hard"))


def _finger(s):
    return bool((s.get("tags") or {}).get("finger"))


def _base():
    wp = plan(PHASE, today=MON)
    # The shape the tests rely on (strength_power, synthetic availability).
    assert _slot(wp, THU, "evening")["session_id"] == "power_contact_gym"
    assert _slot(wp, SAT, "evening")["session_id"] == "strength_long"
    return wp


def _app_remove(wp, d_iso, slot):
    """The app's way (week/page.tsx, today/page.tsx): session_ref only."""
    ref = _slot(wp, d_iso, slot)["session_id"]
    return apply_events(wp, [{"event_type": "remove_session", "date": d_iso, "session_ref": ref}])


def _crag(wp, d_iso):
    """Daniele's flow for a crag day: remove the day's sessions, add_outdoor."""
    evs = [{"event_type": "remove_session", "date": d_iso, "session_ref": s["session_id"]}
           for s in _day(wp, d_iso).get("sessions") or []]
    evs.append({"event_type": "add_outdoor", "date": d_iso, "spot_name": "Crag A", "discipline": "lead"})
    return apply_events(wp, evs)


# ---------------------------------------------------------------------------
# (a) the log
# ---------------------------------------------------------------------------

class TestRemovalLog:
    def test_app_removal_records_the_real_slot(self):
        wp = _app_remove(_base(), THU, "evening")
        ev = wp["adaptations"][-1]["event"]
        assert ev["event_type"] == "remove_session"
        assert ev["session_ref"] == "power_contact_gym" and "slot" not in ev  # the event as sent
        assert ev["removed_slot"] == "evening" and ev["removed_owned"] is False
        recs = uo.removal_records(wp)
        assert recs[-1]["slot"] == "evening" and recs[-1]["kind"] == "removed"
        assert (THU, "evening") in uo.slot_emptied(recs)

    def test_removing_your_own_session_does_not_empty_the_slot(self):
        wp = _base()
        mine = {"slot": "evening", "session_id": "prehab_maintenance", "constraints_applied": ["quick_add"],
                "tags": {}, "status": "planned"}
        _day(wp, WED)["sessions"].append(mine)
        wp = apply_events(wp, [{"event_type": "remove_session", "date": WED,
                                "session_ref": "prehab_maintenance"}])
        ev = wp["adaptations"][-1]["event"]
        assert ev["removed_owned"] is True
        assert (WED, "evening") not in uo.slot_emptied(uo.removal_records(wp))
        _, merged = _regen(wp, MON)
        assert _slot(merged, WED, "evening")["session_id"] == "technique_focus_gym"

    def test_legacy_record_without_slot_keeps_the_by_id_reading(self):
        wp = _base()
        wp.setdefault("adaptations", []).append(
            {"type": "event", "event": {"event_type": "remove_session", "date": THU,
                                        "session_ref": "power_contact_gym"}})
        recs = uo.removal_records(wp)
        assert recs[-1]["slot"] is None
        assert not uo.slot_emptied(recs)


# ---------------------------------------------------------------------------
# (a) the regeneration
# ---------------------------------------------------------------------------

class TestSlotStaysEmpty:
    def test_removed_slot_stays_empty_after_regeneration(self):
        old = _app_remove(_base(), THU, "evening")
        new, merged = _regen(old, MON)
        assert _slot(new, THU, "evening") is None  # the planner did not use it
        assert _slot(merged, THU, "evening") is None
        # The lunch of the same day is not affected.
        assert _slot(merged, THU, "lunch") is not None

    def test_merge_drops_a_different_id_in_an_emptied_slot(self):
        old = _app_remove(_base(), THU, "evening")
        new = deepcopy(old)
        _day(new, THU)["sessions"].append(
            {"slot": "evening", "session_id": "lead_tryhard_gym", "tags": {}, "status": "planned"})
        merged = regenerate_preserving_completed(deepcopy(old), new, preserve_before=MON)
        assert _slot(merged, THU, "evening") is None

    def test_d1_removed_session_may_land_on_another_day(self):
        old = _app_remove(_base(), THU, "evening")
        _, merged = _regen(old, MON)
        placed = [d["date"] for d in days_of(merged)
                  for s in d.get("sessions") or [] if s.get("session_id") == "power_contact_gym"]
        assert placed and THU not in placed

    def test_user_session_put_back_in_the_emptied_slot_is_kept(self):
        old = _app_remove(_base(), THU, "evening")
        mine = {"slot": "evening", "session_id": "my_own", "constraints_applied": ["custom_add"],
                "is_custom": True, "tags": {}, "status": "planned"}
        _day(old, THU)["sessions"].append(deepcopy(mine))
        _, merged = _regen(old, MON)
        assert _slot(merged, THU, "evening") == mine

    def test_moved_source_slot_stays_empty(self):
        old = apply_events(_base(), [{"event_type": "move_session", "from_date": THU, "from_slot": "evening",
                                      "session_ref": "power_contact_gym", "to_date": FRI,
                                      "to_slot": "evening"}])
        _, merged = _regen(old, MON)
        assert _slot(merged, THU, "evening") is None
        assert _slot(merged, FRI, "evening")["session_id"] == "power_contact_gym"

    def test_past_days_are_immutable(self):
        old = _app_remove(_base(), TUE, "evening")
        old = _app_remove(old, THU, "evening")
        _, merged = _regen(old, WED)
        for d_iso in (MON, TUE):
            assert _day(merged, d_iso) == _day(old, d_iso)

    def test_deterministic(self):
        old = _app_remove(_base(), THU, "evening")
        a, ma = _regen(old, MON)
        b, mb = _regen(old, MON)
        assert _fp(a) == _fp(b) and _fp(ma) == _fp(mb)


# ---------------------------------------------------------------------------
# D2 — remove_outdoor gives the day back
# ---------------------------------------------------------------------------

class TestRemoveOutdoorGivesTheDayBack:
    def test_removals_before_add_outdoor_are_cancelled(self):
        old = _crag(_base(), SAT)
        assert (SAT, "evening") in uo.slot_emptied(uo.removal_records(old))
        old = apply_events(old, [{"event_type": "remove_outdoor", "date": SAT}])
        assert not [r for r in uo.removal_records(old) if r["date"] == SAT]
        _, merged = _regen(old, MON)
        assert _slot(merged, SAT, "evening") is not None

    def test_removal_after_add_outdoor_is_kept(self):
        wp = apply_events(_base(), [
            {"event_type": "add_outdoor", "date": SAT, "spot_name": "Crag A", "discipline": "lead"},
            {"event_type": "remove_session", "date": SAT, "session_ref": "strength_long"},
            {"event_type": "remove_outdoor", "date": SAT},
        ])
        assert [(r["date"], r["slot"]) for r in uo.removal_records(wp)] == [(SAT, "evening")]

    def test_without_add_outdoor_on_record_every_earlier_removal_of_the_day_goes(self):
        wp = _app_remove(_base(), SAT, "evening")
        _day(wp, SAT)["outdoor_spot_name"] = "Crag A"  # declared outside the log
        wp = apply_events(wp, [{"event_type": "remove_outdoor", "date": SAT}])
        assert not [r for r in uo.removal_records(wp) if r["date"] == SAT]

    def test_other_days_and_moves_are_untouched(self):
        wp = _app_remove(_base(), THU, "evening")
        wp = apply_events(wp, [{"event_type": "move_session", "from_date": SAT, "from_slot": "evening",
                                "session_ref": "strength_long", "to_date": SUN, "to_slot": "evening"}])
        wp = _crag(wp, SAT)
        before = [(r["date"], r["kind"]) for r in uo.removal_records(wp)]
        wp = apply_events(wp, [{"event_type": "remove_outdoor", "date": SAT}])
        after = [(r["date"], r["kind"]) for r in uo.removal_records(wp)]
        assert (THU, "removed") in after and (SAT, "moved") in after
        assert len(before) - len(after) == len([k for d, k in before if d == SAT and k == "removed"])


# ---------------------------------------------------------------------------
# (b) a declared crag day is a hard, finger-loading day
# ---------------------------------------------------------------------------

class TestCragDayCounts:
    def test_crag_day_counts_in_the_hard_cap(self):
        old = _crag(_base(), SAT)
        _, merged = _regen(old, MON, prefs={**PREFS, "hard_day_cap_per_week": 2})
        hard_days = {d["date"] for d in days_of(merged) if any(_hard(s) for s in d["sessions"])}
        assert len(hard_days) + 1 <= 2  # + the crag day
        assert _day(merged, SAT)["sessions"] == []

    def test_no_finger_or_hard_session_next_to_the_crag_day(self):
        old = _crag(_base(), SAT)
        _, merged = _regen(old, MON)
        for d_iso in (FRI, SUN):
            assert not any(_hard(s) or _finger(s) for s in _day(merged, d_iso)["sessions"])

    def test_previous_week_crag_sunday_seeds_monday(self):
        prev = plan(PHASE, start_date="2026-10-05", today="2026-10-05")
        last = days_of(prev)[-1]
        last["sessions"] = []
        last["outdoor_spot_name"] = "Crag A"
        last["outdoor_session_status"] = "done"
        wp = plan(PHASE, today=MON, prev_week_plan=prev)
        assert not any(_hard(s) or _finger(s) for s in _day(wp, MON)["sessions"])

    def test_past_crag_day_never_done_does_not_count(self):
        prev = plan(PHASE, start_date="2026-10-05", today="2026-10-05")
        last = days_of(prev)[-1]
        last["sessions"] = []
        last["outdoor_spot_name"] = "Crag A"
        last["outdoor_session_status"] = "planned"  # past, never completed
        assert _fp(plan(PHASE, today=MON, prev_week_plan=prev)) == _fp(
            plan(PHASE, today=MON, prev_week_plan={**prev, "weeks": [{"days": days_of(prev)[:-1]}]}))

    def test_without_crag_days_or_removals_nothing_changes(self):
        base = _base()
        _, merged = _regen(base, MON)
        assert _fp(plan(PHASE, today=MON, existing_week_plan=deepcopy(base))) == _fp(plan(PHASE, today=MON))
        assert [[s["session_id"] for s in d["sessions"]] for d in days_of(merged)] == \
            [[s["session_id"] for s in d["sessions"]] for d in days_of(base)]

    def test_deload_week_with_a_crag_day(self):
        old = plan("deload", today=MON)
        old = _crag(old, SAT)
        new = plan("deload", today=MON, existing_week_plan=deepcopy(old))
        assert not any(_hard(s) for d in days_of(new) for s in d["sessions"])
        assert _day(new, SAT)["sessions"] == []

    def test_deterministic(self):
        old = _crag(_base(), SAT)
        a, ma = _regen(old, MON)
        b, mb = _regen(old, MON)
        assert _fp(a) == _fp(b) and _fp(ma) == _fp(mb)
