/**
 * @vitest-environment jsdom
 *
 * B396 review — the lazily loaded dialogs are fetched while idle and online.
 *
 * React.lazy keeps a rejected import for the life of the page, so the
 * ChunkErrorBoundary alone only turns "the page crashes" into "it says it
 * needs a connection". Fetching the chunk while the page is idle and online
 * puts it in the service worker cache before the user is at the gym. Offline
 * there is nothing to fetch: no attempt (and no failure to remember).
 *
 * The order of the tests matters: a module is evaluated once per file, so the
 * offline case (no import) runs before the online one (one import).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { loaded } = vi.hoisted(() => ({ loaded: { sheet: 0, addExercise: 0 } }));

vi.mock("@/components/training/weekly-checkin-sheet", () => {
  loaded.sheet += 1;
  return { WeeklyCheckinSheet: () => null };
});
vi.mock("@/components/training/add-exercise-dialog", () => {
  loaded.addExercise += 1;
  return { AddExerciseDialog: () => null };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }) }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true, isSignedIn: true }) }));
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));
vi.mock("@/lib/api", () => ({
  removeExerciseFromSession: vi.fn(),
  setSessionSurface: vi.fn(),
  apiErrorDetail: vi.fn(),
}));

import { WeeklyCheckinCard } from "@/components/training/weekly-checkin-card";
import { SessionCard } from "@/components/training/session-card";
import type { SessionSlot, WeekPlan } from "@/lib/types";

class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, String(v)); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

const session = {
  session_id: "strength_long",
  slot: "evening",
  location: "gym",
  status: "planned",
  resolved: {
    resolved_session: {
      exercise_instances: [{ exercise_id: "max_hang", name: "Max hang", prescription: { sets: 3 } }],
    },
  },
} as unknown as SessionSlot;
const weekPlan = { weeks: [{ days: [{ date: "2026-10-18", sessions: [session] }] }] } as unknown as WeekPlan;

function renderBoth() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <WeeklyCheckinCard weekPlan={null} onPlanUpdated={() => {}} />
      <SessionCard session={session} date="2026-10-18" weekPlan={weekPlan} sessionIndex={0} />
    </QueryClientProvider>,
  );
}

/** jsdom has no requestIdleCallback: scheduleIdle falls back to a 300 ms timer. */
const idle = () => new Promise((r) => setTimeout(r, 450));

function setOnline(value: boolean) {
  Object.defineProperty(window.navigator, "onLine", { value, configurable: true });
}

beforeEach(() => {
  Object.defineProperty(window, "localStorage", { value: new MemoryStorage(), configurable: true });
  window.matchMedia = ((q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  })) as unknown as typeof window.matchMedia;
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 18, 9, 0)); // Sunday → the check-in card shows
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  setOnline(true);
});

describe("idle preload of the lazy dialogs", () => {
  it("offline: nothing is fetched", async () => {
    setOnline(false);
    renderBoth();
    await idle();
    expect(loaded).toEqual({ sheet: 0, addExercise: 0 });
  });

  it("online: both chunks are fetched without a tap", async () => {
    setOnline(true);
    renderBoth();
    await idle();
    expect(loaded).toEqual({ sheet: 1, addExercise: 1 });
  });
});
