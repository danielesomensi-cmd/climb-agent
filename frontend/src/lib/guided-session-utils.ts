import type { GuidedExercise, GuidedSessionState } from "@/lib/types";
import { anchoredLoadNotes } from "@/lib/anchored-load";
import { asMeasure } from "@/lib/measured-feedback";
import { asLadder } from "@/lib/bw-ladder";
import { pickLoadUnit } from "@/lib/load-units";

/** A298: "custom_cs_ab12" → "cs_ab12" (the promotion tap rewrites that session). */
function customSessionIdOf(sessionId: string): string | undefined {
  return sessionId.startsWith("custom_") ? sessionId.slice("custom_".length) : undefined;
}

const MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours

const ANON_SCOPE = "anon";

/**
 * B397 G1 — the SAME key as `LAST_USER_KEY` in query-persist (B292b): the last
 * user Clerk positively identified on this device. Not a credential — every
 * API call still needs a real Clerk token. b397-resume-key.test couples the
 * two modules, so a rename on either side fails loudly.
 */
export const LAST_USER_KEY = "climb-agent-last-user";

function readLastUser(): string | null {
  try {
    return window.localStorage.getItem(LAST_USER_KEY);
  } catch {
    return null;
  }
}

function rememberLastUser(userId: string): void {
  try {
    if (window.localStorage.getItem(LAST_USER_KEY) !== userId) {
      window.localStorage.setItem(LAST_USER_KEY, userId);
    }
  } catch {
    /* private mode: the fallback simply stays unavailable */
  }
}

/**
 * B397 G1 — who owns the guided scope right now.
 *
 * Clerk.js loads from the network, so `window.Clerk.user` is missing for the
 * first few hundred ms of every cold open — and forever when the PWA opens
 * offline. Reading it alone sent a reload mid-session to the `anon` scope: the
 * guided page found nothing and bounced to /today, the resume banner stayed
 * hidden and, offline, Start began again from zero.
 *
 *  - Clerk knows a user → that user (authoritative), remembered for later.
 *  - Clerk loaded and says nobody → `null` (signed out: `anon`).
 *  - Clerk not ready → the last user it identified on this device, the same
 *    trust the offline plan cache already relies on (B292b). `confirmed:
 *    false` tells callers to re-check once Clerk answers: the guided page drops
 *    a session whose owner Clerk then contradicts.
 */
export function guidedScopeOwner(): { userId: string | null; confirmed: boolean } {
  if (typeof window === "undefined") return { userId: null, confirmed: false };
  const clerk = window.Clerk;
  const clerkUserId = clerk?.user?.id;
  if (clerkUserId) {
    rememberLastUser(clerkUserId);
    return { userId: clerkUserId, confirmed: true };
  }
  if (clerk?.loaded) return { userId: null, confirmed: true };
  return { userId: readLastUser(), confirmed: false };
}

function prefixFor(userId: string | null): string {
  // `anon` is a distinct scope, NOT one of the legacy prefixes: local dev and
  // the legacy-UUID fallback must keep working without being purged below.
  return `guided_session_${userId ?? ANON_SCOPE}_`;
}

/**
 * A245 B-2 — this used to return `guided_session_clerk_` for every signed-in
 * user: the LITERAL string "clerk", never the real id. On a shared device (or
 * after a state import) user A's in-progress session was readable and
 * writable as user B's. Harmless-looking while it only held guided progress,
 * fatal once `state`/`week` are persisted under the same convention — so the
 * scope is now the real Clerk user id everywhere.
 *
 * B397 G1 — the key FORMAT is unchanged (`guided_session_<userId>_`), so every
 * session already saved under the real id is found as-is: nothing to migrate.
 * What changed is the fallback while Clerk is not ready (see
 * guidedScopeOwner). Entries already sitting under `anon` are deliberately NOT
 * adopted: nothing records who wrote them, and handing them to whoever signs
 * in next is exactly the A245 B-2 leak.
 */
export function getKeyPrefix(): string {
  return prefixFor(guidedScopeOwner().userId);
}

/**
 * B290 (closes F54) — THE key builder for guided session state.
 *
 * Every producer must call this. Three separate inline copies existed; when
 * A245 B-2 fixed one of them, writers and readers silently stopped agreeing.
 */
export function guidedStorageKey(date: string, sessionId: string): string {
  return `${getKeyPrefix()}${date}_${sessionId}`;
}

export interface LoadedGuidedSession {
  /** The exact key the state was read from: every later write goes there. */
  key: string;
  /** Owner of that key (`null` = `anon`), to compare with Clerk's answer. */
  owner: string | null;
  state: GuidedSessionState;
}

/**
 * B397 G1 — read a guided session and PIN the key it came from.
 *
 * The player used to rebuild the key on every save. Loaded under the
 * remembered user while Clerk was still booting, a later save would land under
 * whoever Clerk named next — copying one user's session into another's scope.
 */
export function loadGuidedSession(date: string, sessionId: string): LoadedGuidedSession | null {
  if (typeof window === "undefined") return null;
  const owner = guidedScopeOwner().userId;
  const key = `${prefixFor(owner)}${date}_${sessionId}`;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    return { key, owner, state: JSON.parse(raw) as GuidedSessionState };
  } catch {
    return null;
  }
}

/**
 * B397 G7 — body weight for the test sessions' total-load maths, from the
 * `/api/state` payload (the `['state']` cache or a fresh GET: same shape).
 */
export function bodyweightFromState(state: unknown): number | undefined {
  const assessment = (state as { assessment?: { body?: { weight_kg?: unknown } } } | null | undefined)
    ?.assessment;
  const bw = assessment?.body?.weight_kg;
  return typeof bw === "number" && bw > 0 ? bw : undefined;
}

/**
 * Prefixes written before every producer was unified on `getKeyPrefix()`.
 *
 * `guided_session_clerk_` is in here because B290 found the guided page and
 * SessionCard still building it inline: they were the WRITERS while the readers
 * in this module had already moved to the real user id.
 */
export const LEGACY_PREFIXES = ["guided_session__", "guided_session_clerk_"];

/**
 * Move any legacy-keyed guided session onto the current user's key.
 *
 * B290 — this used to be `purgeLegacyGuidedKeys()`, and deleting was the right
 * call in A245 B-2: those keys then held only STALE data of ambiguous
 * ownership, so re-keying it onto whoever signed in next would have been the
 * very leak we were closing.
 *
 * That reasoning stopped holding the moment the fix shipped half-applied. The
 * writers kept using `guided_session_clerk_`, so the prefix stopped meaning
 * "old data from before the fix" and started meaning "the session this user is
 * in the middle of, written minutes ago". Purging it deleted live sessions and
 * pending offline feedback on every app open.
 *
 * Guards that keep the original leak closed:
 *  - runs ONLY with a real signed-in user id (never onto `anon`);
 *  - never overwrites an existing key for the current user;
 *  - skips entries older than the 24h guided TTL, so genuinely stale data from
 *    a previous owner of the device is dropped rather than adopted.
 *
 * Note there is no separate "pending feedback" store to migrate: the guided
 * player records it as `submitStatus: "feedback_pending"` INSIDE the session
 * state, so moving the session moves the queued feedback with it.
 */
export function migrateLegacyGuidedKeys(): void {
  if (typeof window === "undefined") return;
  const userId = window.Clerk?.user?.id;
  if (!userId) return; // no identified owner → leave it alone, do not adopt

  const prefix = `guided_session_${userId}_`;
  const now = Date.now();
  try {
    const legacy: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && LEGACY_PREFIXES.some((p) => key.startsWith(p))) legacy.push(key);
    }

    for (const key of legacy) {
      const raw = localStorage.getItem(key);
      if (raw === null) continue;

      const suffix = key.slice(key.indexOf("_", "guided_session_".length) + 1);
      const target = `${prefix}${suffix}`;

      let keep = true;
      try {
        const saved = JSON.parse(raw) as GuidedSessionState;
        if (saved?.startedAt && now - new Date(saved.startedAt).getTime() > MAX_AGE_MS) {
          keep = false;
        }
      } catch {
        keep = false; // unparseable → not worth adopting
      }

      if (keep && localStorage.getItem(target) === null) {
        localStorage.setItem(target, raw);
      }
      localStorage.removeItem(key);
    }
  } catch {
    // Private mode / storage disabled — nothing to migrate.
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
 * A299: the `suggested` limit fields of a flat custom/adhoc row — present only
 * when the read attached a target (`log_problems` + `target_grade`).
 */
export function limitSuggestedFields(
  ex: Record<string, unknown>,
): Partial<GuidedExercise["suggested"]> {
  const target = typeof ex.target_grade === "string" ? ex.target_grade : undefined;
  if (ex.log_problems !== true || !target) return {};
  const options = Array.isArray(ex.surface_options)
    ? (ex.surface_options as unknown[]).filter((o): o is string => typeof o === "string")
    : undefined;
  return {
    grade: target,
    gradeLow: typeof ex.target_grade_low === "string" ? ex.target_grade_low : undefined,
    gradeScale: "font",
    logProblems: true,
    surface: typeof ex.surface_selected === "string" ? ex.surface_selected : undefined,
    surfaceOptions: options && options.length > 0 ? options : undefined,
    surfaceTargets:
      ex.surface_targets && typeof ex.surface_targets === "object"
        ? (ex.surface_targets as Record<string, { target_grade?: string; target_grade_low?: string }>)
        : undefined,
  };
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
      loadUnit: pickLoadUnit(ex.load_unit),
      // B351: the server stamps alt_sides from the catalog on every custom
      // instance (B324); dropping it here ran Pallof/Copenhagen on one side only.
      altSides: ex.alt_sides === true,
      prescription: {
        sets: ex.sets as number | undefined,
        reps: ex.reps != null ? (ex.reps as string | number) : undefined,
        workSeconds: ex.work_seconds as number | undefined,
        restBetweenRepsSeconds: ex.rest_between_reps_seconds as number | undefined,
        restSeconds: ex.rest_between_sets_seconds as number | undefined,
        loadKg,
        // A298: a ladder row at a terminal level carries its slower eccentric.
        tempo: typeof ex.tempo === "string" ? (ex.tempo as string) : undefined,
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
        loadNotes: anchoredLoadNotes(ex),
        // A295: read-time measure metadata (custom / ad-hoc / body-part rows).
        measure: asMeasure(ex.measure),
        targetReps: typeof ex.target_reps === "number" ? (ex.target_reps as number) : undefined,
        // A298: ladder rows of a custom session (badge + promotion tap).
        ladder: asLadder(ex.ladder),
        ladderSource: ex.progress_source === "bw_ladder" ? "ladder" : undefined,
        customSessionId: customSessionIdOf(sessionId),
        // A299: limit-family rows carry the limit target of the day they are
        // read for (GET /api/week and GET custom ?date= — computed at read,
        // never stored). With it the guided player shows the problem logger
        // and the outcome reaches the limit log, exactly as on a planned limit.
        ...limitSuggestedFields(ex),
      },
      cues: (ex.cues as string[] | undefined) ?? undefined,
      hrTarget: (ex.hr_target as GuidedExercise["hrTarget"]) ?? undefined,  // A316
      videoUrl: (ex.video_url as string | undefined) ?? undefined,
      status: "pending",
      feedbackLabel: null,  // A295: nothing pre-selected
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
  const key = guidedStorageKey(state.date, state.sessionId);
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
