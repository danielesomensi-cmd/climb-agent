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
    const small = new Date();
    small.setDate(small.getDate() + 8 * 7);
    expect(weeksToDeadlineIso(8)).toBe(small.toISOString().split("T")[0]);

    const large = new Date();
    large.setDate(large.getDate() + 24 * 7);
    expect(weeksToDeadlineIso(24)).toBe(large.toISOString().split("T")[0]);
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
    // 4 weeks out — below default min=8 → fallback to default.
    const tooSoon = new Date();
    tooSoon.setDate(tooSoon.getDate() + 4 * 7);
    expect(
      deadlineIsoToWeeks(tooSoon.toISOString().split("T")[0], 12),
    ).toBe(12);

    // 30 weeks out — above default max=24 → fallback.
    const tooFar = new Date();
    tooFar.setDate(tooFar.getDate() + 30 * 7);
    expect(
      deadlineIsoToWeeks(tooFar.toISOString().split("T")[0], 12),
    ).toBe(12);
  });

  it("round-trips a deadline back to its weeks value when in range", () => {
    for (const w of [9, 10, 12, 16, 20, 24]) {
      const iso = weeksToDeadlineIso(w);
      expect(deadlineIsoToWeeks(iso, 12, 8, 24)).toBe(w);
    }
  });

  it("respects custom min override (dialog sets min=9)", () => {
    // 8 weeks should fall back to default when min=9.
    const eightWeeks = weeksToDeadlineIso(8);
    expect(deadlineIsoToWeeks(eightWeeks, 12, 9, 24)).toBe(12);
    // 9 weeks should round-trip when min=9.
    const nineWeeks = weeksToDeadlineIso(9);
    expect(deadlineIsoToWeeks(nineWeeks, 12, 9, 24)).toBe(9);
  });
});
