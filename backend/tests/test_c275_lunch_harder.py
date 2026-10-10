"""C275 — the two strength lunches get harder, not more numerous.

Decision of Daniele (2026-10-06): the lunch complementaries of A300 stay four a
week, but the two strength ones were a maintenance dose. Harder in this order:
intensity (RIR 1-2) → density → volume.

- ``legs_maintenance_lunch``: goblet squat 4x6 and RDL 3x6 at RIR 1-2 (loads
  from the working load, moved by the closed loop), foot block unchanged, one
  rotating floor core exercise;
- ``upper_push_arms_lunch``: bench press 4x6, a ring push-up block that the
  A298 push ladder can take over, triceps 3x10, a pinned dumbbell curl 3x8
  (the biceps stay, and progress by load), one rotating core exercise.

What is pinned here:

1. no load lives in the catalog: every loaded lift is a pin of an
   ``external_load`` exercise, its kg comes from ``working_loads``;
2. the core blocks: A/B rotation from a pool with no plank / dead bug / Pallof,
   never a hanging exercise, never a front lever, never a heavy pull or finger
   stimulus — for tested and untested athletes, in every phase;
3. the planner labels did not move (``medium``, ``hard: False``): the hard-day
   cap and the guards count exactly what they counted before;
4. a tested athlete alternates the two core options week by week and gets the
   ladder dose of his level; the ring push-up follows the push ladder.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.engine import bw_progression
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.resolve_session import resolve_session
from backend.engine.stimulus import is_finger_hard_session, is_pulling_hard_session, session_stimuli
from backend.tests import c272_golden_cases as golden

REPO = Path(__file__).resolve().parents[2]
SESSIONS = REPO / "backend" / "catalog" / "sessions" / "v1"
EXERCISES = "backend/catalog/exercises/v1/exercises.json"
LADDERS = REPO / "backend" / "catalog" / "progressions" / "v1" / "bw_ladders.json"

STRENGTH_LUNCH = ("legs_maintenance_lunch", "upper_push_arms_lunch")
PHASES = ("base", "strength_power", "power_endurance", "performance", "deload")
#: Daniele's lunch gym "Work" (gym_id 3c7f08e0 in production).
WORK = ["barbell", "cable_machine", "leg_press", "bench", "dumbbell", "pullup_bar", "weight",
        "resistance_band", "rings", "ab_wheel", "foam_roller", "treadmill"]
EQUIPMENT_SETS = {
    "work": WORK,
    "c274_work": ["barbell", "cable_machine", "dumbbell", "bench", "pullup_bar", "weight", "treadmill"],
    "dumbbell_cable": ["dumbbell", "cable_machine"],
}
ACTIVATION_ONLY = {"plank", "dead_bug", "plank_shoulder_tap", "pallof_press", "kneeling_superman"}

#: (block_id, exercise_id, sets, reps, rest) of every loaded pin.
LOADED_PINS = {
    "legs_maintenance_lunch": [("squat_main", "goblet_squat", 4, 6, 120),
                               ("hinge", "romanian_deadlift", 3, 6, 120)],
    "upper_push_arms_lunch": [("chest_press", "bench_press", 4, 6, 120),
                              ("biceps", "bicep_curl", 3, 8, 75)],
}


def _session(sid: str) -> dict:
    return json.loads((SESSIONS / f"{sid}.json").read_text(encoding="utf-8"))


def _module(sid: str, block_id: str) -> dict:
    return next(m for m in _session(sid)["modules"] if m.get("block_id") == block_id)


@pytest.fixture(scope="module")
def catalog() -> dict:
    data = json.loads((REPO / EXERCISES).read_text(encoding="utf-8"))
    return {e["id"]: e for e in data["exercises"]}


@pytest.fixture(scope="module")
def ladder_of(catalog) -> dict:
    """exercise_id → family doc of its bodyweight ladder."""
    data = json.loads(LADDERS.read_text(encoding="utf-8"))
    out = {}
    for fam in data["families"]:
        for lv in fam["levels"]:
            out[lv["exercise_id"]] = fam
    return out


def _untested_state(equipment, date) -> dict:
    return {
        "bodyweight_kg": 78.0,
        "body": {"weight_kg": 78.0, "age": 40},
        "assessment": {"experience": {"climbing_years": 16}},
        "equipment": {"home": [], "gyms": [{"gym_id": "work", "name": "Work", "equipment": list(equipment)}]},
        "working_loads": {"entries": [], "rules": {}},
        "context": {"location": "gym", "gym_id": "work", "target_date": date, "date": date},
    }


def _tested_state(date, equipment=WORK) -> dict:
    st = deepcopy(golden.profiles()["advanced"])
    st["equipment"]["gyms"].append({"gym_id": "work", "name": "Work", "priority": 2,
                                    "equipment": list(equipment)})
    st["context"] = {"location": "gym", "gym_id": "work", "target_date": date, "date": date}
    return st


def _resolve(sid: str, state: dict, phase: str) -> dict:
    r = resolve_session(
        str(REPO), f"backend/catalog/sessions/v1/{sid}.json", "backend/catalog/templates", EXERCISES, "",
        user_state_override=state, write_output=False, phase=phase,
    )
    r.pop("generated_at", None)
    return r


def _insts(r: dict) -> list:
    return r["resolved_session"]["exercise_instances"]


def _by_block(r: dict) -> dict:
    return {i["source"]["block_id"]: i for i in _insts(r)}


# ---------------------------------------------------------------------------
# 1. Catalog contract: harder dose, loads never in the catalog
# ---------------------------------------------------------------------------

class TestDose:
    @pytest.mark.parametrize("sid", STRENGTH_LUNCH)
    def test_loaded_pins_are_external_load_with_the_strength_dose(self, sid, catalog):
        for block_id, eid, sets, reps, rest in LOADED_PINS[sid]:
            prim = _module(sid, block_id)["selection"]["primary"]
            assert prim["exercise_id"] == eid
            assert catalog[eid]["load_model"] == "external_load", eid
            ov = prim["prescription_overrides"]
            assert (ov["sets"], ov["reps"], ov["rest_between_sets_seconds"]) == (sets, reps, rest)
            assert "RIR 1-2" in ov["notes"], eid

    @pytest.mark.parametrize("sid", STRENGTH_LUNCH)
    def test_no_load_in_the_catalog(self, sid):
        """Loads come from working_loads (closed loop), never from session data."""
        for m in _session(sid)["modules"]:
            ov = ((m.get("selection") or {}).get("primary") or {}).get("prescription_overrides") or {}
            assert not {"load_kg", "added_load_kg", "intensity_pct", "load_pct"} & set(ov), (sid, m["block_id"])

    @pytest.mark.parametrize("sid", STRENGTH_LUNCH)
    def test_intent_says_rir_and_deload(self, sid):
        notes = _session(sid)["intent"]["notes"]
        assert "RIR 1-2" in notes and "deload" in notes

    def test_biceps_are_kept_and_progress_by_load(self, catalog):
        prim = _module("upper_push_arms_lunch", "biceps")["selection"]["primary"]
        assert prim["exercise_id"] == "bicep_curl"
        assert catalog["bicep_curl"]["pattern"] == "elbow_flexion"
        assert catalog["bicep_curl"]["equipment_required"] == ["dumbbell"]
        assert "dumbbell" in _session("upper_push_arms_lunch")["required_equipment"]

    def test_triceps_dose_on_the_cable(self):
        ov = _module("upper_push_arms_lunch", "triceps")["selection"]["primary"]["prescription_overrides"]
        assert (ov["sets"], ov["reps"]) == (3, 10) and "RIR 1-2" in ov["notes"]

    def test_ring_push_block_can_reach_the_top_ladder_level(self, catalog, ladder_of):
        """The ladder swap passes every block filter: intensity_max must let the
        ring push-up with rings turned out (intensity high) in."""
        filters = _module("upper_push_arms_lunch", "push_bodyweight")["selection"]["primary"]["filters"]
        assert filters["equipment"] == ["rings"] and filters["intensity_max"] == "high"
        fam = ladder_of["ring_pushup"]
        assert fam["family"] == "push_horizontal"
        assert catalog[fam["levels"][-1]["exercise_id"]]["intensity_level"] == "high"


# ---------------------------------------------------------------------------
# 2. Core blocks: rotation, never hanging / front lever / activation-only
# ---------------------------------------------------------------------------

class TestCoreBlocks:
    @pytest.mark.parametrize("sid", STRENGTH_LUNCH)
    def test_core_block_is_an_ab_rotation_without_activation_items(self, sid, catalog, ladder_of):
        m = _module(sid, "core_rotation")
        assert m["rotation"] == "ab" and len(m["ab_pool"]) == 2
        assert ACTIVATION_ONLY <= set(m["rotation_exclude"])
        assert not set(m["ab_pool"]) & ACTIVATION_ONLY
        filters = m["selection"]["primary"]["filters"]
        for eid in m["ab_pool"]:
            e = catalog[eid]
            assert "accessory" in e["role"] and "core" in e["domain"], eid
            assert e["pattern"] in filters["pattern"], eid
            assert "pullup_bar" not in (e.get("equipment_required") or []), eid
            fam = ladder_of.get(eid)
            if fam:
                assert not fam["hanging"] and not fam["heavy_pull"], eid

    @pytest.mark.parametrize("sid", STRENGTH_LUNCH)
    def test_core_patterns_exclude_hanging_and_lever_patterns(self, sid):
        pats = set(_module(sid, "core_rotation")["selection"]["primary"]["filters"]["pattern"])
        # compression = hanging leg raises / toes to bar; isometric_hold = front
        # levers; rotation = hanging windshield wipers.
        assert not pats & {"compression", "isometric_hold", "rotation", "pull_horizontal"}

    @pytest.mark.parametrize("sid", STRENGTH_LUNCH)
    @pytest.mark.parametrize("phase", PHASES)
    @pytest.mark.parametrize("eq", sorted(EQUIPMENT_SETS))
    @pytest.mark.parametrize("tested", [False, True], ids=["untested", "tested"])
    def test_core_pick_is_never_hanging_or_a_lever(self, sid, phase, eq, tested, catalog):
        date = "2026-10-13"
        st = _tested_state(date, EQUIPMENT_SETS[eq]) if tested else _untested_state(EQUIPMENT_SETS[eq], date)
        r = _resolve(sid, st, phase)
        assert r["resolution_status"] == "success"
        core = _by_block(r).get("core_rotation")
        assert core is not None, (sid, phase, eq)
        e = catalog[core["exercise_id"]]
        assert "pullup_bar" not in (e.get("equipment_required") or []), core["exercise_id"]
        assert "front_lever" not in core["exercise_id"]
        assert core["exercise_id"] not in {"plank", "dead_bug", "plank_shoulder_tap", "kneeling_superman"}

    @pytest.mark.parametrize("sid", STRENGTH_LUNCH)
    @pytest.mark.parametrize("phase", PHASES)
    def test_no_stimulus_no_heavy_pull_no_finger_load(self, sid, phase, catalog):
        r = _resolve(sid, _tested_state("2026-10-13"), phase)
        slot = {"session_id": sid, "tags": {"hard": False, "finger": False}, "resolved": r}
        assert session_stimuli(slot) == []
        assert not is_pulling_hard_session(slot) and not is_finger_hard_session(slot)
        for inst in _insts(r):
            assert (catalog[inst["exercise_id"]].get("stress_tags") or {}).get("fingers") in ("none", None)


# ---------------------------------------------------------------------------
# 3. Planner labels unchanged: the hard-day cap and the guards see the same
# ---------------------------------------------------------------------------

class TestLabelsUnchanged:
    @pytest.mark.parametrize("sid", STRENGTH_LUNCH)
    def test_meta_and_tags_did_not_move(self, sid):
        meta = _SESSION_META[sid]
        assert meta["intensity"] == "medium" and meta["hard"] is False and meta["finger"] is False
        assert not meta.get("pulling") and meta["max_per_week"] == 2
        s = _session(sid)
        assert s["tags"] == {"hard": False, "finger": False}
        assert s["time_budget"]["hard_cap_min"] == 45


# ---------------------------------------------------------------------------
# 4. Tested athlete: weekly A/B core, ladder dose, ring push ladder
# ---------------------------------------------------------------------------

class TestTestedAthlete:
    @pytest.mark.parametrize("sid", STRENGTH_LUNCH)
    @pytest.mark.parametrize("phase,dates", [
        # The fixture athlete is tested on 2026-09-24: the A/B rotation is for
        # tested athletes, so every date sits after the test.
        ("strength_power", ("2026-09-29", "2026-10-06", "2026-10-13")),
        ("power_endurance", ("2026-10-20", "2026-10-27", "2026-11-03")),
    ], ids=["strength_power", "power_endurance"])
    def test_core_alternates_week_by_week_inside_the_pool(self, sid, phase, dates, ladder_of):
        pool = _module(sid, "core_rotation")["ab_pool"]
        fams = {ladder_of[e]["family"] if e in ladder_of else e for e in pool}
        picks = []
        for date in dates:
            core = _by_block(_resolve(sid, _tested_state(date), phase))["core_rotation"]
            eid = core["exercise_id"]
            picks.append(ladder_of[eid]["family"] if eid in ladder_of else eid)
        assert set(picks) == fams, picks
        assert all(a != b for a, b in zip(picks, picks[1:])), picks

    def test_ladder_core_gets_the_dose_of_the_level(self):
        """Rollout at level 1 (ring fallout): the A/B pick of the ab wheel is
        swapped to the athlete's level, with the ladder dose."""
        seen = False
        for date in ("2026-10-06", "2026-10-13"):
            st = _tested_state(date)
            bw_progression.set_level(st, "rollout", 1, date, confirm=True)
            core = _by_block(_resolve("upper_push_arms_lunch", st, "strength_power"))["core_rotation"]
            if core["exercise_id"] in ("ab_wheel_rollout", "ring_fallout"):
                assert core["exercise_id"] == "ring_fallout"
                assert core["prescription"]["source"] == "bw_ladder"
                assert (core["prescription"]["sets"], core["prescription"]["reps"]) == (3, 6)
                seen = True
        assert seen, "the rollout never came up in two consecutive weeks"

    def test_ring_push_up_follows_the_push_ladder(self):
        date = "2026-10-16"
        st = _tested_state(date)
        bw_progression.set_level(st, "push_horizontal", 3, date, confirm=True)
        push = _by_block(_resolve("upper_push_arms_lunch", st, "strength_power"))["push_bodyweight"]
        assert push["exercise_id"] == "ring_pushup_rto"
        assert push["prescription"]["source"] == "bw_ladder"
        assert push["prescription"]["sets"] == 3 and push["prescription"]["reps"] == 5

    def test_without_rings_the_push_block_is_still_a_push(self, catalog):
        r = _resolve("upper_push_arms_lunch", _untested_state(EQUIPMENT_SETS["c274_work"], "2026-10-16"), "base")
        push = _by_block(r)["push_bodyweight"]
        assert catalog[push["exercise_id"]]["pattern"] == "push"
        assert push["exercise_id"] not in {"bench_press", "dip", "weighted_dip"}

    @pytest.mark.parametrize("sid", STRENGTH_LUNCH)
    def test_deterministic(self, sid):
        st = _tested_state("2026-10-13")
        assert _resolve(sid, deepcopy(st), "strength_power") == _resolve(sid, deepcopy(st), "strength_power")
