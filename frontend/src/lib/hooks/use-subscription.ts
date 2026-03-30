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
  loading: boolean;
};

const _ALLOW: UseSubscriptionResult = {
  status: "active",
  isActive: true,
  isTrialing: false,
  trialDaysRemaining: null,
  canInteract: true,
  loading: false,
};

function mapResponse(data: SubscriptionStatus): UseSubscriptionResult {
  return {
    status: data.status,
    isActive: data.is_active,
    isTrialing: data.status === "trialing",
    trialDaysRemaining: data.trial_days_remaining,
    canInteract: data.can_interact,
    loading: false,
  };
}

export function useSubscription(): UseSubscriptionResult {
  const [result, setResult] = useState<UseSubscriptionResult>({
    ..._ALLOW,
    loading: true,
  });
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    try {
      const data = await getSubscriptionStatus();
      setResult(mapResponse(data));
    } catch {
      // On error (e.g. network), default to allowing access — don't block on infra issues
      setResult(_ALLOW);
    }
  }, []);

  useEffect(() => {
    fetch();
    timerRef.current = setInterval(fetch, REFRESH_INTERVAL_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetch]);

  return result;
}
