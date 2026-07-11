import type {
  OnboardingData,
  OnboardingDefaults,
  UserState,
  ResolvedSession,
  WeekPlan,
  Macrocycle,
  AssessmentProfile,
  Exercise,
  SessionMeta,
  OutdoorSpot,
  OutdoorSession,
  OutdoorStats,
  OutdoorStrategyResponse,
  OutdoorSessionStartResponse,
  OutdoorSessionFinishResponse,
  WeeklyReport,
  MonthlyReport,
  Quote,
  CustomSession,
  CustomSessionSummary,
  CustomSessionExercise,
  BuilderExercise,
  WarmupCooldownBlock,
  Weather,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function _getAuthHeaders(): Promise<Record<string, string>> {
  if (typeof window === "undefined") return {};
  try {
    const token = await window.Clerk?.session?.getToken();
    if (token) return { Authorization: `Bearer ${token}` };
  } catch {
    // Clerk not loaded yet or session expired — fall through
  }
  return {};
}

async function request<T>(path: string, options?: RequestInit, _isRetry = false): Promise<T> {
  const authHeaders = await _getAuthHeaders();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders,
    ...((options?.headers as Record<string, string>) || {}),
  };
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  // B155: on 401, retry once after 500ms — Clerk token may not be ready yet
  if (res.status === 401 && !_isRetry && typeof window !== "undefined") {
    console.warn(`[B155] 401 on ${path} — retrying in 500ms (Clerk may still be loading)`);
    await new Promise((r) => setTimeout(r, 500));
    return request<T>(path, options, true);
  }
  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/sign-in";
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const body = await res.text();
    if (res.status === 402) {
      // B272: friendly backstop for subscription-gated endpoints — surface
      // the backend detail (tailored by trial status) instead of a raw
      // "API 402: {...}" string on every gated mutation.
      let detail = "";
      try {
        detail = (JSON.parse(body) as { detail?: string }).detail ?? "";
      } catch {
        // non-JSON body — fall through to the generic copy
      }
      throw new ApiError(
        402,
        detail || "Subscription required. Manage your plan in Settings.",
      );
    }
    throw new ApiError(res.status, `API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/** Error thrown by `request()` with the HTTP status attached (B272) — lets
 * callers branch on status without parsing the message string. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// State
export const getState = () => request<UserState>("/api/state");
export const putState = (patch: Record<string, unknown>) =>
  request<UserState>("/api/state", { method: "PUT", body: JSON.stringify(patch) });
export const deleteState = () =>
  request<{ status: string; state: UserState }>("/api/state", { method: "DELETE" });
export const getStateStatus = () =>
  request<{ is_macrocycle_stale: boolean }>("/api/state/status");

// Catalog
export const getExercises = async () => {
  const data = await request<{ exercises: Array<Exercise & { id: string }>; count: number }>("/api/catalog/exercises");
  return {
    ...data,
    exercises: data.exercises.map((e) => ({ ...e, exercise_id: e.exercise_id || e.id })),
  };
};
export const getSessions = () =>
  request<{ sessions: SessionMeta[]; count: number }>("/api/catalog/sessions");

// Onboarding
export const getOnboardingDefaults = () =>
  request<OnboardingDefaults>("/api/onboarding/defaults");
export const completeOnboarding = (data: OnboardingData, extra?: RequestInit) =>
  request<{ profile: AssessmentProfile; macrocycle: Macrocycle }>("/api/onboarding/complete", {
    method: "POST",
    body: JSON.stringify(data),
    ...extra,
  });
export const setStartWeek = (offsetWeeks: number) =>
  request<{ status: string; start_date: string; offset_applied: number }>(
    "/api/onboarding/start-week",
    { method: "POST", body: JSON.stringify({ offset_weeks: offsetWeeks }) }
  );

// Assessment
export const computeAssessment = (
  assessment?: Record<string, unknown>,
  goal?: Record<string, unknown>
) =>
  request<{ profile: AssessmentProfile }>("/api/assessment/compute", {
    method: "POST",
    body: JSON.stringify({ assessment, goal }),
  });

// Macrocycle
export const generateMacrocycle = (
  startDate?: string,
  totalWeeks = 12,
  fromPhase?: string, // "current" = incremental, undefined = full regen
) =>
  request<{ macrocycle: Macrocycle }>("/api/macrocycle/generate", {
    method: "POST",
    body: JSON.stringify({
      start_date: startDate,
      total_weeks: totalWeeks,
      from_phase: fromPhase,
    }),
  });

/** A-NEW-MACRO: start a fresh macrocycle with mandatory goal review.
 * Atomic backend flow: archive current → update goal → recompute profile →
 * generate → set initial_tests_requested → invalidate cache. Subscription-gated.
 */
export const startNewMacrocycle = (
  body: import("@/lib/types").StartNewCycleRequest,
) =>
  request<import("@/lib/types").StartNewCycleResponse>(
    "/api/macrocycle/start-new-cycle",
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );

// A223: plan pause / resume
export interface PauseResponse {
  paused: boolean;
  active_since?: string | null;
  offset_days: number;
  shifted_days?: number;
  end_date?: string;
  weeks_shifted?: number;
  weeks_dropped?: number;
}

export const pausePlan = () =>
  request<PauseResponse>("/api/plan/pause", { method: "POST" });

export const resumePlan = () =>
  request<PauseResponse>("/api/plan/resume", { method: "POST" });

// Week
export const getWeek = (weekNum: number, force?: boolean, preserveBefore?: string) => {
  const params = new URLSearchParams();
  if (force) params.set("force", "true");
  if (preserveBefore) params.set("preserve_before", preserveBefore);
  const qs = params.toString();
  // B257: a past week with no cached data fails closed — week_plan is null and
  // past_week_unavailable is true (past weeks are immutable, never regenerated).
  return request<{
    week_num: number;
    phase_id: string;
    week_plan: WeekPlan | null;
    past_week_unavailable?: boolean;
  }>(`/api/week/${weekNum}${qs ? `?${qs}` : ""}`);
};

// Session
export const resolveSession = (
  sessionId: string,
  context?: Record<string, unknown>,
  equipmentOverride?: string[] | null,
) =>
  request<{ resolved: ResolvedSession }>("/api/session/resolve", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      context,
      equipment_override: equipmentOverride ?? undefined,
    }),
  });

export const addExerciseToSession = (data: {
  date: string;
  session_index: number;
  exercise_id: string;
  prescription_override?: Record<string, unknown>;
  week_plan: WeekPlan;
}) =>
  request<{ week_plan: WeekPlan }>("/api/session/add-exercise", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const removeExerciseFromSession = (data: {
  date: string;
  session_index: number;
  exercise_index: number;
  week_plan: WeekPlan;
}) =>
  request<{ week_plan: WeekPlan }>("/api/session/remove-exercise", {
    method: "POST",
    body: JSON.stringify(data),
  });


// Replanner
export const applyOverride = (data: {
  intent: string;
  location: string;
  reference_date: string;
  slot?: string;
  phase_id?: string;
  week_plan: WeekPlan;
  target_date?: string;
  gym_id?: string;
  session_index?: number;
}) =>
  request<{ week_plan: WeekPlan }>("/api/replanner/override", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const applyEvents = (data: {
  events: Array<Record<string, unknown>>;
  week_plan: WeekPlan;
}) =>
  request<{ week_plan: WeekPlan }>("/api/replanner/events", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const getSuggestedSessions = (targetDate: string, location: string) =>
  request<{
    suggestions: Array<{
      session_id: string;
      session_name?: string;
      intensity: string;
      estimated_load_score: number;
      reason: string;
      required_equipment?: string[];
    }>;
    supplementary: Array<{
      session_id: string;
      session_name: string;
      required_equipment: string[];
      time_budget: string;
    }>;
  }>(`/api/replanner/suggest-sessions?target_date=${targetDate}&location=${location}`);

export const quickAddSession = (data: {
  session_id: string;
  target_date: string;
  slot?: string;
  location?: string;
  phase_id?: string;
  week_plan: WeekPlan;
  gym_id?: string;
}) =>
  request<{ week_plan: WeekPlan; warnings: string[] }>("/api/replanner/quick-add", {
    method: "POST",
    body: JSON.stringify(data),
  });

// Feedback
export const postFeedback = (data: {
  log_entry: Record<string, unknown>;
  resolved_day?: Record<string, unknown>;
  status?: string;
}) =>
  request<{
    status: string;
    week_plan?: WeekPlan;
    limitation_suggestions?: unknown[];
    warning?: string;
  }>("/api/feedback", {
    method: "POST",
    body: JSON.stringify(data),
  });

// Outdoor
export const getOutdoorSpots = () =>
  request<{ spots: OutdoorSpot[] }>("/api/outdoor/spots");

export const addOutdoorSpot = (spot: {
  id?: string;
  name: string;
  discipline: string;
  typical_days?: string[];
  notes?: string;
}) =>
  request<{ status: string; spot: OutdoorSpot }>("/api/outdoor/spots", {
    method: "POST",
    body: JSON.stringify(spot),
  });

export const deleteOutdoorSpot = (spotId: string) =>
  request<{ status: string }>(`/api/outdoor/spots/${spotId}`, {
    method: "DELETE",
  });

export const postOutdoorLog = (session: Omit<OutdoorSession, "log_version">) =>
  request<{ status: string; log_path: string }>("/api/outdoor/log", {
    method: "POST",
    body: JSON.stringify(session),
  });

export const getOutdoorLogByDate = (date: string) =>
  request<{ session: OutdoorSession & { load_score: number } }>(`/api/outdoor/log/${date}`);

export const putOutdoorLog = (session: Omit<OutdoorSession, "log_version">) =>
  request<{ status: string; load_score: number }>("/api/outdoor/log", {
    method: "PUT",
    body: JSON.stringify(session),
  });

export const deleteOutdoorLog = (date: string) =>
  request<{ status: string; date: string }>(`/api/outdoor/log/${date}`, {
    method: "DELETE",
  });

export const getOutdoorSessions = (since?: string) =>
  request<{ sessions: OutdoorSession[]; count: number }>(
    `/api/outdoor/sessions${since ? `?since=${since}` : ""}`
  );

export const getOutdoorStats = (since?: string) =>
  request<OutdoorStats>(
    `/api/outdoor/stats${since ? `?since=${since}` : ""}`
  );

export const convertOutdoorSlot = (data: {
  date: string;
  new_location: string;
  gym_id?: string;
}) =>
  request<{ status: string; suggestions: Array<Record<string, unknown>> }>("/api/outdoor/convert-slot", {
    method: "POST",
    body: JSON.stringify(data),
  });

// Outdoor day (A226) — resolver + active session lifecycle
export const getOutdoorStrategy = (params: {
  day_type: string;
  discipline?: string;
  wall_angle?: string;
  route_length?: string;
  hold_style?: string;
  target_grade_relative?: string;
  condition_band?: string;
  macrocycle_phase?: string;
  use_current_phase?: boolean;
  lat?: number;
  lon?: number;
  date?: string;
}) => {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  });
  return request<OutdoorStrategyResponse>(`/api/outdoor/strategy?${q.toString()}`);
};

export const startOutdoorSession = (data: {
  date: string;
  spot_id?: string;
  spot_name?: string;
  discipline?: string;
  day_type?: string;
}) =>
  request<OutdoorSessionStartResponse>("/api/outdoor/session/start", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const finishOutdoorSession = (
  sessionId: string,
  data: Partial<OutdoorSession> & { spot_name: string; discipline: string; duration_minutes?: number },
) =>
  request<OutdoorSessionFinishResponse>(`/api/outdoor/session/${sessionId}/finish`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const cancelOutdoorSession = (sessionId: string) =>
  request<{ status: string }>(`/api/outdoor/session/${sessionId}`, {
    method: "DELETE",
  });

export const getActiveOutdoorSession = (date?: string) =>
  request<{ session: Record<string, unknown> }>(
    `/api/outdoor/session/active${date ? `?date=${date}` : ""}`,
  );

export const logOutdoorClimb = (
  sessionId: string,
  climb: { name: string; grade: string; attempts: { result: string; notes?: string }[]; style?: string; discipline?: string; at_min?: number },
) =>
  request<{ routes: Array<Record<string, unknown>>; count: number }>(
    `/api/outdoor/session/${sessionId}/log-climb`,
    { method: "POST", body: JSON.stringify(climb) },
  );

export const deleteOutdoorClimb = (sessionId: string, index: number) =>
  request<{ routes: Array<Record<string, unknown>>; count: number }>(
    `/api/outdoor/session/${sessionId}/climb/${index}`,
    { method: "DELETE" },
  );

export const replaceOutdoorRoutes = (sessionId: string, routes: Array<Record<string, unknown>>) =>
  request<{ routes: Array<Record<string, unknown>>; count: number }>(
    `/api/outdoor/session/${sessionId}/routes`,
    { method: "PUT", body: JSON.stringify({ routes }) },
  );

// User backup
export async function exportUserState(): Promise<void> {
  const authHeaders = await _getAuthHeaders();
  const res = await fetch(`${API_BASE}/api/user/export`, { headers: authHeaders });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const match = cd.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] || "climb-agent-backup.json";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const importUserState = (state: Record<string, unknown>) =>
  request<{ status: string }>("/api/user/import", {
    method: "POST",
    body: JSON.stringify(state),
  });

// Recovery code functions removed — Clerk handles account recovery

// Weekly Override (B42)
export const getWeeklyOverride = (weekStart: string) =>
  request<import("./types").WeeklyOverrideResponse>(`/api/weekly-override/${weekStart}`);

export const putWeeklyOverride = (weekStart: string, days: Record<string, {
  available: boolean;
  slots?: Record<string, { available: boolean; location: string; gym_id?: string | null }>;
}>) =>
  request<{ status: string; week_start: string; days: import("./types").DayOverviewEntry[] }>(`/api/weekly-override/${weekStart}`, {
    method: "PUT",
    body: JSON.stringify({ days }),
  });

export const deleteWeeklyOverride = (weekStart: string) =>
  request<{ status: string; week_start: string }>(`/api/weekly-override/${weekStart}`, {
    method: "DELETE",
  });

// Free Session (A136)
export const getFreeSessionSurfaces = () =>
  request<{
    surfaces: Array<{ id: string; name: string }>;
    gyms: Array<{ gym_id: string; name: string }>;
  }>("/api/free-session/surfaces");

export const getFreeSessionPresets = (surface: string) =>
  request<{
    presets: Array<{
      id: string;
      name: string;
      description: string;
      icon: string;
      target_grade: string | null;
      rest_seconds: number;
      target_climbs: string;
      duration: string;
      phase_compatibility: string;
      phase_tip: string;
    }>;
    free_mode_tip: string;
    phase_id: string;
  }>(`/api/free-session/presets?surface=${surface}`);

export const startFreeSession = (data: {
  date: string;
  surface: string;
  gym_id?: string;
  gym_name?: string;
  session_mode: string;
  preset_id?: string;
  context: string;
}) =>
  request<{
    session_id: string;
    phase_at_time: string;
    tip: string | null;
    target_grade: string | null;
    rest_seconds: number | null;
  }>("/api/free-session/start", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const logFreeClimb = (sessionId: string, data: {
  grade: string;
  status: string;
  attempts: number;
  style?: string;
  topped?: boolean;
  notes?: string;
}) =>
  request<{ index: number; logged_at: string }>(
    `/api/free-session/${sessionId}/log-climb`,
    { method: "POST", body: JSON.stringify(data) }
  );

export const deleteFreeClimb = (sessionId: string, climbIndex: number) =>
  request<{ status: string; climbs_remaining: number }>(
    `/api/free-session/${sessionId}/climb/${climbIndex}`,
    { method: "DELETE" }
  );

export const finishFreeSession = (sessionId: string, data: {
  overall_feel?: string;
  notes?: string;
  circuit?: {
    work_seconds: number;
    rest_seconds: number;
    target_exercises: number;
    completed_exercises: number;
    exercises_performed: string[];
  };
  mobility?: {
    completed_entries: Array<{ id: string; name: string; hold_seconds?: number }>;
    completed_count: number;
  };
}) =>
  request<{
    summary: {
      total_climbs: number;
      flashed: number;
      sent: number;
      attempted: number;
      max_grade_sent: string | null;
      max_grade_attempted: string | null;
      send_rate: number;
    };
    duration_minutes: number | null;
    load_score: number | null;
  }>(`/api/free-session/${sessionId}/finish`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const deleteFreeSession = (sessionId: string) =>
  request<{ status: string }>(`/api/free-session/${sessionId}`, {
    method: "DELETE",
  });

export const getFreeSessionHistory = (date: string) =>
  request<{ sessions: Array<Record<string, unknown>> }>(
    `/api/free-session/history?date=${date}`
  );

// Mobility & Stretching pool (A230)
export type MobilityEntry = {
  id: string;
  name: string;
  body_region: string;
  type: string;
  mode: "timed_hold" | "untimed_release";
  unilateral: boolean;
  hold_seconds_editable: boolean;
  pnf_capable: boolean;
  pre_performance_blocked: boolean;
  ux_flow: boolean;
  kb_validated: boolean;
  equipment_required: string[];
  priority: "high" | "medium" | "low";
  fatigue_cost: number;
  stress_tags: Record<string, string>;
  recency_group: string;
  image: string | null;
  prescription_defaults: {
    sets: number;
    reps: number | null;
    work_seconds: number | null;
    rest_between_reps_seconds: number | null;
    rest_between_sets_seconds: number | null;
    notes: string;
  };
  description: string;
  warning?: string; // GATE-2 soft warning, set server-side
};

export type MobilityRegion = {
  id: string;
  label: string;
  count: number;
  entries: MobilityEntry[];
};

export const getMobilityPool = (date?: string) =>
  request<{ regions: MobilityRegion[]; gate2_active: boolean }>(
    `/api/mobility/pool${date ? `?date=${date}` : ""}`
  );

// A231: guided flow — the system picks the stretches
export type MobilityFlowStep = {
  entry_id: string;
  name: string;
  body_region: string;
  side: "left" | "right" | null;
  set: number;
  set_count: number;
  seconds: number;
  kind: "hold" | "release" | "flow";
  cue: string;
  description: string;
};

export type MobilityFlowPlan = {
  steps: MobilityFlowStep[];
  entry_count: number;
  entry_ids: string[];
  total_seconds: number;
  rest_seconds: number;
  pace: string;
  gate2_active: boolean;
  excluded_pre_performance: string[];
};

export const getMobilityFlow = (params: {
  regions: string[];
  minutes: number;
  pace: string;
  rest: number;
  date?: string;
}) => {
  const q = new URLSearchParams({
    regions: params.regions.join(","),
    minutes: String(params.minutes),
    pace: params.pace,
    rest: String(params.rest),
  });
  if (params.date) q.set("date", params.date);
  return request<MobilityFlowPlan>(`/api/mobility/generate?${q.toString()}`);
};

// Reports
export const getWeeklyReport = (weekStart: string) =>
  request<WeeklyReport>(`/api/reports/weekly?week_start=${weekStart}`);

export const getMonthlyReport = (month: string) =>
  request<MonthlyReport>(`/api/reports/monthly?month=${month}`);

// Quotes
export const getDailyQuote = (context?: string) =>
  request<Quote>(`/api/quotes/daily${context ? `?context=${context}` : ""}`);

// Subscription
export type SubscriptionStatus = {
  status: string;
  is_active: boolean;
  trial_days_remaining: number | null;
  can_interact: boolean;
};

export const getSubscriptionStatus = () =>
  request<SubscriptionStatus>("/api/subscription/status");

export type CheckoutResponse = {
  checkout_url?: string;
  already_active?: boolean;
  status?: string;
  redirect_url?: string;
};

export const createCheckoutSession = (email?: string, priceId?: string) =>
  request<CheckoutResponse>("/api/subscription/checkout", {
    method: "POST",
    body: JSON.stringify({ email: email ?? null, price_id: priceId ?? null }),
  });

export const createBillingPortal = () =>
  request<{ portal_url: string }>("/api/subscription/portal", {
    method: "POST",
  });

// Custom Sessions (A206)
export const getCustomSessions = () =>
  request<{ sessions: CustomSessionSummary[]; count: number }>("/api/custom-session/list");

export const getCustomSession = (id: string) =>
  request<CustomSession>(`/api/custom-session/${id}`);

export const createCustomSession = (data: {
  name: string;
  tags: string[];
  exercises: CustomSessionExercise[];
}) =>
  request<CustomSession>("/api/custom-session", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateCustomSession = (id: string, data: {
  name: string;
  tags: string[];
  exercises: CustomSessionExercise[];
}) =>
  request<CustomSession>(`/api/custom-session/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deleteCustomSession = (id: string) =>
  request<{ deleted: string }>(`/api/custom-session/${id}`, {
    method: "DELETE",
  });

export const getBuilderExercises = (params?: { q?: string; domain?: string }) => {
  const sp = new URLSearchParams();
  if (params?.q) sp.set("q", params.q);
  if (params?.domain) sp.set("domain", params.domain);
  const qs = sp.toString();
  return request<{ exercises: BuilderExercise[]; count: number }>(
    `/api/custom-session/exercises${qs ? `?${qs}` : ""}`
  );
};

export const getBuilderBlocks = () =>
  request<{ warmup: WarmupCooldownBlock[]; cooldown: WarmupCooldownBlock[] }>(
    "/api/custom-session/blocks"
  );

// Body Part Picker (A213)
export interface BodyPartOption {
  id: string;
  label: string;
  description: string;
  icon: string;
  enabled: boolean;
  exercise_count: number;
  stub_duration_min: number;
}

export interface BodyPartEquipmentOption {
  mode: "bodyweight" | "home" | "gym" | "all";
  label: string;
  gym_id?: string;
}

export interface BodyPartPickerOptions {
  body_parts: BodyPartOption[];
  equipment_options: BodyPartEquipmentOption[];
}

export interface BodyPartSession {
  session_mode: "custom_build";
  build_kind: "body_parts";
  is_custom: true;
  name: string;
  body_parts_selected: string[];
  equipment_mode: string;
  gym_id?: string | null;
  include_cooldown: boolean;
  exercises: Array<{
    exercise_id: string;
    body_part: string;
    prescription: Record<string, unknown>;
    load_source?: string;
    suggested_external_load_kg?: number;
  }>;
  estimated_duration_minutes: number;
  estimated_load_score: number;
  intensity: string;
  tags: Record<string, boolean>;
  session_id?: string;
}

export const getBodyPartPickerOptions = (equipmentMode?: string, gymId?: string) => {
  const sp = new URLSearchParams();
  if (equipmentMode) sp.set("equipment_mode", equipmentMode);
  if (gymId) sp.set("gym_id", gymId);
  const qs = sp.toString();
  return request<BodyPartPickerOptions>(
    `/api/body-part-picker/options${qs ? `?${qs}` : ""}`
  );
};

export const previewBodyPartSession = (data: {
  body_parts: string[];
  equipment_mode: string;
  gym_id?: string | null;
  include_cooldown?: boolean;
  seed?: number;
}) =>
  request<BodyPartSession>("/api/body-part-picker/preview", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const startBodyPartSession = (data: {
  body_parts: string[];
  equipment_mode: string;
  gym_id?: string | null;
  include_cooldown?: boolean;
  seed?: number;
  target_date: string;
  slot?: string;
  location?: string;
}) =>
  request<{ session: BodyPartSession; week_plan: WeekPlan }>(
    "/api/body-part-picker/start",
    { method: "POST", body: JSON.stringify(data) }
  );

export const getBodyPartEstimate = (bodyParts: string[], includeCooldown = true) => {
  const sp = new URLSearchParams();
  sp.set("body_parts", bodyParts.join(","));
  sp.set("include_cooldown", String(includeCooldown));
  return request<{ estimated_duration_min: number }>(
    `/api/body-part-picker/estimate?${sp.toString()}`
  );
};

// A224 — Weather (live conditions + forecast-by-date)
export const getWeather = (lat: number, lon: number, date?: string) => {
  const sp = new URLSearchParams();
  sp.set("lat", String(lat));
  sp.set("lon", String(lon));
  if (date) sp.set("date", date);
  return request<Weather>(`/api/weather?${sp.toString()}`);
};

// A-COACH-V1a — LLM Coach (conversational layer, suggest-only)
export interface CoachMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
}

export const coachChat = (message: string) =>
  request<{ reply: string }>("/api/coach/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });

export const getCoachHistory = (limit = 50, before?: string) => {
  const sp = new URLSearchParams();
  sp.set("limit", String(limit));
  if (before) sp.set("before", before);
  return request<{ messages: CoachMessage[]; has_more: boolean }>(
    `/api/coach/history?${sp.toString()}`
  );
};
