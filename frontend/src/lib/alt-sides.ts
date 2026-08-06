/**
 * B324: laterality helpers for exercises flagged `alt_sides` in the catalog
 * (Copenhagen plank, Pallof press, side-lying hip abduction…). These are run
 * once per side, so a prescription of "3 sets" means three sets RIGHT and three
 * sets LEFT.
 *
 * The convention is the guided player's (`exercise-timer.tsx`, B169-F3b) and is
 * reproduced here verbatim so the custom-session player behaves identically:
 * the set counter runs over doubled internal sets, odd = RIGHT, even = LEFT,
 * and the label shown to the user is the prescribed set number.
 */

export type Side = "RIGHT" | "LEFT";

/** Internal set count: doubled for alt_sides exercises, prescribed count otherwise. */
export function totalSetsWithSides(sets: number | null | undefined, altSides: boolean): number {
  const base = Math.max(1, sets ?? 1);
  return altSides ? base * 2 : base;
}

/** Side for a 1-based internal set number. Null when the exercise has no sides. */
export function sideForSet(currentSet: number, altSides: boolean): Side | null {
  if (!altSides) return null;
  return currentSet % 2 === 1 ? "RIGHT" : "LEFT";
}

/** Prescribed set number to display for a 1-based internal set number. */
export function displaySetNumber(currentSet: number, altSides: boolean): number {
  return altSides ? Math.ceil(currentSet / 2) : currentSet;
}
