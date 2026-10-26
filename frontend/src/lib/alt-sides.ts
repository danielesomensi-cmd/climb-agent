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

/**
 * B404: the pause between RIGHT and LEFT of one prescribed set. The players
 * used to charge the full set rest there too, so a 3x20s side plank with 60s
 * rest ran five 60s rests instead of two: each side rested more than twice the
 * prescription. The other side's work already is the first side's rest, and
 * contralateral fatigue is trivial for strength (Behm et al. 2021), so the set
 * rest now comes only after LEFT. On rep-based work the switch still ends on a
 * tap (B350), so a heavy split squat starts when the athlete is ready. Same
 * value as SIDE_SWITCH_S in backend/engine/custom_session.py.
 */
export const SIDE_SWITCH_S = 15;

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

/**
 * B404: rest after a 1-based internal set — the side switch after RIGHT, the
 * set rest after LEFT (and after every set of a bilateral exercise). The switch
 * is never longer than the set rest; with no set rest (a stretch) it is still
 * there, because changing sides takes time.
 */
export function restAfterSet(currentSet: number, altSides: boolean, restBetweenSets: number): number {
  return isSideSwitch(currentSet, altSides) ? sideSwitchSeconds(restBetweenSets) : restBetweenSets;
}

/** B404: the side switch for a given set rest. */
export function sideSwitchSeconds(restBetweenSets: number): number {
  return restBetweenSets > 0 ? Math.min(SIDE_SWITCH_S, restBetweenSets) : SIDE_SWITCH_S;
}

/** B404: true while the rest after `currentSet` is a side switch. */
export function isSideSwitch(currentSet: number, altSides: boolean): boolean {
  return altSides && currentSet % 2 === 1;
}
