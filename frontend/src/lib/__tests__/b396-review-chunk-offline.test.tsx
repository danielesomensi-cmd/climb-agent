/**
 * @vitest-environment jsdom
 *
 * B396 review — a lazily loaded dialog whose chunk cannot be fetched.
 *
 * B396 moved the weekly check-in sheet and the "Add exercise" dialog out of
 * the /today first load (next/dynamic). Offline, a chunk the service worker has
 * never seen cannot be fetched: React.lazy throws during render and the route
 * error boundary replaces the whole page. Both are now behind a
 * ChunkErrorBoundary that closes them with a toast, and preloaded while idle
 * and online.
 *
 * next/dynamic is replaced by what it does in the App Router
 * (next/dist/shared/lib/lazy-dynamic/loadable.js, ssr: false): React.lazy
 * inside a Suspense with a null fallback. The pages-router build that vitest
 * would otherwise resolve swallows the error, which is not what ships.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { Component, type ReactNode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { router, toast } = vi.hoisted(() => ({
  router: { push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() },
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), dismiss: vi.fn() }),
}));

vi.mock("next/dynamic", async () => {
  const React = await import("react");
  return {
    default: (loader: () => Promise<unknown>) => {
      const Lazy = React.lazy(() =>
        loader().then((mod) => ({
          default: (mod && typeof mod === "object" && "default" in mod
            ? (mod as { default: unknown }).default
            : mod) as React.ComponentType<Record<string, unknown>>,
        })),
      );
      return function LoadableComponent(props: Record<string, unknown>) {
        return React.createElement(React.Suspense, { fallback: null }, React.createElement(Lazy, props));
      };
    },
  };
});
// The chunks are unreachable: the import itself rejects, as offline.
vi.mock("@/components/training/weekly-checkin-sheet", async () => {
  throw new Error("ChunkLoadError: Loading chunk weekly-checkin-sheet failed");
});
vi.mock("@/components/training/add-exercise-dialog", async () => {
  throw new Error("ChunkLoadError: Loading chunk add-exercise-dialog failed");
});
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true, isSignedIn: true }) }));
vi.mock("sonner", () => ({ toast }));
vi.mock("@/lib/api", () => ({
  removeExerciseFromSession: vi.fn(),
  setSessionSurface: vi.fn(),
  apiErrorDetail: vi.fn(),
}));

import { WeeklyCheckinCard } from "@/components/training/weekly-checkin-card";
import { SessionCard } from "@/components/training/session-card";
import { readCheckinDismissed } from "@/lib/checkin-dismiss";
import type { SessionSlot, WeekPlan } from "@/lib/types";

const OFFLINE = "Needs a connection — try again when you're online";

class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, String(v)); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

/** Stands for the route's error.tsx: anything reaching it is the page crashing. */
const pageCrashes: Error[] = [];
class RouteErrorBoundary extends Component<{ children: ReactNode }, { crashed: boolean }> {
  state = { crashed: false };
  static getDerivedStateFromError() {
    return { crashed: true };
  }
  componentDidCatch(error: Error) {
    pageCrashes.push(error);
  }
  render() {
    return this.state.crashed ? <p>Something went wrong</p> : this.props.children;
  }
}

function renderPage(children: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RouteErrorBoundary>{children}</RouteErrorBoundary>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  pageCrashes.length = 0;
  vi.clearAllMocks();
  Object.defineProperty(window, "localStorage", { value: new MemoryStorage(), configurable: true });
  Object.defineProperty(window, "sessionStorage", { value: new MemoryStorage(), configurable: true });
  window.matchMedia = ((q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  })) as unknown as typeof window.matchMedia;
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 9, 18, 9, 0)); // Sunday → the check-in card shows
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("WeeklyCheckinCard — the sheet's chunk cannot load", () => {
  it("tapping the card toasts instead of crashing /today, and the card stays", async () => {
    renderPage(<WeeklyCheckinCard weekPlan={null} onPlanUpdated={() => {}} />);
    act(() => {
      fireEvent.click(screen.getByText("Plan your week"));
    });
    await waitFor(() => expect(toast).toHaveBeenCalledWith(OFFLINE, expect.anything()));
    expect(pageCrashes).toEqual([]);
    expect(screen.queryByText("Something went wrong")).toBeNull();
    expect(screen.getByText("Plan your week")).toBeTruthy();
    // A failed open is not a dismissal: the card comes back for the next try.
    expect(readCheckinDismissed()).toBe("");
  });

  it("a second tap says it again (the sheet was unmounted, not left broken)", async () => {
    renderPage(<WeeklyCheckinCard weekPlan={null} onPlanUpdated={() => {}} />);
    act(() => {
      fireEvent.click(screen.getByText("Plan your week"));
    });
    await waitFor(() => expect(toast).toHaveBeenCalledTimes(1));
    act(() => {
      fireEvent.click(screen.getByText("Plan your week"));
    });
    await waitFor(() => expect(toast).toHaveBeenCalledTimes(2));
    expect(pageCrashes).toEqual([]);
  });
});

describe("SessionCard — the Add exercise chunk cannot load", () => {
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

  it("Add exercise toasts instead of crashing the page", async () => {
    renderPage(<SessionCard session={session} date="2026-10-18" weekPlan={weekPlan} sessionIndex={0} />);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Session actions" }));
    });
    act(() => {
      fireEvent.click(screen.getByText("Add exercise"));
    });
    await waitFor(() => expect(toast).toHaveBeenCalledWith(OFFLINE, expect.anything()));
    expect(pageCrashes).toEqual([]);
    expect(screen.queryByText("Something went wrong")).toBeNull();
    // The card is still there (its actions button), not the error page.
    expect(screen.getByRole("button", { name: "Session actions", hidden: true })).toBeTruthy();
  });
});
