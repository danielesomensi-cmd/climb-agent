"""A290 (R2) — phase-anchor rotation in the resolver.

Tested athletes get a fixed progressive exercise per phase (phase_anchor), a
stable A/B alternation on accessories and core, a weekly heavy pulling slot and
spacing guards on real fatigue. Untested athletes keep the pre-A290 resolver
bit for bit (golden ``fixtures/a290_untested_golden.json``).
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.engine import phase_anchor as pa
from backend.engine.macro_position import position_on
from backend.engine.resolve_session import load_recent_exercise_ids, pick_best_exercise_p0, resolve_session
from backend.tests.a290_untested_cases import REPO_ROOT, _base_state, compute

FIXTURES = Path(__file__).parent / "fixtures"
CATALOG = Path(REPO_ROOT) / "backend" / "catalog"
LOADED = {"total_load", "external_load"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _tested(*, finger_total=116.0, finger_bw=76.0, pull_total=123.0, pull_bw=78.0, test_date="2026-09-24",
            finger=True, pulling=True, experience=16):
    st = _base_state()
    st["bodyweight_kg"] = 78.0
    st["body"] = {"weight_kg": 78.0, "age": 40}
    st["assessment"] = {"experience": {"climbing_years": experience}}
    st["tests"] = {"max_strength": [], "pulling_strength": []}
    if finger:
        st["tests"]["max_strength"].append({"test_id": "max_hang_7s_total_load", "date": test_date,
                                            "total_load_kg": finger_total, "bodyweight_kg": finger_bw})
    if pulling:
        st["tests"]["pulling_strength"].append({"test_id": "weighted_pullup_2rm", "date": test_date,
                                                "total_load_2rm_kg": pull_total,
                                                "estimated_1rm_kg": round(pull_total * 1.048, 1),
                                                "bodyweight_kg": pull_bw})
    return st


def _plan(days):
    """days: [(date, session_id, location, gym_id[, status])] → one week plan."""
    out = []
    for row in days:
        d, sid, loc, gid = row[:4]
        status = row[4] if len(row) > 4 else "planned"
        out.append({"date": d, "sessions": [{"session_id": sid, "location": loc, "gym_id": gid, "status": status}]})
    monday = min(r[0] for r in days)
    return {"start_date": monday, "weeks": [{"days": out}]}


def _resolve(state, sid, d, loc="home", gid=None, *, phase=None, week_plan=None, extra_recent=None):
    st = deepcopy(state)
    st["context"] = {"location": loc, "gym_id": gid, "target_date": d, "date": d}
    if phase is None:
        phase = position_on(st["macrocycle"], d)["phase_id"]
    r = resolve_session(
        REPO_ROOT, f"backend/catalog/sessions/v1/{sid}.json", "backend/catalog/templates",
        "backend/catalog/exercises/v1/exercises.json", "", user_state_override=st, write_output=False,
        phase=phase, week_plan=week_plan, extra_recent_ex_ids=extra_recent,
    )
    r.pop("generated_at", None)
    return r


def _inst(r, block_uid):
    for i in r["resolved_session"]["exercise_instances"]:
        if i["block_uid"] == block_uid:
            return i
    raise AssertionError(f"{block_uid} not in {[i['block_uid'] for i in r['resolved_session']['exercise_instances']]}")


def _pick(r, block_uid):
    return _inst(r, block_uid)["exercise_id"]


def _rot(r, block_uid):
    for b in r["resolved_session"]["blocks"]:
        if b["block_uid"] == block_uid:
            return (b.get("p0_trace") or {}).get("rotation") or {}
    raise AssertionError(block_uid)


def _catalog_by_id():
    data = json.loads((CATALOG / "exercises" / "v1" / "exercises.json").read_text())
    data = data if isinstance(data, list) else data["exercises"]
    return {e["id"]: e for e in data}


# ---------------------------------------------------------------------------
# (1) untested athletes: bit for bit
# ---------------------------------------------------------------------------

def test_untested_resolver_output_is_bit_for_bit_pre_a290():
    golden = json.loads((FIXTURES / "a290_untested_golden.json").read_text())
    for pass_week_plan in (False, True):
        now = compute(pass_week_plan=pass_week_plan)
        assert set(now) == set(golden)
        diff = [k for k in golden if golden[k] != now[k]]
        assert diff == [], f"untested output changed (week_plan={pass_week_plan}): {diff}"


def test_no_rotation_context_without_a_tested_baseline():
    st = _base_state()
    d = date(2026, 10, 9)
    assert pa.build_rotation_context(st, d, "strength_power") is None
    # Onboarding self-report persisted as source='test' is not a test log.
    st["baselines"] = {"hangboard": [{"max_total_load_kg": 105.0, "source": "test", "updated_at": "2026-09-07",
                                      "hang_seconds": 7, "edge_mm": 20}],
                       "pulling": {"weighted_pullup_2rm_total_kg": 110.0, "source": "test",
                                   "updated_at": "2026-09-07"}}
    assert pa.build_rotation_context(st, d, "strength_power") is None
    assert pa.plan_block(None, {"rotation": "phase_anchor"}, session_id="x", block_id="y") is None


def test_test_after_target_or_older_than_90_days_is_not_tested():
    st = _tested()
    # 22/09: the 24/09 tests do not exist yet.
    assert pa.build_rotation_context(st, date(2026, 9, 22), None) is None
    assert pa.build_rotation_context(st, date(2026, 9, 25), None) is not None
    # 90 days after the test the gate closes again.
    assert pa.build_rotation_context(st, date(2026, 9, 24) + timedelta(days=90), None) is None


# ---------------------------------------------------------------------------
# (2) tested level → which anchor list
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ratio,expected_list", [(1.30, "untested"), (1.40, "tested")])
def test_finger_ratio_threshold_picks_the_list(ratio, expected_list):
    st = _tested(finger_total=round(ratio * 70, 1), finger_bw=70.0)
    r = _resolve(st, "strength_long", "2026-10-09", week_plan=_plan([("2026-10-09", "strength_long", "home", None)]))
    rot = _rot(r, "finger_max_strength.main")
    assert rot["rotation"] == "phase_anchor"
    assert rot["anchor_list"] == expected_list
    expected = "max_hang_7s" if expected_list == "tested" else "horst_7_53"
    assert _pick(r, "finger_max_strength.main") == expected


@pytest.mark.parametrize("ratio,expected", [(1.40, "pullup"), (1.50, "weighted_pullup")])
def test_pulling_ratio_threshold_picks_the_heavy_list(ratio, expected):
    st = _tested(pull_total=round(ratio * 78, 1), pull_bw=78.0)
    r = _resolve(st, "strength_long", "2026-10-09", week_plan=_plan([("2026-10-09", "strength_long", "home", None)]))
    assert _pick(r, "inline.pulling_compound") == expected


def test_tested_ratio_reads_tests_not_baselines_and_uses_test_bodyweight():
    st = _tested()
    assert pa.tested_ratio(st, pa.AXIS_FINGER, date(2026, 10, 9)) == round(116 / 76, 3)
    assert pa.tested_ratio(st, pa.AXIS_PULLING, date(2026, 10, 9)) == round(123 / 78, 3)
    st2 = _tested(finger=False)
    assert pa.tested_ratio(st2, pa.AXIS_FINGER, date(2026, 10, 9)) is None


def test_min_edge_hang_never_the_sp_main_for_a_finger_tested_athlete():
    st = _tested()
    for d in ("2026-10-09", "2026-10-13"):
        sid = "strength_long" if d == "2026-10-09" else "finger_strength_home"
        r = _resolve(st, sid, d, week_plan=_plan([(d, sid, "home", None)]))
        assert _pick(r, "finger_max_strength.main") == "max_hang_7s"


# ---------------------------------------------------------------------------
# (3) phase window: pause-aware, from macro_position
# ---------------------------------------------------------------------------

def test_phase_window_follows_the_a223_pause():
    macro = deepcopy(_base_state()["macrocycle"])
    macro["pause"] = {"offset_days": 14}
    start = date(2026, 9, 7)
    for i in range(20):
        d = start + timedelta(days=7 * i + 3)
        pos = position_on(macro, d)
        phase_id, phase_start = pa.phase_window(macro, None, d)
        assert phase_id == pos["phase_id"]
        assert phase_start.isoformat() == pos["phase_start"]
        # Explicit phase kwarg → the same window.
        assert pa.phase_window(macro, pos["phase_id"], d) == (phase_id, phase_start)


def test_ab_parity_follows_the_pause_shifted_week_index():
    st = _tested()
    st["macrocycle"]["pause"] = {"offset_days": 14}
    ctx = pa.build_rotation_context(st, date(2026, 10, 9), None)
    # SP starts 21/09 + 14 = 05/10 → 09/10 is week 0 of SP.
    assert ctx.phase_id == "strength_power"
    assert ctx.phase_start == date(2026, 10, 5)
    assert ctx.week_idx == 0


# ---------------------------------------------------------------------------
# (4) D35 gate and active filter
# ---------------------------------------------------------------------------

def test_d35_gate_keeps_max_hangs_away_from_beginners_but_not_from_their_test():
    st = _tested(experience=1)
    r = _resolve(st, "finger_strength_home", "2026-10-13",
                 week_plan=_plan([("2026-10-13", "finger_strength_home", "home", None)]))
    advanced = {"max_hang_5s", "max_hang_7s", "max_hang_10s", "max_hang_ladder", "min_edge_hang",
                "one_arm_hang_assisted"}
    assert _pick(r, "finger_max_strength.main") not in advanced
    t = _resolve(st, "test_max_hang_7s", "2026-10-13")
    assert "max_hang_7s" in [i["exercise_id"] for i in t["resolved_session"]["exercise_instances"]]


def test_active_false_is_never_picked_by_p0_with_active_only():
    cat = _catalog_by_id()
    pool = [deepcopy(cat["max_hang_10s"])]
    assert pool[0].get("active") is False
    kw = dict(exercises=pool, location="home", available_equipment=["hangboard"], role_req=["main"],
              domain_req=["finger_strength"])
    sel_legacy, _ = pick_best_exercise_p0(**kw)
    sel_new, _ = pick_best_exercise_p0(**kw, active_only=True)
    assert sel_legacy is not None and sel_legacy["id"] == "max_hang_10s"
    assert sel_new is None


def test_late_dedup_keeps_domain_and_pattern():
    a = {"id": "core_a", "role": ["accessory"], "domain": ["core"], "location_allowed": ["home"],
         "intensity_level": "medium"}
    b = {"id": "glute_b", "role": ["accessory"], "domain": ["legs"], "location_allowed": ["home"],
         "intensity_level": "medium"}
    kw = dict(exercises=[a, b], location="home", available_equipment=[], role_req=["accessory"],
              domain_req=["core"], exclude_ids={"core_a"})
    legacy, _ = pick_best_exercise_p0(**kw)
    late, _ = pick_best_exercise_p0(**kw, dedup_after_filters=True)
    assert legacy["id"] == "glute_b"   # the history pushed the pick out of the domain
    assert late["id"] == "core_a"      # A290: dedup never empties the target pool


# ---------------------------------------------------------------------------
# (5) stability of the anchor
# ---------------------------------------------------------------------------

def test_anchor_is_stable_over_the_phase_whatever_the_history():
    st = _tested()
    picks = []
    for d, sid in (("2026-09-28", "strength_long"), ("2026-10-09", "strength_long"),
                   ("2026-10-13", "finger_strength_home"), ("2026-10-16", "strength_long")):
        r = _resolve(st, sid, d, week_plan=_plan([(d, sid, "home", None)]),
                     extra_recent=["max_hang_7s"] * 10 + ["horst_7_53"] * 10)
        picks.append(_pick(r, "finger_max_strength.main"))
    assert set(picks) == {"max_hang_7s"}


def test_limit_and_campus_are_fixed_and_distinct():
    st = _tested()
    a = _resolve(st, "limit_boulder_gym", "2026-10-05", "gym", "g_board",
                 week_plan=_plan([("2026-10-05", "limit_boulder_gym", "gym", "g_board")]))
    b = _resolve(st, "power_contact_gym", "2026-10-07", "gym", "g_board",
                 week_plan=_plan([("2026-10-07", "power_contact_gym", "gym", "g_board")]))
    assert _pick(a, "inline.limit_projecting") == "limit_bouldering"
    assert _pick(b, "inline.limit_bouldering") == "system_board_limit"
    assert _pick(b, "inline.campus_power") == "campus_max_ladders"
    # Secondary pull after limit: never externally loaded.
    cat = _catalog_by_id()
    assert cat[_pick(a, "inline.supplementary_pulling")].get("load_model") not in LOADED


def test_pe_finger_session_is_max_hang_maintenance_at_three_sets():
    st = _tested()
    r = _resolve(st, "finger_strength_home", "2026-10-20",
                 week_plan=_plan([("2026-10-20", "finger_strength_home", "home", None)]))
    inst = _inst(r, "finger_max_strength.main")
    assert inst["exercise_id"] == "max_hang_7s"
    assert inst["prescription"]["sets"] == 3


def test_pe_blocks_fixed_for_the_phase():
    st = _tested()
    picks = set()
    for d in ("2026-10-22", "2026-10-29", "2026-11-05"):
        r = _resolve(st, "power_endurance_gym", d, "gym", "g_board",
                     week_plan=_plan([(d, "power_endurance_gym", "gym", "g_board")]),
                     extra_recent=["four_by_four_bouldering", "linked_boulders"])
        picks.add((_pick(r, "inline.pe_boulder"), _pick(r, "inline.finger_endurance")))
    assert len(picks) == 1


# ---------------------------------------------------------------------------
# (6) heavy slot
# ---------------------------------------------------------------------------

def test_sp_heavy_slot_is_the_first_two_occurrences_of_the_week():
    st = _tested()
    wp = _plan([("2026-10-05", "strength_long", "home", None),
                ("2026-10-07", "finger_strength_home", "home", None),
                ("2026-10-09", "pulling_strength_gym", "gym", "g_board")])
    mon = _resolve(st, "strength_long", "2026-10-05", week_plan=wp)
    wed = _resolve(st, "finger_strength_home", "2026-10-07", week_plan=wp)
    fri = _resolve(st, "pulling_strength_gym", "2026-10-09", "gym", "g_board", week_plan=wp)
    assert _pick(mon, "inline.pulling_compound") == "weighted_pullup"
    assert _pick(wed, "inline.pulling_maintenance") == "weighted_pullup"
    rot = _rot(fri, "pulling_strength_compound.weighted_pullup_main")
    assert rot["spacing_downgrade"] == "not_heavy_occurrence"
    cat = _catalog_by_id()
    for uid in ("pulling_strength_compound.weighted_pullup_main", "pulling_strength_compound.lock_off_hold",
                "pulling_strength_compound.typewriter_unilateral"):
        assert cat[_pick(fri, uid)].get("load_model") not in LOADED
    picks = [_pick(fri, u) for u in ("pulling_strength_compound.weighted_pullup_main",
                                     "pulling_strength_compound.lock_off_hold",
                                     "pulling_strength_compound.typewriter_unilateral")]
    assert len(set(picks)) == 3


def test_pe_heavy_slot_is_once_a_week():
    st = _tested()
    wp = _plan([("2026-10-19", "strength_long", "home", None),
                ("2026-10-21", "finger_strength_home", "home", None)])
    mon = _resolve(st, "strength_long", "2026-10-19", week_plan=wp)
    wed = _resolve(st, "finger_strength_home", "2026-10-21", week_plan=wp)
    assert _pick(mon, "inline.pulling_compound") == "weighted_pullup"
    assert _pick(wed, "inline.pulling_maintenance") != "weighted_pullup"
    assert _rot(wed, "inline.pulling_maintenance")["spacing_downgrade"] == "not_heavy_occurrence"


def test_heavy_slot_rank_ignores_status():
    st = _tested()
    wp = _plan([("2026-10-19", "strength_long", "home", None, "skipped"),
                ("2026-10-21", "finger_strength_home", "home", None)])
    wed = _resolve(st, "finger_strength_home", "2026-10-21", week_plan=wp)
    assert _rot(wed, "inline.pulling_maintenance")["spacing_downgrade"] == "not_heavy_occurrence"


# ---------------------------------------------------------------------------
# (7) spacing on real fatigue
# ---------------------------------------------------------------------------

def _with_done(state, d, session):
    st = deepcopy(state)
    dd = date.fromisoformat(d)
    monday = (dd - timedelta(days=dd.weekday())).isoformat()
    plan = st["week_plans"].setdefault(monday, {"start_date": monday, "weeks": [{"days": []}]})
    plan["weeks"][0]["days"].append({"date": d, "sessions": [session]})
    return st


def test_weighted_pull_done_yesterday_downgrades_the_heavy_slot():
    base = _tested()
    custom = {"session_id": "custom_cs_x", "is_custom": True, "status": "done",
              "actual_exercises": [{"exercise_id": "weighted_pullup", "completed": True, "completed_sets": 3}]}
    st = _with_done(base, "2026-10-08", custom)
    wp = _plan([("2026-10-09", "strength_long", "home", None)])
    r = _resolve(st, "strength_long", "2026-10-09", week_plan=wp)
    assert _rot(r, "inline.pulling_compound")["spacing_downgrade"] == "heavy_pull_48h"
    assert _catalog_by_id()[_pick(r, "inline.pulling_compound")].get("load_model") not in LOADED

    skipped = dict(custom, status="skipped")
    st2 = _with_done(base, "2026-10-08", skipped)
    r2 = _resolve(st2, "strength_long", "2026-10-09", week_plan=wp)
    assert _pick(r2, "inline.pulling_compound") == "weighted_pullup"


def test_two_heavy_pull_days_in_seven_cap_the_slot():
    base = _tested()
    s = {"session_id": "custom_cs_x", "is_custom": True, "status": "done",
         "actual_exercises": [{"exercise_id": "weighted_chinup", "completed": True, "completed_sets": 3}]}
    st = _with_done(_with_done(base, "2026-10-04", s), "2026-10-06", s)
    r = _resolve(st, "strength_long", "2026-10-09", week_plan=_plan([("2026-10-09", "strength_long", "home", None)]))
    assert _rot(r, "inline.pulling_compound")["spacing_downgrade"] == "heavy_pull_7d_cap"


def test_max_hang_test_two_days_ago_steps_down_to_a_sub_maximal_hang():
    base = _tested()
    test_sess = {"session_id": "test_max_hang_7s", "status": "done", "tags": {"test": True},
                 "resolved": {"resolved_session": {"exercise_instances": [{"exercise_id": "max_hang_7s"}]}}}
    st = _with_done(base, "2026-10-11", test_sess)
    for loc, gid in (("home", None), ("gym", "g_board")):
        r = _resolve(st, "finger_strength_home", "2026-10-13", loc, gid,
                     week_plan=_plan([("2026-10-13", "finger_strength_home", loc, gid)]))
        rot = _rot(r, "finger_max_strength.main")
        assert rot["spacing_downgrade"] == "max_hang_72h"
        assert rot["anchor_list"] == "spacing"
        inst = _inst(r, "finger_max_strength.main")
        ex = _catalog_by_id()[inst["exercise_id"]]
        # A real step-down: never a finger_max-family / max-intensity hang
        # (horst_7_53, min_edge_hang, max_hang_ladder were the old picks).
        assert inst["exercise_id"] not in pa.FINGER_MAX_LOAD_IDS
        assert not pa.is_max_finger_load(ex)
        # ...and the block's max-intensity dose does not bleed onto it.
        assert "intensity_pct_of_total_load_range" not in inst["prescription"]
        assert inst["prescription"].get("sets_range") != [5, 8]


def test_strength_long_yesterday_steps_down_the_next_finger_session():
    base = _tested()
    sl = {"session_id": "strength_long", "status": "done", "resolved": {"resolved_session": {
        "exercise_instances": [{"exercise_id": "max_hang_7s"}, {"exercise_id": "weighted_pullup"}]}}}
    for gap in (1, 2):
        d = (date(2026, 10, 5) + timedelta(days=gap)).isoformat()
        st = _with_done(base, "2026-10-05", sl)
        r = _resolve(st, "finger_strength_home", d, week_plan=_plan([(d, "finger_strength_home", "home", None)]))
        assert _rot(r, "finger_max_strength.main")["anchor_list"] == "spacing"
        assert _pick(r, "finger_max_strength.main") not in pa.FINGER_MAX_LOAD_IDS
    # Three days later the anchor is back.
    st = _with_done(base, "2026-10-05", sl)
    r = _resolve(st, "finger_strength_home", "2026-10-08",
                 week_plan=_plan([("2026-10-08", "finger_strength_home", "home", None)]))
    assert _pick(r, "finger_max_strength.main") == "max_hang_7s"


def test_step_down_with_only_max_hangs_skips_the_block():
    pool = [{"id": "horst_7_53", "intensity_level": "high", "stress_tags": {"fingers": "high"}},
            {"id": "min_edge_hang", "intensity_level": "max"},
            {"id": "repeater_hang_7_3", "stress_tags": {"fingers": "high"}}]
    plan = {"mode": pa.ROTATION_PHASE_ANCHOR, "order": [], "exclude": [], "soft_exclude": [],
            "hard_exclude_max_finger": True, "seed": "x"}
    sel, info = pa.select_from_pool(pool, plan, get_id=lambda e: e["id"])
    assert sel is None and info["hard_excluded_max_finger"] == 3


def test_a_downgraded_heavy_occurrence_does_not_use_a_slot():
    base = _tested()
    sl = {"session_id": "strength_long", "status": "done", "resolved": {"resolved_session": {
        "exercise_instances": [{"exercise_id": "weighted_pullup"}]}}}
    st = _with_done(base, "2026-10-05", sl)
    wp = _plan([("2026-10-05", "strength_long", "home", None, "done"),
                ("2026-10-06", "finger_strength_home", "home", None),
                ("2026-10-08", "pulling_strength_gym", "gym", "g_board")])
    tue = _resolve(st, "finger_strength_home", "2026-10-06", week_plan=wp)
    assert _rot(tue, "inline.pulling_maintenance")["spacing_downgrade"] == "heavy_pull_48h"
    thu = _resolve(st, "pulling_strength_gym", "2026-10-08", "gym", "g_board", week_plan=wp)
    rot = _rot(thu, "pulling_strength_compound.weighted_pullup_main")
    assert rot["heavy_rank"] == 1 and "spacing_downgrade" not in rot
    assert _pick(thu, "pulling_strength_compound.weighted_pullup_main") == "weighted_pullup"

    # Same when the first occurrence was turned light by the 24 h pre-limit rule.
    wp2 = _plan([("2026-10-05", "strength_long", "home", None),
                 ("2026-10-06", "limit_boulder_gym", "gym", "g_board"),
                 ("2026-10-08", "finger_strength_home", "home", None),
                 ("2026-10-10", "pulling_strength_gym", "gym", "g_board")])
    mon = _resolve(base, "strength_long", "2026-10-05", week_plan=wp2)
    assert _rot(mon, "inline.pulling_compound")["spacing_downgrade"] == "pre_limit_24h"
    wed = _resolve(base, "finger_strength_home", "2026-10-08", week_plan=wp2)
    sat = _resolve(base, "pulling_strength_gym", "2026-10-10", "gym", "g_board", week_plan=wp2)
    assert _pick(wed, "inline.pulling_maintenance") == "weighted_pullup"
    assert _pick(sat, "pulling_strength_compound.weighted_pullup_main") == "weighted_pullup"


def test_pre_limit_rule_on_sunday_reads_the_weekday_proxy_when_next_week_is_not_planned():
    st = _tested()
    wp = _plan([("2026-10-05", "limit_boulder_gym", "gym", "g_board"),
                ("2026-10-11", "finger_strength_home", "home", None)])
    ctx = pa.build_rotation_context(st, date(2026, 10, 11), "strength_power", week_plan=wp,
                                    heavy_slot_sessions=frozenset({"finger_strength_home"}))
    assert ctx.tomorrow_source == "weekday_proxy"
    assert "limit_boulder_gym" in ctx.tomorrow_session_ids
    assert pa.heavy_downgrade_reason(ctx, "finger_strength_home") == "pre_limit_24h"
    # A covered tomorrow is read from the plan, never from the proxy.
    ctx2 = pa.build_rotation_context(st, date(2026, 10, 9), "strength_power", week_plan=wp)
    assert ctx2.tomorrow_source == "plan" and not ctx2.tomorrow_session_ids


def test_no_heavy_pull_and_no_front_lever_the_day_before_limit():
    st = _tested()
    wp = _plan([("2026-10-08", "strength_long", "home", None),
                ("2026-10-09", "limit_boulder_gym", "gym", "g_board")])
    r = _resolve(st, "strength_long", "2026-10-08", week_plan=wp)
    assert _rot(r, "inline.pulling_compound")["spacing_downgrade"] == "pre_limit_24h"
    assert _pick(r, "core_standard.core_main") not in pa.FRONT_LEVER_IDS
    ctx = pa.build_rotation_context(st, date(2026, 10, 8), "strength_power", week_plan=wp)
    plan = pa.plan_block(ctx, {"rotation": "ab"}, session_id="strength_long", block_id="core_main")
    assert set(pa.FRONT_LEVER_IDS) <= set(plan["soft_exclude"])


# ---------------------------------------------------------------------------
# (8) A/B: structural, status agnostic
# ---------------------------------------------------------------------------

def test_ab_alternates_within_the_week_and_flips_next_week():
    st = _tested()
    wk1 = _plan([("2026-10-05", "strength_long", "home", None), ("2026-10-08", "strength_long", "home", None)])
    a = _resolve(st, "strength_long", "2026-10-05", week_plan=wk1)
    b = _resolve(st, "strength_long", "2026-10-08", week_plan=wk1)
    ra, rb = _rot(a, "core_standard.core_main"), _rot(b, "core_standard.core_main")
    assert (ra["ab_slot"], rb["ab_slot"]) == ("A", "B")
    assert _pick(a, "core_standard.core_main") != _pick(b, "core_standard.core_main")

    # Marking Monday done does not change Thursday.
    wk1_done = deepcopy(wk1)
    wk1_done["weeks"][0]["days"][0]["sessions"][0]["status"] = "done"
    b2 = _resolve(st, "strength_long", "2026-10-08", week_plan=wk1_done)
    assert _pick(b2, "core_standard.core_main") == _pick(b, "core_standard.core_main")

    wk2 = _plan([("2026-10-12", "strength_long", "home", None), ("2026-10-15", "strength_long", "home", None)])
    c = _resolve(st, "strength_long", "2026-10-12", week_plan=wk2)
    assert _rot(c, "core_standard.core_main")["ab_slot"] == "B"
    assert _pick(c, "core_standard.core_main") == _pick(b, "core_standard.core_main")


def test_core_floor_only_above_a_tested_threshold():
    low = _tested(finger=False, pull_total=86.0, pull_bw=78.0)   # ratio 1.10: tested, not advanced
    ctx = pa.build_rotation_context(low, date(2026, 10, 5), "strength_power")
    assert ctx is not None and not ctx.advanced
    cfg = {"rotation": "ab", "rotation_exclude": ["plank", "dead_bug", "plank_shoulder_tap"]}
    low_sx = pa.plan_block(ctx, cfg, session_id="strength_long", block_id="core_main")["soft_exclude"]
    assert not {"plank", "dead_bug", "plank_shoulder_tap"} & set(low_sx)
    hi = pa.build_rotation_context(_tested(), date(2026, 10, 5), "strength_power")
    assert "plank" in pa.plan_block(hi, cfg, session_id="strength_long", block_id="core_main")["soft_exclude"]


def test_campus_follows_the_finger_level_and_is_anchored_in_sp_only():
    # Pulling tested at 1.15 BW, no finger test: untested finger list.
    st = _tested(finger=False, pull_total=90.0, pull_bw=78.0, experience=4)
    picks = set()
    for d in ("2026-10-07", "2026-10-14"):
        r = _resolve(st, "power_contact_gym", d, "gym", "g_board",
                     week_plan=_plan([(d, "power_contact_gym", "gym", "g_board")]))
        rot = _rot(r, "inline.campus_power")
        assert rot["anchor_axis"] == "finger" and rot["anchor_list"] == "untested"
        picks.add(_pick(r, "inline.campus_power"))
        assert _rot(r, "inline.limit_bouldering")["anchor_list"] == "untested"
    assert len(picks) == 1 and picks.isdisjoint({"campus_max_ladders", "campus_double_dyno", "campus_bumps"})
    # Outside SP the campus block is free (no context plan).
    ctx = pa.build_rotation_context(_tested(), date(2026, 10, 21), "power_endurance")
    cfg = json.loads((CATALOG / "sessions" / "v1" / "power_contact_gym.json").read_text())
    campus = next(m for m in cfg["modules"] if m.get("block_id") == "campus_power")
    assert pa.plan_block(ctx, campus, session_id="power_contact_gym", block_id="campus_power") is None
    assert pa.plan_block(ctx, dict(campus, rotation="phase_anchor"), session_id="x", block_id="y") is None


def test_core_floor_for_advanced_tested_athletes():
    st = _tested()
    for d in ("2026-10-05", "2026-10-08", "2026-10-12"):
        r = _resolve(st, "strength_long", d, week_plan=_plan([(d, "strength_long", "home", None)]))
        assert _pick(r, "core_standard.core_main") not in {"plank", "dead_bug", "plank_shoulder_tap"}


# ---------------------------------------------------------------------------
# (9) recency kwargs
# ---------------------------------------------------------------------------

def test_recency_opt_in_kwargs():
    st = _base_state()
    legacy = load_recent_exercise_ids(None, user_state=st, reference_date="2026-10-04")
    assert "max_hang_7s" in legacy and "weighted_pullup" not in legacy
    new = load_recent_exercise_ids(None, user_state=st, reference_date="2026-10-04",
                                   exclude_test_instances=True, include_custom=True, cap=None)
    assert "max_hang_7s" not in new            # test main instance: not variety
    assert "general_warmup_jog" in new          # test warm-up: still variety
    assert {"weighted_pullup", "core_hollow_hold"} <= set(new)  # done custom counted

    big = deepcopy(st)
    insts = [{"exercise_id": f"ex_{i:03d}"} for i in range(150)]
    big["week_plans"]["2026-09-28"]["weeks"][0]["days"][0]["sessions"][0]["resolved"]["resolved_session"][
        "exercise_instances"] = insts
    assert len(load_recent_exercise_ids(None, user_state=big, reference_date="2026-10-04")) == 100
    assert "ex_000" in load_recent_exercise_ids(None, user_state=big, reference_date="2026-10-04", cap=None)


# ---------------------------------------------------------------------------
# (10) catalog contract
# ---------------------------------------------------------------------------

def _all_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_keys(v)


def _rotation_blocks():
    for folder, key in (("templates", "blocks"), ("sessions", "modules")):
        for p in sorted((CATALOG / folder / "v1").glob("*.json")):
            data = json.loads(p.read_text())
            for b in data.get(key) or []:
                if isinstance(b, dict):
                    yield p.name, b


def test_rotation_keys_live_at_block_level_and_reference_active_exercises():
    cat = _catalog_by_id()
    seen = 0
    for name, b in _rotation_blocks():
        nested_keys = set(_all_keys(b.get("selection") or {}))
        for k in pa.ROTATION_KEYS:
            assert k not in nested_keys, f"{name}:{b.get('block_id')} has {k} inside selection"
        if "rotation" in b:
            seen += 1
            assert b["rotation"] in pa.ROTATION_CLASSES
        ids = []
        ap = b.get("anchor_priority")
        if isinstance(ap, list):
            ids += ap
        elif isinstance(ap, dict):
            for v in ap.values():
                ids += v
        for ph in (b.get("anchor_priority_by_phase") or {}).values():
            for k, v in ph.items():
                if k in ("tested", "untested"):
                    ids += v
                if k == "anchor_exclude":
                    for vv in v.values():
                        ids += vv
        step = b.get("spacing_step_down")
        if step:
            ids += step.get("priority") or []
            for eid in step.get("priority") or []:
                assert not pa.is_max_finger_load(cat[eid]), f"{name}: step-down {eid} is a max hang"
        ids += b.get("ab_pool") or []
        for v in (b.get("anchor_exclude") or {}).values():
            ids += v
        ids += b.get("rotation_exclude") or []
        for eid in ids:
            assert eid in cat, f"{name}: unknown exercise {eid}"
            assert cat[eid].get("active") is not False, f"{name}: inactive exercise {eid}"
    assert seen >= 15


def test_heavy_slot_sessions_are_the_three_weighted_pull_sessions():
    ids = pa.heavy_slot_session_ids(str(CATALOG / "sessions" / "v1"), str(CATALOG / "templates"))
    assert ids == frozenset({"strength_long", "finger_strength_home", "pulling_strength_gym"})


# ---------------------------------------------------------------------------
# (11) immutability + determinism
# ---------------------------------------------------------------------------

def test_auto_resolve_never_touches_done_skipped_or_user_edited_sessions():
    from backend.api.routers.week import _auto_resolve

    st = _tested()
    frozen = {"resolved_session": {"exercise_instances": [
        {"exercise_id": "min_edge_hang", "prescription": {"sets": 6}, "suggested": {"x": 1}}]}}
    wp = {"start_date": "2026-10-05", "weeks": [{"days": [
        {"date": "2026-10-05", "sessions": [{"session_id": "strength_long", "location": "home", "status": "done",
                                             "resolved": deepcopy(frozen), "feedback": {"difficulty": "ok"},
                                             "completed_at": "2026-10-05T19:00:00"}]},
        {"date": "2026-10-06", "sessions": [{"session_id": "finger_strength_home", "location": "home",
                                             "status": "skipped", "resolved": deepcopy(frozen)}]},
        {"date": "2026-10-07", "sessions": [{"session_id": "strength_long", "location": "home",
                                             "_user_edited": True, "resolved": deepcopy(frozen)}]},
        {"date": "2026-10-09", "sessions": [{"session_id": "strength_long", "location": "home",
                                             "status": "planned"}]},
    ]}]}
    before = json.dumps([d["sessions"][0] for d in wp["weeks"][0]["days"][:3]], sort_keys=True)
    _auto_resolve(wp, st, None, phase="strength_power")
    after = json.dumps([d["sessions"][0] for d in wp["weeks"][0]["days"][:3]], sort_keys=True)
    assert before == after
    planned = wp["weeks"][0]["days"][3]["sessions"][0]["resolved"]
    ids = [i["exercise_id"] for i in planned["resolved_session"]["exercise_instances"]]
    assert "max_hang_7s" in ids


def test_resolution_is_deterministic():
    st = _tested()
    wp = _plan([("2026-10-09", "strength_long", "home", None)])
    a = _resolve(st, "strength_long", "2026-10-09", week_plan=wp)
    b = _resolve(st, "strength_long", "2026-10-09", week_plan=wp)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
