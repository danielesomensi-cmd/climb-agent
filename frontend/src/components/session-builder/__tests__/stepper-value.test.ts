/**
 * A309 — the params drawer's steppers can now be typed into. The −/+ buttons
 * keep their pre-A309 semantics and a typed value is clamped to the same
 * min/max the buttons respect.
 */

import { describe, it, expect } from "vitest";
import { parseStepperInput, stepValue, type StepperBounds } from "../stepper-value";

const SETS: StepperBounds = { min: 1, max: 20, step: 1 };
const REPS: StepperBounds = { min: 1, max: 100, step: 1, nullable: true };
const KG: StepperBounds = { min: 0, max: 200, step: 0.5, decimals: 2 };
const REST: StepperBounds = { min: 0, max: 600, step: 15, nullable: true };

describe("stepValue (− / +)", () => {
  it("steps and clamps to max", () => {
    expect(stepValue(3, 1, SETS)).toBe(4);
    expect(stepValue(20, 1, SETS)).toBe(20);
    expect(stepValue(595, 1, REST)).toBe(600);
  });

  it("− stops at min on a non-nullable field", () => {
    expect(stepValue(1, -1, SETS)).toBe(1);
  });

  it("− below min clears a nullable field; + from null starts at one step", () => {
    expect(stepValue(1, -1, REPS)).toBeNull();
    expect(stepValue(null, 1, REPS)).toBe(1);
    expect(stepValue(0, -1, REST)).toBeNull();
    expect(stepValue(null, 1, REST)).toBe(15);
  });

  it("kg moves in 0.5 steps without float noise", () => {
    expect(stepValue(32, 1, KG)).toBe(32.5);
    expect(stepValue(0.1, 1, KG)).toBe(0.6);
    expect(stepValue(0.2, -1, KG)).toBe(0);
    expect(stepValue(0, -1, KG)).toBe(0);
  });
});

describe("parseStepperInput (typed)", () => {
  it("accepts a decimal kg, with dot or comma", () => {
    expect(parseStepperInput("32.5", 30, KG)).toBe(32.5);
    expect(parseStepperInput("32,5", 30, KG)).toBe(32.5);
    expect(parseStepperInput(" 17.25 ", 30, KG)).toBe(17.25);
  });

  it("clamps to the same bounds as the buttons", () => {
    expect(parseStepperInput("250", 30, KG)).toBe(200);
    expect(parseStepperInput("-4", 30, KG)).toBe(0);
    expect(parseStepperInput("0", 5, SETS)).toBe(1);
    expect(parseStepperInput("99", 5, SETS)).toBe(20);
    expect(parseStepperInput("1000", 60, REST)).toBe(600);
  });

  it("rounds integer fields", () => {
    expect(parseStepperInput("4.6", 3, SETS)).toBe(5);
    expect(parseStepperInput("12.4", 8, REPS)).toBe(12);
  });

  it("empty clears a nullable field and keeps the value otherwise", () => {
    expect(parseStepperInput("", 8, REPS)).toBeNull();
    expect(parseStepperInput("  ", 3, SETS)).toBe(3);
    expect(parseStepperInput("", 30, KG)).toBe(30);
  });

  it("garbage keeps the previous value", () => {
    expect(parseStepperInput("abc", 30, KG)).toBe(30);
    expect(parseStepperInput("3..5", 3, SETS)).toBe(3);
    expect(parseStepperInput("abc", null, REPS)).toBeNull();
  });
});
