/**
 * C203 / A-B9 — Boulder-specific phase tips.
 *
 * Static constants served client-side (no backend endpoint). A phase tip is
 * a one-per-phase high-level reminder, orthogonal to per-session process
 * cues (A141, see `backend/catalog/cues/v1/process_cues.json`).
 *
 * Displayed only when the user's goal discipline is "boulder" — lead
 * climbers get a different methodology focus and will have their own tips
 * catalogued separately in the future.
 *
 * Sources: Hörst 4-3-2-1 periodization, Seifert 2017, Ondra/Bachar process
 * focus, Draper 2006 (deload).
 */

export type BoulderPhaseId =
  | "base"
  | "strength_power"
  | "power_endurance"
  | "performance"
  | "deload";

export const BOULDER_PHASE_TIPS: Record<BoulderPhaseId, string> = {
  base: "Expand your movement vocabulary: try different styles (slabs, overhangs, dynamic, static) at easy grades. Technical volume now builds the foundation for future grades.",
  strength_power: "This is the limit project phase: few boulders at your max, long rest (3-5 min), maximum neural quality. If you can't give 100% on each attempt, you've done enough.",
  power_endurance: "Work on work capacity: boulder circuits, linked problems, density. The goal is maintaining quality movement under increasing fatigue.",
  performance: "Send your projects. Focus energy on the boulders that matter - simulate performance conditions (single attempt, full rest, pre-attempt visualization).",
  deload: "Easy, fun bouldering - explore new problems at low grades, play with unusual movements. Zero pressure, zero limit attempts. Let tendons and nervous system recover.",
};

export function getBoulderPhaseTip(phaseId: string | null | undefined): string | null {
  if (!phaseId) return null;
  return BOULDER_PHASE_TIPS[phaseId as BoulderPhaseId] ?? null;
}
