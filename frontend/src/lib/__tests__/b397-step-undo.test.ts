import { describe, it, expect } from "vitest";
import {
  ADVANCE_GUARD_MS,
  applyStepUndo,
  closeStep,
  isWithinAdvanceGuard,
} from "@/lib/guided-step-undo";
import type { GuidedExercise, GuidedSessionState } from "@/lib/types";

/**
 * B397 G5 — Done and Skip are reversible, and only what the step touched is
 * put back.
 */

function ex(id: string, extra: Partial<GuidedExercise> = {}): GuidedExercise {
  return {
    exerciseId: id,
    name: id,
    category: "strength",
    blockUid: "main",
    loadModel: "external_load",
    prescription: {},
    suggested: {},
    status: "pending",
    feedbackLabel: null,
    ...extra,
  } as GuidedExercise;
}

function session(exercises: GuidedExercise[], currentIndex = 0): GuidedSessionState {
  return {
    version: 1,
    date: "2026-10-18",
    sessionId: "strength_long",
    sessionName: "Strength",
    startedAt: "2026-10-18T09:00:00.000Z",
    currentIndex,
    exercises,
  };
}

describe("closeStep — Done / Skip", () => {
  it("closes the current exercise and moves to the next", () => {
    const s = session([ex("a"), ex("b"), ex("c")]);
    const { next, openedSummary } = closeStep(s, 0, { status: "done", feedbackLabel: "hard", usedLoadKg: 20 });

    expect(next.currentIndex).toBe(1);
    expect(next.exercises[0]).toMatchObject({ status: "done", feedbackLabel: "hard", usedLoadKg: 20 });
    expect(openedSummary).toBe(false);
    // Pure: the input is untouched.
    expect(s.exercises[0].status).toBe("pending");
  });

  it("on the last exercise stays put and opens the summary", () => {
    const s = session([ex("a"), ex("b")], 1);
    const { next, openedSummary } = closeStep(s, 1, { status: "skipped", feedbackLabel: null });
    expect(next.currentIndex).toBe(1);
    expect(openedSummary).toBe(true);
  });
});

describe("applyStepUndo", () => {
  it("Undo of Done goes back to the exercise, as it was", () => {
    const s = session([ex("a"), ex("b"), ex("c")]);
    const { next, undo } = closeStep(s, 0, { status: "done", feedbackLabel: "ok", usedLoadKg: 18 });

    const back = applyStepUndo(next, undo);

    expect(back.currentIndex).toBe(0);
    expect(back.exercises[0]).toEqual(s.exercises[0]);
    expect(back.exercises[0].usedLoadKg).toBeUndefined();
  });

  it("Undo of Skip restores the pending exercise", () => {
    const s = session([ex("a"), ex("b"), ex("c")], 1);
    const { next, undo } = closeStep(s, 1, { status: "skipped", feedbackLabel: null });

    const back = applyStepUndo(next, undo);

    expect(back.currentIndex).toBe(1);
    expect(back.exercises[1].status).toBe("pending");
  });

  it("keeps what happened since on OTHER exercises (a set counted on the next card)", () => {
    const s = session([ex("a"), ex("b"), ex("c")]);
    const { next, undo } = closeStep(s, 0, { status: "done", feedbackLabel: null });
    // The athlete already counted a set and wrote a note on exercise b.
    const later: GuidedSessionState = {
      ...next,
      exercises: next.exercises.map((e, i) => (i === 1 ? { ...e, completedSets: 1, notes: "felt good" } : e)),
    };

    const back = applyStepUndo(later, undo);

    expect(back.exercises[0].status).toBe("pending");
    expect(back.exercises[1]).toMatchObject({ completedSets: 1, notes: "felt good" });
  });

  it("also restores what the step rewrote further on (B128 max-test re-base)", () => {
    const duration = ex("lp_duration_test", {
      prescription: { intensityPct: 0.6 },
      suggested: { rightHand: { externalLoadKg: 10 } },
    });
    const s = session([ex("lp_max_test_5s"), duration]);
    const rebase = (exercises: GuidedExercise[]) =>
      exercises.map((e, i) => (i === 1 ? { ...e, suggested: { rightHand: { externalLoadKg: 15 } } } : e));

    const { next, undo } = closeStep(s, 0, { status: "done", feedbackLabel: null }, rebase);
    expect(next.exercises[1].suggested.rightHand?.externalLoadKg).toBe(15);

    const back = applyStepUndo(next, undo);
    expect(back.exercises[1].suggested.rightHand?.externalLoadKg).toBe(10);
  });

  it("Undo after the last step leaves the summary for that exercise", () => {
    const s = session([ex("a"), ex("b")], 1);
    const { next, undo, openedSummary } = closeStep(s, 1, { status: "done", feedbackLabel: "easy" });
    expect(openedSummary).toBe(true);

    const back = applyStepUndo(next, undo);
    expect(back.currentIndex).toBe(1);
    expect(back.exercises[1].status).toBe("pending");
  });

  it("never rewrites a session already submitted or queued", () => {
    const s = session([ex("a"), ex("b")]);
    const { next, undo } = closeStep(s, 0, { status: "done", feedbackLabel: null });
    const queued: GuidedSessionState = { ...next, submitStatus: "feedback_pending" };

    expect(applyStepUndo(queued, undo)).toBe(queued);
  });
});

describe("double tap guard", () => {
  it("swallows a second advance inside the guard window, not after it", () => {
    const t0 = 1_000_000;
    expect(isWithinAdvanceGuard(0, t0)).toBe(false); // nothing advanced yet
    expect(isWithinAdvanceGuard(t0, t0 + 150)).toBe(true); // second half of a double tap
    expect(isWithinAdvanceGuard(t0, t0 + ADVANCE_GUARD_MS + 1)).toBe(false); // a deliberate next tap
  });
});
