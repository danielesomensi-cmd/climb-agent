/**
 * B-NEWMACRO-DEADLINE-FIX — pin the contract between the weeks-selector value
 * and the POST body's `deadline` ISO string.
 *
 * The dialog computes the deadline at submit time as
 *   today + (deadlineWeeks * 7) days.
 * If a refactor ever drops or rebases that conversion, this test fails.
 */

import { describe, it, expect } from "vitest";
import { weeksToDeadlineIso } from "@/components/shared/deadline-weeks-selector";

function isoDaysFromNow(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().split("T")[0];
}

describe("submission body deadline derivation", () => {
  it("12 weeks = today + 84 days", () => {
    expect(weeksToDeadlineIso(12)).toBe(isoDaysFromNow(84));
  });

  it("9 weeks (engine min) = today + 63 days", () => {
    expect(weeksToDeadlineIso(9)).toBe(isoDaysFromNow(63));
  });

  it("16 weeks = today + 112 days", () => {
    expect(weeksToDeadlineIso(16)).toBe(isoDaysFromNow(112));
  });

  it("output is a valid YYYY-MM-DD ISO date string", () => {
    const out = weeksToDeadlineIso(12);
    expect(out).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    // Round-trip through Date — must parse cleanly.
    expect(Number.isNaN(new Date(out).getTime())).toBe(false);
  });
});
