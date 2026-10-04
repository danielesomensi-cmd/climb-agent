import { describe, it, expect } from "vitest";
import { describeQuickAddAdjustments, quickAddCanForce, quickAddHasFingerRisk, type QuickAddAdjustment } from "@/lib/api";

function adj(reason: string): QuickAddAdjustment {
  return { date: "2026-07-22", slot: "evening", action: "downgraded", reason };
}

describe("describeQuickAddAdjustments (B-QUICKADD-ADJUSTMENTS)", () => {
  it("returns null when nothing was adjusted", () => {
    expect(describeQuickAddAdjustments(undefined)).toBeNull();
    expect(describeQuickAddAdjustments([])).toBeNull();
  });

  it("explains a finger-spacing downshift", () => {
    const note = describeQuickAddAdjustments([adj("finger_spacing_downshift")]);
    expect(note).toContain("finger recovery");
    expect(note).toContain("48h");
  });

  it("explains a hard-cap downshift", () => {
    const note = describeQuickAddAdjustments([adj("hard_cap_downshift")]);
    expect(note).toContain("weekly hard-session limit");
  });

  it("combines both reasons into one line", () => {
    const note = describeQuickAddAdjustments([
      adj("finger_spacing_downshift"),
      adj("hard_cap_downshift"),
    ]);
    expect(note).toContain("finger recovery");
    expect(note).toContain("weekly hard-session limit");
    expect(note).toContain(" and ");
  });

  it("dedupes repeated reasons", () => {
    const note = describeQuickAddAdjustments([
      adj("hard_cap_downshift"),
      adj("hard_cap_downshift"),
    ]);
    // one clause, not two
    expect(note?.match(/weekly hard-session limit/g)).toHaveLength(1);
  });

  it("falls back gracefully for an unknown reason", () => {
    const note = describeQuickAddAdjustments([adj("some_future_reason")]);
    expect(note).toContain("Eased to a lighter session");
    expect(note).toContain("balanced");
  });
});

describe("quickAddHasFingerRisk (A254)", () => {
  it("is false when nothing was adjusted", () => {
    expect(quickAddHasFingerRisk(undefined)).toBe(false);
    expect(quickAddHasFingerRisk([])).toBe(false);
  });

  it("is true when a finger downshift is present (needs explicit confirm)", () => {
    expect(quickAddHasFingerRisk([adj("finger_spacing_downshift")])).toBe(true);
    expect(quickAddHasFingerRisk([adj("hard_cap_downshift"), adj("finger_spacing_downshift")])).toBe(true);
  });

  it("is false for a cap-only downshift (toast action is enough)", () => {
    expect(quickAddHasFingerRisk([adj("hard_cap_downshift")])).toBe(false);
  });
});

describe("quick_add_ripple (B366)", () => {
  it("describes a ripple-only result as an eased next day, not an eased session", () => {
    const note = describeQuickAddAdjustments([adj("quick_add_ripple")]);
    expect(note).toContain("next day was eased");
    expect(note).not.toContain("Eased to a lighter session");
  });

  it("keeps the enforcement sentence and appends the ripple one", () => {
    const note = describeQuickAddAdjustments([adj("hard_cap_downshift"), adj("quick_add_ripple")]);
    expect(note).toContain("weekly hard-session limit");
    expect(note).toContain("next day was eased");
  });

  it("offers the force action only when the added session itself was eased", () => {
    expect(quickAddCanForce(undefined)).toBe(false);
    expect(quickAddCanForce([adj("quick_add_ripple")])).toBe(false);
    expect(quickAddCanForce([adj("quick_add_ripple"), adj("hard_cap_downshift")])).toBe(true);
    expect(quickAddCanForce([adj("finger_spacing_downshift")])).toBe(true);
  });

  it("a ripple is never a finger risk", () => {
    expect(quickAddHasFingerRisk([adj("quick_add_ripple")])).toBe(false);
  });
});
