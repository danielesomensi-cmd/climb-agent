"use client";

import { ApiError, NETWORK_ERROR_STATUS } from "@/lib/api";
import { getKeyPrefix } from "@/lib/guided-session-utils";
import type { OutdoorDayType, OutdoorRoute } from "@/lib/types";

/**
 * B336 — the live outdoor session, persisted on the device.
 *
 * D279 finding F3: an outdoor session started with the timer kept its routes in
 * React state and on the server, and nowhere else. Three consequences, all of
 * them at the crag:
 *
 *   - the phone dying mid-session while offline lost every route logged that day
 *     (restore read the SERVER, so there was nothing to come back to);
 *   - `Start session` was gated on a strategy fetch, so with no signal the
 *     session could not even begin;
 *   - the finish call bypassed the outbox precisely when a session had been
 *     started, so at 19:00 with no bars the day could not be saved at all.
 *
 * The fallback path ("Log without timer" → `postOutdoorLog` → outbox) was fully
 * offline-safe while the RECOMMENDED path was not. This module closes that.
 *
 * Scoped per user via `getKeyPrefix()`, the same convention as the guided
 * session and the outbox — that scoping, not a purge, is what stops user A's
 * session being read as user B's on a shared device (A245 B-2 / B290).
 */

const STORAGE_KEY_BASE = "climb-agent-outdoor-live-v1";

/**
 * A long crag day plus an overnight is still the same day's work; anything
 * older is stale and must not be resurrected on top of a fresh session.
 */
export const MAX_AGE_MS = 24 * 60 * 60 * 1000;

/** Same guard as the outbox and the persisted query cache: never risk QuotaExceededError. */
const MAX_BYTES = 500_000;

/** A route as the live logger holds it (`OutdoorRoute` + its pacing mark). */
export type LiveOutdoorRoute = OutdoorRoute & { atMin: number };

export interface LiveOutdoorSession {
  /** Server session id, or a `local_*` id when the session began offline. */
  sessionId: string;
  /** True when no server session exists yet — finish must go through the outbox. */
  isLocal: boolean;
  date: string;
  spotName: string;
  discipline: "lead" | "boulder" | "both";
  dayType: OutdoorDayType | null;
  startedAt: string;
  routes: LiveOutdoorRoute[];
  /** Device clock, for the staleness check only — never sent to the server. */
  updatedAt: number;
}

function storageKey(): string {
  return `${STORAGE_KEY_BASE}-${getKeyPrefix()}`;
}

export function newLocalSessionId(): string {
  const rand =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `local_${rand}`;
}

export function isLocalSessionId(id: string | null | undefined): boolean {
  return typeof id === "string" && id.startsWith("local_");
}

/**
 * Persist the session. Returns false when it could not be stored, so the caller
 * can warn instead of pretending the day is safe.
 */
export function saveLiveSession(session: Omit<LiveOutdoorSession, "updatedAt">): boolean {
  if (typeof window === "undefined") return false;
  try {
    const payload = JSON.stringify({ ...session, updatedAt: Date.now() });
    if (payload.length > MAX_BYTES) {
      console.warn(`[outdoor-live] ${payload.length}B over the ${MAX_BYTES}B guard — write refused`);
      return false;
    }
    window.localStorage.setItem(storageKey(), payload);
    return true;
  } catch (err) {
    console.warn("[outdoor-live] write failed:", err);
    return false;
  }
}

/** The stored session for *date*, or null when absent, stale, or unparseable. */
export function loadLiveSession(date: string, now: number = Date.now()): LiveOutdoorSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(storageKey());
    if (!raw) return null;
    const parsed = JSON.parse(raw) as LiveOutdoorSession;
    if (!parsed || typeof parsed !== "object" || !parsed.sessionId) return null;
    if (parsed.date !== date) return null;
    if (now - (parsed.updatedAt ?? 0) > MAX_AGE_MS) {
      clearLiveSession();
      return null;
    }
    if (!Array.isArray(parsed.routes)) parsed.routes = [];
    return parsed;
  } catch {
    return null;
  }
}

export function clearLiveSession(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(storageKey());
  } catch {
    /* nothing we can do, and nothing that should break the finish flow */
  }
}

/**
 * Choose between the device copy and the server copy on restore.
 *
 * **The local copy wins whenever it exists.** Every mutation is written to the
 * device first and pushed to the server after, so local is by construction at
 * least as new — and "whichever has more routes" would be actively wrong: it
 * resurrects a route the user has just deleted, which is the one edit that
 * makes local shorter than the server.
 *
 * The cost is a genuine second device logging the same day, whose routes would
 * be preferred away. That trade is deliberate: the server session carries no
 * timestamp to compare against, so there is nothing honest to merge on, and
 * losing the climb you logged ten seconds ago is the worse failure of the two.
 */
export function pickRestoredSession(
  local: LiveOutdoorSession | null,
  server: LiveOutdoorSession | null,
): LiveOutdoorSession | null {
  return local ?? server ?? null;
}

/**
 * Did this call fail because the network is gone, rather than because the
 * server said no?
 *
 * A 402/422/404 is an answer and must surface as an error; a transport failure
 * is not, and is the case the whole offline path exists for. `request()` maps
 * every HTTP outcome to an ApiError, so anything else escaping it is transport
 * — except an abort, which is our own unmount and must not be mistaken for it.
 */
export function isOfflineError(err: unknown): boolean {
  if (err instanceof ApiError) {
    if (err.status === NETWORK_ERROR_STATUS) return true;
    // A245 C-3: offline, a 401 is not trustworthy evidence that the session ended.
    return (
      err.status === 401 &&
      typeof navigator !== "undefined" &&
      navigator.onLine === false
    );
  }
  if (err instanceof DOMException && err.name === "AbortError") return false;
  return true;
}
