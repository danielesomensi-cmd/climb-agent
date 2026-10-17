/**
 * B380 — what a load number means.
 *
 * The engine tags external-load exercises with `load_unit`:
 * - "per_dumbbell": a pair of dumbbells, the number is ONE dumbbell;
 * - "implement":    one dumbbell / kettlebell / plate, the number is that implement;
 * - "total":        barbell, cable, machine — the whole load (also the meaning of
 *                   a missing field, i.e. every exercise before B380).
 *
 * Render-only: the number itself is never converted here.
 */

export type LoadUnit = "per_dumbbell" | "implement" | "total";

export function normalizeLoadUnit(value: unknown): LoadUnit {
  return value === "per_dumbbell" || value === "implement" ? value : "total";
}

/** First valid unit among the candidates (suggested block, instance, catalog). */
export function pickLoadUnit(...candidates: unknown[]): LoadUnit | undefined {
  for (const c of candidates) {
    if (c === "per_dumbbell" || c === "implement" || c === "total") return c;
  }
  return undefined;
}

/**
 * A suggested load, as shown on cards and in the player.
 * - per_dumbbell → "34 kg per dumbbell" (never "+": nothing is added to the body)
 * - implement    → "12 kg"
 * - total / missing → the pre-B380 rendering ("+34 kg" when `signed`).
 */
export function formatLoad(kg: number, unit?: LoadUnit | string | null, opts: { signed?: boolean } = {}): string {
  const u = normalizeLoadUnit(unit);
  if (u === "per_dumbbell") return `${kg} kg per dumbbell`;
  if (u === "implement") return `${kg} kg`;
  return opts.signed ? `+${kg} kg` : `${kg} kg`;
}

/** Label of the kg input. `fallback` is the label used for a total load. */
export function loadInputLabel(unit: LoadUnit | string | null | undefined, fallback: string): string {
  return normalizeLoadUnit(unit) === "per_dumbbell" ? "Load per dumbbell (kg)" : fallback;
}
