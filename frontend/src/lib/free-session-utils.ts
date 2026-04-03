/**
 * Draft persistence helpers for free session route/climb logging.
 * Mirrors the pattern used in guided/[date]/[sessionId]/page.tsx.
 *
 * Draft is saved to localStorage on every state change (debounced by caller).
 * Cleared on successful finish or explicit cancel.
 * On resume, form state is restored from draft; climbs are re-hydrated from draft cache.
 */

import type { LoggedClimb } from "@/components/free-session/climb-logger";

export interface FreeSessionDraft {
  version: 1;
  sessionId: string;
  surface: string;
  sessionMode: "template" | "free";
  presetName?: string;
  gymName?: string;
  targetGrade?: string;
  restSeconds?: number;
  tip?: string;
  targetClimbs?: string;
  // Current form state
  currentGrade: string;
  currentStatus: "flash" | "sent" | "attempted";
  currentAttempts: number;
  currentStyle?: string;
  currentTopped?: boolean;
  currentNotes: string;
  // Logged climbs (cached locally — also persisted on backend)
  loggedClimbs: LoggedClimb[];
  startedAt: number;
}

const PREFIX = "free_session_draft_";

export function saveDraft(draft: FreeSessionDraft): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(PREFIX + draft.sessionId, JSON.stringify(draft));
  } catch {
    // Quota exceeded — non-critical, backend is source of truth
  }
}

export function loadDraft(sessionId: string): FreeSessionDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(PREFIX + sessionId);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as FreeSessionDraft;
    // Guard against stale schema versions
    if (parsed.version !== 1) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearDraft(sessionId: string): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(PREFIX + sessionId);
}

/**
 * Scan localStorage for any pending free session draft.
 * Returns the most recently started draft, or null.
 */
export function findPendingDraft(): FreeSessionDraft | null {
  if (typeof window === "undefined") return null;
  let latest: FreeSessionDraft | null = null;
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key?.startsWith(PREFIX)) continue;
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      const parsed = JSON.parse(raw) as FreeSessionDraft;
      if (parsed.version !== 1) continue;
      if (!latest || parsed.startedAt > latest.startedAt) {
        latest = parsed;
      }
    }
  } catch {
    return null;
  }
  return latest;
}
