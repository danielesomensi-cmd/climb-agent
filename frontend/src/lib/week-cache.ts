"use client";

import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import type { WeekPlan } from "@/lib/types";

export type WeekCacheEntry = {
  week_num?: number;
  phase_id?: string | null;
  week_plan: WeekPlan;
  past_week_unavailable?: boolean;
};

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
): void {
  const apply = (key: readonly unknown[], fallbackNum: number) =>
    qc.setQueryData(key, (old: WeekCacheEntry | undefined) =>
      old ? { ...old, week_plan: weekPlan } : { week_num: fallbackNum, week_plan: weekPlan },
    );

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
