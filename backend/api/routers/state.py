"""State router — GET / PUT / DELETE /api/state."""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.deps import (
    EMPTY_TEMPLATE, build_current_level, ensure_monday, get_user_id,
    invalidate_future_week_cache, load_state, save_state,
)
from backend.api.rate_limit import limiter
from backend.engine import storage
from backend.engine.grade_mapping import map_grade_for_discipline_change
from backend.engine.state_checks import is_macrocycle_stale

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/state", tags=["state"])


def _deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *patch* into *base* (mutates base)."""
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


@router.get("")
def get_state(user_id: Optional[str] = Depends(get_user_id)):
    """Return the full user_state.json."""
    return load_state(user_id)


# B165d: Keys the frontend/engine are allowed to set via PUT /api/state
_ALLOWED_STATE_KEYS = {
    "profile", "assessment", "goal", "availability", "equipment",
    "baselines", "macrocycle", "current_week_plan", "week_plans",
    "outdoor_spots", "planning_prefs", "preferences", "limitations",
    "trips", "working_loads", "free_sessions", "weekly_overrides",
    "schema_version", "feedback_log", "session_completion_log",
    "outdoor_log", "fatigue_proxy", "stimulus_recency",
    "quote_history", "progression_counters", "test_queue",
    "other_activities", "_prev_week_plan",
    "user", "progression_config",
    # B270: allow Settings to keep the engine-facing bodyweight copies in sync
    # with assessment.body (progression/resolver read these, not assessment.body).
    "body", "bodyweight_kg",
}


@router.put("")
@limiter.limit("30/minute")
def put_state(request: Request, patch: Dict[str, Any], user_id: Optional[str] = Depends(get_user_id)):
    """Deep-merge patch into existing state."""
    # B165d: reject unknown top-level keys
    unknown = set(patch.keys()) - _ALLOWED_STATE_KEYS
    if unknown:
        logger.warning("PUT /api/state rejected unknown keys: %s (user=%s)", unknown, user_id)
        raise HTTPException(
            status_code=422,
            detail=f"Unknown state keys: {', '.join(sorted(unknown))}",
        )
    # Auto-correct macrocycle.start_date to Monday if present in patch
    mc_patch = patch.get("macrocycle")
    if isinstance(mc_patch, dict) and "start_date" in mc_patch:
        mc_patch["start_date"] = ensure_monday(mc_patch["start_date"])
    state = load_state(user_id)
    # A-NEW-MACRO / D232: when goal.discipline flips, remap target_grade so the
    # assessment + macrocycle generators see a grade in the new convention.
    # The mapping helper is identity for unchanged disciplines.
    goal_patch = patch.get("goal")
    if isinstance(goal_patch, dict) and "discipline" in goal_patch:
        old_discipline = (state.get("goal") or {}).get("discipline")
        new_discipline = goal_patch["discipline"]
        if old_discipline and old_discipline != new_discipline:
            existing_target = (state.get("goal") or {}).get("target_grade")
            patched_target = goal_patch.get("target_grade")
            # Only remap if caller did not already supply a fresh target_grade.
            if existing_target and "target_grade" not in goal_patch:
                goal_patch["target_grade"] = map_grade_for_discipline_change(
                    existing_target, old_discipline, new_discipline,
                )
                logger.info(
                    "PUT /api/state: remapped target_grade %s (%s) → %s (%s)",
                    existing_target, old_discipline,
                    goal_patch["target_grade"], new_discipline,
                )
            # Same for current_grade — keeps the user level coherent post-switch.
            existing_current = (state.get("goal") or {}).get("current_grade")
            if existing_current and "current_grade" not in goal_patch:
                goal_patch["current_grade"] = map_grade_for_discipline_change(
                    existing_current, old_discipline, new_discipline,
                )
            # Drop a stale target_boulder_grade when leaving boulder behind.
            if old_discipline == "boulder" and new_discipline not in ("boulder", "both"):
                if (state.get("goal") or {}).get("target_boulder_grade"):
                    goal_patch.setdefault("target_boulder_grade", None)
            # When entering boulder, mirror target_grade into target_boulder_grade
            # so onboarding-style consumers find the original boulder pick.
            if new_discipline == "boulder" and "target_boulder_grade" not in goal_patch:
                goal_patch["target_boulder_grade"] = goal_patch.get(
                    "target_grade", existing_target,
                )
    _deep_merge(state, patch)
    # B272: grade edits must refresh performance.current_level — progression
    # benchmarks (e.g. kilter fallback on current_level.boulder.worked.grade)
    # read it, and "performance" is deliberately NOT PUT-able, so without this
    # rebuild it stays frozen at the onboarding-era grades forever.
    # A271: a test scalar arriving through this endpoint was typed by a human —
    # it is the settings assessment editor, the only client that patches
    # `assessment.tests`. It never stamped `tests_source`, so every manual edit
    # produced a measured number with no provenance, and A269's sidecar decayed
    # a little each time someone corrected their max hang. `m003` catches it on
    # the next read, but the honest place to record it is where it is written.
    asmt_patch = patch.get("assessment")
    if isinstance(asmt_patch, dict) and isinstance(asmt_patch.get("tests"), dict):
        from backend.engine.migrations.m003_backfill_tests_source_from_values import (
            _TEST_KEYS,
        )

        assessment = state.setdefault("assessment", {})
        source = assessment.get("tests_source")
        if not isinstance(source, dict):
            source = {}
        for key, value in asmt_patch["tests"].items():
            if key in _TEST_KEYS and value not in (None, ""):
                source[key] = "measured"
        assessment["tests_source"] = source

    if isinstance(asmt_patch, dict) and isinstance(asmt_patch.get("grades"), dict):
        merged_grades = (state.get("assessment") or {}).get("grades") or {}
        rebuilt = build_current_level(merged_grades)
        performance = state.get("performance") or {}
        current_level = performance.get("current_level") or {}
        # Replace only the grade-derived branches; keep gym_reference & co.
        for branch in ("sport", "boulder"):
            current_level.pop(branch, None)
            if branch in rebuilt:
                current_level[branch] = rebuilt[branch]
        current_level["updated_at"] = date.today().isoformat()
        performance["current_level"] = current_level
        state["performance"] = performance
    # B151: availability change → invalidate future week cache so they
    # regenerate with the new slots.  Current week is handled by the
    # frontend via GET /api/week/0?force=true.
    if "availability" in patch:
        invalidate_future_week_cache(state)
    save_state(state, user_id)
    return state


@router.get("/status")
def get_state_status(user_id: Optional[str] = Depends(get_user_id)):
    """Lightweight consistency check — no mutations."""
    state = load_state(user_id)
    return {"is_macrocycle_stale": is_macrocycle_stale(state)}


def _clear_outdoor_logs(user_id: Optional[str]) -> int:
    """Remove all outdoor JSONL log files for the user. Returns count removed."""
    return storage.delete_all_outdoor_logs(user_id)


@router.delete("")
def delete_state(user_id: Optional[str] = Depends(get_user_id)):
    """Reset state to minimal empty template and clear outdoor logs."""
    state = deepcopy(EMPTY_TEMPLATE)
    save_state(state, user_id)
    _clear_outdoor_logs(user_id)
    return {"status": "reset", "state": state}
