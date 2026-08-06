import { describe, it, expect } from "vitest";

import { normaliseLadder, summarisePitches } from "../pitch-ladder";
import type { PitchLadderRow } from "../types";

const row = (over: Partial<PitchLadderRow> = {}): PitchLadderRow => ({
  index: 1,
  role: "main",
  grade: "7a",
  attempts: 1,
  rest_after_min: 10,
  ...over,
});

describe("normaliseLadder", () => {
  it("keeps the user's grades verbatim", () => {
    const out = normaliseLadder([row({ grade: "7c+" })]);
    expect(out?.pitches[0].grade).toBe("7c+");
  });

  it("drops rows with no grade and re-indexes what is left", () => {
    const out = normaliseLadder([
      row({ grade: "6a" }),
      row({ grade: "   " }),
      row({ grade: "7a" }),
    ]);
    expect(out?.pitches.map((p) => p.grade)).toEqual(["6a", "7a"]);
    expect(out?.pitches.map((p) => p.index)).toEqual([1, 2]);
  });

  it("returns null when every row is empty — that clears the day's plan", () => {
    expect(normaliseLadder([row({ grade: "" })])).toBeNull();
    expect(normaliseLadder([])).toBeNull();
  });

  it("never emits fewer than one attempt", () => {
    const out = normaliseLadder([row({ attempts: 0 }), row({ attempts: NaN })]);
    expect(out?.pitches.every((p) => p.attempts >= 1)).toBe(true);
  });

  it("clamps a negative rest to zero", () => {
    const out = normaliseLadder([row({ rest_after_min: -5 })]);
    expect(out?.pitches[0].rest_after_min).toBe(0);
  });

  it("trims whitespace around a grade", () => {
    const out = normaliseLadder([row({ grade: "  7b+  " })]);
    expect(out?.pitches[0].grade).toBe("7b+");
  });

  it("marks the ladder as no longer generated", () => {
    const out = normaliseLadder([row()], { pitches: [], generated: true });
    expect(out?.generated).toBe(false);
  });

  it("carries the day_type through so regenerate still knows the day", () => {
    const out = normaliseLadder([row()], {
      pitches: [],
      day_type: "onsight_flash",
      onsight_grade: "7a+",
    });
    expect(out?.day_type).toBe("onsight_flash");
    expect(out?.onsight_grade).toBe("7a+");
  });

  it("recomputes the summary from the edited rows", () => {
    const out = normaliseLadder([
      row({ attempts: 2, rest_after_min: 15 }),
      row({ attempts: 1, rest_after_min: 0 }),
    ]);
    expect(out?.summary).toEqual({
      pitch_count: 2,
      total_attempts: 3,
      estimated_hours: 0.9, // (3*12 + 15) / 60
    });
  });
});

describe("summarisePitches", () => {
  it("matches the backend estimate for the generated onsight day", () => {
    // 8 burns, rests 10+10+12+15+15+10+0 = 72 → (96 + 72) / 60 = 2.8 h
    const pitches = [
      row({ attempts: 1, rest_after_min: 10 }),
      row({ attempts: 1, rest_after_min: 10 }),
      row({ attempts: 1, rest_after_min: 12 }),
      row({ attempts: 1, rest_after_min: 15 }),
      row({ attempts: 2, rest_after_min: 15 }),
      row({ attempts: 1, rest_after_min: 10 }),
      row({ attempts: 1, rest_after_min: 0 }),
    ];
    expect(summarisePitches(pitches)).toEqual({
      pitch_count: 7,
      total_attempts: 8,
      estimated_hours: 2.8,
    });
  });
});
