"use client";

import { getAudioContext } from "@/lib/audio-unlock";
import { isSoundMuted } from "@/lib/sound-pref";

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
  await playTones(freq, duration, volume, [0]);
}

/**
 * B397 G4 — the same tone repeated at `offsets` (seconds), scheduled on the
 * audio clock in ONE call: three setTimeout'd beeps drift apart or get dropped
 * when iOS throttles timers, the audio clock does not.
 */
async function playTones(
  freq: number,
  duration: number,
  volume: number,
  offsets: number[],
): Promise<void> {
  // A306: the session's mute switch silences every beep.
  if (isSoundMuted()) return;
  try {
    const ctx = getAudioContext();
    // Must come before creating nodes: on iOS the context is suspended
    // whenever the app returns from the background, and a suspended context
    // plays nothing while reporting success.
    if (ctx.state !== "running") {
      await ctx.resume();
    }
    if (ctx.state !== "running") return;

    for (const offset of offsets) {
      const at = ctx.currentTime + offset;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(volume, at);
      gain.gain.exponentialRampToValueAtTime(0.001, at + duration);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(at);
      osc.stop(at + duration);
    }
  } catch {
    /* silent — audio is never worth breaking a workout over */
  }
}

/**
 * B397 G4 — a real vibration where the platform has one (Android). iOS has no
 * `navigator.vibrate` and its switch-tick haptic needs a user gesture, which a
 * timer callback is not: there the sound has to carry the cue.
 */
function vibrate(pattern: number | number[]): void {
  try {
    const nav = typeof navigator !== "undefined"
      ? (navigator as Navigator & { vibrate?: (p: number | number[]) => boolean })
      : undefined;
    if (typeof nav?.vibrate === "function") nav.vibrate(pattern);
  } catch {
    /* some browsers throw when the page is hidden — never worth an error */
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

/**
 * B397 G4 — "rest is over, go": the end of a rest the athlete must close with a
 * tap (rep-based work). It used to be the single 0.2 s transition beep, easy to
 * miss across a gym, so the rest silently ran long. Three louder beeps plus a
 * long vibration. The vibration ignores the mute switch on purpose (A306:
 * haptics are untouched by it).
 */
export function restOverCue(): void {
  vibrate([250, 120, 250, 120, 400]);
  void playTones(880, 0.18, 0.6, [0, 0.3, 0.6]);
}
