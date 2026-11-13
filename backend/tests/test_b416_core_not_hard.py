"""B416 (D287 T1) — core, legs and handstand work at ``high`` do not make a hard day.

Daniele's bug-inbox, 2026-11-07: the custom «Casa — core duro appeso»
(``toes_to_bar`` + ``half_windshield_wiper``, both ``high``) came out
``hard: True`` and took the week of 02/11 to 5/5 hard days with a
``hard_back_to_back`` alert. Rule: a ``high`` exercise counts toward the hard
threshold only when it is climbing, pulling or pushing load; the heavy-pull
ladder ids (front lever family) keep counting; ``max`` is unchanged.
"""

from __future__ import annotations

import pytest

from backend.engine.bw_ladders import heavy_pull_exercise_ids
from backend.engine.session_tags import derive_session_tags


def _tags(*ids):
    return derive_session_tags([{"exercise_id": i} for i in ids])


@pytest.mark.parametrize("ids", [
    ("toes_to_bar", "half_windshield_wiper"),                       # the 02/11 custom
    ("archer_pullup", "toes_to_bar", "half_windshield_wiper", "copenhagen_dynamic"),  # done 10/11
    ("dip", "half_windshield_wiper"),                               # the 18/10 technique custom
    ("archer_pullup", "bulgarian_split_squat"),                     # pull + legs
])
def test_core_and_legs_highs_do_not_make_a_hard_day(ids):
    tags, intensity = _tags(*ids)
    assert tags == {"hard": False, "finger": False}
    assert intensity == "medium"


def test_front_lever_family_still_counts_as_heavy_pull():
    fl = [i for i in ("front_lever_one_leg", "front_lever_tuck") if i in heavy_pull_exercise_ids()]
    assert fl, "the front-lever family must stay in the heavy-pull ladder ids"
    tags, intensity = _tags(*fl, "toes_to_bar")
    assert tags["hard"] is (len(fl) >= 2)
    tags, intensity = _tags("front_lever_one_leg", "front_lever_tuck", "archer_pullup")
    assert tags["hard"] is True and intensity == "high"


def test_two_pulling_or_pushing_highs_stay_hard():
    tags, intensity = _tags("weighted_pullup", "dip")
    assert tags == {"hard": True, "finger": False}
    assert intensity == "high"


@pytest.mark.parametrize("eid", ["dragon_flag", "front_lever_full"])
def test_a_max_exercise_is_still_hard_alone(eid):
    tags, intensity = _tags(eid)
    assert tags["hard"] is True and intensity == "max"


def test_handstand_work_never_counts():
    tags, _ = _tags("wall_handstand_hold", "heel_pulls_chest_to_wall", "toes_to_bar", "copenhagen_dynamic")
    assert tags["hard"] is False
