"""C274 — lunch complementary sessions (catalog).

Four supplementary sessions sized for a 45-minute gross lunch break (about 35
useful minutes) at a weights gym with a treadmill:

- ``treadmill_hiit_4x4``     — VO2max 4x4 on the treadmill, ``tags.hiit`` true;
- ``treadmill_zone2_cardio`` — Zone 2 incline walk + optional hip mobility;
- ``upper_push_arms_lunch``  — chest press, triceps, biceps;
- ``legs_maintenance_lunch`` — goblet squat, RDL and a short foot-strength block.

What is pinned here:

1. catalog contract — supplementary, lunch-compatible, no climbing / finger
   load, one HIIT flag in the catalog, equipment the user can declare;
2. resolution — each session resolves at a gym with weights + cable + treadmill
   to the intended exercises, inside the lunch budget, deterministically;
3. opt-in — the sessions are in no phase pool, so a generated week is the same
   with or without the treadmill, and a gym without one never gets the HIIT
   exercise; a quick-add of a lunch session touches nothing but its own slot.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.api.routers.onboarding import EQUIPMENT_GYM
from backend.engine.custom_session import estimate_custom_session_duration
from backend.engine.equipment_utils import KNOWN_EQUIPMENT_KEYS
from backend.engine.macrocycle_v1 import _BASE_WEIGHTS, _adjust_domain_weights, _build_session_pool
from backend.engine.planner_v2 import _SESSION_META, generate_phase_week
from backend.engine.replanner_v1 import apply_day_add
from backend.engine.resolve_session import resolve_session

REPO = Path(__file__).resolve().parents[2]
SESSIONS = REPO / "backend" / "catalog" / "sessions" / "v1"
EXERCISES = "backend/catalog/exercises/v1/exercises.json"

LUNCH = ("treadmill_hiit_4x4", "treadmill_zone2_cardio", "upper_push_arms_lunch", "legs_maintenance_lunch")
PHASES = ("base", "strength_power", "power_endurance", "performance", "deload")

WORK_GYM = ["barbell", "cable_machine", "dumbbell", "bench", "pullup_bar", "weight", "treadmill"]

EXPECTED = {
    "treadmill_hiit_4x4": ["general_pulse_raise", "treadmill_hiit_4x4"],
    "treadmill_zone2_cardio": ["treadmill_incline_walk", "hip_opener_flow"],
    "upper_push_arms_lunch": ["general_pulse_raise", "bench_press", "bicep_curl", "triceps_cable_pushdown"],
    "legs_maintenance_lunch": ["general_pulse_raise", "edge_calf_raise_bigtoe", "goblet_squat",
                               "romanian_deadlift", "toe_flexor_isometric"],
}


def _session(sid: str) -> dict:
    return json.loads((SESSIONS / f"{sid}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog() -> dict:
    data = json.loads((REPO / EXERCISES).read_text(encoding="utf-8"))
    return {e["id"]: e for e in data["exercises"]}


def _state(equipment, *, date="2026-10-07") -> dict:
    return {
        "bodyweight_kg": 78.0,
        "body": {"weight_kg": 78.0, "age": 40},
        "assessment": {"experience": {"climbing_years": 16}},
        "equipment": {"home": [], "gyms": [{"gym_id": "work", "name": "Work", "equipment": list(equipment)}]},
        "working_loads": {"entries": [], "rules": {}},
        "context": {"location": "gym", "gym_id": "work", "target_date": date, "date": date},
    }


def _resolve(sid: str, equipment=WORK_GYM, phase="base") -> dict:
    r = resolve_session(
        str(REPO), f"backend/catalog/sessions/v1/{sid}.json", "backend/catalog/templates", EXERCISES, "",
        user_state_override=_state(equipment), write_output=False, phase=phase,
    )
    r.pop("generated_at", None)
    return r


def _ids(r: dict) -> list:
    return [i["exercise_id"] for i in r["resolved_session"]["exercise_instances"]]


# ---------------------------------------------------------------------------
# 1. Catalog contract
# ---------------------------------------------------------------------------

class TestCatalogContract:
    @pytest.mark.parametrize("sid", LUNCH)
    def test_supplementary_and_lunch_compatible(self, sid):
        s = _session(sid)
        assert s["id"] == sid
        assert s["supplementary"] is True
        assert "lunch_short" in s["compatibility"]["slot"]
        tb = s["time_budget"]
        assert tb["target_duration_min"] <= 35 and tb["hard_cap_min"] == 45

    @pytest.mark.parametrize("sid", LUNCH)
    def test_no_climbing_or_finger_load(self, sid, catalog):
        s = _session(sid)
        assert s["tags"]["hard"] is False and s["tags"]["finger"] is False
        meta = _SESSION_META[sid]
        assert meta["hard"] is False and meta["finger"] is False and meta["climbing"] is False
        assert not meta.get("pulling")
        for eid in _ids(_resolve(sid)):
            e = catalog[eid]
            assert (e.get("stress_tags") or {}).get("fingers") in ("none", None), eid
            assert not set(e.get("equipment_required") or []) & {
                "hangboard", "hangboard_20mm", "loading_pin", "campus_board", "gym_boulder", "gym_routes"}, eid

    def test_hiit_flag_is_a_catalog_tag_on_one_session_only(self):
        flagged = sorted(p.stem for p in SESSIONS.glob("*.json")
                         if (json.loads(p.read_text(encoding="utf-8")).get("tags") or {}).get("hiit"))
        assert flagged == ["treadmill_hiit_4x4"]
        # one source: the planner meta does not duplicate the flag
        assert not any("hiit" in m for m in _SESSION_META.values())
        # HIIT does not consume the hard / finger cap (decision 2026-10-05)
        assert _SESSION_META["treadmill_hiit_4x4"]["hard"] is False
        assert _SESSION_META["treadmill_hiit_4x4"]["max_per_week"] == 1

    @pytest.mark.parametrize("sid", LUNCH)
    def test_equipment_is_declarable_and_meta_matches_catalog(self, sid):
        s = _session(sid)
        assert set(s["required_equipment"]) <= KNOWN_EQUIPMENT_KEYS
        assert set(s["required_equipment"]) == set(_SESSION_META[sid]["required_equipment"])
        assert _SESSION_META[sid]["location"] == ("gym",)

    def test_treadmill_is_a_gym_equipment_option(self):
        assert "treadmill" in KNOWN_EQUIPMENT_KEYS
        assert "treadmill" in {item["id"] for item in EQUIPMENT_GYM}
        assert _session("treadmill_hiit_4x4")["required_equipment"] == ["treadmill"]
        assert _session("treadmill_zone2_cardio")["required_equipment"] == ["treadmill"]

    def test_treadmill_interval_exercise(self, catalog):
        e = catalog["treadmill_hiit_4x4"]
        assert e["equipment_required"] == ["treadmill"]
        assert e["intensity_level"] == "high" and e["load_model"] == "bodyweight_only"
        rx = e["prescription_defaults"]
        assert (rx["sets"], rx["work_seconds"], rx["rest_between_sets_seconds"]) == (4, 240, 180)
        assert e["stress_tags"]["fingers"] == "none" and e["stress_tags"]["elbow"] == "none"

    def test_no_new_movement_pattern(self, catalog):
        new = catalog["treadmill_hiit_4x4"]
        others = {e.get("pattern") for k, e in catalog.items() if k != "treadmill_hiit_4x4"
                  and isinstance(e.get("pattern"), str)}
        assert new["pattern"] in others


# ---------------------------------------------------------------------------
# 2. Resolution at the Work gym (weights + cable + treadmill)
# ---------------------------------------------------------------------------

class TestResolution:
    @pytest.mark.parametrize("sid", LUNCH)
    def test_resolves_to_the_intended_exercises(self, sid):
        r = _resolve(sid)
        assert r["resolution_status"] == "success"
        assert _ids(r) == EXPECTED[sid]

    @pytest.mark.parametrize("sid", LUNCH)
    @pytest.mark.parametrize("phase", PHASES)
    def test_fits_the_lunch_budget_in_every_phase(self, sid, phase, catalog):
        r = _resolve(sid, phase=phase)
        rows = []
        for inst in r["resolved_session"]["exercise_instances"]:
            rx = dict(inst.get("prescription") or {})
            rx["alt_sides"] = bool(catalog[inst["exercise_id"]].get("alt_sides"))
            rows.append(rx)
        minutes = estimate_custom_session_duration(rows)
        assert 15 <= minutes <= _session(sid)["time_budget"]["target_duration_min"], (sid, phase, minutes)

    def test_foot_block_is_five_to_eight_minutes(self, catalog):
        r = _resolve("legs_maintenance_lunch")
        rows = []
        for inst in r["resolved_session"]["exercise_instances"]:
            if inst["exercise_id"] in ("toe_flexor_isometric", "edge_calf_raise_bigtoe"):
                rows.append({**inst["prescription"], "alt_sides": True})
        assert len(rows) == 2
        assert 5 <= estimate_custom_session_duration(rows) <= 8

    def test_hiit_intervals_and_warmup_order(self):
        insts = _resolve("treadmill_hiit_4x4")["resolved_session"]["exercise_instances"]
        warm, main = insts
        assert warm["exercise_id"] == "general_pulse_raise" and warm["prescription"]["work_seconds"] == 480
        assert main["prescription"]["sets"] == 4 and main["prescription"]["work_seconds"] == 240

    def test_biceps_block_never_picks_a_weighted_pull(self):
        for phase in PHASES:
            ids = _ids(_resolve("upper_push_arms_lunch", phase=phase))
            assert not [i for i in ids if "chinup" in i or "pullup" in i], (phase, ids)

    @pytest.mark.parametrize("sid", LUNCH)
    def test_deterministic(self, sid):
        assert _resolve(sid) == _resolve(sid)

    def test_without_a_treadmill_the_hiit_exercise_never_resolves(self):
        no_treadmill = [e for e in WORK_GYM if e != "treadmill"]
        for sid in sorted(p.stem for p in SESSIONS.glob("*.json")):
            for phase in PHASES:
                try:
                    ids = _ids(_resolve(sid, equipment=no_treadmill, phase=phase))
                except Exception:
                    continue
                assert "treadmill_hiit_4x4" not in ids, (sid, phase)


# ---------------------------------------------------------------------------
# 3. Opt-in: no generated week changes, quick-add touches only its slot
# ---------------------------------------------------------------------------

def _week_kwargs(phase_id: str, gym_equipment: list) -> dict:
    profile = {"finger_strength": 60, "pulling_strength": 55, "power_endurance": 45,
               "technique": 50, "endurance": 40}
    avail = {d: {"lunch": {"available": True, "locations": ["gym"]},
                 "evening": {"available": True, "locations": ["gym", "home"]}}
             for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    return dict(
        phase_id=phase_id,
        domain_weights=_adjust_domain_weights(_BASE_WEIGHTS[phase_id], profile),
        session_pool=_build_session_pool(phase_id),
        start_date="2026-10-05",
        availability=avail,
        allowed_locations=["home", "gym"],
        hard_cap_per_week=3,
        planning_prefs={"target_training_days_per_week": 6, "hard_day_cap_per_week": 3},
        default_gym_id="work",
        gyms=[{"gym_id": "work", "equipment": gym_equipment}],
        home_equipment=["hangboard", "pullup_bar"],
    )


class TestOptIn:
    @pytest.mark.parametrize("discipline", ("lead", "boulder", "all_round"))
    def test_lunch_sessions_are_in_no_phase_pool(self, discipline):
        for phase in PHASES:
            assert not set(_build_session_pool(phase, discipline)) & set(LUNCH), (phase, discipline)

    @pytest.mark.parametrize("phase", PHASES)
    def test_declaring_a_treadmill_changes_no_generated_week(self, phase):
        climbing = ["gym_boulder", "gym_routes", "hangboard", "dumbbell", "weight", "pullup_bar", "cable_machine"]
        without = generate_phase_week(**_week_kwargs(phase, climbing))
        with_tm = generate_phase_week(**_week_kwargs(phase, climbing + ["treadmill"]))
        assert json.dumps(without, sort_keys=True, default=str) == json.dumps(with_tm, sort_keys=True, default=str)
        planned = {s["session_id"] for d in with_tm["weeks"][0]["days"] for s in d["sessions"]}
        assert not planned & set(LUNCH)

    @pytest.mark.parametrize("sid", LUNCH)
    def test_quick_add_at_lunch_touches_only_its_slot(self, sid):
        plan = {
            "start_date": "2026-10-05",
            "profile_snapshot": {"phase_id": "base"},
            "weeks": [{"days": [
                {"date": "2026-10-05", "sessions": [{
                    "session_id": "technique_focus_gym", "slot": "evening", "location": "gym",
                    "status": "done", "intensity": "medium", "tags": {"hard": False, "finger": False},
                    "feedback": {"rating": "ok"}, "completed_at": "2026-10-05T20:00:00",
                }]},
                {"date": "2026-10-06", "sessions": [{
                    "session_id": "limit_boulder_gym", "slot": "evening", "location": "gym",
                    "status": "planned", "intensity": "max", "tags": {"hard": True, "finger": True},
                }]},
                {"date": "2026-10-07", "sessions": []},
            ]}],
        }
        before = deepcopy(plan)
        updated, _warnings, adjustments = apply_day_add(
            plan, session_id=sid, target_date="2026-10-06", slot="lunch", location="gym",
            gym_id="work", today="2026-10-06",
        )
        assert plan == before  # input untouched
        days = {d["date"]: d for d in updated["weeks"][0]["days"]}
        # past session immutable, the evening key session untouched
        assert days["2026-10-05"] == before["weeks"][0]["days"][0]
        by_slot = {x["slot"]: x for x in days["2026-10-06"]["sessions"]}
        assert set(by_slot) == {"lunch", "evening"}
        assert by_slot["evening"] == before["weeks"][0]["days"][1]["sessions"][0]
        added = by_slot["lunch"]
        assert added["session_id"] == sid and added["slot"] == "lunch"
        assert added["tags"]["hard"] is False and added["tags"]["finger"] is False
        assert adjustments == []
