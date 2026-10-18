/**
 * @vitest-environment jsdom
 *
 * B396 — useSubscription waits for Clerk.
 *
 * The query used to leave at mount, before Clerk had a session to sign it
 * with: 401, the B155 retry, a second 401, then a hard
 * `location.href = "/sign-in"` on a slow network. And while the answer was
 * pending, /today's Done / Skip / Add sent a paying climber to /subscribe.
 *
 * What must NOT change (B202 / A245 C-1): nothing is granted before the server
 * answers, and when the request cannot be made at all the result is the same
 * _DENY as before — not an endless "loading".
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createElement, type ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { auth, getSubscriptionStatus, ApiError } = vi.hoisted(() => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  }
  return {
    auth: { isLoaded: false },
    getSubscriptionStatus: vi.fn(),
    ApiError,
  };
});

vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: auth.isLoaded }) }));
vi.mock("@/lib/api", () => ({
  ApiError,
  getSubscriptionStatus: (...args: unknown[]) => getSubscriptionStatus(...args),
}));

import {
  paywallDecision,
  subscriptionIsPending,
  useSubscription,
} from "@/lib/hooks/use-subscription";
import { AUTH_WAIT_MS, shouldStopWaitingForAuth } from "@/lib/hooks/use-auth-wait";

const ACTIVE = { status: "active", is_active: true, trial_days_remaining: null, can_interact: true };

let qc: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client: qc }, children);
}

function setOnline(value: boolean) {
  Object.defineProperty(window.navigator, "onLine", { value, configurable: true });
}

beforeEach(() => {
  auth.isLoaded = false;
  getSubscriptionStatus.mockReset();
  getSubscriptionStatus.mockResolvedValue(ACTIVE);
  setOnline(true);
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});

afterEach(() => {
  vi.useRealTimers();
  setOnline(true);
});

describe("shouldStopWaitingForAuth", () => {
  it("never once Clerk has loaded", () => {
    expect(shouldStopWaitingForAuth({ authLoaded: true, online: false, waitedMs: 1e9 })).toBe(false);
  });

  it("immediately when the browser is offline", () => {
    expect(shouldStopWaitingForAuth({ authLoaded: false, online: false, waitedMs: 0 })).toBe(true);
  });

  it("online: only after the limit", () => {
    expect(shouldStopWaitingForAuth({ authLoaded: false, online: true, waitedMs: AUTH_WAIT_MS - 1 })).toBe(false);
    expect(shouldStopWaitingForAuth({ authLoaded: false, online: true, waitedMs: AUTH_WAIT_MS })).toBe(true);
  });
});

describe("subscriptionIsPending", () => {
  it("pending while we are still waiting for Clerk", () => {
    expect(subscriptionIsPending(true, false)).toBe(true);
  });

  it("not pending once we stopped waiting — the old 'could not ask' answer (deny)", () => {
    expect(subscriptionIsPending(true, true)).toBe(false);
  });

  it("an answered query is never pending", () => {
    expect(subscriptionIsPending(false, false)).toBe(false);
  });
});

describe("paywallDecision — /today's Done / Skip / Add", () => {
  it("allows when the server said yes", () => {
    expect(paywallDecision({ canInteract: true, loading: false })).toBe("allow");
  });

  it("waits (no redirect, nothing granted) while the answer is pending", () => {
    expect(paywallDecision({ canInteract: false, loading: true })).toBe("wait");
  });

  it("sends to /subscribe on a real deny", () => {
    expect(paywallDecision({ canInteract: false, loading: false })).toBe("subscribe");
  });
});

describe("useSubscription — gated on Clerk", () => {
  it("does not send the request before Clerk is ready, and grants nothing", () => {
    const { result } = renderHook(() => useSubscription(), { wrapper });
    expect(getSubscriptionStatus).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(true);
    expect(result.current.canInteract).toBe(false);
  });

  it("asks as soon as Clerk is ready", async () => {
    const { result, rerender } = renderHook(() => useSubscription(), { wrapper });
    expect(getSubscriptionStatus).not.toHaveBeenCalled();

    auth.isLoaded = true;
    rerender();

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(getSubscriptionStatus).toHaveBeenCalledTimes(1);
    expect(result.current.canInteract).toBe(true);
  });

  it("offline with Clerk down: _DENY and not loading — exactly the old fail-closed answer", () => {
    setOnline(false);
    const { result } = renderHook(() => useSubscription(), { wrapper });
    expect(getSubscriptionStatus).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    expect(result.current.canInteract).toBe(false);
    expect(result.current.status).toBe("none");
  });

  it("online but Clerk never loads: stops waiting after AUTH_WAIT_MS and denies", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useSubscription(), { wrapper });
    expect(result.current.loading).toBe(true);

    act(() => {
      vi.advanceTimersByTime(AUTH_WAIT_MS);
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.canInteract).toBe(false);
    expect(getSubscriptionStatus).not.toHaveBeenCalled();
  });

  it("a server deny still denies once Clerk is ready (B202 untouched)", async () => {
    auth.isLoaded = true;
    getSubscriptionStatus.mockRejectedValue(new ApiError(402, "nope"));
    const { result } = renderHook(() => useSubscription(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.canInteract).toBe(false);
  });
});
