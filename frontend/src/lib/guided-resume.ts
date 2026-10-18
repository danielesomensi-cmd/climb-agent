import type { DayPlan, GuidedSessionState } from "@/lib/types";

/**
 * B396 — resuming a guided session from /today, without a block above it.
 *
 * Before: a session in progress put a banner above the day — two 28px
 * buttons, and "Discard" deleted the saved progress on the first tap — while
 * the card's own button still said "Start session" even though it resumed.
 * Now the button says "Resume · 3/8"; the banner is left for the session that
 * no card on the page can resume (another day, or a finished card); and
 * discarding is undoable.
 *
 * The key builder stays in guided-session-utils (B290: one producer); these
 * helpers only read, remove and restore the value under a key they are given.
 */

/** Fired on window when saved guided progress is discarded or restored. */
export const GUIDED_PROGRESS_EVENT = "climb-agent:guided-progress";

export type SavedProgress = {
  completed: number;
  total: number;
  /**
   * B396 review — the session was submitted and its feedback is queued on the
   * device (B397: `submitStatus: "feedback_pending"` + `pendingFeedback`, the
   * ONLY copy of that feedback). Nothing to resume and nothing to discard:
   * Start opens the player's "waiting to sync" view.
   */
  pending?: true;
};

/**
 * Progress saved under `key`, with the same rule as `hasSavedProgress` (what
 * "Start session" uses to decide to resume): at least one exercise done or
 * skipped, or the player moved past the first step. Null otherwise.
 *
 * B396 review — a session whose feedback is waiting to sync is reported as
 * `pending` whatever its progress (it read as "Resume · n/n", and the drawer
 * offered to discard it: that deleted feedback never sent); a `completed` one
 * is nothing to show.
 */
export function readSavedProgress(storage: Pick<Storage, "getItem">, key: string): SavedProgress | null {
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const saved = JSON.parse(raw) as GuidedSessionState;
    if (saved?.submitStatus === "completed") return null;
    const exercises = Array.isArray(saved?.exercises) ? saved.exercises : [];
    const completed = exercises.filter((ex) => ex.status !== "pending").length;
    if (saved?.submitStatus === "feedback_pending") {
      return { completed, total: exercises.length, pending: true };
    }
    if (completed === 0 && !(saved.currentIndex > 0)) return null;
    return { completed, total: exercises.length };
  } catch {
    return null;
  }
}

/**
 * "Resume · 3/8" — the start button's label when it resumes.
 * B396 review — "Waiting to sync" for a session whose feedback is queued.
 */
export function resumeLabel(progress: SavedProgress): string {
  if (progress.pending) return "Waiting to sync";
  return progress.total > 0 ? `Resume · ${progress.completed}/${progress.total}` : "Resume";
}

function notify(): void {
  if (typeof window === "undefined" || typeof window.dispatchEvent !== "function") return;
  try {
    window.dispatchEvent(new Event(GUIDED_PROGRESS_EVENT));
  } catch {
    /* very old WebViews without the Event constructor: listeners just miss it */
  }
}

/**
 * Remove the saved session under `key` and return a function that puts it
 * back exactly as it was (for the toast's Undo). Null when nothing was saved.
 * The restore never overwrites a newer session written under the same key in
 * the meantime (e.g. the user tapped Start again before Undo).
 */
export function discardSavedSession(
  storage: Pick<Storage, "getItem" | "setItem" | "removeItem">,
  key: string,
): (() => void) | null {
  let raw: string | null = null;
  try {
    raw = storage.getItem(key);
    if (raw === null) return null;
    storage.removeItem(key);
  } catch {
    return null;
  }
  notify();
  const saved = raw;
  return () => {
    try {
      if (storage.getItem(key) === null) storage.setItem(key, saved);
    } catch {
      /* storage full / blocked: nothing we can restore */
    }
    notify();
  };
}

/**
 * True when the in-progress session is one of the cards of `day` that still
 * shows a start button (planned, not done/skipped) — its "Resume · n/m" says it
 * all, so the banner above the day is redundant.
 */
export function isResumableOnCard(
  resume: { date: string; sessionId: string } | null,
  day: DayPlan | null | undefined,
): boolean {
  if (!resume || !day || day.date !== resume.date) return false;
  return day.sessions.some(
    (s) => s.session_id === resume.sessionId && s.status !== "done" && s.status !== "skipped",
  );
}
