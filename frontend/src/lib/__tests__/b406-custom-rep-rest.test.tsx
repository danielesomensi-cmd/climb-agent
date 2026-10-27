/**
 * @vitest-environment jsdom
 *
 * B406 — the player of a saved custom session (/session-builder/[id]/play,
 * "Start" from My Sessions) ignored the rest between reps: three_attempt_comp
 * 1×3 with 180" between attempts was one "Done set" tap and on to the next
 * exercise. Now each rep is a tap, the rest runs in between and holds at the
 * end ("Next rep"), and the last rep closes the set — same loop as the guided
 * player (B124, B405).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createElement } from "react";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { CustomSession, CustomSessionExercise } from "@/lib/types";

const { router, session } = vi.hoisted(() => ({
  router: { replace: vi.fn(), push: vi.fn() },
  session: { current: null as CustomSession | null },
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "cs_b406" }),
  useRouter: () => router,
  useSearchParams: () => new URLSearchParams("date=2026-10-27"),
}));
vi.mock("@/lib/hooks/queries", () => ({
  useCustomSession: () => ({ data: session.current, isLoading: false, error: null }),
  useBuilderExercises: () => ({
    data: { exercises: [{ id: "three_attempt_comp", name: "Three-attempt comp" }, { id: "pullup", name: "Pull-up" }] },
  }),
}));
vi.mock("@/lib/hooks/use-subscription", () => ({
  useSubscription: () => ({ canInteract: true, loading: false }),
}));
vi.mock("@/lib/hooks/use-wake-lock", () => ({ useWakeLock: () => {} }));
vi.mock("@/lib/api", () => ({ applyEvents: vi.fn(), postFeedback: vi.fn() }));
vi.mock("@/lib/audio-unlock", () => ({
  unlockAudio: vi.fn(async () => {}),
  getAudioContext: vi.fn(() => ({ state: "running", resume: vi.fn() })),
}));
vi.mock("@/lib/haptics", () => ({ tapFeedback: vi.fn(), confirmFeedback: vi.fn(), completeFeedback: vi.fn() }));
vi.mock("@/lib/beep", () => ({
  countdownTick: vi.fn(),
  transitionBeep: vi.fn(),
  longBeep: vi.fn(),
  restOverCue: vi.fn(),
}));

import SessionPlayPage from "@/app/(guided)/session-builder/[id]/play/page";
import { hasRepRest } from "@/components/session-play/custom-exercise-step";

function ex(overrides: Partial<CustomSessionExercise>): CustomSessionExercise {
  return {
    exercise_id: "x",
    sets: 1,
    reps: null,
    work_seconds: null,
    rest_between_sets_seconds: null,
    rest_between_reps_seconds: null,
    load_kg: 0,
    notes: "",
    ...overrides,
  };
}

const COMP = ex({ exercise_id: "three_attempt_comp", sets: 1, reps: 3, rest_between_reps_seconds: 180 });
const PULLUP = ex({ exercise_id: "pullup", sets: 2, reps: 5, rest_between_sets_seconds: 90 });

async function click(name: RegExp) {
  const el = screen.getAllByRole("button", { name })[0];
  await act(async () => {
    fireEvent.click(el);
  });
}

async function advance(ms: number) {
  for (let i = 0; i < Math.ceil(ms / 250); i++) {
    await act(async () => {
      vi.advanceTimersByTime(250);
    });
  }
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(createElement(QueryClientProvider, { client: qc }, createElement(SessionPlayPage)));
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-27T18:00:00Z"));
  session.current = {
    id: "cs_b406",
    name: "Try-hard",
    created_at: "2026-10-27T00:00:00Z",
    updated_at: "2026-10-27T00:00:00Z",
    tags: [],
    exercises: [COMP, PULLUP],
    estimated_load_score: 40,
    estimated_duration_minutes: 30,
  };
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("hasRepRest", () => {
  it("reps at the athlete's pace with a timed rest between them", () => {
    expect(hasRepRest(COMP)).toBe(true);
  });
  it.each([
    ["no rest between reps", { rest_between_reps_seconds: 0 }],
    ["a single rep", { reps: 1 }],
    ["timed work (the clock is the exercise)", { work_seconds: 7 }],
  ])("not with %s", (_label, overrides) => {
    expect(hasRepRest({ ...COMP, ...overrides })).toBe(false);
  });
});

describe("B406 — rest between reps in the custom player", () => {
  it("one tap per rep, the rest in between, then the next exercise as before", async () => {
    renderPage();
    expect(screen.getByText(/180s between reps/)).toBeTruthy();
    await click(/start first exercise/i);

    // Rep 1 of 3: one rep per tap.
    expect(screen.getAllByText(/Rep 1 of 3/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /done set/i })).toBeNull();
    await click(/done rep/i);

    // The rep rest: 3:00, then it holds — rep-based, the athlete decides.
    expect(screen.getByText("3:00")).toBeTruthy();
    expect(screen.getByText(/Rep 2 of 3 · Three-attempt comp/)).toBeTruthy();
    await advance(180_000 + 5_000);
    expect(screen.queryByRole("button", { name: /done rep/i })).toBeNull();
    await click(/^next rep$/i);

    expect(screen.getAllByText(/Rep 2 of 3/).length).toBeGreaterThan(0);
    await click(/done rep/i);
    await click(/skip rest/i);
    expect(screen.getAllByText(/Rep 3 of 3/).length).toBeGreaterThan(0);

    // The last rep closes the set; no set rest → straight to the pull-ups,
    // which keep the plain "Done set" flow.
    await click(/done rep/i);
    expect(screen.getByText("Pull-up")).toBeTruthy();
    expect(screen.getAllByText(/5 reps/).length).toBeGreaterThan(0);
    await click(/done set/i);
    expect(screen.getByText("1:30")).toBeTruthy();
    await click(/skip rest/i);
    await click(/done set/i);

    // 1 set of the comp + 2 of pull-ups.
    expect(screen.getByText("Session complete")).toBeTruthy();
    expect(screen.getByText("1/1 sets")).toBeTruthy();
    expect(screen.getByText("2/2 sets")).toBeTruthy();
  });

  it("skipping the exercise mid-set restarts the reps at 1 for the next one", async () => {
    session.current!.exercises = [COMP, { ...COMP }];
    renderPage();
    await click(/start first exercise/i);
    await click(/done rep/i);
    await click(/skip rest/i);
    expect(screen.getAllByText(/Rep 2 of 3/).length).toBeGreaterThan(0);
    await click(/skip exercise/i);
    expect(screen.getAllByText(/Exercise 2 of 2/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Rep 1 of 3/).length).toBeGreaterThan(0);
  });
});
