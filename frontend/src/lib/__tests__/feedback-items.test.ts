/**
 * B288: the dialog path must actually put the load in the payload.
 *
 * These pin the exact bug reported: a session closed from /today wrote a
 * feedback item with no `used_*` field, which apply_feedback discards.
 */
import { describe, it, expect } from "vitest";
import {
  buildDialogFeedbackItems,
  extractFeedbackExercises,
  hasLoadInput,
  buildGuidedFeedbackItems,
} from "@/lib/feedback-items";
import type { GuidedExercise } from "@/lib/types";

const PREHAB = {
  exercise_id: "reverse_wrist_curl",
  name: "Reverse Wrist Curl",
  loadModel: "external_load",
  suggestedExternalLoadKg: 2,
};

describe("extractFeedbackExercises", () => {
  it("carries load metadata out of a resolved session", () => {
    const session = {
      resolved: {
        resolved_session: {
          exercise_instances: [
            {
              exercise_id: "reverse_wrist_curl",
              name: "Reverse Wrist Curl",
              load_model: "external_load",
              suggested: { suggested_external_load_kg: 2 },
            },
            {
              exercise_id: "plank",
              load_model: "bodyweight_only",
              suggested: {},
            },
          ],
        },
      },
    };
    const out = extractFeedbackExercises(session);
    expect(out).toHaveLength(2);
    expect(out[0].suggestedExternalLoadKg).toBe(2);
    expect(hasLoadInput(out[0])).toBe(true);
    expect(hasLoadInput(out[1])).toBe(false);
  });
});

describe("buildDialogFeedbackItems", () => {
  it("sends the load the user typed (the reported bug)", () => {
    const items = buildDialogFeedbackItems(
      [PREHAB],
      { reverse_wrist_curl: "ok" },
      { reverse_wrist_curl: 5 },
    );
    expect(items[0]).toMatchObject({
      exercise_id: "reverse_wrist_curl",
      feedback_label: "ok",
      completed: true,
      used_external_load_kg: 5,
    });
  });

  it("sends the pre-filled suggestion when the user does not touch it", () => {
    const items = buildDialogFeedbackItems(
      [PREHAB],
      {},
      { reverse_wrist_curl: 2 },
    );
    expect(items[0].used_external_load_kg).toBe(2);
    expect(items[0].feedback_label).toBe("ok");
  });

  it("keeps a legitimate 0 kg", () => {
    const items = buildDialogFeedbackItems(
      [PREHAB],
      {},
      { reverse_wrist_curl: 0 },
    );
    expect(items[0].used_external_load_kg).toBe(0);
  });

  it("derives total load for hangboard-style exercises", () => {
    const items = buildDialogFeedbackItems(
      [{
        exercise_id: "max_hang_ladder",
        name: "Max Hang Ladder",
        loadModel: "total_load",
        suggestedExternalLoadKg: 30,
        suggestedTotalLoadKg: 105,
      }],
      {},
      { max_hang_ladder: 32 },
    );
    // bodyweight implied by the suggestion = 105 - 30 = 75
    expect(items[0].used_total_load_kg).toBe(107);
  });

  it("never sends a load for bodyweight-only exercises", () => {
    const items = buildDialogFeedbackItems(
      [{ exercise_id: "plank", name: "Plank", loadModel: "bodyweight_only" }],
      {},
      { plank: 99 },
    );
    expect(items[0].used_external_load_kg).toBeUndefined();
  });

  it("skips unilateral exercises — they need a per-hand split", () => {
    const items = buildDialogFeedbackItems(
      [{
        exercise_id: "lp_lift",
        name: "LP Lift",
        loadModel: "external_load",
        unilateral: true,
        suggestedExternalLoadKg: 20,
      }],
      {},
      { lp_lift: 20 },
    );
    expect(items[0].used_external_load_kg).toBeUndefined();
  });
});

describe("buildGuidedFeedbackItems", () => {
  const base: GuidedExercise = {
    exerciseId: "reverse_wrist_curl",
    name: "Reverse Wrist Curl",
    category: "prehab",
    blockUid: "",
    loadModel: "external_load",
    prescription: {},
    suggested: { externalLoadKg: 2 },
    status: "done",
    feedbackLabel: "ok",
  } as GuidedExercise;

  it("preserves the load on the offline replay path", () => {
    const items = buildGuidedFeedbackItems([{ ...base, usedLoadKg: 5 }]);
    expect(items[0].used_external_load_kg).toBe(5);
  });

  it("preserves notes and sets that the old replay dropped", () => {
    const items = buildGuidedFeedbackItems([
      { ...base, usedLoadKg: 5, completedSets: 3, notes: "left wrist twinge" },
    ]);
    expect(items[0]).toMatchObject({
      completed_sets: 3,
      completed_reps: 3,
      notes: "left wrist twinge",
    });
  });

  it("preserves the per-hand split that the old replay flattened", () => {
    const items = buildGuidedFeedbackItems([
      { ...base, unilateral: true, usedLoadKgRight: 20, usedLoadKgLeft: 18 },
    ]);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ hand: "right", used_external_load_kg: 20 });
    expect(items[1]).toMatchObject({ hand: "left", used_external_load_kg: 18 });
  });

  it("skips instruction-only blocks", () => {
    const items = buildGuidedFeedbackItems([
      { ...base, isInstructionOnly: true } as GuidedExercise,
    ]);
    expect(items).toHaveLength(0);
  });
});
