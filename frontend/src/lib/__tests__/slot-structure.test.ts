import { describe, it, expect } from "vitest";
import {
  effectiveRole,
  effectiveRotation,
  isComplementary,
  isPrimaryCapable,
  moveItem,
  parseMaxMinutes,
  slotStructureLabel,
  withFocus,
  withMaxMinutes,
  withRole,
  type StructuredSlot,
} from "@/lib/slot-structure";

/**
 * A300 — the editor must write a field only when the user set it: a user who
 * never touches role / max_minutes / focus sends the same slots as before A300,
 * so the backend's byte-identity guarantee holds end to end.
 */

const base: StructuredSlot = { available: true, preferred_location: "gym", gym_id: "g1" };

describe("withRole", () => {
  it("sets a role", () => {
    expect(withRole(base, "complementary", undefined).role).toBe("complementary");
  });

  it("'any' on a slot that never had a role removes the key (no new field sent)", () => {
    const touched = withRole(withRole(base, "primary", undefined), "any", undefined);
    expect("role" in touched).toBe(false);
    expect(touched).toEqual(base);
  });

  it("'any' on a slot that had a stored role writes 'any' (the server deep-merges)", () => {
    const stored = { ...base, role: "complementary" as const };
    expect(withRole(stored, "any", stored).role).toBe("any");
  });

  it("leaving complementary clears a pinned focus", () => {
    const pinned = withFocus(withRole(base, "complementary", undefined), "legs", undefined);
    expect(pinned.focus).toBe("legs");
    const back = withRole(pinned, "primary", undefined);
    expect("focus" in back).toBe(false);
  });
});

describe("withMaxMinutes / withFocus", () => {
  it("null removes a never-stored key and nulls a stored one", () => {
    expect("max_minutes" in withMaxMinutes(withMaxMinutes(base, 45, undefined), null, undefined)).toBe(false);
    const stored = { ...base, max_minutes: 45 };
    expect(withMaxMinutes(stored, null, stored).max_minutes).toBeNull();
    const pinned = { ...base, role: "complementary" as const, focus: "hiit" as const };
    expect(withFocus(pinned, null, pinned).focus).toBeNull();
  });
});

describe("parseMaxMinutes", () => {
  it("accepts 10..240 integers, empty = no limit", () => {
    expect(parseMaxMinutes("45")).toBe(45);
    expect(parseMaxMinutes(" 10 ")).toBe(10);
    expect(parseMaxMinutes("240")).toBe(240);
    expect(parseMaxMinutes("")).toBeNull();
  });

  it("rejects what the backend would 422", () => {
    for (const bad of ["9", "241", "4.5", "abc", "-20"]) {
      expect(Number.isNaN(parseMaxMinutes(bad))).toBe(true);
    }
  });
});

describe("role predicates", () => {
  it("absent / unknown role is 'any' (the pre-A300 behaviour)", () => {
    expect(effectiveRole(base)).toBe("any");
    expect(effectiveRole({ ...base, role: null })).toBe("any");
  });

  it("complementary slots do not count as training days / sessions", () => {
    expect(isPrimaryCapable(base)).toBe(true);
    expect(isPrimaryCapable({ ...base, role: "primary" })).toBe(true);
    expect(isPrimaryCapable({ ...base, role: "complementary" })).toBe(false);
    expect(isComplementary({ ...base, role: "complementary" })).toBe(true);
    expect(isPrimaryCapable({ ...base, preferred_location: "other_sport" })).toBe(false);
    expect(isPrimaryCapable({ ...base, available: false })).toBe(false);
  });
});

describe("rotation", () => {
  it("absent = all four families in the engine's order", () => {
    expect(effectiveRotation(undefined)).toEqual(["legs", "hiit", "z2", "upper_push_arms"]);
    expect(effectiveRotation(null)).toEqual(["legs", "hiit", "z2", "upper_push_arms"]);
  });

  it("keeps order and drops unknown families", () => {
    expect(effectiveRotation(["z2", "bogus", "legs"])).toEqual(["z2", "legs"]);
    expect(effectiveRotation([])).toEqual([]);
  });

  it("moveItem swaps within bounds and is a no-op at the edges", () => {
    expect(moveItem(["a", "b", "c"], 0, 1)).toEqual(["b", "a", "c"]);
    expect(moveItem(["a", "b", "c"], 0, -1)).toEqual(["a", "b", "c"]);
    expect(moveItem(["a", "b", "c"], 2, 1)).toEqual(["a", "b", "c"]);
  });
});

describe("slotStructureLabel", () => {
  it("is empty for a plain slot and compact otherwise", () => {
    expect(slotStructureLabel(base)).toBe("");
    expect(slotStructureLabel({ ...base, role: "complementary", max_minutes: 45 })).toBe("compl. ≤45′");
    expect(slotStructureLabel({ ...base, role: "primary" })).toBe("primary");
  });
});
