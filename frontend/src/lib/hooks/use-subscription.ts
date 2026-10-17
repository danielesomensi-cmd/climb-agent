"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, getSubscriptionStatus, type SubscriptionStatus } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

export type UseSubscriptionResult = {
  status: string;
  isActive: boolean;
  isTrialing: boolean;
  trialDaysRemaining: number | null;
  canInteract: boolean;
  hasPaymentMethod: boolean;
  /**
   * A285 — false only while billing is paused server-side.
   *
   * Everything else here says "you may train"; this says *why*. Without it a
   * paused user looks exactly like a paying one, and Settings would offer them
   * a billing portal that 404s (no Stripe customer behind the row).
   *
   * Defaults to true everywhere it is unknown — including _DENY, an older
   * backend that omits the field, and the pre-answer loading state — so the
   * paused UI only ever appears on an explicit server `false`.
   */
  enforced: boolean;
  loading: boolean;
};

// B355 — `_ALLOW` (il fallback fail-open pre-B202) è stato rimosso: da B202 il
// solo fallback è `_DENY`, la costante non era più referenziata da nessuno.

const _DENY: UseSubscriptionResult = {
  status: "none",
  isActive: false,
  isTrialing: false,
  trialDaysRemaining: null,
  canInteract: false,
  hasPaymentMethod: false,
  enforced: true,
  loading: false,
};

function mapResponse(data: SubscriptionStatus): UseSubscriptionResult {
  return {
    status: data.status,
    isActive: data.is_active,
    isTrialing: data.status === "trialing",
    trialDaysRemaining: data.trial_days_remaining,
    canInteract: data.can_interact,
    hasPaymentMethod: data.has_payment_method ?? false,
    enforced: data.enforced ?? true,
    loading: false,
  };
}

/**
 * A245 C-1 (F8) — the paywall rule, extracted so it can be tested directly.
 *
 * @param err          whatever `getSubscriptionStatus()` rejected with
 * @param everAnswered has the server ever given us an authoritative answer?
 * @returns true to fall back to _DENY (B202 fail-closed)
 *
 * A 401/402/403 is the server actually ruling on entitlement → deny.
 * Anything else is transport (offline, timeout, 5xx). Before the first
 * successful answer we cannot tell entitled from unknown, so deny; afterwards
 * the last known state is better evidence than a dropped connection.
 */
export function shouldDenyOnError(err: unknown, everAnswered: boolean): boolean {
  const status = err instanceof ApiError ? err.status : null;
  if (status === 401 || status === 402 || status === 403) return true;
  return !everAnswered;
}

/**
 * B386 — how long a subscription answer is reused before asking again.
 *
 * /today and the TrialBanner both mount useSubscription on every open; with
 * the old per-instance useEffect that was 2+ identical requests per page. The
 * shared React Query cache makes it one, and navigating between pages inside
 * this window costs nothing.
 */
export const SUBSCRIPTION_STALE_MS = 60_000;

/**
 * B386 — the fail-closed mapping, pure so it can be tested without a client.
 *
 * `hasData` plays the role the old `everAnswered` ref had, but cache-wide: a
 * successful answer from ANY mounted consumer counts. The rule is unchanged —
 * a 401/402/403 denies even with data in hand; a transport failure keeps the
 * last known answer; any failure before the first answer denies (B202).
 */
export function deriveSubscriptionResult(args: {
  data: SubscriptionStatus | undefined;
  error: unknown;
  isPending: boolean;
}): UseSubscriptionResult {
  const { data, error, isPending } = args;
  if (error && shouldDenyOnError(error, data !== undefined)) return _DENY;
  if (data !== undefined) return mapResponse(data);
  if (isPending) return { ..._DENY, loading: true };
  return _DENY;
}

export function useSubscription(): UseSubscriptionResult {
  const query = useQuery({
    queryKey: queryKeys.subscriptionStatus,
    queryFn: getSubscriptionStatus,
    staleTime: SUBSCRIPTION_STALE_MS,
    // The old hook never retried: a retry delays the fail-closed answer and is
    // pointless on a 401/402/403.
    retry: false,
    // A245 B-5 (F44) — poll every 5 minutes, but never while the browser knows
    // it is offline (each tick would be a guaranteed failure + a 15s timeout).
    refetchInterval: () =>
      typeof navigator !== "undefined" && navigator.onLine === false
        ? false
        : REFRESH_INTERVAL_MS,
    refetchIntervalInBackground: false,
    // The old hook refetched on every `online` event: catch up on reconnect.
    refetchOnReconnect: "always",
    // Not persisted (PERSISTED_QUERY_PREFIXES is state/week only): a cold open
    // always asks the server before granting anything — B202 is untouched.
  });

  return useMemo(
    () =>
      deriveSubscriptionResult({
        data: query.data,
        error: query.error,
        isPending: query.isPending,
      }),
    [query.data, query.error, query.isPending],
  );
}
