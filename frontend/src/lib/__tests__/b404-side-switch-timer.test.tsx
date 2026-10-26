/**
 * @vitest-environment jsdom
 *
 * B404 — on a side-alternating exercise the guided timer used to run the full
 * set rest between RIGHT and LEFT too: a 2x20s side plank with 60s rest was
 * R, 60s, L, 60s, R, 60s, L. Now RIGHT is followed by a short side switch and
 * only LEFT by the set rest. Also: "Previous phase" from the start of a set
 * went back to a rest that then skipped that very set.
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
import { SIDE_SWITCH_S } from "@/lib/alt-sides";

const PLANK = {
  workSeconds: 20,
  restBetweenRepsSeconds: 0,
  restBetweenSetsSeconds: 60,
  sets: 2,
  reps: 1,
  altSides: true,
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
  vi.setSystemTime(new Date("2026-10-26T12:00:00Z"));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("B404 — side switch between RIGHT and LEFT", () => {
  it("RIGHT → short switch → LEFT → full set rest", async () => {
    const onSetChange = vi.fn();
    render(<ExerciseTimer {...PLANK} onSetChange={onSetChange} />);
    await click(/start/i);
    await advance(5_000 + 20_000 + 400); // get ready + RIGHT hold

    expect(onSetChange).toHaveBeenLastCalledWith(1);
    expect(screen.getByText("Switch side")).toBeTruthy();
    expect(screen.getAllByText(String(SIDE_SWITCH_S)).length).toBeGreaterThan(0);

    // The switch ends on its own (timed work) and LEFT starts.
    await advance(SIDE_SWITCH_S * 1000 + 400);
    expect(screen.queryByText("Switch side")).toBeNull();
    expect(screen.getAllByText("LEFT").length).toBeGreaterThan(0);

    // After LEFT: the real set rest, a full minute.
    await advance(20_000 + 400);
    expect(onSetChange).toHaveBeenLastCalledWith(2);
    expect(screen.getByText("Rest")).toBeTruthy();
    // A full minute, give or take the tick the phases started on.
    expect(screen.getAllByText(/^(1:00|5\d)$/).length).toBeGreaterThan(0);
  });

  it("a bilateral exercise still rests the full set rest after every set", async () => {
    render(<ExerciseTimer {...PLANK} altSides={false} />);
    await click(/start/i);
    await advance(5_000 + 20_000 + 400);
    expect(screen.getByText("Rest")).toBeTruthy();
    expect(screen.getAllByText("1:00").length).toBeGreaterThan(0);
  });
});

describe("B404 — Previous phase at the start of a set", () => {
  it("goes back to the rest before it, and that rest leads back to the same set", async () => {
    const MANUAL = { workSeconds: 0, restBetweenRepsSeconds: 0, restBetweenSetsSeconds: 30, sets: 3, reps: 1 };
    render(<ExerciseTimer {...MANUAL} />);
    await click(/start/i);
    await click(/done set/i); // set 1 done → rest
    await click(/next phase/i); // skip the rest → set 2
    expect(screen.getAllByText(/Set 2/).length).toBeGreaterThan(0);

    await click(/previous phase/i); // back into the rest after set 1
    await click(/next phase/i); // and forward again
    expect(screen.getAllByText(/Set 2/).length).toBeGreaterThan(0);
    expect(screen.queryAllByText(/Set 3/)).toHaveLength(0);
  });
});
