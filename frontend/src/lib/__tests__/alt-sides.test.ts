import { describe, expect, it } from "vitest";

import {
  SIDE_SWITCH_S,
  displaySetNumber,
  isSideSwitch,
  restAfterSet,
  sideForSet,
  sideSwitchSeconds,
  totalSetsWithSides,
} from "@/lib/alt-sides";

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

  it("B404: a short side switch after RIGHT, the full set rest after LEFT", () => {
    // 3x20s side plank, 60s rest: R, switch, L, rest, R, switch, L, rest, R, switch, L.
    expect([1, 2, 3, 4, 5].map((n) => restAfterSet(n, true, 60))).toEqual([
      SIDE_SWITCH_S, 60, SIDE_SWITCH_S, 60, SIDE_SWITCH_S,
    ]);
    expect([1, 2, 3, 4, 5].map((n) => isSideSwitch(n, true))).toEqual([true, false, true, false, true]);
  });

  it("B404: bilateral exercises keep the set rest after every set", () => {
    expect([1, 2].map((n) => restAfterSet(n, false, 90))).toEqual([90, 90]);
    expect(isSideSwitch(1, false)).toBe(false);
  });

  it("B404: the switch is never longer than the set rest, and exists with no set rest", () => {
    expect(sideSwitchSeconds(10)).toBe(10);
    expect(sideSwitchSeconds(180)).toBe(SIDE_SWITCH_S);
    // A stretch written back-to-back still needs time to change sides.
    expect(sideSwitchSeconds(0)).toBe(SIDE_SWITCH_S);
    expect(restAfterSet(2, true, 0)).toBe(0);
  });
});
