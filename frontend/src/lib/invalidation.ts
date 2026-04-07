import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "./query-keys";

/**
 * A187 — Invalidation helpers.
 *
 * Centralised invalidation patterns for cascade-heavy mutations. Pages and
 * mutation hooks call these instead of duplicating prefix-match logic.
 */

/** Full reset: macrocycle generate, import, delete state. Clears every key. */
export function invalidateAll(qc: QueryClient) {
  qc.clear();
}

/** Equipment, availability, or any change that may shift week plans. */
export function invalidateWeekPlans(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: queryKeys.weekAll });
  qc.invalidateQueries({ queryKey: queryKeys.state });
}

/** Outdoor write: refresh sessions, stats, and any per-date logs. */
export function invalidateOutdoor(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: queryKeys.outdoorAll });
}

/** Free session write: refresh history (badges in today/week). */
export function invalidateFreeSessionHistory(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: queryKeys.freeSessionHistoryAll });
}
