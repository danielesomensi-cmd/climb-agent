"""Pydantic request/response models for the climb-agent API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #

class StatePatch(BaseModel):
    """Body for PUT /api/state — deep-merged into existing state."""
    model_config = {"extra": "allow"}


# --------------------------------------------------------------------------- #
# Assessment
# --------------------------------------------------------------------------- #

class AssessmentRequest(BaseModel):
    """Body for POST /api/assessment/compute."""
    assessment: Dict[str, Any] = Field(default_factory=dict)
    goal: Dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Macrocycle
# --------------------------------------------------------------------------- #

class MacrocycleRequest(BaseModel):
    """Body for POST /api/macrocycle/generate."""
    start_date: Optional[str] = None
    total_weeks: int = 12


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #

class SessionResolveRequest(BaseModel):
    """Body for POST /api/session/resolve."""
    session_id: str
    context: Optional[Dict[str, Any]] = None


# --------------------------------------------------------------------------- #
# Replanner
# --------------------------------------------------------------------------- #

class OverrideRequest(BaseModel):
    """Body for POST /api/replanner/override."""
    intent: str
    location: str
    reference_date: str
    slot: str = "evening"
    phase_id: Optional[str] = None
    week_plan: Optional[Dict[str, Any]] = None
    target_date: Optional[str] = None
    gym_id: Optional[str] = None


class EventsRequest(BaseModel):
    """Body for POST /api/replanner/events."""
    events: List[Dict[str, Any]]
    week_plan: Optional[Dict[str, Any]] = None


class QuickAddRequest(BaseModel):
    """Body for POST /api/replanner/quick-add."""
    session_id: str
    target_date: str
    slot: str = "evening"
    location: str = "gym"
    phase_id: Optional[str] = None
    week_plan: Optional[Dict[str, Any]] = None
    gym_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# Feedback
# --------------------------------------------------------------------------- #

class FeedbackRequest(BaseModel):
    """Body for POST /api/feedback — session log entry."""
    log_entry: Dict[str, Any]
    resolved_day: Optional[Dict[str, Any]] = None
    status: str = "done"


# --------------------------------------------------------------------------- #
# Onboarding
# --------------------------------------------------------------------------- #

class OnboardingData(BaseModel):
    """Body for POST /api/onboarding/complete."""
    profile: Dict[str, Any] = Field(default_factory=dict)
    experience: Dict[str, Any] = Field(default_factory=dict)
    grades: Dict[str, Any] = Field(default_factory=dict)
    goal: Dict[str, Any] = Field(default_factory=dict)
    self_eval: Dict[str, Any] = Field(default_factory=dict)
    tests: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[Dict[str, Any]] = Field(default_factory=list)
    equipment: Dict[str, Any] = Field(default_factory=dict)
    availability: Dict[str, Any] = Field(default_factory=dict)
    planning_prefs: Dict[str, Any] = Field(default_factory=dict)
    trips: List[Dict[str, Any]] = Field(default_factory=list)
