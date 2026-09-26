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
 * Next-week prefetch: when this query loads successfully, prefetch the FOLLOWING
 * week silently in the background so navigation forward is instant.
 *
 * A286 E6 — prima si prefetchavano entrambe le adiacenti. La precedente è quasi
 * sempre sprecata: da /today si guarda avanti (cosa mi tocca), non indietro, e
 * ogni settimana è una `/api/week/{n}` che risolve tutte le sessioni server-side.
 * Chi torna davvero indietro paga un caricamento, una volta.
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

  // Prefetch the next week once we have data for the current one.
  // displayWeekNum (returned by the API) is used as the source of truth: when
  // weekNum=0 the real week number is resolved server-side.
  const displayWeekNum = query.data?.week_num;
  useEffect(() => {
    if (!enabled || displayWeekNum == null) return;
    qc.prefetchQuery({
      queryKey: queryKeys.week(displayWeekNum + 1),
      queryFn: () => getWeek(displayWeekNum + 1),
      staleTime: 60_000,
    });
  }, [qc, enabled, displayWeekNum]);

  return query;
}
