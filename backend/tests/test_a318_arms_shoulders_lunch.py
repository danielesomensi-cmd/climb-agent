"""A318 — the fifth lunch family: shoulders, triceps, biceps + handstand.

Daniele (2026-10-17) enabled a fifth complementary lunch (Monday, 45', gym
"Work"). With the four A300 families one of them repeats; he asked for a fifth:
"mettiamo tricipiti, bicipiti, spalle e handstand".

What is pinned here:

1. catalog — ``arms_shoulders_handstand_lunch`` is a supplementary lunch
   session like the C274 ones (no climbing / finger load, meta == catalog,
   in no phase pool), loads only from ``external_load`` exercises;
2. resolution — at the Work gym it resolves to the intended exercises in every
   phase, the handstand straight after the warm-up, inside the lunch budget,
   deterministically; a deload week drops one set from every lift (A312);
3. engine — ``arms_shoulders`` is a valid family, carries the biceps rule
   (curl → not in the 24 h before a heavy pull), and is opt-in: the default
   rotation is still the four A300 families, so every other user is unchanged
   (the A300 identity digests stay the other guard of that);
4. placement — five lunches with the five families get five different
   families, in rotation order when no rule is in the way.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.engine import complementary_v1 as cv
from backend.engine.custom_session import estimate_custom_session_duration
from backend.engine.equipment_utils import KNOWN_EQUIPMENT_KEYS
from backend.engine.macrocycle_v1 import _build_session_pool
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.resolve_session import resolve_session
from backend.engine.stimulus import is_finger_hard_session, is_pulling_hard_session, session_stimuli
from backend.tests import test_a300_complementary_slots as a300

REPO = Path(__file__).resolve().parents[2]
SESSIONS = REPO / "backend" / "catalog" / "sessions" / "v1"
EXERCISES = "backend/catalog/exercises/v1/exercises.json"
SID = "arms_shoulders_handstand_lunch"
PHASES = ("base", "strength_power", "power_endurance", "performance", "deload")

#: Daniele's lunch gym "Work" (gym_id 3c7f08e0 in production), as in C275.
WORK = ["barbell", "cable_machine", "leg_press", "bench", "dumbbell", "pullup_bar", "weight",
        "resistance_band", "rings", "ab_wheel", "foam_roller", "treadmill"]

EXPECTED = [
    "general_pulse_raise",
    "mobility_thoracic_shoulders_flow",
    # after_warmup: the handstand while fresh, then the heaviest lift
    "heel_pulls_chest_to_wall",
    "wall_handstand_hold",
    "overhead_press",
    # isolation work in the engine's generic order (ties broken by id)
    "hammer_curl",
    "lateral_raise",
    "overhead_tricep_extension",
]
#: block_id → (exercise_id, sets, deload_sets) of every loaded lift.
LOADED = {
    "shoulder_press": ("overhead_press", 3, 2),
    "lateral_delts": ("lateral_raise", 3, 2),
    "triceps": ("overhead_tricep_extension", 3, 2),
    "biceps": ("hammer_curl", 3, 2),
}
DUMBBELL_BLOCKS = ("shoulder_press", "lateral_delts", "triceps", "biceps")


def _session() -> dict:
    return json.loads((SESSIONS / f"{SID}.json").read_text(encoding="utf-8"))


def _module(block_id: str) -> dict:
    return next(m for m in _session()["modules"] if m.get("block_id") == block_id)


@pytest.fixture(scope="module")
def catalog() -> dict:
    data = json.loads((REPO / EXERCISES).read_text(encoding="utf-8"))
    return {e["id"]: e for e in data["exercises"]}


def _state(equipment=WORK, date="2026-10-19", phase=None) -> dict:
    st = {
        "bodyweight_kg": 78.0,
        "body": {"weight_kg": 78.0, "age": 40},
        "assessment": {"experience": {"climbing_years": 16}},
        "equipment": {"home": [], "gyms": [{"gym_id": "work", "name": "Work", "equipment": list(equipment)}]},
        "working_loads": {"entries": [], "rules": {}},
        "context": {"location": "gym", "gym_id": "work", "target_date": date, "date": date},
    }
    if phase:
        st["macrocycle"] = {"start_date": "2026-10-19",
                            "phases": [{"phase_id": phase, "duration_weeks": 1},
                                       {"phase_id": "base", "duration_weeks": 4}]}
    return st


def _resolve(phase="base", equipment=WORK, state=None) -> dict:
    r = resolve_session(
        str(REPO), f"backend/catalog/sessions/v1/{SID}.json", "backend/catalog/templates", EXERCISES, "",
        user_state_override=state or _state(equipment), write_output=False, phase=phase,
    )
    r.pop("generated_at", None)
    return r


def _insts(r: dict) -> list:
    return r["resolved_session"]["exercise_instances"]


def _ids(r: dict) -> list:
    return [i["exercise_id"] for i in _insts(r)]


# ---------------------------------------------------------------------------
# 1. Catalog contract
# ---------------------------------------------------------------------------

class TestCatalog:
    def test_supplementary_lunch_session(self):
        s = _session()
        assert s["id"] == SID and s["supplementary"] is True
        assert "lunch_short" in s["compatibility"]["slot"]
        assert s["time_budget"] == {"target_duration_min": 35, "hard_cap_min": 45}
        assert s["tags"] == {"hard": False, "finger": False}
        assert s["intent"]["primary_goal"] == "strength_general"

    def test_meta_matches_catalog(self):
        meta = _SESSION_META[SID]
        assert meta["hard"] is False and meta["finger"] is False and meta["climbing"] is False
        assert not meta.get("pulling")
        assert meta["intensity"] == "medium" and meta["location"] == ("gym",)
        assert set(_session()["required_equipment"]) <= KNOWN_EQUIPMENT_KEYS
        assert set(_session()["required_equipment"]) == set(meta["required_equipment"])

    @pytest.mark.parametrize("discipline", ("lead", "boulder", "all_round"))
    def test_in_no_phase_pool(self, discipline):
        for phase in PHASES:
            assert SID not in _build_session_pool(phase, discipline), (phase, discipline)

    def test_loaded_lifts_are_external_load_and_say_per_dumbbell(self, catalog):
        for block_id, (eid, sets, deload) in LOADED.items():
            prim = _module(block_id)["selection"]["primary"]
            assert prim["exercise_id"] == eid
            assert catalog[eid]["load_model"] == "external_load", eid
            ov = prim["prescription_overrides"]
            assert (ov["sets"], ov["deload_sets"]) == (sets, deload), block_id
            assert "RIR 1-2" in ov["notes"], block_id
            assert "load_kg" not in ov, block_id  # no load lives in the catalog
        for block_id in DUMBBELL_BLOCKS:
            notes = _module(block_id)["selection"]["primary"]["prescription_overrides"]["notes"]
            assert "per dumbbell" in notes or "that one dumbbell" in notes, block_id

    def test_handstand_blocks_come_after_the_warmup(self):
        assert _module("handstand_hold")["order"] == "after_warmup"
        assert _module("handstand_balance")["order"] == "after_warmup"
        assert _module("handstand_hold")["required"] is True
        assert "first" in _session()["intent"]["notes"]


# ---------------------------------------------------------------------------
# 2. Resolution at the Work gym
# ---------------------------------------------------------------------------

class TestResolution:
    @pytest.mark.parametrize("phase", PHASES)
    def test_resolves_to_the_intended_exercises(self, phase):
        r = _resolve(phase)
        assert r["resolution_status"] == "success"
        assert _ids(r) == EXPECTED
        blocks = {b.get("block_id"): b for b in r["resolved_session"]["blocks"]}
        for m in _session()["modules"]:
            if m.get("required"):
                assert blocks[m["block_id"]]["selected_exercises"], m["block_id"]

    @pytest.mark.parametrize("equipment", [["dumbbell"], ["dumbbell", "cable_machine", "bench"]],
                             ids=["dumbbell_only", "dumbbell_cable_bench"])
    def test_needs_only_dumbbells(self, equipment):
        r = _resolve("base", equipment)
        assert r["resolution_status"] == "success"
        assert _ids(r) == EXPECTED

    @pytest.mark.parametrize("phase", PHASES)
    def test_fits_the_lunch_budget(self, phase, catalog):
        rows = []
        for inst in _insts(_resolve(phase)):
            rx = dict(inst.get("prescription") or {})
            rx["alt_sides"] = bool(catalog[inst["exercise_id"]].get("alt_sides"))
            rows.append(rx)
        minutes = estimate_custom_session_duration(rows)
        assert 25 <= minutes <= _session()["time_budget"]["target_duration_min"], (phase, minutes)

    def test_no_finger_load_no_hanging_no_heavy_pull(self, catalog):
        r = _resolve("strength_power")
        for eid in _ids(r):
            e = catalog[eid]
            assert (e.get("stress_tags") or {}).get("fingers") in ("none", "low", None), eid
            assert not set(e.get("equipment_required") or []) & {
                "hangboard", "hangboard_20mm", "loading_pin", "campus_board", "gym_boulder", "gym_routes",
                "pullup_bar", "rings"}, eid
            assert "pullup" not in eid and "chinup" not in eid, eid
        planned = {"session_id": SID, "exercises": [{"exercise_id": x} for x in _ids(r)]}
        assert session_stimuli(planned) == []
        assert not is_finger_hard_session({"session_id": SID})
        assert not is_pulling_hard_session({"session_id": SID})

    def test_deload_week_drops_one_set_from_every_lift(self):
        by_block = {i["source"]["block_id"]: i for i in
                    _insts(_resolve("deload", state=_state(phase="deload")))}
        for block_id, (_eid, sets, deload) in LOADED.items():
            rx = by_block[block_id]["prescription"]
            assert rx["sets"] == deload and rx["stored_sets"] == sets, block_id
        normal = {i["source"]["block_id"]: i for i in
                  _insts(_resolve("strength_power", state=_state(phase="strength_power")))}
        for block_id, (_eid, sets, _d) in LOADED.items():
            assert normal[block_id]["prescription"]["sets"] == sets, block_id

    def test_deterministic(self):
        assert _resolve() == _resolve()


# ---------------------------------------------------------------------------
# 3. Engine: the family, the biceps rule, opt-in
# ---------------------------------------------------------------------------

class TestFamily:
    def test_registered(self):
        assert "arms_shoulders" in cv.FOCUS_FAMILIES
        assert cv.FAMILY_SESSIONS["arms_shoulders"] == (SID,)
        assert SID in cv.BICEPS_SESSIONS
        assert cv.family_of({"session_id": SID}) == "arms_shoulders"

    def test_default_rotation_unchanged(self):
        assert cv.DEFAULT_ROTATION == ("legs", "hiit", "z2", "upper_push_arms")
        for phase in PHASES:
            assert "arms_shoulders" not in cv.resolve_rotation(None, phase)
            assert "arms_shoulders" not in cv.resolve_rotation({}, phase)

    def test_validators_accept_the_family(self):
        rot = ["arms_shoulders", "legs", "hiit", "z2", "upper_push_arms"]
        assert cv.validate_structure(
            {"mon": {"lunch": {"role": "complementary", "max_minutes": 45, "focus": "arms_shoulders"}}},
            {"complementary_rotation": rot,
             "complementary_rotation_by_phase": {"deload": ["z2", "arms_shoulders"]}},
        ) == []
        assert cv.validate_structure(None, {"complementary_rotation": ["arms"]}) != []
        assert cv.resolve_rotation({"complementary_rotation": rot}, "base") == rot
        # Deload: HIIT → Z2 as before, the new family stays.
        assert cv.resolve_rotation({"complementary_rotation": rot}, "deload") == [
            "arms_shoulders", "legs", "z2", "z2", "upper_push_arms"]

    def test_put_state_accepts_the_family(self, tmp_path, monkeypatch):
        """PUT /api/state validates through validate_structure: the new family
        is accepted as a rotation entry and as a pinned focus."""
        api = a300.api.__wrapped__(tmp_path, monkeypatch)
        client, _deps = api
        av = _five_lunches()
        av["mon"]["lunch"]["focus"] = "arms_shoulders"
        r = client.put("/api/state", json={"availability": av, "planning_prefs": {"complementary_rotation": ROT5}})
        assert r.status_code == 200, r.text
        assert r.json()["planning_prefs"]["complementary_rotation"] == ROT5
        assert r.json()["availability"]["mon"]["lunch"]["focus"] == "arms_shoulders"

    def test_biceps_rule_applies(self):
        events = [{"offset": 0, "t": 19, "kinds": {"max", "heavy_pull"}, "date": "2026-10-19",
                   "session_id": "pulling_strength_gym"}]
        v = cv._violations(SID, 0, "lunch", events)
        assert [x["code"] for x in v] == ["biceps_before_heavy_pull"]
        # 24 h window only: the next day's evening heavy pull (30 h away) is fine.
        later = [{**events[0], "offset": 1, "t": 43}]
        assert cv._violations(SID, 0, "lunch", later) == []
        # Not HIIT, not legs: the other rules never fire on it.
        max_next = [{"offset": 1, "t": 43, "kinds": {"max", "limit", "outdoor"}, "date": "2026-10-20",
                     "session_id": "limit_boulder_gym"}]
        assert cv._violations(SID, 0, "lunch", max_next, frozenset({0})) == []

    def test_user_owned_session_is_flagged_before_a_heavy_pull(self):
        days = [{"date": "2026-10-19", "weekday": "mon", "sessions": [
            {"session_id": SID, "slot": "lunch", "status": "planned", "slot_role": "complementary",
             "focus": "arms_shoulders"},
            {"session_id": "pulling_strength_gym", "slot": "evening", "status": "planned",
             "intensity": "high", "tags": {"hard": True, "finger": False, "pulling": True}},
        ]}] + [{"date": f"2026-10-{20 + i}", "weekday": wd, "sessions": []}
               for i, wd in enumerate(("tue", "wed", "thu", "fri", "sat", "sun"))]
        wp = {"start_date": "2026-10-19", "weeks": [{"days": days}]}
        codes = [(w["code"], w["focus"]) for w in cv.complementary_warnings(wp, {})]
        assert codes == [("biceps_before_heavy_pull", "arms_shoulders")]


# ---------------------------------------------------------------------------
# 4. Placement: five lunches, five families
# ---------------------------------------------------------------------------

FIVE = ("mon", "tue", "wed", "thu", "fri")
ROT5 = ["arms_shoulders", "legs", "hiit", "z2", "upper_push_arms"]


def _five_lunches():
    av = a300.daniele_availability()
    av["mon"]["lunch"] = copy.deepcopy(av["tue"]["lunch"])
    return av


def _lunches(wp):
    out = {}
    for d in a300.days_of(wp):
        for s in d["sessions"]:
            if s.get("slot_role") == "complementary":
                out[d["weekday"]] = s
    return out


def lunches_by_date(wp):
    return {d["date"]: s["session_id"] for d in a300.days_of(wp) for s in d["sessions"]
            if s.get("slot_role") == "complementary"}


class TestPlacement:
    @pytest.mark.parametrize("phase", ("base", "strength_power", "power_endurance", "performance"))
    def test_five_lunches_get_five_different_families(self, phase):
        wp = a300.plan(phase, availability=_five_lunches(),
                       prefs={**a300.PREFS, "complementary_rotation": ROT5})
        lunches = _lunches(wp)
        assert sorted(lunches) == sorted(FIVE)
        fams = [lunches[wd]["focus"] for wd in FIVE]
        assert sorted(fams) == sorted(ROT5), fams
        s = next(x for x in lunches.values() if x["focus"] == "arms_shoulders")
        assert s["session_id"] == SID and s["gym_id"] == "work"
        assert wp["unmet_secondary"] == []
        # Penalties, never blocks: in a week with max days almost everywhere a
        # rule can be unavoidable (HIIT in performance) — then it is reported,
        # never silent, and it is never the new session's biceps rule.
        bad = a300.rule_violations(wp)
        reported = {(w["code"].split("_")[0], w["date"]) for w in wp["secondary_warnings"]}
        for kind, d, _with in bad:
            assert (kind, d) in reported, (kind, d, wp["secondary_warnings"])
        assert not [b for b in bad if b[0] == "biceps" and lunches_by_date(wp).get(b[1]) == SID]

    def test_rotation_order_maps_to_days_when_no_rule_is_in_the_way(self):
        """Ties go to the rotation order: with no rule in the way (no primary
        session at all), the k-th family of the rotation lands on the k-th
        complementary slot of the week — Monday gets the first one."""
        av = _five_lunches()
        for wd in a300.DAYS:
            av[wd]["evening"] = {"available": False}
        wp = a300.plan("base", availability=av, prefs={**a300.PREFS, "complementary_rotation": ROT5})
        lunches = _lunches(wp)
        assert [lunches[wd]["focus"] for wd in FIVE] == ROT5
        assert wp["secondary_warnings"] == []

    def test_deload_keeps_five_lunches_without_hiit(self):
        wp = a300.plan("deload", availability=_five_lunches(),
                       prefs={**a300.PREFS, "complementary_rotation": ROT5})
        fams = sorted(s["focus"] for s in _lunches(wp).values())
        assert fams == sorted(["arms_shoulders", "legs", "z2", "z2", "upper_push_arms"])

    def test_default_rotation_never_places_the_new_session(self):
        prefs = {k: v for k, v in a300.PREFS.items() if k != "complementary_rotation"}
        for phase in PHASES:
            wp = a300.plan(phase, availability=_five_lunches(), prefs=prefs)
            sids = {s["session_id"] for d in a300.days_of(wp) for s in d["sessions"]}
            assert SID not in sids, phase
