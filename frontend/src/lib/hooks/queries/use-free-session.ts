"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getFreeSessionSurfaces, getFreeSessionPresets } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { useUserState } from "./use-user-state";

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

/** B386 — a free session as it sits in `user_state.free_sessions`. */
export type StateFreeSession = Record<string, unknown> & { date?: string };

/**
 * B386 — the free sessions of the given dates, read out of a user state.
 *
 * Pure (no React) so the selection is tested directly. Order follows `dates`,
 * then the order sessions were stored in — the same order the old per-day
 * `/history` calls produced when flattened.
 */
export function selectFreeSessionsForDates(
  state: object | null | undefined,
  dates: readonly string[],
): StateFreeSession[] {
  const raw = (state as { free_sessions?: unknown } | null | undefined)?.free_sessions;
  const all = Array.isArray(raw) ? (raw as StateFreeSession[]) : [];
  if (all.length === 0 || dates.length === 0) return [];
  const out: StateFreeSession[] = [];
  for (const date of dates) {
    for (const s of all) {
      if (s && typeof s === "object" && s.date === date) out.push(s);
    }
  }
  return out;
}

/**
 * Free sessions for a set of days, derived from the shared `['state']` query.
 *
 * B386 — this used to be one `GET /api/free-session/history?date=` per day
 * (`useQueries`, A245 F-5): seven requests on every cold /today, each a full
 * `load_state` server-side, to read rows that are already inside the
 * `/api/state` payload /today and /week fetch anyway. Now it is zero extra
 * requests — and, since `state` is persisted (A245 B-2), the badges also show
 * offline.
 *
 * It also brings back the `date` field the `/history` view did not carry:
 * /week grouped by `fs.date`, so since A245 F-5 its per-day map was always
 * empty and the free sessions never showed on the week's day cards.
 *
 * Writes (finish / delete) go through `invalidateFreeSessionHistory`, which
 * now invalidates `['state']` too.
 */
export function useFreeSessionsForDates(dates: readonly string[], enabled = true) {
  const query = useUserState(enabled);
  const data = query.data;
  const key = dates.join(",");
  const sessions = useMemo(
    () => selectFreeSessionsForDates(data, key ? key.split(",") : []),
    [data, key],
  );
  return {
    sessions,
    /** True once state has resolved (success or failure) — no spinner limbo. */
    isSettled: !query.isPending,
  };
}
