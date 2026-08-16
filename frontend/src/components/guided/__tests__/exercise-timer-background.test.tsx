/**
 * @vitest-environment jsdom
 *
 * B332 — the set/rep counter must never advance while the app is in the
 * background.
 *
 * Reported from production (2026-08-16): boulder guided session, app closed for
 * a while during a rest, and on reopen the counter had gained a set nobody
 * climbed. Two defects behind it:
 *
 *   1. the rest transition auto-advanced on the first tick after resume — the
 *      wall-clock deadline had expired unattended;
 *   2. that transition was not idempotent. On manual (tap-to-work) exercises it
 *      did not re-arm the deadline, so every further tick landing before React
 *      had committed re-entered the same branch with the stale closure and
 *      incremented again — past the prescription, with no clamp.
 *
 * `tick()` below reproduces (2) exactly: several interval fires inside ONE act(),
 * i.e. with no React commit in between, which is the state the app is in while
 * it comes back to the foreground.
 *
 * Nothing covered the state machine before this file: the only other timer suite
 * pins `shouldFireCountdownBeep`, i.e. the beeps.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";

vi.mock("@/lib/audio-unlock", () => ({
  unlockAudio: vi.fn(async () => {}),
  getAudioContext: vi.fn(() => ({ state: "running", resume: vi.fn() })),
}));
vi.mock("@/lib/haptics", () => ({ tapFeedback: vi.fn() }));
vi.mock("@/lib/beep", () => ({ countdownTick: vi.fn(), transitionBeep: vi.fn() }));
vi.mock("@/lib/voice-cues", () => ({ speakPhaseTransition: vi.fn() }));

import { ExerciseTimer } from "../exercise-timer";

/** Boulder shape: manual work (tap "Done set"), 5 min between sets. */
const BOULDER = {
  workSeconds: 0,
  restBetweenRepsSeconds: 0,
  restBetweenSetsSeconds: 300,
  sets: 4,
  reps: 1,
};

/** Click a handler that awaits unlockAudio() before touching state. */
async function click(name: RegExp) {
  const el = screen.getAllByRole("button", { name })[0];
  await act(async () => {
    fireEvent.click(el);
  });
}

/**
 * Time passing WITH the app in the foreground: React commits between ticks, so
 * each phase transition is observed live.
 */
async function advance(ms: number) {
  const steps = Math.ceil(ms / 200);
  for (let i = 0; i < steps; i++) {
    await act(async () => {
      vi.advanceTimersByTime(200);
    });
  }
}

/**
 * The app was away: the wall clock jumped, the interval did not run. Fake timers
 * shift pending timers with the clock, so the interval is still due in 200 ms —
 * it simply wakes up to a deadline that expired long ago.
 */
function background(ms: number) {
  act(() => {
    vi.setSystemTime(Date.now() + ms);
  });
}

/** Interval fires with NO React commit between them — the resume condition. */
async function tick(times = 5) {
  await act(async () => {
    vi.advanceTimersByTime(200 * times);
  });
}

function counter(): string {
  return screen.getAllByText(/Set \d+ \/ \d+/)[0].textContent ?? "";
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-08-16T12:00:00Z"));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("B332 — guided timer never advances the counter unattended", () => {
  it("holds the rest instead of advancing the set when the app was away", async () => {
    const onSetChange = vi.fn();
    render(<ExerciseTimer {...BOULDER} onSetChange={onSetChange} />);

    await click(/start/i);
    // Set 1 climbed → "Done set" starts the 5-minute rest.
    await click(/done set/i);
    expect(onSetChange).toHaveBeenCalledWith(1);
    expect(counter()).toContain("Set 1 / 4");

    // Away for 8 minutes: the rest expires with nobody watching.
    background(8 * 60_000);
    await tick();

    // The counter must NOT have moved, and the timer must be asking for a tap.
    expect(counter()).toContain("Set 1 / 4");
    expect(screen.getAllByText(/REST OVER/i).length).toBeGreaterThan(0);
    expect(onSetChange).toHaveBeenCalledTimes(1);
  });

  it("advances exactly one set when the athlete taps, never two", async () => {
    render(<ExerciseTimer {...BOULDER} />);

    await click(/start/i);
    await click(/done set/i);

    background(8 * 60_000);
    await tick();

    await click(/next set/i);
    expect(counter()).toContain("Set 2 / 4");

    // Further ticks must not re-fire the transition — this is the stale-closure
    // double increment that produced the phantom set.
    await tick(10);
    expect(counter()).toContain("Set 2 / 4");
  });

  it("never advances past the prescribed number of sets", async () => {
    render(<ExerciseTimer {...BOULDER} sets={2} />);

    await click(/start/i);
    await click(/done set/i);
    background(6 * 60_000);
    await tick();
    await click(/next set/i);
    await click(/done set/i);
    await tick(20);

    for (const el of screen.queryAllByText(/Set \d+ \/ 2/)) {
      const n = Number(/Set (\d+) \/ 2/.exec(el.textContent ?? "")?.[1]);
      expect(n).toBeLessThanOrEqual(2);
    }
  });

  it("still auto-advances a timed work phase that expires under our eyes", async () => {
    const onSetChange = vi.fn();
    // 30 s work, 60 s rest — a plank-style circuit must stay hands-free.
    render(
      <ExerciseTimer
        workSeconds={30}
        restBetweenRepsSeconds={0}
        restBetweenSetsSeconds={60}
        sets={3}
        reps={1}
        onSetChange={onSetChange}
      />,
    );

    await click(/start/i);
    // get_ready (5 s) + the 30 s work phase, all watched live.
    await advance(36_000);

    // The set completed on its own — no tap needed.
    expect(onSetChange).toHaveBeenCalledWith(1);
  });

  it("holds a timed work phase that expired while the app was away", async () => {
    const onSetChange = vi.fn();
    render(
      <ExerciseTimer
        workSeconds={30}
        restBetweenRepsSeconds={0}
        restBetweenSetsSeconds={60}
        sets={3}
        reps={1}
        onSetChange={onSetChange}
      />,
    );

    await click(/start/i);
    // Clear get_ready live, then disappear during the work phase.
    await advance(6_000);
    background(10 * 60_000);
    await tick();

    // A set that ran out unattended is not a set that was done.
    expect(onSetChange).not.toHaveBeenCalled();
    expect(screen.getAllByText(/TIME UP/i).length).toBeGreaterThan(0);
  });
});
