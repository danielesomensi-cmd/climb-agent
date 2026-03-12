"""Weekly override router — CRUD for per-week availability overrides."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import ensure_monday, get_user_id, load_state, save_state
from backend.engine.weekly_override import build_merged_view

router = APIRouter(prefix="/api/weekly-override", tags=["weekly-override"])


class DayOverridePayload(BaseModel):
    available: bool = True
    location: str = "gym"  # gym | outdoor | home | rest
    gym_id: Optional[str] = None


class WeeklyOverridePayload(BaseModel):
    days: dict[str, DayOverridePayload] = Field(default_factory=dict)


@router.get("/{week_start}")
def get_weekly_override(
    week_start: str,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Get merged availability for a specific week.

    Returns 7 days with defaults merged with any override,
    plus an ``is_overridden`` flag per day and ``has_override`` at top level.
    """
    state = load_state(user_id)
    validated_start = ensure_monday(week_start)

    overrides = state.get("weekly_overrides") or {}
    override = overrides.get(validated_start)

    availability = state.get("availability")
    gyms = state.get("equipment", {}).get("gyms", [])
    merged = build_merged_view(availability, override, gyms)

    return {
        "week_start": validated_start,
        "has_override": override is not None,
        "days": merged,
    }


@router.put("/{week_start}")
def put_weekly_override(
    week_start: str,
    body: WeeklyOverridePayload,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Save an override for a specific week. Only changed days should be included."""
    state = load_state(user_id)
    validated_start = ensure_monday(week_start)

    override_data = {
        "days": {k: v.model_dump() for k, v in body.days.items()},
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    if "weekly_overrides" not in state:
        state["weekly_overrides"] = {}
    state["weekly_overrides"][validated_start] = override_data
    save_state(state, user_id)

    # Return merged view
    availability = state.get("availability")
    gyms = state.get("equipment", {}).get("gyms", [])
    merged = build_merged_view(availability, override_data, gyms)

    return {
        "status": "ok",
        "week_start": validated_start,
        "days": merged,
    }


@router.delete("/{week_start}")
def delete_weekly_override(
    week_start: str,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Remove override for a specific week (revert to defaults)."""
    state = load_state(user_id)
    validated_start = ensure_monday(week_start)

    overrides = state.get("weekly_overrides") or {}
    if validated_start in overrides:
        del overrides[validated_start]
        state["weekly_overrides"] = overrides
        save_state(state, user_id)

    return {"status": "ok", "week_start": validated_start}
