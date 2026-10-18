/**
 * @vitest-environment jsdom
 *
 * B396 review — a session whose feedback is queued on the device.
 *
 * B397 keeps a failed "Submit & finish" in localStorage as
 * `submitStatus: "feedback_pending"` + `pendingFeedback`: the ONLY copy of that
 * feedback until the replay sends it. B396's card read it like any saved
 * progress — "Resume · n/n" on the button and "Discard saved progress" in the
 * actions sheet, which deleted feedback never sent. Now the card says "Waiting
 * to sync", offers no Discard, and Start only reopens the player's pending view
 * (never a fresh guided state over the queued one).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { router, toast } = vi.hoisted(() => ({
  router: { push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() },
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), dismiss: vi.fn() }),
}));

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true, isSignedIn: true }) }));
vi.mock("sonner", () => ({ toast }));
vi.mock("@/lib/api", () => ({
  removeExerciseFromSession: vi.fn(),
  setSessionSurface: vi.fn(),
  apiErrorDetail: vi.fn(),
}));

import { SessionCard } from "@/components/training/session-card";
import { readSavedProgress, resumeLabel } from "@/lib/guided-resume";
import { getInProgressSession, guidedStorageKey } from "@/lib/guided-session-utils";
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

const DATE = "2026-10-18";
const SESSION_ID = "strength_long";

function entry(
  statuses: string[],
  extra: Record<string, unknown> = {},
  currentIndex = statuses.length - 1,
): string {
  return JSON.stringify({
    version: 1,
    date: DATE,
    sessionId: SESSION_ID,
    sessionName: "Strength",
    startedAt: new Date().toISOString(),
    currentIndex,
    exercises: statuses.map((status, i) => ({ exerciseId: `ex_${i}`, status })),
    ...extra,
  });
}

const PENDING_BODY = { log_entry: { date: DATE, session_id: SESSION_ID }, status: "done" };
const pendingEntry = (statuses = ["done", "done"], currentIndex?: number) =>
  entry(statuses, { submitStatus: "feedback_pending", pendingFeedback: PENDING_BODY }, currentIndex);

const session = {
  session_id: SESSION_ID,
  slot: "evening",
  location: "gym",
  status: "planned",
  resolved: {
    resolved_session: {
      exercise_instances: [
        { exercise_id: "max_hang", name: "Max hang", prescription: { sets: 3 } },
        { exercise_id: "pull_up", name: "Pull up", prescription: { sets: 3 } },
      ],
    },
  },
} as unknown as SessionSlot;

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SessionCard session={session} date={DATE} onMove={() => {}} />
    </QueryClientProvider>,
  );
}

let key: string;

beforeEach(() => {
  Object.defineProperty(window, "localStorage", { value: new MemoryStorage(), configurable: true });
  (window as unknown as { Clerk: unknown }).Clerk = { loaded: true, user: { id: "user_1" } };
  window.matchMedia = ((q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  })) as unknown as typeof window.matchMedia;
  key = guidedStorageKey(DATE, SESSION_ID);
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
  delete (window as unknown as { Clerk?: unknown }).Clerk;
});

describe("readSavedProgress — a queued feedback is not progress to resume", () => {
  it("reports feedback_pending as pending, whatever the exercises say", () => {
    window.localStorage.setItem(key, pendingEntry());
    expect(readSavedProgress(window.localStorage, key)).toEqual({ completed: 2, total: 2, pending: true });
    // Even with nothing marked and the player on step 1: still the only copy.
    window.localStorage.setItem(key, pendingEntry(["pending", "pending"], 0));
    expect(readSavedProgress(window.localStorage, key)?.pending).toBe(true);
  });

  it("a completed session is nothing to show", () => {
    window.localStorage.setItem(key, entry(["done", "done"], { submitStatus: "completed" }));
    expect(readSavedProgress(window.localStorage, key)).toBeNull();
  });

  it("the label says the feedback is waiting, not 'Resume · 2/2'", () => {
    expect(resumeLabel({ completed: 2, total: 2, pending: true })).toBe("Waiting to sync");
    expect(resumeLabel({ completed: 1, total: 2 })).toBe("Resume · 1/2");
  });

  it("the /today resume banner (and its Discard) never picks up a queued session", () => {
    window.localStorage.setItem(key, pendingEntry(["done", "pending"], 1));
    expect(getInProgressSession()).toBeNull();
  });
});

describe("SessionCard — a session waiting to sync", () => {
  it("says 'Waiting to sync' on the start button", () => {
    window.localStorage.setItem(key, pendingEntry());
    renderCard();
    expect(screen.getByRole("button", { name: /Waiting to sync/ })).toBeTruthy();
    expect(screen.queryByText(/Resume ·/)).toBeNull();
  });

  it("offers no 'Discard saved progress' (it would delete the unsent feedback)", () => {
    window.localStorage.setItem(key, pendingEntry());
    renderCard();
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Session actions" }));
    });
    expect(screen.getByText("Move session")).toBeTruthy(); // the sheet is open
    expect(screen.queryByText("Discard saved progress")).toBeNull();
  });

  it("an ordinary in-progress session still resumes and can be discarded", () => {
    window.localStorage.setItem(key, entry(["done", "pending"], {}, 1));
    renderCard();
    expect(screen.getByRole("button", { name: /Resume · 1\/2/ })).toBeTruthy();
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Session actions" }));
    });
    expect(screen.getByText("Discard saved progress")).toBeTruthy();
  });

  it("Start opens the player's pending view and never overwrites the queued entry", () => {
    // Submitted from the summary with nothing marked: no "progress" by the
    // hasSavedProgress rule — Start used to write a fresh state over it.
    const queued = pendingEntry(["pending", "pending"], 0);
    window.localStorage.setItem(key, queued);
    renderCard();
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: /Waiting to sync/ }));
    });
    expect(router.push).toHaveBeenCalledWith(`/guided/${DATE}/${SESSION_ID}`);
    expect(window.localStorage.getItem(key)).toBe(queued);
  });
});
