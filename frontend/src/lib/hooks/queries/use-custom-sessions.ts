"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  getCustomSessions,
  getCustomSession,
  getBuilderExercises,
  getBuilderBlocks,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";

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

/**
 * Search/filter exercises for the builder picker.
 *
 * A286 E5 — il picker chiamava l'API a ogni carattere e la lista collassava su
 * "Loading..." nel mezzo della digitazione. Due correzioni:
 * - `useDebouncedValue` sul testo: una richiesta quando ci si ferma, non una per tasto;
 * - `placeholderData: keepPreviousData`: mentre arriva la nuova lista resta a
 *   schermo la precedente (`isLoading` è vero solo al primissimo caricamento,
 *   `isPlaceholderData`/`isFetching` dicono se è in aggiornamento).
 */
export function useBuilderExercises(q: string, domain: string) {
  const debouncedQ = useDebouncedValue(q, 250);
  return useQuery({
    queryKey: queryKeys.builderExercises(debouncedQ, domain),
    queryFn: () =>
      getBuilderExercises({ q: debouncedQ || undefined, domain: domain || undefined }),
    staleTime: 60_000, // exercises don't change often
    placeholderData: keepPreviousData,
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
