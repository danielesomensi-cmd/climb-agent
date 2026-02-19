// -----------------------------------------------------------------------
// API response types
// -----------------------------------------------------------------------

export interface AssessmentProfile {
  finger_strength: number;
  pulling_strength: number;
  power_endurance: number;
  technique: number;
  endurance: number;
  body_composition: number;
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

export interface Macrocycle {
  start_date: string;
  total_weeks: number;
  phases: Phase[];
  goal_snapshot: Record<string, unknown>;
  profile_snapshot: Record<string, unknown>;
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
  intensity?: string;
}

export interface DayPlan {
  date: string;
  weekday: string;
  sessions: SessionSlot[];
  status?: "planned" | "done" | "skipped";
  outdoor_slot?: boolean;
  pretrip_deload?: boolean;
}

export interface WeekPlan {
  weeks: Array<{ days: DayPlan[] }>;
  profile_snapshot?: Record<string, unknown>;
  weekly_load_summary?: {
    total_load?: number;
    hard_days_count?: number;
    recovery_days_count?: number;
  };
}

export interface Exercise {
  exercise_id: string;
  name: string;
  domain: string;
  role: string;
  equipment_required: string[];
  prescription_defaults: Record<string, unknown>;
}

export interface SessionMeta {
  id: string;
  name: string;
  type: string;
  location: string;
  tags: Record<string, boolean>;
}

export interface ResolvedSession {
  session_id: string;
  session_name: string;
  blocks: Array<{
    block_name: string;
    exercises: Array<{
      exercise_id: string;
      name: string;
      sets?: number;
      reps?: string;
      load_kg?: number;
      rest_s?: number;
      tempo?: string;
      notes?: string;
    }>;
  }>;
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
    body_fat_pct?: number;
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
    target_style: string;
    current_grade: string;
    deadline: string;
  };
  self_eval: {
    primary_weakness: string;
    secondary_weakness: string;
  };
  tests: {
    max_hang_20mm_5s_total_kg?: number;
    weighted_pullup_1rm_total_kg?: number;
    repeater_7_3_max_sets_20mm?: number;
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
    gyms: Array<{ name: string; equipment: string[] }>;
  };
  availability: Record<
    string,
    Record<string, { available: boolean; preferred_location: string; gym_id?: string }>
  >;
  planning_prefs: {
    target_training_days_per_week: number;
    hard_day_cap_per_week: number;
  };
  trips: Array<{
    name: string;
    start_date: string;
    end_date: string;
    discipline: string;
    priority: string;
  }>;
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
}

export interface OutdoorRoute {
  name: string;
  grade: string;
  discipline?: "lead" | "boulder";
  style?: "onsight" | "flash" | "redpoint" | "project" | "repeat";
  attempts: OutdoorAttempt[];
}

export interface OutdoorSession {
  log_version: string;
  date: string;
  spot_id?: string;
  spot_name: string;
  discipline: "lead" | "boulder" | "both";
  duration_minutes: number;
  conditions?: {
    temperature_c?: number;
    humidity?: "low" | "medium" | "high";
    rock_condition?: "dry" | "damp" | "wet";
    wind?: "none" | "light" | "strong";
  };
  routes: OutdoorRoute[];
  notes?: string;
  energy_level?: string;
  overall_feeling?: string;
}

export interface OutdoorStats {
  total_sessions: number;
  total_routes: number;
  grade_histogram: Record<string, number>;
  onsight_pct: number;
  flash_pct: number;
  sent_pct: number;
  top_grade_sent: string | null;
}

// -----------------------------------------------------------------------
// Reports
// -----------------------------------------------------------------------

export interface WeeklyReport {
  report_type: "weekly";
  week_start: string;
  week_end: string;
  planned_sessions: number;
  completed_sessions: number;
  adherence_pct: number;
  total_indoor_minutes: number;
  total_outdoor_minutes: number;
  session_types: Record<string, number>;
  outdoor_sessions: number;
  highlights: string[];
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
  [key: string]: unknown;
}
