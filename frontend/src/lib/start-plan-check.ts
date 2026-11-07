"use client";

import type { QueryClient } from "@tanstack/react-query";
import { getWeek } from "@/lib/api";
import { findDay } from "@/lib/day-slots";
import { queryKeys } from "@/lib/query-keys";
import { PERSIST_MAX_AGE_MS } from "@/lib/query-persist";
import type { WeekCacheEntry } from "@/lib/week-cache";

/**
 * B414 (INBOX-2026-11-04-ORPHAN, prevention) — «Start session» on a NEW
 * session checks that it is still on that day of the plan when the copy on
 * the phone is old. On 04/11 the coach swapped the treadmill for a custom at
 * 12:21 from another client; the phone kept a week cached since the morning
 * (persisted for 7 days, never refetched on focus), the player started the
 * session that was gone and its log became an orphan.
 *
 * Only when it can help and never in the way: online, a cached week holding
 * the day, older than `STALE_MS`; the refetch is bounded (`TIMEOUT_MS`) and a
 * timeout or an error starts the session as before (offline at the crag must
 * still work). Resume and the queued-feedback view never come here.
 */
export const START_CHECK_STALE_MS = 60_000;
export const START_CHECK_TIMEOUT_MS = 3_000;

interface CachedWeekHit {
  weekNum: number;
  updatedAt: number;
}

/** The freshest cached week entry that holds `date`. */
function cachedWeekFor(qc: QueryClient, date: string): CachedWeekHit | null {
  let best: CachedWeekHit | null = null;
  for (const query of qc.getQueryCache().findAll({ queryKey: queryKeys.weekAll })) {
    const key = query.queryKey;
    if (key.length !== 2 || typeof key[1] !== "number") continue;
    const data = query.state.data as WeekCacheEntry | undefined;
    if (!data?.week_plan || !findDay(data.week_plan, date)) continue;
    const updatedAt = query.state.dataUpdatedAt;
    if (!best || updatedAt > best.updatedAt) best = { weekNum: key[1], updatedAt };
  }
  return best;
}

function isOffline(): boolean {
  return typeof navigator !== "undefined" && navigator.onLine === false;
}

/** Does this Start have to look at the server first? Pure on the cache. */
export function startNeedsPlanCheck(qc: QueryClient, date: string, now: number = Date.now()): boolean {
  if (isOffline()) return false;
  const hit = cachedWeekFor(qc, date);
  return !!hit && now - hit.updatedAt > START_CHECK_STALE_MS;
}

/**
 * Is `sessionId` still on `date` in the server's plan? Fail-open: true on a
 * timeout, an error, or a day the fresh week does not hold.
 */
export async function sessionStillPlanned(qc: QueryClient, date: string, sessionId: string): Promise<boolean> {
  const hit = cachedWeekFor(qc, date);
  if (!hit) return true;
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const fresh = await Promise.race([
      qc.fetchQuery<WeekCacheEntry>({
        queryKey: queryKeys.week(hit.weekNum),
        queryFn: () => getWeek(hit.weekNum) as Promise<WeekCacheEntry>,
        staleTime: 0,
        gcTime: PERSIST_MAX_AGE_MS,
      }),
      new Promise<null>((resolve) => {
        timer = setTimeout(() => resolve(null), START_CHECK_TIMEOUT_MS);
      }),
    ]);
    const day = fresh?.week_plan ? findDay(fresh.week_plan, date) : null;
    if (!day) return true;
    return (day.sessions ?? []).some((s) => s.session_id === sessionId);
  } catch {
    return true;
  } finally {
    clearTimeout(timer);
  }
}
