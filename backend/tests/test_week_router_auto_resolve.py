"""B-fix-CORE Patch A: _auto_resolve must inject target_date so working_loads
are honored end-to-end.

Builds a synthetic week_plan with one day containing prehab_maintenance, then
runs `_auto_resolve` directly. Asserts the resolved instance for
elbow_eccentric_curl carries the working_loads value (5.0), not the FIXED_KG
fallback (1.5).

Pre-fix (no target_date in resolve context): the resolved suggested_external_load_kg
would equal EXTERNAL_LOAD_FALLBACK_FIXED_KG['elbow_eccentric_curl'] = 1.5.
Post-fix: the resolved value equals working_loads.next_external_load_kg = 5.0.
"""
from __future__ import annotations

from pathlib import Path

from backend.api.routers.week import _auto_resolve
from backend.engine.progression_v1 import EXTERNAL_LOAD_FALLBACK_FIXED_KG

EX_ID = "elbow_eccentric_curl"
WL_NEXT_KG = 5.0
TARGET_DATE = "2026-05-04"
UPDATED_AT = "2026-04-30"


def _build_state() -> dict:
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
        "working_loads": {
            "entries": [
                {
                    "exercise_id": EX_ID,
                    "key": EX_ID,
                    "setup": {},
                    "last_external_load_kg": WL_NEXT_KG,
                    "next_external_load_kg": WL_NEXT_KG,
                    "last_feedback_label": "ok",
                    "last_completed": True,
                    "updated_at": UPDATED_AT,
                }
            ],
            "rules": {},
        },
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


def test_auto_resolve_honors_working_loads_via_target_date_injection():
    """End-to-end: _auto_resolve injects target_date → working_loads visible."""
    state = _build_state()
    week_plan = _build_week_plan()

    _auto_resolve(week_plan, state, user_id="test-uuid", phase="power_endurance")

    load = _find_load(week_plan, EX_ID)
    fallback = EXTERNAL_LOAD_FALLBACK_FIXED_KG[EX_ID]
    assert load == WL_NEXT_KG, (
        f"_auto_resolve must surface working_loads.next ({WL_NEXT_KG}) "
        f"after injecting target_date={TARGET_DATE}; got {load}. "
        f"FIXED_KG fallback (pre-fix value) would be {fallback}."
    )


def test_auto_resolve_stale_entry_falls_back():
    """Same path with a stale entry (>60d) must reach FIXED_KG fallback."""
    state = _build_state()
    # Move updated_at to >60 days before TARGET_DATE
    state["working_loads"]["entries"][0]["updated_at"] = "2025-12-01"
    week_plan = _build_week_plan()

    _auto_resolve(week_plan, state, user_id="test-uuid", phase="power_endurance")

    load = _find_load(week_plan, EX_ID)
    fallback = EXTERNAL_LOAD_FALLBACK_FIXED_KG[EX_ID]
    assert load == fallback, (
        f"Stale entry must hit FIXED_KG[{fallback}], got {load}"
    )
