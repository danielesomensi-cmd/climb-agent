"""Pydantic request/response models for the climb-agent API."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

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
    from_phase: Optional[str] = None  # "current" or a phase_id for incremental regen


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #

class SessionResolveRequest(BaseModel):
    """Body for POST /api/session/resolve."""
    session_id: str
    context: Optional[Dict[str, Any]] = None
    # A210: ephemeral equipment override for "Boulder only" toggle.
    # When set, replaces the user's available equipment for this resolve only.
    # Used for sessions whose core block is gym_routes-optional (e.g. power_endurance_gym
    # re-resolved with equipment_override = user_eq - {"gym_routes"}).
    equipment_override: Optional[List[str]] = None


class AddExerciseRequest(BaseModel):
    """Body for POST /api/session/add-exercise."""
    date: str
    session_index: int = 0
    exercise_id: str
    prescription_override: Optional[Dict[str, Any]] = None
    week_plan: Optional[Dict[str, Any]] = None


class RemoveExerciseRequest(BaseModel):
    """Body for POST /api/session/remove-exercise."""
    date: str
    session_index: int = 0
    exercise_index: int
    week_plan: Optional[Dict[str, Any]] = None



# --------------------------------------------------------------------------- #
# Replanner
# --------------------------------------------------------------------------- #

class OverrideRequest(BaseModel):
    """Body for POST /api/replanner/override."""
    intent: str
    location: str
    reference_date: str
    slot: Literal["morning", "lunch", "evening"] = "evening"
    phase_id: Optional[str] = None
    week_plan: Optional[Dict[str, Any]] = None
    target_date: Optional[str] = None
    gym_id: Optional[str] = None
    session_index: Optional[int] = None


class EventsRequest(BaseModel):
    """Body for POST /api/replanner/events."""
    events: List[Dict[str, Any]]
    week_plan: Optional[Dict[str, Any]] = None


class QuickAddRequest(BaseModel):
    """Body for POST /api/replanner/quick-add."""
    session_id: str
    target_date: str
    slot: Literal["morning", "lunch", "evening"] = "evening"
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

class StartWeekRequest(BaseModel):
    """Body for POST /api/onboarding/start-week."""
    offset_weeks: int = Field(ge=0)


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
    preferences: Dict[str, Any] = Field(default_factory=dict)
    trips: List[Dict[str, Any]] = Field(default_factory=list)
    outdoor_spots: List[Dict[str, Any]] = Field(default_factory=list)
    test_week_requested: bool = False


class TestReminderResponse(BaseModel):
    """Body for POST /api/week/test-reminder-response."""
    option: str  # "confirm" | "postpone_1_week" | "skip_cycle"


# --------------------------------------------------------------------------- #
# Outdoor
# --------------------------------------------------------------------------- #

class OutdoorSpotCreate(BaseModel):
    """Body for POST /api/outdoor/spots."""
    id: Optional[str] = None
    name: str
    discipline: Literal["lead", "boulder", "both"]
    typical_days: Optional[List[str]] = None
    notes: Optional[str] = None


class OutdoorAttempt(BaseModel):
    """Single attempt on a route."""
    result: Literal["sent", "fell", "topped_out"]
    notes: Optional[str] = None


class OutdoorRoute(BaseModel):
    """A route/problem attempted in an outdoor session."""
    name: str
    grade: str
    discipline: Optional[Literal["lead", "boulder", "both"]] = None
    style: Optional[Literal["onsight", "flash", "redpoint", "project"]] = None
    attempts: List[OutdoorAttempt] = Field(default_factory=list)


class OutdoorSessionLog(BaseModel):
    """Body for POST /api/outdoor/log."""
    date: str
    spot_id: Optional[str] = None
    spot_name: str
    discipline: Literal["lead", "boulder", "both"]
    duration_minutes: int
    conditions: Optional[Dict[str, Any]] = None
    routes: List[OutdoorRoute] = Field(default_factory=list)
    notes: Optional[str] = None
    energy_level: Optional[str] = None
    overall_feeling: Optional[str] = None


class ConvertSlotRequest(BaseModel):
    """Body for POST /api/outdoor/convert-slot."""
    date: str
    new_location: str  # gym | home
    gym_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #

class WeeklyReportRequest(BaseModel):
    """Query params for GET /api/reports/weekly."""
    week_start: str


class MonthlyReportRequest(BaseModel):
    """Query params for GET /api/reports/monthly."""
    month: str  # YYYY-MM


# --------------------------------------------------------------------------- #
# Free Session
# --------------------------------------------------------------------------- #

class FreeSessionStartRequest(BaseModel):
    """Body for POST /api/free-session/start.

    Gym fields (B201): ``gym_id`` identifies a saved gym from the user's
    ``equipment.gyms`` list — validated server-side, 422 if not found.
    ``gym_name`` is reserved for a free-text custom gym that the user has
    NOT saved. When both are provided, ``gym_id`` wins and ``gym_name`` is
    overwritten by the canonical name resolved from the lookup.
    """
    date: str
    surface: str  # gym_boulder | board_kilter | board_moonboard | board_other | gym_routes
    gym_id: Optional[str] = None
    gym_name: Optional[str] = None
    session_mode: str  # template | free
    preset_id: Optional[str] = None
    context: str  # standalone | add_on | replacement


class FreeSessionLogClimbRequest(BaseModel):
    """Body for POST /api/free-session/{session_id}/log-climb."""
    grade: str
    status: Literal["flash", "sent", "attempted"]
    attempts: int = 1
    style: Optional[Literal["onsight", "flash", "redpoint", "project"]] = None  # lead only
    topped: Optional[bool] = None  # lead only
    notes: Optional[str] = None


class FreeSessionFinishRequest(BaseModel):
    """Body for POST /api/free-session/{session_id}/finish."""
    overall_feel: Optional[str] = None  # easy | good | hard
    notes: Optional[str] = None
    circuit: Optional[Dict[str, Any]] = None  # circuit session data
