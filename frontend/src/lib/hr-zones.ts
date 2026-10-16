/**
 * A316 — heart-rate bands in bpm, display only.
 *
 * The catalog carries the band as % of HRmax (`hr_target` on the exercise);
 * the athlete's HRmax is `body.hr_max_bpm`. Mirrors `backend/engine/hr_zones.py`.
 * No age formula: without a recorded HRmax the band stays a percentage.
 */

export type HrTarget = {
  basis?: "hr_max";
  work_pct: [number, number];
  recovery_pct?: [number, number];
};

export const HR_MAX_MIN = 120;
export const HR_MAX_MAX = 230;
export const HR_REST_MIN = 30;
export const HR_REST_MAX = 110;

export function validHrMax(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const v = Math.round(value);
  return v >= HR_MAX_MIN && v <= HR_MAX_MAX ? v : null;
}

/** Never outside the % band: low end rounds up, high end down (same as the backend). */
export function bpmBand(hrMax: number, pct: [number, number]): [number, number] {
  const lo = Math.round(pct[0]);
  const hi = Math.round(pct[1]);
  return [Math.ceil((hrMax * lo) / 100), Math.floor((hrMax * hi) / 100)];
}

/** Read HRmax from a user state: top-level `body` first, then `assessment.body`. */
export function hrMaxFromState(state: unknown): number | null {
  const s = (state ?? {}) as { body?: { hr_max_bpm?: unknown }; assessment?: { body?: { hr_max_bpm?: unknown } } };
  return validHrMax(s.body?.hr_max_bpm) ?? validHrMax(s.assessment?.body?.hr_max_bpm);
}

/**
 * Lines to show under an exercise, e.g. ["Work 171-180 bpm", "Recovery 124-142 bpm"].
 * Without HRmax: ["Work 90-95% HRmax", ...] and a hint to set it in Settings.
 */
export function hrTargetLines(target: HrTarget | null | undefined, hrMax: number | null): string[] {
  if (!target || !Array.isArray(target.work_pct)) return [];
  const fmt = (pct: [number, number]) =>
    hrMax != null ? `${bpmBand(hrMax, pct)[0]}-${bpmBand(hrMax, pct)[1]} bpm` : `${pct[0]}-${pct[1]}% HRmax`;
  const lines = [`${target.recovery_pct ? "Work" : "Target"} ${fmt(target.work_pct)}`];
  if (target.recovery_pct) lines.push(`Recovery ${fmt(target.recovery_pct)}`);
  return lines;
}
