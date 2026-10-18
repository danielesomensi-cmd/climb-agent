/**
 * @vitest-environment jsdom
 *
 * B397 G4 — on rep-based work the end of the rest waits for a tap. It used to
 * be marked by one 0.2 s beep and no voice, easy to miss across a gym; now the
 * timer fires the rest-over cue and says "Go". A rest that expired while the
 * app was away keeps the plain beep (nobody was there to hear it end).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";

const { restOverCue, transitionBeep, speakPhaseTransition } = vi.hoisted(() => ({
  restOverCue: vi.fn(),
  transitionBeep: vi.fn(),
  speakPhaseTransition: vi.fn(),
}));

vi.mock("@/lib/audio-unlock", () => ({
  unlockAudio: vi.fn(async () => {}),
  getAudioContext: vi.fn(() => ({ state: "running", resume: vi.fn() })),
}));
vi.mock("@/lib/haptics", () => ({
  tapFeedback: vi.fn(),
  confirmFeedback: vi.fn(),
  completeFeedback: vi.fn(),
}));
vi.mock("@/lib/beep", () => ({ countdownTick: vi.fn(), transitionBeep, restOverCue }));
vi.mock("@/lib/voice-cues", () => ({ speakPhaseTransition }));

import { ExerciseTimer } from "@/components/guided/exercise-timer";

/** Boulder shape: manual work (tap "Done set"), 2 min between sets. */
const BOULDER = {
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

/** Foreground time: React commits between ticks. */
async function advance(ms: number) {
  for (let i = 0; i < Math.ceil(ms / 200); i++) {
    await act(async () => {
      vi.advanceTimersByTime(200);
    });
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-18T12:00:00Z"));
  restOverCue.mockClear();
  transitionBeep.mockClear();
  speakPhaseTransition.mockClear();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("B397 G4 — the end of a tap-to-continue rest", () => {
  it("watched: fires the rest-over cue once and says Go", async () => {
    render(<ExerciseTimer {...BOULDER} />);
    await click(/start/i);
    await click(/done set/i); // set 1 climbed → 2-minute rest
    transitionBeep.mockClear();
    speakPhaseTransition.mockClear();

    await advance(120_000 + 600);

    expect(restOverCue).toHaveBeenCalledTimes(1);
    expect(transitionBeep).not.toHaveBeenCalled();
    expect(speakPhaseTransition).toHaveBeenCalledWith("work");

    // The held "REST OVER" state keeps ticking — the cue does not repeat.
    await advance(5_000);
    expect(restOverCue).toHaveBeenCalledTimes(1);
  });

  it("expired while the app was away: the plain beep, no voice", async () => {
    render(<ExerciseTimer {...BOULDER} />);
    await click(/start/i);
    await click(/done set/i);
    transitionBeep.mockClear();
    speakPhaseTransition.mockClear();

    act(() => {
      vi.setSystemTime(Date.now() + 8 * 60_000);
    });
    await advance(400);

    expect(restOverCue).not.toHaveBeenCalled();
    expect(transitionBeep).toHaveBeenCalled();
    expect(speakPhaseTransition).not.toHaveBeenCalled();
  });
});
