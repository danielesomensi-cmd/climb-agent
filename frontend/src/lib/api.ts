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
export const getWeek = (weekNum: number) =>
  request<{ week_num: number; phase_id: string; week_plan: WeekPlan }>(`/api/week/${weekNum}`);

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
