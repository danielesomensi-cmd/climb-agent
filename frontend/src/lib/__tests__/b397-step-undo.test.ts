import { describe, it, expect } from "vitest";
import {
  ADVANCE_GUARD_MS,
  applyStepUndo,
  closeStep,
  isWithinAdvanceGuard,
  nextPendingIndex,
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

  it("on the last exercise, with nothing left pending, stays put and opens the summary", () => {
    const s = session([ex("a", { status: "done" }), ex("b")], 1);
    const { next, openedSummary } = closeStep(s, 1, { status: "skipped", feedbackLabel: null });
    expect(next.currentIndex).toBe(1);
    expect(openedSummary).toBe(true);
  });

  // B397 review — from the summary, "Change" reopens a closed exercise: Done
  // must not land on the next one, already closed.
  it("Change from the summary, then Done, with nothing left pending: back to the summary", () => {
    const s = session([ex("a", { status: "done" }), ex("b", { status: "done" }), ex("c", { status: "skipped" })], 0);
    const { next, openedSummary } = closeStep(s, 0, { status: "done", feedbackLabel: "hard" });
    expect(openedSummary).toBe(true);
    expect(next.currentIndex).toBe(0);
    expect(next.exercises[0].feedbackLabel).toBe("hard");
  });

  it("Change, then Skip, skips over closed exercises to the first one still pending", () => {
    const s = session([ex("a", { status: "done" }), ex("b", { status: "done" }), ex("c"), ex("d")], 0);
    const { next, openedSummary } = closeStep(s, 0, { status: "skipped", feedbackLabel: null });
    expect(openedSummary).toBe(false);
    expect(next.currentIndex).toBe(2);
  });

  it("with nothing pending after it, opens the summary even if an earlier one is pending", () => {
    // Jumped ahead with the progress dots: b is still to do, reachable from
    // the summary — the last Done does not pull the athlete back to it.
    const s = session([ex("a", { status: "done" }), ex("b"), ex("c")], 2);
    const { next, openedSummary } = closeStep(s, 2, { status: "done", feedbackLabel: "ok" });
    expect(openedSummary).toBe(true);
    expect(next.currentIndex).toBe(2);
  });

  it("a warm-up skipped with the dots does not come back after the last Done", () => {
    const s = session([ex("w", { category: "warmup_general" } as Partial<GuidedExercise>), ex("a"), ex("b")], 1);
    const first = closeStep(s, 1, { status: "done", feedbackLabel: "ok" });
    expect(first.next.currentIndex).toBe(2);
    const last = closeStep(first.next, 2, { status: "done", feedbackLabel: "ok" });
    expect(last.openedSummary).toBe(true);
  });

  it("Finish early, then Change on the last exercise, then Done: back to the summary", () => {
    // b was left open by "Finish session early"; c is reopened from the summary.
    const s = session([ex("a", { status: "done" }), ex("b"), ex("c", { status: "done" })], 2);
    const { next, openedSummary } = closeStep(s, 2, { status: "done", feedbackLabel: "hard" });
    expect(openedSummary).toBe(true);
    expect(next.exercises[2].feedbackLabel).toBe("hard");
    expect(next.exercises[1].status).toBe("pending");
  });

  it("the usual front-to-back run is unchanged: always the next exercise", () => {
    let s = session([ex("a"), ex("b"), ex("c")]);
    const seen: number[] = [];
    for (let i = 0; i < 3; i++) {
      const step = closeStep(s, s.currentIndex, { status: i === 1 ? "skipped" : "done", feedbackLabel: null });
      s = step.next;
      seen.push(step.openedSummary ? -1 : s.currentIndex);
    }
    expect(seen).toEqual([1, 2, -1]);
  });
});

describe("nextPendingIndex", () => {
  it("first pending after the index, else -1 (never wraps around)", () => {
    const list = [ex("a"), ex("b", { status: "done" }), ex("c"), ex("d", { status: "skipped" })];
    expect(nextPendingIndex(list, 0)).toBe(2);
    expect(nextPendingIndex(list, 2)).toBe(-1);
    expect(nextPendingIndex([ex("a", { status: "done" }), ex("b", { status: "skipped" })], 0)).toBe(-1);
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
    const s = session([ex("a", { status: "done" }), ex("b")], 1);
    const { next, undo, openedSummary } = closeStep(s, 1, { status: "done", feedbackLabel: "easy" });
    expect(openedSummary).toBe(true);

    const back = applyStepUndo(next, undo);
    expect(back.currentIndex).toBe(1);
    expect(back.exercises[1].status).toBe("pending");
  });

  it("Undo of a Done reached through \"Change\" restores that exercise's earlier log", () => {
    const s = session([ex("a", { status: "done", feedbackLabel: "easy", usedLoadKg: 20 }), ex("b", { status: "done" })], 0);
    const { next, undo, openedSummary } = closeStep(s, 0, { status: "done", feedbackLabel: "hard", usedLoadKg: 25 });
    expect(openedSummary).toBe(true);

    const back = applyStepUndo(next, undo);
    expect(back.currentIndex).toBe(0);
    expect(back.exercises[0]).toEqual(s.exercises[0]);
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
