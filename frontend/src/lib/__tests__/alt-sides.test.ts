import { describe, expect, it } from "vitest";

import { displaySetNumber, sideForSet, totalSetsWithSides } from "@/lib/alt-sides";

/**
 * B324: the custom-session player must alternate sides exactly like the guided
 * player's ExerciseTimer (B169-F3b) — a 3-set Copenhagen plank is six bouts,
 * RIGHT first, and the label the athlete reads stays "Set 2 of 3".
 */
describe("alt-sides", () => {
  it("doubles the set count only for side-alternating exercises", () => {
    expect(totalSetsWithSides(3, true)).toBe(6);
    expect(totalSetsWithSides(3, false)).toBe(3);
  });

  it("treats a missing set count as one set", () => {
    expect(totalSetsWithSides(null, true)).toBe(2);
    expect(totalSetsWithSides(undefined, false)).toBe(1);
  });

  it("starts on the right and alternates every internal set", () => {
    expect(sideForSet(1, true)).toBe("RIGHT");
    expect(sideForSet(2, true)).toBe("LEFT");
    expect(sideForSet(3, true)).toBe("RIGHT");
    expect(sideForSet(4, true)).toBe("LEFT");
  });

  it("has no side for bilateral exercises", () => {
    expect(sideForSet(1, false)).toBeNull();
    expect(sideForSet(2, false)).toBeNull();
  });

  it("shows the prescribed set number, not the internal one", () => {
    // Internal sets 1..6 map to prescribed sets 1,1,2,2,3,3.
    expect([1, 2, 3, 4, 5, 6].map((n) => displaySetNumber(n, true))).toEqual([1, 1, 2, 2, 3, 3]);
    expect([1, 2, 3].map((n) => displaySetNumber(n, false))).toEqual([1, 2, 3]);
  });

  it("matches the guided player's convention end to end", () => {
    // A 3x20s Copenhagen plank: six bouts, three per side, R before L.
    const total = totalSetsWithSides(3, true);
    const run = Array.from({ length: total }, (_, i) => ({
      label: `Set ${displaySetNumber(i + 1, true)} of 3`,
      side: sideForSet(i + 1, true),
    }));
    expect(run.filter((s) => s.side === "RIGHT")).toHaveLength(3);
    expect(run.filter((s) => s.side === "LEFT")).toHaveLength(3);
    expect(run[5].label).toBe("Set 3 of 3");
  });
});
