// A304 — every weighted custom row follows the training load unless fixed
// (backend A302 `custom_working_load`); the builder shows Auto / Fixed kg on all.
import { describe, expect, it } from "vitest";
import { followsTrainingLoad, isAutoLoadRow } from "../anchored-load";

describe("followsTrainingLoad", () => {
  it("is true for a weighted non-anchored row", () => {
    expect(followsTrainingLoad({ exercise_id: "reverse_wrist_curl" }, "external_load")).toBe(true);
    expect(followsTrainingLoad({ exercise_id: "repeaters_7_3" }, "total_load")).toBe(true);
  });
  it("is false for anchored, bodyweight, ladder-progress and unknown rows", () => {
    expect(followsTrainingLoad({ exercise_id: "weighted_pullup" }, "total_load")).toBe(false);
    expect(followsTrainingLoad({ exercise_id: "hollow_body_hold" }, "bodyweight_only")).toBe(false);
    expect(followsTrainingLoad({ exercise_id: "pallof_press", progress_mode: "ladder" }, "external_load")).toBe(false);
    expect(followsTrainingLoad({ exercise_id: "reverse_wrist_curl" }, undefined)).toBe(false);
  });
});

describe("isAutoLoadRow", () => {
  it("covers anchored and followed rows, never a fixed one", () => {
    expect(isAutoLoadRow({ exercise_id: "max_hang_7s" }, "total_load")).toBe(true);
    expect(isAutoLoadRow({ exercise_id: "romanian_deadlift" }, "external_load")).toBe(true);
    expect(isAutoLoadRow({ exercise_id: "romanian_deadlift", load_mode: "fixed" }, "external_load")).toBe(false);
    expect(isAutoLoadRow({ exercise_id: "max_hang_7s", load_mode: "fixed" }, "total_load")).toBe(false);
    expect(isAutoLoadRow({ exercise_id: "hollow_body_hold" }, "bodyweight_only")).toBe(false);
  });
});
