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
  DailyTipResponse,
  MonthlyHeatmapData,
  MilestonesResponse,
  CustomSession,
  CustomSessionSummary,
  CustomSessionExercise,
  BuilderExercise,
  WarmupCooldownBlock,
  Weather,
  TestReminder,
  TestReminderOption,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Status used when we have a Clerk session but could not mint a token. */
export const AUTH_UNAVAILABLE_STATUS = 499;

/**
 * A245 C-2 (F9, client half) — this used to swallow every Clerk failure and
 * send the request WITHOUT an Authorization header.
 *
 * The backend half is already closed: since B285, `_auth_enforced()` makes an
 * unauthenticated request 401 instead of serving EMPTY_TEMPLATE with HTTP 200.
 * But the client should not fire a request it knows is unauthenticated in the
 * first place — doing so turned "Clerk could not refresh the token right now"
 * into a round trip whose only possible outcome is a 401, which then triggers
 * the sign-in redirect (F51) and drops the user out of the app.
 *
 * Distinction that matters: NO session means genuinely signed out (let it
 * through, the backend answers 401 authoritatively). A session that exists but
 * cannot produce a token is a transient local failure — raise, do not send.
 */
async function _getAuthHeaders(): Promise<Record<string, string>> {
  if (typeof window === "undefined") return {};
  const session = window.Clerk?.session;
  if (!session) return {};
  try {
    const token = await session.getToken();
    if (token) return { Authorization: `Bearer ${token}` };
  } catch {
    // fall through to the throw below
  }
  throw new ApiError(
    AUTH_UNAVAILABLE_STATUS,
    "Could not verify your session. Check your connection and try again.",
  );
}

/**
 * F7 (A245) — nessuna fetch deve poter restare appesa per sempre.
 *
 * Su rete scarsa una connessione TCP stallata non fallisce mai: il `retry: 1`
 * globale di React Query non scatta, lo spinner gira all'infinito e l'unica via
 * d'uscita è ricaricare la PWA — esattamente nel contesto d'uso primario
 * (palestra/falesia senza campo).
 *
 * `AbortSignal.any()` non è usata di proposito: è iOS 17.4+ e gli utenti PWA
 * iPhone sono il target dichiarato. Il combinatore manuale copre tutti i device.
 */
const DEFAULT_TIMEOUT_MS = 15_000;
/** Endpoint legittimamente lenti (LLM o generazione macrociclo). */
const SLOW_PATHS = ["/api/coach/", "/api/onboarding/complete", "/api/macrocycle/"];
const SLOW_TIMEOUT_MS = 60_000;

function timeoutFor(path: string): number {
  return SLOW_PATHS.some((p) => path.startsWith(p)) ? SLOW_TIMEOUT_MS : DEFAULT_TIMEOUT_MS;
}

/** Combina il signal del chiamante (React Query) con un timeout locale. */
function linkedAbort(caller: AbortSignal | null | undefined, ms: number) {
  const ctrl = new AbortController();
  const timer = setTimeout(
    () => ctrl.abort(new DOMException("Request timed out", "TimeoutError")),
    ms,
  );
  const onAbort = () => ctrl.abort(caller?.reason);
  if (caller) {
    if (caller.aborted) ctrl.abort(caller.reason);
    else caller.addEventListener("abort", onAbort, { once: true });
  }
  return {
    signal: ctrl.signal,
    cleanup: () => {
      clearTimeout(timer);
      caller?.removeEventListener("abort", onAbort);
    },
  };
}

/** Status sintetico per un fallimento di rete/timeout (nessuna risposta HTTP). */
export const NETWORK_ERROR_STATUS = 0;

async function request<T>(path: string, options?: RequestInit, _isRetry = false): Promise<T> {
  const authHeaders = await _getAuthHeaders();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders,
    ...((options?.headers as Record<string, string>) || {}),
  };
  const { signal, cleanup } = linkedAbort(options?.signal, timeoutFor(path));
  try {
    return await _send<T>(path, options, headers, signal, _isRetry);
  } catch (err) {
    // Il timeout è nostro; un abort del chiamante (unmount, query cancellata)
    // deve propagarsi invariato perché React Query lo riconosca.
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new ApiError(
        NETWORK_ERROR_STATUS,
        "Network too slow — check your connection and try again.",
      );
    }
    throw err;
  } finally {
    cleanup();
  }
}

async function _send<T>(
  path: string,
  options: RequestInit | undefined,
  headers: Record<string, string>,
  signal: AbortSignal,
  _isRetry: boolean,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    signal,
  });
  // B155: on 401, retry once after 500ms — Clerk token may not be ready yet.
  // Gli header vanno RIcostruiti: il punto del retry è raccogliere il token che
  // al primo tentativo non c'era ancora.
  if (res.status === 401 && !_isRetry && typeof window !== "undefined") {
    console.warn(`[B155] 401 on ${path} — retrying in 500ms (Clerk may still be loading)`);
    await new Promise((r) => setTimeout(r, 500));
    const retryHeaders = { ...headers, ...(await _getAuthHeaders()) };
    return _send<T>(path, options, retryHeaders, signal, true);
  }
  if (res.status === 401 && typeof window !== "undefined") {
    // A245 C-3 (F51) — this was an unconditional `window.location.href =
    // "/sign-in"`: a full document load that throws away every bit of
    // in-memory state, and offline cannot even complete because /sign-in is
    // not in the precache. The user was left on a dead white page.
    //
    // Offline, a 401 is not trustworthy evidence that the session ended, so
    // surface it as an error the caller can render and leave the user where
    // they are. Online, still send them to sign in — but via the router-free
    // soft path so the SW can serve it.
    if (navigator.onLine === false) {
      throw new ApiError(401, "Session could not be verified while offline.");
    }
    window.location.href = "/sign-in";
    throw new ApiError(401, "Session expired");
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

// B293 — server-side wizard draft (survives a forced re-auth mid-wizard)
export type OnboardingDraft = {
  data: OnboardingData;
  deepest_step: number;
  saved_at: number | null;
};
export const getOnboardingDraft = () =>
  request<{ draft: OnboardingDraft | null }>("/api/onboarding/draft");
export const putOnboardingDraft = (draft: OnboardingDraft) =>
  request<{ status: string }>("/api/onboarding/draft", {
    method: "PUT",
    body: JSON.stringify(draft),
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
    /**
     * A245 G-4 (F52) — the periodic retest reminder.
     *
     * The backend emits this every ~6 weeks (`should_show_test_reminder`,
     * planner_v2), and a whole endpoint exists to answer it
     * (`POST /api/week/test-reminder-response`, with confirm / postpone /
     * skip). It was absent from this type and read by NOTHING in the client, so
     * the reminder has never reached a user: periodic recalibration — a pillar
     * of the 4-3-2-1 methodology — silently never happens.
     *
     * Typed here so the payload stops being invisible. The card that shows it
     * is new user-facing surface and is tracked as A-TEST-REMINDER-UI.
     */
    test_reminder?: TestReminder;
  }>(`/api/week/${weekNum}${qs ? `?${qs}` : ""}`);
};

/**
 * A246 — answer the periodic retest reminder.
 *
 * The endpoint has existed since the reminder was built; nothing ever called
 * it, because no UI ever showed the reminder (A245 G-4 / F52).
 *
 * - `confirm`         → next week generation injects the test session
 * - `postpone_1_week` → ask again next week
 * - `skip_cycle`      → ask again in 6 weeks
 */
export const respondToTestReminder = (option: TestReminderOption) =>
  request<{ status: string; action: string; next_reminder_week?: number }>(
    "/api/week/test-reminder-response",
    { method: "POST", body: JSON.stringify({ option }) },
  );

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

// B287/R-5: quick-add runs _reconcile, so an added session can be eased
// (downgraded) to respect the 48h finger gap or the weekly hard-session cap.
// The backend describes each change here so the UI can explain it.
export type QuickAddAdjustment = {
  date: string;
  slot?: string;
  action: string; // "downgraded"
  reason: string; // "finger_spacing_downshift" | "hard_cap_downshift"
  previous_session_id?: string;
  session_id?: string;
};

// B-QUICKADD-ADJUSTMENTS: turn the machine-readable downshift reasons into one
// plain-language line, so the user understands why the session they added came
// back lighter than the one they picked (instead of silently getting a
// different card). Returns null when nothing was adjusted.
export function describeQuickAddAdjustments(adjustments: QuickAddAdjustment[] | undefined): string | null {
  if (!adjustments || adjustments.length === 0) return null;
  const reasons = new Set(adjustments.map((a) => a.reason));
  const parts: string[] = [];
  if (reasons.has("finger_spacing_downshift")) {
    parts.push("to protect finger recovery (a hard finger session was within 48h)");
  }
  if (reasons.has("hard_cap_downshift")) {
    parts.push("to stay within your weekly hard-session limit");
  }
  if (parts.length === 0) parts.push("to keep your week balanced"); // unknown reason fallback
  return `Eased to a lighter session ${parts.join(" and ")}.`;
}

// A254: a finger downshift is injury protection (48h tendon/pulley recovery) —
// forcing past it warrants an explicit confirm. A cap-only downshift is just
// volume, so a one-tap toast action is enough.
export function quickAddHasFingerRisk(adjustments: QuickAddAdjustment[] | undefined): boolean {
  return !!adjustments?.some((a) => a.reason === "finger_spacing_downshift");
}

export const quickAddSession = (data: {
  session_id: string;
  target_date: string;
  slot?: string;
  location?: string;
  phase_id?: string;
  week_plan: WeekPlan;
  gym_id?: string;
  force?: boolean; // A254: keep the hard session past the finger gap / hard cap
}) =>
  request<{ week_plan: WeekPlan; warnings: string[]; adjustments: QuickAddAdjustment[] }>(
    "/api/replanner/quick-add",
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );

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

// Monthly heatmap (A236)
export const getMonthlyHeatmap = (month: string) =>
  request<MonthlyHeatmapData>(`/api/reports/heatmap?month=${month}`);

// Milestones (A239)
export const getMilestones = () =>
  request<MilestonesResponse>("/api/milestones");

export const markMilestoneSeen = (milestoneId: string) =>
  request<{ ok: boolean }>(`/api/milestones/${encodeURIComponent(milestoneId)}/seen`, {
    method: "POST",
  });

// Daily tips (A234)
export const getDailyTip = (date?: string) =>
  request<DailyTipResponse>(`/api/tips/daily${date ? `?date=${date}` : ""}`);

export const dismissDailyTip = (tipId: string, date?: string) =>
  request<{ ok: boolean }>(
    `/api/tips/${tipId}/dismiss${date ? `?date=${date}` : ""}`,
    { method: "POST" },
  );

// Subscription
export type SubscriptionStatus = {
  status: string;
  is_active: boolean;
  trial_days_remaining: number | null;
  can_interact: boolean;
  has_payment_method?: boolean; // A232: card on file (synced by Stripe webhooks)
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
  // B306 — persisted adhoc-session payload as returned by /coach/history
  // (null/absent on plain turns); hydrated into `adhocSession` on load.
  adhoc_session?: AdhocSessionPreview | null;
  // A243 — structured adhoc-session card payload (client render key).
  adhocSession?: AdhocSessionPreview;
}

// A243 — deterministic adhoc session preview from POST /api/coach/adhoc-session.
export interface AdhocSessionExercisePreview {
  exercise_id: string;
  name: string;
  sets: number;
  reps: number | null;
  work_seconds: number | null;
  rest_between_sets_seconds: number | null;
  rest_between_reps_seconds: number | null;
  load_kg: number;
  notes: string;
}

export interface AdhocSessionPreview {
  adhoc: true;
  name: string;
  tags: string[];
  exercises: AdhocSessionExercisePreview[];
  estimated_load_score: number;
  estimated_duration_minutes: number;
  explanation: string;
  effort_band: string | null;
  phase: string | null;
  intent: {
    equipment_set: string;
    focus: string;
    secondary_focus?: string | null;
    gym_name?: string | null;
    minutes: number;
    energy: string;
  };
}

export const coachAdhocSession = (message: string) =>
  request<{ adhoc: boolean; session?: AdhocSessionPreview; summary?: string }>(
    "/api/coach/adhoc-session",
    { method: "POST", body: JSON.stringify({ message }) },
  );

export const coachChat = (
  message: string,
  coords?: { lat: number; lon: number } | null
) =>
  request<{ reply: string }>("/api/coach/chat", {
    method: "POST",
    body: JSON.stringify({ message, ...(coords ?? {}) }),
  });

// A-COACH-V1b — deterministic context-aware question chips
export const getCoachSuggestions = () =>
  request<{ suggestions: string[] }>("/api/coach/suggestions");

export const getCoachHistory = (limit = 50, before?: string) => {
  const sp = new URLSearchParams();
  sp.set("limit", String(limit));
  if (before) sp.set("before", before);
  return request<{ messages: CoachMessage[]; has_more: boolean }>(
    `/api/coach/history?${sp.toString()}`
  );
};
