"""A298 — bodyweight progression: the closed loop on the C272 ladders.

Rules R0-R12 of the BW spec (phase1/BW.json engine_rules + selection_rules,
revised), the resolver stage (engine blocks pick the athlete's level, every
block filter re-checked), custom 'ladder' rows (dose at read, promotion as a
tap), the feedback contract (fixed rows with another dose never move the
memory), safety (lower-back levels never assigned automatically, 2 sessions on
risky levels, front lever counts as a heavy pull, frozen in performance /
deload) and the minimal technique ladders (feet readjustments, fear 0-10).

Untested athletes stay bit-for-bit unchanged (resolver golden, feedback).
"""

from __future__ import annotations

import copy
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine import bw_ladders as bl
from backend.engine import bw_progression as bp
from backend.engine import resolve_session as rs
from backend.engine.progression_v1 import _load_catalog_cache, apply_feedback
from backend.tests import c272_golden_cases as golden
from backend.tests.test_c272_bw_ladders_catalog import FIXTURE, _add_done, _tested_state

REF = "2026-10-05"
client = TestClient(app)


def _seeded_state():
    """Advanced profile, L-sit test logged 24/09, front lever straddle history."""
    st = _tested_state()
    _add_done(st, "2026-09-24", [{"exercise_id": "test_l_sit_hold", "sets": 1}], sid="custom_test_day")
    _add_done(st, "2026-09-30", [{"exercise_id": "front_lever_straddle", "sets": 4, "work_seconds": 12}])
    return st


def _fam(name):
    return bp.family_doc(name)


def _entry(family, level_idx, target, **extra):
    e = {"level_idx": level_idx, "target": target}
    e.update(extra)
    return bp._normalize(e, _fam(family))


def _log(day, items, sid="custom_cs_core"):
    return {"date": day, "session_id": sid, "feedback_contract": 2,
            "actual": {"exercise_feedback_v1": items}}


# ---------------------------------------------------------------------------
# Gate, seed, dose
# ---------------------------------------------------------------------------

class TestSeedAndDose:
    def test_untested_athlete_has_no_entry(self):
        st = copy.deepcopy(golden.profiles()["untested"])
        st.setdefault("assessment", {})["tests"] = {"l_sit_hold_seconds": 60}
        assert bp.entries_for(st, REF) == {}
        assert bp.build_resolve_context(st, REF) is None

    def test_seed_entries_and_daniele_doses(self):
        e = bp.entries_for(_seeded_state(), REF)
        assert (e["compression_floor"]["exercise_id"], e["compression_floor"]["target"]) == ("straddle_l_sit", 20)
        assert e["compression_floor"]["source"] == "seed_test"
        assert (e["front_lever"]["exercise_id"], e["front_lever"]["sets"], e["front_lever"]["target"]) == (
            "front_lever_straddle", 4, 10)
        assert e["front_lever"]["source"] == "seed_history"
        assert e["lateral"]["ramp"]["sessions_left"] == 2
        assert "pull_bw" not in e  # tested 2RM keeps the weighted pull-up
        dose = bp.dose_for(e["compression_floor"], _fam("compression_floor"))
        assert (dose["sets"], dose["work_seconds"], dose["reps"], dose["summary"]) == (3, 20, None, "3x20 s")

    def test_mastered_lower_level_gets_the_top_of_its_band(self):
        e = _entry("compression_floor", 3, 20)
        dose = bp.dose_for(e, _fam("compression_floor"), level_idx=2)
        assert (dose["exercise_id"], dose["target"], dose["mastered_level"]) == ("core_l_sit", 30, True)

    def test_seed_is_pure(self):
        st = _seeded_state()
        before = json.dumps(st, sort_keys=True)
        outs = {json.dumps(bp.entries_for(st, REF), sort_keys=True) for _ in range(10)}
        assert len(outs) == 1 and json.dumps(st, sort_keys=True) == before


# ---------------------------------------------------------------------------
# next_state — R0..R12
# ---------------------------------------------------------------------------

class TestNextState:
    def test_deterministic_and_ref_date_is_the_only_time_input(self):
        e = _entry("front_lever", 3, 10, sets=4)
        outs = {json.dumps(bp.next_state(e, _fam("front_lever"), label="easy", ref_date="2026-10-06",
                                         phase="strength_power"), sort_keys=True) for _ in range(100)}
        assert len(outs) == 1

    def test_easy_plus_one_step_very_easy_plus_two_never_a_level_jump(self):
        f = _fam("compression_floor")
        e = _entry("compression_floor", 3, 20)
        n, o = bp.next_state(e, f, label="easy", ref_date=REF)
        assert (n["target"], n["level_idx"], o["kind"]) == (25, 3, "step_up")
        n, o = bp.next_state(e, f, label="very_easy", ref_date=REF)
        assert (n["target"], n["level_idx"]) == (30, 3)
        # very_easy from 25: the projection passes the top but 30 s was never
        # held → only reaches the top (R5: no level jump)…
        n, o = bp.next_state(_entry("compression_floor", 3, 25), f, label="very_easy", ref_date=REF)
        assert (n["level_idx"], n["target"], n["top_streak"], o["kind"]) == (3, 30, 0, "step_up")
        # …and a session performed AT the top promotes (straddle advances after 1).
        n, o = bp.next_state(n, f, label="very_easy", ref_date=REF)
        assert (n["level_idx"], n["exercise_id"], n["target"], o["kind"]) == (4, "v_sit_45", 5, "promoted")

    def test_projected_target_above_the_top_never_promotes(self):
        # ring_fallout 3x11 very_easy: never did 12 → 3x12, no standing rollout.
        n, o = bp.next_state(_entry("rollout", 1, 11), _fam("rollout"), label="very_easy", ref_date=REF)
        assert (n["level_idx"], n["target"], o["kind"]) == (1, 12, "step_up")
        # A measure at the top (min reps 12 on a 3x11 day) does count.
        n, o = bp.next_state(_entry("rollout", 1, 11), _fam("rollout"), label="easy", measured=12, ref_date=REF)
        assert (n["level_idx"], o["kind"]) == (2, "promoted")

    def test_risky_level_needs_two_sessions_at_the_top(self):
        f = _fam("front_lever")
        e = _entry("front_lever", 3, 15, sets=4)
        n1, o1 = bp.next_state(e, f, label="easy", ref_date="2026-10-06")
        assert (n1["level_idx"], n1["target"], n1["top_streak"], o1["kind"]) == (3, 15, 1, "top_streak")
        n2, o2 = bp.next_state(n1, f, label="easy", ref_date="2026-10-08")
        assert (n2["exercise_id"], n2["target"], o2["kind"]) == ("front_lever_full", 5, "promoted")

    def test_ok_between_breaks_the_top_streak(self):
        f = _fam("front_lever")
        n1, _ = bp.next_state(_entry("front_lever", 3, 15, sets=4), f, label="easy", ref_date="2026-10-06")
        n2, _ = bp.next_state(n1, f, label="ok", ref_date="2026-10-08")
        assert (n2["top_streak"], n2["level_idx"]) == (0, 3)

    def test_custom_ladder_promotion_is_a_proposal(self):
        f = _fam("compression_floor")
        n, o = bp.next_state(_entry("compression_floor", 3, 30), f, label="easy", ref_date=REF, custom=True)
        assert o["kind"] == "promotion_proposed"
        assert n["level_idx"] == 3 and n["target"] == 30
        assert n["pending_promotion"]["exercise_id"] == "v_sit_45"

    def test_very_hard_minus_two_steps_then_level_down_after_two(self):
        f = _fam("front_lever")
        e = _entry("front_lever", 3, 14, sets=4)
        n1, o1 = bp.next_state(e, f, label="very_hard", ref_date="2026-10-06")
        assert (n1["level_idx"], n1["target"], n1["vh_streak"], o1["kind"]) == (3, 10, 1, "step_down")
        n2, o2 = bp.next_state(n1, f, label="very_hard", ref_date="2026-10-08")
        assert (n2["exercise_id"], n2["target"], o2["kind"]) == ("front_lever_one_leg", 13, "level_down")

    def test_not_completed_at_the_bottom_drops_a_level(self):
        f = _fam("compression_hang")
        n, o = bp.next_state(_entry("compression_hang", 3, 5), f, label="hard", completed=False, ref_date=REF)
        assert (n["exercise_id"], o["kind"]) == ("knees_to_elbows", "level_down")

    def test_skipped_exercise_moves_nothing(self):
        f = _fam("compression_hang")
        e = _entry("compression_hang", 3, 5)
        n, o = bp.next_state(e, f, label=None, completed=False, ref_date=REF)
        assert o["kind"] == "hold" and n == e

    def test_tempo_and_load_are_removed_before_reps(self):
        f = _fam("compression_hang")
        n, o = bp.next_state(_entry("compression_hang", 3, 6, tempo_level=1), f, label="very_hard", ref_date=REF)
        assert (n["tempo_level"], n["target"], o["kind"]) == (0, 6, "tempo_down")
        n, o = bp.next_state(_entry("compression_hang", 3, 6, tempo_level=0, added_kg=2.0), f,
                             label="very_hard", ref_date=REF)
        assert (n["added_kg"], o["kind"]) == (1.0, "load_down")

    def test_never_below_the_advanced_floor_only_a_warning(self):
        f = _fam("compression_floor")  # floor_level_advanced = 2
        e = _entry("compression_floor", 2, 10, vh_streak=1)
        n, o = bp.next_state(e, f, label="very_hard", ref_date=REF)
        assert (n["level_idx"], o["kind"]) == (2, "floor_warning")

    def test_hard_minus_one_step_never_a_level_change(self):
        n, o = bp.next_state(_entry("rollout", 1, 6), _fam("rollout"), label="hard", ref_date=REF)
        assert (n["level_idx"], n["target"]) == (1, 6)
        n, o = bp.next_state(_entry("rollout", 1, 9), _fam("rollout"), label="hard", ref_date=REF)
        assert (n["level_idx"], n["target"]) == (1, 8)

    def test_not_rated_leaves_the_entry_unchanged(self):
        e = _entry("rollout", 1, 8)
        n, o = bp.next_state(e, _fam("rollout"), label=None, ref_date=REF)
        assert n == e and o["kind"] == "hold"

    def test_measure_is_the_base_label_only_the_delta(self):
        f = _fam("compression_hang")
        n, _ = bp.next_state(_entry("compression_hang", 3, 7), f, label="ok", measured=5, ref_date=REF)
        assert n["target"] == 5
        n, _ = bp.next_state(_entry("compression_hang", 3, 6), f, label="easy", measured=7, ref_date=REF)
        assert n["target"] == 8

    def test_hold_stopped_at_target_uses_the_target_failure_test_minus_20pct(self):
        f = _fam("compression_floor")
        n, _ = bp.next_state(_entry("compression_floor", 3, 20), f, label="ok", measured=20, ref_date=REF)
        assert n["target"] == 20
        n, _ = bp.next_state(_entry("compression_floor", 3, 20), f, label="ok", measured=15, ref_date=REF)
        assert n["target"] == 15
        n, _ = bp.next_state(_entry("compression_floor", 3, 25), f, label="ok", measured=25, test_hold=True,
                             ref_date=REF)
        assert n["target"] == 20

    def test_terminal_tempo_then_handoff_to_the_loaded_variant(self):
        f = _fam("compression_hang")
        n, o = bp.next_state(_entry("compression_hang", 3, 8), f, label="easy", ref_date=REF)
        assert (n["tempo_level"], n["target"], o["kind"]) == (1, 6, "tempo_up")
        assert bp.dose_for(n, f)["tempo_ecc_s"] == 3
        n, o = bp.next_state({**n, "target": 8}, f, label="easy", ref_date=REF)
        assert (n["tempo_level"], bp.dose_for(n, f)["tempo_ecc_s"]) == (2, 5)
        n, o = bp.next_state({**n, "target": 8}, f, label="easy", ref_date=REF)
        # R7 'then load' with a named loaded variant: no kg on toes-to-bar.
        assert (n["added_kg"], o["kind"], o["handoff_exercise_id"]) == (0.0, "handoff", "weighted_hanging_leg_raise")
        msg = bp.outcome_message(o, n, f, None)
        assert msg.startswith("Top of the ladder: move on to") and "+1 kg" in msg

    def test_load_terminal_hands_off_when_the_catalog_names_a_variant(self):
        for family, handoff in (("compression_floor", "weighted_l_sit"), ("lateral", "weighted_side_plank"),
                                ("posterior_chain", "back_extension"), ("push_horizontal", "weighted_pushup")):
            f = _fam(family)
            top = len(f["levels"]) - 1
            hi = f["levels"][top]["band"]["hi"]
            e = _entry(family, top, hi, top_streak=5)
            for _ in range(9):
                e, o = bp.next_state(e, f, label="easy", ref_date=REF)
                assert o["kind"] == "handoff" and o["handoff_exercise_id"] == handoff
            assert e["added_kg"] == 0.0 and e["level_idx"] == top
        # No named variant (single-leg squat): the distal kg step stays.
        f = _fam("single_leg_squat")
        n, o = bp.next_state(_entry("single_leg_squat", 3, 8), f, label="easy", ref_date=REF)
        assert (n["added_kg"], o["kind"]) == (5.0, "load_up")

    def test_front_lever_terminal_never_adds_load(self):
        f = _fam("front_lever")
        e = _entry("front_lever", 4, 10, sets=4, top_streak=1)
        n, o = bp.next_state(e, f, label="easy", ref_date=REF)
        assert o["kind"] == "cap" and n["added_kg"] == 0.0
        assert o["then_exercise_ids"] == ["front_lever_raise", "front_lever_row"]

    def test_frozen_in_performance_and_deload(self):
        f = _fam("compression_floor")
        for phase in ("performance", "deload"):
            n, o = bp.next_state(_entry("compression_floor", 3, 30), f, label="very_easy", phase=phase, ref_date=REF)
            assert (n["level_idx"], n["target"], o["kind"]) == (3, 30, "frozen")
            n, o = bp.next_state(_entry("compression_floor", 3, 20), f, label="easy", phase=phase, ref_date=REF)
            assert n["target"] == 20
            n, o = bp.next_state(_entry("compression_floor", 3, 20), f, label="hard", phase=phase, ref_date=REF)
            assert n["target"] == 15  # regressions stay active
            assert bp.dose_for(_entry("compression_floor", 3, 20), f, phase=phase)["sets"] == 2  # 3 − 1

    def test_reentry_after_120_days_60_for_skills(self):
        e = _entry("rollout", 2, 6, last_session_date="2026-05-01")
        eff = bp.effective_entry(e, _fam("rollout"), REF)
        assert (eff["level_idx"], eff["target"], eff["reentry"]["gap_days"]) == (1, 6, 157)
        fl = _entry("front_lever", 3, 12, sets=4, last_session_date="2026-07-20")
        assert bp.effective_entry(fl, _fam("front_lever"), REF)["level_idx"] == 2  # 77 d > 60
        assert bp.effective_entry(fl, _fam("front_lever"), "2026-09-01")["level_idx"] == 3

    def test_lower_back_levels_are_manual_only(self):
        f = _fam("rollout")  # lower_back_risk_from_level = 3
        e = _entry("rollout", 2, 8, sets=4, top_streak=1)
        n, o = bp.next_state(e, f, label="easy", ref_date=REF)
        assert (n["level_idx"], o["kind"]) == (2, "manual_only")
        assert bp.auto_ceiling(f) == 2 and bp.auto_ceiling(_fam("dragon_flag")) == 3

    def test_lateral_ramp_short_then_long(self):
        st = _seeded_state()
        lat = bp.entries_for(st, REF)["lateral"]
        f = _fam("lateral")
        n1, o1 = bp.next_state(lat, f, label="ok", ref_date="2026-10-06")
        assert n1["ramp"]["sessions_left"] == 1 and n1["level_idx"] == 1
        n2, o2 = bp.next_state(n1, f, label="ok", ref_date="2026-10-08")
        assert (n2["exercise_id"], n2["target"], o2["kind"]) == ("copenhagen_plank", 10, "ramp")


# ---------------------------------------------------------------------------
# apply_feedback
# ---------------------------------------------------------------------------

class TestFeedback:
    def test_engine_row_moves_the_state_and_never_writes_working_loads(self):
        st = _seeded_state()
        out = apply_feedback(_log("2026-10-06", [{"exercise_id": "straddle_l_sit", "feedback_label": "easy",
                                                  "completed": True, "bw_ladder": "engine"}]), st)
        e = out["bw_progression"]["compression_floor"]
        assert (e["target"], e["source"], e["last_outcome"]["message"]) == (25, "feedback", "Next time: 3x25 s")
        assert not any(str(x.get("exercise_id", "")).startswith("bw:") for x in out["working_loads"]["entries"])
        assert out["tests"] == st["tests"] and out.get("assessment") == st.get("assessment")  # R9

    def test_fixed_row_with_another_dose_is_ignored_same_dose_counts(self):
        st = _seeded_state()
        other = {"exercise_id": "straddle_l_sit", "feedback_label": "easy", "completed": True,
                 "bw_ladder": "fixed", "prescribed_sets": 5, "prescribed_work_seconds": 15}
        out = apply_feedback(_log("2026-10-06", [other]), st)
        assert "compression_floor" not in (out.get("bw_progression") or {})
        same = dict(other, prescribed_sets=3, prescribed_work_seconds=20)
        out = apply_feedback(_log("2026-10-06", [same]), st)
        assert out["bw_progression"]["compression_floor"]["target"] == 25
        measured = dict(other, held_s=18)
        out = apply_feedback(_log("2026-10-06", [measured]), st)
        assert out["bw_progression"]["compression_floor"]["target"] == 23  # held 18 < 20 → base 18, easy +5

    def test_measured_hold_short_of_target(self):
        st = _seeded_state()
        out = apply_feedback(_log("2026-10-06", [{"exercise_id": "straddle_l_sit", "feedback_label": "ok",
                                                  "completed": True, "held_s": 15}]), st)
        assert out["bw_progression"]["compression_floor"]["target"] == 15

    def test_other_level_and_untested_are_noops(self):
        st = _seeded_state()
        out = apply_feedback(_log("2026-10-06", [{"exercise_id": "core_l_sit", "feedback_label": "easy",
                                                  "completed": True, "bw_ladder": "engine"}]), st)
        assert "compression_floor" not in (out.get("bw_progression") or {})
        un = copy.deepcopy(golden.profiles()["untested"])
        out = apply_feedback(_log("2026-10-06", [{"exercise_id": "straddle_l_sit", "feedback_label": "easy",
                                                  "completed": True, "bw_ladder": "engine"}]), un)
        assert "bw_progression" not in out

    def test_resubmission_is_idempotent(self):
        st = _seeded_state()
        log = _log("2026-10-06", [{"exercise_id": "straddle_l_sit", "feedback_label": "easy", "completed": True,
                                   "bw_ladder": "engine"}])
        once = apply_feedback(log, st)
        twice = apply_feedback(log, once)
        assert twice["bw_progression"]["compression_floor"]["target"] == 25

    def test_custom_ladder_row_sets_a_pending_promotion(self):
        st = _seeded_state()
        st["bw_progression"] = {"compression_floor": {"level_idx": 3, "target": 30, "sets": 3,
                                                      "last_session_date": "2026-10-01"}}
        out = apply_feedback(_log("2026-10-06", [{"exercise_id": "straddle_l_sit", "feedback_label": "easy",
                                                  "completed": True, "bw_ladder": "ladder"}]), st)
        e = out["bw_progression"]["compression_floor"]
        assert e["level_idx"] == 3 and e["pending_promotion"]["exercise_id"] == "v_sit_45"
        assert bp.session_outcomes(out, "2026-10-06|custom_cs_core")[0]["kind"] == "promotion_proposed"

    def test_feedback_context_tags_rows(self):
        st = _seeded_state()
        st["custom_sessions"] = [{"id": "cs_core", "exercises": [
            {"exercise_id": "straddle_l_sit", "progress_mode": "ladder"},
            {"exercise_id": "toes_to_bar", "progress_mode": "fixed"}]}]
        log = _log("2026-10-06", [{"exercise_id": "straddle_l_sit"}, {"exercise_id": "toes_to_bar"},
                                  {"exercise_id": "weighted_pullup"}])
        bp.attach_feedback_context(log, st, "2026-10-06", "custom_cs_core")
        items = log["actual"]["exercise_feedback_v1"]
        assert [i.get("bw_ladder") for i in items] == ["ladder", "fixed", None]

    def test_history_seed_excludes_the_session_being_logged(self):
        # front lever seeded 4x10 from the 30/09 history; the 07/10 session
        # (4x10, already marked done by post_feedback) must not re-seed it.
        st = _seeded_state()
        _add_done(st, "2026-10-07", [{"exercise_id": "front_lever_straddle", "sets": 4, "work_seconds": 10}],
                  sid="custom_cs_fl")
        item = {"exercise_id": "front_lever_straddle", "completed": True, "bw_ladder": "engine"}
        easy = apply_feedback(_log("2026-10-07", [dict(item, feedback_label="easy")], sid="custom_cs_fl"),
                              copy.deepcopy(st))
        assert easy["bw_progression"]["front_lever"]["target"] == 12
        ok = apply_feedback(_log("2026-10-07", [dict(item, feedback_label="ok")], sid="custom_cs_fl"),
                            copy.deepcopy(st))
        e = ok["bw_progression"]["front_lever"]
        assert e["target"] == 10 and e["last_outcome"]["message"] == "Same dose next time: 4x10 s"

    def test_rated_ok_is_not_reported_as_not_rated(self):
        st = _seeded_state()
        out = apply_feedback(_log("2026-10-06", [{"exercise_id": "straddle_l_sit", "feedback_label": "ok",
                                                  "completed": True, "bw_ladder": "engine"}]), st)
        assert out["bw_progression"]["compression_floor"]["last_outcome"]["message"] == "Same dose next time: 3x20 s"
        un = apply_feedback(_log("2026-10-06", [{"exercise_id": "straddle_l_sit", "completed": True,
                                                 "bw_ladder": "engine"}]), _seeded_state())
        assert "compression_floor" not in (un.get("bw_progression") or {})

    def test_external_load_ladder_levels_progress_too(self):
        st = _seeded_state()
        st["bw_progression"] = {"posterior_chain": {"level_idx": 1, "target": 12},
                                "anti_rotation": {"level_idx": 1, "target": 10}}
        items = [{"exercise_id": "back_extension", "feedback_label": "very_easy", "completed": True,
                  "last_set_reps": 12, "bw_ladder": "engine"},
                 {"exercise_id": "pallof_press", "feedback_label": "easy", "completed": True,
                  "bw_ladder": "engine"}]
        out = apply_feedback(_log("2026-10-06", items), st)
        bw = out["bw_progression"]
        assert (bw["posterior_chain"]["exercise_id"], bw["posterior_chain"]["last_outcome"]["kind"]) == (
            "single_leg_back_extension", "promoted")
        assert bw["anti_rotation"]["target"] == 11
        un = copy.deepcopy(golden.profiles()["untested"])
        before = copy.deepcopy(un)
        out = apply_feedback(_log("2026-10-06", items), un)
        assert "bw_progression" not in out and out.get("working_loads") == apply_feedback(
            _log("2026-10-06", items), before).get("working_loads")

    def test_reentry_with_the_stored_level_kept_unsticks_the_row(self):
        st = _seeded_state()
        st["bw_progression"] = {"compression_floor": {"level_idx": 3, "target": 25,
                                                      "last_session_date": "2026-05-01"}}
        row = {"exercise_id": "straddle_l_sit", "sets": 3, "work_seconds": 25, "progress_mode": "ladder"}
        out = bp.resolve_custom_ladder_rows(st, [row], "2026-10-06")[0]
        assert not out["ladder"].get("above_level") and out["measure"] == "bw_hold"
        assert (out["sets"], out["work_seconds"]) == (3, 10)  # bottom of the stored level's band
        assert out["ladder"]["reentry"]["kept_level"] is True
        res = apply_feedback(_log("2026-10-06", [{"exercise_id": "straddle_l_sit", "feedback_label": "easy",
                                                  "completed": True, "held_s": 10, "bw_ladder": "ladder"}]), st)
        e = res["bw_progression"]["compression_floor"]
        assert (e["level_idx"], e["target"], e["last_session_date"]) == (3, 15, "2026-10-06")

    def test_engine_tag_from_the_played_instances(self):
        st = _seeded_state()
        log = _log("2026-10-06", [{"exercise_id": "straddle_l_sit", "feedback_label": "easy"}], sid="core_training")
        log["planned"] = [{"session_id": "core_training", "exercise_instances": [
            {"exercise_id": "straddle_l_sit", "prescription": {"source": "bw_ladder", "sets": 3}}]}]
        bp.attach_feedback_context(log, st, "2026-10-06", "core_training")
        assert log["actual"]["exercise_feedback_v1"][0]["bw_ladder"] == "engine"
        bogus = _log("2026-10-06", [{"exercise_id": "straddle_l_sit", "bw_ladder": "zzz"}], sid="core_training")
        bp.attach_feedback_context(bogus, st, "2026-10-06", "core_training")
        assert "bw_ladder" not in bogus["actual"]["exercise_feedback_v1"][0]

    def test_sanitize_drops_out_of_range_measures(self):
        w = []
        item = {"exercise_id": "x", "held_s": 0, "sample_readjust": 2.5, "fear_max": 11}
        bp.sanitize_item(item, w)
        assert item == {"exercise_id": "x"} and len(w) == 3
        item = {"exercise_id": "x", "held_s": "18.5", "sample_readjust": 1, "fear_max": 3}
        bp.sanitize_item(item, [])
        assert item == {"exercise_id": "x", "held_s": 18.5, "sample_readjust": 1, "fear_max": 3}


# ---------------------------------------------------------------------------
# Resolver stage
# ---------------------------------------------------------------------------

def _catalog_list():
    data = json.loads(open(rs.os.path.join(golden.REPO_ROOT, golden.EXERCISES), encoding="utf-8").read())
    return data["exercises"] if isinstance(data, dict) else data


def _ctx(entries, phase="strength_power"):
    return {"date": REF, "entries": entries, "phase": phase, "lower_back_zone": False, "used_families": set()}


_FILTERS = dict(location="gym", role_req=["accessory"], domain_req=["core"], pattern_req=None,
                intensity_max=None, limitation_map={}, finger_device=None, user_age=40, experience_years=16)


class TestResolverStage:
    def test_untested_profile_is_bit_for_bit_unchanged(self):
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["resolver"]
        now = golden.compute()
        keys = [k for k in expected if k.startswith("untested|")]
        assert keys and all(now[k] == expected[k] for k in keys)

    def test_pick_above_the_level_is_brought_to_the_level(self):
        cat = _catalog_list()
        by = {e["id"]: e for e in cat}
        ctx = _ctx({"front_lever": _entry("front_lever", 2, 11, sets=4)})
        ex, plan, lvl = rs._bw_ladder_stage(ctx, by["front_lever_straddle"], cat,
                                           available_equipment=["pullup_bar"], **_FILTERS)
        assert (ex["id"], lvl) == ("front_lever_one_leg", 2)
        merged = {"sets_range": [3, 5]}
        audit = bp.stage_prescription(ctx, plan, lvl, merged)
        assert merged["source"] == "bw_ladder" and merged["sets"] == 4 and merged["work_seconds"] == 11
        assert "sets_range" not in merged and audit["measure"] == "bw_hold"
        assert audit["ladder"]["level_name"]

    def test_ladder_role_level_is_reached_by_swap_and_equipment_is_rechecked(self):
        cat = _catalog_list()
        by = {e["id"]: e for e in cat}
        ctx = _ctx({"rollout": _entry("rollout", 1, 6)})
        ex, plan, lvl = rs._bw_ladder_stage(ctx, by["ab_wheel_rollout"], cat,
                                           available_equipment=["ab_wheel", "rings"], **_FILTERS)
        assert ex["id"] == "ring_fallout"
        ctx = _ctx({"rollout": _entry("rollout", 1, 6)})
        ex, plan, lvl = rs._bw_ladder_stage(ctx, by["ab_wheel_rollout"], cat,
                                           available_equipment=["ab_wheel"], **_FILTERS)
        assert (ex["id"], lvl) == ("ab_wheel_rollout", 0)  # no rings → nearest compatible level

    def test_phase_affinity_and_pattern_are_hard_filters_for_the_swap(self):
        cat = _catalog_list()
        by = {e["id"]: e for e in cat}
        ctx = _ctx({"compression_floor": _entry("compression_floor", 3, 20)}, phase="base")
        ex, _plan, lvl = rs._bw_ladder_stage(ctx, by["core_l_sit"], cat, available_equipment=[], **_FILTERS)
        assert (ex["id"], lvl) == ("core_l_sit", 2)  # straddle has no base affinity
        filters = dict(_FILTERS, pattern_req=["anti_extension"])
        ctx = _ctx({"compression_floor": _entry("compression_floor", 3, 20)})
        ex, _plan, lvl = rs._bw_ladder_stage(ctx, by["core_l_sit"], cat, available_equipment=[], **filters)
        assert ex["id"] == "core_l_sit"  # straddle is a compression pattern

    def test_lower_back_levels_never_assigned_by_the_engine(self):
        cat = _catalog_list()
        by = {e["id"]: e for e in cat}
        # A seed above the R12 ceiling is capped…
        ctx = _ctx({"rollout": _entry("rollout", 4, 5, sets=4, source="seed_history")})
        ex, _plan, lvl = rs._bw_ladder_stage(ctx, by["ab_wheel_rollout"], cat,
                                            available_equipment=["ab_wheel", "rings"], **_FILTERS)
        assert lvl <= 2 and ex["id"] != "ab_wheel_rollout_standing"

    def test_level_set_by_hand_above_the_ceiling_is_honoured(self):
        # …but the athlete's explicit choice (settings) stands, and its
        # feedback moves the entry (the loop stays alive on that family).
        st = _seeded_state()
        bp.set_level(st, "rollout", 3, REF, confirm=True)
        ctx = bp.build_resolve_context(st, REF)
        plan = bp.swap_plan(ctx, "ab_wheel_rollout_standing_eccentric")
        assert plan["order"][0] == 3 and plan["candidates"][0] == "ab_wheel_rollout_standing_eccentric"
        out = apply_feedback(_log("2026-10-06", [{"exercise_id": "ab_wheel_rollout_standing_eccentric",
                                                  "feedback_label": "easy", "completed": True,
                                                  "bw_ladder": "engine"}], sid="core_training"), st)
        e = out["bw_progression"]["rollout"]
        assert (e["level_idx"], e["target"], e["last_outcome"]["kind"]) == (3, 4, "step_up")

    def test_recovery_session_gets_no_ladder_stage(self):
        st = _seeded_state()
        rec = {"intent": {"primary_goal": "regeneration"}, "phase_tags": ["deload"]}
        ctx = bp.build_resolve_context(st, REF, "strength_power", session=rec)
        assert ctx is not None and ctx["entries"] == {}
        assert bp.swap_plan(ctx, "side_plank") is None
        normal = bp.build_resolve_context(st, REF, "strength_power", session={"intent": {"primary_goal": "core"}})
        assert normal["entries"]

    def test_second_block_on_the_same_family_keeps_its_pick(self):
        cat = _catalog_list()
        by = {e["id"]: e for e in cat}
        ctx = _ctx({"front_lever": _entry("front_lever", 2, 11, sets=4)})
        ex, plan, lvl = rs._bw_ladder_stage(ctx, by["front_lever_straddle"], cat,
                                           available_equipment=["pullup_bar"], **_FILTERS)
        bp.stage_prescription(ctx, plan, lvl, {})
        ex2, plan2, _ = rs._bw_ladder_stage(ctx, by["front_lever_straddle"], cat,
                                           available_equipment=["pullup_bar"], **_FILTERS)
        assert ex2["id"] == "front_lever_straddle" and plan2 is None

    def test_tested_profile_gets_the_ladder_dose_in_a_real_resolution(self):
        st = copy.deepcopy(golden.profiles()["advanced"])
        st["context"] = {"location": "gym", "gym_id": "g_board", "target_date": "2026-10-07", "date": "2026-10-07"}
        r = rs.resolve_session(golden.REPO_ROOT, "backend/catalog/sessions/v1/strength_long.json", golden.TEMPLATES,
                               golden.EXERCISES, "", user_state_override=st, write_output=False,
                               phase="strength_power")
        fl = [i for i in r["resolved_session"]["exercise_instances"] if str(i["exercise_id"]).startswith("front_lever")]
        assert fl and fl[0]["prescription"]["source"] == "bw_ladder"
        assert fl[0]["suggested"]["bw_ladder"]["ladder"]["family"] == "front_lever"
        assert fl[0]["suggested"]["measure"] == "bw_hold"


# ---------------------------------------------------------------------------
# Custom rows, promotion tap, settings level
# ---------------------------------------------------------------------------

class TestCustom:
    def test_ladder_row_gets_the_dose_fixed_row_untouched(self):
        st = _seeded_state()
        rows = [{"exercise_id": "straddle_l_sit", "sets": 5, "work_seconds": 15, "progress_mode": "ladder"},
                {"exercise_id": "toes_to_bar", "sets": 3, "reps": 8},
                {"exercise_id": "core_l_sit", "sets": 5, "work_seconds": 15, "progress_mode": "ladder"}]
        out = bp.resolve_custom_ladder_rows(st, rows, REF)
        assert (out[0]["sets"], out[0]["work_seconds"], out[0]["stored_sets"], out[0]["progress_source"]) == (
            3, 20, 5, "bw_ladder")
        assert out[0]["measure"] == "bw_hold" and out[0]["ladder"]["proposal"] is None
        assert out[1] == rows[1]
        # same family twice: the second row keeps the dose but shows no second proposal
        assert out[2]["ladder"]["proposal"] is None
        assert rows[0]["sets"] == 5  # input untouched

    def test_terminal_tempo_and_load_reach_the_custom_row(self):
        st = _seeded_state()
        st["bw_progression"] = {"compression_hang": {"level_idx": 3, "target": 6, "tempo_level": 1},
                                "single_leg_squat": {"level_idx": 3, "target": 5, "added_kg": 5.0}}
        rows = [{"exercise_id": "toes_to_bar", "sets": 3, "reps": 8, "progress_mode": "ladder"},
                {"exercise_id": "pistol_squat", "sets": 3, "reps": 8, "progress_mode": "ladder"}]
        out = bp.resolve_custom_ladder_rows(st, rows, REF)
        assert (out[0]["reps"], out[0]["tempo"]) == (6, "3 s eccentric")
        assert (out[1]["reps"], out[1]["load_kg"]) == (5, 5.0)

    def test_row_below_the_level_proposes_a_switch(self):
        st = _seeded_state()
        out = bp.resolve_custom_ladder_rows(st, [{"exercise_id": "core_l_sit", "sets": 5, "work_seconds": 15,
                                                  "progress_mode": "ladder"}], REF)
        assert out[0]["work_seconds"] == 30  # mastered: top of the band
        assert out[0]["ladder"]["proposal"]["kind"] == "switch"
        assert out[0]["ladder"]["proposal"]["to_exercise_id"] == "straddle_l_sit"
        assert "measure" not in out[0]

    def test_untested_custom_rows_unchanged(self):
        un = copy.deepcopy(golden.profiles()["untested"])
        rows = [{"exercise_id": "straddle_l_sit", "sets": 5, "work_seconds": 15, "progress_mode": "ladder"}]
        assert bp.resolve_custom_ladder_rows(un, rows, REF) == rows
        assert bp.attach_technique_measures(un, [{"exercise_id": "no_readjust_drill"}], REF) == [
            {"exercise_id": "no_readjust_drill"}]

    def test_promotion_accept_and_decline(self):
        st = _seeded_state()
        st["bw_progression"] = {"compression_floor": {"level_idx": 3, "target": 30, "sets": 3,
                                                      "pending_promotion": {"to_level_idx": 4, "exercise_id": "v_sit_45"}}}
        dec = copy.deepcopy(st)
        bp.resolve_promotion(dec, "compression_floor", accept=False, ref_date=REF)
        assert dec["bw_progression"]["compression_floor"]["pending_promotion"] is None
        assert dec["bw_progression"]["compression_floor"]["level_idx"] == 3
        bp.resolve_promotion(st, "compression_floor", accept=True, ref_date=REF)
        e = st["bw_progression"]["compression_floor"]
        assert (e["exercise_id"], e["target"], e["source"]) == ("v_sit_45", 5, "user_edit")

    def test_set_level_needs_confirm_above_plus_one(self):
        st = _seeded_state()
        with pytest.raises(PermissionError):
            bp.set_level(st, "rollout", 4, REF)
        e = bp.set_level(st, "rollout", 4, REF, confirm=True)
        assert e["exercise_id"] == "ab_wheel_rollout_standing" and e["source"] == "user_edit"
        with pytest.raises(ValueError):
            bp.set_level(st, "rollout", 9, REF, confirm=True)


class TestApi:
    def _save(self, st):
        deps.save_state(st, None)

    def test_state_allowlist_view_and_promotion_rewrites_only_future_rows(self):
        client.delete("/api/state")
        st = deps.load_state(None)
        st.update(_seeded_state())
        st["custom_sessions"] = [{"id": "cs_core", "name": "Core", "tags": [], "exercises": [
            {"exercise_id": "straddle_l_sit", "sets": 3, "work_seconds": 20, "progress_mode": "ladder"}]}]
        st["bw_progression"] = {"compression_floor": {"level_idx": 3, "target": 30, "sets": 3,
                                                      "pending_promotion": {"to_level_idx": 4, "exercise_id": "v_sit_45"}}}
        done_row = {"exercise_id": "straddle_l_sit", "sets": 3, "work_seconds": 20, "progress_mode": "ladder"}
        st["week_plans"]["2026-10-05"] = {"start_date": "2026-10-05", "weeks": [{"days": [
            {"date": "2026-10-05", "sessions": [{"session_id": "custom_cs_core", "status": "done",
                                                 "exercises": [dict(done_row)]}]},
            {"date": "2026-10-07", "sessions": [{"session_id": "custom_cs_core", "status": "planned",
                                                 "exercises": [dict(done_row)]}]}]}]}
        self._save(st)
        assert client.put("/api/state", json={"bw_progression": st["bw_progression"]}).status_code == 200
        view = client.get("/api/bw-progression", params={"date": "2026-10-06"}).json()
        row = next(r for r in view["families"] if r["family"] == "compression_floor")
        assert row["active"] and row["pending_promotion"]["exercise_id"] == "v_sit_45"
        r = client.post("/api/bw-progression/compression_floor/promotion",
                        json={"accept": True, "date": "2026-10-06", "custom_session_id": "cs_core"})
        assert r.status_code == 200 and r.json()["rows_rewritten"] == 2
        after = deps.load_state(None)
        assert after["custom_sessions"][0]["exercises"][0]["exercise_id"] == "v_sit_45"
        days = after["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        assert days[0]["sessions"][0]["exercises"][0] == done_row  # past / done: immutable
        assert days[1]["sessions"][0]["exercises"][0]["exercise_id"] == "v_sit_45"
        r = client.put("/api/bw-progression/rollout", json={"level_idx": 4, "date": "2026-10-06"})
        assert r.status_code == 409
        r = client.put("/api/bw-progression/nope", json={"level_idx": 0})
        assert r.status_code == 422

    def test_custom_session_stores_progress_mode_and_reads_the_dose(self):
        client.delete("/api/state")
        r = client.post("/api/custom-session", json={"name": "Core", "exercises": [
            {"exercise_id": "straddle_l_sit", "sets": 5, "work_seconds": 15, "progress_mode": "ladder"},
            {"exercise_id": "toes_to_bar", "sets": 3, "reps": 8}]})
        assert r.status_code == 201
        saved = r.json()
        assert saved["exercises"][0]["progress_mode"] == "ladder" and "progress_mode" not in saved["exercises"][1]
        st = deps.load_state(None)
        st.update({k: v for k, v in _seeded_state().items() if k != "custom_sessions"})
        self._save(st)
        got = client.get(f"/api/custom-session/{saved['id']}", params={"date": REF}).json()
        assert (got["exercises"][0]["sets"], got["exercises"][0]["work_seconds"]) == (3, 20)
        assert got["exercises"][0]["ladder"]["family"] == "compression_floor"
        lst = client.get("/api/custom-session/exercises", params={"q": "straddle"}).json()
        item = next(e for e in lst["exercises"] if e["id"] == "straddle_l_sit")
        assert item["ladder"] == {"family": "compression_floor", "level_idx": 3}


# ---------------------------------------------------------------------------
# Technique ladders, heavy pull
# ---------------------------------------------------------------------------

class TestTechnique:
    def test_feet_ladder_two_clean_sessions_up_two_bad_down(self):
        e, k = bp.technique_next(None, "feet", 1, "2026-10-01")
        assert (e["level"], k) == ("P1", "hold")
        e, k = bp.technique_next(e, "feet", 0, "2026-10-03")
        assert (e["level"], k) == ("P2", "promoted")
        e, _ = bp.technique_next(e, "feet", 4, "2026-10-05")
        e, k = bp.technique_next(e, "feet", 3, "2026-10-07")
        assert (e["level"], k) == ("P1", "level_down")

    def test_falls_ladder_fear(self):
        e, _ = bp.technique_next(None, "falls", 2, "2026-10-01")
        e, k = bp.technique_next(e, "falls", 3, "2026-10-03")
        assert (e["level"], k) == ("F2", "promoted")
        e, k = bp.technique_next(e, "falls", 8, "2026-10-05")
        assert (e["level"], k) == ("F1", "level_down")

    def test_apply_feedback_tracks_technique_for_tested_only(self):
        st = _seeded_state()
        items = [{"exercise_id": "no_readjust_drill", "feedback_label": "ok", "sample_readjust": 1},
                 {"exercise_id": "fall_ladder", "fear_max": 2}]
        out = apply_feedback(_log("2026-10-06", items), st)
        tech = out["bw_progression"]["technique"]
        assert tech["feet"]["level"] == "P1" and tech["feet"]["good_streak"] == 1
        assert tech["falls"]["level"] == "F1"
        out2 = apply_feedback(_log("2026-10-06", items), out)  # resubmission: same streak
        assert out2["bw_progression"]["technique"]["feet"]["good_streak"] == 1
        un = copy.deepcopy(golden.profiles()["untested"])
        assert "bw_progression" not in apply_feedback(_log("2026-10-06", items), un)

    def test_only_drills_of_the_current_feet_level_count(self):
        st = _seeded_state()
        st["bw_progression"] = {"technique": {"feet": {"level": "P3", "good_streak": 1, "bad_streak": 0}}}
        p1_drill = [{"exercise_id": "no_readjust_drill", "sample_readjust": 0}]
        out = apply_feedback(_log("2026-10-06", p1_drill), copy.deepcopy(st))
        assert out["bw_progression"]["technique"]["feet"]["level"] == "P3"
        assert out["bw_progression"]["technique"]["feet"]["good_streak"] == 1
        p3_drill = [{"exercise_id": "vertical_small_feet_limit", "sample_readjust": 1}]
        out = apply_feedback(_log("2026-10-06", p3_drill), copy.deepcopy(st))
        assert out["bw_progression"]["technique"]["feet"]["level"] == "P4"
        # The measure is only asked on the drills of the current level.
        rows = bp.attach_technique_measures(st, [{"exercise_id": "no_readjust_drill"},
                                                 {"exercise_id": "vertical_small_feet_limit"}], REF)
        assert "measure" not in rows[0] and rows[1]["measure"] == "feet_readjust"

    def test_technique_measure_kinds(self):
        assert bp.technique_measure_kind("no_readjust_drill") == "feet_readjust"
        assert bp.technique_measure_kind("fall_ladder") == "fear_max"
        assert bp.technique_measure_kind("pushup") is None


class TestHeavyPull:
    def test_front_lever_counts_as_heavy_pull_for_tested_only(self):
        from backend.engine.key_sessions_v1 import _is_heavy_pull

        s = {"session_id": "custom_cs_fl", "status": "planned",
             "exercises": [{"exercise_id": "front_lever_tuck", "sets": 4, "work_seconds": 10}]}
        assert _is_heavy_pull(_seeded_state(), s, "2026-10-06") is True
        assert _is_heavy_pull(copy.deepcopy(golden.profiles()["untested"]), s, "2026-10-06") is False


class TestMigration:
    def test_dry_run_marks_future_ladder_rows_and_prints_levels(self, capsys):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "migrate_bw_ladders", str(golden.REPO_ROOT) + "/scripts/migrate_bw_ladders.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        st = _seeded_state()
        st["custom_sessions"] = [{"id": "cs_core", "exercises": [
            {"exercise_id": "straddle_l_sit", "sets": 3}, {"exercise_id": "toes_to_bar", "progress_mode": "fixed"},
            {"exercise_id": "weighted_pullup", "sets": 4}]}]
        st["week_plans"]["2026-10-05"] = {"weeks": [{"days": [
            {"date": "2026-10-04", "sessions": [{"session_id": "custom_cs_core", "status": "planned",
                                                 "exercises": [{"exercise_id": "straddle_l_sit"}]}]},
            {"date": "2026-10-08", "sessions": [{"session_id": "custom_cs_core", "status": "done",
                                                 "exercises": [{"exercise_id": "straddle_l_sit"}]}]},
            {"date": "2026-10-09", "sessions": [{"session_id": "custom_cs_core", "status": "planned",
                                                 "exercises": [{"exercise_id": "straddle_l_sit"}]}]}]}]}
        before = json.dumps(st, sort_keys=True)
        new, log = mod.migrate_state(st, None, date(2026, 10, 6))
        assert json.dumps(st, sort_keys=True) == before  # input untouched
        rows = new["custom_sessions"][0]["exercises"]
        assert rows[0]["progress_mode"] == "ladder" and rows[1]["progress_mode"] == "fixed"
        assert "progress_mode" not in rows[2]
        days = new["week_plans"]["2026-10-05"]["weeks"][0]["days"]
        assert "progress_mode" not in days[0]["sessions"][0]["exercises"][0]  # past
        assert "progress_mode" not in days[1]["sessions"][0]["exercises"][0]  # done
        assert days[2]["sessions"][0]["exercises"][0]["progress_mode"] == "ladder"
        assert len(log) == 2
        assert "level compression_floor: L3 straddle_l_sit 3x20 s" in capsys.readouterr().out
        un = copy.deepcopy(golden.profiles()["untested"])
        assert mod.migrate_state(un, None, date(2026, 10, 6))[1] == []
