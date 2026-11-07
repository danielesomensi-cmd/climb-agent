/**
 * B414 (INBOX-2026-11-04-ORPHAN) — the session being logged is not on that day
 * of the plan any more (removed or replaced since the phone loaded it: the
 * treadmill of 04/11, swapped for a custom by the coach while the player ran
 * from a cached copy). Nothing was saved. Two shapes reach the client:
 *  - `/api/replanner/events` (B414 step 4): 422 whose detail is the engine's
 *    `SessionNotInPlan` sentence ("Session not in the plan: day=… session_ref=…");
 *  - `/api/feedback` (B414 step 27): 409 with a structured
 *    `detail: {code: "session_not_in_plan", date, session_id, day_sessions}`.
 * Never a `StalePlanError` (that one carries `current_revision`).
 *
 * Kept apart from api.ts (which throws `SessionNotInPlanError`): code that only
 * recognizes the error — the replay, the player — needs nothing of the client.
 */
export const SESSION_NOT_IN_PLAN = "session_not_in_plan";
export const SESSION_NOT_IN_PLAN_MESSAGE =
  "This session is no longer in your plan for that day — nothing was saved.";

export interface DaySessionRef {
  session_id: string;
  slot?: string | null;
  status?: string | null;
  name?: string | null;
}

export interface SessionNotInPlanInfo {
  date?: string | null;
  session_id?: string | null;
  day_sessions?: DaySessionRef[] | null;
}

/** The orphan refusal in a failed response, or null. Pure. */
export function parseSessionNotInPlan(status: number, body: string): SessionNotInPlanInfo | null {
  if (status !== 409 && status !== 422) return null;
  let detail: unknown;
  try {
    detail = (JSON.parse(body) as { detail?: unknown }).detail;
  } catch {
    return null;
  }
  if (detail && typeof detail === "object" && (detail as { code?: unknown }).code === SESSION_NOT_IN_PLAN) {
    const d = detail as { date?: string; session_id?: string; day_sessions?: DaySessionRef[] };
    return { date: d.date ?? null, session_id: d.session_id ?? null, day_sessions: d.day_sessions ?? null };
  }
  if (status === 422 && typeof detail === "string" && detail.startsWith("Session not in the plan")) {
    const date = /day=(\d{4}-\d{2}-\d{2})/.exec(detail)?.[1] ?? null;
    const ref = /session_ref=(\S+)/.exec(detail)?.[1] ?? null;
    return { date, session_id: ref && ref !== "None" ? ref : null, day_sessions: null };
  }
  return null;
}

/** What `isSessionNotInPlan` narrows to (the fields of api.ts's `SessionNotInPlanError`). */
export interface SessionNotInPlanLike extends Error {
  code: typeof SESSION_NOT_IN_PLAN;
  status: number;
  date: string | null;
  sessionId: string | null;
  daySessions: DaySessionRef[] | null;
}

/** True for the error `request()` throws on the orphan refusal. */
export function isSessionNotInPlan(err: unknown): err is SessionNotInPlanLike {
  return err instanceof Error && (err as { code?: unknown }).code === SESSION_NOT_IN_PLAN;
}
