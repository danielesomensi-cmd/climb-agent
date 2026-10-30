/**
 * @vitest-environment jsdom
 *
 * B408 — the last set was not counted when the athlete closed the exercise
 * with Done instead of «Done set». Daniele, 3×8 dumbbell bench press (26/10)
 * and overhead press (30/10), all three sets done and rated easy: the item
 * reached the server with completed_sets 2 of 3, `sets_ok` failed and the
 * double progression held (`dp_last_outcome: "hold"`).
 *
 * The real step and the real timer, under a harness that keeps the exercise
 * the way the guided page does (onSetChange, then onDone, both functional
 * updates) and builds the payload with the page's own builder.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useCallback, useEffect, useState } from "react";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";

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
import { buildGuidedFeedbackItems } from "@/lib/feedback-items";
import type { GuidedExercise } from "@/lib/types";

let latest: GuidedExercise;

function Harness({ initial }: { initial: GuidedExercise }) {
  const [exercise, setExercise] = useState(initial);
  useEffect(() => {
    latest = exercise;
  }, [exercise]);
  const onSetChange = useCallback(
    (completedSets: number) => setExercise((prev) => ({ ...prev, completedSets })),
    [],
  );
  const onDone = useCallback(
    (feedbackLabel: string | null) => setExercise((prev) => ({ ...prev, status: "done", feedbackLabel })),
    [],
  );
  return <GuidedExerciseStep exercise={exercise} onDone={onDone} onSkip={() => {}} onSetChange={onSetChange} />;
}

function exercise(prescription: GuidedExercise["prescription"], extra: Partial<GuidedExercise> = {}): GuidedExercise {
  return {
    exerciseId: "dumbbell_bench_press",
    name: "Dumbbell Bench Press",
    category: "strength",
    blockUid: "main",
    loadModel: "external_load",
    prescription,
    suggested: { externalLoadKg: 20 },
    status: "pending",
    feedbackLabel: null,
    ...extra,
  };
}

async function click(name: RegExp) {
  const el = screen.getAllByRole("button", { name })[0];
  await act(async () => {
    fireEvent.click(el);
  });
}

async function advance(ms: number) {
  for (let i = 0; i < Math.ceil(ms / 200); i++) {
    await act(async () => {
      vi.advanceTimersByTime(200);
    });
  }
}

/** The exercise's own Done (not the timer's «Done set» / «Done rep»). */
const exerciseDone = () => click(/^done$/i);

/** Manual set rest: it holds at the end (B332/B350) until «Next set/side». */
async function restThenNext(seconds: number, cta: RegExp) {
  await advance(seconds * 1000 + 400);
  await click(cta);
}

const sentSets = () => buildGuidedFeedbackItems([latest])[0].completed_sets;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-30T18:00:00Z"));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("B408 — Done on the work of the last rep-based set", () => {
  it("3×8: «Done set» twice, then Done on set 3 → completed_sets 3 of 3", async () => {
    render(<Harness initial={exercise({ sets: 3, reps: 8, restSeconds: 10 })} />);
    await click(/^start$/i);
    await click(/^done set$/i);
    await restThenNext(10, /^next set$/i);
    await click(/^done set$/i);
    await restThenNext(10, /^next set$/i);
    expect(latest.completedSets).toBe(2);

    await exerciseDone();

    expect(latest.status).toBe("done");
    expect(latest.completedSets).toBe(3);
    expect(sentSets()).toBe(3);
  });

  it("the usual path is unchanged: «Done set» on set 3, then Done → still 3", async () => {
    render(<Harness initial={exercise({ sets: 3, reps: 8, restSeconds: 10 })} />);
    await click(/^start$/i);
    await click(/^done set$/i);
    await restThenNext(10, /^next set$/i);
    await click(/^done set$/i);
    await restThenNext(10, /^next set$/i);
    await click(/^done set$/i);
    await exerciseDone();

    expect(sentSets()).toBe(3);
  });

  it("Done on a middle set counts that set, not the ones never started", async () => {
    render(<Harness initial={exercise({ sets: 3, reps: 8, restSeconds: 10 })} />);
    await click(/^start$/i);
    await click(/^done set$/i);
    await restThenNext(10, /^next set$/i);

    await exerciseDone();

    expect(sentSets()).toBe(2);
  });
});

describe("B408 — what Done does NOT count", () => {
  it("Done during the set rest after set 2 (they stopped) → 2", async () => {
    render(<Harness initial={exercise({ sets: 3, reps: 8, restSeconds: 10 })} />);
    await click(/^start$/i);
    await click(/^done set$/i);
    await restThenNext(10, /^next set$/i);
    await click(/^done set$/i);
    await advance(3_000); // rest running

    await exerciseDone();

    expect(sentSets()).toBe(2);
  });

  it("Done on the held rest («REST OVER», not tapped) → still 2", async () => {
    render(<Harness initial={exercise({ sets: 3, reps: 8, restSeconds: 10 })} />);
    await click(/^start$/i);
    await click(/^done set$/i);
    await restThenNext(10, /^next set$/i);
    await click(/^done set$/i);
    await advance(10_000 + 400);
    expect(screen.getAllByText(/rest over/i).length).toBeGreaterThan(0);

    await exerciseDone();

    expect(sentSets()).toBe(2);
  });

  it("timed work still counting down on set 3 → a set cut short, 2", async () => {
    render(<Harness initial={exercise({ sets: 3, workSeconds: 30, restSeconds: 10 }, { exerciseId: "plank", loadModel: "bodyweight_only" })} />);
    await click(/^start$/i);
    await advance(5_000 + 400); // get ready
    await advance(30_000 + 400); // set 1
    await advance(10_000 + 400); // rest → set 2 starts on its own (B350)
    await advance(30_000 + 400); // set 2
    await advance(10_000 + 400); // rest → set 3
    expect(latest.completedSets).toBe(2);
    await advance(10_000); // 10 s into the 30 s of set 3

    await exerciseDone();

    expect(sentSets()).toBe(2);
  });

  it("timer never started → nothing is invented", async () => {
    render(<Harness initial={exercise({ sets: 3, reps: 8, restSeconds: 10 })} />);

    await exerciseDone();

    expect(latest.status).toBe("done");
    expect(latest.completedSets).toBeUndefined();
    expect(sentSets()).toBeUndefined();
  });

  it("manual rep loop: Done on an attempt before the last is a set cut short; on the last it counts", async () => {
    const attempts = exercise(
      { sets: 1, reps: 3, restBetweenRepsSeconds: 10 },
      { exerciseId: "three_attempt_comp", loadModel: "grade_relative" },
    );
    render(<Harness initial={attempts} />);
    await click(/^start$/i);
    await exerciseDone();
    expect(sentSets()).toBeUndefined();
    cleanup();

    render(<Harness initial={attempts} />);
    await click(/^start$/i);
    await click(/^done rep$/i);
    await restThenNext(10, /^next rep$/i);
    await click(/^done rep$/i);
    await restThenNext(10, /^next rep$/i);
    await exerciseDone();
    expect(sentSets()).toBe(1);
  });
});

describe("B408 — alt_sides counts internal sets, like the timer", () => {
  it("2 sets per side: Done on LEFT of set 2 → 4 internal sets (2 × 2 sides)", async () => {
    render(
      <Harness
        initial={exercise({ sets: 2, reps: 8, restSeconds: 30 }, { exerciseId: "bulgarian_split_squat", altSides: true })}
      />,
    );
    await click(/^start$/i);
    await click(/^done set$/i); // set 1 RIGHT
    await restThenNext(15, /^next side$/i); // B404: side switch, 15 s
    await click(/^done set$/i); // set 1 LEFT
    await restThenNext(30, /^next set$/i);
    await click(/^done set$/i); // set 2 RIGHT
    await restThenNext(15, /^next side$/i);
    expect(latest.completedSets).toBe(3);

    await exerciseDone(); // set 2 LEFT done, «Done set» skipped

    expect(sentSets()).toBe(4);
  });

  it("Done on RIGHT of set 2 counts that side only → 3", async () => {
    render(
      <Harness
        initial={exercise({ sets: 2, reps: 8, restSeconds: 30 }, { exerciseId: "bulgarian_split_squat", altSides: true })}
      />,
    );
    await click(/^start$/i);
    await click(/^done set$/i);
    await restThenNext(15, /^next side$/i);
    await click(/^done set$/i);
    await restThenNext(30, /^next set$/i);

    await exerciseDone();

    expect(sentSets()).toBe(3);
  });
});

describe("B408 — never lowers a count already there", () => {
  it("timer reset back to set 1 after two sets → Done keeps 2", async () => {
    render(<Harness initial={exercise({ sets: 3, reps: 8, restSeconds: 10 })} />);
    await click(/^start$/i);
    await click(/^done set$/i);
    await restThenNext(10, /^next set$/i);
    await click(/^done set$/i);
    await click(/^reset timer$/i);
    await click(/^reset timer$/i); // A307: two taps
    await click(/^start$/i);

    await exerciseDone();

    expect(sentSets()).toBe(2);
  });
});
