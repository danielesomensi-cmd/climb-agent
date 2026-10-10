/**
 * A309 — value logic of the params drawer's steppers, now that the value can
 * be typed as well as stepped. The −/+ semantics are unchanged from before;
 * a typed value is clamped to the same min/max the buttons respect.
 */

export interface StepperBounds {
  min: number;
  max: number;
  step: number;
  /** Below `min` (−) or an empty field means "not set" (null). */
  nullable?: boolean;
  /** Decimal places kept (0 = integers: sets, reps, seconds). */
  decimals?: number;
}

function roundTo(v: number, decimals: number): number {
  const f = 10 ** decimals;
  return Math.round(v * f) / f;
}

/** −/+ tap. Same as before A309: − below min → null when nullable, else min. */
export function stepValue(value: number | null, direction: -1 | 1, b: StepperBounds): number | null {
  const display = value ?? 0;
  const decimals = b.decimals ?? 0;
  if (direction === -1) {
    const next = roundTo(display - b.step, decimals);
    if (b.nullable && next < b.min) return null;
    return Math.max(b.min, next);
  }
  return Math.min(b.max, roundTo(display + b.step, decimals));
}

/**
 * Typed text → value. Accepts "32,5" as well as "32.5" (Italian keyboards).
 * Empty → null when nullable, otherwise the previous value; garbage → the
 * previous value; anything else is rounded and clamped to [min, max].
 */
export function parseStepperInput(text: string, previous: number | null, b: StepperBounds): number | null {
  const trimmed = text.trim().replace(",", ".");
  if (trimmed === "") return b.nullable ? null : previous;
  const n = Number(trimmed);
  if (!Number.isFinite(n)) return previous;
  return Math.min(b.max, Math.max(b.min, roundTo(n, b.decimals ?? 0)));
}
