import { describe, expect, it } from "vitest";

import { guidedNextLabel } from "@/lib/guided-next-label";

/**
 * A307 — "Next · …" under the guided timer during a rest. Mirrors the custom
 * player's rest label so both players say the same thing.
 */
describe("guidedNextLabel", () => {
  it("names the next set while sets remain", () => {
    expect(guidedNextLabel({ completedSets: 1, sets: 3, altSides: false })).toBe("Set 2 of 3");
    expect(guidedNextLabel({ completedSets: 0, sets: 3, altSides: false })).toBe("Set 1 of 3");
  });

  it("treats a missing completed count as nothing done", () => {
    expect(guidedNextLabel({ completedSets: undefined, sets: 4, altSides: false })).toBe("Set 1 of 4");
  });

  it("adds the side for alt_sides exercises (internal sets are doubled)", () => {
    // RIGHT set 1 done → LEFT of the same prescribed set.
    expect(guidedNextLabel({ completedSets: 1, sets: 3, altSides: true })).toBe("Set 1 of 3 · LEFT");
    // Both sides of set 1 done → RIGHT of set 2.
    expect(guidedNextLabel({ completedSets: 2, sets: 3, altSides: true })).toBe("Set 2 of 3 · RIGHT");
  });

  it("names the next exercise once the last set is done", () => {
    expect(
      guidedNextLabel({ completedSets: 3, sets: 3, altSides: false, nextExerciseName: "Campus ladders" }),
    ).toBe("Campus ladders");
    expect(
      guidedNextLabel({ completedSets: 6, sets: 3, altSides: true, nextExerciseName: "Plank" }),
    ).toBe("Plank");
  });

  it("says Finish on the last exercise of the session", () => {
    expect(guidedNextLabel({ completedSets: 3, sets: 3, altSides: false })).toBe("Finish");
    expect(guidedNextLabel({ completedSets: 3, sets: 3, altSides: false, nextExerciseName: null })).toBe("Finish");
  });

  it("treats a missing set count as one set", () => {
    expect(guidedNextLabel({ completedSets: 0, sets: null, altSides: false })).toBe("Set 1 of 1");
    expect(guidedNextLabel({ completedSets: 1, sets: null, altSides: false, nextExerciseName: "X" })).toBe("X");
  });
});
