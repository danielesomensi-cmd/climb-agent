"""B414 (step 1, INBOX-2026-11-05) — one "was this logged row done" rule.

Before B414 two rules judged the same logged row: ``stimulus.logged_entry_counts``
(exposures, key sessions, finger-hard days, recency) dropped a catalog row
with ``completed: true`` and no counted set or load, while
``bw_ladders.ladder_row_done`` (ladders, closed loop) counted it. The guided
player sends no ``completed_sets`` for rows it never timed (1x1 lead drills,
fall practice done at the wall, timed work closed while running), so a catalog
session played to the end delivered nothing: lead_tryhard_gym of 04/11 → 13
rows, 0 counted, try-hard «missing» and technique «planned» for the week of
02/11.

Now ``stimulus.row_done`` is the one rule; ``logged_entry_counts`` and
``ladder_row_done`` call it. Critic's correction: a catalog row with no
``completed`` flag (non-app client: coach, API) stays done, as the ladders and
``load_score`` already read it — so the ladders and the closed loop do not
change on any row without ``completed_reps``. ``load_score`` is not touched.
"""

from __future__ import annotations

import copy
import itertools
import json
import logging

import pytest

from backend.engine import bw_ladders as bl
from backend.engine import key_sessions_v1 as ks
from backend.engine import measured_feedback as mf
from backend.engine import stimulus as st
from backend.engine.load_score import compute_actual_load_score
from backend.engine.replanner_v1 import regenerate_preserving_completed
from backend.tests.test_a294_key_sessions import _sess, _state
from backend.tests.test_a300_complementary_slots import days_of, plan

ABSENT = object()

# ---------------------------------------------------------------------------
# Frozen copies of the two rules before B414 (reference only, never called by
# the engine): they pin which verdicts move and which do not.
# ---------------------------------------------------------------------------


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pre_b414_logged_entry_counts(e, *, player_session):
    if e.get("completed") is False:
        return False
    if str(e.get("feedback_label") or "") == "skipped":
        return False
    sets = _num(e.get("completed_sets")) or 0
    reps = _num(e.get("completed_reps")) or 0
    if sets >= 1 or reps >= 1:
        return True
    if player_session:
        return False
    return _num(e.get("used_total_load_kg")) is not None or _num(e.get("used_external_load_kg")) is not None


def _pre_b414_ladder_row_done(row, *, player_session, dose_sets=None):
    if str(row.get("feedback_label") or "").strip().lower() == "skipped":
        return False
    sets = _num(row.get("completed_sets"))
    if row.get("completed") is False:
        need = dose_sets if dose_sets else bl._int(row.get("prescribed_sets"))
        return sets is not None and need is not None and sets >= need
    if sets is not None:
        return sets >= 1
    return not player_session


# ---------------------------------------------------------------------------
# 1. The matrix: session kind × completed × counted sets × label × load
# ---------------------------------------------------------------------------

_COMPLETED = (True, False, ABSENT)
_SETS = (ABSENT, 0, 1, 4)          # prescribed_sets is 4: 4 = the dose
_LABELS = (ABSENT, "skipped", "ok")
_LOADS = (ABSENT, 30.0)


def _row(completed, sets, label, load):
    row = {"exercise_id": "max_hang_7s", "prescribed_sets": 4}
    for key, val in (("completed", completed), ("completed_sets", sets),
                     ("feedback_label", label), ("used_external_load_kg", load)):
        if val is not ABSENT:
            row[key] = val
    return row


MATRIX = [(player, _row(c, s, lab, load))
          for player, c, s, lab, load in itertools.product((False, True), _COMPLETED, _SETS, _LABELS, _LOADS)]


def _spec(player, completed, sets, label):
    """The decision of 2026-11-07, written as a table."""
    if label == "skipped":
        return False
    if completed is False:
        return sets is not ABSENT and sets >= 4
    if sets is not ABSENT:
        return sets >= 1
    return not player


@pytest.mark.parametrize("player,completed,sets,label,load",
                         list(itertools.product((False, True), _COMPLETED, _SETS, _LABELS, _LOADS)))
def test_matrix_follows_the_decision(player, completed, sets, label, load):
    row = _row(completed, sets, label, load)
    assert st.row_done(row, player_session=player) is _spec(player, completed, sets, label), row


def test_every_reader_gives_the_same_answer():
    """logged_entry_counts (stimuli, keys, guards), ladder_row_done (ladders)
    and unrated_done (closed loop, no label / no measure) agree on every row."""
    for player, row in MATRIX:
        want = st.row_done(row, player_session=player)
        assert st.logged_entry_counts(row, player_session=player) is want, row
        assert bl.ladder_row_done(row, player_session=player) is want, row
        if "feedback_label" not in row:
            assert mf.unrated_done(row, None, player_session=player) is want, row


def test_a_load_or_a_rating_never_decides():
    """A logged load is pre-filled by the players, a rating is optional
    (A295/B413: no rating = ok): neither changes whether the row was done."""
    for player, c, s in itertools.product((False, True), _COMPLETED, _SETS):
        verdicts = {st.row_done(_row(c, s, lab, load), player_session=player)
                    for lab in (ABSENT, "ok") for load in _LOADS}
        assert len(verdicts) == 1, (player, c, s)


def test_ladders_and_closed_loop_unchanged_on_every_matrix_row():
    """Without completed_reps the ladder rule is exactly B413's: the bodyweight
    ladders and the closed loop's unrated-done read the same verdicts."""
    for player, row in MATRIX:
        for dose in (None, 3, 4, 5):
            assert bl.ladder_row_done(row, player_session=player, dose_sets=dose) is \
                _pre_b414_ladder_row_done(row, player_session=player, dose_sets=dose), (row, dose)


def test_only_these_stimulus_verdicts_move():
    """The rows logged_entry_counts now reads differently, and nothing else:
    (a) catalog, not completed:false, no counted set → done (Done without the
    timer, the dialog, no flag); (b) completed:false with the full dose →
    done; (c) catalog, an explicit 0 sets with a load → not done (the player
    said it counted none; the load is the player's pre-fill)."""
    moved = []
    for player, row in MATRIX:
        before = _pre_b414_logged_entry_counts(row, player_session=player)
        after = st.logged_entry_counts(row, player_session=player)
        if before is not after:
            moved.append((player, row.get("completed", ABSENT), row.get("completed_sets", ABSENT),
                          "used_external_load_kg" in row, after))
    for player, completed, sets, load, after in moved:
        if after:
            assert (not player and completed is not False and sets is ABSENT) or \
                (completed is False and sets == 4), (player, completed, sets, load)
        else:
            assert not player and sets == 0 and load, (player, completed, sets, load)
    assert any(m[-1] for m in moved) and any(not m[-1] for m in moved)


@pytest.mark.parametrize("row,player,done", [
    # completed_reps alone is counted work (per-hand rows, repeater test)
    ({"exercise_id": "x", "completed": True, "completed_reps": 6}, True, True),
    ({"exercise_id": "x", "completed": True, "completed_sets": 0, "completed_reps": 6}, False, True),
    ({"exercise_id": "x", "completed": True, "completed_reps": 0}, False, True),
    ({"exercise_id": "x", "completed": True, "completed_reps": 0}, True, False),
    # dose: dose_sets wins over prescribed_sets; "4-6" reads 4
    ({"exercise_id": "x", "completed": False, "completed_sets": 4, "prescribed_sets": "4-6"}, True, True),
    ({"exercise_id": "x", "completed": False, "completed_sets": 3, "prescribed_sets": "4-6"}, True, False),
    ({"exercise_id": "x", "completed": False, "completed_sets": 4}, False, False),  # no dose known
    # the label is read case- and space-insensitively
    ({"exercise_id": "x", "completed": True, "completed_sets": 4, "feedback_label": " Skipped "}, False, False),
])
def test_edge_rows(row, player, done):
    assert st.row_done(row, player_session=player) is done


def test_dose_sets_argument():
    row = {"exercise_id": "x", "completed": False, "completed_sets": 3, "prescribed_sets": 4}
    assert st.row_done(row, player_session=True) is False
    assert st.row_done(row, player_session=True, dose_sets=3) is True
    assert bl.ladder_row_done(row, player_session=True, dose_sets=3) is True


def test_load_score_is_untouched():
    """load_score keeps its own rule (flag absent = done, completed:false = not
    done whatever the sets): B312 reads it, B414 step 1 does not move it."""
    inst = [{"exercise_id": "four_by_four_bouldering"}, {"exercise_id": "max_hang_7s"}]
    fm = {"four_by_four_bouldering": 10.0, "max_hang_7s": 6.0}
    items = [{"exercise_id": "four_by_four_bouldering", "completed": False, "completed_sets": 4,
              "prescribed_sets": 4}, {"exercise_id": "max_hang_7s"}]
    assert st.row_done(items[0], player_session=True) is True
    from backend.engine.load_score import load_score_from_ids
    assert compute_actual_load_score(items, inst, fm) == load_score_from_ids(["max_hang_7s"], fm)


# ---------------------------------------------------------------------------
# 2. The shapes of the bug inbox
# ---------------------------------------------------------------------------

# lead_tryhard_gym of 04/11 as stored in prod (guided player, no set timed).
ROWS_0411 = [
    ("general_pulse_raise", True, None), ("dynamic_mobility_flow", True, None),
    ("active_hip_mobility", True, None), ("wall_slide", False, None),
    ("warmup_easy_boulders", True, None), ("fall_practice", True, "ok"),
    ("lead_precision_feet_above_bolt", True, None), ("lead_technique_under_pump", True, "ok"),
    ("pushup", False, None), ("scapular_pullup", False, None),
    ("cooldown_forearm_wrist_stretch", True, None), ("cooldown_hip_pigeon", True, None),
    ("full_body_stretch_flow", True, None),
]


def _rows_0411(**override):
    out = []
    for eid, completed, label in ROWS_0411:
        row = {"exercise_id": eid, "completed": override.get(eid, completed)}
        if label:
            row["feedback_label"] = label
        out.append(row)
    return out


def _tryhard_0411(**override):
    return _sess("evening", "lead_tryhard_gym", "done", actual_exercises=_rows_0411(**override))


def _req(phase, key):
    return next(r for r in ks.phase_requirements(phase) if r["key"] == key)


def test_0411_lead_tryhard_is_try_hard_and_technique():
    s = _tryhard_0411()
    cat = ks.load_exercise_catalog()
    entries, origin = st.counted_entries(s)
    assert origin == "actual"
    assert {e["exercise_id"] for e in entries} >= {
        "fall_practice", "lead_precision_feet_above_bolt", "lead_technique_under_pump"}
    assert "wall_slide" not in {e["exercise_id"] for e in entries}
    assert ks.tryhard_hit(s, _req("strength_power", "try_hard")) is True
    assert ks.technique_hit(s, cat, _req("strength_power", "technique")) is True
    # falls not done → not a try-hard (the fall exercise still decides, C276)
    assert ks.tryhard_hit(_tryhard_0411(fall_practice=False), _req("strength_power", "try_hard")) is False


def test_0411_week_status_try_hard_and_technique_done():
    state = _state()
    days = state["week_plans"]["2026-10-05"]["weeks"][0]["days"]
    days[1]["sessions"].append(_tryhard_0411())
    before = copy.deepcopy(state)
    status = ks.compute_key_status(state, "2026-10-07", week_start="2026-10-05", with_proposals=False)
    by_key = {r["key"]: r["status"] for r in status["requirements"]}
    assert by_key["try_hard"] == "done" and by_key["technique"] == "done"
    assert state == before  # a read: nothing stored changes


def test_0511_treadmill_walk_done_is_counted():
    s = _sess("lunch", "treadmill_zone2_cardio", "done", actual_exercises=[
        {"exercise_id": "treadmill_incline_walk", "completed": True, "feedback_label": "ok"},
        {"exercise_id": "hip_opener_flow", "completed": True}])
    entries, _origin = st.counted_entries(s)
    assert [e["exercise_id"] for e in entries] == ["treadmill_incline_walk", "hip_opener_flow"]


@pytest.mark.parametrize("sid,exercise_ids", [
    ("limit_boulder_gym", ["warmup_easy_boulders", "spray_wall_limit", "cooldown_hip_pigeon"]),
    ("route_endurance_gym", ["warmup_easy_boulders", "route_intervals"]),
    ("strength_long", ["general_pulse_raise", "max_hang_7s", "weighted_pullup"]),
])
def test_dialog_logged_catalog_session_delivers_like_unlogged(sid, exercise_ids):
    """The post-session dialog sends completed:true (+ an optional label) and
    no sets: the logged session delivers what the same session marked done
    without feedback delivers (the paradox of the inbox)."""
    planned = {"session_id": sid, "status": "done",
               "resolved": {"resolved_session": {"exercise_instances": [{"exercise_id": e} for e in exercise_ids]}}}
    logged = dict(planned, actual_exercises=[
        {"exercise_id": e, "completed": True, **({"feedback_label": "ok"} if i % 2 else {})}
        for i, e in enumerate(exercise_ids)])
    assert st.session_stimuli(logged) == st.session_stimuli(planned) != []
    assert st.is_finger_hard_session(logged) is st.is_finger_hard_session(planned)


def test_four_by_four_completed_false_with_every_set_counts():
    """03/11: custom, completed:false, 4/4 sets (the player's Skip) → a PE
    exposure; 3/4 → not done."""
    def custom(sets):
        return {"date": "2026-11-03", "slot": "evening", "session_id": "custom_cs_2ea7e4a9",
                "is_custom": True, "status": "done",
                "exercises": [{"exercise_id": "four_by_four_bouldering", "sets": 4}],
                "actual_exercises": [{"exercise_id": "four_by_four_bouldering", "completed": False,
                                      "completed_sets": sets, "prescribed_sets": 4}]}
    assert st.session_stimuli(custom(4)) == [st.FAMILY_POWER_ENDURANCE]
    assert st.session_stimuli(custom(3)) == []
    state = {"week_plans": {"2026-11-02": {"start_date": "2026-11-02", "weeks": [{"days": [
        {"date": "2026-11-03", "sessions": [custom(4)]}]}]}}}
    rows = st.exposures(state, families=[st.FAMILY_POWER_ENDURANCE])
    assert [(r["date"], r["sets_done"], r["evidence"]) for r in rows] == [("2026-11-03", 4, "measured")]


def test_library_player_prefill_still_not_counted():
    """The session-builder player sends completed:true and the pre-filled load
    even for an exercise it skipped: without a counted set it is not done."""
    s = {"session_id": "custom_cs_x", "is_custom": True, "status": "done",
         "exercises": [{"exercise_id": "max_hang_7s", "sets": 5}],
         "actual_exercises": [{"exercise_id": "max_hang_7s", "completed": True, "used_external_load_kg": 30}]}
    assert st.counted_entries(s) == ([], "actual")
    assert st.session_stimuli(s) == []
    assert st.is_finger_hard_session(s) is False
    s["actual_exercises"][0]["completed_sets"] = 2
    assert st.session_stimuli(s) == [st.FAMILY_FINGER_MAX]


def test_row_without_completed_from_a_non_app_client():
    """Critic's correction: /feedback does not require ``completed`` (the coach
    can post items without it). On a catalog session such a row is done for
    every reader — the ladders and load_score already read it so; in a player
    session it still needs a counted set."""
    row = {"exercise_id": "max_hang_7s", "used_total_load_kg": 110}
    assert st.row_done(row, player_session=False) is True
    assert bl.ladder_row_done(row, player_session=False) is True
    assert st.row_done(row, player_session=True) is False
    cat = {"session_id": "strength_long", "status": "done", "actual_exercises": [{"exercise_id": "max_hang_7s"}]}
    assert st.session_stimuli(cat) == [st.FAMILY_FINGER_MAX]


# ---------------------------------------------------------------------------
# 3. The planner: PASS 2.7 sees the lived try-hard (mid-week regeneration)
# ---------------------------------------------------------------------------


def _regenerate_with_tryhard_rows(rows):
    """Strength-power week 12/10: PASS 2.7 puts lead_tryhard_gym on Tuesday.
    Monday and Tuesday are lived (Tuesday logged with *rows*), the week is
    regenerated on Wednesday."""
    logging.disable(logging.WARNING)
    try:
        start, today = "2026-10-12", "2026-10-14"
        old = plan("strength_power", start_date=start)
        days = days_of(old)
        for d in days[:2]:
            for s in d["sessions"]:
                s["status"] = "done"
        (tue,) = [s for s in days[1]["sessions"] if s["session_id"] == "lead_tryhard_gym"]
        tue["actual_exercises"] = rows
        past = json.dumps(days[:2], sort_keys=True)
        new = plan("strength_power", start_date=start, today=today, existing_week_plan=old)
        merged = regenerate_preserving_completed(copy.deepcopy(old), new, preserve_before=today)
        assert json.dumps(days_of(merged)[:2], sort_keys=True) == past  # past byte-identical
        return new, merged
    finally:
        logging.disable(logging.NOTSET)


def test_pass_2_7_counts_the_lived_tryhard_done_without_sets():
    new, merged = _regenerate_with_tryhard_rows(_rows_0411())
    req = _req("strength_power", "try_hard")
    assert [s["session_id"] for d in days_of(merged) for s in d["sessions"] if ks.tryhard_hit(s, req)] == [
        "lead_tryhard_gym"]
    assert not any(u["stimulus"] == "try_hard" for u in new["unmet_stimulus"])
    assert not any(s["session_id"] in req["floor_candidates"] and "pass2.7:key_stimulus" in (s.get("explain") or [])
                   for d in days_of(new) for s in d["sessions"])


def test_pass_2_7_control_falls_not_done():
    """Control: the same week with the falls not done is a try-hard short —
    the test above is not passing by accident."""
    new, _merged = _regenerate_with_tryhard_rows(_rows_0411(fall_practice=False))
    assert any(u["stimulus"] == "try_hard" for u in new["unmet_stimulus"])


# ---------------------------------------------------------------------------
# 4. Reads only: no stored field of a past session moves
# ---------------------------------------------------------------------------


def test_readers_never_write_the_past():
    state = _state()
    days = state["week_plans"]["2026-10-05"]["weeks"][0]["days"]
    days[1]["sessions"].append(_tryhard_0411())
    days[0]["sessions"][0]["status"] = "done"
    days[0]["sessions"][0]["actual_exercises"] = [{"exercise_id": "spray_wall_limit", "completed": True}]
    before = json.dumps(state, sort_keys=True)
    ks.compute_key_status(state, "2026-10-07", week_start="2026-10-05", with_proposals=False)
    st.exposures(state)
    st.finger_hard_days(state)
    bl.seed_levels(state, "2026-10-07")
    assert json.dumps(state, sort_keys=True) == before


# ---------------------------------------------------------------------------
# 5. Review: the same dose for every reader, and the persisted registry
# ---------------------------------------------------------------------------


def _session_with_twin(row, *, custom):
    """A done session whose planned twin prescribes 4 sets; the logged row
    carries no ``prescribed_sets`` (legacy / un-attached rows)."""
    row = {k: v for k, v in row.items() if k != "prescribed_sets"}
    if custom:
        return {"session_id": "custom_cs_x", "is_custom": True, "status": "done",
                "exercises": [{"exercise_id": row["exercise_id"], "sets": 4}], "actual_exercises": [row]}
    return {"session_id": "strength_long", "status": "done",
            "resolved": {"resolved_session": {"exercise_instances": [
                {"exercise_id": row["exercise_id"], "prescription": {"sets": 4}}]}},
            "actual_exercises": [row]}


def test_stimulus_views_and_ladder_seed_read_the_same_dose():
    """B414 review: a completed:false row without its own prescribed_sets takes
    the dose from its planned twin in the stimulus views exactly as in the
    ladder seed (``bw_ladders._planned_twin``) — before, the views read no dose
    and dropped a fully counted row the seed counted."""
    for player, row in MATRIX:
        s = _session_with_twin(row, custom=player)
        e = s["actual_exercises"][0]
        seed = bl.ladder_row_done(e, player_session=player,
                                  dose_sets=bl._sets_of({}, bl._planned_twin(s, e["exercise_id"])))
        entries, _origin = st.counted_entries(s)
        assert (entries == [e]) is seed, (player, e)
        assert (st.session_stimuli(s) == [st.FAMILY_FINGER_MAX]) is seed, (player, e)


def test_four_by_four_without_prescribed_sets_counts_on_the_twin():
    s = _session_with_twin({"exercise_id": "four_by_four_bouldering", "completed": False,
                            "completed_sets": 4}, custom=True)
    assert st.session_stimuli(s) == [st.FAMILY_POWER_ENDURANCE]
    s["actual_exercises"][0]["completed_sets"] = 3
    assert st.session_stimuli(s) == []


def _registry_after(log_entry):
    from backend.engine.anchored_load import record_exposures
    updated = {}
    record_exposures(updated, log_entry)
    return {fam: [(r["exercise_id"], r["sets_done"]) for r in rows]
            for fam, rows in ((updated.get("progression_counters") or {}).get("stimulus_exposures") or {}).items()}


def test_registry_records_a_catalog_row_done_without_sets():
    """The persisted registry (progression_counters.stimulus_exposures, written
    by apply_feedback) follows the one rule: a catalog row closed with Done
    without the timer is an exposure; the library player's pre-fill is not."""
    item = {"exercise_id": "max_hang_7s", "completed": True}
    assert _registry_after({"date": "2026-11-04", "session_id": "strength_long",
                            "actual": {"exercise_feedback_v1": [item]}}) == {
        st.FAMILY_FINGER_MAX: [("max_hang_7s", None)]}
    prefill = dict(item, used_external_load_kg=30)
    assert _registry_after({"date": "2026-11-04", "session_id": "custom_cs_x",
                            "actual": {"exercise_feedback_v1": [prefill]}}) == {}


def test_registry_reads_the_planned_dose_of_a_completed_false_item():
    item = {"exercise_id": "four_by_four_bouldering", "completed": False, "completed_sets": 4}
    log = {"date": "2026-11-03", "session_id": "custom_cs_x",
           "planned": [{"exercise_instances": [{"exercise_id": "four_by_four_bouldering",
                                                "prescription": {"sets": 4}}]}],
           "actual": {"exercise_feedback_v1": [item]}}
    assert _registry_after(log) == {st.FAMILY_POWER_ENDURANCE: [("four_by_four_bouldering", 4)]}
    log["actual"]["exercise_feedback_v1"] = [dict(item, completed_sets=3)]
    assert _registry_after(log) == {}
