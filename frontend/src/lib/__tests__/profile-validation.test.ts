// B293 — profile sanity bounds (mirrors backend _validate_profile)
import { describe, expect, it } from "vitest";
import { profileErrors, fieldBoundError } from "../profile-validation";

const valid = { name: "Dani", age: 40, weight_kg: 66, height_cm: 172 };

describe("profileErrors", () => {
  it("accepts a valid profile", () => {
    expect(profileErrors(valid)).toEqual([]);
  });

  it("rejects the post-clobber default profile (the 0/0/0 case)", () => {
    const errs = profileErrors({ name: "", age: 0, weight_kg: 0, height_cm: 0 });
    expect(errs).toHaveLength(4);
  });

  it.each([
    ["weight_kg", 0],
    ["weight_kg", 29],
    ["weight_kg", 151],
    ["height_cm", 119],
    ["height_cm", 221],
    ["age", 0],
    ["age", 100],
  ] as const)("rejects %s = %d", (field, value) => {
    const errs = profileErrors({ ...valid, [field]: value });
    expect(errs).toHaveLength(1);
  });

  it("rejects a whitespace-only name", () => {
    expect(profileErrors({ ...valid, name: "  " })).toHaveLength(1);
  });

  it("accepts boundary values", () => {
    expect(profileErrors({ ...valid, weight_kg: 30, height_cm: 220, age: 99 })).toEqual([]);
  });
});

describe("fieldBoundError", () => {
  it("stays silent on an untouched (0) field", () => {
    expect(fieldBoundError("weight_kg", 0)).toBeNull();
  });

  it("flags an out-of-bounds typed value", () => {
    expect(fieldBoundError("weight_kg", 20)).toMatch(/between 30 and 150/);
  });

  it("stays silent inside bounds", () => {
    expect(fieldBoundError("height_cm", 180)).toBeNull();
  });
});
