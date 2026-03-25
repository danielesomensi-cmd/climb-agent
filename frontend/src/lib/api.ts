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
  WeeklyReport,
  MonthlyReport,
  Quote,
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
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
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
export const completeOnboarding = (data: OnboardingData) =>
  request<{ profile: AssessmentProfile; macrocycle: Macrocycle }>("/api/onboarding/complete", {
    method: "POST",
    body: JSON.stringify(data),
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

// Week
export const getWeek = (weekNum: number, force?: boolean, preserveBefore?: string) => {
  const params = new URLSearchParams();
  if (force) params.set("force", "true");
  if (preserveBefore) params.set("preserve_before", preserveBefore);
  const qs = params.toString();
  return request<{ week_num: number; phase_id: string; week_plan: WeekPlan }>(
    `/api/week/${weekNum}${qs ? `?${qs}` : ""}`
  );
};

// Session
export const resolveSession = (sessionId: string, context?: Record<string, unknown>) =>
  request<{ resolved: ResolvedSession }>("/api/session/resolve", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, context }),
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
  request<{ status: string; state: UserState }>("/api/feedback", {
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

// Reports
export const getWeeklyReport = (weekStart: string) =>
  request<WeeklyReport>(`/api/reports/weekly?week_start=${weekStart}`);

export const getMonthlyReport = (month: string) =>
  request<MonthlyReport>(`/api/reports/monthly?month=${month}`);

// Quotes
export const getDailyQuote = (context?: string) =>
  request<Quote>(`/api/quotes/daily${context ? `?context=${context}` : ""}`);
