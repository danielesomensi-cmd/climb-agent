/**
 * B293 — profile sanity bounds, one source of truth for the wizard.
 *
 * Mirrors the server-side guard on POST /api/onboarding/complete
 * (`_validate_profile` in backend/api/routers/onboarding.py): reject outside,
 * never clamp silently. Weight/height feed the engine (assessment ratios,
 * hangboard added-load = target_total - bodyweight), so a 0 slipping through
 * becomes a corrupted baseline or a dangerous load prescription.
 */

export const PROFILE_BOUNDS = {
  weight_kg: { min: 30, max: 150, label: "Weight", unit: "kg" },
  height_cm: { min: 120, max: 220, label: "Height", unit: "cm" },
  age: { min: 1, max: 99, label: "Age", unit: "y" },
} as const;

export type ProfileFields = {
  name: string;
  age: number;
  weight_kg: number;
  height_cm: number;
};

/** Human-readable problems with the profile; empty array = valid. */
export function profileErrors(p: ProfileFields): string[] {
  const errs: string[] = [];
  if (!p.name.trim()) errs.push("Name is required");
  for (const key of ["age", "weight_kg", "height_cm"] as const) {
    const { min, max, label, unit } = PROFILE_BOUNDS[key];
    const val = p[key];
    if (!(typeof val === "number" && val >= min && val <= max)) {
      errs.push(`${label} must be between ${min} and ${max} ${unit}`);
    }
  }
  return errs;
}

/** Bound error for one numeric field, only once the user has typed something. */
export function fieldBoundError(
  key: keyof typeof PROFILE_BOUNDS,
  value: number,
): string | null {
  if (!value) return null; // untouched / cleared — Next stays disabled anyway
  const { min, max, label, unit } = PROFILE_BOUNDS[key];
  if (value < min || value > max) {
    return `${label} must be between ${min} and ${max} ${unit}`;
  }
  return null;
}
