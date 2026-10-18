/**
 * @vitest-environment jsdom
 *
 * B397 review (round 2) — "Start session" on /today is the paywall's entry
 * point (B202). After the first review moved the guided gate behind the
 * session load, a session Start had just written counted as "under way" and an
 * expired account trained a whole session, then hit a 402 at Submit.
 *
 * A NEW session is blocked again, but only on the server's own "no"
 * (`can_interact: false` in the cache, or a 402/403): a missing answer —
 * offline at the crag, Clerk booting, a timeout — must never send a paying
 * climber to /subscribe. Resume and the queued-feedback view are never blocked.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, onlineManager } from "@tanstack/react-query";

const { router, toast, ApiError, getSubscriptionStatus } = vi.hoisted(() => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  }
  return {
    router: { push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() },
    toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), dismiss: vi.fn() }),
    ApiError,
    getSubscriptionStatus: vi.fn(),
  };
});

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true, isSignedIn: true }) }));
vi.mock("sonner", () => ({ toast }));
vi.mock("@/lib/api", () => ({
  ApiError,
  getSubscriptionStatus: () => getSubscriptionStatus(),
  removeExerciseFromSession: vi.fn(),
  setSessionSurface: vi.fn(),
  apiErrorDetail: vi.fn(),
}));

import { SessionCard } from "@/components/training/session-card";
import { guidedStorageKey } from "@/lib/guided-session-utils";
import { isServerDenied } from "@/lib/hooks/use-subscription";
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

const DATE = "2026-10-18";
const SESSION_ID = "strength_long";
const ACTIVE = { status: "active", is_active: true, trial_days_remaining: null, can_interact: true };
const EXPIRED = { status: "expired", is_active: false, trial_days_remaining: null, can_interact: false };

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

let qc: QueryClient;
let key: string;

function renderCard() {
  return render(
    <QueryClientProvider client={qc}>
      <SessionCard session={session} date={DATE} onMove={() => {}} />
    </QueryClientProvider>,
  );
}

function tapStart(name: RegExp = /Start session/) {
  act(() => {
    fireEvent.click(screen.getByRole("button", { name }));
  });
}

/** Put a refused subscription request in the cache, as a failed fetch leaves it. */
async function cacheSubscriptionError(err: unknown) {
  await qc
    .fetchQuery({ queryKey: queryKeys.subscriptionStatus, queryFn: () => Promise.reject(err), retry: false })
    .catch(() => {});
}

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
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  key = guidedStorageKey(DATE, SESSION_ID);
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
  delete (window as unknown as { Clerk?: unknown }).Clerk;
});

describe("isServerDenied — a ruling, never a missing answer", () => {
  it("is true only for can_interact:false or a 402/403", () => {
    expect(isServerDenied(EXPIRED as never, null)).toBe(true);
    expect(isServerDenied(ACTIVE as never, null)).toBe(false);
    expect(isServerDenied(undefined, null)).toBe(false);
    expect(isServerDenied(undefined, new ApiError(402, "x"))).toBe(true);
    expect(isServerDenied(ACTIVE as never, new ApiError(403, "x"))).toBe(true);
    // Transport failures and 401 (api.ts handles it with /sign-in) are not rulings.
    expect(isServerDenied(undefined, new ApiError(0, "Network too slow"))).toBe(false);
    expect(isServerDenied(undefined, new ApiError(401, "x"))).toBe(false);
    expect(isServerDenied(undefined, new Error("offline"))).toBe(false);
  });
});

describe("SessionCard Start — the paywall entry point", () => {
  it("a new session with the server's 'no' in the cache, confirmed by a fresh answer: /subscribe, nothing written", async () => {
    qc.setQueryData(queryKeys.subscriptionStatus, EXPIRED);
    getSubscriptionStatus.mockResolvedValue(EXPIRED);
    renderCard();
    tapStart();
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/subscribe"));
    expect(getSubscriptionStatus).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem(key)).toBeNull();
  });

  it("a new session refused with a 402, confirmed: /subscribe", async () => {
    await cacheSubscriptionError(new ApiError(402, "Payment required"));
    getSubscriptionStatus.mockRejectedValue(new ApiError(402, "Payment required"));
    renderCard();
    tapStart();
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/subscribe"));
    expect(window.localStorage.getItem(key)).toBeNull();
  });

  // Review round 3 — someone who has just paid must not bounce off the old "no".
  it("a cached 'no' that the fresh answer turns into a 'yes': Start opens the player", async () => {
    qc.setQueryData(queryKeys.subscriptionStatus, EXPIRED);
    getSubscriptionStatus.mockResolvedValue(ACTIVE);
    renderCard();
    tapStart();
    await waitFor(() => expect(router.push).toHaveBeenCalledWith(`/guided/${DATE}/${SESSION_ID}`));
    expect(router.push).not.toHaveBeenCalledWith("/subscribe");
    expect(window.localStorage.getItem(key)).not.toBeNull();
  });

  it("a cached 'no' and the confirmation fails in transport: the last ruling stands (/subscribe)", async () => {
    qc.setQueryData(queryKeys.subscriptionStatus, EXPIRED);
    getSubscriptionStatus.mockRejectedValue(new ApiError(0, "Network too slow"));
    renderCard();
    tapStart();
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/subscribe"));
  });

  it("a session with sets counted on the first exercise is a session under way: Resume · 0/2, never /subscribe", () => {
    qc.setQueryData(queryKeys.subscriptionStatus, EXPIRED);
    const saved = JSON.stringify({
      version: 1, date: DATE, sessionId: SESSION_ID, sessionName: "Strength",
      startedAt: new Date().toISOString(), currentIndex: 0,
      exercises: [{ exerciseId: "max_hang", status: "pending", completedSets: 2 }, { exerciseId: "pull_up", status: "pending" }],
    });
    window.localStorage.setItem(key, saved);
    renderCard();
    tapStart(/Resume · 0\/2/);
    expect(router.push).toHaveBeenCalledWith(`/guided/${DATE}/${SESSION_ID}`);
    expect(getSubscriptionStatus).not.toHaveBeenCalled();
    expect(window.localStorage.getItem(key)).toBe(saved);
  });

  it("no answer at all (offline, Clerk booting): Start opens the player", () => {
    renderCard();
    tapStart();
    expect(router.push).toHaveBeenCalledWith(`/guided/${DATE}/${SESSION_ID}`);
    expect(router.push).not.toHaveBeenCalledWith("/subscribe");
    expect(window.localStorage.getItem(key)).not.toBeNull();
  });

  it("a transport failure before any answer: Start opens the player", async () => {
    await cacheSubscriptionError(new ApiError(0, "Network too slow"));
    renderCard();
    tapStart();
    expect(router.push).toHaveBeenCalledWith(`/guided/${DATE}/${SESSION_ID}`);
  });

  it("an active subscription: Start opens the player", () => {
    qc.setQueryData(queryKeys.subscriptionStatus, ACTIVE);
    renderCard();
    tapStart();
    expect(router.push).toHaveBeenCalledWith(`/guided/${DATE}/${SESSION_ID}`);
  });

  it("a session under way still resumes, even with the server's 'no' (A245 C-1)", () => {
    qc.setQueryData(queryKeys.subscriptionStatus, EXPIRED);
    const saved = JSON.stringify({
      version: 1, date: DATE, sessionId: SESSION_ID, sessionName: "Strength",
      startedAt: new Date().toISOString(), currentIndex: 1,
      exercises: [{ exerciseId: "max_hang", status: "done" }, { exerciseId: "pull_up", status: "pending" }],
    });
    window.localStorage.setItem(key, saved);
    renderCard();
    tapStart(/Resume · 1\/2/);
    expect(router.push).toHaveBeenCalledWith(`/guided/${DATE}/${SESSION_ID}`);
    expect(window.localStorage.getItem(key)).toBe(saved);
  });

  it("queued feedback still opens the pending view, even with the server's 'no'", () => {
    qc.setQueryData(queryKeys.subscriptionStatus, EXPIRED);
    const queued = JSON.stringify({
      version: 1, date: DATE, sessionId: SESSION_ID, sessionName: "Strength",
      startedAt: new Date().toISOString(), currentIndex: 1,
      exercises: [{ exerciseId: "max_hang", status: "done" }, { exerciseId: "pull_up", status: "done" }],
      submitStatus: "feedback_pending", pendingFeedback: { status: "done" },
    });
    window.localStorage.setItem(key, queued);
    renderCard();
    tapStart(/Waiting to sync/);
    expect(router.push).toHaveBeenCalledWith(`/guided/${DATE}/${SESSION_ID}`);
    expect(window.localStorage.getItem(key)).toBe(queued);
  });

  // Review round 4 — a check that answers after the tap is over must not navigate.
  it("the card goes away before the confirmation answers: no late navigation", async () => {
    qc.setQueryData(queryKeys.subscriptionStatus, EXPIRED);
    let answer!: (v: typeof EXPIRED) => void;
    getSubscriptionStatus.mockReturnValue(new Promise((r) => { answer = r; }));
    const { unmount } = renderCard();
    tapStart();
    unmount();
    await act(async () => { answer(EXPIRED); });
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
    expect(router.push).not.toHaveBeenCalled();
  });

  it("offline with the server's 'no' in the cache: decided at once on that ruling, no paused request", async () => {
    qc.setQueryData(queryKeys.subscriptionStatus, EXPIRED);
    onlineManager.setOnline(false);
    try {
      renderCard();
      tapStart();
      await waitFor(() => expect(router.push).toHaveBeenCalledWith("/subscribe"));
      expect(getSubscriptionStatus).not.toHaveBeenCalled();
    } finally {
      onlineManager.setOnline(true);
    }
  });
});
