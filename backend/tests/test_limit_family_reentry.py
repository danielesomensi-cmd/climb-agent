"""B365 (R6.0) — limit-boulder grade memory per family + surface.

B413 (Daniele, 2026-11-04 «limit a grado pieno»): the re-entry discount (−½
grade for 2 sessions after a ≥14-day gap) is gone, for everyone — after a gap
the target is the remembered grade. The tests that pinned the re-entry now pin
its absence (base grade after a gap, legacy re-entry fields inert).

Fixture = Daniele's real working_loads on 2026-10-04 (read-only snapshot):
  limit_bouldering|board_kilter   7A  (2026-06-18)
  spray_wall_limit|board_kilter   7B  (2026-07-30)
  limit_bouldering|gym_boulder    7B  (2026-03-28, > 180 days on 05/10)
  assessment boulder_max_rp 7C

Before B365 the 60-day freshness gate dropped every one of those memories and
the target jumped back to the 7C outdoor-RP anchor on the Kilter too, with a
band low computed from the anchor (low above target when memory won).
"""

from copy import deepcopy

from backend.engine.progression_v1 import (
    FONT_GRADES,
    FONT_GRADE_TO_INDEX,
    apply_feedback,
    inject_targets,
)


KILTER_GYM = "16710e5a"
WALL_GYM = "wall_only"


def _state():
    return {
        "user": {"id": "daniele", "name": "Daniele"},
        "bodyweight_kg": 76.0,
        "assessment": {
            "grades": {
                "boulder_max_rp": "7C",
                "boulder_max_os": "7A",
                "lead_max_rp": "8a+",
                "lead_max_os": "7a+",
            }
        },
        "equipment": {
            "gyms": [
                {"gym_id": KILTER_GYM, "equipment": ["spraywall", "board_kilter", "gym_routes", "hangboard"]},
                {"gym_id": WALL_GYM, "equipment": ["gym_boulder"]},
            ]
        },
        "working_loads": {
            "rules": {},
            "entries": [
                {
                    "key": "limit_bouldering|surface=board_kilter",
                    "setup": {"surface": "board_kilter"},
                    "updated_at": "2026-06-18",
                    "exercise_id": "limit_bouldering",
                    "last_used_grade": "7A",
                    "surface_selected": "board_kilter",
                    "next_target_grade": "7A",
                    "last_feedback_label": "ok",
                },
                {
                    "key": "limit_bouldering|surface=gym_boulder",
                    "setup": {"surface": "gym_boulder"},
                    "updated_at": "2026-03-28",
                    "exercise_id": "limit_bouldering",
                    "last_used_grade": "7B",
                    "surface_selected": "gym_boulder",
                    "next_target_grade": "7B",
                    "last_feedback_label": "ok",
                },
                {
                    "key": "spray_wall_limit|surface=board_kilter",
                    "setup": {"surface": "board_kilter"},
                    "updated_at": "2026-07-30",
                    "exercise_id": "spray_wall_limit",
                    "last_used_grade": "7B",
                    "surface_selected": "board_kilter",
                    "next_target_grade": "7B",
                    "last_feedback_label": "ok",
                },
            ],
        },
    }


def _day(date: str, gym_id: str = KILTER_GYM, exercise_id: str = "limit_bouldering"):
    return {
        "date": date,
        "sessions": [
            {
                "session_id": "limit_boulder_gym",
                "intent": "power",
                "gym_id": gym_id,
                "tags": {"hard": True, "finger": True},
                "exercise_instances": [
                    {"exercise_id": exercise_id, "prescription": {"grade_ref": "boulder_max_rp", "grade_offset": 0}},
                ],
            }
        ],
    }


def _target(state, date, gym_id=KILTER_GYM, exercise_id="limit_bouldering"):
    out = inject_targets(_day(date, gym_id, exercise_id), deepcopy(state))
    return out["sessions"][0]["exercise_instances"][0]["suggested"]["suggested_boulder_target"]


def _feedback(state, date, label, used_grade, surface="board_kilter", gym_id=KILTER_GYM, exercise_id="limit_bouldering",
              contract=None):
    planned = inject_targets(_day(date, gym_id, exercise_id), deepcopy(state))["sessions"]
    log = {
        "date": date,
        "planned": planned,
        **({"feedback_contract": contract} if contract is not None else {}),
        "actual": {
            "exercise_feedback_v1": [
                {
                    "exercise_id": exercise_id,
                    "completed": True,
                    "feedback_label": label,
                    "used_grade": used_grade,
                    "surface_selected": surface,
                }
            ]
        },
    }
    return apply_feedback(log, state)


def _entry(state, exercise_id, surface):
    key = f"{exercise_id}|surface={surface}"
    return next(e for e in state["working_loads"]["entries"] if e["key"] == key)


def _idx(grade):
    return FONT_GRADE_TO_INDEX[grade]


# ─── Read side ───────────────────────────────────────────────────────────


def test_kilter_reads_family_memory_at_the_base_after_a_gap():
    """05/10: newest family entry on the Kilter is spray_wall_limit 7B (67 days,
    inside 180, past the old 14-day gap). B413: no re-entry — the target is the
    base 7B (B365 gave 7B − 1 half = 7A+ for 2 sessions)."""
    bt = _target(_state(), "2026-10-05")
    assert bt["surface_selected"] == "board_kilter"
    assert bt["target_grade"] == "7B"
    assert bt["target_grade_low"] == "7A"
    assert bt["target_source"] == "memory"
    assert "reentry" not in bt


def test_family_memory_shared_across_exercises():
    """The same Kilter memory drives every exercise of the family."""
    for ex in ("board_limit_boulders", "system_board_limit", "spray_wall_limit"):
        bt = _target(_state(), "2026-10-05", exercise_id=ex)
        assert bt["target_grade"] == "7B", ex


def test_gym_boulder_memory_older_than_180_days_reads_lower_of_anchor_and_stale():
    """gym_boulder 7B is from 28/03 (191 days): not trusted as a grade, but a
    longer absence must not give a HARDER target than a shorter one (review
    finding): min(anchor 7C, stale 7B) = 7B, the same as at 179 days (B413: no
    discount on either)."""
    bt = _target(_state(), "2026-10-05", gym_id=WALL_GYM)
    assert bt["surface_selected"] == "gym_boulder"
    assert bt["target_grade"] == "7B"
    assert bt["target_grade_low"] == "7A"
    assert bt["target_source"] == "memory"
    at_179 = _target(_state(), "2026-09-23", gym_id=WALL_GYM)
    assert at_179["target_grade"] == bt["target_grade"]


def test_stale_memory_above_anchor_reads_the_anchor():
    """Stale grade above the anchor: the anchor is the lower one and wins."""
    state = _state()
    gym = _entry(state, "limit_bouldering", "gym_boulder")
    gym["next_target_grade"] = gym["last_used_grade"] = "8A"
    bt = _target(state, "2026-10-05", gym_id=WALL_GYM)
    assert (bt["target_grade"], bt["target_source"]) == ("7C", "anchor")


def test_board_without_any_memory_anchors_two_half_grades_below_rp():
    """First-ever limit on a board: plain anchor, no re-entry — 7C − 2 half = 7B."""
    state = _state()
    state["working_loads"]["entries"] = []
    bt = _target(state, "2026-10-05")
    assert bt["target_grade"] == "7B"
    assert bt["target_grade_low"] == "7A"
    assert bt["target_source"] == "anchor"
    assert "reentry" not in bt


def test_gym_boulder_without_memory_is_plain_redpoint_anchor():
    state = _state()
    state["working_loads"]["entries"] = []
    bt = _target(state, "2026-10-05", gym_id=WALL_GYM)
    assert bt["target_grade"] == "7C"
    assert bt["target_grade_low"] == "7B"


def test_fresh_memory_wins_without_reentry():
    """Memory younger than 14 days: no re-entry, the remembered grade itself."""
    bt = _target(_state(), "2026-08-08")  # 9 days after the 7B of 30/07
    assert bt["target_grade"] == "7B"
    assert bt["target_source"] == "memory"
    assert "reentry" not in bt


def test_band_low_never_above_target_regression():
    """Old bug: low computed from the 7C anchor (7B) while the memory set the
    target to 7A → low 7B above target 7A. Now low = final target − 2 half."""
    state = _state()
    state["working_loads"]["entries"] = [
        {
            "key": "limit_bouldering|surface=gym_boulder",
            "setup": {"surface": "gym_boulder"},
            "updated_at": "2026-10-01",
            "exercise_id": "limit_bouldering",
            "last_used_grade": "7A",
            "next_target_grade": "7A",
        }
    ]
    bt = _target(state, "2026-10-05", gym_id=WALL_GYM)
    assert bt["target_grade"] == "7A"
    assert bt["target_grade_low"] == "6C"
    assert _idx(bt["target_grade_low"]) < _idx(bt["target_grade"])


def test_low_below_target_on_every_path():
    for date, gym in (("2026-10-05", KILTER_GYM), ("2026-10-05", WALL_GYM), ("2026-08-08", KILTER_GYM)):
        bt = _target(_state(), date, gym_id=gym)
        assert _idx(bt["target_grade_low"]) == _idx(bt["target_grade"]) - 2, (date, gym)


def test_floor_per_surface_holds_target_near_best():
    """Newest entry dropped to 6B, but 7B was logged on the same surface within
    180 days → floor = 7B − 2 half = 7A."""
    state = _state()
    state["working_loads"]["entries"].append(
        {
            "key": "board_limit_boulders|surface=board_kilter",
            "setup": {"surface": "board_kilter"},
            "updated_at": "2026-08-05",
            "exercise_id": "board_limit_boulders",
            "last_used_grade": "6C",
            "next_target_grade": "6B",
        }
    )
    bt = _target(state, "2026-08-10")
    assert bt["target_grade"] == "7A"


def _kilter_only(next_grade, last_grade, label, updated_at="2026-09-01"):
    state = _state()
    state["working_loads"]["entries"] = [
        {
            "key": "limit_bouldering|surface=board_kilter",
            "setup": {"surface": "board_kilter"},
            "updated_at": updated_at,
            "exercise_id": "limit_bouldering",
            "last_used_grade": last_grade,
            "surface_selected": "board_kilter",
            "next_target_grade": next_grade,
            "last_feedback_label": label,
        }
    ]
    return state


def test_floor_after_very_hard_then_gap_is_the_clamped_base():
    """very_hard @7B → memory 6C, then a 34-day gap. The floor clamps the
    memory (best climbed 7B − 2 half = 7A; 7B − 1 half after the failure is
    above it) → 7A. B413: no discount after it (B365 gave 6C+)."""
    bt = _target(_kilter_only("6C", "7B", "very_hard"), "2026-10-05")
    assert (bt["target_source"], bt["target_grade"]) == ("memory", "7A")


def test_hard_then_gap_is_the_memory():
    """hard @7B → memory 7A, gap → 7A (B365 discounted it to 6C+)."""
    bt = _target(_kilter_only("7A", "7B", "hard"), "2026-10-05")
    assert (bt["target_source"], bt["target_grade"]) == ("memory", "7A")
    assert "reentry" not in bt


def test_floor_ignores_targets_never_climbed():
    """An 'easy' at 7B writes next 7C; 7C was never climbed, so it must not
    build the floor (7C − 2 half = 7B). Best climbed = 7B → floor 7A."""
    state = _kilter_only("6B", "6C", "ok", updated_at="2026-10-01")
    state["working_loads"]["entries"].append(
        {
            "key": "board_limit_boulders|surface=board_kilter",
            "setup": {"surface": "board_kilter"},
            "updated_at": "2026-09-28",
            "exercise_id": "board_limit_boulders",
            "last_used_grade": "7B",
            "next_target_grade": "7C",
            "last_feedback_label": "easy",
        }
    )
    assert _target(state, "2026-10-05")["target_grade"] == "7A"


def test_run_of_very_hard_walks_target_down():
    """Review finding: 7C, 7B, 7A failed one after another must not leave the
    target pinned at 7A for 180 days."""
    state = _state()
    state = _feedback(state, "2026-10-05", "ok", "7A+")
    state = _feedback(state, "2026-10-07", "ok", "7A+")
    state = _feedback(state, "2026-10-09", "easy", "7B")
    seen = []
    for d in ("2026-10-11", "2026-10-13", "2026-10-15", "2026-10-17"):
        t = _target(state, d)["target_grade"]
        seen.append(t)
        state = _feedback(state, d, "very_hard", t)
    final = _target(state, "2026-10-19")["target_grade"]
    # strictly decreasing after each failure, never pinned
    assert all(_idx(a) > _idx(b) for a, b in zip(seen, seen[1:] + [final])), (seen, final)


def test_gap_after_gap_is_still_the_base():
    """B413: a rated ok at the base, then 46 days off → still the base (B365
    restarted a 2-session discount here)."""
    state = _feedback(_state(), "2026-10-05", "ok", "7B", contract=2)
    assert _entry(state, "limit_bouldering", "board_kilter")["next_target_grade"] == "7B"
    bt = _target(state, "2026-11-20")
    assert (bt["target_grade"], bt["target_source"]) == ("7B", "memory")
    state = _feedback(state, "2026-11-20", "ok", "7B", contract=2)
    e = _entry(state, "limit_bouldering", "board_kilter")
    assert not any(k.startswith("reentry_") for k in e)
    assert _target(state, "2026-11-22")["target_grade"] == "7B"


def test_limit_next_target_matches_card():
    """Coach prompt / weekly report read the prescribed grade, not the stored
    value (review finding): the per-surface floor lifts a stored 6C to 7A."""
    from backend.engine.progression_v1 import limit_next_target

    state = _kilter_only("6C", "7B", "very_hard")
    e = _entry(state, "limit_bouldering", "board_kilter")
    assert e["next_target_grade"] == "6C"
    assert limit_next_target(state, e, "2026-10-07") == _target(state, "2026-10-07")["target_grade"] == "7A"
    assert limit_next_target(state, {"exercise_id": "weighted_pullup"}, "2026-10-07") is None


def test_surfaces_do_not_leak():
    """A fresh 8A on the gym wall does not move the Kilter target."""
    state = _state()
    state["working_loads"]["entries"].append(
        {
            "key": "limit_bouldering|surface=gym_boulder",
            "setup": {"surface": "gym_boulder"},
            "updated_at": "2026-10-03",
            "exercise_id": "limit_bouldering",
            "last_used_grade": "8A",
            "next_target_grade": "8A",
        }
    )
    assert _target(state, "2026-10-05")["target_grade"] == "7B"


def test_future_entry_ignored_for_past_date():
    """Resolving a date before an entry's updated_at does not read that entry."""
    bt = _target(_state(), "2026-07-01")  # only the 18/06 7A exists then
    assert bt["target_grade"] == "7A"
    assert bt["target_source"] == "memory"


# ─── Write side (B413: no re-entry) ───────────────────────────────────────


def test_three_sessions_ok_after_a_gap_stay_at_the_base():
    """7B → 7B → 7B with a rated 'ok' each time: the first session after the
    gap is already the base, and no re-entry field is written."""
    state = _state()
    for d in ("2026-10-05", "2026-10-12", "2026-10-19"):
        bt = _target(state, d)
        assert (bt["target_grade"], bt["target_source"]) == ("7B", "memory"), d
        state = _feedback(state, d, "ok", "7B", contract=2)
        e = _entry(state, "limit_bouldering", "board_kilter")
        assert e["next_target_grade"] == "7B"
        assert not any(k.startswith("reentry_") for k in e)


def test_label_after_a_gap_steps_from_the_grade_climbed():
    """The first session after a gap is a normal session: 'easy' at the 7B
    base → 7B+ (A291: +1 half grade). B365 held the base for 2 sessions."""
    state = _feedback(_state(), "2026-10-05", "easy", "7B")
    assert _entry(state, "limit_bouldering", "board_kilter")["next_target_grade"] == "7B+"
    state = _feedback(state, "2026-10-12", "very_easy", "7B+")
    assert _entry(state, "limit_bouldering", "board_kilter")["next_target_grade"] == "7C+"


def test_unrated_lower_grade_after_a_gap_keeps_the_memory():
    """B413 (D3): a legacy 'ok' is not rated; done at 7A+ under the 7B memory,
    it never lowers it — the memory entry keeps 7B, only its date moves. Then
    'easy' at 7B steps from the base as usual."""
    state = _feedback(_state(), "2026-10-05", "ok", "7A+")
    spray = _entry(state, "spray_wall_limit", "board_kilter")
    assert (spray["next_target_grade"], spray["updated_at"]) == ("7B", "2026-10-05")
    assert _target(state, "2026-10-12")["target_grade"] == "7B"
    state = _feedback(state, "2026-10-19", "easy", "7B")
    e = _entry(state, "limit_bouldering", "board_kilter")
    assert e["next_target_grade"] == "7B+"  # A291: easy = +1 half grade
    assert "reentry_base_grade" not in e


def test_legacy_open_reentry_fields_are_inert_and_dropped():
    """An entry written while a B365 re-entry was open keeps the BASE in
    next_target_grade: it reads as that base (no discount, no migration) and
    the next write drops the old fields."""
    state = _kilter_only("7B", "7A+", "ok", updated_at="2026-10-01")
    _entry(state, "limit_bouldering", "board_kilter").update({
        "reentry_base_grade": "7B", "reentry_exposures": 1,
        "reentry_started_at": "2026-10-01", "reentry_last_at": "2026-10-01"})
    bt = _target(state, "2026-10-05")
    assert (bt["target_grade"], bt["target_source"]) == ("7B", "memory")
    out = _feedback(state, "2026-10-05", "ok", "7B", contract=2)
    e = _entry(out, "limit_bouldering", "board_kilter")
    assert e["next_target_grade"] == "7B"
    assert not any(k.startswith("reentry_") for k in e)


def test_same_day_resubmission_is_idempotent():
    state = _feedback(_state(), "2026-10-05", "ok", "7B", contract=2)
    again = _feedback(state, "2026-10-05", "ok", "7B", contract=2)
    assert again["working_loads"] == state["working_loads"]
    assert _entry(again, "limit_bouldering", "board_kilter")["next_target_grade"] == "7B"
    unrated = _feedback(_state(), "2026-10-05", "ok", "7A+")
    assert _feedback(unrated, "2026-10-05", "ok", "7A+")["working_loads"] == unrated["working_loads"]


def test_first_ever_feedback_steps_from_the_grade():
    """No memory at all → the legacy per-feedback step (B289 unchanged)."""
    state = _state()
    state["working_loads"]["entries"] = []
    out = _feedback(state, "2026-10-05", "easy", "7A")
    e = _entry(out, "limit_bouldering", "board_kilter")
    assert e["next_target_grade"] == "7A+"  # A291: easy = +1 half grade
    assert "reentry_base_grade" not in e


def test_inject_targets_does_not_mutate_state():
    state = _state()
    snapshot = deepcopy(state)
    _target(state, "2026-10-05")
    assert state == snapshot


def test_deterministic():
    a = _target(_state(), "2026-10-05")
    b = _target(_state(), "2026-10-05")
    assert a == b


def test_font_scale_has_half_grades():
    # Guard on the scale the half-grade arithmetic relies on.
    assert FONT_GRADES[FONT_GRADE_TO_INDEX["7A"] + 1] == "7A+"


# ─── Read-only consumers quote the prescribed grade (review finding) ─────


def test_coach_prompt_quotes_prescribed_limit_grade():
    from datetime import date

    from backend.coach.prompt_builder import _baselines_section

    today = date.today()
    # A stored 6C under a 7B climbed today: the floor makes the card 7A.
    state = _kilter_only("6C", "7B", "very_hard", updated_at=today.isoformat())
    text = _baselines_section(state)
    line = next(l for l in text.splitlines() if "limit_bouldering" in l and "board_kilter" in l)
    assert "next target grade 7A" in line and "7A+" not in line, line


def test_weekly_report_progression_quotes_prescribed_limit_grade():
    from backend.engine.report_engine import _build_progression

    state = _kilter_only("6C", "7B", "very_hard", updated_at="2026-10-06")
    rows = _build_progression(state["working_loads"], "2026-10-05", state)
    row = next(r for r in rows if r["exercise_id"] == "limit_bouldering")
    assert row["current_load"] == "7A"  # stored value is 6C, the floor lifts it
    # Without user_state the legacy raw value is kept (back-compat).
    legacy = _build_progression(state["working_loads"], "2026-10-05")
    assert next(r for r in legacy if r["exercise_id"] == "limit_bouldering")["current_load"] == "6C"
