"use client";

import { getAudioContext } from "@/lib/audio-unlock";

/**
 * A245 F-1 (F53) — the one implementation of the timer beeps.
 *
 * This was copied into six files (guided timer, circuit, mobility, tabata and
 * both session-play timers) and the copies had drifted. Two kinds of drift, one
 * of them audible:
 *
 *  - `custom-rest-timer` and `custom-exercise-step` were SYNCHRONOUS and bailed
 *    out with `if (ctx.state !== "running") return;` — they never got the
 *    `await ctx.resume()` fix the guided timer received. iOS suspends the audio
 *    context aggressively, so on iPhone those two timers were simply silent.
 *  - the transition beep existed as 0.2s/0.4 vol, 0.3s/0.4 and 0.3s/0.5,
 *    so the same event sounded different depending on which screen you were on.
 *
 * The resume-first version below is the correct one; the tones are the guided
 * timer's, which is the most used surface.
 */
export async function beep(freq: number, duration: number, volume: number): Promise<void> {
  try {
    const ctx = getAudioContext();
    // Must come before creating nodes: on iOS the context is suspended
    // whenever the app returns from the background, and a suspended context
    // plays nothing while reporting success.
    if (ctx.state !== "running") {
      await ctx.resume();
    }
    if (ctx.state !== "running") return;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  } catch {
    /* silent — audio is never worth breaking a workout over */
  }
}

/** Short high tick for the 3-2-1 countdown. */
export function countdownTick(): void {
  void beep(660, 0.08, 0.25);
}

/** Longer beep marking a phase change (work → rest, exercise → exercise). */
export function transitionBeep(): void {
  void beep(880, 0.2, 0.4);
}

/** Sustained tone for "the whole thing is finished". */
export function longBeep(): void {
  void beep(660, 0.6, 0.5);
}

/** Soft low tick at the half-way point of a long interval (tabata). */
export function halfwayTick(): void {
  void beep(550, 0.06, 0.15);
}
