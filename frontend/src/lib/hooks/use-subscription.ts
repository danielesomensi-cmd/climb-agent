"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { getSubscriptionStatus, type SubscriptionStatus } from "@/lib/api";

const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

export type UseSubscriptionResult = {
  status: string;
  isActive: boolean;
  isTrialing: boolean;
  trialDaysRemaining: number | null;
  canInteract: boolean;
  hasPaymentMethod: boolean;
  loading: boolean;
};

const _ALLOW: UseSubscriptionResult = {
  status: "active",
  isActive: true,
  isTrialing: false,
  trialDaysRemaining: null,
  canInteract: true,
  hasPaymentMethod: true,
  loading: false,
};

const _DENY: UseSubscriptionResult = {
  status: "none",
  isActive: false,
  isTrialing: false,
  trialDaysRemaining: null,
  canInteract: false,
  hasPaymentMethod: false,
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
    loading: false,
  };
}

export function useSubscription(): UseSubscriptionResult {
  const [result, setResult] = useState<UseSubscriptionResult>({
    ..._DENY,
    loading: true,
  });
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    try {
      const data = await getSubscriptionStatus();
      setResult(mapResponse(data));
    } catch {
      // On error (e.g. network), deny access — fail-closed (B202)
      setResult(_DENY);
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
