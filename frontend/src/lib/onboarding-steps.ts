/**
 * A245 Phase D — the wizard's step order, in one place.
 *
 * `welcome` is deliberately NOT counted (F45): it is a hero screen with no
 * input, and the indicator hides itself there. Counting it made the first
 * screen the user actually fills in announce itself as "2 / 14", which reads
 * as "you already missed one".
 */
export const ONBOARDING_STEPS = [
  "install",
  "profile",
  "experience",
  "discipline",
  "grades",
  "goals",
  "weaknesses",
  "tests",
  "limitations",
  "locations",
  "availability",
  "trips",
  "review",
] as const;

export type OnboardingStep = (typeof ONBOARDING_STEPS)[number];

/** Index of the step a pathname belongs to, or -1. */
export function stepIndexOf(pathname: string): number {
  return ONBOARDING_STEPS.findIndex((s) => pathname.includes(s));
}

export function stepPath(step: string): string {
  return `/onboarding/${step}`;
}
