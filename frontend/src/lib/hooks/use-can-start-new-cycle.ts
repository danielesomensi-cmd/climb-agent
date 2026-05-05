"use client";

/**
 * A-NEW-MACRO — derives "can the user plan their next cycle?" signals from
 * the live state. Used by Settings (always-on Card) and by the Today banner
 * (only when currently in last week or past end_date).
 *
 * Returns:
 * - currentMacrocycle: the live macrocycle (or null if none).
 * - isLastWeek: today falls within the last 7 days of the cycle window.
 * - isPastEndDate: today is strictly past the cycle's end_date.
 * - canShow: a soft "show a CTA" boolean — true when there is a current
 *   macrocycle AND we're in last-week or past-end. Settings ignores this and
 *   surfaces the CTA unconditionally; Today honors it for visibility gating.
 */

import { useMemo } from "react";
import type { UserState } from "@/lib/types";

interface MacrocycleSummary {
  start_date?: string;
  end_date?: string;
  total_weeks?: number;
}

interface UseCanStartNewCycleResult {
  currentMacrocycle: MacrocycleSummary | null;
  isLastWeek: boolean;
  isPastEndDate: boolean;
  canShow: boolean;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysBetween(a: string, b: string): number {
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return Math.floor(ms / (1000 * 60 * 60 * 24));
}

export function useCanStartNewCycle(state: UserState | null): UseCanStartNewCycleResult {
  return useMemo(() => {
    const mc = (state as { macrocycle?: MacrocycleSummary } | null)?.macrocycle ?? null;
    if (!mc?.end_date) {
      return {
        currentMacrocycle: mc,
        isLastWeek: false,
        isPastEndDate: false,
        canShow: false,
      };
    }
    const today = todayIso();
    const isPastEndDate = today > mc.end_date;
    // "Last week" = today is within 7 days of (or past) end_date.
    const daysToEnd = daysBetween(today, mc.end_date);
    const isLastWeek = daysToEnd >= 0 && daysToEnd <= 6;
    return {
      currentMacrocycle: mc,
      isLastWeek,
      isPastEndDate,
      canShow: isLastWeek || isPastEndDate,
    };
  }, [state]);
}
