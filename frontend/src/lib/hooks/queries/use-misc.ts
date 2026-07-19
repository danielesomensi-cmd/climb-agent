"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getDailyQuote,
  getDailyTip,
  getOnboardingDefaults,
  getSubscriptionStatus,
  getWeeklyReport,
  getSuggestedSessions,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export function useDailyQuote(context: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.quotesDaily(context),
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

export function useSubscriptionStatus(enabled = true) {
  return useQuery({
    queryKey: queryKeys.subscriptionStatus,
    queryFn: getSubscriptionStatus,
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000, // matches legacy useSubscription poll
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
