"""Body Part Picker router (A213).

Endpoints:
  GET  /api/body-part-picker/options   — available categories + equipment modes
  POST /api/body-part-picker/preview   — generate session without persisting
  POST /api/body-part-picker/start     — generate + insert into week plan
  GET  /api/body-part-picker/estimate  — live-counter duration estimate
"""

from __future__ import annotations

import json
import logging
from datetime import date as date_type
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.api.deps import (
    REPO_ROOT,
    assert_plan_not_paused,
    get_user_id,
    load_state,
    require_active_subscription,
    save_state,
)
from backend.engine.body_part_picker import (
    BODY_PART_CATEGORIES,
    BODY_PART_ORDER,
    estimate_duration_stub,
    generate_body_part_session,
    get_available_body_parts,
    resolve_equipment_mode,
)
from backend.engine.replanner_v1 import apply_events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/body-part-picker", tags=["body-part-picker"])

EXERCISES_PATH = REPO_ROOT / "backend" / "catalog" / "exercises" / "v1" / "exercises.json"

_CATALOG_CACHE: Optional[List[Dict[str, Any]]] = None


def _load_catalog() -> List[Dict[str, Any]]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is None:
        with open(EXERCISES_PATH, encoding="utf-8") as f:
            _CATALOG_CACHE = json.load(f).get("exercises", [])
    return _CATALOG_CACHE


# ── Request models ────────────────────────────────────────────────────────


class PreviewRequest(BaseModel):
    body_parts: List[str] = Field(..., min_length=1)
    equipment_mode: str
    gym_id: Optional[str] = None
    include_cooldown: bool = True
    seed: Optional[int] = None


class StartRequest(PreviewRequest):
    target_date: str
    slot: str = "evening"
    location: str = "home"


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("/options", dependencies=[Depends(require_active_subscription)])
def options(
    equipment_mode: Optional[str] = Query(None),
    gym_id: Optional[str] = Query(None),
    user_id: Optional[str] = Depends(get_user_id),
):
    """Return available body parts + equipment options for this user.

    When equipment_mode is omitted, counts are computed against the full
    equipment catalog so no category is wrongly greyed out before the user
    picks a mode. The frontend re-queries with the selected mode to refresh
    per-category availability.
    """
    state = load_state(user_id)
    catalog = _load_catalog()

    mode = equipment_mode or "all"
    equipment = resolve_equipment_mode(mode, state, gym_id=gym_id)
    body_parts = get_available_body_parts(catalog, equipment)

    options_list: List[Dict[str, Any]] = [
        {"mode": "bodyweight", "label": "Bodyweight"},
    ]
    eq = state.get("equipment") or {}
    if eq.get("home"):
        options_list.append({"mode": "home", "label": "Home"})
    for g in (eq.get("gyms") or []):
        if g.get("gym_id") and g.get("name"):
            options_list.append({
                "mode": "gym",
                "label": f"Gym: {g['name']}",
                "gym_id": g["gym_id"],
            })
    options_list.append({"mode": "all", "label": "Show All"})

    return {
        "body_parts": body_parts,
        "equipment_options": options_list,
    }


@router.post("/preview", dependencies=[Depends(require_active_subscription)])
def preview(req: PreviewRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Generate a session preview without persisting."""
    _validate_body_parts(req.body_parts)
    state = load_state(user_id)
    catalog = _load_catalog()
    session = generate_body_part_session(
        body_parts=req.body_parts,
        equipment_mode=req.equipment_mode,
        gym_id=req.gym_id,
        user_state=state,
        exercises_catalog=catalog,
        include_cooldown=req.include_cooldown,
        seed=req.seed,
    )
    if not session.get("exercises"):
        raise HTTPException(
            status_code=422,
            detail="No exercises matched — try a broader equipment mode or different body parts.",
        )
    return session


@router.post("/start", dependencies=[Depends(require_active_subscription)])
def start(req: StartRequest, user_id: Optional[str] = Depends(get_user_id)):
    """Generate a session and insert it into the week plan via replanner."""
    _validate_body_parts(req.body_parts)
    _validate_target_date(req.target_date)

    state = load_state(user_id)
    assert_plan_not_paused(state)  # A223 — inserts into the week plan
    catalog = _load_catalog()
    session_payload = generate_body_part_session(
        body_parts=req.body_parts,
        equipment_mode=req.equipment_mode,
        gym_id=req.gym_id,
        user_state=state,
        exercises_catalog=catalog,
        include_cooldown=req.include_cooldown,
        seed=req.seed,
    )
    if not session_payload.get("exercises"):
        raise HTTPException(
            status_code=422,
            detail="No exercises matched — try a broader equipment mode or different body parts.",
        )

    week_plan = state.get("current_week_plan")
    if not week_plan:
        raise HTTPException(
            status_code=422,
            detail="No active week plan — generate one from GET /api/week/0 first.",
        )

    try:
        updated = apply_events(
            week_plan,
            [{
                "event_type": "add_generated_session",
                "session_payload": session_payload,
                "target_date": req.target_date,
                "slot": req.slot,
                "location": req.location,
                "gym_id": req.gym_id,
            }],
            availability=state.get("availability"),
            planning_prefs=state.get("planning_prefs"),
            gyms=(state.get("equipment") or {}).get("gyms"),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    state["current_week_plan"] = updated
    start_key = updated.get("start_date")
    if start_key:
        state.setdefault("week_plans", {})[start_key] = updated
    save_state(state, user_id)

    inserted = _find_session(updated, req.target_date, req.slot)
    return {"session": inserted, "week_plan": updated}


@router.get("/estimate", dependencies=[Depends(require_active_subscription)])
def estimate(
    body_parts: str = Query(..., description="Comma-separated body-part IDs"),
    include_cooldown: bool = True,
):
    """Lightweight duration estimate for the live counter."""
    parts = [p.strip() for p in body_parts.split(",") if p.strip()]
    _validate_body_parts(parts)
    return {
        "estimated_duration_min": estimate_duration_stub(parts, include_cooldown),
    }


# ── Helpers ───────────────────────────────────────────────────────────────


def _validate_body_parts(body_parts: List[str]) -> None:
    unknown = [p for p in body_parts if p not in BODY_PART_CATEGORIES]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown body parts: {', '.join(unknown)}",
        )
    disabled = [p for p in body_parts if not BODY_PART_CATEGORIES[p]["enabled"]]
    if disabled:
        raise HTTPException(
            status_code=422,
            detail=f"Body parts currently disabled: {', '.join(disabled)}",
        )


def _validate_target_date(iso_date: str) -> None:
    try:
        date_type.fromisoformat(iso_date)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid target_date: {iso_date!r} — expected YYYY-MM-DD",
        )


def _find_session(
    week_plan: Dict[str, Any],
    target_date: str,
    slot: str,
) -> Optional[Dict[str, Any]]:
    for week in week_plan.get("weeks", []):
        for day in week.get("days", []):
            if day.get("date") == target_date:
                for s in day.get("sessions", []):
                    if s.get("slot") == slot:
                        return s
    return None
