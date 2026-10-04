// B364 review — the notes promised by the user guide (ceiling, fatigue) must
// reach the screen: the backend computes them, these lines render them.
import { describe, expect, it } from "vitest";
import { anchoredLoadNotes, isAnchoredExercise } from "../anchored-load";

describe("isAnchoredExercise", () => {
  it("knows the four anchored exercises", () => {
    for (const id of ["max_hang_5s", "max_hang_7s", "weighted_pullup", "weighted_chinup"]) {
      expect(isAnchoredExercise(id)).toBe(true);
    }
    expect(isAnchoredExercise("dip")).toBe(false);
    expect(isAnchoredExercise(undefined)).toBe(false);
  });
});

describe("anchoredLoadNotes", () => {
  it("returns nothing for a non-anchored prescription", () => {
    expect(anchoredLoadNotes(undefined)).toEqual([]);
    expect(anchoredLoadNotes({ suggested_total_load_kg: 90 })).toEqual([]);
  });

  it("surfaces the ceiling note", () => {
    const notes = anchoredLoadNotes({
      ceiling_note: "You are at the ceiling of your tested max — the next scheduled retest will raise it.",
      anchored: { clamped: "cap", ramp: { n: 3, factor: 1 } },
    });
    expect(notes).toHaveLength(1);
    expect(notes[0]).toMatch(/ceiling of your tested max/);
  });

  it("surfaces fatigue, pain and re-entry", () => {
    const notes = anchoredLoadNotes({
      anchored: {
        clamped: "fatigue_floor",
        fatigue: { axis: "finger", hard_days: ["2026-10-01", "2026-10-03", "2026-10-06"] },
        pain: { site: "fingers", score: 2, from: "2026-10-05", until: "2026-10-12" },
        ramp: { n: 1, factor: 0.9 },
      },
    });
    expect(notes).toHaveLength(3);
    expect(notes[0]).toMatch(/3 hard sessions/);
    expect(notes[1]).toBe("Pain reported (2/3): load reduced until 2026-10-12.");
    expect(notes[2]).toBe("Back after a break (session 1 of 3): capped at 90% of the usual ceiling.");
  });
});
