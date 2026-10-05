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
    // A295: an untouched exercise is NOT RATED — no label at all, never "ok".
    expect("feedback_label" in items[0]).toBe(false);
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
      notes: "left wrist twinge",
    });
    // A295: completed_reps is no longer a copy of completed_sets…
    expect(items[0].completed_reps).toBeUndefined();
  });

  it("keeps completed_reps for the repeater test only (B133)", () => {
    const items = buildGuidedFeedbackItems([
      { ...base, exerciseId: "test_repeater_7_3_to_failure", completedSets: 14 },
    ]);
    expect(items[0].completed_reps).toBe(14);
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

describe("hasLoadInput — B298 (loadable is always loggable, even first time)", () => {
  it("a loadable exercise with NO suggested load still takes a load", () => {
    // The reported bug: adhoc Back Squat, never logged → no suggestion → the
    // field was hidden and the load could not be recorded at all.
    expect(
      hasLoadInput({ exercise_id: "back_squat", name: "Back Squat", loadModel: "external_load" }),
    ).toBe(true);
    expect(
      hasLoadInput({ exercise_id: "weighted_pullup", name: "Weighted Pull-up", loadModel: "total_load" }),
    ).toBe(true);
  });

  it("a suggested load is not required (but still works)", () => {
    expect(
      hasLoadInput({ exercise_id: "bench_press", name: "Bench Press", loadModel: "external_load", suggestedExternalLoadKg: 40 }),
    ).toBe(true);
  });

  it("bodyweight exercises get no load field (unless opted in)", () => {
    expect(hasLoadInput({ exercise_id: "plank", name: "Plank", loadModel: "bodyweight_only" })).toBe(false);
    expect(
      hasLoadInput({ exercise_id: "pallof_press", name: "Pallof Press", loadModel: "bodyweight_only", allowLoadLogging: true }),
    ).toBe(true);
  });

  it("unilateral loadable exercises are excluded (per-hand handled elsewhere)", () => {
    expect(
      hasLoadInput({ exercise_id: "lp_max_lift_5s", name: "LP Max Lift", loadModel: "external_load", unilateral: true }),
    ).toBe(false);
  });
});

describe("A295 measured feedback", () => {
  const pull: GuidedExercise = {
    exerciseId: "weighted_pullup",
    name: "Weighted pull-up",
    category: "main_strength",
    blockUid: "",
    loadModel: "total_load",
    prescription: { sets: 4, reps: 3 },
    suggested: { externalLoadKg: 30, totalLoadKg: 108, measure: "last_set_reps" },
    status: "done",
    feedbackLabel: null,
  } as GuidedExercise;

  it("omits the label of an untouched guided exercise", () => {
    const items = buildGuidedFeedbackItems([{ ...pull, usedLoadKg: 30 }]);
    expect("feedback_label" in items[0]).toBe(false);
  });

  it("sends last_set_reps only where the server asked for it", () => {
    const items = buildGuidedFeedbackItems([
      { ...pull, usedLoadKg: 30, lastSetReps: 7 },
      { ...pull, exerciseId: "plank", suggested: {}, lastSetReps: 7 },
    ]);
    expect(items[0].last_set_reps).toBe(7);
    expect(items[1].last_set_reps).toBeUndefined();
  });

  it("sends the hang margin and the timed hold, never on a skipped hang", () => {
    const hang = {
      ...pull,
      exerciseId: "max_hang_7s",
      suggested: { measure: "hang_margin" as const },
      hangMargin: ">5" as const,
      hangHeldS: 12.4,
    };
    const [done] = buildGuidedFeedbackItems([hang]);
    expect(done).toMatchObject({ hang_margin: ">5", hang_held_s: 12.4 });
    const [skipped] = buildGuidedFeedbackItems([{ ...hang, status: "skipped" }]);
    expect(skipped.hang_margin).toBeUndefined();
  });

  it("double progression carries the target shown with the measured reps", () => {
    const bench = {
      ...pull,
      exerciseId: "bench_press",
      loadModel: "external_load",
      suggested: { externalLoadKg: 34.5, measure: "dp_reps" as const, targetReps: 5 },
      lastSetReps: 6,
      usedLoadKg: 34.5,
    };
    expect(buildGuidedFeedbackItems([bench])[0]).toMatchObject({ last_set_reps: 6, target_reps: 5 });
    const noMeasure = buildGuidedFeedbackItems([{ ...bench, lastSetReps: undefined }])[0];
    expect(noMeasure.target_reps).toBeUndefined();
  });

  it("dialog: rated label + measures, untouched stays unrated", () => {
    const items = buildDialogFeedbackItems(
      [
        { exercise_id: "weighted_pullup", name: "Pull", loadModel: "total_load", measure: "last_set_reps", prescribedReps: 3 },
        { ...PREHAB },
      ],
      { weighted_pullup: "easy" },
      {},
      { weighted_pullup: { lastSetReps: 5 } },
    );
    expect(items[0]).toMatchObject({ feedback_label: "easy", last_set_reps: 5 });
    expect("feedback_label" in items[1]).toBe(false);
  });

  it("extractFeedbackExercises reads measure and target from suggested", () => {
    const out = extractFeedbackExercises({
      resolved: { resolved_session: { exercise_instances: [{
        exercise_id: "bench_press",
        load_model: "external_load",
        prescription: { sets: 3, reps: 4 },
        suggested: { measure: "dp_reps", target_reps: 5, suggested_external_load_kg: 34.5 },
      }] } },
    });
    expect(out[0]).toMatchObject({ measure: "dp_reps", targetReps: 5, prescribedReps: 4 });
  });
});

describe("A296 — limit problem log in guided feedback items", () => {
  const limit = {
    exerciseId: "limit_bouldering",
    name: "Limit bouldering",
    category: "climbing",
    blockUid: "",
    loadModel: "grade_relative",
    prescription: {},
    suggested: { grade: "7B", surface: "board_kilter", logProblems: true },
    status: "done",
    feedbackLabel: null,
  } as GuidedExercise;

  it("sends the problems with the surface and the hardest send", () => {
    const problems = [
      { grade: "7B", attempts: 3, outcome: "sent" as const },
      { grade: "7B+", attempts: 5, outcome: "high_point" as const },
    ];
    const [item] = buildGuidedFeedbackItems([{ ...limit, usedGrade: "7B", problems }]);
    expect(item).toMatchObject({ exercise_id: "limit_bouldering", used_grade: "7B", surface_selected: "board_kilter", problems });
    expect(item.feedback_label).toBeUndefined();
  });

  it("never sends problems for a skipped exercise", () => {
    const [item] = buildGuidedFeedbackItems([
      { ...limit, status: "skipped", problems: [{ grade: "7B", attempts: 1, outcome: "sent" }] },
    ]);
    expect(item.problems).toBeUndefined();
  });
});

describe("A298 — bodyweight ladder dose source travels with the feedback", () => {
  it("tags the dialog item when the resolver prescribed the ladder dose", () => {
    const session = {
      resolved: {
        resolved_session: {
          exercise_instances: [
            { exercise_id: "straddle_l_sit", load_model: "bodyweight_only", prescription: { source: "bw_ladder", sets: 3 } },
            { exercise_id: "plank", load_model: "bodyweight_only", prescription: { sets: 2 } },
          ],
        },
      },
    };
    const exs = extractFeedbackExercises(session);
    const items = buildDialogFeedbackItems(exs, { straddle_l_sit: "easy", plank: "easy" }, {});
    expect(items[0].bw_ladder).toBe("engine");
    expect(items[1].bw_ladder).toBeUndefined();
  });

  it("tags the guided item from suggested.ladderSource", () => {
    const ex = {
      exerciseId: "straddle_l_sit",
      name: "Straddle L-sit",
      category: "core",
      blockUid: "",
      loadModel: "bodyweight_only",
      prescription: {},
      suggested: { ladderSource: "engine" },
      status: "done",
      feedbackLabel: "easy",
    } as GuidedExercise;
    expect(buildGuidedFeedbackItems([ex])[0].bw_ladder).toBe("engine");
    const plain = { ...ex, suggested: {} } as GuidedExercise;
    expect(buildGuidedFeedbackItems([plain])[0].bw_ladder).toBeUndefined();
  });
});
