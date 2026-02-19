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

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
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

// Catalog
export const getExercises = () =>
  request<{ exercises: Exercise[]; count: number }>("/api/catalog/exercises");
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
export const generateMacrocycle = (startDate?: string, totalWeeks = 12) =>
  request<{ macrocycle: Macrocycle }>("/api/macrocycle/generate", {
    method: "POST",
    body: JSON.stringify({ start_date: startDate, total_weeks: totalWeeks }),
  });

// Week
export const getWeek = (weekNum: number, force?: boolean) =>
  request<{ week_num: number; phase_id: string; week_plan: WeekPlan }>(
    `/api/week/${weekNum}${force ? "?force=true" : ""}`
  );

// Session
export const resolveSession = (sessionId: string, context?: Record<string, unknown>) =>
  request<{ resolved: ResolvedSession }>("/api/session/resolve", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, context }),
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
      intensity: string;
      estimated_load_score: number;
      reason: string;
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

export const getOutdoorSessions = (since?: string) =>
  request<{ sessions: OutdoorSession[]; count: number }>(
    `/api/outdoor/sessions${since ? `?since=${since}` : ""}`
  );

export const getOutdoorStats = (since?: string) =>
  request<OutdoorStats>(
    `/api/outdoor/stats${since ? `?since=${since}` : ""}`
  );

// Reports
export const getWeeklyReport = (weekStart: string) =>
  request<WeeklyReport>(`/api/reports/weekly?week_start=${weekStart}`);

export const getMonthlyReport = (month: string) =>
  request<MonthlyReport>(`/api/reports/monthly?month=${month}`);

// Quotes
export const getDailyQuote = (context?: string) =>
  request<Quote>(`/api/quotes/daily${context ? `?context=${context}` : ""}`);
