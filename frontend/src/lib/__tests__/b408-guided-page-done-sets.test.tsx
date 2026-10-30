/**
 * @vitest-environment jsdom
 *
 * B408 — the page half of "Done counts the last set". The step reports the
 * set with onSetChange right before onDone (like the B133 repeater): the page
 * must keep it through the Done that closes the exercise, and Undo of that
 * Done must take the set back with it. Real guided page, stub step.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createElement } from "react";
import { render, screen, cleanup, act, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const { router, toast } = vi.hoisted(() => {
  const toast = Object.assign(vi.fn<(message: unknown, options?: unknown) => string>(() => "toast-id"), {
    success: vi.fn(),
    error: vi.fn(),
    dismiss: vi.fn(),
  });
  return { router: { replace: vi.fn(), push: vi.fn() }, toast };
});

vi.mock("next/navigation", () => ({
  useParams: () => ({ date: "2026-10-30", sessionId: "custom_push" }),
  useRouter: () => router,
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ isLoaded: true, userId: "user_A" }) }));
vi.mock("sonner", () => ({ toast }));
vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  postFeedback: vi.fn(),
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
// What the real step does when Done lands on the work of set 3: the set,
// then the Done.
vi.mock("@/components/guided/guided-exercise-step", () => ({
  GuidedExerciseStep: ({
    exercise,
    onDone,
    onSetChange,
  }: {
    exercise: { name: string };
    onDone: (label: string | null) => void;
    onSetChange?: (n: number) => void;
  }) =>
    createElement(
      "div",
      null,
      createElement("h2", { "data-testid": "exercise" }, exercise.name),
      createElement(
        "button",
        {
          onClick: () => {
            onSetChange?.(3);
            onDone("easy");
          },
        },
        "Done",
      ),
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

const KEY = "guided_session_user_A_2026-10-30_custom_push";
let storage: MemoryStorage;

function ex(name: string, completedSets?: number) {
  return {
    exerciseId: name,
    name,
    category: "strength",
    blockUid: "main",
    loadModel: "external_load",
    prescription: { sets: 3, reps: 8, restSeconds: 90 },
    suggested: { externalLoadKg: 20 },
    status: "pending",
    feedbackLabel: null,
    ...(completedSets != null ? { completedSets } : {}),
  };
}

const stored = () => JSON.parse(storage.getItem(KEY) ?? "null");

beforeEach(() => {
  storage = new MemoryStorage();
  Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
  vi.stubGlobal("localStorage", storage);
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  (window as unknown as { Clerk?: unknown }).Clerk = { session: {}, user: { id: "user_A" }, loaded: true };
  toast.mockClear();
  storage.setItem(
    KEY,
    JSON.stringify({
      version: 1,
      date: "2026-10-30",
      sessionId: "custom_push",
      sessionName: "Push",
      startedAt: new Date(Date.now() - 3600_000).toISOString(),
      currentIndex: 0,
      exercises: [ex("dumbbell_bench_press", 2), ex("overhead_press")],
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("B408 — the guided page keeps the set counted by Done", () => {
  it("set 3 and Done land together: 3 of 3, done, rated", () => {
    render(createElement(QueryClientProvider, { client: new QueryClient() }, createElement(GuidedSessionPage)));

    fireEvent.click(screen.getByText("Done"));

    expect(screen.getByTestId("exercise").textContent).toBe("overhead_press");
    const bench = stored().exercises[0];
    expect(bench.status).toBe("done");
    expect(bench.feedbackLabel).toBe("easy");
    expect(bench.completedSets).toBe(3);
  });

  it("Undo of that Done takes the set back: 2, pending", async () => {
    render(createElement(QueryClientProvider, { client: new QueryClient() }, createElement(GuidedSessionPage)));
    fireEvent.click(screen.getByText("Done"));

    const call = [...toast.mock.calls].reverse().find((c) => /^Done: /.test(String(c[0])));
    const options = call?.[1] as { action?: { onClick: () => void } } | undefined;
    act(() => options!.action!.onClick());

    expect(screen.getByTestId("exercise").textContent).toBe("dumbbell_bench_press");
    await waitFor(() => expect(stored().exercises[0].status).toBe("pending"));
    expect(stored().exercises[0].completedSets).toBe(2);
  });
});
