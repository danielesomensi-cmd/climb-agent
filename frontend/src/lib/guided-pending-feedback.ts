"use client";

import { useEffect } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError, postFeedback } from "@/lib/api";
import { buildGuidedFeedbackItems } from "@/lib/feedback-items";
import { getKeyPrefix } from "@/lib/guided-session-utils";
import { notifyGuidedProgress } from "@/lib/guided-resume";
import { withFeedbackContract } from "@/lib/measured-feedback";
import { queryKeys } from "@/lib/query-keys";
import type { GuidedExercise, GuidedSessionState, WeekPlan } from "@/lib/types";

/**
 * B397 G3 — the guided player's offline feedback, sent once and sent whole.
 *
 * When "Submit & finish" fails, the player keeps the session in localStorage as
 * `submitStatus: "feedback_pending"` (B127/B128). The replay used to live in a
 * mount effect of /today, and was fragile in three ways:
 *
 *  - it ran only when /today MOUNTED: coming back online while on the page sent
 *    nothing until the next navigation;
 *  - it rebuilt the payload from the exercises and dropped
 *    `session_duration_seconds` (the replay could not know when the session
 *    ended — it was not saved);
 *  - nothing guarded it: every remount of /today fired a fresh POST while the
 *    previous one was still in flight, and the server runs `apply_feedback` on
 *    every POST, so the same session could move the loads twice.
 *
 * Now the player saves the EXACT body that failed (`pendingFeedback`), one
 * single-flight sender replays it — on mount, on `online`, or from the
 * player's pending view — and a session the server already logged (the POST
 * landed, only its response was lost to the 15 s timeout) is never sent again.
 *
 * Kept apart from the generic outbox (lib/outbox.ts) on purpose: the queued
 * session must stay visible to Start, which reopens it in a "waiting to sync"
 * view instead of a fresh player — a separate outbox entry would need a second
 * record, and two records drift.
 */

/** Body of POST /api/feedback, exactly as the guided player sends it. */
export interface GuidedFeedbackBody {
  log_entry: Record<string, unknown>;
  status: "done";
}

/** A guided state saved after a failed submit. B397: it carries the body. */
export type PendingGuidedState = GuidedSessionState & { pendingFeedback?: GuidedFeedbackBody };

/** Finished or abandoned sessions are cleaned up after this (B127). */
const STALE_MS = 24 * 60 * 60 * 1000;

/** Upper bound on refreshing the week before a replay (see syncPendingGuidedFeedback). */
const REFRESH_TIMEOUT_MS = 6000;

/**
 * B288 / A295 — the ONE builder of the guided feedback body. The first POST and
 * the replay go through it, so a replay is never poorer than the original.
 */
export function buildGuidedFeedbackBody(
  session: Pick<GuidedSessionState, "date" | "sessionId" | "startedAt" | "pain" | "isTestSession">,
  exercises: GuidedExercise[],
  durationSeconds?: number,
): GuidedFeedbackBody {
  // A295: feedback_contract 2 + the session's "Any pain?" answer.
  const logEntry: Record<string, unknown> = withFeedbackContract(
    {
      date: session.date,
      session_id: session.sessionId,
      // Real wall-clock start the timer already runs on (health-vault export).
      ...(session.startedAt ? { started_at: session.startedAt } : {}),
      ...(durationSeconds != null ? { session_duration_seconds: durationSeconds } : {}),
      actual: { exercise_feedback_v1: buildGuidedFeedbackItems(exercises) },
    },
    session.pain ?? null,
  );
  if (session.isTestSession) {
    logEntry.planned = [{ session_id: session.sessionId, tags: { test: true }, exercise_instances: [] }];
  }
  return { log_entry: logEntry, status: "done" };
}

/**
 * The body to replay. Entries saved before B397 carry no body: rebuild it with
 * the same builder — without a duration, which was never saved.
 */
export function pendingFeedbackBody(saved: PendingGuidedState): GuidedFeedbackBody {
  if (saved.pendingFeedback?.log_entry) return saved.pendingFeedback;
  return buildGuidedFeedbackBody(saved, saved.exercises ?? []);
}

/** True when the current user's scope holds at least one pending feedback. */
export function hasPendingGuidedFeedback(): boolean {
  return pendingKeys().length > 0;
}

function scopedKeys(): string[] {
  if (typeof window === "undefined") return [];
  const prefix = getKeyPrefix();
  const keys: string[] = [];
  try {
    for (let i = 0; i < window.localStorage.length; i++) {
      const key = window.localStorage.key(i);
      if (key && key.startsWith(prefix)) keys.push(key);
    }
  } catch {
    /* storage unavailable */
  }
  return keys;
}

function readEntry(key: string): PendingGuidedState | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as PendingGuidedState) : null;
  } catch {
    return null; // malformed entry: ignored, as before
  }
}

function pendingKeys(): string[] {
  return scopedKeys().filter((key) => readEntry(key)?.submitStatus === "feedback_pending");
}

/**
 * A payload the server will never accept. Everything else — offline, timeout,
 * 5xx, and also 401/402/403 (sign-in or subscription can come back) — stays
 * queued: losing a whole session's feedback is worse than retrying it.
 */
function isPermanent(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 400 || err.status === 422);
}

export interface PendingSyncResult {
  /** POSTed and accepted. */
  sent: number;
  /** Dropped without a POST: the server already logged this session. */
  alreadySaved: number;
  /** Dropped after a permanent rejection (never silently: see announce). */
  rejected: number;
  /** Still queued after a retryable failure. */
  failed: number;
}

export interface FlushOptions {
  /** True when the server already holds feedback for this session. */
  alreadyLogged?: (date: string, sessionId: string) => boolean;
}

let inflight: Promise<PendingSyncResult> | null = null;

/**
 * Replay every pending guided feedback of the current user. Concurrent calls
 * share ONE pass — a remount, an `online` event and a tap in the player can all
 * ask at once, and the server must see each session at most once.
 */
export function flushPendingGuidedFeedback(options: FlushOptions = {}): Promise<PendingSyncResult> {
  if (inflight) return inflight;
  inflight = runFlush(options).finally(() => {
    inflight = null;
  });
  return inflight;
}

async function runFlush({ alreadyLogged }: FlushOptions): Promise<PendingSyncResult> {
  const result: PendingSyncResult = { sent: 0, alreadySaved: 0, rejected: 0, failed: 0 };
  const now = Date.now();
  const housekeeping = { removedStale: 0 };
  try {
    return await flushEntries(result, housekeeping, now, alreadyLogged);
  } finally {
    // B397 review (round 2) — a queued entry that is gone (sent, already on
    // the server, refused, or stale) must not leave its card on "Waiting to
    // sync": the cards re-read their label on this event.
    if (result.sent || result.alreadySaved || result.rejected || housekeeping.removedStale) notifyGuidedProgress();
  }
}

async function flushEntries(
  result: PendingSyncResult,
  housekeeping: { removedStale: number },
  now: number,
  alreadyLogged: FlushOptions["alreadyLogged"],
): Promise<PendingSyncResult> {

  for (const key of scopedKeys()) {
    const saved = readEntry(key);
    if (!saved) continue;

    if (saved.submitStatus !== "feedback_pending") {
      // B127 housekeeping, moved here from /today: sessions older than 24h
      // that are not waiting to be sent are dropped.
      const age = saved.startedAt ? now - new Date(saved.startedAt).getTime() : NaN;
      if (age > STALE_MS) {
        window.localStorage.removeItem(key);
        housekeeping.removedStale++;
      }
      continue;
    }
    if (!saved.exercises) continue;

    if (alreadyLogged?.(saved.date, saved.sessionId)) {
      window.localStorage.removeItem(key);
      result.alreadySaved++;
      continue;
    }

    try {
      await postFeedback(pendingFeedbackBody(saved));
      window.localStorage.removeItem(key);
      result.sent++;
    } catch (err) {
      if (isPermanent(err)) {
        window.localStorage.removeItem(key);
        result.rejected++;
        console.error("[guided] pending feedback rejected by the server:", err);
        continue;
      }
      // Keep it for the next pass, and stop this one: the network is down,
      // hammering it for every queued session only wastes battery.
      result.failed++;
      console.error("Failed to retry pending feedback submission:", err);
      break;
    }
  }
  return result;
}

/**
 * Does any cached week already show this session done WITH its feedback?
 * `actual_exercises` is written only by POST /api/feedback (step 4b), so its
 * presence means a feedback for this session has landed — replaying ours would
 * run `apply_feedback` a second time.
 */
export function sessionHasLoggedFeedback(qc: QueryClient, date: string, sessionId: string): boolean {
  const entries = qc.getQueriesData<{ week_plan?: WeekPlan | null }>({ queryKey: queryKeys.weekAll });
  for (const [, data] of entries) {
    for (const week of data?.week_plan?.weeks ?? []) {
      for (const day of week.days ?? []) {
        if (day.date !== date) continue;
        for (const s of day.sessions ?? []) {
          if (s.session_id === sessionId && s.status === "done" && (s.actual_exercises?.length ?? 0) > 0) {
            return true;
          }
        }
      }
    }
  }
  return false;
}

/**
 * Refresh the current week (bounded), then replay. The refresh is what lets
 * `sessionHasLoggedFeedback` see a POST whose response never came back.
 */
export async function syncPendingGuidedFeedback(qc: QueryClient): Promise<PendingSyncResult> {
  if (hasPendingGuidedFeedback()) {
    let timer: ReturnType<typeof setTimeout> | undefined;
    await Promise.race([
      qc.refetchQueries({ queryKey: queryKeys.week(0) }, { cancelRefetch: false }).catch(() => undefined),
      new Promise((resolve) => {
        timer = setTimeout(resolve, REFRESH_TIMEOUT_MS);
      }),
    ]);
    clearTimeout(timer);
  }
  const result = await flushPendingGuidedFeedback({
    alreadyLogged: (date, sessionId) => sessionHasLoggedFeedback(qc, date, sessionId),
  });
  if (result.sent > 0 || result.alreadySaved > 0) {
    // Feedback badges, the loads progression just moved, and every resolved
    // session that showed the pre-feedback numbers (A245 G-3).
    qc.invalidateQueries({ queryKey: queryKeys.weekAll });
    qc.invalidateQueries({ queryKey: queryKeys.state });
    qc.invalidateQueries({ queryKey: queryKeys.sessionResolveAll });
  }
  return result;
}

/** Tell the user what happened to their saved session — never drop it silently. */
export function announcePendingSync(result: PendingSyncResult): void {
  const synced = result.sent + result.alreadySaved;
  if (synced > 0) {
    toast.success(synced === 1 ? "Session feedback synced." : `${synced} session feedbacks synced.`);
  }
  if (result.rejected > 0) {
    toast.error("Saved session feedback was rejected by the server and could not be sent.", {
      duration: 10_000,
    });
  }
}

/**
 * Mount on /today (the first screen after a session): replays on mount and
 * whenever the connection comes back. `enabled` = Clerk is ready, since every
 * replay needs a token.
 */
export function usePendingGuidedFeedback(enabled: boolean): void {
  const qc = useQueryClient();
  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;
    const sync = () => {
      syncPendingGuidedFeedback(qc)
        .then(announcePendingSync)
        .catch((err) => console.error("[guided] pending feedback sync failed:", err));
    };
    sync();
    window.addEventListener("online", sync);
    return () => window.removeEventListener("online", sync);
  }, [enabled, qc]);
}
