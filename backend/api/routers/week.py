"""Week router — generate a week plan from macrocycle context."""

from __future__ import annotations

import logging
import os
from copy import deepcopy
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from backend.api.deps import (
    REPO_ROOT,
    current_phase_and_week,
    load_state,
    save_state,
    week_num_to_phase_context,
)
from backend.engine.macrocycle_v1 import compute_pretrip_dates
from backend.engine.planner_v2 import generate_phase_week
from backend.engine.replanner_v1 import regenerate_preserving_completed
from backend.engine.resolve_session import resolve_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/week", tags=["week"])

SESSIONS_DIR = "backend/catalog/sessions/v1"
TEMPLATES_DIR = "backend/catalog/templates/v1"
EXERCISES_PATH = "backend/catalog/exercises/v1/exercises.json"


def _auto_resolve(week_plan: dict, state: dict) -> None:
    """Resolve all sessions in a week plan inline."""
    for week_block in week_plan.get("weeks", []):
        for day_entry in week_block.get("days", []):
            for session_entry in day_entry.get("sessions", []):
                session_id = session_entry.get("session_id", "")
                session_path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
                full_path = REPO_ROOT / session_path
                if not full_path.exists():
                    session_entry["resolved"] = None
                    continue
                try:
                    resolve_state = deepcopy(state)
                    resolve_state["context"] = {
                        **resolve_state.get("context", {}),
                        "location": session_entry.get("location", "home"),
                        "gym_id": session_entry.get("gym_id"),
                    }
                    resolved = resolve_session(
                        repo_root=str(REPO_ROOT),
                        session_path=session_path,
                        templates_dir=TEMPLATES_DIR,
                        exercises_path=EXERCISES_PATH,
                        out_path="",
                        user_state_override=resolve_state,
                        write_output=False,
                    )
                    session_entry["resolved"] = resolved
                except Exception:
                    session_entry["resolved"] = None


def _attach_feedback(week_plan: dict, feedback_log: list) -> None:
    """Attach feedback_summary from feedback_log to matching sessions (B32)."""
    if not feedback_log:
        return
    # Index by (date, session_id) for O(1) lookup
    fb_index = {(fb["date"], fb["session_id"]): fb["difficulty"] for fb in feedback_log if fb.get("session_id") != "unknown"}
    for week_block in week_plan.get("weeks", []):
        for day_entry in week_block.get("days", []):
            day_date = day_entry.get("date", "")
            for session_entry in day_entry.get("sessions", []):
                key = (day_date, session_entry.get("session_id", ""))
                if key in fb_index:
                    session_entry["feedback_summary"] = fb_index[key]


def _current_week_num(macrocycle: dict) -> int:
    """Compute the 1-based absolute week number for today."""
    pi, wi = current_phase_and_week(macrocycle)
    phases = macrocycle.get("phases") or []
    cumulative = sum(p.get("duration_weeks", 1) for p in phases[:pi])
    return cumulative + wi + 1


@router.get("/{week_num}")
def get_week(week_num: int, force: bool = False):
    """Generate the plan for a given week (1-based). week_num=0 → current week.

    When force=True and this is the current week, regenerate from scratch but
    preserve any sessions already marked done/skipped.
    """
    state = load_state()
    macrocycle = state.get("macrocycle")
    if not macrocycle:
        raise HTTPException(status_code=422, detail="No macrocycle — generate one first")

    try:
        ctx = week_num_to_phase_context(macrocycle, week_num)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    availability = state.get("availability")
    planning_prefs = state.get("planning_prefs", {})
    equipment = state.get("equipment", {})
    gyms = equipment.get("gyms", [])
    hard_cap = planning_prefs.get("hard_day_cap_per_week", 3)

    # Determine default gym_id (highest priority first)
    default_gym_id = None
    if gyms:
        sorted_gyms = sorted(gyms, key=lambda g: (g.get("priority", 999), g.get("gym_id", "")))
        default_gym_id = sorted_gyms[0].get("gym_id")

    # For the current week, try to use the cached plan from state
    is_current_week = (week_num == 0) or (ctx["week_num"] == _current_week_num(macrocycle))
    week_plan = None

    # Store old plan before force-regeneration
    old_plan = state.get("current_week_plan") if (force and is_current_week) else None

    if is_current_week and not force:
        try:
            cached = state.get("current_week_plan")
            if (
                cached
                and cached.get("start_date") == ctx["start_date"]
                and cached.get("weeks")
                and len(cached["weeks"]) > 0
                and cached["weeks"][0].get("days")
            ):
                week_plan = cached
        except Exception:
            logger.warning("Failed to read cached week plan, regenerating")
            week_plan = None

    if week_plan is None:
        # Compute pre-trip deload dates for this week (5 days before + trip start day)
        week_start = ctx["start_date"]
        week_end_date = datetime.strptime(week_start, "%Y-%m-%d").date() + timedelta(days=6)
        pretrip_dates = compute_pretrip_dates(
            state.get("trips", []), week_start, week_end_date.isoformat()
        )

        try:
            week_plan = generate_phase_week(
                phase_id=ctx["phase_id"],
                domain_weights=ctx["domain_weights"],
                session_pool=ctx["session_pool"],
                start_date=ctx["start_date"],
                availability=availability,
                hard_cap_per_week=hard_cap,
                planning_prefs=planning_prefs,
                default_gym_id=default_gym_id,
                gyms=gyms,
                intensity_cap=ctx.get("intensity_cap"),
                pretrip_dates=pretrip_dates if pretrip_dates else None,
                is_last_week_of_phase=ctx.get("is_last_week_of_phase", False),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Week generation failed: {e}")

        # When force-regenerating, preserve completed sessions from old plan
        if (
            old_plan
            and old_plan.get("start_date") == week_plan.get("start_date")
        ):
            try:
                week_plan = regenerate_preserving_completed(old_plan, week_plan)
            except Exception:
                logger.warning("Failed to preserve completed sessions, using fresh plan")

        # Cache the freshly generated plan for the current week
        if is_current_week:
            state["current_week_plan"] = week_plan
            save_state(state)

    # Auto-resolve each session so the frontend gets exercises inline
    _auto_resolve(week_plan, state)

    # Attach feedback summaries from feedback_log (B32)
    _attach_feedback(week_plan, state.get("feedback_log", []))

    return {
        "week_num": ctx["week_num"],
        "phase_id": ctx["phase_id"],
        "week_plan": week_plan,
    }
