import type { GuidedExercise, GuidedSessionState } from "@/lib/types";

/**
 * B397 G5 — Done and Skip in the guided player, as reversible steps.
 *
 * A mistaken Done/Skip used to be a detour: open the progress dots, find the
 * exercise, redo it. Worse, a double tap on Done could close TWO exercises,
 * because the next card mounts with its own Done button exactly under the
 * finger. Each step now returns its own inverse, which the player offers in an
 * "Undo" toast.
 */

/** What one Done/Skip changed, enough to put it back. */
export interface StepUndo {
  /** The exercise the step closed: the player returns to it. */
  index: number;
  /** Previous version of every exercise the step touched, by position. */
  previous: Record<number, GuidedExercise>;
}

export interface ClosedStep {
  next: GuidedSessionState;
  /** The step closed the last exercise: the player shows the summary. */
  openedSummary: boolean;
  undo: StepUndo;
}

/**
 * B397 review — where the player goes after closing exercise `index`: the
 * first exercise still pending after it, else the first one still pending
 * anywhere; -1 when none is left (the summary).
 *
 * It used to be plain `index + 1`. From the summary, "Change" on an exercise
 * followed by Done then landed on the NEXT exercise — already closed — instead
 * of back on the summary, one more Done away from overwriting its log. In the
 * usual front-to-back run the next exercise is the first pending one after
 * `index`, so that flow is unchanged.
 */
export function nextPendingIndex(exercises: GuidedExercise[], index: number): number {
  for (let i = index + 1; i < exercises.length; i++) {
    if (exercises[i].status === "pending") return i;
  }
  return exercises.findIndex((ex, i) => i !== index && ex.status === "pending");
}

/**
 * Close exercise `index` with `updates`, then move to the next exercise still
 * pending (or stay on it and open the summary when none is left).
 *
 * `extra` may rewrite later exercises (B128: a finished max test re-bases the
 * duration test's suggestion). Whatever it touches is captured in the undo
 * too, so undoing the max test also restores the old suggestion.
 */
export function closeStep(
  state: GuidedSessionState,
  index: number,
  updates: Partial<GuidedExercise>,
  extra?: (exercises: GuidedExercise[]) => GuidedExercise[],
): ClosedStep {
  let exercises = [...state.exercises];
  exercises[index] = { ...exercises[index], ...updates };
  if (extra) exercises = extra(exercises);

  const nextIndex = nextPendingIndex(exercises, index);
  const openedSummary = nextIndex < 0;
  const next: GuidedSessionState = {
    ...state,
    exercises,
    currentIndex: openedSummary ? index : nextIndex,
  };

  const previous: Record<number, GuidedExercise> = {};
  state.exercises.forEach((ex, i) => {
    if (exercises[i] !== ex) previous[i] = ex;
  });
  return { next, openedSummary, undo: { index, previous } };
}

/**
 * Put a step back. Only the exercises the step touched are restored: what the
 * athlete did since on OTHER exercises (a set counted on the next card, a
 * note) survives. A session already submitted is never rewritten.
 */
export function applyStepUndo(current: GuidedSessionState, undo: StepUndo): GuidedSessionState {
  if (current.submitStatus) return current;
  if (undo.index < 0 || undo.index >= current.exercises.length) return current;
  return {
    ...current,
    currentIndex: undo.index,
    exercises: current.exercises.map((ex, i) => undo.previous[i] ?? ex),
  };
}

/**
 * Ignore a second Done/Skip landing this soon after an advance: the new card
 * mounts with its buttons where the old ones were, so the second half of a
 * double tap would close an exercise nobody looked at.
 */
export const ADVANCE_GUARD_MS = 600;

export function isWithinAdvanceGuard(lastAdvanceAt: number, now: number): boolean {
  return lastAdvanceAt > 0 && now - lastAdvanceAt < ADVANCE_GUARD_MS;
}
