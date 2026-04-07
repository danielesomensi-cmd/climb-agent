"use client";

import { useQuery } from "@tanstack/react-query";
import { getWeek } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

/**
 * A187 — Cached read of /api/week/{n}.
 *
 * staleTime 60s — week plan changes via mutations (replanner, feedback)
 * which use setQueryData / invalidateQueries to push updates immediately.
 * Background revalidation after 60s catches any server-side cascade.
 */
export function useWeekPlan(weekNum = 0, enabled = true) {
  return useQuery({
    queryKey: queryKeys.week(weekNum),
    queryFn: () => getWeek(weekNum),
    staleTime: 60_000,
    enabled,
  });
}
