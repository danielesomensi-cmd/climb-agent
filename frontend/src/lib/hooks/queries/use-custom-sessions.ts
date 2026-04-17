"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getCustomSessions,
  getCustomSession,
  getBuilderExercises,
  getBuilderBlocks,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

/** List all custom sessions (summary view). */
export function useCustomSessions(enabled = true) {
  return useQuery({
    queryKey: queryKeys.customSessions,
    queryFn: getCustomSessions,
    enabled,
  });
}

/** Get full custom session detail. */
export function useCustomSession(id: string | null) {
  return useQuery({
    queryKey: queryKeys.customSession(id ?? ""),
    queryFn: () => getCustomSession(id!),
    enabled: !!id,
  });
}

/** Search/filter exercises for the builder picker. */
export function useBuilderExercises(q: string, domain: string) {
  return useQuery({
    queryKey: queryKeys.builderExercises(q, domain),
    queryFn: () => getBuilderExercises({ q: q || undefined, domain: domain || undefined }),
    staleTime: 60_000, // exercises don't change often
  });
}

/** Warmup/cooldown template blocks (static data). */
export function useBuilderBlocks() {
  return useQuery({
    queryKey: queryKeys.builderBlocks,
    queryFn: getBuilderBlocks,
    staleTime: Infinity,
  });
}
