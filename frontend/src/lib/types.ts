// -----------------------------------------------------------------------
// API response types
// -----------------------------------------------------------------------

export interface AssessmentProfile {
  finger_strength: number;
  pulling_strength: number;
  power_endurance: number;
  technique: number;
  endurance: number;
}

export interface Phase {
  phase_id: string;
  phase_name: string;
  duration_weeks: number;
  energy_system: string;
  domain_weights: Record<string, number>;
  session_pool: string[];
  intensity_cap: string;
}

// A223: plan pause/resume state (lives inside the macrocycle object).
export interface MacrocyclePause {
  active_since: string | null; // ISO date while paused, null otherwise
  offset_days: number; // cumulative, multiple of 7
  log: { from: string; to: string }[]; // closed intervals
}

export interface Macrocycle {
  start_date: string;
  total_weeks: number;
  phases: Phase[];
  goal_snapshot: Record<string, unknown>;
  profile_snapshot: Record<string, unknown>;
  end_date?: string;
  pause?: MacrocyclePause; // A223
}

// A-NEW-MACRO: types for POST /api/macrocycle/start-new-cycle
export interface StartNewCycleGoal {
  discipline: "lead" | "boulder" | "both" | "all_round";
  target_grade: string;
  target_style?: "redpoint" | "onsight";
  deadline: string; // YYYY-MM-DD
}

export interface StartNewCycleRequest {
  goal: StartNewCycleGoal;
  total_weeks?: number;
}

export interface StartNewCycleResponse {
  macrocycle: Macrocycle;
  archived_count: number;
  start_date: string;
}

export interface MacrocycleHistoryEntry {
  archived_at: string;
  macrocycle: Macrocycle;
  goal_at_archive: Record<string, unknown>;
  weeks_completed: number;
  total_weeks: number;
  completion_summary: {
    sessions_done: number;
    sessions_skipped: number;
    sessions_planned: number;
    tests_completed: Array<{ session_id: string; date: string }>;
    phases_completed: string[];
  };
}

/** A139: Raw actual exercise data persisted after feedback submission. */
export interface ActualExercise {
  exercise_id: string;
  feedback_label?: string;
  completed?: boolean;
  used_external_load_kg?: number;
  used_total_load_kg?: number;
  used_grade?: string;
  completed_sets?: number;
  completed_reps?: number;
  hand?: string;
  surface_selected?: string;
  notes?: string;
  [key: string]: unknown;
}

export interface SessionSlot {
  session_id: string;
  location: string;
  gym_id?: string;
  slot: string;
  status?: "planned" | "done" | "skipped";
  tags?: Record<string, boolean>;
  resolved?: Record<string, unknown> | null;
  estimated_load_score?: number;
  session_load_score?: number;
  intensity?: string;
  feedback_summary?: string;
  exercise_feedback?: Record<string, string>;
  session_duration_seconds?: number;
  actual_exercises?: ActualExercise[];
  process_cue?: { id: string; text: string } | null;
  // A207: custom (user-built) session fields — inline-resolved, no catalog lookup.
  is_custom?: boolean;
  name?: string;
  custom_session_id?: string;
  session_mode?: string;
  exercises?: CustomSessionExercise[];
  target_duration_min?: number;
}

export interface OtherActivity {
  slot?: "morning" | "lunch" | "evening";
  name?: string;
  status?: "completed";
  feedback?: "easy" | "ok" | "hard";
  load?: number;
  duration_minutes?: number;
}

export interface DayPlan {
  date: string;
  weekday: string;
  sessions: SessionSlot[];
  status?: "planned" | "done" | "skipped";
  outdoor_slot?: boolean;
  outdoor_spot_name?: string;
  outdoor_discipline?: "lead" | "boulder" | "both";
  outdoor_spot_id?: string;
  outdoor_session_status?: "planned" | "done";
  pretrip_deload?: boolean;
  // B276: multiple other activities per day (one per slot).
  other_activities?: OtherActivity[];
  // Legacy scalar fields (pre-B276) — kept for reading preserved past days.
  other_activity?: boolean;
  other_activity_name?: string;
  other_activity_slot?: "morning" | "lunch" | "evening";
  other_activity_status?: "completed";
  other_activity_feedback?: "easy" | "ok" | "hard";
  other_activity_load?: number;
  other_activity_duration_minutes?: number;
  prev_other_activity_reduce?: boolean;
  outdoor_load_score?: number;
}

export interface WeekPlan {
  weeks: Array<{ days: DayPlan[] }>;
  profile_snapshot?: Record<string, unknown>;
  weekly_load_summary?: {
    planned_load?: number;
    total_load?: number;  // deprecated — use planned_load
    hard_days_count?: number;
    recovery_days_count?: number;
  };
}

export interface Exercise {
  id: string;
  exercise_id: string;
  name: string;
  domain: string[];
  category?: string;
  description?: string | null;
  role: string;
  equipment_required: string[];
  equipment_required_any?: string[];
  prescription_defaults: Record<string, unknown>;
}

export interface SessionMeta {
  id: string;
  name: string;
  type: string;
  location: string;
  tags: Record<string, boolean>;
  required_equipment?: string[];
}

/**
 * A245 G-6 (F23) — the REAL shape of a resolved session.
 *
 * The previous declaration was fiction: it claimed a top-level
 * `blocks: [{ block_name, exercises }]`. The payload
 * (`resolve_session.py`, `session_instance`) actually nests everything under
 * `resolved_session` and names the fields `block_uid` / `selected_exercises`.
 * The only consumer did `resolved.blocks.map(...)` — a guaranteed TypeError
 * that never fired only because nothing links to `/session/[id]`.
 *
 * A type that lies is worse than no type: it makes 220 `as X` casts elsewhere
 * (finding F24) look safe while the compiler validates nothing real.
 */
export interface ResolvedExerciseInstance {
  exercise_id: string;
  name?: string;
  block_uid?: string;
  prescription?: Record<string, unknown>;
  suggested?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ResolvedBlock {
  block_uid: string;
  block_id?: string;
  type?: string;
  status?: string;
  message?: string | null;
  selected_exercises: ResolvedExerciseInstance[];
}

export interface ResolvedSession {
  session_instance_version?: string;
  context?: Record<string, unknown>;
  session: {
    session_id: string;
    session_name: string;
    session_version?: string;
    target_duration_min?: number | null;
  };
  resolved_session: {
    resolver_version?: string;
    modules?: unknown[];
    blocks: ResolvedBlock[];
    exercise_instances: ResolvedExerciseInstance[];
  };
}

export interface WeaknessOption {
  id: string;
  label: string;
  description: string;
}

export interface EquipmentOption {
  id: string;
  label: string;
  description: string;
}

export interface TestDescription {
  label: string;
  description: string;
  unit: string;
  example: string;
}

export interface OnboardingDefaults {
  grades: string[];
  boulder_grades: string[];
  disciplines: string[];
  weakness_options: WeaknessOption[];
  weakness_options_grouped?: {
    universal: WeaknessOption[];
    lead: WeaknessOption[];
    boulder: WeaknessOption[];
  };
  equipment_home: EquipmentOption[];
  equipment_gym: EquipmentOption[];
  limitation_areas: string[];
  test_descriptions: Record<string, TestDescription>;
  slots: string[];
  weekdays: string[];
}

// -----------------------------------------------------------------------
// Onboarding form state
// -----------------------------------------------------------------------

export interface OnboardingData {
  profile: {
    name: string;
    preferred_name?: string;
    age: number;
    weight_kg: number;
    height_cm: number;
    // D64: body_fat_pct removed — RED-S guardrail, never display body composition metrics
  };
  experience: {
    climbing_years: number;
    structured_training_years: number;
  };
  grades: {
    lead_max_rp: string;
    lead_max_os: string;
    boulder_max_rp?: string;
    boulder_max_os?: string;
  };
  goal: {
    goal_type: string;
    discipline: string;
    target_grade: string;
    target_boulder_grade?: string;
    target_style: string;
    current_grade: string;
    deadline: string;
    total_weeks?: number;
  };
  self_eval: {
    primary_weakness: string;
    secondary_weakness: string;
  };
  tests: {
    max_hang_20mm_7s_total_kg?: number;
    max_hang_20mm_5s_total_kg?: number;  // legacy compat
    weighted_pullup_1rm_total_kg?: number;
    repeater_7_3_max_sets_20mm?: number;
    max_hang_duration_20mm_seconds?: number;
    l_sit_hold_seconds?: number;
    hip_flexibility_cm?: number;
    lp_max_lift_5s_right_kg?: number;
    lp_max_lift_5s_left_kg?: number;
    lp_repeater_7_3_right_reps?: number;
    lp_repeater_7_3_left_reps?: number;
    lp_duration_20mm_right_seconds?: number;
    lp_duration_20mm_left_seconds?: number;
    last_test_date?: string;
  };
  limitations: Array<{
    area: string;
    side: string;
    severity: string;
    notes?: string;
  }>;
  equipment: {
    home_enabled: boolean;
    home: string[];
    equipment_other?: string;
    gyms: Array<{ gym_id?: string; name: string; equipment: string[]; equipment_other?: string }>;
  };
  availability: Record<
    string,
    Record<string, { available: boolean; preferred_location: string; gym_id?: string }>
  >;
  planning_prefs: {
    target_training_days_per_week: number;
    hard_day_cap_per_week: number;
  };
  preferences: {
    finger_training_device: "hangboard" | "loading_pin";
    grade_system_boulder?: "font" | "v_scale";
  };
  trips: Array<{
    name: string;
    start_date: string;
    end_date: string;
    discipline: string;
    priority: string;
  }>;
  outdoor_spots: Array<{
    name: string;
    discipline: "lead" | "boulder" | "both";
  }>;
  test_week_requested?: boolean;
  /** A233: first-touch attribution (utm_*, referrer, landing_page, first_touch_at) */
  attribution?: Record<string, string>;
}

// -----------------------------------------------------------------------
// Outdoor
// -----------------------------------------------------------------------

export interface OutdoorSpot {
  id: string;
  name: string;
  discipline: "lead" | "boulder" | "both";
  typical_days?: string[];
  notes?: string;
}

export interface OutdoorAttempt {
  result: "sent" | "fell" | "topped_out";
  notes?: string;
  // B279 — per-attempt timing (optional). On multi-attempt (project) routes each
  // burn carries its own rest/climb; route-level fields stay = first burn (A227).
  rest_seconds?: number;
  climb_seconds?: number;
  // A241 — end-of-burn timestamp (ISO 8601 UTC, client-stamped). Rest between
  // tries is derived at render from the chronological chain (any route) —
  // new tries carry logged_at and omit rest_seconds. Absent on legacy tries.
  logged_at?: string;
}

export interface OutdoorRoute {
  name: string;
  grade: string;
  discipline?: "lead" | "boulder";
  style?: "onsight" | "flash" | "redpoint" | "project" | "repeat";
  attempts: OutdoorAttempt[];
  // A227 — additive timing (optional). rest_seconds = rest before the burn;
  // climb_seconds = on-the-wall time when the optional climb timer was used.
  rest_seconds?: number;
  climb_seconds?: number;
}

// A225/A226 — outdoor.v2 vocabulary
export type OutdoorDayType = "project" | "onsight_flash" | "volume" | "scout_easy";

// 4-value catalog band (distinct from the 3-value weather `ConditionBand`).
export type CatalogConditionBand = "prime" | "ok" | "poor_hot_humid" | "poor_cold_dry";

export interface OutdoorRouteProfile {
  wall_angle?: "slab" | "vertical" | "overhang" | "roof";
  route_length?: "short_power" | "medium" | "long_endurance";
  hold_style?: "crimp" | "sloper_pinch" | "mixed";
  target_grade_relative?: "within_limit" | "at_or_above_limit";
}

// outdoor.v2 conditions written to / read from the log.
export interface OutdoorConditions {
  temperature?: number;
  feels_like?: number; // A227
  humidity?: number;
  dew_point?: number; // A227
  wind?: number;
  wind_label?: string;
  wind_deg?: number; // A227
  cloud_cover?: number; // A227 (%)
  precip_prob?: number; // A227 (%, forecast only)
  condition_band?: CatalogConditionBand;
  weather_band_raw?: string;
  // A238 — additive friction verdict from the weather layer (same as Weather).
  band?: ConditionBand;
  friction_score?: number;
  dew_spread?: number;
  headline?: string;
  qualifiers?: WeatherQualifiers;
}

export interface OutdoorSession {
  log_version: string;
  date: string;
  spot_id?: string;
  spot_name: string;
  discipline: "lead" | "boulder" | "both";
  duration_minutes: number;
  conditions?: OutdoorConditions;
  routes: OutdoorRoute[];
  notes?: string;
  energy_level?: string;
  overall_feeling?: string;
  day_type?: OutdoorDayType;
  route_profile?: OutdoorRouteProfile;
  load_score?: number;
}

// ── Resolver (GET /api/outdoor/strategy) ────────────────────────────────
export interface OutdoorStrategyBase {
  warmup_protocol: string;
  target_burns: string;
  rest_between_attempts_min: string;
  stop_criteria: string[];
  skin_tips: string[];
  time_of_day_advice: string;
  hours_plan: string;
  downgrade_rule: string;
}

export interface OutdoorModifier {
  dimension: string;
  value: string;
  key: string;
  text: string;
}

export interface OutdoorNutrition {
  pre_day: string;
  during_by_duration: { short: string; long: string };
  hydration_by_climate: string;
  caffeine_timing: string;
  post_day: string;
  climate_addons: { precool: string };
  day_type_nuances: Record<string, string>;
  day_type_nuance: string | null;
}

export interface OutdoorStrategyResponse {
  strategy: {
    discipline: string;
    day_type: OutdoorDayType;
    base: OutdoorStrategyBase;
    modifiers: OutdoorModifier[];
    applied_dimensions: string[];
    skipped_dimensions: string[];
  };
  nutrition: OutdoorNutrition;
  safety: Record<string, string>;
  conditions: OutdoorConditions | null;
}

// ── Active session lifecycle ────────────────────────────────────────────
export interface OutdoorSessionStartResponse {
  session_id: string;
  started_at: string;
  status: "active";
}

export interface OutdoorSessionFinishResponse {
  status: "done";
  date: string;
  duration_minutes: number;
  duration_capped: boolean;
  duration_raw_minutes: number | null;
  duration_source: "timer" | "timer_capped" | "manual" | "none";
  load_score: number;
}

export interface OutdoorStats {
  total_sessions: number;
  total_routes: number;
  grade_histogram: Record<string, number>;
  onsight_pct: number;
  flash_pct: number;
  sent_pct: number;
  top_grade_sent: string | null;
  total_load: number;
  avg_load_per_session: number;
}

// -----------------------------------------------------------------------
// Reports
// -----------------------------------------------------------------------

export interface WeeklyReportContext {
  phase_id: string | null;
  phase_week: number | null;
  phase_total_weeks: number | null;
  macrocycle_week: number | null;
  macrocycle_total_weeks: number | null;
  goal: Record<string, unknown> | null;
  assessment_profile: Record<string, number> | null;
}

export interface WeeklyReportAdherence {
  planned: number;
  completed: number;
  skipped: number;
  added: number;
  pct: number;
  skipped_sessions: Array<{ date: string; session_id: string }>;
}

export interface WeeklyReportLoad {
  planned_total: number;
  actual_total: number;
  outdoor_load: number;
  free_session_load: number;
  load_ratio: number;
  hard_days: number;
  recovery_days: number;
  indoor_minutes: number;
  outdoor_minutes: number;
}

export interface WeeklyReportDifficulty {
  distribution: Record<string, number>;
  avg_label: string;
  hardest_session: { date: string; session_id: string; difficulty: string } | null;
  easiest_session: { date: string; session_id: string; difficulty: string } | null;
}

export interface WeeklyReportStimulusEntry {
  sessions_this_week: number;
  days_since_last: number | null;
}

export interface WeeklyReportProgression {
  exercise_id: string;
  previous_load: number | string;
  current_load: number | string;
  change_pct: number | null;
  direction: "up" | "down" | "same" | "grade_change";
}

export interface WeeklyReportOutdoor {
  sessions: number;
  routes_attempted: number;
  routes_sent: number;
  send_pct: number;
  top_grade_sent: string | null;
  top_grade_attempted: string | null;
  onsight_pct: number;
  spots: string[];
  // Backward compat aliases
  total_routes: number;
  sends: number;
}

export interface WeeklyReportSession {
  session_id: string;
  status: "planned" | "done" | "skipped";
  slot: string;
  estimated_load_score: number | null;
  intensity: string | null;
  feedback_summary: string | null;
}

export interface WeeklyReportFreeSession {
  id: string;
  surface: string;
  preset_name: string;
  context: string;
  total_climbs: number;
  max_grade_sent: string | null;
  send_rate: number;
  duration_minutes: number | null;
  load_score: number;
  climb_type: string;
}

export interface WeeklyReportDay {
  date: string;
  weekday: string;
  sessions: WeeklyReportSession[];
  outdoor: { spot_name: string; discipline: string; status: string; route_count?: number } | null;
  // B276: per-slot list of other activities (was a single object).
  other_activities: { slot?: string; name: string; status: string; feedback: string; load?: number }[];
  free_sessions?: WeeklyReportFreeSession[];
  is_rest_day: boolean;
}

export interface WeeklyReportTrainingTime {
  total_minutes: number;
  total_seconds: number;
  estimated_minutes: number;
  has_estimates: boolean;
  formatted: string;
  sources: Record<string, number>;
}

export interface WeeklyReportActiveDays {
  count: number;
  total: number;
  dots: boolean[];
}

export interface WeeklyReportHighlight {
  type: "positive" | "progress" | "warning" | "info";
  key: string;
  text: string;
}

export interface WeeklyReport {
  report_type: "weekly";
  week_start: string;
  week_end: string;
  context: WeeklyReportContext;
  adherence: WeeklyReportAdherence;
  load: WeeklyReportLoad;
  training_time: WeeklyReportTrainingTime;
  active_days: WeeklyReportActiveDays;
  difficulty: WeeklyReportDifficulty;
  stimulus_balance: Record<string, WeeklyReportStimulusEntry>;
  progression: WeeklyReportProgression[];
  outdoor: WeeklyReportOutdoor;
  days: WeeklyReportDay[];
  highlights: WeeklyReportHighlight[];
}

export interface MonthlyReport {
  report_type: "monthly";
  month: string;
  period_start: string;
  period_end: string;
  total_indoor_sessions: number;
  total_outdoor_sessions: number;
  avg_sessions_per_week: number;
  weekly_session_counts: number[];
  total_indoor_minutes: number;
  total_outdoor_minutes: number;
  feedback_summary: Record<string, number>;
  suggestions: string[];
}

// A236 (A-GAMIFY-03): monthly heatmap — rest-positive day cells.
export type HeatmapDayStatus =
  | "done"
  | "planned"
  | "skipped"
  | "rest"
  | "rest_planned"
  | "none";

export interface HeatmapDay {
  date: string;
  status: HeatmapDayStatus;
  load: number;
}

export interface MonthlyHeatmapData {
  month: string;
  today: string;
  days: HeatmapDay[];
}

// A239 (A-GAMIFY-02): milestone system.
export interface MilestoneItem {
  id: string;
  name: string;
  description: string;
  category: "session" | "outdoor" | "grade" | "exercise" | "process";
  tier: "activation" | "medium" | "career";
  icon: string;
  dynamic?: boolean;
  unlocked: boolean;
  unlocked_at?: string | null;
  seen?: boolean;
  context?: { rule?: string; discipline?: string; grade?: string } | null;
}

export interface MilestonesResponse {
  milestones: MilestoneItem[];
  unlocked_count: number;
  newly_unlocked: Array<{ id: string; unlocked_at: string }>;
}

// -----------------------------------------------------------------------
// Quotes
// -----------------------------------------------------------------------

export interface Quote {
  id: string;
  text: string;
  author: string;
  source_type: string;
  context: string;
}

// -----------------------------------------------------------------------
// Daily tips (A234)
// -----------------------------------------------------------------------

export interface DailyTip {
  id: string;
  category: string;
  text: string;
  cta_label?: string | null;
  cta_url?: string | null;
  tags?: string[];
}

export interface DailyTipResponse {
  tip: DailyTip | null;
  dismissed_today: boolean;
}

// -----------------------------------------------------------------------
// Weekly Check-in (B42)
// -----------------------------------------------------------------------

export interface SlotEntry {
  slot: "morning" | "lunch" | "evening";
  available: boolean;
  location: "gym" | "outdoor" | "home";
  gym_id: string | null;
}

export interface DayOverviewEntry {
  day: string;
  available: boolean;
  slots: SlotEntry[];
  default_slots: SlotEntry[];
  summary: string;
  is_overridden: boolean;
}

export interface WeeklyOverrideResponse {
  week_start: string;
  has_override: boolean;
  days: DayOverviewEntry[];
}

// -----------------------------------------------------------------------
// Guided Session Mode
// -----------------------------------------------------------------------

export interface GuidedExercise {
  exerciseId: string;
  name: string;
  category: string;
  blockUid: string;
  loadModel: string;
  unilateral?: boolean;    // true for loading-pin LP exercises (per-hand load tracking)
  altSides?: boolean;      // true for timer side-alternation exercises (RIGHT/LEFT badge)
  allowLoadLogging?: boolean;  // A228: opt a bodyweight/band exercise into the optional "weight used" field (record-only, e.g. Pallof Press)

  // Instruction-only blocks (warmup, mobility) — no exercise selection
  isInstructionOnly?: boolean;
  instructionNotes?: string[];
  instructionOptions?: string[];
  instructionFocus?: string[];
  instructionDuration?: [number, number];

  prescription: {
    sets?: number;
    reps?: string | number;
    workSeconds?: number;
    restBetweenRepsSeconds?: number;
    restSeconds?: number;
    loadKg?: number;
    tempo?: string;
    notes?: string;
    intensityPct?: number;
  };

  suggested: {
    externalLoadKg?: number;
    totalLoadKg?: number;
    grade?: string;
    gradeLow?: string;         // A-B7: lower bound of target grade range
    repScheme?: string;
    surface?: string;
    attemptGuidance?: string;  // A-B7: e.g. "1 serious attempt per problem"
    restGuidance?: string;     // A-B7: e.g. "3-5 min between problems"
    loadSource?: string;   // "estimated" if derived from grade/pullup (no real test)
    loadWarning?: string;  // "counterweight_required..." if external < 0
    rightHand?: { externalLoadKg?: number };
    leftHand?: { externalLoadKg?: number };
  };

  videoUrl?: string;
  cues?: string[];

  // Limitation system (B38)
  limitationWarning?: "monitor" | "active" | "severe";
  limitationZone?: string;
  limitationLoadModifier?: number;
  limitationPrehabFor?: string;

  status: "pending" | "done" | "skipped";
  feedbackLabel: string;
  usedLoadKg?: number;
  usedLoadKgRight?: number;
  usedLoadKgLeft?: number;
  completedRepsRight?: number;  // B134: per-hand reps (e.g. LP repeater test to failure)
  completedRepsLeft?: number;
  usedTotalLoadKg?: number;
  usedGrade?: string;
  completedSets?: number;  // sets completed within this exercise (for timer resume)

  // Test measurement exercises (category=test_measurement): single value input
  testField?: string;   // e.g. "max_hang_duration_20mm_seconds"
  testUnit?: string;    // e.g. "seconds" or "cm"
  testMeasurement?: number;
  testMeasurementRight?: number;  // per-hand measurement (e.g. seconds for lp_duration_test)
  testMeasurementLeft?: number;

  // B156: per-exercise notes (free text, max 500 chars)
  notes?: string;
}

export interface GuidedSessionState {
  version: 1;
  date: string;
  sessionId: string;
  sessionName: string;
  startedAt: string;
  currentIndex: number;
  exercises: GuidedExercise[];
  isTestSession?: boolean;
  bodyweightKg?: number;
  submitStatus?: "in_progress" | "feedback_pending" | "completed";
  processCue?: { id: string; text: string };
}

// -----------------------------------------------------------------------
// Session Builder (A206)
// -----------------------------------------------------------------------

export interface CustomSessionExercise {
  exercise_id: string;
  sets: number;
  reps: number | null;
  work_seconds: number | null;
  rest_between_sets_seconds: number | null;
  rest_between_reps_seconds: number | null;
  load_kg: number;
  notes: string;
  cues?: string[];
}

export interface CustomSession {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  tags: string[];
  exercises: CustomSessionExercise[];
  estimated_load_score: number;
  estimated_duration_minutes: number;
}

export interface CustomSessionSummary {
  id: string;
  name: string;
  tags: string[];
  exercise_count: number;
  estimated_load_score: number;
  estimated_duration_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface BuilderExercise {
  id: string;
  name: string;
  description: string;
  domain: string[];
  equipment_required: string[];
  prescription_defaults: {
    sets?: number;
    reps?: number;
    work_seconds?: number;
    rest_between_sets_seconds?: number;
    rest_between_reps_seconds?: number;
    notes?: string;
  };
  fatigue_cost: number;
  load_model: string;
  // A242: deterministic starting proposal + last-logged memory (custom-only).
  proposal?: ExerciseProposal;
}

export interface ExerciseProposal {
  sets?: number | null;
  reps?: number | null;
  work_seconds?: number | null;
  rest_between_sets_seconds?: number | null;
  rest_between_reps_seconds?: number | null;
  load_kg: number; // remembered value or 0 — never an invented absolute
  effort_band: string | null; // display-only phase cue (no RPE number)
  last_logged: {
    load_kg: number | null;
    feedback_label: string | null;
    date: string | null;
  } | null;
}

export interface WarmupCooldownBlock {
  template_id: string;
  label: string;
  exercises: Array<{
    exercise_id: string;
    name: string;
    sets: number;
    reps: number | null;
    work_seconds: number | null;
    rest_between_sets_seconds: number | null;
    rest_between_reps_seconds: number | null;
    load_kg: number;
    notes: string;
  }>;
}

// -----------------------------------------------------------------------
// User state (simplified — backend may have more keys)
// -----------------------------------------------------------------------

export interface UserState {
  schema_version: string;
  user: Record<string, unknown>;
  assessment: {
    profile?: AssessmentProfile | null;
    grades?: Record<string, string>;
    tests?: Record<string, unknown>;
    self_eval?: Record<string, string>;
    experience?: Record<string, number>;
    body?: Record<string, number>;
    [key: string]: unknown;
  };
  goal: Record<string, unknown>;
  macrocycle: Macrocycle | null;
  equipment: Record<string, unknown>;
  availability: Record<string, unknown>;
  planning_prefs: Record<string, unknown>;
  limitations: Record<string, unknown>;
  trips: Array<Record<string, unknown>>;
  // B272: engine-facing top-level fields the app reads/writes — previously
  // absent, forcing `as Record<string, unknown>` casts that hid exactly the
  // fields prone to drift (see D251 C2/W1).
  body?: { age?: number; weight_kg?: number; height_cm?: number };
  bodyweight_kg?: number;
  performance?: {
    current_level?: Record<string, unknown>;
    [key: string]: unknown;
  };
  preferences?: {
    finger_training_device?: "hangboard" | "loading_pin";
    grade_system_boulder?: "font" | "v_scale";
    /** A235: celebration keys `${macrocycle.start_date}:${phase_id}` already shown. */
    phase_celebrations_seen?: string[];
    [key: string]: unknown;
  };
  baselines?: Record<string, unknown>;
  working_loads?: Record<string, unknown>;
  fatigue_proxy?: Record<string, unknown>;
  stimulus_recency?: Record<string, unknown>;
  outdoor_spots?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

// A224 — weather conditions (live + forecast). A238: 4-value friction band.
export type ConditionBand = "prime" | "good" | "ok" | "poor";

// A238 — per-metric plain-English chips (backend-owned copy).
export interface WeatherQualifiers {
  temp: string;
  humidity: string;
  dew_spread: string;
  wind: string;
  precip: string;
}

// A238 — best later window of the local day (null when now is already best).
export interface BestWindow {
  from: string; // local "HH:MM"
  to: string;
  score: number;
  band: ConditionBand;
  reason: string;
}

export interface Weather {
  temp: number;
  feels_like?: number | null; // A227
  humidity: number;
  dew_point: number;
  wind: number;
  wind_label: string;
  wind_deg?: number | null; // A227
  cloud_cover?: number | null; // A227 (%)
  precip_prob?: number | null; // A227 (%, forecast only)
  condition_text: string;
  condition_code: number;
  condition_band: ConditionBand;
  // A238 — composite friction verdict (additive)
  friction_score?: number;
  band?: ConditionBand;
  dew_spread?: number;
  headline?: string;
  qualifiers?: WeatherQualifiers;
  best_window?: BestWindow | null;
  recent_rain_mm?: number;
  is_forecast: boolean;
  date: string | null;
  source: string;
}

/**
 * A245 G-4 (F52) — periodic retest reminder emitted by `GET /api/week/{n}`.
 *
 * Shape mirrors `should_show_test_reminder()` in `backend/engine/planner_v2.py`.
 */
export type TestReminderOption = "confirm" | "postpone_1_week" | "skip_cycle";

export interface TestReminder {
  type: "test_week_reminder";
  message: string;
  options: TestReminderOption[];
}
