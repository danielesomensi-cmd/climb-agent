import { describe, it, expect } from "vitest";
import {
  behindWeekNotice,
  isCachedWeekStale,
  isWeekPlanBehind,
  mondayOf,
  startOfLocalWeek,
  updatedAtLabel,
  weekPlanMonday,
} from "@/lib/week-freshness";
import type { WeekPlan } from "@/lib/types";

/**
 * B396 — Monday's false "No sessions planned this week".
 *
 * week(0) is persisted for up to 7 days, so on Monday the cache holds the week
 * that just ended. /today read it as the current week (no today, no later day)
 * and told every user to review their availability until the GET answered —
 * and with no end offline.
 */

function plan(dates: string[], startDate?: string): WeekPlan {
  return {
    ...(startDate ? { start_date: startDate } : {}),
    weeks: [{ days: dates.map((date) => ({ date, weekday: "", sessions: [] })) }],
  } as WeekPlan;
}

const LAST_WEEK = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"];
const THIS_WEEK = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"];
const NEXT_WEEK = ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"];

describe("mondayOf (local calendar)", () => {
  it.each([
    ["2026-10-19", "2026-10-19"], // Monday
    ["2026-10-21", "2026-10-19"], // Wednesday
    ["2026-10-25", "2026-10-19"], // Sunday belongs to the week that started Monday
    ["2026-11-01", "2026-10-26"], // across a month boundary
    ["2027-01-03", "2026-12-28"], // across a year boundary
  ])("%s → %s", (day, monday) => {
    expect(mondayOf(day)).toBe(monday);
  });
});

describe("weekPlanMonday", () => {
  it("uses start_date when present", () => {
    expect(weekPlanMonday(plan(THIS_WEEK, "2026-10-19"))).toBe("2026-10-19");
  });

  it("falls back to the first day when start_date is missing", () => {
    expect(weekPlanMonday(plan(THIS_WEEK))).toBe("2026-10-19");
  });

  it("is null for no plan or a plan without days", () => {
    expect(weekPlanMonday(null)).toBeNull();
    expect(weekPlanMonday({ weeks: [] } as unknown as WeekPlan)).toBeNull();
  });
});

describe("isWeekPlanBehind — the Monday case", () => {
  it("Monday morning with last week's plan in cache → behind", () => {
    expect(isWeekPlanBehind(plan(LAST_WEEK, "2026-10-12"), "2026-10-19")).toBe(true);
  });

  it("is behind for the whole new week, not only Monday", () => {
    expect(isWeekPlanBehind(plan(LAST_WEEK, "2026-10-12"), "2026-10-23")).toBe(true);
  });

  it("Sunday with the same plan → still the current week", () => {
    expect(isWeekPlanBehind(plan(LAST_WEEK, "2026-10-12"), "2026-10-18")).toBe(false);
  });

  it("the current week is never behind", () => {
    expect(isWeekPlanBehind(plan(THIS_WEEK, "2026-10-19"), "2026-10-19")).toBe(false);
    expect(isWeekPlanBehind(plan(THIS_WEEK), "2026-10-25")).toBe(false);
  });

  it("a FUTURE week is legitimate (macrocycle not started: the pre-start hero)", () => {
    expect(isWeekPlanBehind(plan(NEXT_WEEK, "2026-10-26"), "2026-10-21")).toBe(false);
  });

  it("no plan is not 'behind' (that is B257's past_week_unavailable / onboarding)", () => {
    expect(isWeekPlanBehind(null, "2026-10-19")).toBe(false);
    expect(isWeekPlanBehind(undefined, "2026-10-19")).toBe(false);
  });
});

describe("isCachedWeekStale — a copy from an earlier week, not the server's answer", () => {
  const MONDAY_0830 = new Date(2026, 9, 19, 8, 30);
  const SUNDAY_2100 = new Date(2026, 9, 18, 21, 0).getTime();
  const MONDAY_0829 = new Date(2026, 9, 19, 8, 29).getTime();

  it("startOfLocalWeek is Monday 00:00 local", () => {
    expect(startOfLocalWeek(MONDAY_0830)).toBe(new Date(2026, 9, 19, 0, 0).getTime());
    expect(startOfLocalWeek(new Date(2026, 9, 25, 23, 59))).toBe(new Date(2026, 9, 19, 0, 0).getTime());
  });

  it("Monday, last week's plan fetched on Sunday → stale (skeleton / offline notice)", () => {
    expect(isCachedWeekStale(plan(LAST_WEEK, "2026-10-12"), SUNDAY_2100, MONDAY_0830)).toBe(true);
  });

  it("the same past week fetched THIS week is the server's answer → shown as before", () => {
    // A paused plan holds its week (A223), an ended cycle serves its last
    // (B257), and the server's clock is UTC: none of these is a stale cache.
    expect(isCachedWeekStale(plan(LAST_WEEK, "2026-10-12"), MONDAY_0829, MONDAY_0830)).toBe(false);
  });

  it("the current week is never stale, however old the copy", () => {
    expect(isCachedWeekStale(plan(THIS_WEEK, "2026-10-19"), SUNDAY_2100, MONDAY_0830)).toBe(false);
  });

  it("no plan → nothing to hide", () => {
    expect(isCachedWeekStale(null, 0, MONDAY_0830)).toBe(false);
  });
});

describe("behindWeekNotice — what /today says while the cache is behind", () => {
  const base = { online: true, authReady: true, authWaitExpired: false, isFetching: false };

  it("online and fetching → loading (skeleton, never 'No sessions planned')", () => {
    expect(behindWeekNotice({ ...base, isFetching: true })).toBe("loading");
  });

  it("online with Clerk still coming up → loading", () => {
    expect(behindWeekNotice({ ...base, authReady: false })).toBe("loading");
  });

  it("browser offline → offline notice", () => {
    expect(behindWeekNotice({ ...base, online: false })).toBe("offline");
    expect(behindWeekNotice({ ...base, online: false, isFetching: true })).toBe("offline");
  });

  it("Clerk never came up (dead connection that looks online) → offline notice", () => {
    expect(behindWeekNotice({ ...base, authReady: false, authWaitExpired: true })).toBe("offline");
  });

  it("asked and still holding last week (e.g. the server clock is not on Monday yet) → not_loaded + Retry", () => {
    expect(behindWeekNotice(base)).toBe("not_loaded");
  });
});

describe("updatedAtLabel — the line that replaces the red box over a visible plan", () => {
  const now = new Date(2026, 9, 19, 18, 5); // Mon 19 Oct, 18:05 local

  it("same day → time only", () => {
    expect(updatedAtLabel(new Date(2026, 9, 19, 7, 3).getTime(), now)).toBe("updated 07:03");
  });

  it("another day → weekday and time", () => {
    expect(updatedAtLabel(new Date(2026, 9, 17, 14, 32).getTime(), now)).toBe("updated Sat 14:32");
  });

  it("unknown time → empty", () => {
    expect(updatedAtLabel(0, now)).toBe("");
    expect(updatedAtLabel(Number.NaN, now)).toBe("");
  });
});
