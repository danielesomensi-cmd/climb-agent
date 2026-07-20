"use client";

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getWeek } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { PERSIST_MAX_AGE_MS } from "@/lib/query-persist";

/**
 * A187 — Cached read of /api/week/{n}.
 *
 * staleTime 60s — week plan changes via mutations (replanner, feedback)
 * which use setQueryData / invalidateQueries to push updates immediately.
 * Background revalidation after 60s catches any server-side cascade.
 *
 * structuralSharing: false — React Query's default deep-equality structural
 * sharing preserves the OLD reference when new data is "structurally similar".
 * For week plans mutated via setQueryData (mark_done, mark_skipped, replan, etc.)
 * this prevents subscriber re-renders even though the cache is updated. Disabling
 * structural sharing ensures every cache write produces a fresh top-level reference
 * that useSyncExternalStore always picks up.
 *
 * Adjacent-week prefetch: when this query loads successfully, prefetch the
 * previous and next week silently in the background so navigation is instant.
 */
export function useWeekPlan(weekNum = 0, enabled = true) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.week(weekNum),
    queryFn: () => getWeek(weekNum),
    staleTime: 60_000,
    enabled,
    structuralSharing: false,
    // A245 B-2: see use-user-state — gcTime must outlive the persisted cache.
    gcTime: PERSIST_MAX_AGE_MS,
  });

  // Prefetch adjacent weeks once we have data for the current one.
  // displayWeekNum (returned by the API) is used as the source of truth: when
  // weekNum=0 the real week number is resolved server-side.
  const displayWeekNum = query.data?.week_num;
  useEffect(() => {
    if (!enabled || displayWeekNum == null) return;
    const prev = displayWeekNum - 1;
    const next = displayWeekNum + 1;
    if (prev >= 1) {
      qc.prefetchQuery({
        queryKey: queryKeys.week(prev),
        queryFn: () => getWeek(prev),
        staleTime: 60_000,
      });
    }
    qc.prefetchQuery({
      queryKey: queryKeys.week(next),
      queryFn: () => getWeek(next),
      staleTime: 60_000,
    });
  }, [qc, enabled, displayWeekNum]);

  return query;
}
