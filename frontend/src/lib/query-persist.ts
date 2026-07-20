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
 * an unscoped key means that after an account switch or a recovery-code import
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

function currentUserId(): string | null {
  if (typeof window === "undefined") return null;
  return window.Clerk?.user?.id ?? null;
}

/**
 * Restore runs at mount, when Clerk may still be bootstrapping. Reading the
 * user id too early would return null and we would throw away a perfectly good
 * cache on every cold start — so wait, but bounded.
 */
async function waitForClerk(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const deadline = Date.now() + CLERK_READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (window.Clerk?.loaded) return currentUserId();
    await new Promise((r) => setTimeout(r, CLERK_POLL_MS));
  }
  return currentUserId();
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
      const userId = currentUserId();
      // No identified user (signed out, or Clerk still loading) → persisting
      // would produce a payload we could never safely attribute on restore.
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

      const userId = await waitForClerk();
      try {
        const envelope = JSON.parse(raw) as Partial<Envelope>;
        // Unscoped legacy payload, or a different user: never hand it over.
        if (!envelope.userId || !envelope.client || envelope.userId !== userId) {
          purgePersistedCache();
          return undefined;
        }
        return envelope.client;
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
