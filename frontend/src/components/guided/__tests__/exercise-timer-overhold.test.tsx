/**
 * @vitest-environment jsdom
 *
 * A295 (R4) — opt-in timed overhold of the LAST rep of the LAST set.
 * The timer keeps counting past the target, records how long the athlete
 * really held when they tap "I let go", and never past target + 6 s.
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

/** One 7-second hang, one set (the last rep is the first one). */
const HANG = { workSeconds: 7, restBetweenRepsSeconds: 0, restBetweenSetsSeconds: 0, sets: 1, reps: 1 };

async function advance(ms: number) {
  const steps = Math.ceil(ms / 200);
  for (let i = 0; i < steps; i++) {
    await act(async () => {
      vi.advanceTimersByTime(200);
    });
  }
}

async function start() {
  const el = screen.getAllByRole("button", { name: /start/i })[0];
  await act(async () => {
    fireEvent.click(el);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-05T12:00:00Z"));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("A295 — overhold", () => {
  it("records the real hold when the athlete lets go", async () => {
    const onSetChange = vi.fn();
    const onOverholdResult = vi.fn();
    render(<ExerciseTimer {...HANG} overholdLastRep onSetChange={onSetChange} onOverholdResult={onOverholdResult} />);
    await start();
    await advance(5000 + 7000 + 400); // get ready + target
    expect(onSetChange).not.toHaveBeenCalled(); // still hanging
    expect(screen.getAllByText(/tap when you let go/i).length).toBeGreaterThan(0);
    await advance(3000);
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: /i let go/i })[0]);
    });
    expect(onOverholdResult).toHaveBeenCalledTimes(1);
    const held = onOverholdResult.mock.calls[0][0] as number;
    // ~3.4 s past the target minus 1 s of tap latency (A295 review).
    expect(held).toBeGreaterThan(8.5);
    expect(held).toBeLessThan(10);
    expect(onSetChange).toHaveBeenCalledWith(1);
  });

  it("never counts past target + 6 s", async () => {
    const onOverholdResult = vi.fn();
    render(<ExerciseTimer {...HANG} overholdLastRep onOverholdResult={onOverholdResult} />);
    await start();
    await advance(5000 + 7000 + 400);
    await advance(5_000);
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: /i let go/i })[0]);
    });
    const held = onOverholdResult.mock.calls[0][0] as number;
    expect(held).toBeLessThanOrEqual(13);
  });

  it("records nothing when the cap runs out without a tap (A295 review)", async () => {
    const onSetChange = vi.fn();
    const onOverholdResult = vi.fn();
    render(<ExerciseTimer {...HANG} overholdLastRep onSetChange={onSetChange} onOverholdResult={onOverholdResult} />);
    await start();
    await advance(5000 + 7000 + 400);
    await advance(10_000);
    expect(onOverholdResult).not.toHaveBeenCalled();
    expect(onSetChange).toHaveBeenCalledWith(1); // the watched set still counts
  });

  it("records nothing when the overhold expires unwatched (phone locked)", async () => {
    const onOverholdResult = vi.fn();
    render(<ExerciseTimer {...HANG} overholdLastRep onOverholdResult={onOverholdResult} />);
    await start();
    await advance(5000 + 7000 + 400);
    // Suspended: the clock jumps 30 s with no tick in between.
    await act(async () => {
      vi.setSystemTime(Date.now() + 30_000);
      vi.advanceTimersByTime(200);
    });
    await advance(400);
    expect(onOverholdResult).not.toHaveBeenCalled();
  });

  it("is off by default: the hang stops at the target", async () => {
    const onSetChange = vi.fn();
    const onOverholdResult = vi.fn();
    render(<ExerciseTimer {...HANG} onSetChange={onSetChange} onOverholdResult={onOverholdResult} />);
    await start();
    await advance(5000 + 7000 + 400);
    expect(onSetChange).toHaveBeenCalledWith(1);
    expect(onOverholdResult).not.toHaveBeenCalled();
  });
});
