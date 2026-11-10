// A325 — a session duration is a measure only while it is plausible.
// Mirror of backend/engine/session_duration.py (the server enforces it too):
// the players time a session on the wall clock, and a player left open
// overnight is not a 10-hour session.

/** Longest indoor session taken as real (seconds). */
export const MAX_SESSION_DURATION_S = 5 * 3600;

/** `seconds` when it is a real duration within the bound, else undefined. */
export function plausibleDuration(seconds: number | null | undefined): number | undefined {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return undefined;
  return seconds <= MAX_SESSION_DURATION_S ? seconds : undefined;
}

/** Wall-clock seconds since `startedAtMs`, or undefined when not a real session length. */
export function elapsedDuration(startedAtMs: number, nowMs: number = Date.now()): number | undefined {
  if (!Number.isFinite(startedAtMs) || startedAtMs <= 0) return undefined;
  return plausibleDuration(Math.max(0, Math.floor((nowMs - startedAtMs) / 1000)));
}
