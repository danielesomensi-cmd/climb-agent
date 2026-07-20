"""B-fix-CORE Patch A: _auto_resolve must inject target_date so working_loads
are honored end-to-end.

Builds a synthetic week_plan with one day containing prehab_maintenance, then
runs `_auto_resolve` directly. Asserts the resolved instance for the selected
external_load exercise carries the working_loads value (5.0), not the FIXED_KG
fallback.

B274 note: selection inside prehab blocks rotates weekly (variety tie-break),
so this test no longer hardcodes WHICH exercise gets picked. It runs
_auto_resolve once to discover the selected external_load exercise, then
attaches the working_loads entry to that id and re-runs (discover-then-assert)
— the intent under test is target_date injection, not the tie-break winner.
"""
from __future__ import annotations

from pathlib import Path

from backend.api.routers.week import _auto_resolve
from backend.engine.progression_v1 import EXTERNAL_LOAD_FALLBACK_FIXED_KG

WL_NEXT_KG = 5.0
TARGET_DATE = "2026-05-04"
UPDATED_AT = "2026-04-30"


def _build_state(wl_ex_id: str | None = None, updated_at: str = UPDATED_AT) -> dict:
    entries = []
    if wl_ex_id:
        entries.append(
            {
                "exercise_id": wl_ex_id,
                "key": wl_ex_id,
                "setup": {},
                "last_external_load_kg": WL_NEXT_KG,
                "next_external_load_kg": WL_NEXT_KG,
                "last_feedback_label": "ok",
                "last_completed": True,
                "updated_at": updated_at,
            }
        )
    return {
        "schema_version": "1.4",
        "bodyweight_kg": 70.0,
        "baselines": {"hangboard": [{"max_total_load_kg": 95.0}]},
        "assessment": {
            "grades": {
                "boulder_max_os": "6C",
                "boulder_max_rp": "7A",
                "lead_max_rp": "7a",
            },
        },
        "equipment": {"home": ["weight"], "gyms": []},
        "working_loads": {"entries": entries, "rules": {}},
    }


def _build_week_plan() -> dict:
    """Synthetic week_plan with one day, one session (prehab_maintenance)."""
    return {
        "start_date": TARGET_DATE,
        "weeks": [
            {
                "week_num": 0,
                "days": [
                    {
                        "date": TARGET_DATE,
                        "sessions": [
                            {
                                "session_id": "prehab_maintenance",
                                "location": "home",
                                "gym_id": None,
                                "status": "pending",
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _find_load(week_plan: dict, exercise_id: str) -> float | None:
    for wb in week_plan.get("weeks", []):
        for day in wb.get("days", []):
            for sess in day.get("sessions", []):
                resolved = sess.get("resolved") or {}
                rs = resolved.get("resolved_session", {})
                for inst in rs.get("exercise_instances", []):
                    if inst.get("exercise_id") == exercise_id:
                        return (inst.get("suggested") or {}).get("suggested_external_load_kg")
    return None


def _discover_loadable_ex() -> str:
    """Run _auto_resolve without working_loads and return the selected
    exercise that has a FIXED_KG fallback (external_load). Selection is
    independent of working_loads, so re-running with the same date and state
    picks the same exercise."""
    week_plan = _build_week_plan()
    _auto_resolve(week_plan, _build_state(), user_id="test-uuid", phase="power_endurance")
    for wb in week_plan.get("weeks", []):
        for day in wb.get("days", []):
            for sess in day.get("sessions", []):
                rs = (sess.get("resolved") or {}).get("resolved_session", {})
                for inst in rs.get("exercise_instances", []):
                    eid = inst.get("exercise_id")
                    if eid in EXTERNAL_LOAD_FALLBACK_FIXED_KG:
                        return eid
    raise AssertionError(
        "prehab_maintenance selected no external_load exercise — fixture broken"
    )


def test_auto_resolve_honors_working_loads_via_target_date_injection():
    """End-to-end: _auto_resolve injects target_date → working_loads visible."""
    ex_id = _discover_loadable_ex()
    state = _build_state(wl_ex_id=ex_id)
    week_plan = _build_week_plan()

    _auto_resolve(week_plan, state, user_id="test-uuid", phase="power_endurance")

    load = _find_load(week_plan, ex_id)
    fallback = EXTERNAL_LOAD_FALLBACK_FIXED_KG[ex_id]
    assert load == WL_NEXT_KG, (
        f"_auto_resolve must surface working_loads.next ({WL_NEXT_KG}) "
        f"after injecting target_date={TARGET_DATE}; got {load}. "
        f"FIXED_KG fallback (pre-fix value) would be {fallback}."
    )


def test_auto_resolve_months_old_entry_survives():
    """B288: months-old external_load memory survives through the auto-resolve path.

    Was asserting the opposite (>60d → FIXED_KG). See
    test_resolve_session_freshness.test_months_old_working_loads_survives for
    the rationale; this pins the same behaviour through week.py's _auto_resolve,
    the path that actually builds what /today renders.
    """
    ex_id = _discover_loadable_ex()
    state = _build_state(wl_ex_id=ex_id, updated_at="2025-12-01")
    week_plan = _build_week_plan()

    _auto_resolve(week_plan, state, user_id="test-uuid", phase="power_endurance")

    load = _find_load(week_plan, ex_id)
    assert load == WL_NEXT_KG, (
        f"Months-old entry must surface working_loads ({WL_NEXT_KG}), got {load}"
    )
