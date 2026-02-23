"""E2E tests: full feedback → progression loop.

Each test simulates multiple sessions, feeding the output of one
back as input to the next, and asserts that load/grade progression
behaves correctly end-to-end.

Run with:  python -m pytest backend/tests/test_feedback_loop_e2e.py -v -s
"""
from copy import deepcopy

from backend.engine.progression_v1 import (
    EXTERNAL_LOAD_FALLBACK_PCT_BW,
    WHOLE_FONT_GRADES,
    _round_half_step,
    apply_feedback,
    inject_targets,
    step_grade,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_user_state(bodyweight: float = 75.0, *, baseline_total: float = 100.0,
                     grades: dict | None = None, extra: dict | None = None) -> dict:
    us = {
        "schema_version": "1.4",
        "bodyweight_kg": bodyweight,
        "baselines": {"hangboard": [{"max_total_load_kg": baseline_total}]},
        "assessment": {"grades": grades or {}},
        "working_loads": {"entries": [], "rules": {}},
        "performance": {},
        "equipment": {"home": ["hangboard", "pullup_bar"], "gyms": []},
    }
    if extra:
        us.update(extra)
    return us


def _day_with_instance(exercise_id: str, prescription: dict | None = None,
                       attributes: dict | None = None) -> dict:
    inst = {"exercise_id": exercise_id, "prescription": prescription or {}}
    if attributes:
        inst["attributes"] = attributes
    return {"date": "2026-02-01", "sessions": [{"exercise_instances": [inst]}]}


def _feedback_log(date: str, exercise_id: str, label: str, *,
                  used_external: float | None = None,
                  used_total: float | None = None,
                  prescription: dict | None = None) -> dict:
    item: dict = {"exercise_id": exercise_id, "completed": True, "feedback_label": label}
    if used_external is not None:
        item["used_external_load_kg"] = used_external
    if used_total is not None:
        item["used_total_load_kg"] = used_total
    return {
        "date": date,
        "planned": [{"exercise_instances": [{"exercise_id": exercise_id, "prescription": prescription or {}}]}],
        "actual": {"exercise_feedback_v1": [item]},
    }


def _get_entry(user_state: dict, exercise_id: str) -> dict:
    return next(e for e in user_state["working_loads"]["entries"]
                if e["exercise_id"] == exercise_id)


# ─── B1: max_hang_5s  (3-session loop) ───────────────────────────────────────

def test_e2e_max_hang_loop():
    """max_hang_5s: hard decreases total, easy increases total."""
    BW = 75.0
    us = _make_user_state(BW, baseline_total=100.0)

    # S1: inject → suggested 90kg total (100×0.9), 15kg external
    day1 = _day_with_instance("max_hang_5s", {"intensity_pct_of_total_load": 0.9, "sets": 6, "hang_seconds": 5})
    day1 = inject_targets(day1, us)
    s1 = day1["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"S1 suggested: total={s1['suggested_total_load_kg']}, ext={s1['suggested_external_load_kg']}")
    assert s1["suggested_total_load_kg"] == 90.0
    assert s1["suggested_external_load_kg"] == 15.0

    # Feedback "hard" → pct = -0.025 → total 90×0.975 = 87.75 → 88.0, ext = 88-75 = 13.0
    log1 = _feedback_log("2026-02-01", "max_hang_5s", "hard", used_total=90.0, used_external=15.0)
    us = apply_feedback(log1, us)
    e1 = _get_entry(us, "max_hang_5s")
    print(f"After hard: next_total={e1['next_total_load_kg']}, next_ext={e1['next_external_load_kg']}")
    assert e1["next_total_load_kg"] == 88.0
    assert e1["next_external_load_kg"] == 13.0

    # S2: inject again — should pick up working_loads
    day2 = _day_with_instance("max_hang_5s", {"intensity_pct_of_total_load": 0.9, "sets": 6, "hang_seconds": 5})
    day2["date"] = "2026-02-03"
    day2 = inject_targets(day2, us)
    s2 = day2["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"S2 suggested: total={s2['suggested_total_load_kg']}, ext={s2['suggested_external_load_kg']}")
    assert s2["suggested_total_load_kg"] == 88.0
    assert s2["suggested_external_load_kg"] == 13.0

    # Feedback "easy" → pct = 0.075 → total 88×1.075 = 94.6 → 94.5, ext = 94.5-75 = 19.5
    log2 = _feedback_log("2026-02-03", "max_hang_5s", "easy", used_total=88.0, used_external=13.0)
    us = apply_feedback(log2, us)
    e2 = _get_entry(us, "max_hang_5s")
    print(f"After easy: next_total={e2['next_total_load_kg']}, next_ext={e2['next_external_load_kg']}")
    assert e2["next_total_load_kg"] == 94.5
    assert e2["next_external_load_kg"] == 19.5

    # S3: inject — should pick up latest
    day3 = _day_with_instance("max_hang_5s", {"intensity_pct_of_total_load": 0.9, "sets": 6, "hang_seconds": 5})
    day3["date"] = "2026-02-05"
    day3 = inject_targets(day3, us)
    s3 = day3["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"S3 suggested: total={s3['suggested_total_load_kg']}, ext={s3['suggested_external_load_kg']}")
    assert s3["suggested_total_load_kg"] == 94.5
    assert s3["suggested_external_load_kg"] == 19.5

    # Monotonicity: hard decreased, easy increased
    assert s2["suggested_total_load_kg"] < s1["suggested_total_load_kg"]
    assert s3["suggested_total_load_kg"] > s2["suggested_total_load_kg"]


# ─── B2: repeater_hang_7_3  (2-session loop, counterweight) ──────────────────

def test_e2e_repeater_hang_loop():
    """repeater_hang_7_3: light climber starts with negative external (counterweight)."""
    BW = 75.0
    us = _make_user_state(BW, baseline_total=100.0)

    # S1: default intensity 0.70 → 100×0.70 = 70.0 total, -5.0 external (counterweight!)
    day1 = _day_with_instance("repeater_hang_7_3")
    day1 = inject_targets(day1, us)
    s1 = day1["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"S1 suggested: total={s1['suggested_total_load_kg']}, ext={s1['suggested_external_load_kg']}")
    assert s1["suggested_total_load_kg"] == 70.0
    assert s1["suggested_external_load_kg"] == -5.0

    # Feedback "very_easy" → pct = 0.15 → total 70×1.15 = 80.5, ext = 80.5-75 = 5.5
    log1 = _feedback_log("2026-02-01", "repeater_hang_7_3", "very_easy", used_total=70.0, used_external=-5.0)
    us = apply_feedback(log1, us)
    e1 = _get_entry(us, "repeater_hang_7_3")
    print(f"After very_easy: next_total={e1['next_total_load_kg']}, next_ext={e1['next_external_load_kg']}")
    assert e1["next_total_load_kg"] == 80.5
    assert e1["next_external_load_kg"] == 5.5

    # S2: inject — picks up working_loads
    day2 = _day_with_instance("repeater_hang_7_3")
    day2["date"] = "2026-02-03"
    day2 = inject_targets(day2, us)
    s2 = day2["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"S2 suggested: total={s2['suggested_total_load_kg']}, ext={s2['suggested_external_load_kg']}")
    assert s2["suggested_total_load_kg"] == 80.5
    assert s2["suggested_external_load_kg"] == 5.5

    # Progression: total increased, external went from negative to positive
    assert s2["suggested_total_load_kg"] > s1["suggested_total_load_kg"]


# ─── B3: bench_press  (3-session external_load loop) ─────────────────────────

def test_e2e_bench_press_loop():
    """bench_press: EXTERNAL_LOAD path, no bodyweight involved."""
    BW = 75.0
    us = _make_user_state(BW)

    # S1: no history → fallback 40% BW = 30.0
    day1 = _day_with_instance("bench_press", {"sets": 3, "reps": 8})
    day1 = inject_targets(day1, us)
    s1 = day1["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"S1 suggested: ext={s1['suggested_external_load_kg']}")
    assert s1["suggested_external_load_kg"] == 30.0

    # Feedback "easy" → pct 0.075 → 30×1.075 = 32.25 → 32.0
    log1 = _feedback_log("2026-02-01", "bench_press", "easy", used_external=30.0)
    us = apply_feedback(log1, us)
    e1 = _get_entry(us, "bench_press")
    print(f"After easy: next_ext={e1['next_external_load_kg']}")
    assert e1["next_external_load_kg"] == 32.0

    # S2: from history
    day2 = _day_with_instance("bench_press", {"sets": 3, "reps": 8})
    day2["date"] = "2026-02-03"
    day2 = inject_targets(day2, us)
    s2 = day2["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"S2 suggested: ext={s2['suggested_external_load_kg']}")
    assert s2["suggested_external_load_kg"] == 32.0

    # Feedback "ok" → pct 0.025 → 32×1.025 = 32.8 → 33.0
    log2 = _feedback_log("2026-02-03", "bench_press", "ok", used_external=32.0)
    us = apply_feedback(log2, us)
    e2 = _get_entry(us, "bench_press")
    print(f"After ok: next_ext={e2['next_external_load_kg']}")
    assert e2["next_external_load_kg"] == 33.0

    # S3: from history
    day3 = _day_with_instance("bench_press", {"sets": 3, "reps": 8})
    day3["date"] = "2026-02-05"
    day3 = inject_targets(day3, us)
    s3 = day3["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"S3 suggested: ext={s3['suggested_external_load_kg']}")
    assert s3["suggested_external_load_kg"] == 33.0


# ─── B4: turkish_getup  (external_load, reads constant) ──────────────────────

def test_e2e_turkish_getup_loop():
    """turkish_getup: uses EXTERNAL_LOAD_FALLBACK_PCT_BW constant, no hardcoded %."""
    BW = 75.0
    us = _make_user_state(BW)
    pct = EXTERNAL_LOAD_FALLBACK_PCT_BW["turkish_getup"]

    # S1: fallback = pct × BW, rounded
    expected_fallback = _round_half_step(BW * pct)
    day1 = _day_with_instance("turkish_getup", {"sets": 3, "reps": 5})
    day1 = inject_targets(day1, us)
    s1 = day1["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"S1 suggested: ext={s1['suggested_external_load_kg']} (fallback pct={pct})")
    assert s1["suggested_external_load_kg"] == expected_fallback

    # Feedback "very_hard" → pct = -0.10 → fallback × 0.90
    expected_next = _round_half_step(expected_fallback * 0.90)
    log1 = _feedback_log("2026-02-01", "turkish_getup", "very_hard", used_external=expected_fallback)
    us = apply_feedback(log1, us)
    e1 = _get_entry(us, "turkish_getup")
    print(f"After very_hard: next_ext={e1['next_external_load_kg']}")
    assert e1["next_external_load_kg"] == expected_next

    # S2: decreased
    day2 = _day_with_instance("turkish_getup", {"sets": 3, "reps": 5})
    day2["date"] = "2026-02-03"
    day2 = inject_targets(day2, us)
    s2 = day2["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"S2 suggested: ext={s2['suggested_external_load_kg']}")
    assert s2["suggested_external_load_kg"] == expected_next
    assert s2["suggested_external_load_kg"] < s1["suggested_external_load_kg"]


# ─── B5: grade-relative (route_intervals) ────────────────────────────────────

def test_e2e_grade_relative_loop():
    """route_intervals: grade_ref + grade_offset resolves correctly."""
    us = _make_user_state(grades={"lead_max_os": "7c"})

    day = _day_with_instance("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -2})
    day = inject_targets(day, us)
    s = day["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"Suggested grade: {s.get('suggested_grade')}")
    # "7c" → upper "7C" → step_grade("7C", -2) → "7A"
    assert s["suggested_grade"] == "7A"


# ─── B6: ARC training grade ──────────────────────────────────────────────────

def test_e2e_arc_training_grade():
    """ARC training: lead_max_os 8a, offset -4 → 6C."""
    us = _make_user_state(grades={"lead_max_os": "8a"})

    day = _day_with_instance("arc_training", {"grade_ref": "lead_max_os", "grade_offset": -4})
    day = inject_targets(day, us)
    s = day["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"Suggested grade: {s.get('suggested_grade')}")
    # "8a" → "8A" (idx=9), -4 → idx=5 → "6C"
    assert s["suggested_grade"] == "6C"


# ─── B7: grade offset table ──────────────────────────────────────────────────

def test_e2e_grade_offset_table():
    """Verify step_grade across a range of offsets from 8B."""
    expected = {0: "8B", -1: "8A", -2: "7C", -3: "7B", -4: "7A", -5: "6C"}
    for offset, grade in expected.items():
        result = step_grade("8B", offset)
        print(f"step_grade('8B', {offset}) = {result}")
        assert result == grade, f"offset {offset}: expected {grade}, got {result}"


# ─── B8: grade_ref with "+" modifier ─────────────────────────────────────────

def test_e2e_grade_ref_with_plus():
    """step_grade strips '+' before applying offset."""
    us = _make_user_state(grades={"lead_max_os": "7c+"})

    day = _day_with_instance("route_intervals", {"grade_ref": "lead_max_os", "grade_offset": -2})
    day = inject_targets(day, us)
    s = day["sessions"][0]["exercise_instances"][0]["suggested"]
    print(f"Suggested grade: {s.get('suggested_grade')}")
    # "7c+" → upper "7C+" → step_grade strips "+" → "7C", offset -2 → "7A"
    assert s["suggested_grade"] == "7A"
    assert "+" not in s["suggested_grade"]
