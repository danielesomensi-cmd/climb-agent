"""B365 (R6.0) — limit-boulder grade memory per family + surface, re-entry.

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


def _feedback(state, date, label, used_grade, surface="board_kilter", gym_id=KILTER_GYM, exercise_id="limit_bouldering"):
    planned = inject_targets(_day(date, gym_id, exercise_id), deepcopy(state))["sessions"]
    log = {
        "date": date,
        "planned": planned,
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


def test_kilter_reads_family_memory_and_opens_reentry():
    """05/10: newest family entry on the Kilter is spray_wall_limit 7B (67 days,
    inside 180, past the 14-day gap) → re-entry at 7B − 1 half = 7A+."""
    bt = _target(_state(), "2026-10-05")
    assert bt["surface_selected"] == "board_kilter"
    assert bt["target_grade"] == "7A+"
    assert bt["target_grade_low"] == "6C+"
    assert bt["target_source"] == "reentry"
    assert bt["reentry"]["base_grade"] == "7B"
    assert bt["reentry"]["exposures_done"] == 0
    assert bt["reentry"]["exposures_required"] == 2


def test_family_memory_shared_across_exercises():
    """The same Kilter memory drives every exercise of the family."""
    for ex in ("board_limit_boulders", "system_board_limit", "spray_wall_limit"):
        bt = _target(_state(), "2026-10-05", exercise_id=ex)
        assert bt["target_grade"] == "7A+", ex


def test_gym_boulder_memory_older_than_180_days_reenters_from_lower_of_anchor_and_stale():
    """gym_boulder 7B is from 28/03 (191 days): not trusted as a grade, but a
    longer absence must not give a HARDER target than a shorter one (review
    finding): base = min(anchor 7C, stale 7B) = 7B → re-entry 7A+, the same
    as at 179 days."""
    bt = _target(_state(), "2026-10-05", gym_id=WALL_GYM)
    assert bt["surface_selected"] == "gym_boulder"
    assert bt["target_grade"] == "7A+"
    assert bt["target_grade_low"] == "6C+"
    assert bt["reentry"]["base_grade"] == "7B"
    at_179 = _target(_state(), "2026-09-23", gym_id=WALL_GYM)
    assert at_179["target_grade"] == bt["target_grade"]


def test_stale_memory_above_anchor_reenters_from_anchor():
    """Stale grade above the anchor: the anchor is the lower one and wins."""
    state = _state()
    gym = _entry(state, "limit_bouldering", "gym_boulder")
    gym["next_target_grade"] = gym["last_used_grade"] = "8A"
    bt = _target(state, "2026-10-05", gym_id=WALL_GYM)
    assert bt["reentry"]["base_grade"] == "7C"
    assert bt["target_grade"] == "7B+"


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


def test_floor_never_lifts_reentry_above_base_after_very_hard():
    """Review finding (high): very_hard @7B → memory 6C, then a 34-day gap.
    The floor used to be applied AFTER the discount and gave 7A, a full letter
    above the 6C base. Now the floor clamps the base (7B − 1 half = 7A+ cap
    after a failure, best-climbed floor 7A → base 7A), then the discount: 6C+."""
    bt = _target(_kilter_only("6C", "7B", "very_hard"), "2026-10-05")
    assert bt["target_source"] == "reentry"
    assert bt["target_grade"] == "6C+"
    assert _idx(bt["target_grade"]) < _idx(bt["reentry"]["base_grade"])


def test_hard_then_gap_still_discounted():
    """hard @7B → memory 7A, gap → re-entry 6C+ (the floor no longer cancels
    the discount)."""
    bt = _target(_kilter_only("7A", "7B", "hard"), "2026-10-05")
    assert bt["reentry"]["base_grade"] == "7A"
    assert bt["target_grade"] == "6C+"


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


def test_new_gap_restarts_open_reentry():
    """Review finding: one re-entry session, then 46 days off → the ramp
    restarts from zero (2 eased sessions), not closed after one."""
    state = _feedback(_state(), "2026-10-05", "ok", "7A+")
    bt = _target(state, "2026-11-20")
    assert bt["target_grade"] == "7A+"
    assert bt["reentry"]["exposures_done"] == 0
    state = _feedback(state, "2026-11-20", "ok", "7A+")
    e = _entry(state, "limit_bouldering", "board_kilter")
    assert e["reentry_exposures"] == 1
    assert e["reentry_started_at"] == "2026-11-20"
    assert _target(state, "2026-11-22")["target_grade"] == "7A+"


def test_limit_next_target_matches_card():
    """Coach prompt / weekly report read the prescribed grade, not the stored
    base (review finding)."""
    from backend.engine.progression_v1 import limit_next_target

    state = _feedback(_state(), "2026-10-05", "ok", "7A+")
    e = _entry(state, "limit_bouldering", "board_kilter")
    assert e["next_target_grade"] == "7B"
    assert limit_next_target(state, e, "2026-10-07") == _target(state, "2026-10-07")["target_grade"] == "7A+"
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
    assert _target(state, "2026-10-05")["target_grade"] == "7A+"


def test_future_entry_ignored_for_past_date():
    """Resolving a date before an entry's updated_at does not read that entry."""
    bt = _target(_state(), "2026-07-01")  # only the 18/06 7A exists then
    assert bt["target_grade"] == "7A"
    assert bt["target_source"] == "memory"


# ─── Write side: the discount must not become permanent ──────────────────


def test_three_sessions_ok_reentry_then_base():
    """7A+ → 7A+ → 7B with 'ok' each time (the spec's stability test)."""
    state = _state()

    assert _target(state, "2026-10-05")["target_grade"] == "7A+"
    state = _feedback(state, "2026-10-05", "ok", "7A+")
    e = _entry(state, "limit_bouldering", "board_kilter")
    assert e["next_target_grade"] == "7B"  # the BASE, not the discounted 7A+
    assert e["reentry_base_grade"] == "7B"
    assert e["reentry_exposures"] == 1
    assert e["reentry_started_at"] == "2026-10-05"

    bt = _target(state, "2026-10-12")
    assert bt["target_grade"] == "7A+"
    assert bt["reentry"]["exposures_done"] == 1
    state = _feedback(state, "2026-10-12", "ok", "7A+")
    e = _entry(state, "limit_bouldering", "board_kilter")
    assert e["next_target_grade"] == "7B"
    assert e["reentry_exposures"] == 2

    bt = _target(state, "2026-10-19")
    assert bt["target_grade"] == "7B"
    assert bt["target_source"] == "memory"
    assert "reentry" not in bt


def test_reentry_closing_applies_label_delta_to_base():
    """Second re-entry session 'easy' → base + 1 half grade (A291; was a whole
    letter) = 7B+, regardless of the discounted grade that was actually climbed."""
    state = _feedback(_state(), "2026-10-05", "very_easy", "7A+")
    assert _entry(state, "limit_bouldering", "board_kilter")["next_target_grade"] == "7B"
    state = _feedback(state, "2026-10-12", "easy", "7A+")
    assert _entry(state, "limit_bouldering", "board_kilter")["next_target_grade"] == "7B+"


def test_normal_progression_after_reentry_unchanged():
    state = _feedback(_state(), "2026-10-05", "ok", "7A+")
    state = _feedback(state, "2026-10-12", "ok", "7A+")
    state = _feedback(state, "2026-10-19", "easy", "7B")
    e = _entry(state, "limit_bouldering", "board_kilter")
    assert e["next_target_grade"] == "7B+"  # A291: easy = +1 half grade
    assert "reentry_base_grade" not in e


def test_same_day_resubmission_is_idempotent():
    state = _feedback(_state(), "2026-10-05", "ok", "7A+")
    again = _feedback(state, "2026-10-05", "ok", "7A+")
    e = _entry(again, "limit_bouldering", "board_kilter")
    assert e["reentry_exposures"] == 1
    assert e["next_target_grade"] == "7B"


def test_first_ever_feedback_has_no_reentry():
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
    state = _feedback(_state(), today.isoformat(), "ok", "7A+")
    # Force an open re-entry dated today: base 7B, 1 exposure done.
    e = _entry(state, "limit_bouldering", "board_kilter")
    e.update({"next_target_grade": "7B", "reentry_base_grade": "7B", "reentry_exposures": 1,
              "reentry_started_at": today.isoformat(), "reentry_last_at": today.isoformat()})
    text = _baselines_section(state)
    line = next(l for l in text.splitlines() if "limit_bouldering" in l and "board_kilter" in l)
    assert "next target grade 7A+" in line, line


def test_weekly_report_progression_quotes_prescribed_limit_grade():
    from backend.engine.report_engine import _build_progression

    state = _feedback(_state(), "2026-10-05", "ok", "7A+")
    rows = _build_progression(state["working_loads"], "2026-10-05", state)
    row = next(r for r in rows if r["exercise_id"] == "limit_bouldering")
    assert row["current_load"] == "7A+"  # stored base is 7B
    # Without user_state the legacy raw value is kept (back-compat).
    legacy = _build_progression(state["working_loads"], "2026-10-05")
    assert next(r for r in legacy if r["exercise_id"] == "limit_bouldering")["current_load"] == "7B"
