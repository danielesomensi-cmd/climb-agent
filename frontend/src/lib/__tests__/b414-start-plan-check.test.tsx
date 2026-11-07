/**
 * @vitest-environment jsdom
 *
 * B414 (INBOX-2026-11-04-ORPHAN, prevention) — «Start session» from a week
 * copy older than a minute reads the week again (bounded) and does not start a
 * session the plan no longer has: on 04/11 the phone started the treadmill
 * the coach had already swapped for a custom. A fresh copy starts at once, as
 * before; and back in the foreground the week query refetches when stale.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { router, toast, getWeek } = vi.hoisted(() => ({
  router: { push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() },
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn(), dismiss: vi.fn() }),
  getWeek: vi.fn<(n: number) => Promise<unknown>>(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true, isSignedIn: true }) }));
vi.mock("sonner", () => ({ toast }));
vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  getSubscriptionStatus: vi.fn(),
  getWeek: (n: number) => getWeek(n),
  removeExerciseFromSession: vi.fn(),
  setSessionSurface: vi.fn(),
  apiErrorDetail: vi.fn(),
}));

import { SessionCard } from "@/components/training/session-card";
import { useWeekPlan } from "@/lib/hooks/queries/use-week-plan";
import { guidedStorageKey } from "@/lib/guided-session-utils";
import { queryKeys } from "@/lib/query-keys";
import type { SessionSlot } from "@/lib/types";

class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, String(v)); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

const DATE = "2026-11-04";
const TREADMILL = {
  session_id: "treadmill_hiit_4x4",
  slot: "lunch",
  location: "home",
  status: "planned",
  resolved: {
    resolved_session: {
      exercise_instances: [{ exercise_id: "treadmill_intervals", name: "Intervals", prescription: { sets: 4 } }],
    },
  },
} as unknown as SessionSlot;
const CUSTOM = { session_id: "custom_cs_320de282", slot: "lunch", location: "home", status: "planned" };

const week = (sessions: unknown[]) => ({
  week_num: 9,
  week_plan: { plan_revision: 5, weeks: [{ days: [{ date: DATE, sessions }] }] },
});

let qc: QueryClient;

function renderCard() {
  return render(
    <QueryClientProvider client={qc}>
      <SessionCard session={TREADMILL} date={DATE} onMove={() => {}} />
    </QueryClientProvider>,
  );
}

function tapStart() {
  act(() => {
    fireEvent.click(screen.getByRole("button", { name: /Start session/ }));
  });
}

beforeEach(() => {
  Object.defineProperty(window, "localStorage", { value: new MemoryStorage(), configurable: true });
  (window as unknown as { Clerk: unknown }).Clerk = { loaded: true, user: { id: "user_1" } };
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  window.matchMedia = ((q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  })) as unknown as typeof window.matchMedia;
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
  delete (window as unknown as { Clerk?: unknown }).Clerk;
});

describe("B414 — Start from an old week copy", () => {
  it("the session is gone on the server: no start, the athlete is told", async () => {
    qc.setQueryData(queryKeys.week(0), week([TREADMILL]), { updatedAt: Date.now() - 5 * 60_000 });
    getWeek.mockResolvedValue(week([CUSTOM]));
    renderCard();
    tapStart();
    await waitFor(() => expect(toast.warning).toHaveBeenCalledTimes(1));
    expect(getWeek).toHaveBeenCalledWith(0);
    expect(router.push).not.toHaveBeenCalled();
    expect(window.localStorage.getItem(guidedStorageKey(DATE, "treadmill_hiit_4x4"))).toBeNull();
  });

  it("still there: the player opens", async () => {
    qc.setQueryData(queryKeys.week(0), week([TREADMILL]), { updatedAt: Date.now() - 5 * 60_000 });
    getWeek.mockResolvedValue(week([TREADMILL]));
    renderCard();
    tapStart();
    await waitFor(() => expect(router.push).toHaveBeenCalledWith(`/guided/${DATE}/treadmill_hiit_4x4`));
    expect(toast.warning).not.toHaveBeenCalled();
  });

  it("a copy younger than a minute: starts at once, no GET", () => {
    qc.setQueryData(queryKeys.week(0), week([TREADMILL]));
    renderCard();
    tapStart();
    expect(router.push).toHaveBeenCalledWith(`/guided/${DATE}/treadmill_hiit_4x4`);
    expect(getWeek).not.toHaveBeenCalled();
  });

  it("offline: starts at once, as before", () => {
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
    qc.setQueryData(queryKeys.week(0), week([TREADMILL]), { updatedAt: Date.now() - 5 * 60_000 });
    renderCard();
    tapStart();
    expect(router.push).toHaveBeenCalledWith(`/guided/${DATE}/treadmill_hiit_4x4`);
    expect(getWeek).not.toHaveBeenCalled();
  });
});

describe("B414 — the week refetches when the app comes back to the foreground", () => {
  it("useWeekPlan turns refetchOnWindowFocus on (the global default stays off)", () => {
    getWeek.mockResolvedValue(week([TREADMILL]));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => createElement(QueryClientProvider, { client }, children);
    renderHook(() => useWeekPlan(0), { wrapper });
    const query = client.getQueryCache().find({ queryKey: queryKeys.week(0) });
    const observer = query?.observers[0];
    expect(observer?.options.refetchOnWindowFocus).toBe(true);
    expect(observer?.options.staleTime).toBe(60_000);
  });
});
