/**
 * @vitest-environment jsdom
 *
 * B405 — one set of reps with timed rest between them had no timer: the guided
 * step showed it only for timed work or for several sets with a set rest, so
 * `three_attempt_comp` (1 × 7 attempts, 3 min apart) came up with no timer at
 * the wall (Daniele, 26/10 at the Bkl). The timer itself already ran that loop.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
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

import { ExerciseTimer } from "@/components/guided/exercise-timer";
import { hasExerciseTimer } from "@/components/guided/guided-exercise-step";

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

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-26T19:24:00Z"));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("B405 — which prescriptions get the timer", () => {
  it("one set of reps with rest between them", () => {
    expect(hasExerciseTimer({ sets: 1, reps: 7, restBetweenRepsSeconds: 180 })).toBe(true);
    expect(hasExerciseTimer({ sets: 1, reps: 3, restBetweenRepsSeconds: 60, restSeconds: 240 })).toBe(true);
  });

  it("unchanged: timed work, several sets with rest, nothing to time", () => {
    expect(hasExerciseTimer({ sets: 1, workSeconds: 30 })).toBe(true);
    expect(hasExerciseTimer({ sets: 3, reps: 8, restSeconds: 90 })).toBe(true);
    expect(hasExerciseTimer({ sets: 1, reps: 7 })).toBe(false);
    expect(hasExerciseTimer({ sets: 1, reps: 1, restBetweenRepsSeconds: 180 })).toBe(false);
    expect(hasExerciseTimer({ sets: 1, reps: "max", restBetweenRepsSeconds: 180 })).toBe(false);
  });
});

describe("B405 — the rep loop of a single set", () => {
  it("attempt → 3 min rest → attempt … → complete after the last one", async () => {
    const onSetChange = vi.fn();
    render(
      <ExerciseTimer
        workSeconds={0}
        restBetweenRepsSeconds={180}
        restBetweenSetsSeconds={0}
        sets={1}
        reps={2}
        onSetChange={onSetChange}
      />,
    );
    await click(/start/i);
    await advance(5_000 + 400); // get ready
    await click(/done rep/i);

    // Rest between attempts: 3:00, counting down.
    expect(screen.getAllByText(/^(3:00|2:5\d)$/).length).toBeGreaterThan(0);
    expect(onSetChange).not.toHaveBeenCalled();

    await advance(180_000 + 400);
    // Rep-based work waits for the tap after a rest (B350).
    expect(screen.getAllByText(/rest over/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /done rep/i })).toBeNull();
    await click(/^next rep$/i);
    await click(/done rep/i);

    expect(onSetChange).toHaveBeenLastCalledWith(1);
    expect(screen.queryByText(/^(3:00|2:5\d)$/)).toBeNull();
  });
});
