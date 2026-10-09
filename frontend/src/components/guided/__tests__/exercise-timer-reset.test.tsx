/**
 * @vitest-environment jsdom
 *
 * A307 — Reset sits next to the controls a chalky thumb aims for, so it takes
 * two taps; and the rest shows what comes next.
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
vi.mock("@/lib/beep", () => ({ countdownTick: vi.fn(), transitionBeep: vi.fn() }));
vi.mock("@/lib/voice-cues", () => ({ speakPhaseTransition: vi.fn() }));

import { ExerciseTimer } from "../exercise-timer";

const MANUAL = {
  workSeconds: 0,
  restBetweenRepsSeconds: 0,
  restBetweenSetsSeconds: 120,
  sets: 3,
  reps: 1,
};

async function click(name: RegExp) {
  const el = screen.getAllByRole("button", { name })[0];
  await act(async () => {
    fireEvent.click(el);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-09T12:00:00Z"));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("A307 — two-tap reset", () => {
  it("first tap only arms, second tap resets", async () => {
    render(<ExerciseTimer {...MANUAL} />);
    await click(/start/i);
    expect(screen.queryAllByText(/Set 1 \/ 3/)).not.toHaveLength(0);

    await click(/reset timer/i);
    expect(screen.getByText(/tap again to reset/i)).toBeTruthy();
    // Still running: the counter is there, no Start button.
    expect(screen.queryAllByText(/Set 1 \/ 3/)).not.toHaveLength(0);

    await click(/reset timer/i);
    expect(screen.queryAllByText(/Set \d+ \/ 3/)).toHaveLength(0);
    expect(screen.getAllByRole("button", { name: /start/i }).length).toBeGreaterThan(0);
  });

  it("disarms after 3 seconds", async () => {
    render(<ExerciseTimer {...MANUAL} />);
    await click(/start/i);
    await click(/reset timer/i);
    await act(async () => {
      vi.advanceTimersByTime(3100);
    });
    expect(screen.queryByText(/tap again to reset/i)).toBeNull();
    // A single tap now arms again instead of resetting.
    await click(/reset timer/i);
    expect(screen.queryAllByText(/Set 1 \/ 3/)).not.toHaveLength(0);
  });
});

describe("A307 — next up during rest", () => {
  it("shows the label passed by the step during the set rest", async () => {
    render(<ExerciseTimer {...MANUAL} nextLabel="Set 2 of 3" />);
    expect(screen.queryByText(/Next · /)).toBeNull();
    await click(/start/i);
    expect(screen.queryByText(/Next · /)).toBeNull();
    await click(/done set/i);
    expect(screen.getByText("Next · Set 2 of 3")).toBeTruthy();
  });
});
