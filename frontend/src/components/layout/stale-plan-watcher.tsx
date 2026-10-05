"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { queryKeys } from "@/lib/query-keys";
import { STALE_PLAN_MESSAGE, onStalePlan } from "@/lib/plan-revision";

/**
 * B371 — one listener for every stale-plan 409, wherever it comes from (today,
 * week, session card, coach, guided player). The week caches are refetched so
 * the page shows the plan the other device wrote, and one toast says so (a
 * fixed id: two conflicts in a row do not stack two toasts).
 */
export function StalePlanWatcher() {
  const qc = useQueryClient();
  useEffect(
    () =>
      onStalePlan(({ retried }) => {
        void qc.invalidateQueries({ queryKey: queryKeys.weekAll });
        toast(STALE_PLAN_MESSAGE, {
          id: "plan-stale",
          description: retried
            ? "Your change was applied to the latest version."
            : "Nothing was saved — check the plan and redo your change.",
          duration: 8000,
        });
      }),
    [qc],
  );
  return null;
}
