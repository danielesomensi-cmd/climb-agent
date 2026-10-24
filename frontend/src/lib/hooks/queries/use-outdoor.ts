"use client";

import { queryOptions, useQuery, type QueryClient } from "@tanstack/react-query";
import {
  getOutdoorSpots,
  getOutdoorSessions,
  getOutdoorStats,
  getOutdoorLogByDate,
  getQuaderno,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

/**
 * B398 (O11) — one definition of the spots query, shared by the hook and by the
 * click handlers that need the list once (log / edit an outdoor day). /settings
 * and /week used to call `getOutdoorSpots()` directly: one request per opening
 * of /settings and per outdoor edit, for a list that rarely changes. The add /
 * delete mutations (use-outdoor-mutations) write the cached list in place.
 */
export const outdoorSpotsQuery = () =>
  queryOptions({
    queryKey: queryKeys.outdoorSpots,
    queryFn: getOutdoorSpots,
    staleTime: 5 * 60_000, // rarely changes
  });

export function useOutdoorSpots(enabled = true) {
  return useQuery({ ...outdoorSpotsQuery(), enabled });
}

/** B398 (O11) — the spots for a handler: the cache when fresh, else one GET. */
export function fetchOutdoorSpots(qc: QueryClient) {
  return qc.fetchQuery(outdoorSpotsQuery());
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

/**
 * A321 — does the user have a quaderno, and for which days. Only the day list
 * is read from here: the viewer signs a fresh link with its own call on open,
 * so a page left open for hours never hands the iframe an expired one.
 */
export function useQuaderno(enabled = true) {
  return useQuery({
    queryKey: queryKeys.quaderno,
    queryFn: getQuaderno,
    staleTime: 10 * 60_000,
    enabled,
    retry: false, // optional feature: a failure just hides the button
  });
}
