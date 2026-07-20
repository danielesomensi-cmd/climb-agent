import type { GuidedExercise, GuidedSessionState } from "@/lib/types";

const MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours

/**
 * A245 B-2 — this used to return `guided_session_clerk_` for every signed-in
 * user: the LITERAL string "clerk", never the real id. On a shared device (or
 * after a recovery-code import) user A's in-progress session was readable and
 * writable as user B's. Harmless-looking while it only held guided progress,
 * fatal once `state`/`week` are persisted under the same convention — so the
 * scope is now the real Clerk user id everywhere.
 */
export function getKeyPrefix(): string {
  if (typeof window === "undefined") return `guided_session_${ANON_SCOPE}_`;
  const userId = window.Clerk?.user?.id;
  // `anon` is a distinct scope, NOT one of the legacy prefixes: local dev and
  // the legacy-UUID fallback must keep working without being purged below.
  return `guided_session_${userId ?? ANON_SCOPE}_`;
}

const ANON_SCOPE = "anon";

/** Unscoped prefixes written before the fix above. */
const LEGACY_PREFIXES = ["guided_session__", "guided_session_clerk_"];

/**
 * Drop every unscoped guided-session key.
 *
 * Deliberately a PURGE and not a migration: re-keying legacy data onto the
 * currently signed-in user is exactly the leak we are closing — on a shared
 * device it would hand A's session to whoever signs in next. The cost is
 * losing a session that was literally mid-workout across one deploy; those
 * entries expire in 24h anyway.
 */
export function purgeLegacyGuidedKeys(): void {
  if (typeof window === "undefined") return;
  try {
    const doomed: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && LEGACY_PREFIXES.some((p) => key.startsWith(p))) doomed.push(key);
    }
    doomed.forEach((k) => localStorage.removeItem(k));
  } catch {
    // Private mode / storage disabled — nothing to purge.
  }
}

export interface InProgressSession {
  key: string;
  state: GuidedSessionState;
  date: string;
  sessionId: string;
  completedCount: number;
  totalCount: number;
}

/**
 * Scan localStorage for the most recent in-progress guided session.
 * Returns null if none found, or if all candidates are stale (> 24h)
 * or already submitted (feedback_pending / completed).
 */
export function getInProgressSession(): InProgressSession | null {
  if (typeof window === "undefined") return null;

  const prefix = getKeyPrefix();
  const now = Date.now();
  let best: InProgressSession | null = null;

  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (!key || !key.startsWith(prefix)) continue;

    try {
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      const saved = JSON.parse(raw) as GuidedSessionState;

      // Skip completed/pending-feedback sessions
      if (saved.submitStatus === "feedback_pending" || saved.submitStatus === "completed") continue;

      // Skip stale sessions (> 24h)
      if (saved.startedAt) {
        const age = now - new Date(saved.startedAt).getTime();
        if (age > MAX_AGE_MS) continue;
      }

      // Check genuinely in-progress: at least one exercise done/skipped, but not all
      const completed = saved.exercises.filter((ex) => ex.status !== "pending").length;
      const total = saved.exercises.length;
      if (completed === 0 && saved.currentIndex === 0) continue; // fresh, never started
      if (completed === total) continue; // fully done

      // Pick most recent by startedAt
      if (!best || saved.startedAt > best.state.startedAt) {
        best = {
          key,
          state: saved,
          date: saved.date,
          sessionId: saved.sessionId,
          completedCount: completed,
          totalCount: total,
        };
      }
    } catch {
      // Ignore malformed entries
    }
  }

  return best;
}

/**
 * Check if a specific session has saved progress in localStorage.
 */
export function hasSavedProgress(date: string, sessionId: string): boolean {
  if (typeof window === "undefined") return false;
  const prefix = getKeyPrefix();
  const key = `${prefix}${date}_${sessionId}`;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return false;
    const saved = JSON.parse(raw) as GuidedSessionState;
    // Has real progress (not a fresh empty session)
    return saved.exercises.some((ex) => ex.status !== "pending") || saved.currentIndex > 0;
  } catch {
    return false;
  }
}

/**
 * Remove a specific session's saved state from localStorage.
 */
export function clearSavedSession(date: string, sessionId: string): void {
  if (typeof window === "undefined") return;
  const prefix = getKeyPrefix();
  const key = `${prefix}${date}_${sessionId}`;
  localStorage.removeItem(key);
}

/**
 * B283: build GuidedSessionState from a flat CustomSessionExercise-shaped
 * list (saved custom sessions, adhoc coach sessions, body-part inline
 * sessions). Custom sessions now run through the REAL guided player — the
 * minimal A211 playback page is retired. Exercises may carry catalog display
 * enrichment (name, cues, video_url, load_model, category — B283 backend);
 * everything degrades gracefully when absent.
 */
export function buildGuidedStateFromExercises(
  sessionId: string,
  sessionName: string,
  date: string,
  exList: Array<Record<string, unknown>>,
): GuidedSessionState | null {
  if (exList.length === 0) return null;

  const exercises: GuidedExercise[] = exList.map((ex) => {
    const exerciseId = (ex.exercise_id as string) ?? "";
    const name =
      (ex.name as string) ??
      exerciseId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    const loadKg = typeof ex.load_kg === "number" ? (ex.load_kg as number) : undefined;
    return {
      exerciseId,
      name,
      category: (ex.category as string) ?? "",
      blockUid: (ex.body_part as string) ?? (ex.module_role as string) ?? "",
      loadModel: (ex.load_model as string) ?? "",
      prescription: {
        sets: ex.sets as number | undefined,
        reps: ex.reps != null ? (ex.reps as string | number) : undefined,
        workSeconds: ex.work_seconds as number | undefined,
        restBetweenRepsSeconds: ex.rest_between_reps_seconds as number | undefined,
        restSeconds: ex.rest_between_sets_seconds as number | undefined,
        loadKg,
        notes: ex.notes as string | undefined,
      },
      suggested: {
        // Show the stored load as the suggested weight (remembered value from
        // working_loads via the builder proposal, or the user's own entry).
        externalLoadKg:
          (ex.suggested_external_load_kg as number | undefined) ??
          (loadKg != null && loadKg > 0 ? loadKg : undefined),
        totalLoadKg: ex.suggested_total_load_kg as number | undefined,
        loadSource: ex.load_source as string | undefined,
      },
      cues: (ex.cues as string[] | undefined) ?? undefined,
      videoUrl: (ex.video_url as string | undefined) ?? undefined,
      status: "pending",
      feedbackLabel: "ok",
    };
  });

  return {
    version: 1,
    date,
    sessionId,
    sessionName,
    startedAt: new Date().toISOString(),
    currentIndex: 0,
    exercises,
  };
}

/**
 * B283: persist a guided state under the canonical localStorage key,
 * preserving a prior startedAt (B197 — duration must not reset on re-entry).
 */
export function saveGuidedState(state: GuidedSessionState): void {
  if (typeof window === "undefined") return;
  const key = `${getKeyPrefix()}${state.date}_${state.sessionId}`;
  try {
    const raw = localStorage.getItem(key);
    if (raw) {
      const prior = JSON.parse(raw) as GuidedSessionState;
      if (prior?.startedAt) state.startedAt = prior.startedAt;
    }
  } catch {
    /* fresh startedAt */
  }
  localStorage.setItem(key, JSON.stringify(state));
}
