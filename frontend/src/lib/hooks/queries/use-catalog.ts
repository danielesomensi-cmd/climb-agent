"use client";

import { useQuery } from "@tanstack/react-query";
import { getSessions, getExercises } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

/**
 * A187 — Catalog reads.
 *
 * staleTime: Infinity — catalog is immutable at runtime. Once loaded,
 * it stays in cache for the entire session.
 */
export function useCatalogSessions(enabled = true) {
  return useQuery({
    queryKey: queryKeys.catalogSessions,
    queryFn: getSessions,
    staleTime: Infinity,
    enabled,
  });
}

export function useCatalogExercises(enabled = true) {
  return useQuery({
    queryKey: queryKeys.catalogExercises,
    queryFn: getExercises,
    staleTime: Infinity,
    enabled,
  });
}
