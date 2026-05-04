/**
 * B247 — Guided session countdown beep dedup gate.
 *
 * Pre-fix: exercise-timer.tsx used a useEffect([secondsLeft]) gate with a 1s
 * setInterval. Any tick drift on iOS PWA could land Math.ceil(remainingMs/1000)
 * outside the (0, 3000] ms window and silently drop 1–3 of the countdown beeps.
 *
 * Post-fix: the countdown is fired inline in the tick handler at 200ms cadence,
 * gated by `shouldFireCountdownBeep` + a `lastBeepedSecRef` dedup ref reset on
 * every phase transition.
 *
 * These tests pin the pure decision function so any future refactor that
 * loosens the gate (e.g. dropping the dedup, widening the range, ignoring the
 * paused flag) is caught immediately.
 */
import { describe, it, expect } from "vitest";
import { shouldFireCountdownBeep } from "../exercise-timer";

const ACTIVE = true;
const NOT_PAUSED = false;

describe("shouldFireCountdownBeep (B247 dedup gate)", () => {
  it("T1 happy path: fires once at sec=3, sec=2, sec=1 in sequence", () => {
    // Phase start: lastBeepedSec = -1 (set by startCountdown).
    expect(shouldFireCountdownBeep(3, -1, NOT_PAUSED, ACTIVE)).toBe(true);
    // Caller has updated lastBeeped to 3, then to 2 after firing.
    expect(shouldFireCountdownBeep(2, 3, NOT_PAUSED, ACTIVE)).toBe(true);
    expect(shouldFireCountdownBeep(1, 2, NOT_PAUSED, ACTIVE)).toBe(true);
  });

  it("T2 tick-skip resilience: when a tick lands in sec=1 after skipping 3,2 windows, beep still fires", () => {
    // Pre-fix bug surface: on a 1s tick, drift could land sec directly at 1 with
    // no tick ever having computed 3 or 2. Post-fix dedup is initialised to -1,
    // so the first sec value in {1,2,3} unconditionally fires.
    expect(shouldFireCountdownBeep(1, -1, NOT_PAUSED, ACTIVE)).toBe(true);
    // Subsequent ticks within the same sec=1 window must no-op.
    expect(shouldFireCountdownBeep(1, 1, NOT_PAUSED, ACTIVE)).toBe(false);
  });

  it("T3 idempotency: multiple ticks within the same sec window fire only once", () => {
    // At 200ms tick rate, ~5 ticks land in each 1-s window. Without dedup we'd
    // get 15 countdown beeps per phase; with dedup we get exactly 3.
    expect(shouldFireCountdownBeep(3, -1, NOT_PAUSED, ACTIVE)).toBe(true);
    expect(shouldFireCountdownBeep(3, 3, NOT_PAUSED, ACTIVE)).toBe(false);
    expect(shouldFireCountdownBeep(3, 3, NOT_PAUSED, ACTIVE)).toBe(false);
    expect(shouldFireCountdownBeep(3, 3, NOT_PAUSED, ACTIVE)).toBe(false);
    expect(shouldFireCountdownBeep(3, 3, NOT_PAUSED, ACTIVE)).toBe(false);
  });

  it("T4 reset across phases: lastBeepedSec=-1 (set by startCountdown / handleReset) re-arms the gate", () => {
    // End of phase 1: sec=1 already fired, ref now holds 1.
    expect(shouldFireCountdownBeep(1, 1, NOT_PAUSED, ACTIVE)).toBe(false);
    // Phase 2 starts → startCountdown resets lastBeeped to -1.
    expect(shouldFireCountdownBeep(3, -1, NOT_PAUSED, ACTIVE)).toBe(true);
  });

  it("does NOT fire when paused", () => {
    expect(shouldFireCountdownBeep(3, -1, /* paused */ true, ACTIVE)).toBe(false);
    expect(shouldFireCountdownBeep(2, -1, /* paused */ true, ACTIVE)).toBe(false);
    expect(shouldFireCountdownBeep(1, -1, /* paused */ true, ACTIVE)).toBe(false);
  });

  it("does NOT fire outside the 1..3 window", () => {
    expect(shouldFireCountdownBeep(4, -1, NOT_PAUSED, ACTIVE)).toBe(false);
    expect(shouldFireCountdownBeep(10, -1, NOT_PAUSED, ACTIVE)).toBe(false);
    expect(shouldFireCountdownBeep(0, -1, NOT_PAUSED, ACTIVE)).toBe(false);
    expect(shouldFireCountdownBeep(-1, -1, NOT_PAUSED, ACTIVE)).toBe(false);
  });

  it("does NOT fire when phase is idle / complete / manual-work (caller passes inActiveCountdownPhase=false)", () => {
    expect(shouldFireCountdownBeep(2, -1, NOT_PAUSED, /* inActive */ false)).toBe(false);
    expect(shouldFireCountdownBeep(3, -1, NOT_PAUSED, /* inActive */ false)).toBe(false);
    expect(shouldFireCountdownBeep(1, -1, NOT_PAUSED, /* inActive */ false)).toBe(false);
  });
});
