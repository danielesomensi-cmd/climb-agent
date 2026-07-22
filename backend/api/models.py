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
    # A245 E-2 (B15): bounded at the edge. Unbounded, an absurd total_weeks made
    # it all the way into generate_macrocycle() and came back as a 422 carrying
    # the engine's own ValueError text. 8 is the boulder floor and 16 the KB
    # consensus cap (A218); the per-discipline floor (lead 11) still belongs to
    # the engine, which knows the discipline.
    total_weeks: int = Field(12, ge=8, le=16)
    from_phase: Optional[str] = None  # "current" or a phase_id for incremental regen


class StartNewCycleGoal(BaseModel):
    """Goal payload for POST /api/macrocycle/start-new-cycle.

    Mirrors the subset of ``state["goal"]`` the user can edit during the
    "Plan Next Cycle" flow. Other goal fields (e.g. ``current_grade``,
    ``goal_type``) are derived server-side.
    """
    discipline: Literal["lead", "boulder", "both", "all_round"]
    target_grade: str
    target_style: Optional[Literal["redpoint", "onsight"]] = "redpoint"
    deadline: str  # YYYY-MM-DD


class StartNewCycleRequest(BaseModel):
    """Body for POST /api/macrocycle/start-new-cycle (A-NEW-MACRO)."""
    goal: StartNewCycleGoal
    total_weeks: Optional[int] = None  # falls back to discipline default


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
    # A254: user explicitly keeps the hard session they picked, at their own risk
    # (skips the 48h finger gap / weekly hard-cap downshift for THIS session only).
    force: bool = False


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
    # A233: first-touch attribution captured client-side (utm_*, referrer,
    # landing_page, first_touch_at). Sanitized server-side before persisting.
    attribution: Optional[Dict[str, Any]] = None


class OnboardingDraftEnvelope(BaseModel):
    """Body for PUT /api/onboarding/draft (B293).

    Server-side copy of the wizard draft, keyed to the authenticated user, so
    a forced re-auth mid-wizard cannot lose entered data. ``saved_at`` is the
    client epoch-ms timestamp — newer-wins when reconciling with the local
    draft on the client.
    """
    data: Dict[str, Any]
    deepest_step: int = Field(default=0, ge=0)
    saved_at: Optional[float] = None


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
    # B279 — per-attempt timing (optional, backward-compatible). On multi-attempt
    # (project) routes each burn carries its own rest/climb; route-level fields
    # keep describing the first burn only (A227 legacy).
    rest_seconds: Optional[int] = None
    climb_seconds: Optional[int] = None
    # A241 — client-stamped end-of-burn timestamp (ISO 8601 UTC). Rest between
    # tries is DERIVED at render from the chronological chain (any route), never
    # stored: new attempts carry logged_at (+climb_seconds when timed) and omit
    # rest_seconds. Absent on legacy tries → no breakdown, old display.
    logged_at: Optional[str] = None


class OutdoorRoute(BaseModel):
    """A route/problem attempted in an outdoor session."""
    name: str
    grade: str
    discipline: Optional[Literal["lead", "boulder", "both"]] = None
    style: Optional[Literal["onsight", "flash", "redpoint", "project", "repeat"]] = None
    attempts: List[OutdoorAttempt] = Field(default_factory=list)
    # A227 — additive timing (optional, backward-compatible). rest_seconds = rest
    # taken before the burn; climb_seconds = on-the-wall time when the optional
    # climb timer was used. Absent on legacy logs → no timing shown.
    rest_seconds: Optional[int] = None
    climb_seconds: Optional[int] = None


class OutdoorRouteProfile(BaseModel):
    """A225 (outdoor.v2): optional project/route characteristics.

    All fields optional — progressive disclosure / graceful degradation. They key
    the deterministic strategy catalog patches (C241). Absent fields → catalog
    base defaults. Values mirror the catalog ``dimensions`` block exactly.
    """
    wall_angle: Optional[Literal["slab", "vertical", "overhang", "roof"]] = None
    route_length: Optional[Literal["short_power", "medium", "long_endurance"]] = None
    hold_style: Optional[Literal["crimp", "sloper_pinch", "mixed"]] = None
    target_grade_relative: Optional[Literal["within_limit", "at_or_above_limit"]] = None


class OutdoorSessionLog(BaseModel):
    """Body for POST /api/outdoor/log.

    A225: ``outdoor.v2`` adds optional ``day_type`` + ``route_profile``, and
    ``conditions.temperature`` / ``conditions.condition_band``. All additive —
    ``outdoor.v1`` logs (without these) stay valid, no migration.
    """
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
    # outdoor.v2 (A225) — all optional
    day_type: Optional[Literal["project", "onsight_flash", "volume", "scout_easy"]] = None
    route_profile: Optional[OutdoorRouteProfile] = None


class OutdoorSessionStartRequest(BaseModel):
    """Body for POST /api/outdoor/session/start (A225 active-session lifecycle)."""
    date: str
    spot_id: Optional[str] = None
    spot_name: Optional[str] = None
    discipline: Optional[Literal["lead", "boulder", "both"]] = None
    day_type: Optional[Literal["project", "onsight_flash", "volume", "scout_easy"]] = None


class OutdoorSessionFinishRequest(BaseModel):
    """Body for POST /api/outdoor/session/{id}/finish (A225).

    Mirrors OutdoorSessionLog but ``duration_minutes`` is OPTIONAL: when omitted
    the backend derives it from the timer (started_at→now, capped). When present
    it is treated as an explicit manual override that always wins.
    """
    spot_name: str
    discipline: Literal["lead", "boulder", "both"]
    duration_minutes: Optional[int] = None  # manual override; None → derive from timer
    spot_id: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    routes: List[OutdoorRoute] = Field(default_factory=list)
    notes: Optional[str] = None
    energy_level: Optional[str] = None
    overall_feeling: Optional[str] = None
    day_type: Optional[Literal["project", "onsight_flash", "volume", "scout_easy"]] = None
    route_profile: Optional[OutdoorRouteProfile] = None


class OutdoorClimbLogRequest(BaseModel):
    """Body for POST /api/outdoor/session/{id}/log-climb (A226 live logging)."""
    name: str
    grade: str
    attempts: List[OutdoorAttempt] = Field(default_factory=list)
    style: Optional[Literal["onsight", "flash", "redpoint", "project", "repeat"]] = None
    discipline: Optional[Literal["lead", "boulder", "both"]] = None
    at_min: Optional[int] = None
    rest_seconds: Optional[int] = None  # A227
    climb_seconds: Optional[int] = None  # A227


class OutdoorActiveRoute(BaseModel):
    """A route on an active session (allows the live ``at_min`` marker)."""
    name: str
    grade: str
    attempts: List[OutdoorAttempt] = Field(default_factory=list)
    style: Optional[Literal["onsight", "flash", "redpoint", "project", "repeat"]] = None
    discipline: Optional[Literal["lead", "boulder", "both"]] = None
    at_min: Optional[int] = None
    rest_seconds: Optional[int] = None  # A227
    climb_seconds: Optional[int] = None  # A227


class OutdoorRoutesReplaceRequest(BaseModel):
    """Body for PUT /api/outdoor/session/{id}/routes (A226 live route sync)."""
    routes: List[OutdoorActiveRoute] = Field(default_factory=list)


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
    mobility: Optional[Dict[str, Any]] = None  # mobility session data (A230)


# --------------------------------------------------------------------------- #
# Custom Session (A205)
# --------------------------------------------------------------------------- #

class CustomSessionExerciseEntry(BaseModel):
    """Single exercise inside a custom session."""
    exercise_id: str
    sets: int = Field(ge=1, le=20)
    reps: Optional[int] = Field(default=None, ge=1, le=100)
    work_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    rest_between_sets_seconds: Optional[int] = Field(default=None, ge=0, le=600)
    rest_between_reps_seconds: Optional[int] = Field(default=None, ge=0, le=300)
    load_kg: Optional[float] = Field(default=0, ge=0, le=200)
    notes: Optional[str] = Field(default=None, max_length=1000)


class CustomSessionCreateRequest(BaseModel):
    """Body for POST /api/custom-session."""
    name: str = Field(min_length=1, max_length=100)
    tags: List[str] = Field(default_factory=list, max_length=5)
    exercises: List[CustomSessionExerciseEntry] = Field(min_length=1, max_length=30)


class CustomSessionUpdateRequest(BaseModel):
    """Body for PUT /api/custom-session/{session_id}."""
    name: str = Field(min_length=1, max_length=100)
    tags: List[str] = Field(default_factory=list, max_length=5)
    exercises: List[CustomSessionExerciseEntry] = Field(min_length=1, max_length=30)
