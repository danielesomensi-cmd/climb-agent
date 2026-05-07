/**
 * B-NEWMACRO-STARTDATE-FIX — pin the mid-cycle warning copy.
 *
 * The dialog confirm step shows a yellow "Heads up" warning whenever the
 * current macrocycle still has planned sessions ahead of today. Copy must
 * include:
 *   - the exact remaining-weeks count (Math.ceil((end - today) / 7))
 *   - "remain in your history" reassurance about completed sessions
 */

import { describe, it, expect } from "vitest";
import { buildMidCycleWarning } from "../start-new-macrocycle-dialog";

const TODAY = "2026-05-06"; // Wednesday

describe("buildMidCycleWarning", () => {
  it("returns null when there is no current cycle end_date", () => {
    expect(buildMidCycleWarning(undefined, TODAY)).toBeNull();
    expect(buildMidCycleWarning(null, TODAY)).toBeNull();
  });

  it("returns null when end_date is today or in the past", () => {
    expect(buildMidCycleWarning(TODAY, TODAY)).toBeNull();
    expect(buildMidCycleWarning("2026-05-05", TODAY)).toBeNull();
    expect(buildMidCycleWarning("2026-04-01", TODAY)).toBeNull();
  });

  it("returns 5 weeks for an end_date 5 weeks (35 days) in the future", () => {
    // 2026-05-06 + 35 days = 2026-06-10.
    const w = buildMidCycleWarning("2026-06-10", TODAY);
    expect(w).not.toBeNull();
    expect(w!.weeksRemaining).toBe(5);
    expect(w!.text).toContain("5 weeks");
    expect(w!.text).toContain("remain in your history");
  });

  it("uses singular 'week' for exactly 1 remaining week", () => {
    // 7 days ahead = 1 week.
    const w = buildMidCycleWarning("2026-05-13", TODAY);
    expect(w).not.toBeNull();
    expect(w!.weeksRemaining).toBe(1);
    expect(w!.text).toContain("about 1 week");
    // No "1 weeks" anywhere (plural mistake).
    expect(w!.text).not.toContain("1 weeks");
  });

  it("rounds up partial weeks (3 days remaining = 1 week)", () => {
    // 3 days ahead.
    const w = buildMidCycleWarning("2026-05-09", TODAY);
    expect(w).not.toBeNull();
    expect(w!.weeksRemaining).toBe(1);
  });

  it("handles a far-future end_date (~ 30 weeks)", () => {
    // 2026-05-06 + 210 days = 2026-12-02 → 30 weeks.
    const w = buildMidCycleWarning("2026-12-02", TODAY);
    expect(w).not.toBeNull();
    expect(w!.weeksRemaining).toBe(30);
    expect(w!.text).toMatch(/about 30 weeks/);
  });
});
