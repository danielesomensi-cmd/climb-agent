"""B392 — a light warm-up does not make a custom session a finger session.

``warmup_easy_boulders`` has the ``climbing_limit_boulder`` pattern, so a
technique custom opening with easy boulders came out ``finger: True`` and put
«NO dita max» on the following day (prod, custom of 18/10 → 19/10).
"""

from backend.engine.session_tags import derive_session_tags

_TECHNIQUE_DAY = [
    {"exercise_id": "warmup_easy_boulders"},
    {"exercise_id": "small_feet_press_hold"},
    {"exercise_id": "no_readjust_drill"},
]


def test_technique_custom_with_easy_boulder_warmup_is_not_finger():
    tags, _ = derive_session_tags(_TECHNIQUE_DAY)
    assert tags["finger"] is False


def test_prod_case_with_dip_stays_not_finger():
    """The 18/10 draft: technique + dip. ``hard`` is the dip's business, not B392's."""
    tags, _ = derive_session_tags(_TECHNIQUE_DAY + [{"exercise_id": "dip"}])
    assert tags["finger"] is False


def test_light_hangboard_warmups_alone_are_not_finger():
    tags, _ = derive_session_tags([
        {"exercise_id": "dead_hang_easy"},
        {"exercise_id": "hang_rampup_progressive"},
        {"exercise_id": "warmup_repeaters_large"},
    ])
    assert tags["finger"] is False


def test_warmup_does_not_mask_real_finger_work():
    tags, _ = derive_session_tags([
        {"exercise_id": "warmup_easy_boulders"},
        {"exercise_id": "limit_bouldering"},
    ])
    assert tags["finger"] is True


def test_submax_hangboard_main_work_keeps_the_finger_tag():
    """Rated ``low`` finger stress too, but it is the main load, not a warm-up."""
    for ex in ("sub_max_capacity_hang", "repeater_sub_max_endurance",
               "intermittent_dead_hangs", "long_interval_repeaters"):
        tags, _ = derive_session_tags([{"exercise_id": ex}])
        assert tags["finger"] is True, ex
