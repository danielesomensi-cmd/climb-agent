/**
 * A215 — Founding Climber config
 *
 * Hardcoded constants for launch. Update manually when Stripe dashboard
 * shows real Founding subscriber count. Post-launch we may expose
 * `/api/subscription/founding-spots` if the dynamic signal proves useful.
 */

export const FOUNDING_SPOTS_TOTAL = 20;
export const FOUNDING_SPOTS_LEFT = 20;

/**
 * Badge copy for Founding card:
 * - if all spots still open → "20 spots available · Limited"
 * - once at least one taken  → "Only N of 20 spots left"
 */
export function foundingBadgeCopy(): string {
  if (FOUNDING_SPOTS_LEFT >= FOUNDING_SPOTS_TOTAL) {
    return `${FOUNDING_SPOTS_TOTAL} spots available · Limited`;
  }
  return `Only ${FOUNDING_SPOTS_LEFT} of ${FOUNDING_SPOTS_TOTAL} spots left`;
}
