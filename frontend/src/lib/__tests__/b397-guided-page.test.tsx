/**
 * @vitest-environment jsdom
 *
 * B397 — the guided player, rendered for real (only the exercise card is a
 * stub): resume without Clerk, never across users, one submit, reversible
 * Done/Skip, a confirmed "Finish early", a summary you can leave, and a queued
 * session that cannot be submitted twice.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createElement } from "react";
import { render, screen, cleanup, act, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { ApiError, router, auth, postFeedback, getState, toast } = vi.hoisted(() => {
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
}));
vi.mock("@/lib/hooks/use-subscription", () => ({
  useSubscription: () => ({ canInteract: true, loading: false }),
}));
vi.mock("@/lib/hooks/use-wake-lock", () => ({ useWakeLock: () => {} }));
vi.mock("@/lib/hooks/use-state", () => ({ useUserState: () => ({ state: null }) }));
vi.mock("@/lib/audio-unlock", () => ({
  unlockAudio: vi.fn(),
  getAudioContext: vi.fn(() => ({ state: "running", resume: vi.fn() })),
}));
vi.mock("@/components/guided/guided-exercise-step", () => ({
  GuidedExerciseStep: ({
    exercise,
    bodyweightKg,
    onDone,
    onSkip,
  }: {
    exercise: { name: string };
    bodyweightKg?: number;
    onDone: (label: string | null) => void;
    onSkip: () => void;
  }) =>
    createElement(
      "div",
      null,
      createElement("h2", { "data-testid": "exercise" }, exercise.name),
      createElement("span", { "data-testid": "bw" }, bodyweightKg ?? ""),
      createElement("button", { onClick: () => onDone("ok") }, "Done"),
      createElement("button", { onClick: () => onSkip() }, "Skip"),
    ),
}));

import GuidedSessionPage from "@/app/(guided)/guided/[date]/[sessionId]/page";

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
const KEY_B = "guided_session_user_B_2026-10-18_strength_long";

let storage: MemoryStorage;
let qc: QueryClient;

function ex(name: string, status = "pending") {
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
      currentIndex: 0,
      exercises: [ex("a"), ex("b"), ex("c")],
      ...extra,
    }),
  );
}

const stored = (key: string) => JSON.parse(storage.getItem(key) ?? "null");

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

function page() {
  return createElement(QueryClientProvider, { client: qc }, createElement(GuidedSessionPage));
}

const shownExercise = () => screen.queryByTestId("exercise")?.textContent ?? null;

/** The options sonner received for the last toast whose message matches. */
function lastToast(match: RegExp) {
  const call = [...toast.mock.calls].reverse().find((c) => match.test(String(c[0])));
  return call?.[1] as { action?: { label: string; onClick: () => void } } | undefined;
}

beforeEach(() => {
  storage = new MemoryStorage();
  Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
  vi.stubGlobal("localStorage", storage);
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  router.replace.mockReset();
  postFeedback.mockReset();
  getState.mockReset();
  toast.mockClear();
  toast.dismiss.mockClear();
  clerk({ userId: "user_A" });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// G1 — resume without Clerk, never across users
// ---------------------------------------------------------------------------

describe("G1 — reload mid-session", () => {
  it("resumes before Clerk is ready, from the user remembered on this device", () => {
    saveSession(KEY_A, { currentIndex: 1, exercises: [ex("a", "done"), ex("b"), ex("c")] });
    storage.setItem("climb-agent-last-user", "user_A");
    clerk("booting");

    const { rerender } = render(page());

    expect(shownExercise()).toBe("b");
    expect(router.replace).not.toHaveBeenCalled();

    // Clerk answers: same user, the session stays.
    clerk({ userId: "user_A" });
    rerender(page());
    expect(shownExercise()).toBe("b");
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("drops the session from the screen when Clerk then names ANOTHER user", () => {
    saveSession(KEY_A, { currentIndex: 1, exercises: [ex("a", "done"), ex("b"), ex("c")] });
    storage.setItem("climb-agent-last-user", "user_A");
    clerk("booting");

    const { rerender } = render(page());
    expect(shownExercise()).toBe("b");

    clerk({ userId: "user_B" });
    rerender(page());

    expect(shownExercise()).toBeNull();
    expect(router.replace).toHaveBeenCalledWith("/today?date=2026-10-18");
    // A's data stays A's, and nothing was copied into B's scope.
    expect(stored(KEY_A).currentIndex).toBe(1);
    expect(storage.getItem(KEY_B)).toBeNull();
  });

  it("with no remembered user, waits for Clerk instead of bouncing to /today", () => {
    saveSession(KEY_A);
    clerk("booting");

    const { rerender } = render(page());
    expect(router.replace).not.toHaveBeenCalled();

    clerk({ userId: "user_A" });
    rerender(page());

    expect(shownExercise()).toBe("a");
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("offline with nothing to resume, goes back to /today at once", () => {
    clerk("booting");
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });

    render(page());

    expect(router.replace).toHaveBeenCalledWith("/today?date=2026-10-18");
  });
});

// ---------------------------------------------------------------------------
// G5 — Done / Skip
// ---------------------------------------------------------------------------

describe("G5 — reversible Done / Skip", () => {
  it("Undo of Done brings the exercise back as it was", async () => {
    saveSession(KEY_A);
    render(page());

    fireEvent.click(screen.getByText("Done"));
    expect(shownExercise()).toBe("b");
    expect(stored(KEY_A).exercises[0].status).toBe("done");

    const options = lastToast(/^Done: a$/);
    expect(options?.action?.label).toBe("Undo");
    act(() => options!.action!.onClick());

    expect(shownExercise()).toBe("a");
    await waitFor(() => expect(stored(KEY_A).exercises[0].status).toBe("pending"));
    expect(stored(KEY_A).currentIndex).toBe(0);
  });

  it("Undo of Skip restores the skipped exercise", async () => {
    saveSession(KEY_A);
    render(page());

    fireEvent.click(screen.getByText("Skip"));
    expect(shownExercise()).toBe("b");

    act(() => lastToast(/^Skipped: a$/)!.action!.onClick());

    expect(shownExercise()).toBe("a");
    await waitFor(() => expect(stored(KEY_A).exercises[0].status).toBe("pending"));
  });

  it("a double tap on Done closes ONE exercise, not the next one too", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-18T10:00:00Z"));
    saveSession(KEY_A);
    render(page());

    fireEvent.click(screen.getByText("Done")); // closes a
    vi.setSystemTime(new Date("2026-10-18T10:00:00.180Z"));
    fireEvent.click(screen.getByText("Done")); // lands on b's fresh card

    expect(shownExercise()).toBe("b");
    expect(stored(KEY_A).exercises[1].status).toBe("pending");

    // A deliberate tap a moment later goes through.
    vi.setSystemTime(new Date("2026-10-18T10:00:01.500Z"));
    fireEvent.click(screen.getByText("Done"));
    expect(shownExercise()).toBe("c");
  });
});

// ---------------------------------------------------------------------------
// G6 — Finish early asks first; the summary is not a dead end
// ---------------------------------------------------------------------------

describe("G6 — finish early and the summary", () => {
  it("Finish early asks first, and Keep going stays in the session", () => {
    saveSession(KEY_A);
    render(page());

    fireEvent.click(screen.getByText("Finish session early"));
    expect(screen.queryByText("Submit & finish")).toBeNull();
    expect(screen.getByText(/End the session now\?/)).toBeTruthy();

    fireEvent.click(screen.getByText("Keep going"));
    expect(shownExercise()).toBe("a");

    fireEvent.click(screen.getByText("Finish session early"));
    fireEvent.click(screen.getByText("Finish now"));
    expect(screen.getByText("Submit & finish")).toBeTruthy();
  });

  it("from the summary: back to the first exercise left, or straight to one row", () => {
    saveSession(KEY_A, { exercises: [ex("a", "done"), ex("b"), ex("c", "done")] });
    render(page());
    fireEvent.click(screen.getByText("Finish session early"));
    fireEvent.click(screen.getByText("Finish now"));

    fireEvent.click(screen.getByText("Back to exercises"));
    expect(shownExercise()).toBe("b");

    fireEvent.click(screen.getByText("Finish session early"));
    fireEvent.click(screen.getByText("Finish now"));
    fireEvent.click(screen.getByRole("button", { name: "Change c" }));
    expect(shownExercise()).toBe("c");
  });

  // B397 review — Done after "Change" used to land on the next exercise,
  // already closed, instead of going back to the summary.
  it("Change a → Done → back on the summary, and Undo still reopens a as it was", async () => {
    saveSession(KEY_A, { exercises: [ex("a", "done"), ex("b", "done"), ex("c", "skipped")] });
    render(page());
    expect(screen.getByText("Submit & finish")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Change a" }));
    expect(shownExercise()).toBe("a");

    fireEvent.click(screen.getByText("Done"));
    expect(shownExercise()).toBeNull();
    expect(screen.getByText("Submit & finish")).toBeTruthy();
    await waitFor(() => expect(stored(KEY_A).exercises[0].feedbackLabel).toBe("ok"));
    // b was not touched by a second Done.
    expect(stored(KEY_A).exercises[1]).toMatchObject({ status: "done", feedbackLabel: null });

    act(() => lastToast(/^Done: a$/)!.action!.onClick());
    expect(shownExercise()).toBe("a");
    await waitFor(() => expect(stored(KEY_A).exercises[0].feedbackLabel).toBeNull());
    expect(stored(KEY_A).currentIndex).toBe(0);
  });

  it("Change a → Skip with c still pending → straight to c, over the closed b", () => {
    saveSession(KEY_A, { exercises: [ex("a", "done"), ex("b", "done"), ex("c")] });
    render(page());
    fireEvent.click(screen.getByText("Finish session early"));
    fireEvent.click(screen.getByText("Finish now"));

    fireEvent.click(screen.getByRole("button", { name: "Change a" }));
    fireEvent.click(screen.getByText("Skip"));
    expect(shownExercise()).toBe("c");
    expect(stored(KEY_A).exercises[1]).toMatchObject({ status: "done", feedbackLabel: null });
  });
});

// ---------------------------------------------------------------------------
// G2 / G3 — one submit; a queued session cannot be submitted again
// ---------------------------------------------------------------------------

describe("G2 — Submit & finish", () => {
  function allDone() {
    saveSession(KEY_A, { exercises: [ex("a", "done"), ex("b", "done")] });
  }

  it("a double tap sends ONE feedback", async () => {
    allDone();
    let release!: (v: unknown) => void;
    postFeedback.mockReturnValue(new Promise((r) => (release = r)));
    render(page());

    const submit = screen.getByText("Submit & finish");
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(postFeedback).toHaveBeenCalledTimes(1);

    await act(async () => release({ status: "ok", week_plan: null }));
    // A tap between the response and the route change does not resend either.
    fireEvent.click(screen.getByRole("button", { name: /Submit/ }));
    expect(postFeedback).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/today?date=2026-10-18"));
    expect(storage.getItem(KEY_A)).toBeNull();
  });

  it("offline: keeps the exact body, duration included, for the replay", async () => {
    allDone();
    postFeedback.mockRejectedValue(new ApiError(0, "Network too slow"));
    render(page());

    await act(async () => {
      fireEvent.click(screen.getByText("Submit & finish"));
    });

    await waitFor(() => expect(router.replace).toHaveBeenCalled());
    const saved = stored(KEY_A);
    expect(saved.submitStatus).toBe("feedback_pending");
    const duration = saved.pendingFeedback.log_entry.session_duration_seconds;
    expect(duration).toBeGreaterThanOrEqual(3599);
    expect(duration).toBeLessThan(3700);
    expect(toast).toHaveBeenCalledWith(
      "Session saved on this device — it will sync when you're back online.",
      expect.anything(),
    );
  });
});

describe("G3 — Start on a session whose feedback is queued", () => {
  it("shows where the feedback is, with no second Submit", () => {
    saveSession(KEY_A, {
      exercises: [ex("a", "done"), ex("b", "done")],
      submitStatus: "feedback_pending",
    });
    render(page());

    expect(screen.getByText("Session saved on this device")).toBeTruthy();
    expect(screen.queryByText("Submit & finish")).toBeNull();
    expect(screen.getByText("Send now")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// G7 — body weight from the cache
// ---------------------------------------------------------------------------

describe("G7 — test sessions' body weight", () => {
  it("comes from the ['state'] cache, with no GET", () => {
    qc.setQueryData(["state"], { assessment: { body: { weight_kg: 68 } } });
    saveSession(KEY_A, { isTestSession: true });
    render(page());

    expect(screen.getByTestId("bw").textContent).toBe("68");
    expect(getState).not.toHaveBeenCalled();
  });

  it("falls back to the GET only when the cache does not have it", async () => {
    getState.mockResolvedValue({ assessment: { body: { weight_kg: 70 } } });
    saveSession(KEY_A, { isTestSession: true });
    render(page());

    expect(getState).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.getByTestId("bw").textContent).toBe("70"));
  });
});
