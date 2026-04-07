"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { postFeedback } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

/**
 * A187 — Feedback mutation.
 *
 * Server-side cascade: feedback triggers progression_v1 → load adjusted
 * for future sessions. The endpoint does NOT return week_plan, so we
 * invalidate the entire week prefix to refetch any visible week.
 *
 * NOTE: the legacy localStorage retry logic in today/page.tsx (B127/B128)
 * stays outside React Query — it's recovery of pending writes, not a
 * fetch-on-demand. The caller wraps this hook in the same useEffect.
 */
export function useFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: postFeedback,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.weekAll });
    },
  });
}
