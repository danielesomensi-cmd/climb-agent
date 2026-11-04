"""B413 (D4) — the floor core of the catalog lunches follows the athlete's ladder.

Before B413 the core blocks of the four lunches were pinned (hollow hold,
side plank): the ladder stage only ever touched free picks, so a tested
athlete at L-sit / ab-wheel / Copenhagen dynamic was handed a 3x30 s hollow
hold three times a week. Now a pinned block that declares ``ladder_pin``
(catalog, top level of the block — never in ``selection``) is replaced, for a
tested athlete with an entry, by his level of the first family that has one:

| lunch | hollow block | lateral block |
|---|---|---|
| arms (Mon) | L-sit, rollout | his lateral level |
| HIIT (Tue) | rollout, L-sit | one level below (A2), top of its band |
| legs | rollout | — (the A/B rotation block) |
| push (Fri) | L-sit | — (the A/B rotation block) |

then the pinned exercise's own family (hollow ladder), then the catalog pin.
Never a hanging or heavy-pull level, one family per session, R12 caps, the
pin level exempt from the phase affinity (nothing else is), the catalog dose
as a floor of a SEEDED level on the pinned exercise, the chosen exercise's
own notes. Untested athletes and athletes with no entry: bit for bit.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from backend.engine import bw_ladders as bl
from backend.engine import bw_progression as bp
from backend.engine import resolve_session as rs
from backend.engine.custom_session import estimate_custom_session_duration
from backend.engine.progression_v1 import apply_feedback
from backend.engine.stimulus import is_finger_hard_session, is_pulling_hard_session, session_stimuli
from backend.tests import b413_lunch_golden_cases as lg
from backend.tests import c272_golden_cases as golden

REPO = Path(__file__).resolve().parents[2]
SESSIONS = REPO / "backend" / "catalog" / "sessions" / "v1"
TEMPLATES = REPO / "backend" / "catalog" / "templates"
EXERCISES = "backend/catalog/exercises/v1/exercises.json"
GOLDEN = Path(__file__).parent / "fixtures" / "b413_lunch_ladder_golden.json"

ARMS, HIIT, LEGS, PUSH = lg.LUNCHES
PHASES = ("base", "strength_power", "power_endurance", "performance", "deload")
DATES = ("2026-11-10", "2026-11-17")  # performance, two A/B weeks

#: (session, block) → ladder_pin of the catalog (the Phase-1 family table, A2).
PINS = {
    (ARMS, "core_lateral"): {"families": ["lateral"]},
    (ARMS, "core_anti_extension"): {"families": ["compression_floor", "rollout"]},
    (HIIT, "core_anti_extension"): {"families": ["rollout", "compression_floor"]},
    (HIIT, "core_lateral"): {"families": ["lateral"], "level_offset": -1},
    (LEGS, "core_anti_extension"): {"families": ["rollout"]},
    (PUSH, "core_anti_extension"): {"families": ["compression_floor"]},
}
#: The filters of the pinned blocks before D4 (the "without ladder_pin" catalog).
PRE_D4_FILTERS = {
    "core_lateral": {"pattern": ["anti_lateral_flexion"], "intensity_max": "medium"},
    "core_anti_extension": {"pattern": ["anti_extension"]},
}
HOLLOW_NOTE = "3 x 30 s hollow hold"


@pytest.fixture(scope="module")
def catalog() -> dict:
    data = json.loads((REPO / EXERCISES).read_text(encoding="utf-8"))
    return {e["id"]: e for e in data["exercises"]}


@pytest.fixture(scope="module")
def pre_d4_dir(tmp_path_factory) -> Path:
    """A copy of the session catalog with every ``ladder_pin`` removed and the
    pinned blocks' filters as they were before D4 (the BSS rest stays)."""
    out = tmp_path_factory.mktemp("sessions_pre_d4")
    for p in SESSIONS.glob("*.json"):
        shutil.copy(p, out / p.name)
    for sid in lg.LUNCHES:
        doc = json.loads((SESSIONS / f"{sid}.json").read_text(encoding="utf-8"))
        for m in doc["modules"]:
            if m.pop("ladder_pin", None) is not None:
                m["selection"]["primary"]["filters"].update(copy.deepcopy(PRE_D4_FILTERS[m["block_id"]]))
        (out / f"{sid}.json").write_text(json.dumps(doc), encoding="utf-8")
    return out


def _resolve(sid: str, state: dict, phase: str, session_dir: Path = SESSIONS) -> dict:
    r = rs.resolve_session(
        str(REPO), str(session_dir / f"{sid}.json"), "backend/catalog/templates", EXERCISES, "",
        user_state_override=copy.deepcopy(state), write_output=False, phase=phase,
    )
    r.pop("generated_at", None)
    # The source path is the only field that says which directory was read.
    r["session"]["source_path"] = f"backend/catalog/sessions/v1/{sid}.json"
    return r


def _insts(r: dict) -> list:
    return r["resolved_session"]["exercise_instances"]


def _block(r: dict, block_id: str) -> dict:
    return next(i for i in _insts(r) if i["source"]["block_id"] == block_id)


def _rx(inst: dict) -> tuple:
    p = inst["prescription"]
    return inst["exercise_id"], p.get("sets"), p.get("work_seconds") or p.get("reps")


def _state(date: str = "2026-11-10", levels=None, equipment=None) -> dict:
    st = lg.daniele_state(date, levels)
    if equipment is not None:
        st["equipment"]["gyms"][-1]["equipment"] = list(equipment)
    return st


def _levels(**over) -> dict:
    out = copy.deepcopy(lg.DANIELE_LEVELS)
    for fam, entry in over.items():
        if entry is None:
            out.pop(fam, None)
        else:
            out[fam] = entry
    return out


def _untested(date: str) -> dict:
    st = copy.deepcopy(golden.profiles()["untested"])
    st["equipment"]["gyms"].append({"gym_id": "work", "name": "Work", "priority": 2, "equipment": list(lg.WORK)})
    st["context"] = {"location": "gym", "gym_id": "work", "target_date": date, "date": date}
    return st


def _no_entry(date: str) -> dict:
    """Tested (test logs < 90 d) but no ladder entry: no history, no levels."""
    st = _state(date, levels={})
    st["week_plans"] = {}
    return st


# ---------------------------------------------------------------------------
# Unchanged: untested athletes and athletes without an entry
# ---------------------------------------------------------------------------

class TestUntestedUnchanged:
    @pytest.mark.parametrize("sid", lg.LUNCHES)
    @pytest.mark.parametrize("phase", PHASES)
    def test_bit_for_bit_vs_the_catalog_without_ladder_pin(self, sid, phase, pre_d4_dir):
        for date in DATES:
            st = _untested(date)
            assert _resolve(sid, st, phase) == _resolve(sid, st, phase, pre_d4_dir)

    def test_untested_keeps_the_catalog_core(self):
        r = _resolve(ARMS, _untested("2026-11-10"), "performance")
        assert _rx(_block(r, "core_anti_extension")) == ("core_hollow_hold", 3, 30)
        assert _rx(_block(r, "core_lateral")) == ("side_plank", 3, 30)
        assert _block(r, "core_lateral")["source"]["picked_by"] == "resolver_v0.2/explicit_exercise_id"


class TestNoEntryUnchanged:
    @pytest.mark.parametrize("sid", lg.LUNCHES)
    @pytest.mark.parametrize("phase", PHASES)
    def test_bit_for_bit_vs_the_catalog_without_ladder_pin(self, sid, phase, pre_d4_dir):
        for date in DATES:
            st = _no_entry(date)
            assert bp.tested(st, date)
            assert _resolve(sid, st, phase) == _resolve(sid, st, phase, pre_d4_dir)

    def test_entries_only_in_other_families_change_nothing(self, pre_d4_dir):
        st = _state(levels={"push_horizontal": {"level_idx": 2, "sets": 3, "target": 6, "source": "user_edit"}})
        st["week_plans"] = {}
        for sid in lg.LUNCHES:
            assert _resolve(sid, st, "strength_power") == _resolve(sid, st, "strength_power", pre_d4_dir)


# ---------------------------------------------------------------------------
# The lateral block
# ---------------------------------------------------------------------------

class TestLateralFollowsLadder:
    def test_arms_gets_his_level(self):
        inst = _block(_resolve(ARMS, _state(), "performance"), "core_lateral")
        assert _rx(inst) == ("copenhagen_dynamic", 3, 6)
        assert inst["prescription"]["source"] == "bw_ladder"
        assert inst["source"]["picked_by"] == "resolver_v0.2/ladder_pin"
        assert inst["suggested"]["measure"] == "bw_reps"
        assert "level_offset" not in inst["suggested"]["bw_ladder"]["ladder"]

    def test_hiit_is_one_level_below_at_the_top_of_its_band(self):
        """A2: never the dynamic Copenhagen two days in a row (Mon arms, Tue
        HIIT) — the HIIT day gets the mastered level below, no switch offer."""
        inst = _block(_resolve(HIIT, _state(), "performance"), "core_lateral")
        assert _rx(inst) == ("copenhagen_plank", 3, 20)
        ladder = inst["suggested"]["bw_ladder"]["ladder"]
        assert ladder["level_offset"] == -1 and ladder["proposal"] is None
        assert ladder["entry_level_idx"] == 3 and ladder["level_idx"] == 2
        assert "measure" not in inst["suggested"]  # a mastered level is not measured

    @pytest.mark.parametrize("lvl,arms,hiit", [
        (0, ("side_plank", 3, 15), ("side_plank", 3, 15)),             # floor L0: his own dose
        (1, ("copenhagen_short_lever", 3, 15), ("side_plank", 3, 30)),
        (2, ("copenhagen_plank", 3, 15), ("copenhagen_short_lever", 3, 20)),  # anti_rotation: widened pattern
        (3, ("copenhagen_dynamic", 3, 9), ("copenhagen_plank", 3, 20)),       # high: widened intensity
    ])
    def test_every_lateral_level(self, lvl, arms, hiit):
        target = {0: 15, 1: 15, 2: 15, 3: 9}[lvl]
        st = _state(levels=_levels(lateral={"level_idx": lvl, "sets": 3, "target": target, "source": "feedback"}))
        assert _rx(_block(_resolve(ARMS, st, "strength_power"), "core_lateral")) == arms
        hi = _block(_resolve(HIIT, st, "strength_power"), "core_lateral")
        assert _rx(hi) == hiit
        assert ("level_offset" in hi["suggested"]["bw_ladder"]["ladder"]) is (lvl > 0)

    def test_without_a_bench_the_dynamic_walks_down(self):
        """Copenhagen dynamic needs a bench: the walk goes down, and only the
        pin level is exempt from the phase affinity — the Copenhagen plank
        (base / PE) is taken in power endurance, not in strength & power."""
        eq = [e for e in lg.WORK if e != "bench"]
        inst = _block(_resolve(ARMS, _state(equipment=eq), "power_endurance"), "core_lateral")
        assert _rx(inst) == ("copenhagen_plank", 3, 20)  # mastered level, top of its band
        inst = _block(_resolve(ARMS, _state(equipment=eq), "strength_power"), "core_lateral")
        assert _rx(inst) == ("side_plank", 3, 30) and inst["prescription"]["source"] == "bw_ladder"


# ---------------------------------------------------------------------------
# The hollow block: the anti-extension families of each lunch
# ---------------------------------------------------------------------------

class TestAntiExtensionCrossFamily:
    def test_daniele_levels(self):
        st = _state()
        assert _rx(_block(_resolve(ARMS, st, "performance"), "core_anti_extension")) == ("core_l_sit", 4, 10)
        assert _rx(_block(_resolve(HIIT, st, "performance"), "core_anti_extension")) == ("ab_wheel_rollout", 3, 10)
        assert _rx(_block(_resolve(LEGS, st, "performance"), "core_anti_extension")) == ("ab_wheel_rollout", 3, 10)
        assert _rx(_block(_resolve(PUSH, st, "performance"), "core_anti_extension")) == ("core_l_sit", 4, 10)

    def test_first_family_without_entry_falls_to_the_second(self):
        st = _state(levels=_levels(compression_floor=None))
        assert _rx(_block(_resolve(ARMS, st, "strength_power"), "core_anti_extension")) == ("ab_wheel_rollout", 3, 10)
        st = _state(levels=_levels(rollout=None))
        assert _rx(_block(_resolve(HIIT, st, "strength_power"), "core_anti_extension")) == ("core_l_sit", 4, 10)

    def test_without_an_ab_wheel_the_hiit_takes_the_l_sit(self):
        eq = [e for e in lg.WORK if e != "ab_wheel"]
        st = _state(equipment=eq)
        assert _rx(_block(_resolve(HIIT, st, "strength_power"), "core_anti_extension")) == ("core_l_sit", 4, 10)

    def test_no_family_entry_follows_the_hollow_ladder_then_the_catalog(self):
        st = _state(levels=_levels(rollout=None, compression_floor=None))
        inst = _block(_resolve(LEGS, st, "strength_power"), "core_anti_extension")
        assert _rx(inst) == ("core_hollow_hold", 3, 30) and inst["prescription"]["source"] == "bw_ladder"
        st = _state(levels=_levels(rollout=None, compression_floor=None,
                                   hollow_plank={"level_idx": 3, "sets": 3, "target": 20, "source": "user_edit"}))
        assert _rx(_block(_resolve(LEGS, st, "strength_power"), "core_anti_extension")) == ("hollow_rock", 3, 20)
        st = _state(levels=_levels(rollout=None, compression_floor=None, hollow_plank=None))
        st["week_plans"] = {}
        inst = _block(_resolve(LEGS, st, "strength_power"), "core_anti_extension")
        assert _rx(inst) == ("core_hollow_hold", 3, 30)
        assert inst["source"]["picked_by"] == "resolver_v0.2/explicit_exercise_id"
        assert "source" not in inst["prescription"]

    def test_a_compression_level_reaches_the_block(self):
        """Straddle L-sit (pattern compression): the hollow blocks with the
        L-sit family accept it — otherwise the lunch would stall at core_l_sit."""
        st = _state(levels=_levels(compression_floor={"level_idx": 3, "sets": 3, "target": 15,
                                                      "source": "feedback"}))
        assert _rx(_block(_resolve(PUSH, st, "performance"), "core_anti_extension")) == ("straddle_l_sit", 3, 15)

    def test_one_family_per_session(self):
        for sid in lg.LUNCHES:
            for date, phase in lg.DANIELE_SLOTS:
                r = _resolve(sid, _state(date), phase)
                fams = [bl.family_of(i["exercise_id"], date)[0] for i in _insts(r)
                        if i["source"]["block_id"].startswith("core") and bl.family_of(i["exercise_id"], date)]
                assert len(fams) == len(set(fams)), (sid, date, fams)

    def test_a_used_family_is_skipped(self, catalog):
        st = _state()
        ctx = bp.build_resolve_context(st, "2026-11-10", "strength_power")
        ctx["used_families"].add("compression_floor")
        picked = rs._bw_ladder_pin_stage(
            ctx, PINS[(ARMS, "core_anti_extension")], catalog["core_hollow_hold"], list(catalog.values()),
            location="gym", available_equipment=list(lg.WORK), role_req=["accessory"], domain_req=["core"],
            pattern_req=["anti_extension", "compression"], intensity_max="high", limitation_map={},
            finger_device=None, user_age=40, experience_years=16)
        assert picked is not None and picked[0]["id"] == "ab_wheel_rollout"


# ---------------------------------------------------------------------------
# Pin floor, hanging guard, lower back
# ---------------------------------------------------------------------------

def _with_entries(monkeypatch, entries: dict) -> None:
    """The ladder sees exactly these entries (normalised), whatever the state."""
    def fake(state, ref_date, **kw):
        if kw.get("require_tested", True) and not bp.tested(state, ref_date):
            return {}
        return {f: bp._normalize(dict(e, last_session_date="2026-10-01"), bp.family_doc(f))
                for f, e in entries.items()}
    monkeypatch.setattr(bp, "entries_for", fake)


class TestPinFloor:
    def test_a_seed_below_the_catalog_dose_gets_the_catalog_dose(self, monkeypatch):
        _with_entries(monkeypatch, {"hollow_plank": {"level_idx": 2, "sets": 2, "target": 20,
                                                     "source": "seed_history"}})
        inst = _block(_resolve(LEGS, _state(), "strength_power"), "core_anti_extension")
        assert _rx(inst) == ("core_hollow_hold", 3, 30)
        aud = inst["suggested"]["bw_ladder"]
        assert aud["dose"]["pin_floor"] is True and aud["dose"]["summary"] == "3x30 s"
        assert aud["ladder"]["dose"] == "3x30 s"
        assert inst["prescription"]["notes"].startswith(HOLLOW_NOTE)  # the catalog dose: its note stays

    def test_a_seed_above_the_catalog_dose_keeps_its_dose(self, monkeypatch):
        _with_entries(monkeypatch, {"hollow_plank": {"level_idx": 2, "sets": 3, "target": 40,
                                                     "source": "seed_history"}})
        inst = _block(_resolve(LEGS, _state(), "strength_power"), "core_anti_extension")
        assert _rx(inst) == ("core_hollow_hold", 3, 40)
        assert "pin_floor" not in inst["suggested"]["bw_ladder"]["dose"]

    @pytest.mark.parametrize("source", sorted(bp.MANUAL_SOURCES))
    def test_feedback_or_a_hand_set_level_wins(self, monkeypatch, source):
        _with_entries(monkeypatch, {"hollow_plank": {"level_idx": 2, "sets": 2, "target": 20, "source": source}})
        inst = _block(_resolve(LEGS, _state(), "strength_power"), "core_anti_extension")
        assert _rx(inst) == ("core_hollow_hold", 2, 20)
        assert "pin_floor" not in inst["suggested"]["bw_ladder"]["dose"]

    def test_deload_floor_is_the_catalog_deload_dose(self, monkeypatch):
        _with_entries(monkeypatch, {"hollow_plank": {"level_idx": 2, "sets": 3, "target": 20,
                                                     "source": "seed_history"}})
        inst = _block(_resolve(LEGS, _state("2026-12-01"), "deload"), "core_anti_extension")
        assert _rx(inst) == ("core_hollow_hold", 2, 30)  # deload_sets 2, never below 30 s

    def test_the_floor_never_applies_to_another_exercise(self, monkeypatch):
        _with_entries(monkeypatch, {"rollout": {"level_idx": 0, "sets": 2, "target": 6, "source": "seed_history"}})
        inst = _block(_resolve(LEGS, _state(), "strength_power"), "core_anti_extension")
        assert _rx(inst) == ("ab_wheel_rollout", 2, 6)


class TestHangingGuard:
    @pytest.mark.parametrize("family", sorted(bp._families()))
    def test_pin_plan_never_offers_a_guarded_level(self, family):
        fam = bp.family_doc(family)
        top = len(fam["levels"]) - 1
        ctx = {"date": "2026-11-10", "used_families": set(), "lower_back_zone": False, "phase": "strength_power",
               "entries": {family: bp._normalize({"level_idx": top, "source": "user_edit"}, fam)}}
        plan = bp.pin_plan(ctx, family)
        allowed = [i for i in range(top, -1, -1) if not bp.is_guarded_level(fam, i)]
        if not allowed:
            assert plan is None
        else:
            assert plan["order"] == allowed

    def test_hanging_families_never_reach_a_lunch(self, tmp_path, monkeypatch):
        """A (hypothetical) pin on hanging families: never a hanging row."""
        for p in SESSIONS.glob("*.json"):
            shutil.copy(p, tmp_path / p.name)
        doc = json.loads((SESSIONS / f"{LEGS}.json").read_text(encoding="utf-8"))
        for m in doc["modules"]:
            if m["block_id"] == "core_anti_extension":
                m["ladder_pin"] = {"families": ["compression_hang", "front_lever", "rotation"]}
                m["selection"]["primary"]["filters"]["pattern"] += ["compression", "isometric_hold", "rotation"]
        (tmp_path / f"{LEGS}.json").write_text(json.dumps(doc), encoding="utf-8")
        _with_entries(monkeypatch, {"compression_hang": {"level_idx": 3, "source": "user_edit"},
                                    "front_lever": {"level_idx": 3, "source": "user_edit"},
                                    "rotation": {"level_idx": 2, "source": "user_edit"}})
        inst = _block(_resolve(LEGS, _state(), "power_endurance", tmp_path), "core_anti_extension")
        # rotation L0 (lying wipers, on the floor) is the only unguarded level.
        assert inst["exercise_id"] == "lying_windshield_wiper"
        fam, lvl = bl.family_of(inst["exercise_id"], "2026-11-10")
        assert not bp.is_guarded_level(bp.family_doc(fam), lvl)


class TestLowerBackCaps:
    def test_a_seed_above_the_ceiling_is_capped(self, monkeypatch):
        _with_entries(monkeypatch, {"rollout": {"level_idx": 4, "sets": 4, "target": 5, "source": "seed_history"}})
        inst = _block(_resolve(LEGS, _state(), "strength_power"), "core_anti_extension")
        fam, lvl = bl.family_of(inst["exercise_id"], "2026-11-10")
        assert fam == "rollout" and lvl == bp.auto_ceiling(bp.family_doc("rollout")) == 2

    def test_a_hand_set_lower_back_level_still_passes_the_block_filters(self, monkeypatch):
        # L3 (standing eccentric) is honoured by R12 (user_edit) but its
        # intensity "max" is above the block's "high": the mastered L2.
        _with_entries(monkeypatch, {"rollout": {"level_idx": 3, "sets": 4, "target": 4, "source": "user_edit"}})
        inst = _block(_resolve(LEGS, _state(), "strength_power"), "core_anti_extension")
        assert _rx(inst) == ("ab_wheel_rollout_standing_wall", 4, 8)


# ---------------------------------------------------------------------------
# Catalog contract
# ---------------------------------------------------------------------------

def _all_modules():
    for p in sorted(SESSIONS.glob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        for m in doc.get("modules") or []:
            if isinstance(m, dict):
                yield doc, m


class TestCatalogContract:
    def test_ladder_pin_only_on_the_six_lunch_blocks(self):
        found = {(d["id"], m["block_id"]): m["ladder_pin"] for d, m in _all_modules() if "ladder_pin" in m}
        assert found == PINS

    def test_never_in_selection_nor_in_templates(self):
        for _d, m in _all_modules():
            assert "ladder_pin" not in json.dumps(m.get("selection") or {})
        for p in TEMPLATES.rglob("*.json"):
            assert "ladder_pin" not in p.read_text(encoding="utf-8"), p
        assert "ladder_pin" not in (SESSIONS / "heavy_conditioning_gym.json").read_text(encoding="utf-8")
        assert "ladder_pin" not in (TEMPLATES / "v1" / "antagonist_prehab.json").read_text(encoding="utf-8")

    @pytest.mark.parametrize("key", sorted(PINS))
    def test_pinned_block_shape(self, key, catalog):
        sid, block_id = key
        m = next(m for d, m in _all_modules() if d["id"] == sid and m["block_id"] == block_id)
        prim = m["selection"]["primary"]
        assert "template_id" not in m and prim.get("exercise_id") and prim.get("pin_strict") is not True
        assert not rs._is_test_exercise(catalog[prim["exercise_id"]])
        own = bl.family_of(prim["exercise_id"])
        assert own, prim["exercise_id"]
        filters = prim["filters"]
        assert not set(filters["pattern"]) & {"isometric_hold", "rotation", "pull_horizontal"}
        if "compression" in filters["pattern"]:
            assert "compression_floor" in m["ladder_pin"]["families"]
        if block_id == "core_lateral":
            assert filters["intensity_max"] == "high" and "anti_rotation" in filters["pattern"]
        offset = m["ladder_pin"].get("level_offset", 0)
        assert isinstance(offset, int) and offset <= 0
        assert (offset != 0) is (key == (HIIT, "core_lateral"))

    @pytest.mark.parametrize("key", sorted(PINS))
    def test_families_are_floor_families(self, key, catalog):
        sid, block_id = key
        m = next(m for d, m in _all_modules() if d["id"] == sid and m["block_id"] == block_id)
        own = bl.family_of(m["selection"]["primary"]["exercise_id"])[0]
        for family in m["ladder_pin"]["families"] + [own]:
            fam = bp.family_doc(family)
            assert fam is not None, family
            assert not fam["hanging"] and not fam["heavy_pull"], family
            for lv in fam["levels"]:
                e = catalog[lv["exercise_id"]]
                assert "pullup_bar" not in (e.get("equipment_required") or []), lv["exercise_id"]
                assert (e.get("stress_tags") or {}).get("fingers") in ("none", None), lv["exercise_id"]

    @pytest.mark.parametrize("sid", lg.LUNCHES)
    def test_core_blocks_of_a_session_never_share_a_family(self, sid):
        doc = json.loads((SESSIONS / f"{sid}.json").read_text(encoding="utf-8"))
        groups = []
        for m in doc["modules"]:
            if "ladder_pin" in m:
                own = bl.family_of(m["selection"]["primary"]["exercise_id"])[0]
                groups.append(set(m["ladder_pin"]["families"]))
                if own not in ("hollow_plank",):
                    groups[-1].add(own)
            elif m.get("ab_pool"):
                groups.append({(bl.family_of(e) or (e,))[0] for e in m["ab_pool"]})
        for i, a in enumerate(groups):
            for b in groups[i + 1:]:
                assert not a & b, (sid, a, b)


# ---------------------------------------------------------------------------
# Notes, duration, determinism, stimuli
# ---------------------------------------------------------------------------

class TestNotes:
    def test_a_moved_row_carries_the_chosen_exercise_notes(self, catalog):
        r = _resolve(ARMS, _state(), "strength_power")
        for block_id, eid in (("core_anti_extension", "core_l_sit"), ("core_lateral", "copenhagen_dynamic")):
            inst = _block(r, block_id)
            assert inst["exercise_id"] == eid
            own = (catalog[eid].get("defaults") or catalog[eid].get("prescription_defaults") or {}).get("notes")
            assert own
            assert inst["prescription"].get("notes") == own
            assert "hollow" not in str(inst["prescription"].get("notes")).lower()
            assert "side plank" not in str(inst["prescription"].get("notes")).lower()

    def test_same_exercise_other_dose_drops_the_catalog_dose_text(self):
        st = _state(levels=_levels(rollout=None, compression_floor=None,
                                   hollow_plank={"level_idx": 2, "sets": 3, "target": 35, "source": "user_edit"}))
        inst = _block(_resolve(LEGS, st, "strength_power"), "core_anti_extension")
        assert _rx(inst) == ("core_hollow_hold", 3, 35)
        assert HOLLOW_NOTE not in str(inst["prescription"].get("notes"))

    def test_catalog_dose_keeps_the_catalog_note(self):
        st = _state(levels=_levels(rollout=None, compression_floor=None))  # hollow 3x30 by hand
        inst = _block(_resolve(LEGS, st, "strength_power"), "core_anti_extension")
        assert _rx(inst) == ("core_hollow_hold", 3, 30)
        assert inst["prescription"]["notes"].startswith(HOLLOW_NOTE)

    def test_untested_keeps_the_catalog_note(self):
        inst = _block(_resolve(LEGS, _untested("2026-11-10"), "strength_power"), "core_anti_extension")
        assert inst["prescription"]["notes"].startswith(HOLLOW_NOTE)


class TestDuration:
    @pytest.mark.parametrize("sid", lg.LUNCHES)
    def test_within_55_minutes_in_every_phase(self, sid, catalog):
        """Daniele's levels of 2026-11-04, the five phases (performance on two
        A/B weeks): never above the 55' lunch slot. Before the split-squat rest
        went 90 → 60 s the legs lunch was 56' in the Copenhagen weeks."""
        for date, phase in lg.DANIELE_SLOTS + (("2026-11-16", "strength_power"),):
            rows = []
            for inst in _insts(_resolve(sid, _state(date), phase)):
                rx = dict(inst["prescription"])
                rx["alt_sides"] = bool(catalog[inst["exercise_id"]].get("alt_sides"))
                rows.append(rx)
            minutes = estimate_custom_session_duration(rows)
            assert 15 <= minutes <= 55, (sid, date, phase, minutes)


class TestDeterminism:
    @pytest.mark.parametrize("sid", lg.LUNCHES)
    def test_same_input_same_output(self, sid):
        st = _state()
        first = _resolve(sid, st, "performance")
        for _ in range(5):
            assert _resolve(sid, st, "performance") == first

    def test_ladder_on_golden(self):
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        now = lg.compute()
        assert set(now) == set(expected)
        diff = [k for k in expected if expected[k] != now[k]]
        assert diff == [], f"ladder-on resolver output changed: {diff[:10]}"

    def test_changed_keys_are_lunches_only(self):
        assert lg.CHANGED_BY_D4 and all(any(k.endswith(s) for s in lg.LUNCHES) for k in lg.CHANGED_BY_D4)
        assert len(lg.CHANGED_BY_D4) == len(set(lg.CHANGED_BY_D4)) == 40


class TestStimuli:
    @pytest.mark.parametrize("sid", lg.LUNCHES)
    def test_no_stimulus_no_heavy_pull_no_finger_load(self, sid, catalog):
        for date, phase in lg.DANIELE_SLOTS:
            r = _resolve(sid, _state(date), phase)
            slot = {"session_id": sid, "tags": {"hard": False, "finger": False}, "resolved": r}
            assert session_stimuli(slot) == []
            assert not is_pulling_hard_session(slot) and not is_finger_hard_session(slot)
            for inst in _insts(r):
                if not inst["source"]["block_id"].startswith("core"):
                    continue
                assert (catalog[inst["exercise_id"]].get("stress_tags") or {}).get("fingers") in ("none", None)
                hit = bl.family_of(inst["exercise_id"], date)
                if hit:
                    assert not bp.is_guarded_level(bp.family_doc(hit[0]), hit[1]), inst["exercise_id"]


# ---------------------------------------------------------------------------
# Closed loop and past sessions
# ---------------------------------------------------------------------------

def _log(day, sid, items):
    return {"date": day, "session_id": sid, "feedback_contract": 2, "actual": {"exercise_feedback_v1": items}}


class TestClosedLoop:
    def test_feedback_on_his_level_moves_the_ladder(self):
        st = _state("2026-11-10")
        out = apply_feedback(_log("2026-11-10", ARMS, [
            {"exercise_id": "copenhagen_dynamic", "feedback_label": "ok", "completed": True, "bw_ladder": "engine"},
            {"exercise_id": "core_l_sit", "completed": True, "bw_ladder": "engine"},
        ]), st)
        lat, lsit = out["bw_progression"]["lateral"], out["bw_progression"]["compression_floor"]
        assert (lat["level_idx"], lat["target"]) == (3, 7)    # ok = +1
        assert (lsit["level_idx"], lsit["target"]) == (2, 15)  # done unrated = ok (A1): +5 s

    def test_the_hiit_offset_row_never_moves_the_ladder(self):
        st = _state("2026-11-10")
        before = copy.deepcopy(st["bw_progression"]["lateral"])
        out = apply_feedback(_log("2026-11-10", HIIT, [
            {"exercise_id": "copenhagen_plank", "feedback_label": "easy", "completed": True, "bw_ladder": "engine"},
        ]), st)
        assert out["bw_progression"]["lateral"] == before  # a mastered lower level: other_level

    def test_mark_done_items_carry_the_pinned_rows(self):
        r = _resolve(ARMS, _state(), "strength_power")
        items = bp.mark_done_items({"session_id": ARMS, "resolved": r})
        assert {i["exercise_id"] for i in items} >= {"copenhagen_dynamic", "core_l_sit"}
        assert all(i["bw_ladder"] == "engine" for i in items)


class TestPastImmutable:
    def test_a_resolved_done_lunch_is_never_rewritten_by_get(self, tmp_path, monkeypatch):
        """A lunch played before D4 (hollow + side plank stored) stays byte for
        byte through GET /week and a forced regeneration; the planned one of
        the same week gets the ladder core."""
        from backend.api import deps
        from backend.engine import storage_file
        from backend.tests import test_b413_freeze_prescription as fz

        monkeypatch.setattr(storage_file, "DATA_DIR", tmp_path)
        monkeypatch.setattr(storage_file, "USERS_DIR", tmp_path / "users")
        monkeypatch.delenv("STORAGE_REQUEST_MEMO", raising=False)

        arms = {"slot": "lunch", "session_id": ARMS, "location": "home", "tags": {"hard": False, "finger": False}}
        st = fz._state(this_week={0: [dict(arms)], 2: [dict(arms)]}, offset=4)
        st["equipment"]["home"] = sorted(set(st["equipment"]["home"]) | {"dumbbell", "bench"})
        with monkeypatch.context() as m:  # the pre-D4 resolution of the played Monday
            m.setattr(rs, "_bw_ladder_pin_stage", lambda *a, **k: None)
            old = _resolve(ARMS, dict(st, context={"location": "home", "target_date": fz.MON_ISO,
                                                   "date": fz.MON_ISO}), "strength_power")
        assert _rx(_block(old, "core_lateral"))[0] == "side_plank"
        played = fz._session(st["week_plans"][fz.MON_ISO], ARMS, 0)
        played.update(status="done", resolved=old)
        st["current_week_plan"] = st["week_plans"][fz.MON_ISO]
        deps.save_state(st, fz.UID)
        want = fz._played(fz._stored(ARMS, 0))

        view = fz._get()["week_plan"]
        assert fz._played(fz._stored(ARMS, 0)) == want
        wed = fz._session(view, ARMS, 2)["resolved"]
        assert _block(wed, "core_lateral")["exercise_id"] == "copenhagen_plank"  # his lateral L2
        assert not fz._get(force="true").get("regeneration_failed")
        assert fz._played(fz._stored(ARMS, 0)) == want
