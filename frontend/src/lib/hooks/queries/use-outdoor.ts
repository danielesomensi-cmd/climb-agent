"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getOutdoorSpots,
  getOutdoorSessions,
  getOutdoorStats,
  getOutdoorLogByDate,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export function useOutdoorSpots(enabled = true) {
  return useQuery({
    queryKey: queryKeys.outdoorSpots,
    queryFn: getOutdoorSpots,
    staleTime: 5 * 60_000, // rarely changes
    enabled,
  });
}

export function useOutdoorSessions(since?: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.outdoorSessions(since),
    queryFn: () => getOutdoorSessions(since),
    staleTime: 60_000,
    enabled,
  });
}

export function useOutdoorStats(since?: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.outdoorStats(since),
    queryFn: () => getOutdoorStats(since),
    staleTime: 2 * 60_000,
    enabled,
  });
}

export function useOutdoorLog(date: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.outdoorLog(date),
    queryFn: () => getOutdoorLogByDate(date),
    staleTime: 60_000,
    enabled: enabled && !!date,
    retry: false, // 404 is a normal "no log for this date" case
  });
}
