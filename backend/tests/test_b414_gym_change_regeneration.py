"""B414 (step 18, B369-P6 point 2, Option B) — a change of gym survives the
regeneration of its week.

``change_gym`` rewrites location / gym_id (and sometimes the session) of a day
but stamps no user marker: on the next regeneration of the week (GET /api/week
stale/force) the merge did not keep the session and the planner, which never
read the change, put the default gym back. Decided by Daniele (2026-11-07,
Option B): the planner re-reads the place the user chose on that date
(``user_owned.gym_changes``, the last record of a date wins) and every available
slot of that day takes it — the session stays the engine's, chosen again for
that place's equipment. A ``slot`` in the event (the coach sends one) changes
that slot only, in the event and on the regeneration.

Invariants: weeks without a change_gym record are byte-identical (the A300
identity digests stay green in their own file); past days are copied
byte-identical by the merge; deterministic.

Synthetic fixtures only.
"""
from __future__ import annotations

import copy
import json
from copy import deepcopy
from datetime import date, timedelta

import pytest

from backend.engine import user_owned as uo
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _adjust_domain_weights, _build_session_pool
from backend.engine.planner_v2 import _SESSION_META, generate_phase_week
from backend.engine.replanner_v1 import apply_events, regenerate_preserving_completed
from backend.engine.equipment_utils import expand_equipment
from backend.tests.test_a289_retest_policy import _avail, _decision, _due_1019, _pe_week
from backend.tests.test_a300_complementary_slots import PREFS, PROFILE, daniele_availability, days_of

START = "2026-10-12"  # Monday
MON, TUE, WED, THU, FRI, SAT, SUN = ((date.fromisoformat(START) + timedelta(days=i)).isoformat() for i in range(7))
PHASE = "strength_power"
GYMS = [
    {"gym_id": "blocx", "priority": 1,
     "equipment": ["spraywall", "board_kilter", "hangboard", "gym_boulder", "gym_routes", "pullup_bar"]},
    {"gym_id": "work", "priority": 5,
     "equipment": ["dumbbell", "barbell", "cable_machine", "treadmill", "pullup_bar"]},
    {"gym_id": "rope", "priority": 9, "equipment": ["gym_routes", "pullup_bar"]},
]
HOME = ["hangboard", "pullup_bar"]


def plan(today=MON, existing_week_plan=None, allowed=("home", "gym"), **extra):
    return generate_phase_week(
        phase_id=PHASE,
        domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[PHASE], PROFILE),
        session_pool=_build_session_pool(PHASE, "lead"),
        start_date=START,
        availability=daniele_availability(),
        allowed_locations=list(allowed),
        hard_cap_per_week=3,
        planning_prefs=copy.deepcopy(PREFS),
        default_gym_id="blocx",
        gyms=copy.deepcopy(GYMS),
        home_equipment=list(HOME),
        today=today,
        existing_week_plan=deepcopy(existing_week_plan) if existing_week_plan is not None else None,
        **extra,
    )


def _regen(old, today=MON, **kw):
    """The GET /api/week force path: plan with existing_week_plan, then merge."""
    new = plan(today=today, existing_week_plan=old, **kw)
    return new, regenerate_preserving_completed(deepcopy(old), deepcopy(new), preserve_before=today)


def _fp(wp) -> str:
    p = json.loads(json.dumps(wp))
    p.pop("generated_at", None)
    return json.dumps(p, sort_keys=True)


def _day(wp, d_iso):
    return next(d for d in days_of(wp) if d["date"] == d_iso)


def _slot(wp, d_iso, slot):
    return next((s for s in _day(wp, d_iso).get("sessions") or [] if s.get("slot") == slot), None)


def _change(wp, d_iso, gym_id=None, location="gym", slot=None):
    ev = {"event_type": "change_gym", "date": d_iso, "location": location}
    if gym_id:
        ev["gym_id"] = gym_id
    if slot:
        ev["slot"] = slot
    return apply_events(wp, [ev], gyms=deepcopy(GYMS), home_equipment=list(HOME))


def _gym_equipment(gym_id):
    eq = list(next(g for g in GYMS if g["gym_id"] == gym_id)["equipment"])
    if "pullup_bar" not in eq:
        eq.append("pullup_bar")
    return set(expand_equipment(eq))


def _fits(session, gym_id) -> bool:
    req = _SESSION_META.get(session["session_id"], {}).get("required_equipment") or []
    return set(req) <= _gym_equipment(gym_id)


@pytest.fixture(scope="module")
def base():
    wp = plan()
    # The shape the tests rely on (synthetic availability, A300 lunches).
    assert (_slot(wp, THU, "evening")["session_id"], _slot(wp, THU, "evening")["gym_id"]) == \
        ("power_contact_gym", "blocx")
    assert _slot(wp, THU, "lunch")["gym_id"] == "work"
    return wp


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------

class TestGymChangesReader:
    def test_no_record_no_change(self):
        assert uo.gym_changes({}) == {} and uo.gym_changes({"adaptations": [{"type": "event"}]}) == {}

    def test_last_record_of_a_date_wins(self):
        wp = {"adaptations": [
            {"type": "change_gym", "date": THU, "new_location": "gym", "new_gym_id": "rope"},
            {"type": "change_gym", "date": THU, "new_location": "home", "new_gym_id": "rope"},
            {"type": "change_gym", "date": FRI, "new_location": "gym", "new_gym_id": "work"},
        ]}
        assert uo.gym_changes(wp) == {THU: {None: {"location": "home", "gym_id": None}},
                                      FRI: {None: {"location": "gym", "gym_id": "work"}}}

    def test_slot_record_sets_that_slot_and_a_whole_day_one_resets(self):
        wp = {"adaptations": [
            {"type": "change_gym", "date": THU, "new_location": "gym", "new_gym_id": "rope"},
            {"type": "change_gym", "date": THU, "new_location": "gym", "new_gym_id": "work", "slot": "lunch"},
        ]}
        assert uo.gym_changes(wp) == {THU: {None: {"location": "gym", "gym_id": "rope"},
                                            "lunch": {"location": "gym", "gym_id": "work"}}}
        wp["adaptations"].append({"type": "change_gym", "date": THU, "new_location": "gym", "new_gym_id": "blocx"})
        assert uo.gym_changes(wp) == {THU: {None: {"location": "gym", "gym_id": "blocx"}}}

    def test_event_records_the_slot(self, base):
        out = _change(base, THU, "rope", slot="evening")
        rec = next(a for a in out["adaptations"] if a.get("type") == "change_gym")
        assert rec["slot"] == "evening"
        assert uo.gym_changes(out) == {THU: {"evening": {"location": "gym", "gym_id": "rope"}}}


# ---------------------------------------------------------------------------
# The event with a slot
# ---------------------------------------------------------------------------

class TestChangeGymSlot:
    def test_named_slot_only(self, base):
        out = _change(base, THU, "rope", slot="evening")
        assert _slot(out, THU, "lunch") == _slot(base, THU, "lunch")
        assert _slot(out, THU, "evening")["gym_id"] == "rope"

    def test_without_slot_the_whole_day_moves(self, base):
        out = _change(base, THU, "rope")
        assert {s["gym_id"] for s in _day(out, THU)["sessions"]} == {"rope"}


# ---------------------------------------------------------------------------
# The regeneration
# ---------------------------------------------------------------------------

class TestRegenerationKeepsTheChoice:
    def test_before_b414_the_default_gym_came_back(self, base):
        # Non-vacuity: what a regeneration that ignores the record does.
        old = _change(base, THU, "rope")
        stripped = deepcopy(old)
        stripped["adaptations"] = [a for a in stripped["adaptations"] if a.get("type") != "change_gym"]
        _, merged = _regen(stripped)
        assert _slot(merged, THU, "evening")["gym_id"] == "blocx"

    def test_whole_day_stays_at_the_chosen_gym_with_its_equipment(self, base):
        old = _change(base, THU, "rope")
        new, merged = _regen(old)
        thu = _day(merged, THU)["sessions"]
        assert thu, "the day keeps training"
        for s in thu:
            assert (s["location"], s["gym_id"]) == ("gym", "rope"), s
            assert _fits(s, "rope"), s["session_id"]
        # The planner itself chose for rope (not the merge putting back the old one).
        assert all(s["gym_id"] == "rope" for s in _day(new, THU)["sessions"])
        # The record is carried for the next regeneration.
        assert uo.gym_changes(merged) == uo.gym_changes(old)

    def test_a_second_regeneration_keeps_it_too(self, base):
        _, once = _regen(_change(base, THU, "rope"))
        _, twice = _regen(once)
        assert {s["gym_id"] for s in _day(twice, THU)["sessions"]} == {"rope"}

    def test_named_slot_only_on_regeneration(self, base):
        _, merged = _regen(_change(base, THU, "rope", slot="evening"))
        assert _slot(merged, THU, "evening")["gym_id"] == "rope"
        assert _slot(merged, THU, "lunch")["gym_id"] == "work"

    def test_change_to_home_reads_the_home_kit(self, base):
        _, merged = _regen(_change(base, THU, location="home"))
        for s in _day(merged, THU)["sessions"]:
            assert (s["location"], s["gym_id"]) == ("home", None), s
            req = _SESSION_META.get(s["session_id"], {}).get("required_equipment") or []
            assert set(req) <= set(expand_equipment(HOME)), s["session_id"]

    def test_home_outside_the_allowed_locations_is_not_applied(self, base):
        old = _change(base, THU, location="home")
        new = plan(existing_week_plan=old, allowed=("gym",))
        assert _fp(new) == _fp(plan(existing_week_plan=_without_changes(old), allowed=("gym",)))

    def test_a_gym_no_longer_in_the_list_is_not_applied(self, base):
        old = _change(base, THU, "rope")
        for a in old["adaptations"]:
            if a.get("type") == "change_gym":
                a["new_gym_id"] = "closed_gym"
        assert _fp(plan(existing_week_plan=old)) == _fp(plan(existing_week_plan=_without_changes(old)))

    def test_past_change_is_ignored_and_past_days_are_byte_identical(self, base):
        old = _change(base, TUE, "rope")
        old = _change(old, THU, "rope")
        new, merged = _regen(old, today=WED)
        for d_iso in (MON, TUE):
            assert _day(merged, d_iso) == _day(old, d_iso)
        assert _fp(new) == _fp(plan(today=WED, existing_week_plan=_without_changes(old, keep={THU})))

    def test_done_session_on_the_changed_day_is_byte_identical(self, base):
        old = deepcopy(base)
        _slot(old, THU, "lunch")["status"] = "done"
        old = _change(old, THU, "rope")
        done = deepcopy(_slot(old, THU, "lunch"))
        _, merged = _regen(old)
        assert _slot(merged, THU, "lunch") == done

    def test_week_without_records_is_identical(self, base):
        other = apply_events(base, [{"event_type": "mark_skipped", "date": SAT, "slot": "evening"}])
        assert _fp(plan(existing_week_plan=other)) == _fp(plan(existing_week_plan=_without_changes(other)))
        assert _fp(plan(existing_week_plan=base)) == _fp(plan())

    def test_deterministic(self, base):
        old = _change(base, THU, "rope")
        a, ma = _regen(old)
        b, mb = _regen(old)
        assert _fp(a) == _fp(b) and _fp(ma) == _fp(mb)


def _without_changes(wp, keep=()):
    out = deepcopy(wp)
    out["adaptations"] = [a for a in out.get("adaptations") or []
                          if a.get("type") != "change_gym" or str(a.get("date"))[:10] in set(keep)]
    return out


# ---------------------------------------------------------------------------
# The combined test moved to a gym without weights, then regenerated
# ---------------------------------------------------------------------------

COCQUE = {"gym_id": "cocque", "equipment": ["spraywall", "gym_routes", "hangboard", "pullup_bar"]}
_G1 = {"gym_id": "g1", "equipment": ["spraywall", "board_kilter", "hangboard", "gym_boulder",
                                     "gym_routes", "dumbbell", "pullup_bar", "weights"]}


def _combo_week(**over):
    dec = _decision(_due_1019(), "2026-10-19")
    return generate_phase_week(**_pe_week(retest_decisions=dec, availability=_avail(slots=("evening",)),
                                          gyms=[_G1, COCQUE], **over))


class TestCombinedAfterTheChange:
    def test_regeneration_puts_no_weighted_test_at_the_gym_without_weights(self):
        old = _combo_week()
        d = next(day["date"] for day in days_of(old)
                 if any(s["session_id"] == "test_max_hang_pullup" for s in day["sessions"]))
        old = apply_events(old, [{"event_type": "change_gym", "date": d, "location": "gym", "gym_id": "cocque"}],
                           gyms=[_G1, COCQUE])
        assert [s["session_id"] for s in _day(old, d)["sessions"]] == ["test_max_hang_7s"]
        new = _combo_week(existing_week_plan=deepcopy(old), today="2026-10-19")
        merged = regenerate_preserving_completed(deepcopy(old), deepcopy(new), preserve_before="2026-10-19")
        cocque_eq = set(expand_equipment(COCQUE["equipment"]))
        for s in _day(merged, d)["sessions"]:
            assert s["gym_id"] == "cocque"
            req = _SESSION_META.get(s["session_id"], {}).get("required_equipment") or []
            assert set(req) <= cocque_eq, s["session_id"]
        # The snapshot says what the plan holds: every placed row is there.
        idx = {(day["date"], s["slot"]): s["session_id"] for day in days_of(merged) for s in day["sessions"]}
        for row in merged["profile_snapshot"]["retest_decisions"]["required_sessions"]:
            if row["status"] == "placed":
                assert idx.get((row["placed_date"], row["placed_slot"])) == row["session_id"], row
