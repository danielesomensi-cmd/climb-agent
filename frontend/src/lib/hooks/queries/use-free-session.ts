"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import {
  getFreeSessionSurfaces,
  getFreeSessionPresets,
  getFreeSessionHistory,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export function useFreeSessionSurfaces(enabled = true) {
  return useQuery({
    queryKey: queryKeys.freeSessionSurfaces,
    queryFn: getFreeSessionSurfaces,
    staleTime: 5 * 60_000,
    enabled,
  });
}

export function useFreeSessionPresets(surface: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.freeSessionPresets(surface),
    queryFn: () => getFreeSessionPresets(surface),
    staleTime: 5 * 60_000,
    enabled: enabled && !!surface,
  });
}

export function useFreeSessionHistory(date: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.freeSessionHistory(date),
    queryFn: () => getFreeSessionHistory(date),
    staleTime: 60_000,
    enabled: enabled && !!date,
  });
}

/**
 * A245 F-5 (F15) — free-session history for a whole week, through the cache.
 *
 * `/today` and `/week` each ran a hand-rolled `Promise.all` over the 7 days
 * inside a `useEffect` keyed on `[weekPlan]`. With `structuralSharing: false`
 * every `setQueryData` hands back a fresh reference, so the effect refired on
 * EVERY user action — 7 requests each time, no dedup, no cache, and they all
 * ran again on every today→week→today navigation.
 *
 * `useQueries` reuses the same per-date keys as `useFreeSessionHistory`, so a
 * day already fetched by either page is served from cache.
 */
export function useFreeSessionsForDates(dates: string[], enabled = true) {
  const results = useQueries({
    queries: dates.map((date) => ({
      queryKey: queryKeys.freeSessionHistory(date),
      queryFn: () => getFreeSessionHistory(date),
      staleTime: 60_000,
      enabled: enabled && !!date,
    })),
  });

  return {
    sessions: results.flatMap((r) => r.data?.sessions ?? []),
    /** True once every day has resolved (success or failure) — no spinner limbo. */
    isSettled: results.every((r) => !r.isPending),
  };
}
