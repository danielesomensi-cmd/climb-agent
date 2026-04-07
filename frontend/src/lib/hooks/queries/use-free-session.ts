"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getFreeSessionSurfaces,
  getFreeSessionPresets,
  getFreeSessionHistory,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export function useFreeSessionSurfaces(enabled = true) {
  return useQuery({
    queryKey: queryKeys.freeSessionSurfaces,
    queryFn: getFreeSessionSurfaces,
    staleTime: 5 * 60_000,
    enabled,
  });
}

export function useFreeSessionPresets(surface: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.freeSessionPresets(surface),
    queryFn: () => getFreeSessionPresets(surface),
    staleTime: 5 * 60_000,
    enabled: enabled && !!surface,
  });
}

export function useFreeSessionHistory(date: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.freeSessionHistory(date),
    queryFn: () => getFreeSessionHistory(date),
    staleTime: 60_000,
    enabled: enabled && !!date,
  });
}
