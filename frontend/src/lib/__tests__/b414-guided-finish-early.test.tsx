/**
 * @vitest-environment jsdom
 *
 * B414 (PLAYER-COMPLETED-FALSE) — the page half: an exercise with every set
 * counted, never closed with Done, then «Finish session early» → «Submit &
 * finish». The summary shows it done («all sets counted», not among the
 * exercises left), and the POST says `completed: true`. Real guided page and
 * summary, stub step.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createElement } from "react";
import { render, screen, cleanup, act, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { router, toast, postFeedback } = vi.hoisted(() => {
  const toast = Object.assign(vi.fn<(message: unknown, options?: unknown) => string>(() => "toast-id"), {
    success: vi.fn(),
    error: vi.fn(),
    dismiss: vi.fn(),
  });
  return {
    router: { replace: vi.fn(), push: vi.fn() },
    toast,
    postFeedback: vi.fn<(body: unknown) => Promise<{ week_plan: null }>>(async () => ({ week_plan: null })),
  };
});

vi.mock("next/navigation", () => ({
  useParams: () => ({ date: "2026-11-03", sessionId: "custom_cs_2ea7e4a9" }),
  useRouter: () => router,
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true, userId: "user_A" }) }));
vi.mock("sonner", () => ({ toast }));
vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  postFeedback,
  getState: vi.fn(),
}));
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

class MemoryStorage {
  private map = new Map<string, string>();
  get length() { return this.map.size; }
  key(i: number) { return Array.from(this.map.keys())[i] ?? null; }
  getItem(k: string) { return this.map.get(k) ?? null; }
  setItem(k: string, v: string) { this.map.set(k, v); }
  removeItem(k: string) { this.map.delete(k); }
  clear() { this.map.clear(); }
}

const KEY = "guided_session_user_A_2026-11-03_custom_cs_2ea7e4a9";
let storage: MemoryStorage;

function ex(name: string, completedSets?: number) {
  return {
    exerciseId: name,
    name,
    category: "power_endurance",
    blockUid: "main",
    loadModel: "grade_relative",
    prescription: { sets: 4, reps: 4, restSeconds: 240 },
    suggested: {},
    status: "pending",
    feedbackLabel: null,
    ...(completedSets != null ? { completedSets } : {}),
  };
}

beforeEach(() => {
  storage = new MemoryStorage();
  Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
  vi.stubGlobal("localStorage", storage);
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  (window as unknown as { Clerk?: unknown }).Clerk = { session: {}, user: { id: "user_A" }, loaded: true };
  postFeedback.mockClear();
  storage.setItem(
    KEY,
    JSON.stringify({
      version: 1,
      date: "2026-11-03",
      sessionId: "custom_cs_2ea7e4a9",
      sessionName: "PE",
      startedAt: new Date(Date.now() - 3600_000).toISOString(),
      currentIndex: 1,
      isCustom: true,
      exercises: [ex("four_by_four_bouldering", 4), ex("linked_boulders", 1)],
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("B414 — Finish early with an exercise whose sets are all counted", () => {
  it("summary shows it done, the POST says completed:true", async () => {
    render(createElement(QueryClientProvider, { client: new QueryClient() }, createElement(GuidedSessionPage)));

    fireEvent.click(screen.getByRole("button", { name: /finish session early/i }));
    fireEvent.click(screen.getByRole("button", { name: /finish now/i }));

    expect(screen.getByText("1 done")).toBeTruthy();
    expect(screen.getByText("all sets counted")).toBeTruthy();
    // Only the partial one is left to decide.
    expect(screen.getByText(/1 exercise not completed/)).toBeTruthy();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /submit & finish/i }));
    });
    await waitFor(() => expect(postFeedback).toHaveBeenCalledTimes(1));

    const body = postFeedback.mock.calls[0][0] as {
      log_entry: { actual: { exercise_feedback_v1: Array<Record<string, unknown>> } };
    };
    const [fourByFour, linked] = body.log_entry.actual.exercise_feedback_v1;
    expect(fourByFour).toMatchObject({ exercise_id: "four_by_four_bouldering", completed: true, completed_sets: 4 });
    // Partial: not done, but the counted set is saved.
    expect(linked).toMatchObject({ exercise_id: "linked_boulders", completed: false, completed_sets: 1 });
  });
});
