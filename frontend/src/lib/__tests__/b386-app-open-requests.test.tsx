/**
 * @vitest-environment jsdom
 *
 * B386 — fewer requests when the PWA opens.
 *
 * The measured number is the count of API calls made by the data hooks /today
 * mounts on a cold open (state, current week, free-session badges for the day
 * and the week, and the two useSubscription consumers: the page and the
 * TrialBanner). Before B386 that set made 12 calls — 1 state + 1 week + 1
 * week(n+1) prefetch + 7 per-day /free-session/history + 2 subscription — on
 * top of the root dispatcher's own /api/state. After B386 it is 3.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { createElement, useMemo, type ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { ApiError, STATE, WEEK_DATES, calls, getState, getWeek, getSubscriptionStatus, getFreeSessionHistory } =
  vi.hoisted(() => {
    class ApiError extends Error {
      status: number;
      constructor(status: number, message: string) {
        super(message);
        this.name = "ApiError";
        this.status = status;
      }
    }
    const WEEK_DATES = [
      "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15",
      "2026-10-16", "2026-10-17", "2026-10-18",
    ];
    const STATE = {
      macrocycle: { start_date: "2026-09-07" },
      free_sessions: [
        { id: "fs-1", date: "2026-10-13", surface: "boulder", load_score: 40 },
        { id: "fs-2", date: "2026-10-17", surface: "mobility", load_score: 5 },
        { id: "fs-3", date: "2026-10-17", surface: "circuit_core", load_score: 12 },
        { id: "fs-old", date: "2026-09-01", surface: "boulder", load_score: 30 },
      ],
    };
    const WEEK = {
      week_num: 6,
      week_plan: { weeks: [{ days: WEEK_DATES.map((date) => ({ date, sessions: [] })) }] },
    };
    const calls: string[] = [];
    const getState = vi.fn(async () => {
      calls.push("state");
      return STATE;
    });
    const getWeek = vi.fn(async (n: number) => {
      calls.push(`week:${n}`);
      return { ...WEEK, week_num: n === 0 ? 6 : n };
    });
    const getSubscriptionStatus = vi.fn(async () => {
      calls.push("subscription");
      return { status: "active", is_active: true, trial_days_remaining: null, can_interact: true };
    });
    const getFreeSessionHistory = vi.fn(async (date: string) => {
      calls.push(`history:${date}`);
      return { sessions: [] };
    });
    return { ApiError, STATE, WEEK, WEEK_DATES, calls, getState, getWeek, getSubscriptionStatus, getFreeSessionHistory };
  });

vi.mock("@/lib/api", () => ({
  ApiError,
  getState: () => getState(),
  getStateStatus: vi.fn(),
  getWeek: (n: number) => getWeek(n),
  getSubscriptionStatus: () => getSubscriptionStatus(),
  getFreeSessionHistory: (d: string) => getFreeSessionHistory(d),
  getFreeSessionSurfaces: vi.fn(),
  getFreeSessionPresets: vi.fn(),
}));

// B396 — useSubscription waits for Clerk; the cold open measured here has it loaded.
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true }) }));

import { useUserState } from "@/lib/hooks/queries/use-user-state";
import { useWeekPlan } from "@/lib/hooks/queries/use-week-plan";
import {
  selectFreeSessionsForDates,
  useFreeSessionsForDates,
} from "@/lib/hooks/queries/use-free-session";
import { useSubscription, deriveSubscriptionResult } from "@/lib/hooks/use-subscription";
import { fastPathDestination } from "@/lib/last-destination";
import { invalidateFreeSessionHistory } from "@/lib/invalidation";
import { queryKeys } from "@/lib/query-keys";

let qc: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client: qc }, children);
}

beforeEach(() => {
  calls.length = 0;
  vi.clearAllMocks();
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});

/** The data hooks /today mounts on a cold open (page + TrialBanner). */
function useTodayOpen(targetDate: string) {
  const state = useUserState(true);
  const week = useWeekPlan(0, true);
  const page = useSubscription();
  const banner = useSubscription();
  const weekDates = useMemo(
    () => week.data?.week_plan?.weeks.flatMap((w) => w.days).map((d) => d.date) ?? [],
    [week.data],
  );
  const targetDates = useMemo(() => [targetDate], [targetDate]);
  const day = useFreeSessionsForDates(targetDates, true);
  const wk = useFreeSessionsForDates(weekDates, true);
  return { state, week, page, banner, day, wk };
}

/** Let idle callbacks / timers (the lazy prefetch) run. */
const flushIdle = () => new Promise((r) => setTimeout(r, 400));

describe("B386 — request count on a cold /today", () => {
  it("makes 3 API calls: state, current week, one subscription", async () => {
    const { result } = renderHook(() => useTodayOpen("2026-10-17"), { wrapper });
    await waitFor(() => {
      expect(result.current.week.isSuccess).toBe(true);
      expect(result.current.state.isSuccess).toBe(true);
      expect(result.current.page.loading).toBe(false);
    });
    await flushIdle();

    expect([...calls].sort()).toEqual(["state", "subscription", "week:0"]);
    expect(getFreeSessionHistory).not.toHaveBeenCalled();
  });

  it("still delivers the free-session badges, from the state payload", async () => {
    const { result } = renderHook(() => useTodayOpen("2026-10-17"), { wrapper });
    await waitFor(() => expect(result.current.wk.sessions).toHaveLength(3));

    expect(result.current.day.sessions.map((s) => s.id)).toEqual(["fs-2", "fs-3"]);
    expect(result.current.wk.sessions.map((s) => s.id)).toEqual(["fs-1", "fs-2", "fs-3"]);
    // /week groups by `date`, which the old /history view did not carry.
    expect(result.current.wk.sessions.every((s) => typeof s.date === "string")).toBe(true);
    expect(result.current.wk.isSettled).toBe(true);
  });

  it("shares one subscription answer between page and banner", async () => {
    const { result } = renderHook(() => useTodayOpen("2026-10-17"), { wrapper });
    await waitFor(() => expect(result.current.banner.loading).toBe(false));
    expect(result.current.page.canInteract).toBe(true);
    expect(result.current.banner.canInteract).toBe(true);
    expect(getSubscriptionStatus).toHaveBeenCalledTimes(1);
  });
});

describe("B386 — lazy next-week prefetch", () => {
  it("does not prefetch week n+1 by default (/today, Settings)", async () => {
    const { result } = renderHook(() => useWeekPlan(0, true), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    await flushIdle();
    expect(calls).toEqual(["week:0"]);
  });

  it("prefetches week n+1 on idle when asked (/week)", async () => {
    const { result } = renderHook(() => useWeekPlan(0, true, { prefetchNext: true }), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    await waitFor(() => expect(calls).toContain("week:7"));
    expect(qc.getQueryData(queryKeys.week(7))).toBeDefined();
  });
});

describe("selectFreeSessionsForDates", () => {
  it("filters by date and follows the order of the dates", () => {
    const out = selectFreeSessionsForDates(STATE, ["2026-10-17", "2026-10-13"]);
    expect(out.map((s) => s.id)).toEqual(["fs-2", "fs-3", "fs-1"]);
  });

  it("is empty for a missing state, no free_sessions or no dates", () => {
    expect(selectFreeSessionsForDates(null, WEEK_DATES)).toEqual([]);
    expect(selectFreeSessionsForDates({}, WEEK_DATES)).toEqual([]);
    expect(selectFreeSessionsForDates({ free_sessions: "nope" }, WEEK_DATES)).toEqual([]);
    expect(selectFreeSessionsForDates(STATE, [])).toEqual([]);
  });
});

describe("invalidateFreeSessionHistory", () => {
  it("refreshes ['state'] (where the badges come from) but not ['state','status']", () => {
    qc.setQueryData(queryKeys.state, STATE);
    qc.setQueryData(queryKeys.stateStatus, { is_macrocycle_stale: false });
    invalidateFreeSessionHistory(qc);
    expect(qc.getQueryState(queryKeys.state)?.isInvalidated).toBe(true);
    expect(qc.getQueryState(queryKeys.stateStatus)?.isInvalidated).toBe(false);
  });
});

describe("deriveSubscriptionResult — B202 fail-closed through the cache", () => {
  const ok = { status: "active", is_active: true, trial_days_remaining: null, can_interact: true };

  it("loading and denied before the first answer", () => {
    const r = deriveSubscriptionResult({ data: undefined, error: null, isPending: true });
    expect(r.loading).toBe(true);
    expect(r.canInteract).toBe(false);
  });

  it("denies a transport failure before any answer", () => {
    const r = deriveSubscriptionResult({ data: undefined, error: new ApiError(0, "offline"), isPending: false });
    expect(r.canInteract).toBe(false);
    expect(r.loading).toBe(false);
  });

  it("keeps the last answer on a transport failure after one", () => {
    const r = deriveSubscriptionResult({ data: ok, error: new ApiError(503, "down"), isPending: false });
    expect(r.canInteract).toBe(true);
  });

  it.each([401, 402, 403])("denies on %i even with a cached answer", (status) => {
    const r = deriveSubscriptionResult({ data: ok, error: new ApiError(status, "no"), isPending: false });
    expect(r.canInteract).toBe(false);
  });
});

describe("root dispatcher fast path", () => {
  it("goes straight to /today only when /today is remembered", () => {
    expect(fastPathDestination("/today")).toBe("/today");
    expect(fastPathDestination("/onboarding/welcome")).toBeNull();
    expect(fastPathDestination(null)).toBeNull();
  });
});
