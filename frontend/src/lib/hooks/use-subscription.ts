"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { ApiError, getSubscriptionStatus, type SubscriptionStatus } from "@/lib/api";

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

const _ALLOW: UseSubscriptionResult = {
  status: "active",
  isActive: true,
  isTrialing: false,
  trialDaysRemaining: null,
  canInteract: true,
  hasPaymentMethod: true,
  enforced: true,
  loading: false,
};

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

export function useSubscription(): UseSubscriptionResult {
  const [result, setResult] = useState<UseSubscriptionResult>({
    ..._DENY,
    loading: true,
  });
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /**
   * A245 C-1 (F8) — have we ever had an authoritative answer from the server?
   *
   * Until we have, a failure means "unknown" and B202 fail-closed applies.
   * Once we have, a failure means "the network is down", which is NOT evidence
   * that the subscription lapsed.
   */
  const everAnswered = useRef(false);

  const fetch = useCallback(async () => {
    try {
      const data = await getSubscriptionStatus();
      everAnswered.current = true;
      setResult(mapResponse(data));
    } catch (err) {
      // A245 C-1 (F8) — this used to be an unconditional _DENY, so ANY fetch
      // error (plain offline included) flipped canInteract to false and /today
      // bounced the user to /subscribe on mark-done. A paying climber in a gym
      // with no signal was told to go buy a subscription: the worst possible
      // message in the worst possible place.
      //
      // A 401/402/403 is the server actually answering about entitlement —
      // still fail-closed. Anything else (network, timeout, 5xx) is transport,
      // so keep the last known state if we ever had one.
      if (shouldDenyOnError(err, everAnswered.current)) {
        setResult(_DENY);
        return;
      }
      setResult((prev) => ({ ...prev, loading: false }));
    }
  }, []);

  useEffect(() => {
    fetch();
    // A245 B-5 (F44) — the 5-minute poll used to fire regardless of
    // connectivity: offline it burned a request (and, since A245 A-3, a 15s
    // timeout) every 5 minutes, all guaranteed to fail. Skip the tick when the
    // browser knows there is no connection, and catch up on reconnect.
    //
    // Scope note: this only gates WHEN we poll. The fail-closed _DENY on error
    // (B202) is untouched here — that is F8, Phase C.
    const tick = () => {
      if (typeof navigator !== "undefined" && navigator.onLine === false) return;
      fetch();
    };
    timerRef.current = setInterval(tick, REFRESH_INTERVAL_MS);
    window.addEventListener("online", fetch);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      window.removeEventListener("online", fetch);
    };
  }, [fetch]);

  return result;
}
