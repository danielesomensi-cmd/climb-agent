"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { postFeedback } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { writeWeekCache } from "@/lib/week-cache";
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
        // B371: also the week(N) alias — the feedback moved the plan's
        // revision, and a stale alias would make the next write from /week a
        // 409. Only when the sentinel is loaded (nothing is invented).
        if (qc.getQueryData(queryKeys.week(0))) {
          writeWeekCache(qc, 0, data.week_plan as WeekPlan);
        }
      } else {
        // Fallback when backend could not produce an updated plan
        qc.invalidateQueries({ queryKey: queryKeys.weekAll });
      }
      qc.invalidateQueries({ queryKey: queryKeys.state });
    },
  });
}
