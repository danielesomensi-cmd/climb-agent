import { describe, it, expect } from "vitest";
import { describeQuickAddAdjustments, type QuickAddAdjustment } from "@/lib/api";

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
