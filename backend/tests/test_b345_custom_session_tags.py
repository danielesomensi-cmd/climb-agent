"""B345 — user-authored sessions carry honest safety tags, and survive the guards.

Found by the D280 methodology audit. `add_custom_session` hardcoded
`{"hard": False, "finger": False}` and `intensity: "medium"` onto every custom
session slot, whatever it contained; `add_generated_session` shipped whatever
`**session_payload` happened to carry, which for a payload without `tags` was
nothing at all. All three planner safety guards — the 48h finger gap
(`_seed_finger_date`, `_enforce_no_consecutive_finger`) and the weekly hard cap
(`_enforce_caps`) — read nothing but those tags, so a coach-composed max hang
was invisible to the gap that exists to protect the tendons from it.

The second half of the fix matters as much as the first: the guards downshift by
`session.update({"session_id": "regeneration_easy", ...})`, which on a custom
session leaves `is_custom`/`custom_session_id`/`exercises` attached to a
session_id that now claims to be recovery. So a custom session CONSTRAINS its
neighbours but is never rewritten (`_is_rewritable`).
"""

import pytest

from backend.engine.replanner_v1 import _is_rewritable, apply_events
from backend.engine.session_tags import derive_session_tags, merge_declared_tags


# ─── derivation ──────────────────────────────────────────────────────────────

def test_max_hang_makes_a_session_finger_and_hard():
    """The production case: 'Riattivazione dita post-montagna' contained max_hang_7s."""
    tags, intensity = derive_session_tags([
        {"exercise_id": "dead_hang_easy"},
        {"exercise_id": "max_hang_7s"},
    ])
    assert tags == {"hard": True, "finger": True}
    assert intensity == "max"


def test_limit_bouldering_is_finger_work():
    tags, intensity = derive_session_tags([{"exercise_id": "limit_bouldering"}])
    assert tags["finger"] is True
    assert intensity == "max"


def test_extensor_and_prehab_work_is_not_finger_loading():
    """The 48h gap spaces FLEXOR loading. Antagonist bands must not trigger it.

    Otherwise a prehab session blocks the following day for nothing — and the
    catalog agrees: `prehab_maintenance` is finger: False.
    """
    tags, _ = derive_session_tags([
        {"exercise_id": "finger_extensor_band"},
        {"exercise_id": "reverse_wrist_curl"},
        {"exercise_id": "forearm_pronation_supination"},
    ])
    assert tags["finger"] is False


def test_one_high_accessory_does_not_make_a_core_session_hard():
    """The first draft's bug: max-over-exercises marked a 15-min core session hard.

    `front_lever_one_leg` is intensity `high`, but the catalog's own
    `core_training` is medium/not-hard. One high accessory is not a hard day —
    it would eat a slot of the weekly cap and push real training out.
    """
    tags, intensity = derive_session_tags([
        {"exercise_id": "plank"},
        {"exercise_id": "dead_bug"},
        {"exercise_id": "core_hollow_hold"},
        {"exercise_id": "front_lever_one_leg"},
    ])
    assert tags["hard"] is False
    assert intensity == "medium"


def test_two_high_exercises_do_make_it_hard():
    """'Pull DANI': frenchies + uneven_grip_pullup — that is a pulling strength day."""
    tags, intensity = derive_session_tags([
        {"exercise_id": "frenchies"},
        {"exercise_id": "uneven_grip_pullup"},
    ])
    assert tags["hard"] is True
    assert intensity == "high"


def test_easy_session_is_low():
    tags, intensity = derive_session_tags([
        {"exercise_id": "dynamic_mobility_flow"},
        {"exercise_id": "cooldown_hamstring_fold"},
    ])
    assert tags == {"hard": False, "finger": False}
    assert intensity == "low"


@pytest.mark.parametrize("exercises", [None, [], [{"exercise_id": "does_not_exist"}], [None, "junk"]])
def test_unknown_and_empty_input_is_safe(exercises):
    """A session referencing a retired exercise must still land in the plan."""
    tags, intensity = derive_session_tags(exercises)
    assert tags == {"hard": False, "finger": False}
    assert intensity == "low"


def test_invariant_hard_iff_high_or_max():
    """_SESSION_META holds this for all 34 catalog sessions; derived tags must too."""
    cases = [
        [{"exercise_id": "max_hang_7s"}],
        [{"exercise_id": "frenchies"}, {"exercise_id": "uneven_grip_pullup"}],
        [{"exercise_id": "plank"}],
        [{"exercise_id": "front_lever_one_leg"}],
        [],
    ]
    for exercises in cases:
        tags, intensity = derive_session_tags(exercises)
        assert tags["hard"] == (intensity in ("high", "max")), (exercises, tags, intensity)


# ─── merge (generated sessions) ──────────────────────────────────────────────

def test_merge_only_escalates():
    """body_part_picker derives its own `finger` — that answer must survive."""
    tags, intensity = merge_declared_tags(
        {"hard": False, "finger": True}, "medium",
        {"hard": True, "finger": False}, "high",
    )
    assert tags == {"hard": True, "finger": True}
    assert intensity == "high"


def test_merge_keeps_a_stronger_declaration():
    tags, intensity = merge_declared_tags(
        {"hard": True, "finger": True}, "max",
        {"hard": False, "finger": False}, "low",
    )
    assert tags == {"hard": True, "finger": True}
    assert intensity == "max"


# ─── _is_rewritable ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("session,expected", [
    ({"session_id": "finger_strength_home"}, True),
    ({"session_id": "x", "status": "done"}, False),
    ({"session_id": "x", "status": "skipped"}, False),
    ({"session_id": "x", "forced": True}, False),          # A254
    ({"session_id": "custom_abc", "is_custom": True}, False),  # B345
])
def test_is_rewritable(session, expected):
    assert _is_rewritable(session) is expected


# ─── end-to-end through apply_events ─────────────────────────────────────────

def _plan(dates):
    return {
        "start_date": dates[0],
        "plan_revision": 1,
        "profile_snapshot": {"hard_cap_per_week": 3, "recovery_multiplier": 1.0},
        "adaptations": [],
        "weeks": [{"days": [{"date": d, "sessions": []} for d in dates]}],
    }


_WEEK = ["2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10",
         "2026-09-11", "2026-09-12", "2026-09-13"]


def _finger_custom_session():
    return {
        "id": "cs_finger",
        "name": "Riattivazione dita",
        "estimated_load_score": 45,
        "estimated_duration_minutes": 40,
        "exercises": [{"exercise_id": "dead_hang_easy"}, {"exercise_id": "max_hang_7s"}],
    }


def test_custom_session_lands_with_derived_tags():
    out = apply_events(
        _plan(_WEEK),
        [{"event_type": "add_custom_session", "custom_session_id": "cs_finger",
          "target_date": "2026-09-08", "slot": "evening"}],
        custom_sessions=[_finger_custom_session()],
    )
    day = next(d for d in out["weeks"][0]["days"] if d["date"] == "2026-09-08")
    session = day["sessions"][0]
    assert session["tags"] == {"hard": True, "finger": True}
    assert session["intensity"] == "max"


def test_custom_finger_session_is_not_rewritten_by_the_guard():
    """The whole point of _is_rewritable: honest tags must not cost the user their session."""
    plan = _plan(_WEEK)
    # A planner finger session the day before, so the custom one sits inside the gap.
    plan["weeks"][0]["days"][0]["sessions"] = [{
        "slot": "evening", "session_id": "finger_strength_home", "status": "planned",
        "intensity": "high", "tags": {"hard": True, "finger": True},
    }]
    out = apply_events(
        plan,
        [{"event_type": "add_custom_session", "custom_session_id": "cs_finger",
          "target_date": "2026-09-08", "slot": "evening"}],
        custom_sessions=[_finger_custom_session()],
    )
    day = next(d for d in out["weeks"][0]["days"] if d["date"] == "2026-09-08")
    session = day["sessions"][0]
    assert session["session_id"] == "custom_cs_finger", (
        "the guard rewrote a user-authored session into regeneration_easy"
    )
    assert session["exercises"], "the user's exercises were dropped"
    assert session["tags"]["finger"] is True


def test_custom_finger_session_constrains_the_following_day():
    """Exempt from rewriting is NOT exempt from counting: the engine moves around it."""
    plan = _plan(_WEEK)
    # Planner finger session the day AFTER the custom one.
    plan["weeks"][0]["days"][2]["sessions"] = [{
        "slot": "evening", "session_id": "finger_strength_home", "status": "planned",
        "intensity": "high", "tags": {"hard": True, "finger": True},
    }]
    out = apply_events(
        plan,
        [{"event_type": "add_custom_session", "custom_session_id": "cs_finger",
          "target_date": "2026-09-08", "slot": "evening"}],
        custom_sessions=[_finger_custom_session()],
    )
    day_after = next(d for d in out["weeks"][0]["days"] if d["date"] == "2026-09-09")
    assert day_after["sessions"][0]["session_id"] == "regeneration_easy", (
        "the planner's finger session survived 24h after a custom finger session — "
        "the 48h gap is still blind to custom content"
    )


def test_generated_session_without_tags_is_not_untagged():
    """`**session_payload` used to produce a slot with no `tags` key at all."""
    out = apply_events(
        _plan(_WEEK),
        [{"event_type": "add_generated_session", "target_date": "2026-09-08", "slot": "evening",
          "session_payload": {
              "build_kind": "adhoc",
              "name": "Coach ad-hoc",
              "exercises": [{"exercise_id": "max_hang_7s"}],
          }}],
    )
    day = next(d for d in out["weeks"][0]["days"] if d["date"] == "2026-09-08")
    session = day["sessions"][0]
    assert session["tags"] == {"hard": True, "finger": True}
    assert session["intensity"] == "max"
