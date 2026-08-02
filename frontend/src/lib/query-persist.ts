"use client";

import type { Persister, PersistedClient } from "@tanstack/react-query-persist-client";

/**
 * A245 B-2 (F1) — persist the two queries that make the PWA usable offline.
 *
 * React Query is in-memory only with `gcTime` 5 min, so when iOS kills the PWA
 * the plan, the week and the resolved sessions are simply gone: reopening in
 * falesia with no signal showed nothing at all.
 *
 * SCOPING (mandatory, not an optimisation). The pre-existing localStorage
 * convention was `guided_session_${userId}_` where `userId` was the LITERAL
 * string "clerk" (never the real id). Harmless while it only held guided
 * progress on a single-user browser — but persisting `state` and `week` under
 * an unscoped key means that after an account switch or a state import
 * user A's training plan renders for user B. Every persisted payload therefore
 * carries the real Clerk user id and is dropped on mismatch.
 */

const STORAGE_KEY = "climb-agent-rq-cache-v1";

/**
 * localStorage is a synchronous, ~5MB-per-origin store shared with everything
 * else we keep there (guided sessions, dismissed tips, drafts). A week plan
 * with resolved sessions is the biggest thing we write, so refuse to persist
 * past a conservative ceiling rather than throwing QuotaExceededError — which
 * on Safari can wedge OTHER writes, including the outbox.
 */
const MAX_BYTES = 2_000_000;

/** How long to wait for Clerk before deciding we cannot identify the user. */
const CLERK_READY_TIMEOUT_MS = 3000;
const CLERK_POLL_MS = 50;

type Envelope = {
  userId: string;
  client: PersistedClient;
};

/**
 * B292b — the last user id we positively identified on this device.
 *
 * Clerk.js is loaded FROM THE NETWORK. With no connection it never initialises,
 * so `window.Clerk.user.id` is unavailable exactly when the offline cache
 * matters most. Remembering the id locally gives us identity without a network
 * round trip; it is not a credential and grants nothing on its own (every API
 * call still needs a real Clerk token).
 */
const LAST_USER_KEY = "climb-agent-last-user";

function currentUserId(): string | null {
  if (typeof window === "undefined") return null;
  return window.Clerk?.user?.id ?? null;
}

function rememberUser(userId: string): void {
  try {
    window.localStorage.setItem(LAST_USER_KEY, userId);
  } catch {
    /* private mode */
  }
}

function lastKnownUserId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(LAST_USER_KEY);
  } catch {
    return null;
  }
}

export function forgetLastUser(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(LAST_USER_KEY);
  } catch {
    /* nothing to forget */
  }
}

type Identity =
  /** Clerk answered: this is definitively who is signed in. */
  | { known: true; userId: string | null }
  /** Clerk never initialised (offline, script blocked): we do NOT know. */
  | { known: false; userId: string | null };

/**
 * Restore runs at mount, when Clerk may still be bootstrapping. Reading the id
 * too early returns null, and treating that as "a different user" is what made
 * the offline cache delete itself: with no network Clerk NEVER loads, so the
 * timeout always expired, the ids never matched and we purged.
 *
 * The distinction that fixes it: "Clerk says nobody" is not the same fact as
 * "we could not ask Clerk".
 */
async function resolveIdentity(): Promise<Identity> {
  if (typeof window === "undefined") return { known: false, userId: null };

  // B292b — when the browser already knows there is no connection, waiting for
  // Clerk is 3 seconds of guaranteed-blank screen on EVERY offline open, which
  // is exactly the moment the app has to feel instant. Go straight to the
  // remembered id.
  if (navigator.onLine === false && !window.Clerk?.loaded) {
    return { known: false, userId: lastKnownUserId() };
  }

  const deadline = Date.now() + CLERK_READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (window.Clerk?.loaded) {
      const id = currentUserId();
      if (id) rememberUser(id);
      return { known: true, userId: id };
    }
    await new Promise((r) => setTimeout(r, CLERK_POLL_MS));
  }
  // Could not ask. Fall back to the last id we saw on this device.
  return { known: false, userId: lastKnownUserId() };
}

/** Wipe the persisted cache. Called on sign-out and on any user mismatch. */
export function purgePersistedCache(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Private mode / storage disabled — nothing to purge.
  }
}

export function createPersister(): Persister {
  return {
    persistClient(client: PersistedClient) {
      // B292b: fall back to the remembered id so a cache written while offline
      // (e.g. after an outbox flush) still carries an owner.
      const userId = currentUserId() ?? lastKnownUserId();
      // No identified user at all → persisting would produce a payload we could
      // never safely attribute on restore.
      if (!userId) return;
      try {
        const payload = JSON.stringify({ userId, client } satisfies Envelope);
        if (payload.length > MAX_BYTES) {
          console.warn(
            `[query-persist] cache ${payload.length}B over the ${MAX_BYTES}B guard — not persisted`,
          );
          return;
        }
        window.localStorage.setItem(STORAGE_KEY, payload);
      } catch (err) {
        console.warn("[query-persist] persist failed:", err);
      }
    },

    async restoreClient() {
      if (typeof window === "undefined") return undefined;
      let raw: string | null = null;
      try {
        raw = window.localStorage.getItem(STORAGE_KEY);
      } catch {
        return undefined;
      }
      if (!raw) return undefined;

      const identity = await resolveIdentity();
      try {
        const envelope = JSON.parse(raw) as Partial<Envelope>;
        if (!envelope.userId || !envelope.client) {
          purgePersistedCache(); // unscoped legacy payload
          return undefined;
        }
        if (envelope.userId === identity.userId) return envelope.client;

        // Mismatch. Purge ONLY when Clerk actually told us someone else is
        // signed in. When we could not ask (offline), leave the cache alone —
        // deleting it is precisely how the PWA lost its offline data.
        if (identity.known) purgePersistedCache();
        return undefined;
      } catch {
        purgePersistedCache();
        return undefined;
      }
    },

    removeClient() {
      purgePersistedCache();
    },
  };
}

/**
 * Only `state` and `week` are worth persisting: they are what /today and /week
 * render. Everything else (catalog, coach history, subscription, reports) is
 * either large, sensitive, or meaningless without a connection.
 */
export const PERSISTED_QUERY_PREFIXES = ["state", "week"];

/**
 * A plan older than a week is not worth showing offline — the server copy is
 * authoritative and the macrocycle has moved on.
 *
 * The persisted queries MUST also carry a `gcTime` at least this long (see
 * use-user-state / use-week-plan): React Query evicts an observer-less query
 * after `gcTime` and the next persist would write it back out, silently
 * emptying the offline cache while the user is on another page.
 */
export const PERSIST_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
