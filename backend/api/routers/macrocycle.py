"""Macrocycle router — generate periodized macrocycle."""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import (
    current_phase_and_week,
    ensure_monday,
    get_user_id,
    invalidate_week_cache,
    load_state,
    require_active_subscription,
    this_monday,
    save_state,
)
from backend.api.models import MacrocycleRequest, StartNewCycleRequest
from backend.engine.assessment_v1 import compute_assessment_profile
from backend.engine.grade_mapping import BOULDER_TO_LEAD, map_grade_for_discipline_change
from backend.engine.macrocycle_archive import archive_current_macrocycle
from backend.engine.macrocycle_v1 import compute_new_macrocycle_start_date, generate_macrocycle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/macrocycle", tags=["macrocycle"])


@router.post("/generate")
def generate(req: MacrocycleRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Generate a macrocycle and save it into state.

    When *from_phase* is set, performs incremental regeneration:
    earlier phases are kept intact, remaining phases are regenerated
    with the current assessment profile.
    """
    state = load_state(user_id)

    goal = state.get("goal")
    if not goal:
        raise HTTPException(status_code=422, detail="No goal in state — complete onboarding first")

    profile = (state.get("assessment") or {}).get("profile")
    if not profile:
        raise HTTPException(status_code=422, detail="No assessment profile — run assessment first")

    # Validate goal deadline is not in the past
    deadline = goal.get("deadline")
    if deadline:
        try:
            dl = datetime.strptime(deadline, "%Y-%m-%d").date()
            if dl < date.today():
                raise HTTPException(
                    status_code=400,
                    detail="Goal deadline is in the past. Please update your goal with a future date.",
                )
        except ValueError:
            pass  # Non-standard format, let macrocycle generator handle it

    # --- resolve incremental vs full regen --------------------------------
    from_phase = req.from_phase
    if from_phase:
        old_mc = state.get("macrocycle")
        if not old_mc:
            raise HTTPException(
                status_code=422,
                detail="No existing macrocycle for incremental regen",
            )
        if from_phase == "current":
            pi, _ = current_phase_and_week(old_mc)
            from_phase = old_mc["phases"][pi]["phase_id"]

        start_date = old_mc["start_date"]
        if ensure_monday(start_date) != start_date:
            import logging
            logging.getLogger(__name__).warning(
                "Incremental regen: existing start_date %s is not a Monday", start_date,
            )
            start_date = ensure_monday(start_date)
        total_weeks = old_mc.get("total_weeks", 12)
    else:
        start_date = ensure_monday(req.start_date) if req.start_date else this_monday()
        total_weeks = req.total_weeks

    try:
        macrocycle = generate_macrocycle(
            goal, profile, state, start_date, total_weeks,
            from_phase=from_phase,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Macrocycle generation failed: {e}")

    state["macrocycle"] = macrocycle
    state.pop("initial_tests_requested", None)
    invalidate_week_cache(state)
    save_state(state, user_id)

    return {"macrocycle": macrocycle}


# ---------------------------------------------------------------------------
# A-NEW-MACRO: POST /api/macrocycle/start-new-cycle
# ---------------------------------------------------------------------------

# Total-weeks bounds (engine constraints — A218 / A-MACRO-CAPS).
# Must match macrocycle_v1._MIN_TOTAL_WEEKS_LEAD / _MIN_TOTAL_WEEKS_BOULDER /
# _MAX_TOTAL_WEEKS.
_TOTAL_WEEKS_MIN_LEAD = 11
_TOTAL_WEEKS_MIN_BOULDER = 8
_TOTAL_WEEKS_MAX = 16
_DEFAULT_TOTAL_WEEKS_LEAD = 12
_DEFAULT_TOTAL_WEEKS_BOULDER = 10


def _clear_week_cache_for_new_cycle(state: dict, new_start_date: str) -> None:
    """Invalidate the week cache for the new cycle.

    - ``current_week_plan`` (B216 legacy single-pointer) is always cleared.
    - ``week_plans[]`` entries with key ``< new_start_date`` are preserved
      (history view of past cycles); entries ``>= new_start_date`` are removed
      so the new cycle doesn't inherit stale plans from the old one.
    """
    state["current_week_plan"] = None
    state.pop("_prev_week_plan", None)
    plans = state.get("week_plans") or {}
    state["week_plans"] = {k: v for k, v in plans.items() if k < new_start_date}


@router.post(
    "/start-new-cycle",
    dependencies=[Depends(require_active_subscription)],
)
def start_new_cycle(
    req: StartNewCycleRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Start a fresh macrocycle while preserving all training history.

    A-NEW-MACRO. Differs from ``/api/macrocycle/generate`` in five ways:

    1. Mandatory goal review (``req.goal``) replaces ``state["goal"]``.
    2. Discipline switch is honored end-to-end (target_grade remap, boulder
       grades mirrored into ``target_boulder_grade``).
    3. The previous macrocycle is archived into ``state["macrocycle_history"]``
       BEFORE being overwritten — D232 §11 gap #5.
    4. ``initial_tests_requested = True`` is set AFTER the generate (the standard
       generate handler pops it).
    5. Atomic: all mutations happen on a deep-copy; commit only on success.
    """
    state = load_state(user_id)

    # ── 1. Validate request ───────────────────────────────────────────────
    goal_in = req.goal
    discipline = goal_in.discipline
    try:
        deadline_date = datetime.strptime(goal_in.deadline, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deadline: expected YYYY-MM-DD")

    today = date.today()
    # Use the per-discipline minimum (boulder is the lower of the two, so any
    # deadline that satisfies the boulder minimum also gives the user a chance
    # to pick boulder discipline). A218: bounds raised to 11 (lead) / 8 (boulder).
    if deadline_date < today + timedelta(weeks=_TOTAL_WEEKS_MIN_BOULDER):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Deadline is too soon. Choose a date at least "
                f"{_TOTAL_WEEKS_MIN_LEAD} weeks from today "
                f"({_TOTAL_WEEKS_MIN_BOULDER} for boulder)."
            ),
        )

    # Resolve total_weeks (caller override, or discipline default, clamped).
    if req.total_weeks is not None:
        total_weeks = req.total_weeks
    else:
        total_weeks = _DEFAULT_TOTAL_WEEKS_BOULDER if discipline == "boulder" else _DEFAULT_TOTAL_WEEKS_LEAD
    min_weeks = _TOTAL_WEEKS_MIN_BOULDER if discipline == "boulder" else _TOTAL_WEEKS_MIN_LEAD
    if total_weeks < min_weeks or total_weeks > _TOTAL_WEEKS_MAX:
        raise HTTPException(
            status_code=400,
            detail=(
                f"total_weeks {total_weeks} out of range "
                f"[{min_weeks}, {_TOTAL_WEEKS_MAX}] for discipline={discipline}."
            ),
        )

    # ── 2. Work on a deep-copy — atomicity guard ─────────────────────────
    new_state = deepcopy(state)
    new_state.setdefault("macrocycle_history", [])

    # ── 3. Archive the current macrocycle BEFORE overwrite ────────────────
    archived_count_before = len(new_state.get("macrocycle_history") or [])
    archive_current_macrocycle(new_state)
    archived_count = len(new_state["macrocycle_history"]) - archived_count_before

    # ── 4. Update goal (with discipline-aware grade mapping) ──────────────
    old_goal = new_state.get("goal") or {}
    old_discipline = old_goal.get("discipline")

    new_goal = dict(old_goal)
    new_goal["discipline"] = discipline
    new_goal["target_grade"] = goal_in.target_grade
    new_goal["target_style"] = goal_in.target_style or "redpoint"
    new_goal["deadline"] = goal_in.deadline

    # Derive goal_type from discipline (mirrors onboarding behavior).
    new_goal["goal_type"] = {
        "lead": "lead_grade",
        "boulder": "boulder_grade",
        "both": "all_round",
        "all_round": "all_round",
    }.get(discipline, "lead_grade")

    # If discipline flipped, remap current_grade and surface boulder grades.
    if old_discipline and old_discipline != discipline:
        existing_current = old_goal.get("current_grade")
        if existing_current:
            new_goal["current_grade"] = map_grade_for_discipline_change(
                existing_current, old_discipline, discipline,
            )

    # Boulder bookkeeping: target_boulder_grade mirrors target_grade for boulder
    # discipline, and assessment uses the lead-equivalent.
    if discipline == "boulder":
        boulder_target = goal_in.target_grade
        new_goal["target_boulder_grade"] = boulder_target
        new_goal["target_grade"] = BOULDER_TO_LEAD.get(boulder_target, boulder_target)
    else:
        # Leaving boulder behind — clear stale target_boulder_grade.
        new_goal.pop("target_boulder_grade", None)

    new_state["goal"] = new_goal

    # ── 5. Recompute assessment profile against the new goal ──────────────
    assessment = new_state.get("assessment") or {}
    try:
        profile = compute_assessment_profile(assessment, new_goal)
    except Exception as e:
        # No mutation has reached the on-disk state yet — safe to bail.
        raise HTTPException(status_code=422, detail=f"Assessment recomputation failed: {e}")
    new_state.setdefault("assessment", {})["profile"] = profile

    # ── 6. Resolve start_date for the new cycle ───────────────────────────
    new_start = compute_new_macrocycle_start_date(new_state, today)
    new_start_str = new_start.isoformat()

    # ── 7. Generate the new macrocycle (from_phase=None — clean fresh cycle) ─
    try:
        macrocycle = generate_macrocycle(
            new_goal, profile, new_state, new_start_str, total_weeks,
            from_phase=None,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Macrocycle generation failed: {e}")

    new_state["macrocycle"] = macrocycle

    # ── 8. Set initial_tests_requested=True (AFTER generate — see D232 §11) ─
    new_state["initial_tests_requested"] = True

    # ── 9. Invalidate week cache for the new cycle ────────────────────────
    _clear_week_cache_for_new_cycle(new_state, new_start_str)

    # ── 10. Persist (single write — atomic from caller's perspective) ─────
    save_state(new_state, user_id)

    return {
        "macrocycle": macrocycle,
        "archived_count": archived_count,
        "start_date": new_start_str,
    }
