import { describe, it, expect, beforeEach } from "vitest";
import { QueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/query-keys";
import { siblingsOf, writeWeekCache, type WeekCacheEntry } from "@/lib/week-cache";
import type { GuardWarning, WeekPlan } from "@/lib/types";

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

/**
 * A301 — `guard_warnings` is a sibling of week_plan like `key_status`: fresh
 * alerts replace the cached ones; a response without them keeps the cached
 * alerts, pruned to the sessions that still exist (no stale badge on a
 * removed or completed session).
 */
describe("writeWeekCache — guard_warnings (A301)", () => {
  const gw = (date: string, sessionId = "s1"): GuardWarning => ({
    code: "finger_gap", severity: "warning", date, slot: "evening", session_id: sessionId,
    user_owned: true, with: [], message: "m",
  });
  const planWith = (sessions: Array<{ date: string; status?: string }>): WeekPlan =>
    ({ weeks: [{ days: sessions.map((s) => ({ date: s.date, sessions: [{ session_id: "s1", slot: "evening", location: "gym", status: s.status ?? "planned" }] })) }] }) as unknown as WeekPlan;

  it("replaces the cached alerts when the response carries them", () => {
    qc.setQueryData(queryKeys.week(3), { week_num: 3, week_plan: plan("old"), guard_warnings: [gw("2026-10-06")] });
    writeWeekCache(qc, 3, plan("NEW"), { guard_warnings: [] });
    expect(qc.getQueryData<WeekCacheEntry>(queryKeys.week(3))?.guard_warnings).toEqual([]);
  });

  it("keeps + prunes them when the response has none", () => {
    qc.setQueryData(queryKeys.week(3), {
      week_num: 3, week_plan: plan("old"),
      guard_warnings: [gw("2026-10-06"), gw("2026-10-07"), gw("2026-10-08")],
    });
    writeWeekCache(qc, 3, planWith([{ date: "2026-10-06" }, { date: "2026-10-07", status: "done" }]));
    const e = qc.getQueryData<WeekCacheEntry>(queryKeys.week(3));
    expect(e?.guard_warnings?.map((w) => w.date)).toEqual(["2026-10-06"]);
  });

  it("siblingsOf reads key_status and guard_warnings, leaves absent ones undefined", () => {
    expect(siblingsOf({ week_plan: {} })).toEqual({});
    expect(siblingsOf({ key_status: null })).toEqual({ key_status: null });
    expect(siblingsOf({ guard_warnings: [gw("2026-10-06")] }).guard_warnings).toHaveLength(1);
    expect(siblingsOf({ guard_warnings: "nope" })).toEqual({});
  });

  it("keeps the cached key_status when only guard_warnings arrive", () => {
    qc.setQueryData(queryKeys.week(3), { week_num: 3, week_plan: plan("old"), key_status: { version: "x" } });
    writeWeekCache(qc, 3, plan("NEW"), { guard_warnings: [] });
    expect(qc.getQueryData<WeekCacheEntry>(queryKeys.week(3))?.key_status).toEqual({ version: "x" });
  });
});
