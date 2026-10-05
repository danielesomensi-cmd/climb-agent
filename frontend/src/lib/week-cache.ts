"use client";

import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import { pruneGuardWarnings } from "@/lib/week-alerts";
import type { GuardWarning, KeyStatus, WeekPlan } from "@/lib/types";

export type WeekCacheEntry = {
  week_num?: number;
  phase_id?: string | null;
  week_plan: WeekPlan;
  past_week_unavailable?: boolean;
  /** A294 — sibling of week_plan; refreshed by every replanner response that carries it. */
  key_status?: KeyStatus | null;
  /** A301 — guard alerts of the week; sibling of week_plan, never persisted. */
  guard_warnings?: GuardWarning[];
};

/**
 * What a mutation response carries next to `week_plan`. `undefined` on a field
 * means "the response did not say": the cached value is kept (the guard alerts
 * are then pruned to the sessions that still exist in the new plan).
 */
export type WeekSiblings = {
  key_status?: KeyStatus | null;
  guard_warnings?: GuardWarning[];
};

/** A294 — the key status a mutation response carries, if any (undefined = keep the cached one). */
export function keyStatusOf(result: unknown): KeyStatus | null | undefined {
  if (!result || typeof result !== "object" || !("key_status" in result)) return undefined;
  return (result as { key_status?: KeyStatus | null }).key_status;
}

/** A294 + A301 — the siblings a mutation response carries (absent fields stay undefined). */
export function siblingsOf(result: unknown): WeekSiblings {
  const out: WeekSiblings = {};
  const ks = keyStatusOf(result);
  if (ks !== undefined) out.key_status = ks;
  if (result && typeof result === "object" && Array.isArray((result as { guard_warnings?: unknown }).guard_warnings)) {
    out.guard_warnings = (result as { guard_warnings: GuardWarning[] }).guard_warnings;
  }
  return out;
}

/**
 * A245 G-2 (F34) — the current week lives under TWO cache keys.
 *
 * `useWeekPlan(0)` is the "current week" sentinel used by /today, but the
 * server answers with the real `week_num` (say 7), and `useWeekPlan` prefetches
 * neighbours by that number. So `week(0)` and `week(7)` are two independent
 * entries describing the same seven days. A mark-done written through /today
 * updated `week(0)` only: open /week, navigate to week 7 explicitly, and the
 * session looked un-done for up to the 60s staleTime.
 *
 * Writing through this helper keeps the alias in step. It is a mirror, not a
 * key change: `week(0)` stays the sentinel every caller already uses.
 */
export function writeWeekCache(
  qc: QueryClient,
  weekNum: number,
  weekPlan: WeekPlan,
  siblings: WeekSiblings = {},
): void {
  // A294: `key_status === undefined` (a response without it) keeps the cached
  // status; a value (null included) replaces it.
  const ks = siblings.key_status === undefined ? {} : { key_status: siblings.key_status };
  const apply = (key: readonly unknown[], fallbackNum: number) =>
    qc.setQueryData(key, (old: WeekCacheEntry | undefined) => {
      // A301: fresh alerts replace the cached ones; without them, the cached
      // alerts survive only for the sessions still in the plan (a removed or
      // completed session must not keep its badge).
      const gw = siblings.guard_warnings !== undefined
        ? { guard_warnings: siblings.guard_warnings }
        : old?.guard_warnings
          ? { guard_warnings: pruneGuardWarnings(old.guard_warnings, weekPlan) }
          : {};
      return old
        ? { ...old, week_plan: weekPlan, ...ks, ...gw }
        : { week_num: fallbackNum, week_plan: weekPlan, ...ks, ...gw };
    });

  apply(queryKeys.week(weekNum), weekNum);

  // Mirror between the sentinel and the server's real number, in whichever
  // direction we were called. Only when the other entry already exists: we must
  // not invent a cache entry for a week nobody has loaded.
  const entry = qc.getQueryData<WeekCacheEntry>(queryKeys.week(weekNum));
  const serverNum = entry?.week_num;

  if (weekNum === 0) {
    if (typeof serverNum === "number" && serverNum > 0 && aliasExists(qc, serverNum)) {
      apply(queryKeys.week(serverNum), serverNum);
    }
    return;
  }
  // Called with a real week number: mirror onto the sentinel only if the
  // sentinel currently describes this same week.
  const sentinel = qc.getQueryData<WeekCacheEntry>(queryKeys.week(0));
  if (sentinel && sentinel.week_num === weekNum) {
    apply(queryKeys.week(0), 0);
  }
}

function aliasExists(qc: QueryClient, weekNum: number): boolean {
  return qc.getQueryData(queryKeys.week(weekNum)) !== undefined;
}
