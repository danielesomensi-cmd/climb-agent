/**
 * A295 (R4) — measured-feedback helpers: contract marker, pain, stepper range.
 */
import { describe, it, expect } from "vitest";
import {
  FEEDBACK_CONTRACT,
  OVERHOLD_CAP_S,
  asMeasure,
  lastSetStepperMax,
  measureFields,
  withFeedbackContract,
} from "@/lib/measured-feedback";

describe("withFeedbackContract", () => {
  it("marks the log entry with contract 2", () => {
    const out = withFeedbackContract({ date: "2026-10-05", session_id: "s" });
    expect(out.feedback_contract).toBe(FEEDBACK_CONTRACT);
    expect(out.feedback_contract).toBe(2);
    expect("pain" in out).toBe(false);
  });

  it("carries the pain, and the zone only from score 2", () => {
    expect(withFeedbackContract({}, { score: 2, site: "fingers" }).pain).toEqual({ score: 2, site: "fingers" });
    expect(withFeedbackContract({}, { score: 1, site: "fingers" }).pain).toEqual({ score: 1, site: null });
    expect("pain" in withFeedbackContract({}, null)).toBe(false);
  });
});

describe("lastSetStepperMax", () => {
  it("reaches 8 on a 4x3 pull-up (7 reps at +30 is the retest signal)", () => {
    expect(lastSetStepperMax(3)).toBe(8);
  });
  it("is prescribed + 4 for longer sets, capped at 20", () => {
    expect(lastSetStepperMax(8)).toBe(12);
    expect(lastSetStepperMax(18)).toBe(20);
    expect(lastSetStepperMax(4, 6)).toBe(10);
  });
});

describe("measureFields", () => {
  it("returns nothing without a measure or a value", () => {
    expect(measureFields(undefined, { lastSetReps: 5 })).toEqual({});
    expect(measureFields("last_set_reps", {})).toEqual({});
  });
  it("never mixes measures", () => {
    expect(measureFields("hang_margin", { lastSetReps: 5, hangMargin: "3-5" })).toEqual({ hang_margin: "3-5" });
    expect(measureFields("last_set_reps", { hangMargin: "3-5", lastSetReps: 4, targetReps: 3 })).toEqual({ last_set_reps: 4 });
  });
});

describe("asMeasure / overhold cap", () => {
  it("accepts only the three kinds", () => {
    expect(asMeasure("dp_reps")).toBe("dp_reps");
    expect(asMeasure("rpe")).toBeUndefined();
    expect(asMeasure(undefined)).toBeUndefined();
  });
  it("caps the overhold at target + 6 s", () => {
    expect(OVERHOLD_CAP_S).toBe(6);
  });
});
