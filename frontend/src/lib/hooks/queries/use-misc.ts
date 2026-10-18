"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getDailyQuote,
  getDailyTip,
  getMilestones,
  getMonthlyHeatmap,
  getOnboardingDefaults,
  getWeeklyReport,
  getSuggestedSessions,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { toISODateLocal } from "@/lib/dates";

export function useDailyQuote(context: string, enabled = true) {
  // B396 review — the day is in the key: a persisted quote from yesterday
  // (still inside its 24 h staleTime) is never shown as today's. Read at each
  // render, so a PWA resumed after midnight switches on its next render.
  const localDate = toISODateLocal(new Date());
  return useQuery({
    queryKey: queryKeys.quotesDaily(context, localDate),
    queryFn: () => getDailyQuote(context),
    staleTime: 24 * 60 * 60_000, // 24h — quote is per-phase, daily refresh enough
    gcTime: 24 * 60 * 60_000,
    enabled: enabled && !!context,
  });
}

export function useDailyTip(date: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.tipsDaily(date),
    queryFn: () => getDailyTip(date),
    staleTime: 60 * 60_000, // tip is per-day; hourly refresh is plenty
    enabled: enabled && !!date,
  });
}

export function useOnboardingDefaults(enabled = true) {
  return useQuery({
    queryKey: queryKeys.onboardingDefaults,
    queryFn: getOnboardingDefaults,
    staleTime: Infinity, // static
    enabled,
  });
}

export function useWeeklyReport(weekStart: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.reportsWeekly(weekStart),
    queryFn: () => getWeeklyReport(weekStart),
    staleTime: 60_000,
    enabled: enabled && !!weekStart,
  });
}

export function useMonthlyHeatmap(month: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.reportsHeatmap(month),
    queryFn: () => getMonthlyHeatmap(month),
    staleTime: 60_000,
    enabled: enabled && !!month,
  });
}

export function useMilestones(enabled = true) {
  return useQuery({
    queryKey: queryKeys.milestones,
    queryFn: getMilestones,
    staleTime: 5 * 60_000,
    enabled,
  });
}

export function useReplannerSuggestions(
  targetDate: string,
  location: string,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.replannerSuggest(targetDate, location),
    queryFn: () => getSuggestedSessions(targetDate, location),
    staleTime: 60_000,
    enabled: enabled && !!targetDate && !!location,
  });
}
