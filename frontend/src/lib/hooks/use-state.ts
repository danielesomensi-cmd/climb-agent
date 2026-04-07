"use client";

import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getState } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { UserState } from "@/lib/types";

/**
 * A187 — Thin compatibility wrapper around React Query.
 *
 * Legacy pages (plan, settings, outdoor, free-session) import this hook and
 * expect the `{ state, loading, error, refresh }` shape. Instead of migrating
 * every call site, we delegate to React Query here so all four pages
 * automatically benefit from the shared `['state']` cache: navigation between
 * today/week/plan/settings/outdoor no longer re-fetches state.
 *
 * refresh() calls invalidateQueries so subscribers refetch in background while
 * still showing stale-then-fresh UI.
 */
export function useUserState(enabled = true) {
  const qc = useQueryClient();
  const query = useQuery<UserState>({
    queryKey: queryKeys.state,
    queryFn: getState,
    enabled,
  });

  const refresh = useCallback(async () => {
    await qc.invalidateQueries({ queryKey: queryKeys.state });
  }, [qc]);

  return {
    state: query.data ?? null,
    loading: query.isLoading,
    error: query.error ? (query.error instanceof Error ? query.error.message : "Failed to load state") : null,
    refresh,
  };
}
