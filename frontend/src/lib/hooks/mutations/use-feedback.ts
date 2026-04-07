"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { postFeedback } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { WeekPlan } from "@/lib/types";

/**
 * A194 — Atomic feedback mutation.
 *
 * The backend now returns the updated `week_plan` inline (mark_done applied
 * atomically). On success we write it directly into the `['week', 0]` cache
 * with setQueryData, merging into whatever shape is already there so that
 * `week_num` and `phase_id` are preserved. This removes the round-trip that
 * `refetchQueries(weekAll)` previously cost.
 *
 * State cache is still invalidated because progression_v1 may have updated
 * working_loads.
 *
 * Scope: only the current week (`['week', 0]`) is updated. Past/future weeks
 * continue to refetch on next view — consistent with A194 R6.
 *
 * NOTE: the legacy localStorage retry logic in today/page.tsx (B127/B128)
 * stays outside React Query — it's recovery of pending writes, not a
 * fetch-on-demand. The caller wraps this hook in the same useEffect.
 */
export function useFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: postFeedback,
    onSuccess: (data) => {
      if (data.week_plan) {
        qc.setQueryData<{
          week_num: number;
          phase_id: string;
          week_plan: WeekPlan;
        }>(queryKeys.week(0), (old) =>
          old ? { ...old, week_plan: data.week_plan as WeekPlan } : old,
        );
      } else {
        // Fallback when backend could not produce an updated plan
        qc.invalidateQueries({ queryKey: queryKeys.weekAll });
      }
      qc.invalidateQueries({ queryKey: queryKeys.state });
    },
  });
}
