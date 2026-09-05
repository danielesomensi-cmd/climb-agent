"""A282 — the domain weights bind as FLOORS, and the finger guarantee finally fires.

`A-DOMAIN-WEIGHTS-BINDING` (from D280) proposed validating that the distribution
of placed sessions approximates the phase's domain weights within ±0.10. That is
arithmetically impossible: the planner places ~4 sessions across 6 domains, so
the finest distribution it can express is 0.25, and in `strength_power` five of
the six weights sit below that. The check would fail every week, for ever.

What IS meaningful — and what this brief implements — is a floor: a primary
quality may not be absent from a week whose phase declares it matters.

Fixing it surfaced a real bug. PASS 2.5 ("ensure PE phase has at least one
finger maintenance session") never fired, for two reasons that compound:

  1. `day_has_available_slot` is zeroed for days pruned by `target_days`
     (7 available evenings, target 4 → 3 usable days become False), and the
     pass skipped them all;
  2. on the kept days it could only replace a NON-primary session, but
     `_is_primary_session` is `hard or climbing`, and every session in a PE
     week is climbing.

No empty day, nothing replaceable, guarantee dead — silently, across a phase
that runs three weeks against a ~30±5 day decay of maximal strength (Issurin).
"""

import json

import pytest

from backend.engine.planner_v2 import (
    QUALITY_FLOOR_WEIGHT,
    _SESSION_META,
    generate_phase_week,
)

PE_POOL = ["power_endurance_gym", "prehab_maintenance", "endurance_aerobic_gym",
           "finger_strength_home", "flexibility_full", "handstand_practice",
           "route_endurance_gym", "technique_focus_gym"]

GYM = [{"gym_id": "g1", "name": "Gym", "equipment": [
    "spraywall", "board_kilter", "gym_routes", "hangboard", "campus_board", "pullup_bar"]}]


def _kwargs(**over):
    kwargs = dict(
        phase_id="power_endurance",
        domain_weights={"finger_strength": 0.128, "power_endurance": 0.372,
                        "volume_climbing": 0.160, "technique": 0.160,
                        "core_prehab": 0.106, "pulling_strength": 0.074},
        session_pool=PE_POOL,
        start_date="2026-10-05",
        # Seven available evenings: exactly the shape that triggers target_days
        # pruning and made the guarantee unreachable.
        availability={d: {"evening": {"available": True, "preferred_location": "gym",
                                      "gym_id": "g1"}}
                      for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        home_equipment=["hangboard", "pullup_bar", "dumbbell"],
        gyms=GYM,
        default_gym_id="g1",
        allowed_locations=["gym", "home"],
        intensity_cap="high",
    )
    kwargs.update(over)
    return kwargs


def _sessions(plan):
    return [s["session_id"] for d in plan["weeks"][0]["days"] for s in d.get("sessions", [])]


def _finger_sessions(plan):
    return [s for s in _sessions(plan) if _SESSION_META.get(s, {}).get("finger")]


def _training_days(plan):
    return sum(1 for d in plan["weeks"][0]["days"] if d.get("sessions"))


# ─── the bug this brief fixes ────────────────────────────────────────────────

def test_pe_week_is_no_longer_finger_blind():
    """The reproduction: a PE week used to come out with zero finger stimulus."""
    plan = generate_phase_week(**_kwargs())
    assert _finger_sessions(plan), (
        "PE week has no session with the finger tag — the floor did not fire"
    )


def test_the_floor_may_use_a_day_target_days_had_pruned():
    """Last resort, and it costs one extra day — that is the trade-off.

    With 7 available evenings and target_days=4 the four kept days are all
    filled with climbing sessions, so there is nothing empty and nothing
    replaceable. The only way to keep the quality off zero is a fifth, short
    maintenance day.
    """
    plan = generate_phase_week(**_kwargs())
    assert _training_days(plan) == 5
    assert "finger_maintenance_gym" in _sessions(plan)


def test_the_extra_day_is_never_used_for_hard_work():
    """A maintenance dose is worth an extra day. A hard session is not."""
    plan = generate_phase_week(**_kwargs())
    for day in plan["weeks"][0]["days"]:
        for session in day.get("sessions", []):
            if "finger_floor" in (session.get("constraints_applied") or []):
                assert not (session.get("tags") or {}).get("hard")


# ─── the floor is driven by the weight ───────────────────────────────────────

def test_no_floor_when_the_phase_barely_weights_the_quality():
    """Below QUALITY_FLOOR_WEIGHT the phase is not claiming to train it."""
    weights = dict(_kwargs()["domain_weights"])
    weights["finger_strength"] = QUALITY_FLOOR_WEIGHT - 0.01
    plan = generate_phase_week(**_kwargs(domain_weights=weights))
    assert _training_days(plan) == 4, "the floor fired below its own threshold"


def test_deload_is_exempt():
    """A deload week with no finger work is correct, not a gap."""
    plan = generate_phase_week(**_kwargs(
        phase_id="deload", intensity_cap="low",
        session_pool=["deload_recovery", "flexibility_full", "prehab_maintenance",
                      "regeneration_easy", "easy_climbing_deload"],
    ))
    assert _finger_sessions(plan) == []


def test_floor_is_satisfied_by_the_tag_not_the_session_name():
    """In strength_power the fingers are loaded by limit bouldering.

    Checking for a session id starting with `finger_maintenance` (the old rule)
    would have added a redundant dose on top of two max-intensity finger days.
    """
    plan = generate_phase_week(**_kwargs(
        phase_id="strength_power", intensity_cap="max",
        domain_weights={"finger_strength": 0.340, "pulling_strength": 0.234,
                        "power_endurance": 0.106, "volume_climbing": 0.106,
                        "technique": 0.106, "core_prehab": 0.106},
        session_pool=["limit_boulder_gym", "power_contact_gym", "route_endurance_gym",
                      "technique_focus_gym", "prehab_maintenance"],
    ))
    assert "finger_maintenance_gym" not in _sessions(plan)
    assert "finger_maintenance_home" not in _sessions(plan)
    assert _finger_sessions(plan), "the fingers must still be trained"


# ─── safety constraints are never traded away ────────────────────────────────

def test_floor_never_breaks_the_finger_gap():
    """48h between finger sessions outranks the floor."""
    plan = generate_phase_week(**_kwargs())
    offsets = [i for i, d in enumerate(plan["weeks"][0]["days"])
               if any(_SESSION_META.get(s["session_id"], {}).get("finger")
                      for s in d.get("sessions", []))]
    for a, b in zip(offsets, offsets[1:]):
        assert b - a > 1, f"finger sessions on consecutive days: offsets {offsets}"


def test_floor_never_exceeds_the_hard_day_cap():
    plan = generate_phase_week(**_kwargs(hard_cap_per_week=1))
    hard_days = sum(
        1 for d in plan["weeks"][0]["days"]
        if any((s.get("tags") or {}).get("hard") for s in d.get("sessions", []))
    )
    assert hard_days <= 1


def test_an_unplaceable_floor_is_recorded_never_silent():
    """No equipment for any finger work → the gap must be reported, not hidden."""
    plan = generate_phase_week(**_kwargs(
        home_equipment=[],
        gyms=[{"gym_id": "g1", "name": "Gym", "equipment": ["gym_routes"]}],
        session_pool=["route_endurance_gym", "technique_focus_gym", "flexibility_full"],
    ))
    assert _finger_sessions(plan) == []
    stimuli = [u["stimulus"] for u in plan.get("unmet_stimulus") or []]
    assert "finger_strength" in stimuli, (
        "the floor could not be met and said nothing — B308's lesson undone"
    )


def test_unmet_entry_carries_the_weight_that_justified_the_floor():
    plan = generate_phase_week(**_kwargs(
        home_equipment=[],
        gyms=[{"gym_id": "g1", "name": "Gym", "equipment": ["gym_routes"]}],
        session_pool=["route_endurance_gym", "technique_focus_gym", "flexibility_full"],
    ))
    entry = next(u for u in plan["unmet_stimulus"] if u["stimulus"] == "finger_strength")
    assert entry["weight"] == 0.128
    assert entry["phase_id"] == "power_endurance"


# ─── invariants that must survive ────────────────────────────────────────────

def test_planner_stays_deterministic():
    kwargs = _kwargs()
    assert generate_phase_week(**kwargs) == generate_phase_week(**kwargs)


def test_b308_pulling_guarantee_still_holds():
    """PASS 2.6 is deliberately untouched: its trigger stays unconditional."""
    plan = generate_phase_week(**_kwargs())
    pulling = [s for s in _sessions(plan) if _SESSION_META.get(s, {}).get("pulling")]
    assert pulling, "the pulling guarantee regressed"


def test_target_days_is_respected_when_the_floor_does_not_need_the_extra_day():
    """The extra day is a last resort, not a new default."""
    plan = generate_phase_week(**_kwargs(
        availability={d: {"evening": {"available": True, "preferred_location": "gym",
                                      "gym_id": "g1"}}
                      for d in ("mon", "wed", "fri", "sat")},
    ))
    assert _training_days(plan) <= 5
