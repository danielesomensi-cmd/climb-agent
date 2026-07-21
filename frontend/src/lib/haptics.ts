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
 * Two engines, one entry point:
 *
 *  - Android (and anything else with `navigator.vibrate`): a real vibration.
 *  - iOS 17.4+ Safari/PWA: Apple never exposed the taptic engine to the web,
 *    BUT toggling an `<input type="checkbox" switch>` via its label fires the
 *    native switch haptic tick. We keep one such element hidden in the DOM and
 *    click its label programmatically. The element must NOT be `display:none`
 *    (iOS ignores toggles on undisplayed elements) — standard visually-hidden
 *    CSS instead.
 *  - Anything supporting neither: silent no-op, never an error.
 *
 * The tick fires on `pointerdown` (see Button) so it lands while the finger is
 * still on the glass — a haptic 200ms after lift-off feels like a glitch, not
 * a confirmation.
 */

type VibratePattern = number | number[];

function canVibrate(): boolean {
  return (
    typeof navigator !== "undefined" &&
    typeof (navigator as Navigator & { vibrate?: unknown }).vibrate === "function"
  );
}

// ---------------------------------------------------------------------------
// iOS switch-toggle fallback
// ---------------------------------------------------------------------------

let switchLabel: HTMLLabelElement | null = null;

/**
 * Lazy singleton: one hidden switch for the whole app, created on first use
 * inside a user gesture (iOS requires user activation for the haptic anyway,
 * so creating it lazily costs nothing).
 */
function ensureSwitch(): HTMLLabelElement | null {
  if (typeof document === "undefined" || !document.body) return null;
  if (switchLabel && switchLabel.isConnected) return switchLabel;

  const label = document.createElement("label");
  label.setAttribute("aria-hidden", "true");
  // Visually hidden, NOT display:none — iOS skips the haptic on undisplayed
  // elements. `fixed` keeps it out of layout; pointer-events:none keeps real
  // taps from ever landing on it (programmatic .click() skips hit-testing).
  Object.assign(label.style, {
    position: "fixed",
    top: "0",
    left: "0",
    width: "1px",
    height: "1px",
    overflow: "hidden",
    clipPath: "inset(50%)",
    pointerEvents: "none",
    opacity: "0",
  });

  const input = document.createElement("input");
  input.type = "checkbox";
  // Safari's proprietary switch rendering — this is what carries the haptic.
  input.setAttribute("switch", "");
  input.tabIndex = -1;
  label.appendChild(input);

  document.body.appendChild(label);
  switchLabel = label;
  return label;
}

function switchTick(): void {
  try {
    ensureSwitch()?.click();
  } catch {
    /* a buzz is never worth breaking a tap over */
  }
}

function buzz(pattern: VibratePattern): void {
  if (canVibrate()) {
    try {
      (navigator as Navigator & { vibrate: (p: VibratePattern) => boolean }).vibrate(pattern);
    } catch {
      /* some browsers throw when the page is not visible — never worth an error */
    }
    return;
  }
  // No vibration API (iOS): fall back to the switch-toggle tick. Intensity
  // cannot be modulated this way — every pattern degrades to one tick.
  switchTick();
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
