/**
 * @vitest-environment jsdom
 *
 * B411 — Skip / Done pinned to the bottom of the guided player.
 *
 * Daniele, 02/11: «devo premere spesso done due volte». Done closed a long
 * card, so every exercise ended with a swipe down to reach it; on an iPhone a
 * tap that lands while the page is still gliding only stops the scroll. The
 * buttons now live in a fixed bar, visible without scrolling, with the
 * exercise Done leads to written above them.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createElement } from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, cleanup, fireEvent, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/audio-unlock", () => ({
  unlockAudio: vi.fn(async () => {}),
  getAudioContext: vi.fn(() => ({ state: "running", resume: vi.fn() })),
}));
vi.mock("@/lib/haptics", () => ({
  tapFeedback: vi.fn(),
  confirmFeedback: vi.fn(),
  completeFeedback: vi.fn(),
}));
vi.mock("@/lib/beep", () => ({ countdownTick: vi.fn(), transitionBeep: vi.fn(), restOverCue: vi.fn() }));
vi.mock("@/lib/voice-cues", () => ({ speakPhaseTransition: vi.fn() }));

import { GuidedExerciseStep } from "@/components/guided/guided-exercise-step";
import { GUIDED_ACTION_BAR_SPACE } from "@/components/guided/guided-action-bar";
import type { GuidedExercise } from "@/lib/types";

function exercise(extra: Partial<GuidedExercise> = {}): GuidedExercise {
  return {
    exerciseId: "dumbbell_bench_press",
    name: "Dumbbell Bench Press",
    category: "strength",
    blockUid: "main",
    loadModel: "external_load",
    prescription: { sets: 3, reps: 8, restSeconds: 90 },
    suggested: { externalLoadKg: 20 },
    status: "pending",
    feedbackLabel: null,
    ...extra,
  };
}

const bar = () => screen.getByTestId("guided-action-bar");

afterEach(() => {
  cleanup();
});

describe("B411 — the step's Skip / Done sit in a bar pinned to the screen", () => {
  it("one Done, in a fixed bar at the bottom, clear of the home indicator", () => {
    render(<GuidedExerciseStep exercise={exercise()} onDone={vi.fn()} onSkip={vi.fn()} />);

    expect(bar().className).toContain("fixed");
    expect(bar().className).toContain("bottom-0");
    expect(bar().innerHTML).toContain("env(safe-area-inset-bottom)");
    // No second Done left at the bottom of the card.
    const dones = screen.getAllByRole("button", { name: /^done$/i });
    expect(dones).toHaveLength(1);
    expect(bar().contains(dones[0])).toBe(true);
    expect(within(bar()).getByRole("button", { name: /^skip$/i })).toBeTruthy();
  });

  it("the bar's Done closes the exercise and its Skip skips it", () => {
    const onDone = vi.fn();
    const onSkip = vi.fn();
    render(<GuidedExerciseStep exercise={exercise()} onDone={onDone} onSkip={onSkip} />);

    fireEvent.click(within(bar()).getByRole("button", { name: /^done$/i }));
    expect(onDone).toHaveBeenCalledTimes(1);
    // The load field travels with it, as before (pre-filled 20 kg).
    expect(onDone.mock.calls[0][1]).toBe(20);

    fireEvent.click(within(bar()).getByRole("button", { name: /^skip$/i }));
    expect(onSkip).toHaveBeenCalledTimes(1);
  });

  it("an exercise already done says Update", () => {
    render(<GuidedExerciseStep exercise={exercise({ status: "done" })} onDone={vi.fn()} onSkip={vi.fn()} />);
    expect(within(bar()).getByRole("button", { name: /^update$/i })).toBeTruthy();
  });

  it("an instruction-only block (warm-up) gets the bar with Done only", () => {
    const onDone = vi.fn();
    render(
      <GuidedExerciseStep
        exercise={exercise({ isInstructionOnly: true, name: "General warm-up", category: "warmup_general" })}
        onDone={onDone}
        onSkip={vi.fn()}
      />,
    );
    expect(within(bar()).queryByRole("button", { name: /^skip$/i })).toBeNull();
    fireEvent.click(within(bar()).getByRole("button", { name: /^done$/i }));
    expect(onDone).toHaveBeenCalledWith(null);
  });

  it("says where Done leads: the next exercise, or the summary", () => {
    const { rerender } = render(
      <GuidedExerciseStep exercise={exercise()} onDone={vi.fn()} onSkip={vi.fn()} upNext="Overhead Press" />,
    );
    expect(screen.getByTestId("guided-up-next").textContent).toContain("Overhead Press");

    rerender(<GuidedExerciseStep exercise={exercise()} onDone={vi.fn()} onSkip={vi.fn()} upNext={null} />);
    expect(screen.getByTestId("guided-up-next").textContent).toMatch(/summary/i);

    rerender(<GuidedExerciseStep exercise={exercise()} onDone={vi.fn()} onSkip={vi.fn()} />);
    expect(screen.queryByTestId("guided-up-next")).toBeNull();
  });

  it("the enlarged timer still covers the bar", () => {
    const src = (rel: string) => readFileSync(join(process.cwd(), "src", rel), "utf8");
    expect(src("components/guided/guided-action-bar.tsx")).toContain("z-40");
    expect(src("components/guided/exercise-timer.tsx")).toContain("fixed inset-0 z-[60]");
  });
});

// ---------------------------------------------------------------------------
// The page: what it tells the step, and the room it keeps for the bar
// ---------------------------------------------------------------------------

const { router, toast } = vi.hoisted(() => {
  const toast = Object.assign(vi.fn<(message: unknown, options?: unknown) => string>(() => "toast-id"), {
    success: vi.fn(),
    error: vi.fn(),
    dismiss: vi.fn(),
  });
  return { router: { replace: vi.fn(), push: vi.fn() }, toast };
});

vi.mock("next/navigation", () => ({
  useParams: () => ({ date: "2026-11-02", sessionId: "custom_push" }),
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

const KEY = "guided_session_user_A_2026-11-02_custom_push";
let storage: MemoryStorage;

function seed(currentIndex: number, exercises: GuidedExercise[]) {
  storage.setItem(
    KEY,
    JSON.stringify({
      version: 1,
      date: "2026-11-02",
      sessionId: "custom_push",
      sessionName: "Push",
      startedAt: new Date(Date.now() - 600_000).toISOString(),
      currentIndex,
      exercises,
    }),
  );
}

function renderPage() {
  return render(createElement(QueryClientProvider, { client: new QueryClient() }, createElement(GuidedSessionPage)));
}

describe("B411 — the guided page", () => {
  beforeEach(() => {
    storage = new MemoryStorage();
    Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
    vi.stubGlobal("localStorage", storage);
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
    (window as unknown as { Clerk?: unknown }).Clerk = { session: {}, user: { id: "user_A" }, loaded: true };
    toast.mockClear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("Next names the first exercise still pending, like Done does — not the one after", () => {
    seed(0, [
      exercise({ exerciseId: "a", name: "Bench" }),
      exercise({ exerciseId: "b", name: "Curl", status: "done" }),
      exercise({ exerciseId: "c", name: "Overhead Press" }),
    ]);
    renderPage();

    expect(screen.getByTestId("guided-up-next").textContent).toContain("Overhead Press");
    expect(screen.getByTestId("guided-up-next").textContent).not.toContain("Curl");
  });

  it("on the last exercise left, Next says the summary comes next", () => {
    seed(1, [exercise({ exerciseId: "a", name: "Bench", status: "done" }), exercise({ exerciseId: "b", name: "Curl" })]);
    renderPage();

    expect(screen.getByTestId("guided-up-next").textContent).toMatch(/summary/i);
  });

  it("keeps room for the bar under the exercise, none on the summary", () => {
    seed(0, [exercise({ exerciseId: "a", name: "Bench" })]);
    renderPage();

    const spaceClass = GUIDED_ACTION_BAR_SPACE;
    expect(document.querySelector("main")!.className).toContain(spaceClass);
    // "Finish session early" stays in the flow, above the reserved room.
    expect(screen.getByRole("button", { name: /finish session early/i })).toBeTruthy();

    fireEvent.click(within(bar()).getByRole("button", { name: /^done$/i }));

    expect(screen.queryByTestId("guided-action-bar")).toBeNull();
    expect(document.querySelector("main")!.className).not.toContain(spaceClass);
  });
});
