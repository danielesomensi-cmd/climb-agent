import { describe, expect, it } from "vitest";

import { formatPrescription } from "@/components/guided/guided-exercise-step";
import { buildGuidedStateFromExercises } from "@/lib/guided-session-utils";

/**
 * B351: custom, coach ad-hoc and body-part sessions reach the real guided
 * player through buildGuidedStateFromExercises. B324 made the server stamp
 * `alt_sides` on those instances, but this builder never copied it — so a
 * Pallof press ran 3 sets on one side, with no RIGHT/LEFT badge.
 */
describe("guided player — alt_sides on flat custom exercises", () => {
  const pallof = {
    exercise_id: "pallof_press",
    name: "Pallof Press (Anti-Rotation)",
    sets: 3,
    reps: 10,
    rest_between_sets_seconds: 30,
    load_kg: 10,
    alt_sides: true,
  };
  const plank = { exercise_id: "plank", sets: 3, work_seconds: 30 };

  it("carries alt_sides into the guided exercise", () => {
    const state = buildGuidedStateFromExercises("custom_x", "Core", "2026-09-11", [pallof, plank]);
    expect(state?.exercises[0].altSides).toBe(true);
    expect(state?.exercises[1].altSides).toBe(false);
  });

  it("never treats a truthy non-boolean as per-side", () => {
    const state = buildGuidedStateFromExercises("custom_x", "Core", "2026-09-11", [
      { ...pallof, alt_sides: "false" },
    ]);
    expect(state?.exercises[0].altSides).toBe(false);
  });

  it("labels the prescription per side", () => {
    const state = buildGuidedStateFromExercises("custom_x", "Core", "2026-09-11", [pallof, plank]);
    expect(formatPrescription(state!.exercises[0])[0]).toBe("3 × 10 per side");
    expect(formatPrescription(state!.exercises[1])[0]).toBe("3 × 30s");
  });
});
