"""B192: Undo session must clear stale feedback artifacts from session.

Root cause: `mark_planned` in replanner_v1.py only cleared `status`. The
fields populated at feedback submit (`actual_exercises`,
`feedback_summary`, `exercise_feedback`, `session_duration_seconds`)
stayed on the session, producing ghost "OK" pills + "Completed · ~NN min"
text after undo.

Secondary cause: `_attach_feedback` in week.py had no status gate, so it
re-hydrated 3 of the 4 fields on every `GET /api/week` from
`feedback_log` (which is genuinely append-only). Without the gate, the
pop in mark_planned would have been undone on the next fetch.

Tests T1..T7 spec'd in B192 Phase 1 analysis.

NOT reverted on purpose (trade-off accepted):
- `working_loads.entries[*].next_external_load_kg` mutations from
  progression_v1.apply_feedback (closed-loop adaptation).
- `feedback_log` (append-only).
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.engine.replanner_v1 import apply_events

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STATE_PATH = REPO_ROOT / "backend" / "tests" / "fixtures" / "test_user_state.json"


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    tmp_state = tmp_path / "user_state.json"
    if REAL_STATE_PATH.exists():
        shutil.copy2(REAL_STATE_PATH, tmp_state)
    else:
        tmp_state.write_text(json.dumps(deps.EMPTY_TEMPLATE, indent=2))
    from backend.engine import storage
    monkeypatch.setattr(storage, "STATE_PATH", tmp_state)
    monkeypatch.setattr(deps, "STATE_PATH", tmp_state)
    yield tmp_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FEEDBACK_FIELDS = (
    "actual_exercises",
    "feedback_summary",
    "exercise_feedback",
    "session_duration_seconds",
)


def _minimal_plan(start_date: str = "2030-01-07") -> dict:
    """Single-day plan with one session. Uses a far-future date for T1/T5/T6/T7
    so the fixture is insulated from "today" drift."""
    start = date.fromisoformat(start_date)
    days = []
    for i in range(7):
        day_iso = (start + timedelta(days=i)).isoformat()
        entry = {
            "date": day_iso,
            "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][i],
            "sessions": [],
        }
        if i == 0:
            entry["sessions"].append({
                "session_id": "strength_long",
                "slot": "evening",
                "resolved": {"resolved_session": {"exercise_instances": []}},
            })
        days.append(entry)
    return {"start_date": start_date, "weeks": [{"phase": "base", "days": days}]}


def _add_done_with_feedback(plan: dict) -> dict:
    """Simulate post-feedback state: status=done + all 4 leak fields populated."""
    p = deepcopy(plan)
    sess = p["weeks"][0]["days"][0]["sessions"][0]
    sess["status"] = "done"
    sess["actual_exercises"] = [
        {"exercise_id": "deadhang_20mm", "feedback": "ok"},
    ]
    sess["feedback_summary"] = "hard"
    sess["exercise_feedback"] = {"deadhang_20mm": "hard"}
    sess["session_duration_seconds"] = 5400
    p["weeks"][0]["days"][0]["status"] = "done"
    return p


# ---------------------------------------------------------------------------
# T1 — mark_planned pops all 4 feedback-derived fields (unit, on apply_events)
# ---------------------------------------------------------------------------

def test_T1_mark_planned_pops_all_feedback_fields():
    plan = _add_done_with_feedback(_minimal_plan())
    sess = plan["weeks"][0]["days"][0]["sessions"][0]
    assert sess["status"] == "done"
    for k in FEEDBACK_FIELDS:
        assert k in sess, f"precondition failed: {k} must be present before undo"

    restored = apply_events(
        plan,
        [{
            "event_type": "mark_planned",
            "date": plan["weeks"][0]["days"][0]["date"],
            "slot": "evening",
            "session_ref": "strength_long",
        }],
    )

    restored_sess = restored["weeks"][0]["days"][0]["sessions"][0]
    assert "status" not in restored_sess
    for k in FEEDBACK_FIELDS:
        assert k not in restored_sess, f"B192 leak: {k} survived mark_planned"
    assert "status" not in restored["weeks"][0]["days"][0]


# ---------------------------------------------------------------------------
# T2 — end-to-end: submit feedback → GET /api/week → undo → GET /api/week again
#      confirms BOTH the pop (mark_planned) AND the _attach_feedback gate.
# ---------------------------------------------------------------------------

def test_T2_end_to_end_undo_clears_ui_fields_across_fetches():
    # GET /api/week/0 to populate current_week_plan if empty
    r = client.get("/api/week/0")
    assert r.status_code == 200, r.text
    week_plan = r.json()["week_plan"]

    # Find a day with sessions
    target_day = next(
        (d for wk in week_plan["weeks"] for d in wk["days"] if d.get("sessions")),
        None,
    )
    assert target_day is not None, "no session in generated week plan"
    target_session = target_day["sessions"][0]
    target_date = target_day["date"]
    target_sid = target_session["session_id"]

    # 1. Submit feedback (atomic: mark_done + progression + append feedback_log)
    feedback_payload = {
        "log_entry": {
            "date": target_date,
            "session_id": target_sid,
            "session_duration_seconds": 5100,
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "deadhang_20mm", "feedback": "hard"},
                ],
            },
        },
        "resolved_day": {"date": target_date, "sessions": [target_session]},
        "status": "done",
    }
    r = client.post("/api/feedback", json=feedback_payload)
    assert r.status_code == 200, r.text

    # 2. GET /api/week/0 to confirm leak fields are present (via _attach_feedback
    #    for feedback_summary/exercise_feedback/session_duration_seconds, and
    #    via feedback router direct write for actual_exercises)
    r = client.get("/api/week/0")
    assert r.status_code == 200, r.text
    wp2 = r.json()["week_plan"]
    done_sess = next(
        s for wk in wp2["weeks"] for d in wk["days"]
        if d["date"] == target_date for s in d["sessions"]
        if s["session_id"] == target_sid
    )
    assert done_sess.get("status") == "done"
    # At least one of the 4 fields should be set post-feedback (sanity)
    assert done_sess.get("feedback_summary") is not None
    assert done_sess.get("session_duration_seconds") in (5100, None) or done_sess["session_duration_seconds"] == 5100

    # 3. Undo via /api/replanner/events
    r = client.post("/api/replanner/events", json={
        "week_plan": wp2,
        "events": [{
            "event_type": "mark_planned",
            "date": target_date,
            "slot": target_session["slot"],
            "session_ref": target_sid,
        }],
    })
    assert r.status_code == 200, r.text

    # 4. GET /api/week/0 again — the critical test for the _attach_feedback gate
    r = client.get("/api/week/0")
    assert r.status_code == 200, r.text
    wp3 = r.json()["week_plan"]
    restored_sess = next(
        s for wk in wp3["weeks"] for d in wk["days"]
        if d["date"] == target_date for s in d["sessions"]
        if s["session_id"] == target_sid
    )
    assert restored_sess.get("status") != "done"
    for k in FEEDBACK_FIELDS:
        assert k not in restored_sess, (
            f"B192 regression: {k} present after undo+refetch "
            f"(value={restored_sess.get(k)!r})"
        )


# ---------------------------------------------------------------------------
# T3 — undo preserves feedback_log (genuinely append-only)
# ---------------------------------------------------------------------------

def test_T3_undo_preserves_feedback_log():
    r = client.get("/api/week/0")
    assert r.status_code == 200
    week_plan = r.json()["week_plan"]
    target_day = next(d for wk in week_plan["weeks"] for d in wk["days"] if d.get("sessions"))
    target_session = target_day["sessions"][0]

    # Submit feedback
    r = client.post("/api/feedback", json={
        "log_entry": {
            "date": target_day["date"],
            "session_id": target_session["session_id"],
            "session_duration_seconds": 3600,
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "deadhang_20mm", "feedback": "ok"},
                ],
            },
        },
        "resolved_day": {"date": target_day["date"], "sessions": [target_session]},
        "status": "done",
    })
    assert r.status_code == 200

    # feedback_log should have our entry
    state = deps.load_state(None)
    fb_log_before = state.get("feedback_log", [])
    matching_before = [
        e for e in fb_log_before
        if e.get("date") == target_day["date"] and e.get("session_id") == target_session["session_id"]
    ]
    assert len(matching_before) == 1, f"feedback_log missing entry, got: {fb_log_before}"

    # Undo
    r = client.get("/api/week/0")
    wp2 = r.json()["week_plan"]
    r = client.post("/api/replanner/events", json={
        "week_plan": wp2,
        "events": [{
            "event_type": "mark_planned",
            "date": target_day["date"],
            "slot": target_session["slot"],
            "session_ref": target_session["session_id"],
        }],
    })
    assert r.status_code == 200

    # feedback_log entry still there
    state_after = deps.load_state(None)
    fb_log_after = state_after.get("feedback_log", [])
    matching_after = [
        e for e in fb_log_after
        if e.get("date") == target_day["date"] and e.get("session_id") == target_session["session_id"]
    ]
    assert len(matching_after) == 1, "feedback_log entry was removed (append-only contract violated)"


# ---------------------------------------------------------------------------
# T4 — undo preserves working_loads mutations (closed-loop NOT reverted)
# ---------------------------------------------------------------------------

def test_T4_undo_preserves_working_loads_mutation():
    # Seed a known working_loads entry
    state = deps.load_state(None)
    state.setdefault("working_loads", {})
    state["working_loads"]["deadhang_20mm"] = {
        "next_external_load_kg": 12.5,
        "last_feedback": "ok",
    }
    deps.save_state(state, None)

    # Feedback loop will normally mutate working_loads on hard/very_hard
    r = client.get("/api/week/0")
    week_plan = r.json()["week_plan"]
    target_day = next(d for wk in week_plan["weeks"] for d in wk["days"] if d.get("sessions"))
    target_session = target_day["sessions"][0]

    r = client.post("/api/feedback", json={
        "log_entry": {
            "date": target_day["date"],
            "session_id": target_session["session_id"],
            "actual": {
                "exercise_feedback_v1": [
                    {"exercise_id": "deadhang_20mm", "feedback": "very_hard"},
                ],
            },
        },
        "resolved_day": {"date": target_day["date"], "sessions": [target_session]},
        "status": "done",
    })
    assert r.status_code == 200

    wl_post_feedback = deps.load_state(None).get("working_loads", {})
    post_feedback_snapshot = deepcopy(wl_post_feedback)

    # Undo
    r = client.get("/api/week/0")
    wp2 = r.json()["week_plan"]
    r = client.post("/api/replanner/events", json={
        "week_plan": wp2,
        "events": [{
            "event_type": "mark_planned",
            "date": target_day["date"],
            "slot": target_session["slot"],
            "session_ref": target_session["session_id"],
        }],
    })
    assert r.status_code == 200

    # working_loads should be identical post-undo (closed-loop NOT reverted)
    wl_after_undo = deps.load_state(None).get("working_loads", {})
    assert wl_after_undo == post_feedback_snapshot, (
        "B192 contract violation: undo reverted working_loads (closed-loop "
        "must be immutable against undo)"
    )


# ---------------------------------------------------------------------------
# T5 — undo → redo (mark_done) — no ghost from prior feedback contaminates
#      the fresh completion. New feedback submit will refill as expected,
#      but between undo and the NEXT feedback the session must be pristine.
# ---------------------------------------------------------------------------

def test_T5_undo_then_redo_no_ghost_contamination():
    plan = _add_done_with_feedback(_minimal_plan())
    target_date = plan["weeks"][0]["days"][0]["date"]

    # Undo
    after_undo = apply_events(
        plan,
        [{"event_type": "mark_planned", "date": target_date, "slot": "evening", "session_ref": "strength_long"}],
    )
    undone_sess = after_undo["weeks"][0]["days"][0]["sessions"][0]
    for k in FEEDBACK_FIELDS:
        assert k not in undone_sess

    # Redo (mark_done) — should NOT resurrect old fields
    after_redo = apply_events(
        after_undo,
        [{"event_type": "mark_done", "date": target_date, "slot": "evening", "session_ref": "strength_long"}],
    )
    redone_sess = after_redo["weeks"][0]["days"][0]["sessions"][0]
    assert redone_sess["status"] == "done"
    for k in FEEDBACK_FIELDS:
        assert k not in redone_sess, (
            f"ghost leak: {k} resurfaced after undo→redo (value={redone_sess.get(k)!r})"
        )


# ---------------------------------------------------------------------------
# T6 — idempotence: undo × 3 = undo × 1 (byte-identical)
# ---------------------------------------------------------------------------

def test_T6_undo_is_idempotent():
    plan = _add_done_with_feedback(_minimal_plan())
    target_date = plan["weeks"][0]["days"][0]["date"]
    event = {
        "event_type": "mark_planned",
        "date": target_date,
        "slot": "evening",
        "session_ref": "strength_long",
    }

    once = apply_events(plan, [event])
    thrice = apply_events(apply_events(apply_events(plan, [event]), [event]), [event])

    # apply_events logs each call in plan["adaptations"] + bumps plan_revision,
    # so plan-wide equality doesn't hold. Idempotence is asserted at session
    # level: the target session must be byte-identical after 1× vs 3× undo.
    once_sess = once["weeks"][0]["days"][0]["sessions"][0]
    thrice_sess = thrice["weeks"][0]["days"][0]["sessions"][0]
    assert json.dumps(once_sess, sort_keys=True) == json.dumps(thrice_sess, sort_keys=True), (
        "mark_planned is not idempotent at session level (3x ≠ 1x)"
    )
    once_day = {k: v for k, v in once["weeks"][0]["days"][0].items() if k != "sessions"}
    thrice_day = {k: v for k, v in thrice["weeks"][0]["days"][0].items() if k != "sessions"}
    assert json.dumps(once_day, sort_keys=True) == json.dumps(thrice_day, sort_keys=True), (
        "mark_planned is not idempotent at day level (3x ≠ 1x)"
    )


# ---------------------------------------------------------------------------
# T7 — past-date / missing-session: no-op with logger.warning (no raise,
#      no state mutation). Preserves frontend contract.
# ---------------------------------------------------------------------------

def test_T7_mark_planned_no_op_on_unknown_session(caplog):
    plan = _minimal_plan()
    target_date = plan["weeks"][0]["days"][0]["date"]
    baseline = json.dumps(plan, sort_keys=True)

    import logging
    with caplog.at_level(logging.WARNING, logger="backend.engine.replanner_v1"):
        updated = apply_events(
            plan,
            [{
                "event_type": "mark_planned",
                "date": target_date,
                "slot": "evening",
                "session_ref": "__nonexistent_session__",
            }],
        )

    # State shape preserved (no raise, no silent drift)
    # Allow day-status clear (no done/skipped sessions ⇒ day status popped)
    target_day = updated["weeks"][0]["days"][0]
    assert "status" not in target_day
    # No session was modified
    sess = target_day["sessions"][0]
    assert sess.get("session_id") == "strength_long"
    assert "status" not in sess
    for k in FEEDBACK_FIELDS:
        assert k not in sess

    # Warning emitted for traceability (B216 lesson: never silent-swallow)
    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("mark_planned no-op" in m for m in warning_messages), (
        f"expected 'mark_planned no-op' warning, got: {warning_messages}"
    )
