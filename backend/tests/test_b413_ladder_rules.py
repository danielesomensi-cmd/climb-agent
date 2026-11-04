"""B413 — bodyweight ladder rules (D3 + D5 on the ladders, Daniele's A1).

- Label steps (D5): very_easy +3, easy +2, ok +1, hard −1, very_hard the
  failure path; one table shared by the closed loop and the history seed.
- A1: a DONE row with no label counts exactly as ``ok`` — the step, the top of
  the band, the promotion (a proposal in a custom), the R11 clock. A row not
  done (skipped, ``completed: false`` without the sets, a player row with no
  counted set) moves nothing.
- One "done" predicate (``bw_ladders.ladder_row_done``) for the seed and the
  closed loop; ``completed: false`` with every set logged is done.
- Phases: performance is not frozen (full sets, steps, promotions) but a
  guarded level (hanging / heavy pull, or the promotion into one) defers its
  level / tempo change; the deload stays frozen (one set fewer, nothing up).
- Seed (D1, second half): the dose the closed loop would give after the last
  clean session; no retroactive walk; an unrated row never below an earlier
  rated dose; an unknown dose keeps the previous one; no level change.
- Gate closed (untested / expired test): the ladders are neither read nor
  written.
"""

from __future__ import annotations

import copy
import json

import pytest

from backend.engine import bw_ladders as bl
from backend.engine import bw_progression as bp
from backend.engine.progression_v1 import apply_feedback
from backend.tests import c272_golden_cases as golden
from backend.tests.test_c272_bw_ladders_catalog import FIXTURE, _add_done, _tested_state

REF = "2026-10-06"  # strength_power in the golden macrocycle
PHASES = ("base", "strength_power", "power_endurance", "performance", "deload")


def _fam(name):
    return bp.family_doc(name)


def _entry(family, level_idx, target, **extra):
    e = {"level_idx": level_idx, "target": target}
    e.update(extra)
    return bp._normalize(e, _fam(family))


def _log(day, items, sid="core_training"):
    return {"date": day, "session_id": sid, "feedback_contract": 2, "actual": {"exercise_feedback_v1": items}}


def _state_with(**entries):
    st = _tested_state()
    st["bw_progression"] = {k: dict(v) for k, v in entries.items()}
    return st


def _strip(entry):
    return {k: v for k, v in entry.items() if k not in ("_prev", "last_outcome")}


def _add_session(st, d, session):
    """A done session of any id (``_add_done`` always makes a custom one)."""
    from datetime import date

    dd = date.fromisoformat(d)
    monday = dd.fromordinal(dd.toordinal() - dd.weekday()).isoformat()
    plan = st.setdefault("week_plans", {}).setdefault(monday, {"start_date": monday, "weeks": [{"days": []}]})
    plan["weeks"][0]["days"].append({"date": d, "sessions": [dict(session, status="done")]})


def _all_levels():
    for name, fam in bp._families().items():
        for lv in fam["levels"]:
            yield name, fam, int(lv["level_idx"]), lv


# ---------------------------------------------------------------------------
# Steps and A1
# ---------------------------------------------------------------------------

class TestSteps:
    def test_label_steps_table(self):
        assert bp.LABEL_STEPS is bl.LABEL_STEPS
        assert bl.LABEL_STEPS == {"very_easy": 3, "easy": 2, "ok": 1, "hard": -1, "very_hard": -2}
        f = _fam("rollout")  # ring_fallout band 6-12, step 1
        got = {lab: bp.next_state(_entry("rollout", 1, 8), f, label=lab, ref_date=REF)[0]["target"]
               for lab in ("very_easy", "easy", "ok", "hard", "very_hard")}
        assert got == {"very_easy": 11, "easy": 10, "ok": 9, "hard": 7, "very_hard": 6}
        f = _fam("front_lever")  # seconds, step 2 s
        n, _ = bp.next_state(_entry("front_lever", 3, 9, sets=4), f, label="ok", ref_date=REF)
        assert n["target"] == 11

    def test_unrated_done_equals_ok_including_level_change(self):
        # Every family, every level, every target of the band, every phase:
        # a done unrated row is EXACTLY an ok — level changes included.
        for name, fam, idx, lv in _all_levels():
            b = lv["band"]
            for target in range(int(b["lo"]), int(b["hi"]) + 1, int(b["step"])):
                for streak in (0, 1):
                    e = _entry(name, idx, target, top_streak=streak)
                    for phase in PHASES:
                        for custom in (False, True):
                            kw = dict(ref_date=REF, phase=phase, custom=custom)
                            assert bp.next_state(e, fam, label=None, completed=True, **kw) == \
                                bp.next_state(e, fam, label="ok", completed=True, **kw), (name, idx, target, phase)
        # The level change fires on an unrated row (engine: promoted).
        f = _fam("front_lever")
        n, o = bp.next_state(_entry("front_lever", 3, 15, sets=4, top_streak=1), f, label=None, ref_date=REF)
        assert (n["exercise_id"], n["target"], o["kind"]) == ("front_lever_full", 5, "promoted")
        # Through apply_feedback: a dialog row marked done, no label.
        st = _state_with(compression_floor={"level_idx": 3, "target": 30, "sets": 3, "last_session_date": "2026-10-01"})
        out = apply_feedback(_log(REF, [{"exercise_id": "straddle_l_sit", "completed": True,
                                         "bw_ladder": "engine"}]), st)
        e = out["bw_progression"]["compression_floor"]
        assert (e["exercise_id"], e["target"], e["last_outcome"]["kind"]) == ("v_sit_45", 5, "promoted")

    def test_unrated_not_done_is_noop(self):
        base = {"level_idx": 3, "target": 20, "sets": 3, "last_session_date": "2026-10-01"}
        cases = [
            ("core_training", {"completed": False}),                              # guided: not done
            ("core_training", {"completed": True, "feedback_label": "skipped"}),  # skipped
            ("core_training", {"completed": True, "completed_sets": 0}),          # guided: no set counted
            ("custom_cs_core", {"completed": True}),                               # custom player: no set
            ("custom_cs_core", {"completed": False, "completed_sets": 2, "prescribed_sets": 3}),
        ]
        for sid, extra in cases:
            st = _state_with(compression_floor=base)
            item = dict({"exercise_id": "straddle_l_sit", "bw_ladder": "engine"}, **extra)
            out = apply_feedback(_log(REF, [item], sid=sid), copy.deepcopy(st))
            assert out["bw_progression"]["compression_floor"] == st["bw_progression"]["compression_floor"], (sid, extra)
            assert bp.apply_bw_item(copy.deepcopy(st), item, rating=None, date_value=REF,
                                    session_key=f"{REF}|{sid}", phase="strength_power") == {
                "family": "compression_floor", "kind": "hold", "applied": False, "message": bp.NOT_DONE_MESSAGE}
        # next_state itself: not done, no label, no measure → unchanged.
        e = _entry("compression_floor", 3, 20)
        assert bp.next_state(e, _fam("compression_floor"), label=None, completed=False, ref_date=REF) == (
            e, {"kind": "hold"})

    @pytest.mark.parametrize("sid,row,done", [
        ("core_training", {"completed": True}, True),                                   # dialog
        ("core_training", {"completed": True, "completed_sets": 3}, True),              # guided
        ("core_training", {"completed": True, "completed_sets": 0}, False),             # guided, no set
        ("core_training", {"completed": False}, False),                                 # guided, not done
        ("core_training", {"completed": False, "completed_sets": 3}, True),             # all sets logged
        ("core_training", {"completed": False, "completed_sets": 2}, False),            # short of the dose
        ("core_training", {"completed": True, "feedback_label": "skipped"}, False),
        ("custom_cs_core", {"completed": True}, False),                                 # custom player, no set
        ("custom_cs_core", {"completed": True, "completed_sets": 1}, True),             # custom player
    ])
    def test_done_predicate_shared_by_seed_and_closed_loop(self, sid, row, done):
        item = dict({"exercise_id": "ring_fallout"}, **row)
        planned = {"exercise_id": "ring_fallout", "sets": 3, "reps": 9}
        # 1. the predicate
        assert bl.ladder_row_done(item, player_session=sid.startswith("custom_"), dose_sets=3) is done
        # 2. the seed: the logged row of a done session seeds the family iff done
        st = _tested_state()
        session = {"session_id": sid, "exercises": [planned], "actual_exercises": [dict(item)]}
        if sid.startswith("custom_"):
            session["is_custom"] = True
        _add_session(st, "2026-10-01", session)
        r = next(x for x in bl.seed_levels(st, REF)["families"] if x["family"] == "rollout")
        assert (r["source"] == "history") is done
        if done:
            assert (r["exercise_id"], r["target"]) == ("ring_fallout", 10)  # 3x9 unrated + 1
        # 3. the closed loop: the same row, unrated, moves the entry iff done
        st = _state_with(rollout={"level_idx": 1, "target": 9, "sets": 3, "last_session_date": "2026-10-01"})
        out = apply_feedback(_log(REF, [dict(item, bw_ladder="engine")], sid=sid), copy.deepcopy(st))
        moved = out["bw_progression"]["rollout"]["target"] == 10
        assert moved is done

    def test_completed_false_with_all_sets_is_not_a_failure(self):
        base = {"level_idx": 1, "target": 9, "sets": 3, "last_session_date": "2026-10-01"}
        item = {"exercise_id": "ring_fallout", "feedback_label": "ok", "completed": False, "completed_sets": 3,
                "bw_ladder": "engine"}
        out = apply_feedback(_log(REF, [item]), _state_with(rollout=base))
        e = out["bw_progression"]["rollout"]
        assert (e["level_idx"], e["target"], e["last_outcome"]["kind"]) == (1, 10, "step_up")
        # Short of the dose: still a failed session (R1), as before.
        out = apply_feedback(_log(REF, [dict(item, completed_sets=2)]), _state_with(rollout=base))
        e = out["bw_progression"]["rollout"]
        assert (e["target"], e["last_outcome"]["kind"]) == (7, "step_down")
        # Unrated with every set: an ok.
        out = apply_feedback(_log(REF, [{k: v for k, v in item.items() if k != "feedback_label"}]),
                             _state_with(rollout=base))
        assert out["bw_progression"]["rollout"]["target"] == 10


# ---------------------------------------------------------------------------
# Top of the band, R5, measures, R12, custom
# ---------------------------------------------------------------------------

class TestTopOfBand:
    def test_ok_at_top_counts_and_very_easy_promotes_two_session_levels(self):
        f = _fam("front_lever")  # straddle: advance_sessions 2
        n1, o1 = bp.next_state(_entry("front_lever", 3, 15, sets=4), f, label="ok", ref_date=REF)
        assert (n1["level_idx"], n1["top_streak"], o1["kind"]) == (3, 1, "top_streak")
        n2, o2 = bp.next_state(n1, f, label="ok", ref_date=REF)
        assert (n2["exercise_id"], o2["kind"]) == ("front_lever_full", "promoted")
        n, o = bp.next_state(_entry("front_lever", 3, 15, sets=4), f, label="very_easy", ref_date=REF)
        assert (n["exercise_id"], n["target"], o["kind"]) == ("front_lever_full", 5, "promoted")
        lat = _fam("lateral")  # copenhagen_plank: advance_sessions 2
        n, o = bp.next_state(_entry("lateral", 2, 20), lat, label="very_easy", ref_date=REF)
        assert (n["exercise_id"], n["target"], o["kind"]) == ("copenhagen_dynamic", 6, "promoted")
        # easy keeps the two sessions.
        n, o = bp.next_state(_entry("lateral", 2, 20), lat, label="easy", ref_date=REF)
        assert (n["level_idx"], n["top_streak"], o["kind"]) == (2, 1, "top_streak")

    def test_r5_projection_never_promotes(self):
        for name, fam, idx, lv in _all_levels():
            b = lv["band"]
            below = int(b["hi"]) - int(b["step"])
            if below < int(b["lo"]):
                continue
            for label in ("very_easy", "easy", "ok", None):
                n, o = bp.next_state(_entry(name, idx, below), fam, label=label, ref_date=REF, phase="strength_power")
                assert n["level_idx"] == idx and n["target"] == int(b["hi"]), (name, idx, label)
                assert n["top_streak"] == 0 and o["kind"] in ("step_up", "hold"), (name, idx, label)

    def test_measure_below_target_ok_adds_nothing(self):
        f = _fam("rollout")
        for label in ("ok", None):
            n, _ = bp.next_state(_entry("rollout", 1, 9), f, label=label, measured=8, ref_date=REF)
            assert n["target"] == 8, label  # the measure is data: it can lower
            n, _ = bp.next_state(_entry("rollout", 1, 9), f, label=label, measured=9, ref_date=REF)
            assert n["target"] == 10, label
        # easy keeps its steps over the measure (only ok is held back).
        n, _ = bp.next_state(_entry("rollout", 1, 9), f, label="easy", measured=8, ref_date=REF)
        assert n["target"] == 10
        lf = _fam("compression_floor")
        n, _ = bp.next_state(_entry("compression_floor", 3, 20), lf, label=None, measured=15, ref_date=REF)
        assert n["target"] == 15

    def test_lower_back_ceiling_still_manual_only(self):
        f = _fam("rollout")  # standing levels from L3: manual only
        for label in ("ok", None, "very_easy"):
            n, o = bp.next_state(_entry("rollout", 2, 8, sets=4, top_streak=1), f, label=label, ref_date=REF)
            assert (n["level_idx"], o["kind"]) == (2, "manual_only"), label

    def test_custom_promotion_still_a_proposal(self):
        f = _fam("compression_floor")
        for label in ("ok", None):
            n, o = bp.next_state(_entry("compression_floor", 3, 30), f, label=label, ref_date=REF, custom=True)
            assert o["kind"] == "promotion_proposed" and n["level_idx"] == 3
            assert n["pending_promotion"]["exercise_id"] == "v_sit_45"
        st = _state_with(compression_floor={"level_idx": 3, "target": 30, "sets": 3, "last_session_date": "2026-10-01"})
        out = apply_feedback(_log(REF, [{"exercise_id": "straddle_l_sit", "completed": True, "completed_sets": 3,
                                         "bw_ladder": "ladder"}], sid="custom_cs_core"), st)
        e = out["bw_progression"]["compression_floor"]
        assert e["level_idx"] == 3 and e["pending_promotion"]["exercise_id"] == "v_sit_45"


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------

class TestPhases:
    def test_performance_not_frozen_guarded_levels_defer(self):
        assert not bp.is_frozen("performance") and bp.is_frozen("deload")
        # Front lever (hanging + heavy pull): grows in the band, the level waits.
        f = _fam("front_lever")
        n, o = bp.next_state(_entry("front_lever", 3, 12, sets=4), f, label="ok", phase="performance", ref_date=REF)
        assert (n["level_idx"], n["target"], o["kind"]) == (3, 14, "step_up")
        e = _entry("front_lever", 3, 15, sets=4, top_streak=1)
        n, o = bp.next_state(e, f, label="very_easy", phase="performance", ref_date=REF)
        assert (n["level_idx"], n["target"], n["top_streak"], o["kind"]) == (3, 15, 2, "deferred")
        assert bp.dose_for(n, f, phase="performance")["sets"] == 4  # full sets
        # The streak stays: the first session of the new cycle moves up.
        n, o = bp.next_state(n, f, label="ok", phase="base", ref_date=REF)
        assert (n["exercise_id"], o["kind"]) == ("front_lever_full", "promoted")
        # Toes-to-bar (hanging, last level): the slower eccentric waits.
        th = _fam("compression_hang")
        n, o = bp.next_state(_entry("compression_hang", 3, 8), th, label="ok", phase="performance", ref_date=REF)
        assert (n["tempo_level"], n["target"], o["kind"]) == (0, 8, "deferred")
        # Promotion INTO a guarded level waits too (lying wipers → half wipers).
        rot = _fam("rotation")
        n, o = bp.next_state(_entry("rotation", 0, 12), rot, label="ok", phase="performance", ref_date=REF)
        assert (n["level_idx"], o["kind"]) == (0, "deferred")
        # Not guarded: promotions are active in performance.
        ph = _fam("push_horizontal")
        n, o = bp.next_state(_entry("push_horizontal", 2, 8), ph, label="ok", phase="performance", ref_date=REF)
        assert (n["exercise_id"], o["kind"]) == ("ring_pushup_rto", "promoted")
        # Regressions stay active on a guarded level.
        n, o = bp.next_state(_entry("front_lever", 3, 6, sets=4, vh_streak=1), f, label="very_hard",
                             phase="performance", ref_date=REF)
        assert (n["level_idx"], o["kind"]) == (2, "level_down")
        assert bp.outcome_message({"kind": "deferred"}, n, f, "performance").startswith("Performance phase")

    def test_deload_minus_one_set_nothing_up(self):
        f = _fam("rollout")
        e = _entry("rollout", 1, 9)
        assert bp.dose_for(e, f, phase="deload")["sets"] == 2
        for label in ("very_easy", "easy", "ok", None):
            n, o = bp.next_state(e, f, label=label, phase="deload", ref_date=REF)
            assert (n["level_idx"], n["target"], o["kind"]) == (1, 9, "frozen"), label
            assert n["last_session_date"] == REF  # a done row still refreshes the R11 clock
            n, o = bp.next_state(_entry("rollout", 1, 12), f, label=label, phase="deload", ref_date=REF)
            assert (n["level_idx"], n["target"]) == (1, 12), label
        n, _ = bp.next_state(e, f, label="hard", phase="deload", ref_date=REF)
        assert n["target"] == 8

    def test_unrated_refreshes_r11_clock(self):
        # Ring push-up last logged 03/08; marked done (no label) on 13/11; on
        # 02/12 (121 days after 03/08) the R11 re-entry would drop it to the
        # push-up — the unrated session moved the clock, so it does not.
        base = {"level_idx": 2, "target": 7, "sets": 3, "last_session_date": "2026-08-03"}
        assert bp.effective_entry(_entry("push_horizontal", 2, 7, last_session_date="2026-08-03"),
                                  _fam("push_horizontal"), "2026-12-02")["level_idx"] == 1
        item = {"exercise_id": "ring_pushup", "completed": True, "bw_ladder": "engine"}
        out = apply_feedback(_log("2026-11-13", [item]), _state_with(push_horizontal=base))
        e = out["bw_progression"]["push_horizontal"]
        assert (e["last_session_date"], e["target"]) == ("2026-11-13", 8)
        eff = bp.effective_entry(e, _fam("push_horizontal"), "2026-12-02")
        assert (eff["exercise_id"], eff["target"], "reentry" in eff) == ("ring_pushup", 8, False)
        # Already at the top, in a custom 'ladder' row: still ring 3x8 on
        # 02/12, with the promotion as a proposal (A1: the unrated row counts).
        top = dict(base, target=8)
        out = apply_feedback(_log("2026-11-13", [dict(item, bw_ladder="ladder", completed_sets=3)],
                                  sid="custom_cs_push"), _state_with(push_horizontal=top))
        e = out["bw_progression"]["push_horizontal"]
        eff = bp.effective_entry(e, _fam("push_horizontal"), "2026-12-02")
        assert (eff["exercise_id"], eff["target"]) == ("ring_pushup", 8)
        assert e["pending_promotion"]["exercise_id"] == "ring_pushup_rto"


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def _seed(st, family, ref=REF):
    return next(r for r in bl.seed_levels(st, ref)["families"] if r["family"] == family)


class TestSeed:
    def test_seed_equals_closed_loop_after_last_session(self):
        # One clean session per label: the seed is next_state's target.
        f = _fam("rollout")
        for label in ("very_easy", "easy", "ok", None):
            st = _tested_state()
            actual = {"exercise_id": "ring_fallout", "completed": True, "completed_sets": 3}
            if label:
                actual["feedback_label"] = label
            _add_done(st, "2026-10-02", [{"exercise_id": "ring_fallout", "sets": 3, "reps": 8}], actual=[actual])
            want = bp.next_state(_entry("rollout", 1, 8), f, label=label, ref_date="2026-10-02")[0]["target"]
            assert _seed(st, "rollout")["target"] == want, label
        # Daniele's rollout: 3x10 ok on 02/10, then 3x9 unrated on 22/10 →
        # 3x10 (not 3x8: no −1 step, never below the dose rated before).
        st = _tested_state()
        _add_done(st, "2026-10-02", [{"exercise_id": "ab_wheel_rollout", "sets": 3, "reps": 10}],
                  actual=[{"exercise_id": "ab_wheel_rollout", "completed": True, "completed_sets": 3,
                           "feedback_label": "ok"}])
        _add_done(st, "2026-10-22", [{"exercise_id": "ab_wheel_rollout", "sets": 3, "reps": 9}], sid="custom_cs_b")
        r = _seed(st, "rollout", "2026-10-25")
        assert (r["exercise_id"], r["sets"], r["target"]) == ("ab_wheel_rollout", 3, 10)
        # An unrated 3x7 after the rated 3x10: the floor is the rated dose.
        st2 = copy.deepcopy(st)
        st2["week_plans"]["2026-10-19"]["weeks"][0]["days"][0]["sessions"][0]["exercises"][0]["reps"] = 7
        r = _seed(st2, "rollout", "2026-10-25")
        assert (r["target"], r["evidence"]["rule"], r["evidence"]["floor"]) == (10, "rated_floor", 10)
        # A RATED lower row is information: it wins.
        st3 = copy.deepcopy(st2)
        st3["week_plans"]["2026-10-19"]["weeks"][0]["days"][0]["sessions"][0]["actual_exercises"] = [
            {"exercise_id": "ab_wheel_rollout", "completed": True, "completed_sets": 3, "feedback_label": "ok"}]
        assert _seed(st3, "rollout", "2026-10-25")["target"] == 8
        # Unknown last dose → the previous known dose; never the bottom (6).
        st4 = copy.deepcopy(st)
        st4["week_plans"]["2026-10-19"]["weeks"][0]["days"][0]["sessions"][0]["exercises"] = [
            {"exercise_id": "ab_wheel_rollout"}]
        r = _seed(st4, "rollout", "2026-10-25")
        assert (r["target"], r["evidence"]["rule"]) == (10, "previous_dose")
        # A seed never changes level: at the top it stays there.
        st5 = _tested_state()
        _add_done(st5, "2026-10-02", [{"exercise_id": "ab_wheel_rollout", "sets": 3, "reps": 12}],
                  actual=[{"exercise_id": "ab_wheel_rollout", "completed": True, "completed_sets": 3,
                           "feedback_label": "very_easy"}])
        r = _seed(st5, "rollout")
        assert (r["level_idx"], r["target"], r["at_top_of_band"]) == (0, 12, True)

    def test_seed_never_walks_the_band_retroactively(self):
        st = _tested_state()
        for d in ("2026-09-22", "2026-09-24", "2026-09-26", "2026-09-29", "2026-10-01"):
            _add_done(st, d, [{"exercise_id": "pallof_press", "sets": 3, "reps": 8}], sid=f"custom_{d}",
                      actual=[{"exercise_id": "pallof_press", "completed": True, "completed_sets": 3,
                               "feedback_label": "ok"}])
        assert _seed(st, "anti_rotation")["target"] == 9  # the last 3x8 + 1, not 8 + 5

    def test_property_unrated_done_never_lowers(self):
        for name, fam, idx, lv in _all_levels():
            b = lv["band"]
            for target in range(int(b["lo"]), int(b["hi"]) + 1, int(b["step"])):
                for phase in PHASES:
                    e = _entry(name, idx, target)
                    n, _ = bp.next_state(e, fam, label=None, completed=True, phase=phase, ref_date=REF)
                    assert n["level_idx"] >= idx, (name, idx, target, phase)
                    if n["level_idx"] == idx:
                        harder = (int(n.get("tempo_level") or 0), float(n.get("added_kg") or 0)) > (
                            int(e.get("tempo_level") or 0), float(e.get("added_kg") or 0))
                        # R7: a tempo / load step restarts the reps lower — a
                        # harder dose, not a lower one.
                        assert harder or n["target"] >= target, (name, idx, target, phase)
                        assert n["sets"] >= e["sets"], (name, idx, target, phase)


# ---------------------------------------------------------------------------
# Gate, determinism, untested
# ---------------------------------------------------------------------------

class TestGateAndPurity:
    def test_gate_closed_ladders_neither_read_nor_written(self):
        un = copy.deepcopy(golden.profiles()["untested"])
        un["bw_progression"] = {"compression_floor": {"level_idx": 3, "target": 20, "sets": 3,
                                                      "last_session_date": "2026-10-01", "source": "user_edit"}}
        assert not bp.tested(un, REF)
        before = copy.deepcopy(un["bw_progression"])
        for item in ({"exercise_id": "straddle_l_sit", "completed": True, "bw_ladder": "engine"},
                     {"exercise_id": "straddle_l_sit", "completed": True, "feedback_label": "easy",
                      "bw_ladder": "ladder"}):
            out = apply_feedback(_log(REF, [item]), copy.deepcopy(un))
            assert out["bw_progression"] == before
            assert bp.apply_bw_item(copy.deepcopy(un), item, rating=item.get("feedback_label"), date_value=REF,
                                    session_key=f"{REF}|core_training") is None
        rows = [{"exercise_id": "straddle_l_sit", "sets": 5, "work_seconds": 15, "progress_mode": "ladder"}]
        assert bp.resolve_custom_ladder_rows(un, rows, REF) == rows
        assert bp.build_resolve_context(un, REF) is None

    def test_determinism_100_runs(self):
        st = _state_with(rollout={"level_idx": 1, "target": 9, "sets": 3, "last_session_date": "2026-10-01"})
        _add_done(st, "2026-09-24", [{"exercise_id": "test_l_sit_hold", "sets": 1}], sid="custom_test_day")
        _add_done(st, "2026-09-30", [{"exercise_id": "front_lever_straddle", "sets": 4, "work_seconds": 12}])
        log = _log(REF, [{"exercise_id": "ring_fallout", "completed": True, "bw_ladder": "engine"},
                         {"exercise_id": "front_lever_straddle", "completed": True, "bw_ladder": "engine"},
                         {"exercise_id": "straddle_l_sit", "feedback_label": "easy", "completed": True,
                          "bw_ladder": "engine"}])
        outs = {json.dumps(apply_feedback(copy.deepcopy(log), copy.deepcopy(st)).get("bw_progression"),
                           sort_keys=True) for _ in range(100)}
        assert len(outs) == 1
        seeds = {json.dumps(bl.seed_levels(st, REF), sort_keys=True) for _ in range(100)}
        assert len(seeds) == 1

    def test_untested_bit_for_bit(self):
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["resolver"]
        now = golden.compute()
        keys = [k for k in expected if k.startswith("untested|")]
        assert keys and all(now[k] == expected[k] for k in keys)
        un = copy.deepcopy(golden.profiles()["untested"])
        items = [{"exercise_id": "straddle_l_sit", "completed": True, "bw_ladder": "engine"},
                 {"exercise_id": "back_extension", "completed": True, "used_external_load_kg": 10}]
        out = apply_feedback(_log(REF, items), un)
        assert "bw_progression" not in out
        assert {r["source"] for r in bl.seed_levels(un, REF)["families"]} == {"catalog"}
