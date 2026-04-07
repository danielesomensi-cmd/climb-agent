import { QueryClient } from "@tanstack/react-query";

/**
 * A187 — React Query client factory.
 *
 * Defaults chosen for climb-agent:
 * - staleTime 30s: most reads (state/week) tolerate brief staleness while
 *   the background revalidation completes.
 * - gcTime 5min: cached data survives navigation across pages without
 *   refetching, but is reclaimed if unused.
 * - retry 1: matches existing B155 behaviour (one Clerk-token retry).
 * - refetchOnWindowFocus false: prevents wasteful refetches on alt-tab.
 *
 * Per-query overrides (e.g. catalog → Infinity, quotes → 24h) are set in
 * the individual query hooks under hooks/queries/.
 */
export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  });
}
