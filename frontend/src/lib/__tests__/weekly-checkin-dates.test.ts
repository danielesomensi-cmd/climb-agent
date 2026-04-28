import { describe, it, expect } from "vitest";
import { getTargetMonday } from "../weekly-checkin-dates";

describe("getTargetMonday", () => {
  it("Sunday → next Monday (tomorrow)", () => {
    // 2026-04-26 is a Sunday
    const sun = new Date(2026, 3, 26);
    expect(sun.getDay()).toBe(0);
    expect(getTargetMonday(sun)).toBe("2026-04-27");
  });

  it("Monday → today (current week)", () => {
    // 2026-04-27 is a Monday — the regression case
    const mon = new Date(2026, 3, 27);
    expect(mon.getDay()).toBe(1);
    expect(getTargetMonday(mon)).toBe("2026-04-27");
  });

  it("Tue–Sat → null (banner hidden)", () => {
    for (let dayOffset = 1; dayOffset <= 5; dayOffset++) {
      const d = new Date(2026, 3, 27 + dayOffset); // Tue 28 … Sat 02 May
      expect(getTargetMonday(d)).toBeNull();
    }
  });

  it("crosses month boundary correctly on Sunday", () => {
    // 2026-05-31 is a Sunday → next Monday = 2026-06-01
    const sun = new Date(2026, 4, 31);
    expect(sun.getDay()).toBe(0);
    expect(getTargetMonday(sun)).toBe("2026-06-01");
  });

  it("crosses year boundary correctly on Sunday", () => {
    // 2026-12-27 is a Sunday → next Monday = 2026-12-28; pick a year-end one
    // 2027-12-26 is a Sunday → next Monday = 2027-12-27
    // 2027-01-31 is a Sunday → next Monday = 2027-02-01
    const sun = new Date(2027, 0, 31);
    expect(sun.getDay()).toBe(0);
    expect(getTargetMonday(sun)).toBe("2027-02-01");
  });
});
