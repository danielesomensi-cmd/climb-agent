"use client";

/**
 * A245 B-3 (F1) — where the root `/` should send the user when the network
 * cannot answer. Kept in its own module so SessionScopeGuard can purge it
 * alongside the rest of the per-user device state: it encodes whether a user
 * has a plan, so leaving it behind would send a brand-new signup straight to
 * /today on their first offline open.
 */
const LAST_DEST_KEY = "climb-agent-last-destination";

export type RootDestination = "/today" | "/onboarding/welcome";

export function readLastDestination(): RootDestination | null {
  if (typeof window === "undefined") return null;
  try {
    const v = window.localStorage.getItem(LAST_DEST_KEY);
    // Only ever trust the two values this module writes.
    return v === "/today" || v === "/onboarding/welcome" ? v : null;
  } catch {
    return null;
  }
}

export function writeLastDestination(dest: RootDestination): void {
  try {
    window.localStorage.setItem(LAST_DEST_KEY, dest);
  } catch {
    // Private mode — degrade to the online-only behaviour.
  }
}

export function purgeLastDestination(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(LAST_DEST_KEY);
  } catch {
    // Nothing to purge.
  }
}
