"use client";

import { useQuery } from "@tanstack/react-query";
import { getState, getStateStatus } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

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
  });
}

export function useStateStatus(enabled = true) {
  return useQuery({
    queryKey: queryKeys.stateStatus,
    queryFn: getStateStatus,
    enabled,
  });
}
