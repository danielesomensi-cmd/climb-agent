"use client";

/**
 * A306 — one switch that silences every sound of a session: the timer beeps
 * (`beep.ts`) and the spoken cues (`voice-cues.ts`). Haptics are untouched —
 * the phone still vibrates, so a muted session at the gym keeps its cues.
 *
 * Stored per device (a gym at lunch vs home in the evening); the change is
 * broadcast so every toggle on screen shows the same state.
 */
const STORAGE_KEY = "climb_sound_muted";
export const SOUND_MUTED_EVENT = "climb-sound-muted";

export function isSoundMuted(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function setSoundMuted(muted: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, String(muted));
  } catch {
    /* private mode: the toggle still works for this page */
  }
  if (muted) {
    try {
      window.speechSynthesis?.cancel();
    } catch {
      /* no Web Speech API */
    }
  }
  window.dispatchEvent(new CustomEvent(SOUND_MUTED_EVENT, { detail: muted }));
}
