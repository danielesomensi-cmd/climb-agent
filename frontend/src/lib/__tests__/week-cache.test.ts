import { describe, it, expect, beforeEach } from "vitest";
import { QueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/query-keys";
import { writeWeekCache, type WeekCacheEntry } from "@/lib/week-cache";
import type { WeekPlan } from "@/lib/types";

/**
 * A245 G-2 (F34) — the current week lives under two cache keys.
 *
 * `useWeekPlan(0)` is the "current week" sentinel used by /today, but the
 * server answers with the real `week_num`, and adjacent weeks are prefetched by
 * that number. So `week(0)` and `week(7)` are independent entries describing
 * the same seven days: a mark-done through /today updated only the first, and
 * /week showed the session un-done until the 60s staleTime expired.
 */
const plan = (marker: string): WeekPlan =>
  ({ weeks: [{ days: [{ date: marker, sessions: [] }] }] }) as unknown as WeekPlan;

const dateIn = (qc: QueryClient, weekNum: number): string | undefined => {
  const e = qc.getQueryData<WeekCacheEntry>(queryKeys.week(weekNum));
  return e?.week_plan?.weeks?.[0]?.days?.[0]?.date;
};

let qc: QueryClient;
beforeEach(() => {
  qc = new QueryClient();
});

describe("writeWeekCache", () => {
  it("writes the key it was given", () => {
    writeWeekCache(qc, 0, plan("A"));
    expect(dateIn(qc, 0)).toBe("A");
  });

  it("mirrors a sentinel write onto the real week number", () => {
    qc.setQueryData(queryKeys.week(0), { week_num: 7, week_plan: plan("old") });
    qc.setQueryData(queryKeys.week(7), { week_num: 7, week_plan: plan("old") });

    writeWeekCache(qc, 0, plan("NEW"));

    expect(dateIn(qc, 0)).toBe("NEW");
    // The bug: this used to stay "old" for up to 60s.
    expect(dateIn(qc, 7)).toBe("NEW");
  });

  it("mirrors a numbered write back onto the sentinel", () => {
    qc.setQueryData(queryKeys.week(0), { week_num: 7, week_plan: plan("old") });
    qc.setQueryData(queryKeys.week(7), { week_num: 7, week_plan: plan("old") });

    writeWeekCache(qc, 7, plan("NEW"));

    expect(dateIn(qc, 7)).toBe("NEW");
    expect(dateIn(qc, 0)).toBe("NEW");
  });

  it("does NOT touch the sentinel when it describes a different week", () => {
    // /today is on week 7; the user edits week 9 from /week.
    qc.setQueryData(queryKeys.week(0), { week_num: 7, week_plan: plan("week7") });
    qc.setQueryData(queryKeys.week(9), { week_num: 9, week_plan: plan("week9") });

    writeWeekCache(qc, 9, plan("NEW"));

    expect(dateIn(qc, 9)).toBe("NEW");
    expect(dateIn(qc, 0)).toBe("week7");
  });

  it("does not invent a cache entry for a week nobody loaded", () => {
    qc.setQueryData(queryKeys.week(0), { week_num: 7, week_plan: plan("old") });

    writeWeekCache(qc, 0, plan("NEW"));

    expect(dateIn(qc, 0)).toBe("NEW");
    // week(7) was never fetched — creating it here would fabricate a cache hit
    // for a query that has never run.
    expect(qc.getQueryData(queryKeys.week(7))).toBeUndefined();
  });

  it("creates the entry when the key is empty", () => {
    writeWeekCache(qc, 3, plan("A"));
    const e = qc.getQueryData<WeekCacheEntry>(queryKeys.week(3));
    expect(e?.week_num).toBe(3);
    expect(dateIn(qc, 3)).toBe("A");
  });

  it("preserves sibling fields such as phase_id", () => {
    qc.setQueryData(queryKeys.week(0), {
      week_num: 4,
      phase_id: "strength_power",
      week_plan: plan("old"),
    });

    writeWeekCache(qc, 0, plan("NEW"));

    expect(qc.getQueryData<WeekCacheEntry>(queryKeys.week(0))?.phase_id).toBe("strength_power");
  });
});
