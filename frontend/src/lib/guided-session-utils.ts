import type { GuidedSessionState } from "@/lib/types";

const MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours

function getKeyPrefix(): string {
  if (typeof window === "undefined") return "guided_session__";
  const userId = window.Clerk?.session ? "clerk" : "";
  return `guided_session_${userId}_`;
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
