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
  tags?: Record<string, boolean>;
}

export interface DayPlan {
  date: string;
  weekday: string;
  sessions: SessionSlot[];
  status?: "planned" | "done" | "skipped";
}

export interface WeekPlan {
  weeks: Array<{ days: DayPlan[] }>;
  profile_snapshot?: Record<string, unknown>;
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
