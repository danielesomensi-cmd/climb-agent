/**
 * B414 — the players tell the truth about «done» (PLAYER-COMPLETED-FALSE,
 * CUSTOM-PLAYER-DONE-FLAG, B-ALTSIDES-SETS; Daniele's decision 4 of 07/11).
 *
 * - Guided player: a row is done when Done (or «Mark done») closed it OR when
 *   every set of the prescription was counted, however it was closed (Skip,
 *   left pending, Finish early). The 4x4 of 03/11 had 4/4 sets and went out
 *   `completed: false`. Partial sets stay not done, but the sets travel.
 * - `completed_sets` goes out in REAL sets: an alt_sides prescription is per
 *   side, so only complete RIGHT+LEFT pairs count (6 → 3, 5 → 2, 1 → 0).
 *   The repeater tests are never halved: their counter is reps to failure.
 * - On a custom / generated session a Done with no counted set carries the
 *   prescribed sets (the server wants a counted set there); a catalog row
 *   does not (Done is done).
 */
import { describe, expect, it } from "vitest";

import {
  buildGuidedFeedbackItems,
  guidedRowDone,
  guidedSentSets,
  isPlayerSession,
} from "@/lib/feedback-items";
import { buildGuidedFeedbackBody } from "@/lib/guided-pending-feedback";
import { realSetsFromInternal } from "@/lib/alt-sides";
import type { GuidedExercise } from "@/lib/types";

function row(extra: Partial<GuidedExercise> = {}): GuidedExercise {
  return {
    exerciseId: "four_by_four_bouldering",
    name: "4x4",
    category: "power_endurance",
    blockUid: "main",
    loadModel: "grade_relative",
    prescription: { sets: 4, reps: 4, restSeconds: 240 },
    suggested: {},
    status: "pending",
    feedbackLabel: null,
    ...extra,
  };
}

const item = (ex: GuidedExercise, playerSession = false) =>
  buildGuidedFeedbackItems([ex], { playerSession })[0];

describe("realSetsFromInternal", () => {
  it.each([
    [6, true, 3],
    [5, true, 2],
    [3, true, 1],
    [1, true, 0],
    [0, true, 0],
    [4, false, 4],
    [1, false, 1],
  ])("%i internal (alt_sides %s) → %i", (internal, alt, real) => {
    expect(realSetsFromInternal(internal, alt)).toBe(real);
  });
});

describe("guided player — every set counted is done", () => {
  it("the 4x4 of 03/11: 4/4 sets, closed with Skip → completed true, 4 sets", () => {
    const ex = row({ status: "skipped", completedSets: 4 });
    expect(guidedRowDone(ex)).toBe(true);
    expect(item(ex)).toMatchObject({ completed: true, completed_sets: 4 });
  });

  it("left pending with every set counted → done", () => {
    expect(item(row({ completedSets: 4 }))).toMatchObject({ completed: true, completed_sets: 4 });
  });

  it("partial sets stay not done, the sets travel", () => {
    expect(item(row({ completedSets: 2 }))).toMatchObject({ completed: false, completed_sets: 2 });
    expect(item(row({ status: "skipped", completedSets: 3 }))).toMatchObject({ completed: false, completed_sets: 3 });
  });

  it("nothing counted and skipped → not done, no sets", () => {
    const sent = item(row({ status: "skipped" }));
    expect(sent.completed).toBe(false);
    expect(sent.completed_sets).toBeUndefined();
  });

  it("Done stays done whatever was counted", () => {
    expect(item(row({ status: "done", completedSets: 2 }))).toMatchObject({ completed: true, completed_sets: 2 });
  });

  it("alt_sides: compared in internal sets, sent in real sets", () => {
    const split = (completedSets: number, status: GuidedExercise["status"] = "skipped") =>
      row({
        exerciseId: "bulgarian_split_squat",
        altSides: true,
        prescription: { sets: 3, reps: 8, restSeconds: 90 },
        completedSets,
        status,
      });
    expect(item(split(6))).toMatchObject({ completed: true, completed_sets: 3 });
    expect(item(split(5))).toMatchObject({ completed: false, completed_sets: 2 });
    expect(item(split(1))).toMatchObject({ completed: false, completed_sets: 0 });
    // Done after 6 internal sets: still 3 real sets.
    expect(item(split(6, "done"))).toMatchObject({ completed: true, completed_sets: 3 });
  });

  it("a non-alt_sides row is not halved", () => {
    expect(guidedSentSets(row({ completedSets: 3 }))).toBe(3);
  });

  it("per-hand items follow the same rule", () => {
    const lp = row({
      exerciseId: "lp_max_lift_5s",
      unilateral: true,
      altSides: true,
      prescription: { sets: 3, reps: 1 },
      usedLoadKgRight: 30,
      usedLoadKgLeft: 28,
      completedSets: 6,
      status: "skipped",
    });
    const items = buildGuidedFeedbackItems([lp]);
    expect(items).toHaveLength(2);
    expect(items.every((i) => i.completed === true)).toBe(true);
    const partial = buildGuidedFeedbackItems([{ ...lp, completedSets: 4 }]);
    expect(partial.every((i) => i.completed === false)).toBe(true);
  });

  it("instruction-only blocks are never sent", () => {
    expect(buildGuidedFeedbackItems([row({ isInstructionOnly: true, completedSets: 4 })])).toHaveLength(0);
    expect(guidedRowDone(row({ isInstructionOnly: true, completedSets: 4 }))).toBe(false);
  });
});

describe("repeater tests — the counter is reps to failure, never halved", () => {
  const repeater = (extra: Partial<GuidedExercise>) =>
    row({
      exerciseId: "test_repeater_7_3_to_failure",
      testField: undefined,
      prescription: { sets: 1, reps: 40, workSeconds: 7, restBetweenRepsSeconds: 3 },
      ...extra,
    });

  it("Done with 12 reps: completed_reps and completed_sets carry 12", () => {
    expect(item(repeater({ status: "done", completedSets: 12 }))).toMatchObject({
      completed: true,
      completed_sets: 12,
      completed_reps: 12,
    });
  });

  it("even flagged alt_sides, the reps are not halved", () => {
    expect(item(repeater({ status: "done", completedSets: 13, altSides: true }))).toMatchObject({
      completed_sets: 13,
      completed_reps: 13,
    });
  });

  it("a typed rep count does not close the test on its own", () => {
    expect(guidedRowDone(repeater({ status: "skipped", completedSets: 12 }))).toBe(false);
    expect(guidedRowDone(row({ exerciseId: "repeater_hang_7_3", completedSets: 18 }))).toBe(false);
  });
});

describe("custom / generated sessions — Done without the timer carries the prescribed sets", () => {
  const drill = (extra: Partial<GuidedExercise> = {}) =>
    row({
      exerciseId: "no_readjust_drill",
      loadModel: "bodyweight_only",
      prescription: { sets: 3, reps: 4 },
      status: "done",
      ...extra,
    });

  it("player session: Done with no counted set → prescription.sets", () => {
    expect(item(drill(), true).completed_sets).toBe(3);
  });

  it("catalog session: nothing added (Done is done)", () => {
    expect(item(drill(), false).completed_sets).toBeUndefined();
  });

  it("counted sets win; a skipped row gets nothing", () => {
    expect(item(drill({ completedSets: 2 }), true).completed_sets).toBe(2);
    expect(item(drill({ status: "skipped" }), true).completed_sets).toBeUndefined();
  });

  it("isPlayerSession mirrors the server (is_custom, custom_, generated_)", () => {
    expect(isPlayerSession("custom_cs_2ea7e4a9")).toBe(true);
    expect(isPlayerSession("generated_core_2026")).toBe(true);
    expect(isPlayerSession("adhoc_x", true)).toBe(true);
    expect(isPlayerSession("lead_tryhard_gym")).toBe(false);
    expect(isPlayerSession(undefined)).toBe(false);
  });

  it("the body builder (first POST and replay) passes the session kind", () => {
    const base = { date: "2026-11-07", startedAt: "2026-11-07T10:00:00Z", pain: undefined, isTestSession: false };
    const sent = (sessionId: string, isCustom?: boolean) =>
      (buildGuidedFeedbackBody({ ...base, sessionId, isCustom }, [drill()]).log_entry.actual as {
        exercise_feedback_v1: Array<Record<string, unknown>>;
      }).exercise_feedback_v1[0].completed_sets;
    expect(sent("custom_cs_1")).toBe(3);
    expect(sent("coach_adhoc", true)).toBe(3);
    expect(sent("strength_long")).toBeUndefined();
  });
});
