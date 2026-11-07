/**
 * @vitest-environment jsdom
 *
 * B414 (CUSTOM-PLAYER-DONE-FLAG + B-ALTSIDES-SETS) — the player of a saved
 * custom session (/session-builder/[id]/play, "Start" from My Sessions) sent
 * every row `completed: true` with the saved load, skipped rows included, and
 * the sets of an alt_sides exercise in internal units (one per side).
 *
 * Now: done = the exercise ran to its last set; stopped earlier with «Skip
 * exercise» it is not done and keeps its sets (real sets: complete
 * RIGHT+LEFT pairs); skipped with nothing done it goes out `completed: false`,
 * `completed_sets: 0`, with no rating, load or measure — a rating on a
 * not-done row is a failed session for bw_progression (R1) and would lower its
 * ladder, so a skipped row carries no signal at all (review of step 23).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createElement } from "react";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { CustomSession, CustomSessionExercise } from "@/lib/types";
import { queryKeys } from "@/lib/query-keys";

const { router, session, api } = vi.hoisted(() => ({
  router: { replace: vi.fn(), push: vi.fn() },
  session: { current: null as CustomSession | null },
  api: {
    applyEvents: vi.fn<(req: unknown) => Promise<unknown>>(async () => ({ week_plan: { weeks: [] } })),
    postFeedback: vi.fn<(body: unknown) => Promise<unknown>>(async () => ({})),
  },
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "cs_b414" }),
  useRouter: () => router,
  useSearchParams: () => new URLSearchParams("date=2026-11-07"),
}));
vi.mock("@/lib/hooks/queries", () => ({
  useCustomSession: () => ({ data: session.current, isLoading: false, error: null }),
  useBuilderExercises: () => ({
    data: {
      exercises: [
        { id: "pullup", name: "Pull-up" },
        { id: "bulgarian_split_squat", name: "Bulgarian split squat" },
        { id: "plank", name: "Plank" },
      ],
    },
  }),
}));
vi.mock("@/lib/hooks/use-subscription", () => ({
  useSubscription: () => ({ canInteract: true, loading: false }),
}));
vi.mock("@/lib/hooks/use-wake-lock", () => ({ useWakeLock: () => {} }));
vi.mock("@/lib/api", () => api);
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

const PULLUP = ex({ exercise_id: "pullup", sets: 2, reps: 5, load_kg: 10 });
const SPLIT = ex({ exercise_id: "bulgarian_split_squat", sets: 2, reps: 8, load_kg: 12, alt_sides: true });
const PLANK = ex({ exercise_id: "plank", sets: 3, reps: 1, load_kg: 5, measure: "last_set_reps", target_reps: 1 });

async function click(name: RegExp) {
  const el = screen.getAllByRole("button", { name })[0];
  await act(async () => {
    fireEvent.click(el);
  });
}

/** handleFinish awaits /events then /feedback (mocked: microtasks only). */
async function flush() {
  for (let i = 0; i < 5; i++) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // The player marks custom_<id> done on the cached week before the feedback.
  qc.setQueryData(queryKeys.week(0), {
    week_num: 0,
    week_plan: {
      weeks: [{ days: [{ date: "2026-11-07", sessions: [{ session_id: "custom_cs_b414", status: "planned" }] }] }],
    },
  });
  return render(createElement(QueryClientProvider, { client: qc }, createElement(SessionPlayPage)));
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-11-07T12:00:00Z"));
  api.applyEvents.mockClear();
  api.postFeedback.mockClear();
  session.current = {
    id: "cs_b414",
    name: "Lunch",
    created_at: "2026-11-07T00:00:00Z",
    updated_at: "2026-11-07T00:00:00Z",
    tags: [],
    exercises: [PULLUP, SPLIT, PLANK],
    estimated_load_score: 30,
    estimated_duration_minutes: 30,
  };
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("B414 — the custom-session player tells the truth", () => {
  it("full / partial (alt_sides) / skipped rows", async () => {
    renderPage();
    await click(/start first exercise/i);

    // Pull-ups 2×5, no rest: both sets.
    await click(/done set/i);
    await click(/done set/i);

    // Split squat 2×8 per side: RIGHT, LEFT, RIGHT, then skip.
    expect(screen.getAllByText(/Bulgarian split squat/).length).toBeGreaterThan(0);
    await click(/done set/i); // set 1 RIGHT
    await click(/skip rest/i); // side switch
    await click(/done set/i); // set 1 LEFT
    await click(/done set/i); // set 2 RIGHT
    await click(/skip rest/i);
    await click(/skip exercise/i);

    // Plank: skipped straight away — nothing to rate or fill on the completion screen.
    await click(/skip exercise/i);
    expect(screen.getByText("Session complete")).toBeTruthy();
    expect(screen.getByText("Skipped")).toBeTruthy();
    // Nothing to fill on a skipped row: two load fields (pull-ups, split squat), not three,
    // and two rating rows, not three.
    expect(screen.getAllByText("Used load")).toHaveLength(2);
    const hardPills = screen.getAllByRole("button", { name: /^hard$/i });
    expect(hardPills).toHaveLength(2);
    await act(async () => {
      fireEvent.click(hardPills[1]);
    });

    await click(/^done$/i);
    await flush();
    expect(api.postFeedback).toHaveBeenCalledTimes(1);
    const body = api.postFeedback.mock.calls[0][0] as {
      log_entry: { actual: { exercise_feedback_v1: Array<Record<string, unknown>> } };
    };
    const [pullup, split, plank] = body.log_entry.actual.exercise_feedback_v1;

    expect(pullup).toEqual({
      exercise_id: "pullup",
      completed: true,
      completed_sets: 2,
      used_external_load_kg: 10,
    });
    // 3 internal sets = one complete pair: not done, 1 real set, the load it used.
    // Stopped before the last set: the rating goes along with completed:false.
    expect(split).toMatchObject({
      exercise_id: "bulgarian_split_squat",
      completed: false,
      completed_sets: 1,
      feedback_label: "hard",
    });
    expect(split.used_external_load_kg).toBe(12);
    // Skipped: not done, 0 sets, no rating, no pre-filled load or measure.
    expect(plank).toEqual({
      exercise_id: "plank",
      completed: false,
      completed_sets: 0,
    });
  });

  it("an alt_sides exercise run to its end sends the prescribed sets, not the sides", async () => {
    session.current!.exercises = [SPLIT];
    renderPage();
    await click(/start first exercise/i);
    for (let set = 0; set < 2; set++) {
      await click(/done set/i); // RIGHT
      await click(/skip rest/i);
      await click(/done set/i); // LEFT
    }
    expect(screen.getByText("Session complete")).toBeTruthy();
    expect(screen.getByText("4/4 sets (R+L)")).toBeTruthy();

    await click(/^done$/i);
    await flush();
    expect(api.postFeedback).toHaveBeenCalledTimes(1);
    const body = api.postFeedback.mock.calls[0][0] as {
      log_entry: { actual: { exercise_feedback_v1: Array<Record<string, unknown>> } };
    };
    expect(body.log_entry.actual.exercise_feedback_v1[0]).toMatchObject({ completed: true, completed_sets: 2 });
  });
});
