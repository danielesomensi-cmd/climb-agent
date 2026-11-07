"""B414 (step 15, INBOX-2026-11-02-e, rule E2) — sub-max hangs after PE intervals
carry no finger tag.

The 02/11 custom (PE boulders + ``intermittent_dead_hangs``) came out
``finger: True`` + hard, hence finger-hard: a finger_gap alert and a
finger_gap conflict in ``check_insertion``. The catalog session with the same
content (``power_endurance_gym``) is ``finger: False``. Daniele, 2026-11-07:
the custom follows the catalog session.

Rule (``session_tags.derive_session_tags``): a sub-max hang — pattern
``repeater_hang`` / ``isometric_hang`` / ``hang``, intensity ≤ medium, not
finger-hard by itself — does not make the session ``finger`` when the session
has PE intervals (role main, pattern ``climbing_intervals``, PE / anaerobic
domain) and no other finger load. Alone, next to a 7/3, a max hang or a limit
boulder it still does (B345 / B392 unchanged).

Consumer: ``replanner_v1.add_custom_session`` (tags derived once and stored).
Planned customs keep their stored tags; after deploy ``scripts/athlete_context.py``
reports any ``STALE_CUSTOM_TAGS`` (B395).
"""
from __future__ import annotations

import copy
import logging
import os

import pytest

from backend.engine.planner_v2 import _SESSION_META
from backend.engine.replanner_v1 import apply_events
from backend.engine.session_tags import derive_session_tags
from backend.tests import b413_lunch_golden_cases as lg
from backend.tests import c272_golden_cases as golden

SUB_MAX = ("intermittent_dead_hangs", "sub_max_capacity_hang", "repeater_sub_max_endurance",
           "long_interval_repeaters", "bar_dead_hang", "long_duration_hang", "hangboard_moving_hangs")
PE = ("four_by_four_bouldering", "linked_boulders")


def _tags(*ids):
    return derive_session_tags([{"exercise_id": i} for i in ids])


class TestRule:
    def test_the_0211_custom_is_hard_not_finger(self):
        tags, intensity = _tags("warmup_easy_boulders", *PE, "intermittent_dead_hangs")
        assert tags == {"hard": True, "finger": False} and intensity == "high"

    @pytest.mark.parametrize("hang", SUB_MAX)
    def test_every_sub_max_hang_after_pe(self, hang):
        assert _tags("route_intervals", hang)[0]["finger"] is False

    @pytest.mark.parametrize("hang", SUB_MAX)
    def test_alone_a_sub_max_hang_is_still_finger(self, hang):
        """B392: the sub-max hang is the session's main finger load."""
        assert _tags("general_pulse_raise", hang)[0]["finger"] is True

    @pytest.mark.parametrize("other", ["repeater_hang_7_3", "max_hang_7s", "limit_bouldering", "density_hangs"])
    def test_other_finger_load_keeps_the_tag(self, other):
        assert _tags(*PE, "intermittent_dead_hangs", other)[0]["finger"] is True
        assert _tags(*PE, other)[0]["finger"] is True

    def test_without_pe_intervals_the_arc_does_not_clear_it(self):
        """E3 rejected: finger_maintenance_gym (ARC + moving hangs) stays finger."""
        assert _tags("arc_easy_traverse", "hangboard_moving_hangs")[0]["finger"] is True
        assert _tags("arc_training", "intermittent_dead_hangs")[0]["finger"] is True

    def test_hard_is_untouched(self):
        assert _tags("route_intervals", "intermittent_dead_hangs")[0] == {"hard": False, "finger": False}
        assert _tags(*PE, "bar_dead_hang")[0]["hard"] is True


def _plan():
    dates = [f"2026-11-{d:02d}" for d in range(9, 16)]
    return {"start_date": dates[0], "plan_revision": 1,
            "profile_snapshot": {"hard_cap_per_week": 3, "recovery_multiplier": 1.0}, "adaptations": [],
            "weeks": [{"days": [{"date": d, "sessions": []} for d in dates]}]}


def test_add_custom_session_stores_the_catalog_like_tags():
    cs = {"id": "cs_pe", "name": "PE + sospensioni", "estimated_load_score": 60, "estimated_duration_minutes": 80,
          "exercises": [{"exercise_id": e} for e in ("warmup_easy_boulders", *PE, "intermittent_dead_hangs")]}
    out = apply_events(_plan(), [{"event_type": "add_custom_session", "custom_session_id": "cs_pe",
                                  "target_date": "2026-11-10", "slot": "evening"}], custom_sessions=[cs])
    s = next(d for d in out["weeks"][0]["days"] if d["date"] == "2026-11-10")["sessions"][0]
    assert s["tags"] == {"hard": True, "finger": False}


# ---------------------------------------------------------------------------
# Derived tag of the RESOLVED catalog sessions vs _SESSION_META.finger
# ---------------------------------------------------------------------------

COCQUE = ["gym_boulder", "gym_routes", "hangboard", "pullup_bar"]
ESCALE = ["gym_boulder", "gym_routes", "hangboard", "pullup_bar", "campus_board", "dumbbell", "weight"]
PHASES = (("2026-10-13", "base"), ("2026-10-13", "strength_power"),
          ("2026-10-27", "power_endurance"), ("2026-11-10", "performance"))

#: Known discrepancies, each with its direction. True = derived finger where
#: the catalog says False (conservative: a secondary block may pick a sub-max
#: or a prehab finger exercise); False = the reverse.
KNOWN = {
    "endurance_aerobic_gym": True,   # sub-max repeaters next to the ARC (no PE intervals)
    "regeneration_easy": True,       # bar_dead_hang
    "prehab_maintenance": True,      # active_finger_curls (one profile)
    "route_projecting_gym": False,   # route climbing is not a finger pattern
}


def _states():
    for name in ("advanced", "intermediate", "untested"):
        for gym, eq in (("cocque", COCQUE), ("escale", ESCALE), ("home", None)):
            for d, ph in PHASES:
                st = copy.deepcopy(golden.profiles()[name])
                if eq is None:
                    st["context"] = {"location": "home", "target_date": d, "date": d}
                else:
                    st["equipment"]["gyms"].append({"gym_id": gym, "priority": 1, "equipment": list(eq)})
                    st["context"] = {"location": "gym", "gym_id": gym, "target_date": d, "date": d}
                yield f"{name}|{gym}|{ph}", st, ph


@pytest.fixture(scope="module")
def mismatches():
    logging.disable(logging.WARNING)
    try:
        out = {}
        for sid, meta in sorted(_SESSION_META.items()):
            if sid.startswith("test_") or not os.path.exists(
                    os.path.join(golden.REPO_ROOT, f"backend/catalog/sessions/v1/{sid}.json")):
                continue
            for key, st, ph in _states():
                if st["context"]["location"] not in (meta.get("location") or ("gym", "home")):
                    continue
                insts = lg._resolve(sid, st, ph)["resolved_session"]["exercise_instances"]
                if not insts:
                    continue
                derived = derive_session_tags([{"exercise_id": i["exercise_id"]} for i in insts])[0]["finger"]
                if derived != bool(meta.get("finger")):
                    out.setdefault(sid, []).append((key, derived, insts))
        return out
    finally:
        logging.disable(logging.NOTSET)


def test_resolved_catalog_sessions_match_the_catalog_finger_flag(mismatches):
    unexpected = {}
    for sid, rows in mismatches.items():
        for key, derived, insts in rows:
            if sid in KNOWN and derived is KNOWN[sid]:
                continue
            unexpected.setdefault(sid, []).append((key, derived, [i["exercise_id"] for i in insts]))
    assert unexpected == {}


def test_power_endurance_gym_matches_everywhere(mismatches):
    """The E2 rule plus the step-16 ``intensity_max: medium`` on its finger
    block (never the 7/3): the catalog PE derives ``finger: False`` in every
    profile, gym and phase, like ``_SESSION_META``."""
    assert "power_endurance_gym" not in mismatches
