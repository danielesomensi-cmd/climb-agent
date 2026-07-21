"use client";

/**
 * A247 — tactile confirmation that a tap registered.
 *
 * During a guided session the phone is on the floor, hands are chalked and
 * you are breathing hard. A button that changes colour for 100ms while you are
 * looking away tells you nothing, and the app's own answer to "did that work?"
 * used to be "scroll up and check" — which is precisely the friction this
 * removes.
 *
 * `navigator.vibrate` is a no-op on iOS Safari (Apple does not expose the
 * taptic engine to the web). It is still worth calling — it works on Android,
 * which is half the userbase — but it must NEVER be the only signal. The
 * visual `active:` state and, in the guided flow, scrolling the new exercise
 * into view are what carry iOS.
 */

type VibratePattern = number | number[];

function canVibrate(): boolean {
  return (
    typeof navigator !== "undefined" &&
    typeof (navigator as Navigator & { vibrate?: unknown }).vibrate === "function"
  );
}

function buzz(pattern: VibratePattern): void {
  if (!canVibrate()) return;
  try {
    (navigator as Navigator & { vibrate: (p: VibratePattern) => boolean }).vibrate(pattern);
  } catch {
    /* some browsers throw when the page is not visible — never worth an error */
  }
}

/** A single short tick: "I registered your tap." */
export function tapFeedback(): void {
  buzz(15);
}

/** Slightly firmer: a step is complete and the screen is about to change. */
export function confirmFeedback(): void {
  buzz(30);
}

/** Double pulse for the end of something (session or circuit finished). */
export function completeFeedback(): void {
  buzz([120, 80, 120]);
}
