/**
 * @vitest-environment jsdom
 *
 * B414 (INBOX-2026-11-04-ORPHAN) — the player when the server refuses the
 * feedback because the session is no longer on that day of the plan. Before,
 * any failure became «saved on this device, it will sync later» — for an
 * orphan that meant a feedback stuck forever (or, before the server check,
 * an orphan completion). Now the player keeps the exact body «to decide» and
 * shows the choices (Daniele, decision 4f): «Log it in place of X», «as an
 * extra» only with a free slot, «Discard» with a confirmation. Errors are
 * always shown; nothing pretends to be saved.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createElement } from "react";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { router, toast, postFeedback, OrphanError, orphan, sync } = vi.hoisted(() => {
  const toast = Object.assign(vi.fn<(message: unknown, options?: unknown) => string>(() => "toast-id"), {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    dismiss: vi.fn(),
  });
  class OrphanError extends Error {
    code = "session_not_in_plan";
    status = 409;
    date = "2026-11-04";
    sessionId = "treadmill_hiit_4x4";
    daySessions = null;
  }
  return {
    router: { replace: vi.fn(), push: vi.fn() },
    toast,
    postFeedback: vi.fn<(body: unknown) => Promise<unknown>>(),
    OrphanError,
    orphan: {
      loadDayFromServer: vi.fn<(...a: unknown[]) => Promise<unknown>>(),
      placeOrphanSession: vi.fn<(...a: unknown[]) => Promise<void>>(),
    },
    sync: vi.fn<(...a: unknown[]) => Promise<unknown>>(),
  };
});

vi.mock("next/navigation", () => ({
  useParams: () => ({ date: "2026-11-04", sessionId: "treadmill_hiit_4x4" }),
  useRouter: () => router,
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true, userId: "user_A" }) }));
vi.mock("sonner", () => ({ toast }));
vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  postFeedback: (body: unknown) => postFeedback(body),
  getState: vi.fn(),
  apiErrorDetail: (_e: unknown, fallback: string) => fallback,
}));
vi.mock("@/lib/orphan-session", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/orphan-session")>();
  return {
    ...real,
    loadDayFromServer: (...a: unknown[]) => orphan.loadDayFromServer(...a),
    placeOrphanSession: (...a: unknown[]) => orphan.placeOrphanSession(...a),
  };
});
vi.mock("@/lib/guided-pending-feedback", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/guided-pending-feedback")>();
  return { ...real, syncPendingGuidedFeedback: (...a: unknown[]) => sync(...a) };
});
vi.mock("@/lib/hooks/use-subscription", () => ({
  useSubscription: () => ({ canInteract: true, loading: false }),
  useServerRuling: () => "unknown",
  readServerRuling: () => "unknown",
}));
vi.mock("@/lib/hooks/use-wake-lock", () => ({ useWakeLock: () => {} }));
vi.mock("@/lib/hooks/use-state", () => ({ useUserState: () => ({ state: null }) }));
vi.mock("@/lib/audio-unlock", () => ({
  unlockAudio: vi.fn(),
  getAudioContext: vi.fn(() => ({ state: "running", resume: vi.fn() })),
}));
vi.mock("@/components/guided/guided-exercise-step", () => ({
  GuidedExerciseStep: ({ exercise }: { exercise: { name: string } }) =>
    createElement("h2", { "data-testid": "exercise" }, exercise.name),
}));

import GuidedSessionPage from "@/app/(guided)/guided/[date]/[sessionId]/page";
import { OrphanSessionBox } from "@/components/guided/orphan-session-box";

class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, v); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

const KEY = "guided_session_user_A_2026-11-04_treadmill_hiit_4x4";
let storage: MemoryStorage;
const stored = () => JSON.parse(storage.getItem(KEY) ?? "null");

const CUSTOM = { session_id: "custom_cs_320de282", slot: "lunch", status: "planned", location: "home", name: "VO2 max" };
const dayWith = (sessions: unknown[]) => ({
  weekNum: 0,
  weekPlan: { weeks: [{ days: [{ date: "2026-11-04", sessions }] }] },
  day: { date: "2026-11-04", sessions },
});

async function flush() {
  for (let i = 0; i < 6; i++) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

function renderPage() {
  return render(createElement(QueryClientProvider, { client: new QueryClient() }, createElement(GuidedSessionPage)));
}

function renderBox(sessionId = "treadmill_hiit_4x4", onDone = vi.fn()) {
  render(
    createElement(
      QueryClientProvider,
      { client: new QueryClient() },
      createElement(OrphanSessionBox, { date: "2026-11-04", sessionId, sessionName: "Treadmill HIIT", storageKey: KEY, onDone }),
    ),
  );
  return onDone;
}

beforeEach(() => {
  storage = new MemoryStorage();
  Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
  vi.stubGlobal("localStorage", storage);
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  (window as unknown as { Clerk?: unknown }).Clerk = { session: {}, user: { id: "user_A" }, loaded: true };
  vi.spyOn(console, "error").mockImplementation(() => {});
  router.replace.mockClear();
  toast.mockClear();
  postFeedback.mockReset();
  orphan.loadDayFromServer.mockReset();
  orphan.placeOrphanSession.mockReset();
  sync.mockReset();
  storage.setItem(
    KEY,
    JSON.stringify({
      version: 1,
      date: "2026-11-04",
      sessionId: "treadmill_hiit_4x4",
      sessionName: "Treadmill HIIT",
      startedAt: "2026-11-04T11:28:57.000Z",
      currentIndex: 0,
      exercises: [
        {
          exerciseId: "treadmill_intervals",
          name: "Intervals",
          category: "cardio",
          blockUid: "main",
          loadModel: "bodyweight_only",
          prescription: { sets: 4 },
          suggested: {},
          status: "done",
          feedbackLabel: "hard",
        },
      ],
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("B414 — the player and a session no longer in the plan", () => {
  it("Submit refused → kept «to decide» with the exact body, the choices on screen, no fake save", async () => {
    postFeedback.mockRejectedValue(new OrphanError("not in plan"));
    orphan.loadDayFromServer.mockResolvedValue(dayWith([CUSTOM]));
    renderPage();
    expect(screen.getByText("Session complete")).toBeTruthy();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /submit & finish/i }));
    });
    await flush();

    const saved = stored();
    expect(saved.submitStatus).toBe("feedback_pending");
    expect(saved.orphan).toBeTruthy();
    expect(saved.pendingFeedback).toEqual(postFeedback.mock.calls[0][0]);
    // Not the offline message, not a redirect.
    expect(toast).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
    expect(screen.getByText("This session is no longer in your plan")).toBeTruthy();
    expect(screen.getByRole("button", { name: /log it in place of vo2 max · lunch/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /log it as an extra \(evening\)/i })).toBeTruthy();
  });

  it("«in place of X»: places it, sends the saved feedback, back to Today", async () => {
    storage.setItem(KEY, JSON.stringify({ ...stored(), submitStatus: "feedback_pending", orphan: { detectedAt: "x" } }));
    orphan.loadDayFromServer.mockResolvedValue(dayWith([CUSTOM]));
    orphan.placeOrphanSession.mockResolvedValue(undefined);
    sync.mockImplementation(async () => {
      storage.removeItem(KEY); // the replay sent it
      return { sent: 1, alreadySaved: 0, rejected: 0, failed: 0, undecided: 0 };
    });
    renderPage();
    await flush();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /log it in place of vo2 max/i }));
    });
    await flush();

    expect(orphan.placeOrphanSession).toHaveBeenCalledTimes(1);
    const placement = orphan.placeOrphanSession.mock.calls[0][4] as { kind: string; target: { session_id: string } };
    expect(placement.kind).toBe("replace");
    expect(placement.target.session_id).toBe("custom_cs_320de282");
    expect(sync).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith("/today?date=2026-11-04");
  });

  // B414 review: «Send now» in the plain pending view (an offline submit) whose
  // replay is refused because the session left the plan in the meantime. The
  // replay marks the entry «to decide» and never re-sends it on its own, so
  // «it will go out when the connection is back» would be false: the choices
  // come up instead.
  it("«Send now» refused as an orphan → the choices, never «it will go out later»", async () => {
    storage.setItem(KEY, JSON.stringify({ ...stored(), submitStatus: "feedback_pending" }));
    orphan.loadDayFromServer.mockResolvedValue(dayWith([CUSTOM]));
    sync.mockImplementation(async () => {
      // what the replay's markOrphan leaves behind
      storage.setItem(KEY, JSON.stringify({ ...stored(), orphan: { detectedAt: "2026-11-04T12:30:00Z" } }));
      return { sent: 0, alreadySaved: 0, rejected: 0, failed: 0, undecided: 1 };
    });
    renderPage();
    await flush();
    expect(screen.getByText("Session saved on this device")).toBeTruthy();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /send now/i }));
    });
    await flush();

    expect(sync).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/will go out when the connection is back/i)).toBeNull();
    expect(screen.getByText("This session is no longer in your plan")).toBeTruthy();
    expect(screen.getByRole("button", { name: /log it in place of vo2 max · lunch/i })).toBeTruthy();
    expect(stored().orphan).toBeTruthy();
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("B414 — OrphanSessionBox", () => {
  beforeEach(() => {
    storage.setItem(KEY, JSON.stringify({ ...stored(), submitStatus: "feedback_pending", orphan: { detectedAt: "x" } }));
  });

  it("a failed placement is shown, the entry stays «to decide»", async () => {
    orphan.loadDayFromServer.mockResolvedValue(dayWith([CUSTOM]));
    orphan.placeOrphanSession.mockRejectedValue(new Error("boom"));
    const onDone = renderBox();
    await flush();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /log it in place of/i }));
    });
    await flush();
    expect(screen.getByText(/couldn't update your plan — nothing was changed/i)).toBeTruthy();
    expect(stored().orphan).toBeTruthy();
    expect(sync).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("no free slot → no «extra»; a generated session cannot be placed", async () => {
    const full = [CUSTOM, { session_id: "mobility", slot: "morning", status: "planned" }, { session_id: "x", slot: "evening", status: "done" }];
    orphan.loadDayFromServer.mockResolvedValue(dayWith(full));
    renderBox();
    await flush();
    expect(screen.queryByRole("button", { name: /as an extra/i })).toBeNull();
    expect(screen.getAllByRole("button", { name: /log it in place of/i })).toHaveLength(2);
    cleanup();

    orphan.loadDayFromServer.mockResolvedValue(dayWith([CUSTOM]));
    renderBox("generated_core_x");
    await flush();
    expect(screen.queryByRole("button", { name: /log it/i })).toBeNull();
    expect(screen.getByText(/generated session can't be put back/i)).toBeTruthy();
  });

  it("Discard asks first, then deletes the saved feedback", async () => {
    orphan.loadDayFromServer.mockResolvedValue(dayWith([CUSTOM]));
    const onDone = renderBox();
    await flush();
    fireEvent.click(screen.getByRole("button", { name: /^discard$/i }));
    expect(stored()).toBeTruthy(); // not yet
    fireEvent.click(screen.getByRole("button", { name: /keep it/i }));
    expect(stored()).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /^discard$/i }));
    const confirm = screen.getAllByRole("button", { name: /^discard$/i });
    fireEvent.click(confirm[confirm.length - 1]);
    expect(stored()).toBeNull();
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("offline: says so and offers to try again, nothing is sent", async () => {
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
    renderBox();
    await flush();
    expect(screen.getByText(/you're offline/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /try again/i })).toBeTruthy();
    expect(orphan.loadDayFromServer).not.toHaveBeenCalled();
  });

  it("back in the plan (put back from elsewhere): one button sends it", async () => {
    orphan.loadDayFromServer.mockResolvedValue(dayWith([{ session_id: "treadmill_hiit_4x4", slot: "lunch", status: "planned" }]));
    sync.mockImplementation(async () => {
      storage.removeItem(KEY);
      return { sent: 1, alreadySaved: 0, rejected: 0, failed: 0, undecided: 0 };
    });
    const onDone = renderBox();
    await flush();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /send it now/i }));
    });
    await flush();
    expect(sync).toHaveBeenCalledTimes(1);
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});
