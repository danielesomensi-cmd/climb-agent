"use client";

import { useQuery } from "@tanstack/react-query";
import { getState, getStateStatus } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { PERSIST_MAX_AGE_MS } from "@/lib/query-persist";

/**
 * A187 — Cached read of /api/state.
 *
 * Replaces the legacy useUserState() hook in src/lib/hooks/use-state.ts.
 * Shared across today, week, plan, settings, guided, start-week — all
 * pages now read from the same cache instead of refetching on every mount.
 */
export function useUserState(enabled = true) {
  return useQuery({
    queryKey: queryKeys.state,
    queryFn: getState,
    enabled,
    // A245 B-2: must be >= PERSIST_MAX_AGE_MS, otherwise React Query evicts
    // this query 5 min after the last observer and the next persist writes the
    // offline cache back out empty.
    gcTime: PERSIST_MAX_AGE_MS,
  });
}

export function useStateStatus(enabled = true) {
  return useQuery({
    queryKey: queryKeys.stateStatus,
    queryFn: getStateStatus,
    enabled,
  });
}
