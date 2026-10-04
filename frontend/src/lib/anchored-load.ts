// B364 — anchored exercises (weighted pull-up / chin-up, max hangs 5"/7").
//
// For an athlete with a recent test the backend computes their load from the
// official max + the training load (`anchored_load`). These helpers keep the
// frontend side in one place: which exercises are anchored, and the notes the
// backend attaches to an anchored prescription (ceiling, fatigue, pain,
// re-entry) turned into short user-facing lines.

export const ANCHORED_EXERCISE_IDS: ReadonlySet<string> = new Set([
  "max_hang_5s",
  "max_hang_7s",
  "weighted_pullup",
  "weighted_chinup",
]);

export function isAnchoredExercise(exerciseId: string | null | undefined): boolean {
  return !!exerciseId && ANCHORED_EXERCISE_IDS.has(exerciseId);
}

type Obj = Record<string, unknown>;

function asObj(v: unknown): Obj | undefined {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Obj) : undefined;
}

/**
 * Notes for an anchored prescription. `src` is the object that carries the
 * backend fields: a planned instance's `suggested` (`ceiling_note`, `anchored`)
 * or a custom exercise resolved with `?date=` (same two fields).
 * Returns [] for anything that is not an anchored prescription.
 */
export function anchoredLoadNotes(src: Obj | null | undefined): string[] {
  if (!src) return [];
  const notes: string[] = [];
  const anchored = asObj(src.anchored);

  if (typeof src.ceiling_note === "string" && src.ceiling_note) {
    notes.push(src.ceiling_note);
  }
  if (!anchored) return notes;

  if (anchored.clamped === "fatigue_floor" || asObj(anchored.fatigue)) {
    notes.push(
      "3 hard sessions in the last 14 days: load set to the bottom of the phase range. Your max is unchanged.",
    );
  }
  const pain = asObj(anchored.pain);
  if (pain && typeof pain.score === "number") {
    const until = typeof pain.until === "string" ? ` until ${pain.until}` : "";
    notes.push(`Pain reported (${pain.score}/3): load reduced${until}.`);
  }
  const ramp = asObj(anchored.ramp);
  if (ramp && typeof ramp.factor === "number" && ramp.factor < 1 && typeof ramp.n === "number") {
    notes.push(
      `Back after a break (session ${ramp.n} of 3): capped at ${Math.round(ramp.factor * 100)}% of the usual ceiling.`,
    );
  }
  return notes;
}
