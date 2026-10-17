import { describe, expect, it } from "vitest";
import { bpmBand, hrMaxFromState, hrTargetLines, validHrMax } from "../hr-zones";

describe("A316 hr-zones", () => {
  it("computes bpm bands like the backend", () => {
    expect(bpmBand(190, [90, 95])).toEqual([171, 180]);
    expect(bpmBand(190, [60, 70])).toEqual([114, 133]);
    // .5 cases: inside the band on both ends (Python round() is half-even, Math.round half-up).
    expect(bpmBand(190, [65, 75])).toEqual([124, 142]);
    expect(bpmBand(185, [90, 95])).toEqual([167, 175]);
  });

  it("rejects implausible HRmax", () => {
    expect(validHrMax(190)).toBe(190);
    for (const bad of [undefined, null, 0, 90, 260, "190", NaN]) expect(validHrMax(bad)).toBeNull();
  });

  it("reads HRmax from body, then assessment.body", () => {
    expect(hrMaxFromState({ body: { hr_max_bpm: 190 } })).toBe(190);
    expect(hrMaxFromState({ body: {}, assessment: { body: { hr_max_bpm: 192 } } })).toBe(192);
    expect(hrMaxFromState({})).toBeNull();
  });

  it("renders bpm with HRmax, percentages without", () => {
    const t = { basis: "hr_max" as const, work_pct: [90, 95] as [number, number], recovery_pct: [65, 75] as [number, number] };
    expect(hrTargetLines(t, 190)).toEqual(["Work 171-180 bpm", "Recovery 124-142 bpm"]);
    expect(hrTargetLines(t, null)).toEqual(["Work 90-95% HRmax", "Recovery 65-75% HRmax"]);
    expect(hrTargetLines({ work_pct: [60, 70] }, 190)).toEqual(["Target 114-133 bpm"]);
    expect(hrTargetLines(undefined, 190)).toEqual([]);
  });
});
