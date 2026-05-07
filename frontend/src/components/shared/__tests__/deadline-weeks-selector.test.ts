/**
 * B-NEWMACRO-DEADLINE-FIX — pin the shared selector helpers.
 *
 * The component itself is a thin wrapper around shadcn `<Slider>`; the
 * conversion helpers (`weeksToDeadlineIso`, `deadlineIsoToWeeks`) are the
 * load-bearing logic — used by both onboarding and the new-macrocycle dialog.
 */

import { describe, it, expect } from "vitest";
import {
  weeksToDeadlineIso,
  deadlineIsoToWeeks,
} from "../deadline-weeks-selector";

describe("weeksToDeadlineIso", () => {
  it("returns today + N*7 days as YYYY-MM-DD", () => {
    const out = weeksToDeadlineIso(12);
    const expected = new Date();
    expected.setDate(expected.getDate() + 12 * 7);
    const expectedIso = expected.toISOString().split("T")[0];
    expect(out).toBe(expectedIso);
  });

  it("handles small and large values", () => {
    // A218: range tightened to [8 boulder / 11 lead, 16].
    const small = new Date();
    small.setDate(small.getDate() + 8 * 7);
    expect(weeksToDeadlineIso(8)).toBe(small.toISOString().split("T")[0]);

    const large = new Date();
    large.setDate(large.getDate() + 16 * 7);
    expect(weeksToDeadlineIso(16)).toBe(large.toISOString().split("T")[0]);
  });
});

describe("deadlineIsoToWeeks", () => {
  it("returns the default when the deadline is missing", () => {
    expect(deadlineIsoToWeeks(undefined, 12)).toBe(12);
    expect(deadlineIsoToWeeks("", 12)).toBe(12);
  });

  it("returns the default when the deadline is malformed", () => {
    expect(deadlineIsoToWeeks("not-a-date", 12)).toBe(12);
  });

  it("returns the default when the computed weeks fall outside [min, max]", () => {
    // A218: default min=11 (lead floor) → 4 weeks out is below it.
    const tooSoon = new Date();
    tooSoon.setDate(tooSoon.getDate() + 4 * 7);
    expect(
      deadlineIsoToWeeks(tooSoon.toISOString().split("T")[0], 12),
    ).toBe(12);

    // A218: default max=16 → 20 weeks out is above it.
    const tooFar = new Date();
    tooFar.setDate(tooFar.getDate() + 20 * 7);
    expect(
      deadlineIsoToWeeks(tooFar.toISOString().split("T")[0], 12),
    ).toBe(12);
  });

  it("round-trips a deadline back to its weeks value when in range", () => {
    // A218: valid range is [8 (boulder min), 16] when both are widened.
    for (const w of [8, 11, 12, 13, 14, 15, 16]) {
      const iso = weeksToDeadlineIso(w);
      expect(deadlineIsoToWeeks(iso, 12, 8, 16)).toBe(w);
    }
  });

  it("respects custom min override (lead dialog sets min=11)", () => {
    // 10 weeks should fall back to default when min=11.
    const tenWeeks = weeksToDeadlineIso(10);
    expect(deadlineIsoToWeeks(tenWeeks, 12, 11, 16)).toBe(12);
    // 11 weeks should round-trip when min=11.
    const elevenWeeks = weeksToDeadlineIso(11);
    expect(deadlineIsoToWeeks(elevenWeeks, 12, 11, 16)).toBe(11);
  });
});
