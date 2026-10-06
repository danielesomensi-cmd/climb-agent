"""C276 — try-hard in the catalog (decision 2 of the A305 Phase 2, 2026-10-06).

Before C276 the try-hard key of A294 could only be met by chance: the one
engine exercise that delivers it (``fall_practice``) entered a session only
through rotation, and the other try-hard drills are library-only. What is
pinned here:

1. ``lead_tryhard_gym`` — falls 8-10' right after the warm-up, then two lead
   routes with a declared rule (``lead_precision_feet_above_bolt``,
   ``lead_technique_under_pump``, pinned by id like C274). Needs rope routes,
   not hard, not finger, medium intensity, in no phase pool (A305 decides);
2. ``route_projecting_gym`` opens with 2-3 maintenance falls after the warm-up
   (athlete_plan §5), before the redpoint attempts, in every phase;
3. every pin is strict: without ``gym_routes`` the blocks fail loudly instead
   of degrading to a boulder drill; ``fall_practice`` requires ``gym_routes``
   in ``equipment_required``;
4. the A294 key catalog counts both sessions as try-hard — by session id while
   unresolved, by the fall exercise once resolved or logged.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.engine import key_sessions_v1 as ks
from backend.engine.exercise_ordering import enforce_ordering_constraints
from backend.engine.macrocycle_v1 import _build_session_pool
from backend.engine.planner_v2 import _SESSION_META
from backend.engine.resolve_session import resolve_session
from backend.engine.stimulus import is_finger_hard_session
from backend.tests.test_a294_key_sessions import _req, _sess, _state, _week

REPO = Path(__file__).resolve().parents[2]
SESSIONS = REPO / "backend" / "catalog" / "sessions" / "v1"
EXERCISES = "backend/catalog/exercises/v1/exercises.json"
PHASES = ("base", "strength_power", "power_endurance", "performance", "deload")

ROUTES_GYM = ["gym_boulder", "gym_routes", "hangboard", "pullup_bar", "dumbbell", "weight"]
BOULDER_ONLY = ["gym_boulder", "hangboard", "pullup_bar", "spraywall", "board_kilter", "dumbbell"]

TRYHARD_PINS = {
    "falls_block": "fall_practice",
    "route_feet_rule": "lead_precision_feet_above_bolt",
    "route_pump_rule": "lead_technique_under_pump",
}


def _session(sid: str) -> dict:
    return json.loads((SESSIONS / f"{sid}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog() -> dict:
    data = json.loads((REPO / EXERCISES).read_text(encoding="utf-8"))
    return {e["id"]: e for e in data["exercises"]}


def _user(equipment, *, date="2026-10-07") -> dict:
    return {
        "bodyweight_kg": 78.0,
        "body": {"weight_kg": 78.0, "age": 40},
        "assessment": {"experience": {"climbing_years": 16},
                       "grades": {"lead_max_rp": "8a+", "lead_max_os": "7b"}},
        "equipment": {"home": [], "gyms": [{"gym_id": "g", "name": "Gym", "equipment": list(equipment)}]},
        "working_loads": {"entries": [], "rules": {}},
        "context": {"location": "gym", "gym_id": "g", "target_date": date, "date": date},
    }


def _resolve(sid: str, equipment=ROUTES_GYM, phase="performance") -> dict:
    r = resolve_session(
        str(REPO), f"backend/catalog/sessions/v1/{sid}.json", "backend/catalog/templates", EXERCISES, "",
        user_state_override=_user(equipment), write_output=False, phase=phase,
    )
    r.pop("generated_at", None)
    return r


def _ids(r: dict) -> list:
    return [i["exercise_id"] for i in r["resolved_session"]["exercise_instances"]]


def _warmup_count(r: dict) -> int:
    """Instances that come from the warm-up template (the prefix the falls follow)."""
    n = 0
    for inst in r["resolved_session"]["exercise_instances"]:
        if "warmup" not in str(inst.get("block_uid") or ""):
            break
        n += 1
    return n


# ---------------------------------------------------------------------------
# 1. lead_tryhard_gym — catalog contract
# ---------------------------------------------------------------------------

class TestLeadTryhardContract:
    def test_needs_rope_routes_and_is_not_hard_or_finger(self):
        s = _session("lead_tryhard_gym")
        assert s["id"] == "lead_tryhard_gym"
        assert s["required_equipment"] == ["gym_routes"]
        assert s["tags"] == {"hard": False, "finger": False}
        assert s.get("boulder_fallback") is None
        assert not s.get("supplementary")
        meta = _SESSION_META["lead_tryhard_gym"]
        assert meta == {"hard": False, "finger": False, "intensity": "medium", "climbing": True,
                        "location": ("gym",), "required_equipment": ["gym_routes"], "max_per_week": 1}

    def test_blocks_are_pinned_by_id_and_strict(self):
        mods = {m.get("block_id"): m for m in _session("lead_tryhard_gym")["modules"] if m.get("block_id")}
        for block, eid in TRYHARD_PINS.items():
            prim = mods[block]["selection"]["primary"]
            assert prim["exercise_id"] == eid and prim["pin_strict"] is True, block
            assert mods[block]["required"] is True
        assert mods["falls_block"]["order"] == "after_warmup"

    def test_two_routes_one_each(self):
        mods = {m.get("block_id"): m for m in _session("lead_tryhard_gym")["modules"] if m.get("block_id")}
        for block in ("route_feet_rule", "route_pump_rule"):
            ov = mods[block]["selection"]["primary"]["prescription_overrides"]
            assert ov["sets"] == 1 and ov["reps"] == 1, block

    def test_falls_are_eight_to_ten_minutes(self):
        mods = {m.get("block_id"): m for m in _session("lead_tryhard_gym")["modules"] if m.get("block_id")}
        ov = mods["falls_block"]["selection"]["primary"]["prescription_overrides"]
        assert ov["sets"] * ov["reps"] == 9
        assert "8-10 min" in ov["notes"]

    def test_pump_route_never_above_onsight(self):
        """The library exercise is finger-hard 'when the routes are at or above
        onsight': the session caps the route so it stays not-finger."""
        mods = {m.get("block_id"): m for m in _session("lead_tryhard_gym")["modules"] if m.get("block_id")}
        notes = mods["route_pump_rule"]["selection"]["primary"]["prescription_overrides"]["notes"]
        assert "never above" in notes

    @pytest.mark.parametrize("discipline", ("lead", "boulder", "all_round"))
    def test_in_no_phase_pool(self, discipline):
        for phase in PHASES:
            assert "lead_tryhard_gym" not in _build_session_pool(phase, discipline), (phase, discipline)

    def test_not_finger_hard_planned_or_resolved(self):
        assert not is_finger_hard_session({"session_id": "lead_tryhard_gym"})
        r = _resolve("lead_tryhard_gym")
        resolved = {"session_id": "lead_tryhard_gym", "resolved": r}
        entries = [{"exercise_id": e} for e in _ids(r)]
        assert not is_finger_hard_session({"session_id": "lead_tryhard_gym", "exercises": entries}), resolved


# ---------------------------------------------------------------------------
# 2. Resolution
# ---------------------------------------------------------------------------

class TestResolution:
    @pytest.mark.parametrize("phase", PHASES)
    def test_lead_tryhard_resolves_falls_first_then_two_routes(self, phase):
        r = _resolve("lead_tryhard_gym", phase=phase)
        assert r["resolution_status"] == "success"
        ids = _ids(r)
        w = _warmup_count(r)
        assert w >= 1
        assert ids[w:w + 3] == ["fall_practice", "lead_precision_feet_above_bolt", "lead_technique_under_pump"]
        assert ids.count("fall_practice") == 1

    @pytest.mark.parametrize("phase", PHASES)
    def test_route_projecting_opens_with_two_to_three_falls(self, phase):
        r = _resolve("route_projecting_gym", phase=phase)
        assert r["resolution_status"] == "success"
        ids = _ids(r)
        w = _warmup_count(r)
        assert ids[w] == "fall_practice", ids
        assert ids.index("fall_practice") < ids.index("route_redpoint_attempt")
        falls = r["resolved_session"]["exercise_instances"][w]
        assert falls["prescription"]["sets"] == 1 and 2 <= falls["prescription"]["reps"] <= 3

    @pytest.mark.parametrize("sid", ("lead_tryhard_gym", "route_projecting_gym"))
    def test_deterministic(self, sid):
        assert _resolve(sid) == _resolve(sid)

    @pytest.mark.parametrize("phase", PHASES)
    def test_lead_tryhard_without_routes_fails_loudly(self, phase):
        r = _resolve("lead_tryhard_gym", equipment=BOULDER_ONLY, phase=phase)
        assert r["resolution_status"] == "failed"
        blocks = {b["block_id"]: b for b in r["resolved_session"]["blocks"]}
        for block in TRYHARD_PINS:
            assert blocks[block]["status"] == "failed" and blocks[block]["selected_exercises"] == [], block
        assert not set(_ids(r)) & set(TRYHARD_PINS.values())

    @pytest.mark.parametrize("phase", PHASES)
    def test_route_projecting_without_routes_fails_its_falls(self, phase):
        r = _resolve("route_projecting_gym", equipment=BOULDER_ONLY, phase=phase)
        assert r["resolution_status"] == "failed"
        blocks = {b["block_id"]: b for b in r["resolved_session"]["blocks"]}
        assert blocks["falls_primer"]["status"] == "failed"

    def test_strict_pins_allowlist(self):
        found = []
        for p in sorted(SESSIONS.glob("*.json")):
            for m in json.loads(p.read_text(encoding="utf-8")).get("modules") or []:
                if ((m.get("selection") or {}).get("primary") or {}).get("pin_strict"):
                    found.append((p.stem, m["block_id"]))
        assert found == [
            ("lead_tryhard_gym", "falls_block"),
            ("lead_tryhard_gym", "route_feet_rule"),
            ("lead_tryhard_gym", "route_pump_rule"),
            ("route_projecting_gym", "falls_primer"),
            ("treadmill_hiit_4x4", "hiit_intervals"),
        ]

    def test_after_warmup_order_only_where_declared(self):
        found = []
        for p in sorted(SESSIONS.glob("*.json")):
            for m in json.loads(p.read_text(encoding="utf-8")).get("modules") or []:
                if m.get("order"):
                    found.append((p.stem, m["block_id"], m["order"]))
        assert found == [("lead_tryhard_gym", "falls_block", "after_warmup"),
                         ("route_projecting_gym", "falls_primer", "after_warmup")]


# ---------------------------------------------------------------------------
# 3. fall_practice needs rope routes everywhere
# ---------------------------------------------------------------------------

class TestFallPracticeEquipment:
    def test_equipment_required_is_gym_routes(self, catalog):
        fp = catalog["fall_practice"]
        assert fp["equipment_required"] == ["gym_routes"]
        assert not fp.get("equipment_required_any")

    def test_never_resolves_without_routes(self):
        for sid in sorted(p.stem for p in SESSIONS.glob("*.json")):
            for phase in PHASES:
                try:
                    ids = _ids(_resolve(sid, equipment=BOULDER_ONLY, phase=phase))
                except Exception:
                    continue
                assert "fall_practice" not in ids, (sid, phase)


# ---------------------------------------------------------------------------
# 4. Ordering constraint (exercise_ordering, Constraint 6)
# ---------------------------------------------------------------------------

class TestAfterWarmupOrdering:
    LOOKUP = {
        "general_pulse_raise": {"role": ["warmup"], "domain": ["aerobic_capacity"]},
        "route_redpoint_attempt": {"role": ["main"], "domain": ["climbing_routes"]},
        "fall_practice": {"role": ["technique"], "domain": ["technique_lead"]},
        "side_plank": {"role": ["accessory"], "domain": ["core"]},
    }

    def test_declared_instance_moves_right_after_warmup(self):
        exs = [{"exercise_id": "general_pulse_raise"}, {"exercise_id": "route_redpoint_attempt"},
               {"exercise_id": "fall_practice", "source": {"order": "after_warmup"}},
               {"exercise_id": "side_plank"}]
        out = enforce_ordering_constraints(exs, "performance", self.LOOKUP)
        assert [e["exercise_id"] for e in out] == ["general_pulse_raise", "fall_practice",
                                                   "route_redpoint_attempt", "side_plank"]

    def test_undeclared_instance_does_not_move(self):
        exs = [{"exercise_id": "general_pulse_raise"}, {"exercise_id": "route_redpoint_attempt"},
               {"exercise_id": "fall_practice"}, {"exercise_id": "side_plank"}]
        out = enforce_ordering_constraints(deepcopy(exs), "performance", self.LOOKUP)
        assert [e["exercise_id"] for e in out] == [e["exercise_id"] for e in exs]


# ---------------------------------------------------------------------------
# 5. A294 key catalog: both sessions deliver try_hard
# ---------------------------------------------------------------------------

def _tryhard_req():
    return next(r for r in ks.phase_requirements("performance") if r["key"] == "try_hard")


class TestKeyCatalog:
    def test_catalog_lists_the_two_sessions(self):
        req = _tryhard_req()
        assert req["session_ids"] == ["lead_tryhard_gym", "route_projecting_gym"]
        assert req["propose"] == []  # A294 proposals unchanged: A305 decides

    @pytest.mark.parametrize("sid", ("lead_tryhard_gym", "route_projecting_gym"))
    def test_unresolved_session_counts(self, sid):
        assert ks.tryhard_hit({"session_id": sid}, _tryhard_req())

    @pytest.mark.parametrize("sid", ("lead_tryhard_gym", "route_projecting_gym"))
    def test_resolved_session_counts_through_its_falls(self, sid):
        r = _resolve(sid)
        s = {"session_id": sid, "exercises": [{"exercise_id": e} for e in _ids(r)]}
        assert ks.tryhard_hit(s, _tryhard_req())

    def test_falls_removed_by_hand_do_not_count(self):
        r = _resolve("route_projecting_gym")
        s = {"session_id": "route_projecting_gym",
             "exercises": [{"exercise_id": e} for e in _ids(r) if e != "fall_practice"]}
        assert not ks.tryhard_hit(s, _tryhard_req())

    def test_logged_without_falls_does_not_count(self):
        s = {"session_id": "lead_tryhard_gym", "status": "done",
             "actual_exercises": [{"exercise_id": "lead_technique_under_pump", "completed_sets": 1},
                                  {"exercise_id": "fall_practice", "completed": False}]}
        assert not ks.tryhard_hit(s, _tryhard_req())

    def test_limit_session_alone_still_does_not_count(self):
        """A294 finding 9 unchanged."""
        for sid in ("limit_boulder_gym", "power_contact_gym", "technique_focus_gym"):
            assert not ks.tryhard_hit({"session_id": sid}, _tryhard_req()), sid

    def test_session_keys_never_list_try_hard(self):
        for phase in ("strength_power", "power_endurance", "performance"):
            keys = ks.session_keys({"session_id": "lead_tryhard_gym"}, phase)
            assert "try_hard" not in keys

    def test_resolved_tryhard_session_is_also_feet_and_positioning_technique(self):
        """The two route rules are feet / positioning drills (recency
        technique_lead_rules), so a resolved lead_tryhard_gym also delivers the
        technique key — the falls do not count towards it."""
        cat = ks.load_exercise_catalog()
        r = _resolve("lead_tryhard_gym")
        s = {"session_id": "lead_tryhard_gym", "exercises": [{"exercise_id": e} for e in _ids(r)]}
        assert ks.technique_hit(s, cat)
        only_falls = {"session_id": "lead_tryhard_gym", "exercises": [{"exercise_id": "fall_practice"}]}
        assert not ks.technique_hit(only_falls, cat)

    def test_planned_tryhard_session_closes_the_week_key(self):
        st = _state()
        days = st["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        assert _req(ks.compute_key_status(st, "2026-10-05"), "try_hard")["status"] == "missing"
        days[3]["sessions"] = [_sess("evening", "lead_tryhard_gym")]
        th = _req(ks.compute_key_status(st, "2026-10-05"), "try_hard")
        assert th["status"] == "planned" and th["debt"] == 0

    def test_performance_project_session_closes_try_hard(self):
        st = _state()
        st["week_plans"]["2026-11-16"] = _week(
            "2026-11-16", {"2026-11-18": [_sess("evening", "route_projecting_gym")],
                           "2026-11-16": [_sess("evening", "technique_focus_gym")]},
            phase="performance")
        s = ks.compute_key_status(st, "2026-11-16")
        assert _req(s, "project")["status"] == "planned"
        th = _req(s, "try_hard")
        assert th["status"] == "planned" and th["debt"] == 0


# ---------------------------------------------------------------------------
# 6. English catalog text
# ---------------------------------------------------------------------------

def test_catalog_text_is_english():
    italian = (" il ", " la ", " le ", " di ", " per ", " cadute", " via ", " vie ", " sessione", " palestra")
    for sid in ("lead_tryhard_gym", "route_projecting_gym"):
        blob = json.dumps(_session(sid), ensure_ascii=False).lower()
        for w in italian:
            assert w not in blob, (sid, w)
