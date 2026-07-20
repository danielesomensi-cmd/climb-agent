"use client";

import { ApiError, NETWORK_ERROR_STATUS, completeOnboarding } from "@/lib/api";
import type { OnboardingData } from "@/lib/types";

/**
 * A245 Phase D (F17) — the onboarding submit, at the single highest-intent
 * moment in the product ("Start training now").
 *
 * What the user used to see there: `API 422: {"detail":"Macrocycle generation
 * failed: ..."}`, `API 429: ...`, or `TypeError: Load failed`. Raw JSON, one
 * tap from the finish line. This maps every failure to something a human can
 * act on, and says whether retrying is worth it.
 *
 * The 15s client abort is also gone. `/api/onboarding/complete` is in
 * SLOW_PATHS (A245 A-3) with a 60s budget, because this call generates a whole
 * macrocycle and can land on a Railway cold start. The old 15s abort fired
 * while the server was still working — and the server saved anyway, so the
 * user retried against a request that had already succeeded, burning the
 * 3/min rate limit on the way.
 */

export type SubmitFailure = {
  /** Human-readable, actionable. Never a raw status or JSON body. */
  message: string;
  /** False when retrying immediately cannot help (e.g. rate limited). */
  retryable: boolean;
};

export function describeSubmitError(err: unknown): SubmitFailure {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return {
      message:
        "You're offline. Your answers are saved on this device — reconnect and tap Retry.",
      retryable: true,
    };
  }

  const status = err instanceof ApiError ? err.status : null;

  switch (true) {
    case status === NETWORK_ERROR_STATUS:
      return {
        message:
          "This is taking longer than usual — the server may be waking up. Your answers are saved; tap Retry.",
        retryable: true,
      };
    case status === 429:
      return {
        message:
          "Too many attempts in a row. Wait about a minute, then tap Retry — no need to redo the wizard.",
        retryable: false,
      };
    case status === 401:
      return {
        message: "Your session expired. Sign in again — your answers are saved on this device.",
        retryable: false,
      };
    case status === 422 || status === 400:
      return {
        message:
          "We couldn't build a plan from these answers. Check the summary below — especially your grades, locations and availability — then try again.",
        retryable: true,
      };
    case status != null && status >= 500:
      return {
        message: "Something went wrong on our side. Your answers are saved; tap Retry.",
        retryable: true,
      };
    default:
      return {
        message: "We couldn't create your plan. Your answers are saved; tap Retry.",
        retryable: true,
      };
  }
}

export type SubmitResult = { ok: true } | ({ ok: false } & SubmitFailure);

export async function submitOnboarding(
  data: OnboardingData,
  opts: { testWeek?: boolean } = {},
): Promise<SubmitResult> {
  try {
    await completeOnboarding(
      opts.testWeek ? { ...data, test_week_requested: true } : data,
    );
    return { ok: true };
  } catch (err) {
    console.error("[onboarding] submit failed:", err);
    return { ok: false, ...describeSubmitError(err) };
  }
}
