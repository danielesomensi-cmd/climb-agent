"""B346 — the closed loop's dead channels: connected or removed.

D280 found five state fields that were written and never read. Four are handled
here (`freshness_policy` stays open on purpose, tracked in the roadmap):

1. `test_queue` — written by `progression_v1._enqueue_test` after two
   concordant feedbacks on a max hang, read ONLY by `planner_v1`, which no
   module imports. The engine's single self-correction mechanism wrote into a
   channel with no outlet. Now consumed by `planner_v2` PASS 3, and pruned once
   the test is actually done.
2. `stimulus_recency` / `fatigue_proxy` — the only writer sat behind
   `if req.resolved_day` in POST /api/feedback, a field no client sends. Both
   were `{}` in production after 98 completed sessions. Now written from
   mark_done / mark_skipped.
3. `recent_sessions` — initialised in two places, written by nothing, read by
   two callers who therefore always saw `[]`. Removed; the readers now use the
   real source (completed sessions in `week_plans`).
4. `deload_factor` — written by three modules, read by none. Removed.
"""

import pytest

from backend.engine.planner_v2 import generate_phase_week
from backend.engine.progression_v1 import _prune_test_queue, apply_feedback
from backend.engine.closed_loop_v1 import apply_day_result_to_user_state


# ─── 1. test_queue → PASS 3 ──────────────────────────────────────────────────

def _planner_kwargs(**over):
    kwargs = dict(
        phase_id="power_endurance",   # a phase whose gate would normally skip a finger test
        domain_weights={"finger_strength": 0.2, "power_endurance": 0.3, "technique": 0.2,
                        "volume_climbing": 0.2, "pulling_strength": 0.05, "core_prehab": 0.05},
        # Deliberately WITHOUT test_* sessions: they must reach the plan only
        # through PASS 3, otherwise these tests would pass for the wrong reason
        # (PASS 1 placing a test session straight out of the pool).
        session_pool=["power_endurance_gym", "prehab_maintenance", "finger_strength_home",
                      "route_endurance_gym", "technique_focus_gym", "flexibility_full"],
        start_date="2026-09-07",
        availability={d: {"evening": {"available": True, "preferred_location": "home"}}
                      for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        home_equipment=["hangboard", "pullup_bar", "dumbbell"],
        allowed_locations=["home"],
    )
    kwargs.update(over)
    return kwargs


def _queue(test_id="max_hang_7s_total_load", by="2026-09-10", created="2026-09-03"):
    return [{"test_id": test_id, "recommended_by_date": by,
             "reason": "two_recent_hard_feedback_on_max_hang", "created_at": created}]


def _session_ids(plan):
    return [s.get("session_id")
            for d in plan["weeks"][0]["days"] for s in (d.get("sessions") or [])]


def test_queued_retest_is_placed_despite_the_phase_gate():
    """power_endurance does not target the finger axis — the queue overrides that."""
    plan = generate_phase_week(**_planner_kwargs(test_queue=_queue()))
    assert "test_max_hang_7s" in _session_ids(plan)


def test_no_queue_means_no_test_placed():
    """The baseline this brief must not disturb: an empty queue changes nothing."""
    plan = generate_phase_week(**_planner_kwargs())
    assert "test_max_hang_7s" not in _session_ids(plan)
    plan_empty = generate_phase_week(**_planner_kwargs(test_queue=[]))
    assert _session_ids(plan_empty) == _session_ids(plan)


def test_queue_entry_due_after_this_week_is_not_placed():
    plan = generate_phase_week(**_planner_kwargs(test_queue=_queue(by="2026-10-30")))
    assert "test_max_hang_7s" not in _session_ids(plan)


def test_queued_retest_still_respects_the_freshness_gate():
    """The phase gate is bypassed; the 42-day window is NOT.

    This is what stops a queue entry from re-placing the same test every week.
    """
    plan = generate_phase_week(**_planner_kwargs(
        test_queue=_queue(),
        recent_test_dates={"finger": "2026-09-01"},   # 6 days before the week
    ))
    assert "test_max_hang_7s" not in _session_ids(plan)


def test_unknown_test_id_in_queue_is_ignored():
    plan = generate_phase_week(**_planner_kwargs(test_queue=_queue(test_id="not_a_test")))
    assert "test_max_hang_7s" not in _session_ids(plan)


def test_planner_output_is_deterministic_with_a_queue():
    kwargs = _planner_kwargs(test_queue=_queue())
    assert generate_phase_week(**kwargs) == generate_phase_week(**kwargs)


# ─── 1b. queue pruning ───────────────────────────────────────────────────────

def test_queue_entry_is_pruned_once_the_test_is_done():
    state = {
        "test_queue": _queue(),
        "tests": {"max_strength": [
            {"test_id": "max_hang_7s_total_load", "date": "2026-09-09", "total_load_kg": 120.0},
        ]},
    }
    _prune_test_queue(state)
    assert state["test_queue"] == []


def test_queue_entry_survives_an_older_test():
    """A test done BEFORE the entry was created did not satisfy it."""
    state = {
        "test_queue": _queue(created="2026-09-03"),
        "tests": {"max_strength": [
            {"test_id": "max_hang_7s_total_load", "date": "2026-05-19", "total_load_kg": 122.0},
        ]},
    }
    _prune_test_queue(state)
    assert len(state["test_queue"]) == 1


def test_prune_is_safe_on_empty_and_malformed_state():
    for state in ({}, {"test_queue": []}, {"test_queue": _queue(), "tests": {}},
                  {"test_queue": _queue(), "tests": {"max_strength": "junk"}}):
        _prune_test_queue(state)  # must not raise


def test_apply_feedback_prunes_after_logging_a_test():
    """End-to-end: logging the retest empties the queue that asked for it."""
    state = {
        "bodyweight_kg": 76.0,
        "working_loads": {"entries": [], "rules": {}},
        "test_queue": _queue(created="2026-09-03"),
        "tests": {},
    }
    log = {
        "date": "2026-09-09",
        "planned": [{"session_id": "test_max_hang_7s", "tags": {"test": True}}],
        "actual": {"exercise_feedback_v1": [{
            "exercise_id": "max_hang_7s", "completed": True,
            "feedback_label": "ok", "used_total_load_kg": 118.0,
        }]},
    }
    out = apply_feedback(log, state)
    assert out["test_queue"] == []


# ─── 2. stimulus_recency / fatigue_proxy ─────────────────────────────────────

def test_closed_loop_writer_records_a_finger_session():
    """The writer itself was never broken — nothing reached it. Pin the contract."""
    state = apply_day_result_to_user_state(
        {},
        resolved_day={"date": "2026-09-08", "sessions": [
            {"session_id": "finger_strength_home", "tags": {"hard": True, "finger": True}},
        ]},
        status="done",
    )
    assert state["stimulus_recency"]["finger_strength"]["last_done_date"] == "2026-09-08"
    assert state["fatigue_proxy"]["finger_sessions_total"] == 1
    assert state["fatigue_proxy"]["hard_sessions_total"] == 1


def test_closed_loop_writer_separates_skipped():
    state = apply_day_result_to_user_state(
        {},
        resolved_day={"date": "2026-09-08", "sessions": [
            {"session_id": "finger_strength_home", "tags": {"finger": True}},
        ]},
        status="skipped",
    )
    entry = state["stimulus_recency"]["finger_strength"]
    assert entry["last_skipped_date"] == "2026-09-08"
    assert entry["last_done_date"] is None
    assert state["fatigue_proxy"]["skipped_sessions_total"] == 1


def test_only_the_marked_session_counts_on_a_two_session_day():
    """Marking one session done says nothing about the other one on that day."""
    state = apply_day_result_to_user_state(
        {},
        resolved_day={"date": "2026-09-08", "sessions": [
            {"session_id": "finger_strength_home", "tags": {"hard": True, "finger": True}},
        ]},
        status="done",
    )
    assert state["fatigue_proxy"]["done_sessions_total"] == 1
    # `ensure_planning_defaults` pre-seeds every category, so absence of a key
    # proves nothing — the counters are what must stay at zero.
    assert state["stimulus_recency"].get("endurance", {}).get("done_count", 0) == 0
    assert state["fatigue_proxy"]["endurance_sessions_total"] == 0


# ─── 3 & 4. removed fields ───────────────────────────────────────────────────

def test_recent_sessions_is_not_seeded_into_new_state():
    from backend.api.deps import EMPTY_TEMPLATE

    assert "recent_sessions" not in EMPTY_TEMPLATE


def test_harmonization_note_fires_from_week_plans():
    """It used to read `recent_sessions` and therefore could never fire."""
    from backend.engine.adhoc_builder import _harmonization_note

    state = {"week_plans": {"2026-09-07": {"weeks": [{"days": [
        {"date": "2026-09-08", "sessions": [
            {"session_id": "custom_cs_x", "status": "done", "tags": {"finger": True}},
        ]},
    ]}]}}}
    assert _harmonization_note(state, "2026-09-09") is not None


def test_harmonization_note_ignores_sessions_outside_the_window():
    from backend.engine.adhoc_builder import _harmonization_note

    state = {"week_plans": {"2026-08-01": {"weeks": [{"days": [
        {"date": "2026-08-02", "sessions": [
            {"session_id": "finger_strength_home", "status": "done", "tags": {"finger": True}},
        ]},
    ]}]}}}
    assert _harmonization_note(state, "2026-09-09") is None


def test_harmonization_note_ignores_sessions_that_were_not_done():
    from backend.engine.adhoc_builder import _harmonization_note

    state = {"week_plans": {"2026-09-07": {"weeks": [{"days": [
        {"date": "2026-09-08", "sessions": [
            {"session_id": "finger_strength_home", "status": "planned", "tags": {"finger": True}},
        ]},
    ]}]}}}
    assert _harmonization_note(state, "2026-09-09") is None


@pytest.mark.parametrize("phase", ["deload", "base", "performance"])
def test_deload_factor_is_gone_from_every_phase(phase):
    plan = generate_phase_week(**_planner_kwargs(phase_id=phase))
    assert "deload_factor" not in plan["weeks"][0].get("targets", {})
