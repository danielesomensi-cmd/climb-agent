/**
 * @vitest-environment jsdom
 *
 * B397 review — the guided player with the REAL useSubscription and the REAL
 * useUserState (only the API, Clerk's useAuth and the exercise card are stubbed).
 *
 * 1. Offline cold open (Clerk not loaded): useSubscription (B396) answers _DENY
 *    with loading:false at once. The paywall gate used to run before the saved
 *    session was loaded and sent a climber in the middle of a workout to
 *    /subscribe. The gate now runs only after the load, and only with Clerk.
 * 3. The page loads the session before Clerk (B397 G1): nothing may call
 *    /api/state before Clerk can sign it — a 401 there ends in the B155 hard
 *    redirect to /sign-in mid-workout.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createElement } from "react";
import { render, screen, cleanup, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { ApiError, router, auth, postFeedback, getState, getSubscriptionStatus, toast } = vi.hoisted(() => {
  class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  }
  const toast = Object.assign(vi.fn<(message: unknown, options?: unknown) => string>(() => "toast-id"), {
    success: vi.fn(),
    error: vi.fn(),
    dismiss: vi.fn(),
  });
  return {
    ApiError,
    router: { replace: vi.fn(), push: vi.fn() },
    auth: { current: { isLoaded: false, userId: undefined as string | null | undefined } },
    postFeedback: vi.fn(),
    getState: vi.fn(),
    getSubscriptionStatus: vi.fn(),
    toast,
  };
});

vi.mock("next/navigation", () => ({
  useParams: () => ({ date: "2026-10-18", sessionId: "strength_long" }),
  useRouter: () => router,
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth.current }));
vi.mock("sonner", () => ({ toast }));
vi.mock("@/lib/api", () => ({
  ApiError,
  postFeedback: (...a: unknown[]) => postFeedback(...a),
  getState: () => getState(),
  getSubscriptionStatus: () => getSubscriptionStatus(),
}));
vi.mock("@/lib/hooks/use-wake-lock", () => ({ useWakeLock: () => {} }));
vi.mock("@/lib/audio-unlock", () => ({
  unlockAudio: vi.fn(),
  getAudioContext: vi.fn(() => ({ state: "running", resume: vi.fn() })),
}));
vi.mock("@/components/guided/guided-exercise-step", () => ({
  GuidedExerciseStep: ({ exercise, bodyweightKg }: { exercise: { name: string }; bodyweightKg?: number }) =>
    createElement(
      "div",
      null,
      createElement("h2", { "data-testid": "exercise" }, exercise.name),
      createElement("span", { "data-testid": "bw" }, bodyweightKg ?? ""),
    ),
}));

import GuidedSessionPage from "@/app/(guided)/guided/[date]/[sessionId]/page";
import { queryKeys } from "@/lib/query-keys";

class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, v); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

const KEY_A = "guided_session_user_A_2026-10-18_strength_long";
const ACTIVE = { status: "active", is_active: true, trial_days_remaining: null, can_interact: true };
const EXPIRED = { status: "expired", is_active: false, trial_days_remaining: null, can_interact: false };

let storage: MemoryStorage;
let qc: QueryClient;

function ex(name: string, status = "pending", extra: Record<string, unknown> = {}) {
  return {
    exerciseId: name,
    name,
    category: "strength",
    blockUid: "main",
    loadModel: "bodyweight_only",
    prescription: {},
    suggested: {},
    status,
    feedbackLabel: null,
    ...extra,
  };
}

function saveSession(key: string, extra: Record<string, unknown> = {}) {
  storage.setItem(
    key,
    JSON.stringify({
      version: 1,
      date: "2026-10-18",
      sessionId: "strength_long",
      sessionName: "Strength",
      startedAt: new Date(Date.now() - 3600_000).toISOString(),
      currentIndex: 1,
      exercises: [ex("a", "done"), ex("b"), ex("c")],
      ...extra,
    }),
  );
}

/** Clerk state, both as `useAuth()` and as `window.Clerk` (read by the key). */
function clerk(state: "booting" | { userId: string | null }) {
  if (state === "booting") {
    auth.current = { isLoaded: false, userId: undefined };
    (window as unknown as { Clerk?: unknown }).Clerk = undefined;
  } else {
    auth.current = { isLoaded: true, userId: state.userId };
    (window as unknown as { Clerk?: unknown }).Clerk = state.userId
      ? { session: {}, user: { id: state.userId }, loaded: true }
      : { session: null, user: null, loaded: true };
  }
}

function setOnline(value: boolean) {
  Object.defineProperty(navigator, "onLine", { configurable: true, value });
}

function page() {
  return createElement(QueryClientProvider, { client: qc }, createElement(GuidedSessionPage));
}

const shownExercise = () => screen.queryByTestId("exercise")?.textContent ?? null;
const sentToSubscribe = () => router.replace.mock.calls.some((c) => c[0] === "/subscribe");

/** Let pending promises (query results) settle. */
async function settle() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
}

beforeEach(() => {
  storage = new MemoryStorage();
  Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
  vi.stubGlobal("localStorage", storage);
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
  setOnline(true);
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  router.replace.mockReset();
  postFeedback.mockReset();
  getState.mockReset();
  getState.mockResolvedValue({});
  getSubscriptionStatus.mockReset();
  getSubscriptionStatus.mockResolvedValue(ACTIVE);
  toast.mockClear();
  clerk({ userId: "user_A" });
});

afterEach(() => {
  cleanup();
  setOnline(true);
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// 1 — the paywall gate never beats the saved session, and never fires without Clerk
// ---------------------------------------------------------------------------

describe("B397 review — subscription gate with the real useSubscription", () => {
  it("offline cold open, Clerk not loaded: the saved session is on screen, no /subscribe", async () => {
    setOnline(false);
    clerk("booting");
    storage.setItem("climb-agent-last-user", "user_A");
    saveSession(KEY_A);

    render(page());
    await settle();

    expect(shownExercise()).toBe("b");
    expect(sentToSubscribe()).toBe(false);
    expect(router.replace).not.toHaveBeenCalled();
    // B396: nothing asked the server without a token.
    expect(getSubscriptionStatus).not.toHaveBeenCalled();
  });

  it("...and when Clerk then loads while still offline (the request fails), the session stays", async () => {
    setOnline(false);
    clerk("booting");
    storage.setItem("climb-agent-last-user", "user_A");
    saveSession(KEY_A);
    getSubscriptionStatus.mockRejectedValue(new ApiError(0, "Network too slow"));

    const { rerender } = render(page());
    clerk({ userId: "user_A" });
    rerender(page());
    await waitFor(() => expect(getSubscriptionStatus).toHaveBeenCalled());
    await settle();

    expect(shownExercise()).toBe("b");
    expect(sentToSubscribe()).toBe(false);
  });

  it("offline, Clerk not loaded, nothing to resume: back to /today, never /subscribe for a missing answer", async () => {
    setOnline(false);
    clerk("booting");

    render(page());
    await settle();

    expect(router.replace).toHaveBeenCalledWith("/today?date=2026-10-18");
    expect(sentToSubscribe()).toBe(false);
  });

  it("deny already in the cache when the session loads (same commit): no /subscribe", () => {
    qc.setQueryData(queryKeys.subscriptionStatus, EXPIRED);
    getSubscriptionStatus.mockResolvedValue(EXPIRED);
    saveSession(KEY_A);

    render(page());

    expect(shownExercise()).toBe("b");
    expect(sentToSubscribe()).toBe(false);
  });

  it("Clerk loaded and a real deny, but a session is under way: no /subscribe (A245 C-1)", async () => {
    getSubscriptionStatus.mockResolvedValue(EXPIRED);
    saveSession(KEY_A);

    render(page());
    await waitFor(() => expect(getSubscriptionStatus).toHaveBeenCalled());
    await settle();

    expect(shownExercise()).toBe("b");
    expect(sentToSubscribe()).toBe(false);
  });

  it("cold hit on the URL with no saved session, Clerk loaded, subscription denied: /subscribe", async () => {
    getSubscriptionStatus.mockResolvedValue(EXPIRED);

    render(page());

    await waitFor(() => expect(router.replace).toHaveBeenLastCalledWith("/subscribe"));
  });

  it("cold hit, Clerk loaded, subscription already denied in the cache: /subscribe is the last word", () => {
    qc.setQueryData(queryKeys.subscriptionStatus, EXPIRED);
    getSubscriptionStatus.mockResolvedValue(EXPIRED);

    render(page());

    expect(router.replace).toHaveBeenLastCalledWith("/subscribe");
  });
});

// ---------------------------------------------------------------------------
// 3 — no /api/state GET before Clerk
// ---------------------------------------------------------------------------

describe("B397 review — /api/state waits for Clerk", () => {
  it("HR-target session: useUserState does not fetch before Clerk, and does once Clerk is ready", async () => {
    clerk("booting");
    storage.setItem("climb-agent-last-user", "user_A");
    saveSession(KEY_A, {
      exercises: [ex("a", "done"), ex("b", "pending", { hrTarget: { work_pct: [90, 95] } }), ex("c")],
    });

    const { rerender } = render(page());
    await settle();
    expect(shownExercise()).toBe("b");
    expect(getState).not.toHaveBeenCalled();

    clerk({ userId: "user_A" });
    rerender(page());
    await waitFor(() => expect(getState).toHaveBeenCalledTimes(1));
  });

  it("test session body weight: the GET fallback waits for Clerk, then fills the weight", async () => {
    clerk("booting");
    storage.setItem("climb-agent-last-user", "user_A");
    getState.mockResolvedValue({ assessment: { body: { weight_kg: 70 } } });
    saveSession(KEY_A, { isTestSession: true });

    const { rerender } = render(page());
    await settle();
    expect(shownExercise()).toBe("b");
    expect(getState).not.toHaveBeenCalled();
    expect(screen.getByTestId("bw").textContent).toBe("");

    clerk({ userId: "user_A" });
    rerender(page());

    await waitFor(() => expect(screen.getByTestId("bw").textContent).toBe("70"));
    expect(getState).toHaveBeenCalledTimes(1);
  });

  it("the ['state'] cache stays the first source: filled after the load, it is used with no GET", async () => {
    clerk("booting");
    storage.setItem("climb-agent-last-user", "user_A");
    saveSession(KEY_A, { isTestSession: true });

    const { rerender } = render(page());
    await settle();
    expect(screen.getByTestId("bw").textContent).toBe("");

    // e.g. the persisted cache finished restoring after the session was read.
    qc.setQueryData(queryKeys.state, { assessment: { body: { weight_kg: 68 } } });
    clerk({ userId: "user_A" });
    rerender(page());

    await waitFor(() => expect(screen.getByTestId("bw").textContent).toBe("68"));
    expect(getState).not.toHaveBeenCalled();
  });
});
