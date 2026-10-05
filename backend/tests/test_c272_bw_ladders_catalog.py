"""C272 — bodyweight ladders, technique / try-hard library, pocket warm-up.

Catalog-only brief: 73 exercises with role ``ladder`` / ``library`` that the
engine never selects, the ladder file
``backend/catalog/progressions/v1/bw_ladders.json``, and the read-only level
seed Claude Code sees in the athlete context. The review reverted the note
rewrites on engine-selected exercises (other users stay bit for bit) and wired
the guards the data promises (finger-hard comp drill, ladder heavy pulls).

What is pinned here:
1. the ladder file is internally valid and agrees with the catalog;
2. the new entries are library-only and fully described (cues, measure, sources);
3. no engine path selects them — resolver golden on 3 profiles vs origin/main,
   ad-hoc builder / composer pool golden, an in-process differential for the
   body-part picker (its static golden is impossible: see c272_golden_cases);
4. the read-only seed (``bw_ladders.seed_levels``) follows the BW rules and is
   deterministic, and the athlete context shows it.
"""

from __future__ import annotations

import copy
import json
import os
from datetime import date
from pathlib import Path

import pytest

from backend.engine import athlete_context as ac
from backend.engine import bw_ladders as bw
from backend.engine.catalog_roles import LIBRARY_ONLY_ROLES, is_library_only
from backend.tests import c272_golden_cases as golden

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "c272_resolver_golden.json"
INTENSITY = {"very_low": 0, "low": 1, "medium": 2, "high": 3, "max": 4}
#: Ids that existed before C272 and are now levels of a ladder: they keep their
#: original roles (an engine-selectable exercise stays engine-selectable).
PRE_EXISTING_LEVELS = {
    "core_l_sit", "hanging_leg_raise", "knees_to_elbows", "toes_to_bar", "ab_wheel_rollout", "plank",
    "core_hollow_hold", "front_lever_tuck", "front_lever_one_leg", "front_lever_straddle", "side_plank",
    "copenhagen_plank", "back_extension", "pallof_press", "windshield_wipers", "incline_pushup", "pushup",
    "ring_pushup", "pike_pushup", "handstand_pushup_wall", "dip", "pullup", "l_sit_pullup", "archer_pullup",
    "one_arm_pullup_assisted", "nordic_curl",
}


@pytest.fixture(scope="module")
def catalog():
    data = json.loads((REPO / golden.EXERCISES).read_text(encoding="utf-8"))
    return {e["id"]: e for e in data["exercises"]}


@pytest.fixture(scope="module")
def ladders():
    return bw.load_ladders()


def _all_refs(doc) -> set:
    refs = set()
    for f in doc["families"]:
        refs.update(lv["exercise_id"] for lv in f["levels"])
        t = f.get("terminal") or {}
        if t.get("handoff_exercise_id"):
            refs.add(t["handoff_exercise_id"])
        refs.update(t.get("then_exercise_ids") or [])
        refs.update(f.get("variants") or [])
        refs.update(f.get("extras") or [])
        refs.update(g["requires_accessory_id"] for g in f.get("gates") or [] if g.get("requires_accessory_id"))
    for t in doc["technique_ladders"]:
        for lv in t["levels"]:
            refs.update(lv["drills"])
        refs.update(t.get("support_drills") or [])
        if t.get("benchmark"):
            refs.add(t["benchmark"])
    refs.update(u["drill"] for u in doc["untracked_progressions"])
    refs.update(doc["try_hard"]["drills"])
    for p in doc["protocols"].values():
        refs.update(p.get("drills") or [])
        refs.update(p.get("applies_to") or [])
    for a in doc["history_aliases"]:
        refs.update({a["exercise_id"], a["counts_as"]})
    return refs


# ---------------------------------------------------------------------------
# 1. Ladder file validation
# ---------------------------------------------------------------------------

class TestLadderFile:
    def test_sixteen_families_and_three_technique_ladders(self, ladders):
        assert len(ladders["families"]) == 16
        assert [t["ladder"] for t in ladders["technique_ladders"]] == ["feet", "positions", "falls"]
        assert [lv["level"] for lv in ladders["technique_ladders"][2]["levels"]] == ["F1", "F2", "F3"]

    def test_every_referenced_id_exists_and_is_active(self, ladders, catalog):
        refs = _all_refs(ladders)
        assert sorted(r for r in refs if r not in catalog) == []
        assert sorted(r for r in refs if catalog[r].get("active") is False) == []

    def test_each_exercise_is_a_level_of_at_most_one_family(self, ladders):
        seen = {}
        for f in ladders["families"]:
            for lv in f["levels"]:
                assert lv["exercise_id"] not in seen, (lv["exercise_id"], seen.get(lv["exercise_id"]), f["family"])
                seen[lv["exercise_id"]] = f["family"]

    def test_level_idx_starts_at_zero_and_bands_are_sane(self, ladders):
        caps = ladders["caps"]
        for f in ladders["families"]:
            assert f["sources"], f["family"]
            assert f["axis_default"] in ("reps", "seconds")
            for i, lv in enumerate(f["levels"]):
                b = lv["band"]
                assert lv["level_idx"] == i
                assert lv["axis"] in ("reps", "seconds")
                assert 0 < b["lo"] < b["hi"] and b["step"] > 0, (f["family"], lv)
                cap = caps["max_seconds"] if lv["axis"] == "seconds" else caps["max_reps"]
                assert b["hi"] <= cap, (f["family"], lv["exercise_id"])
                assert lv["sets"] >= 1 and lv["rest_s"] > 0 and lv["advance_sessions"] in (1, 2)

    def test_intensity_never_decreases_within_a_family(self, ladders, catalog):
        for f in ladders["families"]:
            ints = [INTENSITY[catalog[lv["exercise_id"]]["intensity_level"]] for lv in f["levels"]]
            assert ints == sorted(ints), (f["family"], ints)

    def test_level_pointers_are_in_range(self, ladders):
        for f in ladders["families"]:
            n = len(f["levels"])
            for key in ("floor_level_advanced", "lower_back_risk_from_level", "heavy_pull_from_level",
                        "hanging_from_level"):
                v = f.get(key)
                assert v is None or 0 <= v < n, (f["family"], key, v)
            for rule in f["entry_seed"]:
                assert 0 <= rule["level"] < n, (f["family"], rule)
                assert rule["test"] == "l_sit_hold_seconds"
                if rule.get("ramp"):
                    assert 0 <= rule["ramp"]["then_level"] < n
            for g in f["gates"]:
                assert 0 <= g["level"] < n
            assert f["stimulus_ref"] in (None, "pulling_max")
            assert f["terminal"]["kind"] in ("tempo", "load", "handoff", "cap")

    def test_seed_rules_quoted_in_the_spec_point_to_the_right_levels(self, ladders):
        fams = {f["family"]: f for f in ladders["families"]}
        # l_sit ≥ 30 → straddle L-sit / toes to bar; l_sit ≥ 35 → ring fallout, Copenhagen short, tuck DF negative.
        assert fams["compression_floor"]["levels"][3]["exercise_id"] == "straddle_l_sit"
        assert fams["compression_hang"]["levels"][3]["exercise_id"] == "toes_to_bar"
        assert fams["rollout"]["levels"][1]["exercise_id"] == "ring_fallout"
        assert fams["lateral"]["levels"][1]["exercise_id"] == "copenhagen_short_lever"
        assert fams["dragon_flag"]["levels"][2]["exercise_id"] == "dragon_flag_tuck_negative"
        assert fams["compression_floor"]["floor_level_advanced"] == 2  # core_l_sit
        # Every front-lever level is a heavy pull (DECISIONS), no added load at the end.
        fl = fams["front_lever"]
        assert fl["heavy_pull"] and fl["heavy_pull_from_level"] == 0 and fl["terminal"]["no_added_load"]

    def test_history_alias_maps_hlr_to_toes_to_bar_for_every_log(self, ladders):
        # C272 review: the catalog note of hanging_leg_raise stays "to bar" for
        # every user, so the alias has no cut-off; the 90° level is its own id.
        assert bw.family_of("hanging_leg_raise", "2026-09-30") == ("compression_hang", 3)
        assert bw.family_of("hanging_leg_raise", "2026-10-05") == ("compression_hang", 3)
        assert bw.family_of("hanging_leg_raise", "2027-03-01") == ("compression_hang", 3)
        assert bw.family_of("hanging_leg_raise") == ("compression_hang", 3)
        assert bw.family_of("hanging_leg_raise_horizontal", "2027-03-01") == ("compression_hang", 1)
        assert bw.family_of("not_an_exercise") is None
        assert all("before" not in a for a in ladders["history_aliases"])

    def test_alias_with_a_cutoff_only_applies_before_it(self, ladders):
        doc = copy.deepcopy(ladders)
        doc["history_aliases"] = [{"exercise_id": "hanging_leg_raise", "counts_as": "toes_to_bar",
                                   "before": "2026-10-05"}]
        assert bw.family_of("hanging_leg_raise", "2026-10-04", doc) == ("compression_hang", 3)
        assert bw.family_of("hanging_leg_raise", "2026-10-05", doc) is None
        assert bw.family_of("hanging_leg_raise", None, doc) is None

    def test_protocols_carry_steps_and_sources(self, ladders):
        for pid in ("limit_weak_style", "template_warmup", "outdoor_technique_day", "pocket_warmup"):
            p = ladders["protocols"][pid]
            assert p["steps"] and p["sources"] and p["label"]
        pocket = ladders["protocols"]["pocket_warmup"]
        assert "never a mono in the gym" in pocket["safety"]


# ---------------------------------------------------------------------------
# 2. Catalog entries
# ---------------------------------------------------------------------------

class TestCatalogEntries:
    def test_seventy_three_library_only_entries(self, catalog):
        lib = {i for i, e in catalog.items() if is_library_only(e)}
        assert len(lib) == 73
        assert {r for e in catalog.values() for r in (e.get("role") or [])} >= LIBRARY_ONLY_ROLES
        # library-only means ONLY that role: never mixed with an engine role.
        for i in lib:
            assert set(catalog[i]["role"]) <= LIBRARY_ONLY_ROLES, i

    def test_pre_existing_levels_keep_their_engine_roles(self, catalog):
        for eid in PRE_EXISTING_LEVELS:
            assert not is_library_only(catalog[eid]), eid

    def test_new_ladder_levels_have_role_ladder(self, ladders, catalog):
        for f in ladders["families"]:
            for lv in f["levels"]:
                eid = lv["exercise_id"]
                if eid not in PRE_EXISTING_LEVELS:
                    assert catalog[eid]["role"] == ["ladder"], eid

    def test_no_orphan_library_entry(self, ladders, catalog):
        refs = _all_refs(ladders)
        orphans = sorted(i for i, e in catalog.items() if is_library_only(e) and i not in refs)
        assert orphans == []

    def test_library_drills_are_fully_described(self, catalog):
        for eid, e in catalog.items():
            if "library" not in (e.get("role") or []):
                continue
            assert len(e["cues"]) >= 2, eid
            assert e.get("measure"), eid
            assert e.get("progression"), eid
            assert e.get("sources"), eid
            assert e["prescription_defaults"].get("notes"), eid

    def test_spine_safe_ids(self, catalog):
        # The A259 spine filter drops ids containing these markers; none may be new.
        lib = [i for i, e in catalog.items() if is_library_only(e)]
        assert not [i for i in lib if any(m in i for m in ("crunch", "situp", "sit_up", "russian_twist"))]

    def test_pocket_drills_are_submaximal_and_never_a_gym_mono(self, catalog):
        for eid in ("pocket_rampup_hangboard", "single_finger_pocket_rampup"):
            e = catalog[eid]
            text = (e["prescription_defaults"]["notes"] + " " + e["description"]).lower()
            assert e["intensity_level"] == "low" and e["equipment_required"] == ["hangboard"]
            assert "never" in text and "mono" in text
            assert "feet" in text  # load controlled from the feet
        assert "always" in catalog["single_finger_pocket_rampup"]["prescription_defaults"]["notes"].lower()

    def test_engine_selected_notes_are_unchanged(self, catalog):
        # C272 review: rewriting the notes of exercises the engine selects for
        # every user broke "other users bit for bit" (hanging_leg_raise even
        # became an easier movement at the same dose). Reverted; the 90° raise
        # is the ladder-only hanging_leg_raise_horizontal.
        notes = {eid: catalog[eid]["prescription_defaults"]["notes"]
                 for eid in ("hanging_leg_raise", "front_lever_tuck", "lock_off_isometric", "bear_crawl")}
        assert notes["hanging_leg_raise"] == "Straight legs to bar. Control the negative. No kipping."
        assert notes["front_lever_tuck"].startswith("Advance to next progression when 4x15s is consistent.")
        assert notes["lock_off_isometric"] == "Hold 5-10s at each angle. 90°, 120°, full lock. 3-5 sets per angle."
        assert notes["bear_crawl"].startswith("Quadrupedia.")
        core = json.loads((REPO / "backend/catalog/templates/v1/core_standard.json").read_text(encoding="utf-8"))
        assert core["blocks"][0]["prescription"]["notes"] == (
            "Core exercise: hollow hold, dead bug, side plank, or pallof press. Pick one.")
        hz = catalog["hanging_leg_raise_horizontal"]
        assert hz["role"] == ["ladder"] and "horizontal (90°)" in hz["prescription_defaults"]["notes"]

    def test_one_arm_negative_starts_from_an_open_angle(self, catalog):
        e = catalog["one_arm_pullup_negative"]
        text = " ".join([e["prescription_defaults"]["notes"]] + e["cues"]).lower()
        assert "90°" in e["cues"][0] and "never from the top" in e["cues"][0].lower()
        assert "start at the top" not in text

    def test_limit_exercises_point_to_the_weak_style_protocol(self, catalog):
        for eid in ("limit_bouldering", "board_limit_boulders", "system_board_limit", "spray_wall_limit"):
            assert catalog[eid]["protocol_refs"] == ["limit_weak_style"]

    def test_no_template_or_session_block_requests_a_library_role(self):
        offenders = []
        for folder in ("templates/v1", "sessions/v1"):
            for path in sorted((REPO / "backend" / "catalog" / folder).glob("*.json")):
                text = path.read_text(encoding="utf-8")
                doc = json.loads(text)
                for block in doc.get("blocks") or doc.get("modules") or []:
                    roles = set(block.get("role") or [])
                    filt = ((block.get("selection") or {}).get("primary") or {}).get("filters") or {}
                    roles |= set(filt.get("role") or [])
                    if roles & LIBRARY_ONLY_ROLES:
                        offenders.append(f"{path.name}:{block.get('block_id')}")
                assert '"ladder"' not in text and '"library"' not in text, path.name
        assert offenders == []

    def test_is_library_only(self):
        assert is_library_only({"role": ["ladder"]}) and is_library_only({"role": "library"})
        assert not is_library_only({"role": ["main", "test"]}) and not is_library_only({})


# ---------------------------------------------------------------------------
# 3. No engine path selects them
# ---------------------------------------------------------------------------

class TestEngineUnchanged:
    def test_resolver_golden_three_profiles_unchanged_vs_main(self, monkeypatch):
        # A298: the ladder stage deliberately changes the bodyweight rows of
        # TESTED athletes (their level, their dose). This golden pins the C272
        # claim — the catalog additions alone change no selection — so it runs
        # with the ladder stage off; the untested profile is pinned with the
        # stage ON in test_a298_bw_progression (bit for bit).
        from backend.engine import bw_progression

        monkeypatch.setattr(bw_progression, "build_resolve_context", lambda *a, **k: None)
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["resolver"]
        now = golden.compute()
        assert set(now) == set(expected)
        diff = [k for k in expected if expected[k] != now[k]]
        assert diff == [], f"resolver output changed: {diff[:10]}"

    def test_adhoc_builder_and_composer_pool_unchanged_vs_main(self):
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["other_engines"]
        now = golden.compute_other_engines()
        assert set(now) == set(expected)
        assert [k for k in expected if expected[k] != now[k]] == []

    def test_body_part_picker_ignores_library_entries(self, tmp_path, catalog):
        """In-process differential: full catalog vs catalog without the
        library-only entries must give the same sessions."""
        full = golden.compute_other_engines(body_parts=True)
        data = json.loads((REPO / golden.EXERCISES).read_text(encoding="utf-8"))
        data["exercises"] = [e for e in data["exercises"] if not is_library_only(e)]
        stripped_path = tmp_path / "exercises.json"
        stripped_path.write_text(json.dumps(data), encoding="utf-8")
        stripped = golden.compute_other_engines(str(stripped_path), body_parts=True)
        assert full == stripped
        lib = {i for i, e in catalog.items() if is_library_only(e)}
        picked = {x for k, v in full.items() if isinstance(v, list) for x in v}
        assert not (picked & lib)

    def test_body_part_picker_still_finds_the_pre_c272_ids(self, catalog):
        from backend.engine.body_part_picker import build_body_part_index

        idx = build_body_part_index(list(catalog.values()))
        everything = set().union(*idx.values())
        assert "pistol_squat_progression" in everything and "copenhagen_adductor_plank" in everything
        assert not (everything & {i for i, e in catalog.items() if is_library_only(e)})

    def test_composer_pool_never_offers_library_entries(self, catalog):
        from backend.coach.session_composer import build_pool

        st = golden.profiles()["advanced"]
        for focus in ("technique", "core", "general_strength", "fingers"):
            pool = build_pool({"equipment_set": "gym", "focus": focus, "gym_name": "Board gym"}, st, catalog)
            assert not [e["id"] for e in pool if is_library_only(e)]

    def test_key_status_counts_the_new_tryhard_drills_but_not_as_technique(self, catalog):
        from backend.engine import key_sessions_v1 as ks

        session = {"session_id": "custom_x", "is_custom": True, "status": "done",
                   "exercises": [{"exercise_id": "three_attempt_comp", "sets": 1},
                                 {"exercise_id": "no_take_lead_onsight", "sets": 3},
                                 {"exercise_id": "small_feet_press_hold", "sets": 1}]}
        req = ks.load_key_catalog()["stimuli"]["try_hard"]
        assert ks.tryhard_hit(session, req)
        assert not ks.technique_hit(session, catalog)  # try-hard + warm-up drills are not the technique key
        tech = {**session, "exercises": [{"exercise_id": "glued_feet_board", "sets": 4},
                                         {"exercise_id": "position_menu_3way", "sets": 3}]}
        assert ks.technique_hit(tech, catalog)

    def test_vertical_small_feet_limit_is_a_limit_power_exposure(self):
        from backend.engine.stimulus import FAMILY_LIMIT_POWER, stimulus_of

        assert stimulus_of("vertical_small_feet_limit") == FAMILY_LIMIT_POWER

    def test_three_attempt_comp_is_finger_hard_for_every_guard(self, catalog):
        from backend.engine.stimulus import is_finger_hard_session, session_stimuli, stimulus_of

        s = {"session_id": "custom_x", "is_custom": True, "exercises": [{"exercise_id": "three_attempt_comp"}]}
        assert is_finger_hard_session(s)
        assert session_stimuli(s) == [] and stimulus_of("three_attempt_comp") is None  # not an exposure
        assert "three_attempt_comp" in ac.finger_hard_session_ids(catalog)
        assert not is_finger_hard_session({**s, "exercises": [{"exercise_id": "glued_feet_board"}]})

    def test_every_library_drill_tagged_fingers_high_is_finger_hard(self, catalog):
        from backend.engine.stimulus import is_finger_hard_session

        for eid, e in catalog.items():
            if is_library_only(e) and (e.get("stress_tags") or {}).get("fingers") == "high":
                assert is_finger_hard_session({"session_id": "custom_x", "exercises": [{"exercise_id": eid}]}), eid

    def test_finger_hard_day_from_a_comp_custom_blocks_the_next_day(self):
        from backend.engine.stimulus import finger_hard_days

        st = _tested_state()
        _add_done(st, "2026-10-01", [{"exercise_id": "three_attempt_comp", "sets": 1, "reps": 7}],
                  actual=[{"exercise_id": "three_attempt_comp", "completed": True, "completed_sets": 1}])
        days = {r["date"] for r in finger_hard_days(st, since="2026-09-28", until="2026-10-04")}
        assert "2026-10-01" in days

    def test_technique_benchmark_does_not_close_the_technique_key(self, catalog):
        from backend.engine import key_sessions_v1 as ks

        s = {"session_id": "custom_x", "is_custom": True, "status": "done",
             "exercises": [{"exercise_id": "technique_benchmark_test", "sets": 1},
                           {"exercise_id": "rest_and_clip_drill", "sets": 2}]}
        assert "technique_benchmark" in ks.TECHNIQUE_EXCLUDED_RECENCY
        assert not ks.technique_hit(s, catalog)

    def test_ladder_heavy_pull_ids(self, ladders):
        ids = bw.heavy_pull_exercise_ids()
        fl = next(f for f in ladders["families"] if f["family"] == "front_lever")
        assert {lv["exercise_id"] for lv in fl["levels"]} <= ids
        assert {"front_lever_raise", "front_lever_row", "front_lever_negative", "front_lever_raise_tuck"} <= ids
        assert {"one_arm_pullup_assisted", "one_arm_pullup_negative", "one_arm_pullup"} <= ids
        assert not ({"pullup", "l_sit_pullup", "archer_pullup"} & ids)


# ---------------------------------------------------------------------------
# 4. Read-only seed and athlete context
# ---------------------------------------------------------------------------

REF = "2026-10-05"


def _tested_state():
    st = copy.deepcopy(golden.profiles()["advanced"])
    st["assessment"]["tests"] = {"l_sit_hold_seconds": 60}
    # Start from an empty history: the golden profile's past week holds a
    # front_lever_one_leg that would seed the front lever in every test.
    st["week_plans"] = {}
    return st


def _add_done(st, d, exercises, *, sid="custom_cs_core", actual=None):
    monday = date.fromisoformat(d)
    monday = monday.fromordinal(monday.toordinal() - monday.weekday()).isoformat()
    plan = st.setdefault("week_plans", {}).setdefault(monday, {"start_date": monday, "weeks": [{"days": []}]})
    session = {"session_id": sid, "is_custom": True, "status": "done", "exercises": exercises}
    if actual is not None:
        session["actual_exercises"] = actual
    plan["weeks"][0]["days"].append({"date": d, "sessions": [session]})


def _fam(seed, name):
    return next(r for r in seed["families"] if r["family"] == name)


class TestSeed:
    def test_untested_athlete_gets_no_seed(self):
        st = copy.deepcopy(golden.profiles()["untested"])
        st.setdefault("assessment", {})["tests"] = {"l_sit_hold_seconds": 60}
        seed = bw.seed_levels(st, REF)
        assert seed["tested_gate"] is False
        assert {r["source"] for r in seed["families"]} == {"catalog"}
        assert all(r["level_idx"] is None for r in seed["families"])

    def test_l_sit_without_a_test_log_in_90_days_does_not_seed(self):
        seed = bw.seed_levels(_tested_state(), REF)
        assert seed["tested_gate"] and seed["l_sit_test"] is None
        assert _fam(seed, "compression_floor")["source"] == "none"

    def test_l_sit_test_log_seeds_straddle_3x20_and_copenhagen_ramp(self):
        st = _tested_state()
        _add_done(st, "2026-09-24", [{"exercise_id": "test_l_sit_hold", "sets": 1}], sid="custom_test_day")
        seed = bw.seed_levels(st, REF, equipment=["bench", "rings", "ab_wheel", "pullup_bar"])
        cf = _fam(seed, "compression_floor")
        assert (cf["source"], cf["exercise_id"], cf["target"], cf["sets"]) == ("test", "straddle_l_sit", 20, 3)
        assert cf["seeded_from"] == {"test": "l_sit_hold_seconds", "value": 60.0, "log_date": "2026-09-24"}
        ch = _fam(seed, "compression_hang")
        assert (ch["exercise_id"], ch["target"]) == ("toes_to_bar", 5)
        lat = _fam(seed, "lateral")
        assert lat["exercise_id"] == "copenhagen_short_lever" and lat["ramp"]["sessions"] == 2
        assert _fam(seed, "rollout")["exercise_id"] == "ring_fallout"
        assert _fam(seed, "dragon_flag")["exercise_id"] == "dragon_flag_tuck_negative"
        # The front lever is never seeded from a test (elbow-risk skill).
        assert _fam(seed, "front_lever")["source"] == "none"
        # A tested 2RM keeps the weighted pull-up.
        assert _fam(seed, "pull_bw")["source"] == "not_applicable"

    def test_dragon_flag_test_seed_needs_a_bench(self):
        st = _tested_state()
        _add_done(st, "2026-09-24", [{"exercise_id": "test_l_sit_hold", "sets": 1}], sid="custom_test_day")
        seed = bw.seed_levels(st, REF, equipment=["pullup_bar"])
        assert _fam(seed, "dragon_flag")["source"] == "none"

    def test_the_golden_history_week_seeds_the_front_lever(self):
        st = copy.deepcopy(golden.profiles()["advanced"])  # strength_long of 2026-09-29: front_lever_one_leg
        fl = _fam(bw.seed_levels(st, REF), "front_lever")
        assert (fl["source"], fl["exercise_id"], fl["evidence"]["evidence"]) == ("history", "front_lever_one_leg", "planned")

    def test_history_wins_with_last_dose_minus_one_step(self):
        st = _tested_state()
        _add_done(st, "2026-09-30", [{"exercise_id": "front_lever_one_leg", "sets": 4, "work_seconds": 12},
                                     {"exercise_id": "front_lever_straddle", "sets": 4, "work_seconds": 12}])
        seed = bw.seed_levels(st, REF)
        fl = _fam(seed, "front_lever")
        assert (fl["source"], fl["exercise_id"], fl["target"], fl["sets"]) == ("history", "front_lever_straddle", 10, 4)
        assert fl["heavy_pull"] and fl["evidence"]["date"] == "2026-09-30"

    def test_history_ignores_hard_labels_and_uses_the_logged_session(self):
        st = _tested_state()
        _add_done(st, "2026-09-30",
                  [{"exercise_id": "toes_to_bar", "sets": 3, "reps": 8}, {"exercise_id": "knees_to_elbows", "sets": 3, "reps": 8}],
                  actual=[{"exercise_id": "toes_to_bar", "completed": True, "completed_sets": 3, "feedback_label": "very_hard"},
                          {"exercise_id": "knees_to_elbows", "completed": True, "completed_sets": 3, "feedback_label": "ok"}])
        ch = _fam(bw.seed_levels(st, REF), "compression_hang")
        assert (ch["exercise_id"], ch["target"]) == ("knees_to_elbows", 7)

    def test_hlr_counts_as_toes_to_bar_at_the_top_of_the_band(self):
        st = _tested_state()
        _add_done(st, "2026-09-20", [{"exercise_id": "hanging_leg_raise", "sets": 3, "reps": 8}])
        ch = _fam(bw.seed_levels(st, REF), "compression_hang")
        assert (ch["exercise_id"], ch["target"], ch["at_top_of_band"]) == ("toes_to_bar", 7, True)

    def test_history_window_is_120_days_and_60_for_skill_families(self):
        st = _tested_state()
        _add_done(st, "2026-07-01", [{"exercise_id": "front_lever_straddle", "sets": 4, "work_seconds": 12},
                                     {"exercise_id": "ring_pushup", "sets": 3, "reps": 8}])
        seed = bw.seed_levels(st, REF)
        assert _fam(seed, "front_lever")["source"] == "none"            # 96 days > 60 (skill family)
        assert _fam(seed, "push_horizontal")["exercise_id"] == "ring_pushup"  # 96 days ≤ 120

    def test_future_sessions_are_ignored(self):
        st = _tested_state()
        _add_done(st, "2026-10-10", [{"exercise_id": "ring_pushup", "sets": 3, "reps": 8}])
        assert _fam(bw.seed_levels(st, REF), "push_horizontal")["source"] == "none"

    def test_persisted_state_wins_when_it_exists(self):
        st = _tested_state()
        st["bw_progression"] = {"rollout": {"level_idx": 2, "target": 6, "sets": 4, "last_session_date": "2026-10-01"}}
        r = _fam(bw.seed_levels(st, REF), "rollout")
        assert (r["source"], r["exercise_id"], r["target"], r["manual_only"]) == (
            "state", "ab_wheel_rollout_standing_wall", 6, False)

    def test_seed_is_pure_and_deterministic(self):
        st = _tested_state()
        _add_done(st, "2026-09-24", [{"exercise_id": "test_l_sit_hold", "sets": 1}], sid="custom_test_day")
        before = json.dumps(st, sort_keys=True)
        outs = {json.dumps(bw.seed_levels(st, REF), sort_keys=True) for _ in range(20)}
        assert len(outs) == 1 and json.dumps(st, sort_keys=True) == before
        assert "bw_progression" not in st


class TestAthleteContext:
    def test_context_carries_the_seed_and_the_library(self):
        st = _tested_state()
        st["macrocycle"] = golden.profiles()["advanced"]["macrocycle"]
        _add_done(st, "2026-09-24", [{"exercise_id": "test_l_sit_hold", "sets": 1}], sid="custom_test_day")
        ctx = ac.build_athlete_context(st, REF, with_proposals=False, include_next_week=False)
        assert ctx["version"] == ac.VERSION == "c272.1"
        assert _fam(ctx["bw_ladders"], "compression_floor")["exercise_id"] == "straddle_l_sit"
        ids = {d["exercise_id"] for d in ctx["technique_library"]["drills"]}
        assert {"glued_feet_board", "three_attempt_comp", "fall_ladder", "pocket_rampup_hangboard"} <= ids
        assert "limit_weak_style" in ctx["technique_library"]["protocols"]
        text = ac.render_text(ctx)
        assert "## Scale corpo libero" in text and "straddle_l_sit 3×20 s" in text
        assert "## Libreria tecnica / try-hard" in text and "Scala feet:" in text
        assert "vertical_small_feet_limit (dita-hard)" in text

    def test_untested_context_says_no_seed_and_leaves_the_coach_block_alone(self):
        st = copy.deepcopy(golden.profiles()["untested"])
        ctx = ac.build_athlete_context(st, REF, with_proposals=False, include_next_week=False)
        assert ctx["bw_ladders"]["tested_gate"] is False
        assert "atleta non testato: nessun seed" in ac.render_text(ctx)
        # The in-app prompt blocks (A297) do not carry the C272 sections.
        assert "Scale corpo libero" not in ac.render_coach_block(ctx)
        assert "ladder" not in ac.render_composer_block(ctx, day=REF).lower()

    def test_front_lever_day_is_a_heavy_pull_day_for_a_tested_athlete(self):
        st = _tested_state()
        st["macrocycle"] = golden.profiles()["advanced"]["macrocycle"]
        _add_done(st, "2026-10-03", [{"exercise_id": "front_lever_straddle", "sets": 4, "work_seconds": 10}],
                  sid="custom_fl")
        ctx = ac.build_athlete_context(st, REF, with_proposals=False, include_next_week=False)
        assert "custom_fl" in ctx["guards"]["heavy_pull_days"].get("2026-10-03", [])
        # Same for a one-arm negative (pull_bw L4), never for a plain pull-up.
        st2 = _tested_state()
        st2["macrocycle"] = st["macrocycle"]
        _add_done(st2, "2026-10-03", [{"exercise_id": "one_arm_pullup_negative", "sets": 3, "reps": 2}], sid="custom_oa")
        _add_done(st2, "2026-10-02", [{"exercise_id": "pullup", "sets": 3, "reps": 8}], sid="custom_pu")
        days = ac.build_athlete_context(st2, REF, with_proposals=False, include_next_week=False)["guards"]["heavy_pull_days"]
        assert "custom_oa" in days.get("2026-10-03", []) and "2026-10-02" not in days

    def test_untested_athlete_front_lever_day_is_not_counted(self):
        st = copy.deepcopy(golden.profiles()["untested"])
        _add_done(st, "2026-10-03", [{"exercise_id": "front_lever_straddle", "sets": 4, "work_seconds": 10}],
                  sid="custom_fl")
        ctx = ac.build_athlete_context(st, REF, with_proposals=False, include_next_week=False)
        assert "2026-10-03" not in ctx["guards"]["heavy_pull_days"]

    def test_comp_drill_is_rendered_finger_hard_and_comfy_board_drills_are_not(self):
        st = _tested_state()
        st["macrocycle"] = golden.profiles()["advanced"]["macrocycle"]
        text = ac.render_text(ac.build_athlete_context(st, REF, with_proposals=False, include_next_week=False))
        assert "three_attempt_comp (dita-hard)" in text
        assert "glued_feet_board (dita-hard)" not in text and "position_menu_3way (dita-hard)" not in text
