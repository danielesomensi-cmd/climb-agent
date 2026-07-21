import { describe, it, expect } from "vitest";
import { detectCategory } from "../custom-exercise-step";
import { colorForRatio } from "../custom-rest-timer";
import type { CustomSessionExercise } from "@/lib/types";

function ex(overrides: Partial<CustomSessionExercise>): CustomSessionExercise {
  return {
    exercise_id: "x",
    sets: 1,
    reps: null,
    work_seconds: null,
    rest_between_sets_seconds: null,
    rest_between_reps_seconds: null,
    load_kg: 0,
    notes: "",
    ...overrides,
  };
}

describe("detectCategory", () => {
  it("classifies single-set work as time_based", () => {
    expect(detectCategory(ex({ sets: 1, work_seconds: 30 }))).toBe("time_based");
  });

  it("classifies multi-set work as timed_sets", () => {
    expect(detectCategory(ex({ sets: 4, work_seconds: 30 }))).toBe("timed_sets");
  });

  it("classifies reps-only as reps_based", () => {
    expect(detectCategory(ex({ sets: 3, reps: 10 }))).toBe("reps_based");
  });

  it("prefers work over reps when both present (hangboard-style)", () => {
    expect(detectCategory(ex({ sets: 6, work_seconds: 7, reps: 5 }))).toBe("timed_sets");
  });

  it("falls back to reps_based when neither work nor reps present", () => {
    expect(detectCategory(ex({ sets: 1 }))).toBe("reps_based");
  });
});

describe("colorForRatio", () => {
  it("returns green at or under target", () => {
    expect(colorForRatio(0)).toBe("green");
    expect(colorForRatio(0.5)).toBe("green");
    expect(colorForRatio(1.0)).toBe("green");
  });

  it("returns yellow between 1.0x and 1.2x", () => {
    expect(colorForRatio(1.01)).toBe("yellow");
    expect(colorForRatio(1.1)).toBe("yellow");
    expect(colorForRatio(1.2)).toBe("yellow");
  });

  it("returns red above 1.2x", () => {
    expect(colorForRatio(1.21)).toBe("red");
    expect(colorForRatio(2.0)).toBe("red");
  });
});
