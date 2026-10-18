import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "./query-keys";

/**
 * A187 — Invalidation helpers.
 *
 * Centralised invalidation patterns for cascade-heavy mutations. Pages and
 * mutation hooks call these instead of duplicating prefix-match logic.
 */

/**
 * B398 (O13) — cache roots that do not depend on the user's training data:
 * the immutable catalog, the subscription (a billing row, not part of the
 * state) and the static onboarding defaults. A data reset leaves them alone.
 */
export const DATA_INDEPENDENT_ROOTS: readonly string[] = ["catalog", "subscription", "onboarding"];

/**
 * Full reset of the user's DATA: macrocycle generate, import, delete state.
 *
 * B398 (O13) — this used to be `qc.clear()`, which also dropped the catalog and
 * the subscription status: 2-4 requests to fetch again what had not changed,
 * and a TrialBanner that flickered while the subscription reloaded. Every
 * query built from the user's data is still REMOVED (not just invalidated —
 * after an import or a delete the old plan must never be shown again, not even
 * for the second a background refetch takes).
 *
 * Not for a sign-out or an account switch: there the whole cache belongs to
 * another person and `SessionScopeGuard` keeps calling `qc.clear()`.
 */
export function invalidateAll(qc: QueryClient) {
  qc.removeQueries({
    predicate: (query) => {
      const root = query.queryKey[0];
      return !(typeof root === "string" && DATA_INDEPENDENT_ROOTS.includes(root));
    },
  });
}

/** Equipment, availability, or any change that may shift week plans. */
export function invalidateWeekPlans(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: queryKeys.weekAll });
  qc.invalidateQueries({ queryKey: queryKeys.state });
}

/** Outdoor write: refresh sessions, stats, and any per-date logs. B371: and
 * the weeks — logging an outdoor session syncs it onto the week plan server
 * side (B273), which moves the plan's revision; a cached week left behind
 * would make the next write a 409.
 *
 * B398 (O1): returns the refetch so a caller can wait for the fresh routes. */
export function invalidateOutdoor(qc: QueryClient): Promise<void> {
  return Promise.all([
    qc.invalidateQueries({ queryKey: queryKeys.outdoorAll }),
    qc.invalidateQueries({ queryKey: queryKeys.weekAll }),
  ]).then(() => undefined);
}

/** Free session write: refresh the badges in today/week.
 *
 * B386 — those badges are now derived from `['state']` (free_sessions rides on
 * the state payload), so state is what has to refetch. The history prefix is
 * kept for any per-day `/history` reader that may still exist. */
export function invalidateFreeSessionHistory(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: queryKeys.state, exact: true });
  qc.invalidateQueries({ queryKey: queryKeys.freeSessionHistoryAll });
}

/** Custom session write: refresh list + detail caches. */
export function invalidateCustomSessions(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: queryKeys.customSessionAll });
}
