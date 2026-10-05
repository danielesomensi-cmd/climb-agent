"""A293 (R7a) — the read-only athlete context for Claude Code.

Covers ``backend/engine/athlete_context.py``:
- pure / deterministic / input never mutated / JSON-serialisable;
- position (pause-aware, via macro_position), maxima per PROTOCOL with the
  COMPUTED confidence (stored "high" ignored), anchored loads taken verbatim
  from ``anchored_load`` (no local formula);
- key sessions (A294 ``key_sessions_v1``, switched from the A293 fallback): current week only, no carried debt,
  skipped ids recovered from ``session_completion_log`` by date, unknown ids,
  technique + try-hard in every phase (try-hard not in deload);
- guards from session PROPERTIES (finger gap, hang-test block, pre-limit pull
  / front lever, heavy pulls per 7 days, HIIT, hard cap), never a load score;
- variety (actual_exercises not the union, tests excluded, 3 Monday weeks),
  working-load flags, try-hard outcomes from outdoor notes;
- the athlete plan doc: notes block present, every referenced catalog id
  exists (or is declared NEW / C271);
- the /custom-session command file.
"""

from __future__ import annotations

import json
import re
import sys
import types
from copy import deepcopy
from pathlib import Path

import pytest

from backend.engine import athlete_context as ac
from backend.engine.anchored_load import anchored_load
from backend.engine.macro_position import position_on

REPO_ROOT = Path(__file__).resolve().parents[2]
TODAY = "2026-10-04"  # Sunday, SP week 2/4


# ---------------------------------------------------------------------------
# Builders (synthetic copy of the 2026-10-04 shape, no prod data)
# ---------------------------------------------------------------------------

def _macrocycle(start: str = "2026-09-07") -> dict:
    return {
        "start_date": start,
        "phases": [
            {"phase_id": "base", "duration_weeks": 2},
            {"phase_id": "strength_power", "duration_weeks": 4, "intensity_cap": "max"},
            {"phase_id": "power_endurance", "duration_weeks": 3},
            {"phase_id": "performance", "duration_weeks": 3},
            {"phase_id": "deload", "duration_weeks": 1},
        ],
    }


def _sess(slot, sid, status=None, **kw):
    s = {"slot": slot, "session_id": sid}
    if status:
        s["status"] = status
    s.update(kw)
    return s


def _week(start: str, days: dict, **extra) -> dict:
    from datetime import date, timedelta

    d0 = date.fromisoformat(start)
    out_days = []
    for k in range(7):
        d = (d0 + timedelta(days=k)).isoformat()
        out_days.append({"date": d, "weekday": ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[k],
                         "sessions": days.get(d, [])})
    plan = {"start_date": start, "weeks": [{"week_index": 1, "days": out_days}],
            "profile_snapshot": {"phase_id": "strength_power", "hard_cap_per_week": 4}}
    plan.update(extra)
    return plan


def _state(**over) -> dict:
    prev_week = _week("2026-09-21", {
        "2026-09-23": [_sess("evening", "limit_boulder_gym", "skipped", tags={"hard": True, "finger": True})],
    })
    cur_week = _week("2026-09-28", {
        "2026-09-28": [_sess("evening", "technique_focus_gym", "done", tags={"hard": False, "finger": False})],
        "2026-09-30": [_sess("evening", "regeneration_easy", "skipped", tags={"hard": False, "finger": False})],
        "2026-10-02": [_sess("evening", "custom_cs_hiit", "done", is_custom=True, name="Work — HIIT 4x4 (VO2max)",
                             tags={"hard": False, "finger": False},
                             exercises=[{"exercise_id": "easy_run_zone2", "sets": 1}])],
        "2026-10-04": [_sess("morning", "custom_cs_pull", "done", is_custom=True, name="Trazioni",
                             tags={"hard": True, "finger": False},
                             exercises=[{"exercise_id": "weighted_pullup", "sets": 4, "reps": 3},
                                        {"exercise_id": "dead_bug", "sets": 2}],
                             actual_exercises=[{"exercise_id": "weighted_pullup", "completed_sets": 4,
                                                "completed_reps": 3, "used_external_load_kg": 30.0},
                                               {"exercise_id": "toes_to_bar", "completed_sets": 3,
                                                "completed_reps": 6}])],
    })
    next_week = _week("2026-10-05", {
        "2026-10-05": [_sess("evening", "limit_boulder_gym", tags={"hard": True, "finger": True})],
        "2026-10-06": [_sess("lunch", "prehab_maintenance", tags={"hard": False, "finger": False})],
        "2026-10-07": [_sess("lunch", "custom_cs_hiit", "planned", is_custom=True, name="Work — HIIT 4x4 (VO2max)",
                             tags={"hard": False, "finger": False}),
                       _sess("evening", "power_contact_gym", tags={"hard": True, "finger": True})],
        "2026-10-09": [_sess("evening", "strength_long", tags={"hard": True, "finger": True})],
        "2026-10-11": [_sess("evening", "finger_maintenance_gym", tags={"hard": False, "finger": True})],
    })
    state = {
        "bodyweight_kg": 78,
        "goal": {"goal_type": "lead_grade", "discipline": "lead", "target_grade": "8b",
                 "target_style": "redpoint", "current_grade": "8a+", "deadline": "2026-12-06"},
        "macrocycle": _macrocycle(),
        "preferences": {"finger_training_device": "hangboard"},
        "planning_prefs": {"hard_day_cap_per_week": 4},
        "tests": {
            "max_strength": [
                {"date": "2026-03-17", "test_id": "max_hang_5s_total_load", "total_load_kg": 120.0,
                 "external_load_kg": 43.0, "bodyweight_kg": 77.0, "exercise_id": "max_hang_5s", "confidence": "high"},
                {"date": "2026-09-24", "test_id": "max_hang_7s_total_load", "total_load_kg": 116.0,
                 "external_load_kg": 40.0, "bodyweight_kg": 76.0, "exercise_id": "max_hang_7s", "confidence": "high"},
            ],
            "pulling_strength": [
                {"date": "2026-09-24", "test_id": "weighted_pullup_2rm", "total_load_2rm_kg": 123.0,
                 "external_load_2rm_kg": 45.0, "estimated_1rm_kg": 128.9, "bodyweight_kg": 78.0,
                 "exercise_id": "weighted_pullup", "confidence": "high"},
            ],
        },
        "working_loads": {"entries": [
            {"key": "weighted_pullup", "exercise_id": "weighted_pullup", "setup": {}, "updated_at": "2026-10-04",
             "last_reps": 3, "last_external_load_kg": 30.0, "last_total_load_kg": 108.0,
             "next_external_load_kg": 28.5, "next_total_load_kg": 106.5, "last_feedback_label": "ok"},
            {"key": "max_hang_7s", "exercise_id": "max_hang_7s", "setup": {}, "updated_at": "2026-06-01",
             "last_external_load_kg": 40.0, "next_external_load_kg": 40.0, "last_feedback_label": "ok"},
        ]},
        "week_plans": {"2026-09-21": prev_week, "2026-09-28": cur_week, "2026-10-05": next_week},
        "session_completion_log": [
            {"date": "2026-09-30", "status": "skipped", "session_id": "finger_strength_home"},
            {"date": "2026-09-29", "status": "skipped", "session_id": ""},
            {"date": "2026-09-23", "status": "skipped", "session_id": "limit_boulder_gym"},
        ],
        "limitations": {"active_flags": [], "details": []},
        "trips": [{"name": "Spring trip", "start_date": "2026-11-20", "end_date": "2026-11-27"}],
    }
    state.update(over)
    return state


def _outdoor() -> list:
    return [{"entry": {"date": "2026-10-03", "spot_name": "Berdorf", "discipline": "lead",
                       "notes": "Progetto: T1 M7 FALL +1 | T2 M8 TAKE",
                       "routes": [
                           {"name": "Warmup", "grade": "6b", "attempts": [{"result": "sent"}]},
                           {"name": "Jactatio", "grade": "8a",
                            "attempts": [{"result": "fell", "notes": "T3 M5 LET_GO"}]},
                       ]}}]


def _ctx(state=None, **kw):
    kw.setdefault("outdoor_rows", _outdoor())
    return ac.build_athlete_context(state if state is not None else _state(), TODAY, **kw)


def _req(ctx, key):
    return next(r for r in ctx["key_sessions"]["requirements"] if r["key"] == key)


# ---------------------------------------------------------------------------
# Purity
# ---------------------------------------------------------------------------

class TestPurity:
    def test_deterministic_and_input_untouched(self):
        st, rows = _state(), _outdoor()
        snap_st, snap_rows = deepcopy(st), deepcopy(rows)
        a = ac.build_athlete_context(st, TODAY, outdoor_rows=rows)
        b = ac.build_athlete_context(st, TODAY, outdoor_rows=rows)
        assert a == b
        assert st == snap_st and rows == snap_rows

    def test_json_serialisable_and_versioned(self):
        ctx = _ctx()
        json.dumps(ctx)
        assert ctx["version"] == ac.VERSION and ctx["as_of"] == TODAY

    def test_empty_state_no_crash(self):
        ctx = ac.build_athlete_context({}, TODAY)
        assert ctx["position"]["available"] is False
        assert all(v is None for v in ctx["anchors"]["exercises"].values())
        assert "nessun macrociclo" in ac.render_text(ctx)

    def test_constants_are_the_engine_ones(self):
        from backend.engine import retest_policy as rp
        from backend.engine.anchored_load import HEAVY_PULL_WEEKLY_MAX

        assert ac.FINGER_GAP_H == rp.FINGER_GAP_H == 48
        assert ac.RETEST_BLOCK_H == rp.RETEST_BLOCK_H == 72
        assert ac.HEAVY_PULL_MAX_PER_7D == HEAVY_PULL_WEEKLY_MAX


# ---------------------------------------------------------------------------
# Position, maxima, anchors
# ---------------------------------------------------------------------------

class TestPositionMaximaAnchors:
    def test_position_sp_week_2_of_4(self):
        pos = _ctx()["position"]
        assert pos["phase_id"] == "strength_power"
        assert pos["week_in_phase_1based"] == 2 and pos["phase_weeks"] == 4
        assert pos["goal"]["target_grade"] == "8b"

    def test_position_is_pause_aware(self):
        st = _state()
        st["macrocycle"]["pause"] = {"active_since": "2026-09-14"}
        pos = _ctx(st)["position"]
        ref = position_on(st["macrocycle"], TODAY)
        assert pos["phase_id"] == ref["phase_id"] == "base" and pos["paused"] is True

    def test_maxima_per_protocol_with_computed_confidence(self):
        mx = _ctx()["maxima"]
        h7, h5, pull = mx["max_hang_7s_total_load"], mx["max_hang_5s_total_load"], mx["weighted_pullup_2rm"]
        assert h7["total_kg"] == 116.0 and h7["date"] == "2026-09-24"
        # The 5 s max comes from the FRESHER 7 s test, never the March 5 s test.
        assert h5["converted"] is True and h5["date"] == "2026-09-24"
        assert pull["one_rm_kg"] == 128.9
        # Stored "high" is ignored: no finger/pull exposure in the 21 days before.
        assert h7["stored_confidence"] == "high" and h7["confidence"] == "low"
        assert h7["confidence_basis"] == "computed"

    def test_confidence_high_with_archived_exposures(self):
        archive = [{"week_start": "2026-09-07", "plan": _week("2026-09-07", {
            "2026-09-08": [_sess("evening", "finger_strength_home", "done")],
            "2026-09-11": [_sess("evening", "strength_long", "done")],
        })}]
        mx = _ctx(archived_weeks=archive)["maxima"]
        assert mx["max_hang_7s_total_load"]["confidence"] == "high"
        assert mx["weighted_pullup_2rm"]["confidence"] == "low"  # only strength_long → 1 pull day

    def test_anchors_are_anchored_load_verbatim(self):
        st = _state()
        ctx = _ctx(st)
        for ex in ("weighted_pullup", "max_hang_7s"):
            ref = anchored_load(st, ex, date=TODAY)
            row = ctx["anchors"]["exercises"][ex]
            assert row["total"] == ref["total"] and row["external"] == ref["external"]
            assert row["rep_scheme"] == ref["rep_scheme"] and row["cap"] == ref["cap"]

    def test_untested_athlete_has_no_anchor_numbers(self):
        st = _state(tests={})
        ctx = _ctx(st)
        assert all(v is None for v in ctx["anchors"]["exercises"].values())
        assert "carico non disponibile" in ac.render_text(ctx)

    def test_stale_test_flags_max_not_tested(self):
        ctx = ac.build_athlete_context(_state(), "2027-02-01")
        codes = {w["code"] for w in ctx["warnings"]}
        assert "MAX_NOT_TESTED" in codes


# ---------------------------------------------------------------------------
# Key sessions (A294 key_sessions_v1)
# ---------------------------------------------------------------------------

class TestKeySessions:
    def test_a294_source_and_current_week_only(self):
        ks = _ctx()["key_sessions"]
        assert ks["source"] == "a294"
        assert ks["week_start"] == "2026-09-28" and ks["week_end"] == "2026-10-04"
        # The limit skipped on 23/09 (previous week) is NOT carried as debt.
        assert all(s["date"] >= "2026-09-28" for r in ks["requirements"] for s in r["skipped"])

    def test_sp_requirements_and_status(self):
        ctx = _ctx()
        fm, lp, pm = _req(ctx, "finger_max"), _req(ctx, "limit_power"), _req(ctx, "pulling_max")
        assert fm["status"] == "missing"
        # mark_skipped replaced it with regeneration_easy: recovered from the log by date.
        assert fm["skipped"] == [{"date": "2026-09-30", "slot": None, "session_id": "finger_strength_home"}]
        assert lp["status"] == "missing"
        assert pm["status"] == "done" and pm["done"][0]["session_id"] == "custom_cs_pull"

    def test_technique_and_try_hard_in_every_phase(self):
        ctx = _ctx()
        assert _req(ctx, "technique")["status"] == "done"   # technique_focus_gym + outdoor day
        th = _req(ctx, "try_hard")
        assert th["status"] == "done" and th["done"][0]["evidence"].startswith("outdoor")

    def test_unknown_skip_id_reported(self):
        ctx = _ctx()
        assert ctx["key_sessions"]["unknown_skips"] == [{"date": "2026-09-29", "slot": None, "session_id": None}]
        assert any(w["code"] == "SKIP_WITHOUT_ID" for w in ctx["warnings"])

    def test_next_week_counts_planned(self):
        ctx = ac.build_athlete_context(_state(), "2026-10-06")
        assert [p["session_id"] for p in _req(ctx, "limit_power")["planned"]] == \
            ["limit_boulder_gym", "power_contact_gym"]
        assert _req(ctx, "limit_power")["status"] == "planned"
        assert _req(ctx, "limit_power")["planned"][0]["unmarked"] is True  # 05/10, never marked
        assert "(passata, non segnata)" in ac.render_text(ctx)
        fm = _req(ctx, "finger_max")
        assert [p["session_id"] for p in fm["planned"]] == ["strength_long"]
        assert ctx["key_sessions"]["summary"]["required"] == 5

    def test_next_week_planning_view(self):
        ctx = _ctx()
        nxt = ctx["key_sessions_next_week"]
        assert nxt["week_start"] == "2026-10-05" and nxt["phase_id"] == "strength_power"
        by = {r["key"]: r for r in nxt["requirements"]}
        assert [p["session_id"] for p in by["finger_max"]["planned"]] == ["strength_long"]
        assert by["limit_power"]["status"] == "planned"
        # Next-week gaps are planning info, not warnings about this week.
        assert not any(w.get("key") == "technique" for w in ctx["warnings"])
        assert "## Sessioni chiave, settimana prossima" in ac.render_text(ctx)

    def test_base_has_only_technique(self):
        # A294 review: no limit key in base → no try-hard row.
        ctx = ac.build_athlete_context(_state(), "2026-09-10")
        assert [r["key"] for r in ctx["key_sessions"]["requirements"]] == ["technique"]

    def test_deload_has_technique_without_try_hard(self):
        assert [r["key"] for r in ac.key_requirements_for("deload")] == ["technique"]

    def test_pe_limit_gap(self):
        st = _state()
        ctx = ac.build_athlete_context(st, "2026-10-21")  # PE week 1
        lp = _req(ctx, "limit_power")
        assert lp["label"].lower().startswith("limit") and "due_by" in lp

    def test_free_boulder_at_limit_counts_as_limit(self):
        st = _state(free_sessions=[{"id": "free_1", "date": "2026-10-01", "surface": "gym_boulder",
                                    "finished_at": "2026-10-01T20:00:00",
                                    "climbs": [{"grade": "7B+"}, {"grade": "7C"}]}],
                    performance={"current_level": {"boulder": {"worked": {"grade": "7C"}}}})
        lp = _req(ac.build_athlete_context(st, TODAY), "limit_power")
        assert lp["status"] == "done" and lp["done"][0]["evidence"].startswith("free session")

    def test_free_boulder_below_threshold_does_not_count(self):
        st = _state(free_sessions=[{"id": "free_1", "date": "2026-10-01", "surface": "gym_boulder",
                                    "finished_at": "2026-10-01T20:00:00",
                                    "climbs": [{"grade": "6C"}, {"grade": "7A"}]}],
                    performance={"current_level": {"boulder": {"worked": {"grade": "7C"}}}})
        assert _req(ac.build_athlete_context(st, TODAY), "limit_power")["status"] == "missing"

    def test_key_matches(self):
        assert ac.key_matches({"session_id": "power_contact_gym"}, "strength_power") == ["limit_power"]
        assert ac.key_matches({"session_id": "strength_long"}, "strength_power") == ["finger_max", "pulling_max"]
        assert ac.key_matches({"session_id": "technique_focus_gym"}, "base") == ["technique"]
        assert ac.key_matches({"session_id": "prehab_maintenance"}, "strength_power") == []


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def _day(ctx, d):
    return next(r for r in ctx["guards"]["days"] if r["date"] == d)


class TestGuards:
    def test_finger_gap_both_sides(self):
        ctx = _ctx()
        tue = _day(ctx, "2026-10-06")  # limit Mon, power_contact Wed
        assert tue["finger_max_ok"] is False and len(tue["finger_reasons"]) == 2
        mon = _day(ctx, "2026-10-05")
        assert mon["finger_max_ok"] is True and mon["finger_hard_today"] is True

    def test_outdoor_hard_yesterday_blocks_fingers(self):
        sun = _day(_ctx(), TODAY)
        assert sun["finger_max_ok"] is False
        assert any("outdoor_hard" in r for r in sun["finger_reasons"])

    def test_pre_limit_blocks_heavy_pull_and_front_lever(self):
        sun = _day(_ctx(), TODAY)
        assert sun["front_lever_ok"] is False and sun["heavy_pull_ok"] is False

    def test_hang_test_within_72h_blocks_fingers(self):
        st = _state()
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][5]["sessions"] = [
            _sess("evening", "test_max_hang_7s", tags={"hard": True, "finger": True, "test": True})]
        ctx = ac.build_athlete_context(st, "2026-10-08")
        thu = _day(ctx, "2026-10-08")
        assert any("test dita" in r for r in thu["finger_reasons"])

    def test_heavy_pulls_per_7_days(self):
        ctx = _ctx()
        sat = _day(ctx, "2026-10-10")  # limit 05 + strength_long 09 are pulling-hard
        assert sat["heavy_pull_ok"] is False
        assert any("2 sedute" in r for r in sat["pull_reasons"])

    def test_hiit_flag_and_guard(self):
        ctx = _ctx()
        hiit = [s for s in ctx["upcoming"] if s["session_id"] == "custom_cs_hiit"]
        assert hiit and all(s["hiit"] for s in hiit)
        assert _day(ctx, "2026-10-07")["hiit_ok"] is False  # same day as power_contact

    def test_guards_ignore_load_score(self):
        st = _state()
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][2]["sessions"] = [
            _sess("evening", "custom_cs_heavy", is_custom=True, estimated_load_score=999,
                  tags={"hard": False, "finger": False}, exercises=[{"exercise_id": "goblet_squat", "sets": 5}])]
        ctx = ac.build_athlete_context(st, TODAY)
        assert _day(ctx, "2026-10-07")["finger_hard_today"] is False

    def test_finger_maintenance_is_finger_but_not_hard(self):
        ctx = _ctx()
        sun = next(s for s in ctx["upcoming"] if s["session_id"] == "finger_maintenance_gym")
        assert sun["finger"] is True and sun["finger_hard"] is False

    def test_hard_cap(self):
        hc = _ctx()["guards"]["hard_cap"]
        assert hc["cap"] == 4 and hc["hard_days"] == ["2026-10-04"]


# ---------------------------------------------------------------------------
# Variety, working loads, try-hard, limits
# ---------------------------------------------------------------------------

class TestVarietyAndLoads:
    def test_variety_uses_actual_exercises_not_union(self):
        v = _ctx()["variety"]
        counts = v["exercise_counts"]
        assert "toes_to_bar" in counts and "dead_bug" not in counts
        assert v["window_start"] == "2026-09-14"  # current week + 2 before, like the resolver

    def test_variety_excludes_tests(self):
        st = _state()
        st["week_plans"]["2026-09-28"]["weeks"][0]["days"][3]["sessions"] = [
            _sess("evening", "test_max_hang_7s", "done",
                  actual_exercises=[{"exercise_id": "max_hang_7s", "completed_sets": 3}])]
        assert "max_hang_7s" not in ac.build_athlete_context(st, TODAY)["variety"]["exercise_counts"]

    def test_overused(self):
        st = _state()
        days = st["week_plans"]["2026-09-28"]["weeks"][0]["days"]
        for k in (1, 3, 5):
            days[k]["sessions"] = [_sess("lunch", f"custom_cs_core{k}", "done", is_custom=True,
                                         exercises=[{"exercise_id": "pallof_press", "sets": 3}])]
        v = ac.build_athlete_context(st, TODAY)["variety"]
        assert "core_anti_rotation" in v["overused"]

    def test_working_load_flags(self):
        st = _state()
        st["working_loads"]["entries"][0]["last_external_load_kg"] = 45.0  # == test 2RM external
        wl = {w["exercise_id"]: w for w in ac.build_athlete_context(st, TODAY)["working_loads"]}
        assert "TEST_COPY" in wl["weighted_pullup"]["flags"]
        assert "STALE" in wl["max_hang_7s"]["flags"]

    def test_try_hard_from_outdoor_notes(self):
        th = _ctx()["try_hard"]
        assert th["counts"] == {"SEND": 0, "FALL": 1, "TAKE": 1, "LET_GO": 1}
        assert th["fall_pct_of_non_send"] == pytest.approx(33.3)

    def test_try_hard_empty_is_not_a_missing_key(self):
        ctx = ac.build_athlete_context(_state(), TODAY, outdoor_rows=[])
        assert ctx["try_hard"]["logged_attempts"] == 0
        assert "non è una sessione chiave mancante" in ac.render_text(ctx)

    def test_limits_and_trips(self):
        st = _state(preferences={"finger_training_device": "hangboard", "coach_notes": "x" * 900})
        ctx = ac.build_athlete_context(st, TODAY)
        assert len(ctx["limits"]["coach_notes"]) == ac.COACH_NOTES_MAX
        assert ctx["trips"][0]["days_to_start"] == 47


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

class TestRender:
    def test_render_sections_and_labels(self):
        txt = ac.render_text(_ctx(), plan_notes="PIEDI: P2", source_line="Fonte: test")
        for needle in ("## Posizione", "## Massimali ufficiali", "## Carichi ancorati oggi",
                       "## Sessioni chiave, questa settimana",
                       "[A294", "## Retest", "## Guardie", "## Prossimi 14 giorni",
                       "## Varietà", "## Note atleta", "PIEDI: P2", "Fonte: test",
                       "mai working_loads grezzi"):
            assert needle in txt, needle

    def test_anchor_line_has_calculation_note(self):
        txt = ac.render_text(_ctx())
        line = next(l for l in txt.splitlines() if l.strip().startswith("weighted_pullup:"))
        assert "% di 128.9 kg 1RM (test 2026-09-24)" in line


# ---------------------------------------------------------------------------
# Docs: athlete plan + command
# ---------------------------------------------------------------------------

# The drills A293 listed as "proposed, not yet in the catalog". C272 added them
# all (role "library"), so the plan may no longer declare any id as new.
_C272_IDS = {
    "glued_feet_board", "position_menu_3way", "variant_ladder_board", "lead_technique_under_pump",
    "rest_and_clip_drill", "vertical_small_feet_limit", "lead_precision_feet_above_bolt",
    "three_attempt_comp", "no_take_lead_onsight", "toe_flexor_isometric", "edge_calf_raise_bigtoe",
    "technique_benchmark_test", "pre_attempt_routine",
}
_NEW_IDS: set = set()


def _ladder_tokens() -> set:
    """C272: protocol ids, ladder family and technique-ladder names of
    backend/catalog/progressions/v1/bw_ladders.json (backticked in the plan)."""
    doc = json.loads((REPO_ROOT / "backend/catalog/progressions/v1/bw_ladders.json").read_text(encoding="utf-8"))
    out = set(doc.get("protocols") or {})
    out |= {f["family"] for f in doc.get("families") or []}
    out |= {t["ladder"] for t in doc.get("technique_ladders") or []}
    return out
_NON_EXERCISE_TOKENS = {
    "anchored_load", "working_loads", "tests.*", "baselines", "notes", "load_kg", "load_mode", "anchored",
    "week_plans[<lunedì>]", "custom_sessions",
}


class TestDocs:
    def test_plan_has_notes_block(self):
        md = (REPO_ROOT / ac.ATHLETE_PLAN_PATH).read_text(encoding="utf-8")
        notes = ac.extract_plan_notes(md)
        assert notes and "PIEDI" in notes and "medio SINISTRO" in notes and "Nikita" in notes

    def test_extract_plan_notes_missing_markers(self):
        assert ac.extract_plan_notes("# nothing") is None

    def test_plan_ids_exist_in_catalog_or_are_declared_new(self):
        md = (REPO_ROOT / ac.ATHLETE_PLAN_PATH).read_text(encoding="utf-8")
        catalog = ac.load_exercise_catalog()
        tokens = set(re.findall(r"`([a-z][a-z0-9_]+)`", md))
        allowed = _NEW_IDS | _NON_EXERCISE_TOKENS | _ladder_tokens() | {"library", "ladder", "technique_tryhard", "protocols", "technique_ladders"}
        unknown = sorted(t for t in tokens if t not in catalog and t not in allowed and not t.startswith("test_"))
        assert unknown == []
        # Every NEW id is really absent today (else move it to the catalog table).
        assert not (_NEW_IDS & set(catalog))
        # C272: the drills A293 could only name are in the catalog now.
        assert _C272_IDS <= set(catalog)

    def test_plan_is_not_nikita_centric(self):
        md = (REPO_ROOT / ac.ATHLETE_PLAN_PATH).read_text(encoding="utf-8")
        assert "Non si pianifica attorno alle giornate Nikita" in md
        assert "La forza continua a progredire" in md

    def test_command_points_to_script_and_plan(self):
        cmd = (REPO_ROOT / ".claude" / "commands" / "custom-session.md").read_text(encoding="utf-8")
        assert cmd.startswith("---\ndescription:")
        assert "scripts/athlete_context.py" in cmd and "docs/training/athlete_plan.md" in cmd
        assert "--simulate" in cmd and "OK esplicito" in cmd


# ---------------------------------------------------------------------------
# Review fixes (A293 review, 2026-10-04)
# ---------------------------------------------------------------------------

def _set_day(st, week, d, sessions):
    for day in st["week_plans"][week]["weeks"][0]["days"]:
        if day["date"] == d:
            day["sessions"] = sessions
            return
    raise AssertionError(d)


class TestReviewFixes:
    def test_finger_guard_sees_replanner_spacing_of_finger_tagged_sessions(self):
        st = _state()
        _set_day(st, "2026-10-05", "2026-10-09", [])  # no strength_long
        sat = _day(ac.build_athlete_context(st, TODAY), "2026-10-10")
        # finger_maintenance_gym on Sunday is tagged finger (not hard): a max-hang
        # custom on Saturday would make the replanner downgrade it.
        assert sat["finger_max_ok"] is False
        assert any("finger_maintenance_gym" in r and "declasserebbe" in r for r in sat["finger_reasons"])

    def test_finger_spacing_follows_recovery_multiplier(self):
        st = _state()
        _set_day(st, "2026-10-05", "2026-10-09", [])
        st["week_plans"]["2026-10-05"]["profile_snapshot"]["recovery_multiplier"] = 1.5
        ctx = ac.build_athlete_context(st, TODAY)
        fri = _day(ctx, "2026-10-09")
        assert fri["finger_spacing_gap_d"] == 2
        assert fri["finger_max_ok"] is False  # power_contact Wed and finger_maintenance Sun, both 2 days away
        assert any("2026-10-11" in r for r in fri["finger_reasons"])

    def test_hard_cap_zero_is_honoured(self):
        st = _state()
        st["week_plans"]["2026-10-05"]["profile_snapshot"]["hard_cap_per_week"] = 0
        ctx = ac.build_athlete_context(st, "2026-10-06")
        assert ctx["guards"]["hard_cap"]["cap"] == 0 and ctx["guards"]["hard_cap"]["at_cap"] is True
        tue = _day(ctx, "2026-10-06")  # not a hard day yet
        assert tue["finger_max_ok"] is False and tue["heavy_pull_ok"] is False
        assert any("cap giorni hard" in r for r in tue["pull_reasons"])

    def test_deload_blocks_max_rows_and_intensity_cap_rendered(self):
        ctx = ac.build_athlete_context(_state(), "2026-11-30")
        assert ctx["position"]["phase_id"] == "deload"
        row = _day(ctx, "2026-11-30")
        assert row["finger_max_ok"] is False and row["heavy_pull_ok"] is False
        assert any("deload" in r for r in row["finger_reasons"])
        assert "Tetto di intensità della fase: max" in ac.render_text(_ctx())

    def test_heavy_pull_window_looks_forward(self):
        # 05/10 limit and 09/10 strength_long are planned heavy pulls: a heavy
        # pull on 03/10 would make 3 in the window 03..09.
        ctx = ac.build_athlete_context(_state(), "2026-10-02")
        sat = _day(ctx, "2026-10-03")
        assert sat["heavy_pull_ok"] is False and sat["front_lever_ok"] is False
        assert "2026-10-09" in sat["pull_reasons"][0]
        assert _day(ctx, "2026-10-02")["heavy_pull_ok"] is True  # window 26/09..02/10 has none

    def test_planned_technique_custom_counts(self):
        st = _state()
        _set_day(st, "2026-10-05", "2026-10-10", [_sess(
            "evening", "custom_cs_tech", is_custom=True, name="Tecnica",
            tags={"hard": False, "finger": False},
            exercises=[{"exercise_id": "silent_feet_drill", "sets": 1},
                       {"exercise_id": "no_readjust_drill", "sets": 2},
                       {"exercise_id": "hover_hands", "sets": 2}])])
        ctx = ac.build_athlete_context(st, "2026-10-06")
        tech = _req(ctx, "technique")
        assert tech["status"] == "planned" and tech["planned"][0]["session_id"] == "custom_cs_tech"
        assert not any(w.get("key") == "technique" for w in ctx["warnings"])
        sess = st["week_plans"]["2026-10-05"]["weeks"][0]["days"][5]["sessions"][0]
        assert "technique" in ac.key_matches(sess, "strength_power")

    def test_warmup_drills_are_not_the_technique_key(self):
        cat = ac.load_exercise_catalog()
        warm = {"session_id": "custom_cs_x", "status": "done",
                "exercises": [{"exercise_id": "silent_feet_drill"}, {"exercise_id": "foothold_stare"},
                              {"exercise_id": "weighted_pullup"}]}
        assert ac._technique_hit(warm, cat) is False
        real = dict(warm, exercises=warm["exercises"] + [{"exercise_id": "no_readjust_drill"},
                                                         {"exercise_id": "twist_lock_drill"}])
        assert ac._technique_hit(real, cat) is True

    def test_pe_limit_not_due_inside_gap(self):
        st = _state()
        st["week_plans"]["2026-10-12"] = _week("2026-10-12", {
            "2026-10-17": [_sess("evening", "power_contact_gym", "done", tags={"hard": True, "finger": True})]})
        ctx = ac.build_athlete_context(st, "2026-10-20")  # PE week 1
        lp, th = _req(ctx, "limit_power"), _req(ctx, "try_hard")
        assert lp["last_done"] == "2026-10-17" and lp["due_by"] == "2026-10-29"
        assert lp["status"] == "not_due" and th["status"] == "not_due"
        assert not any(w.get("key") in ("limit_power", "try_hard") for w in ctx["warnings"])
        assert "NOT_DUE" in ac.render_text(ctx)

    def test_pe_limit_due_this_week_is_missing(self):
        st = _state()
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][0]["sessions"][0]["status"] = "done"
        st["week_plans"]["2026-10-05"]["weeks"][0]["days"][2]["sessions"][1]["status"] = "skipped"
        ctx = ac.build_athlete_context(st, "2026-10-20")  # last limit 05/10 → due 17/10
        assert _req(ctx, "limit_power")["status"] == "missing"

    def test_hiit_work_on_guard_day_warned(self):
        ctx = _ctx()
        w = [x for x in ctx["warnings"] if x["code"] == "HIIT_ON_GUARD_DAY"]
        assert [x["date"] for x in w] == ["2026-10-07"]

    def test_work_recurrences_flagged_at_phase_change(self):
        st = _state()
        st["week_plans"]["2026-10-19"] = _week("2026-10-19", {
            "2026-10-21": [_sess("lunch", "custom_cs_hiit", "planned", is_custom=True,
                                 name="Work — HIIT 4x4 (VO2max)", tags={"hard": False, "finger": False})]})
        ctx = ac.build_athlete_context(st, "2026-10-12")  # SP ends 19/10
        w = [x for x in ctx["warnings"] if x["code"] == "WORK_RECURRENCE_PHASE_CHANGE"]
        assert len(w) == 1 and "power_endurance" in w[0]["message"] and "2026-10-21" in w[0]["message"]
        # Far from a phase change: no flag.
        assert not any(x["code"] == "WORK_RECURRENCE_PHASE_CHANGE"
                       for x in ac.build_athlete_context(st, "2026-09-28")["warnings"])

    def test_anchor_section_says_it_is_scheme_specific(self):
        assert "carico al play" in ac.render_text(_ctx())

    def test_plan_pain_rule_complete(self):
        text = (REPO_ROOT / ac.ATHLETE_PLAN_PATH).read_text(encoding="utf-8")
        assert "hang ≤ 85%" in text and "0.80" in text

    def test_command_points_to_play_line_for_other_schemes(self):
        text = (REPO_ROOT / ".claude" / "commands" / "custom-session.md").read_text(encoding="utf-8")
        assert "carico al play" in text and "NOT_DUE" in text
