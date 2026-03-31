/**
 * A-B5: Discipline-aware phase display labels.
 * Centralizes PHASE_LABELS that were previously duplicated in 5 files.
 */

const LEAD_PHASE_LABELS: Record<string, string> = {
  base: "Endurance Base",
  strength_power: "Strength & Power",
  power_endurance: "Power Endurance",
  performance: "Performance",
  deload: "Deload",
};

const BOULDER_PHASE_LABELS: Record<string, string> = {
  base: "Movement & Volume Base",
  strength_power: "Max Strength & Power",
  power_endurance: "Work Capacity",
  performance: "Projecting & Peak",
  deload: "Deload",
};

/** Short labels for tight spaces (e.g. macrocycle timeline bar). */
const LEAD_PHASE_SHORT: Record<string, string> = {
  base: "Base",
  strength_power: "Strength",
  power_endurance: "Power End.",
  performance: "Performance",
  deload: "Deload",
};

const BOULDER_PHASE_SHORT: Record<string, string> = {
  base: "Volume",
  strength_power: "Max Str.",
  power_endurance: "Work Cap.",
  performance: "Projecting",
  deload: "Deload",
};

type Discipline = "lead" | "boulder" | "all_round";

export function getPhaseName(
  phaseId: string,
  discipline: Discipline = "lead",
): string {
  const labels =
    discipline === "boulder" || discipline === "all_round"
      ? BOULDER_PHASE_LABELS
      : LEAD_PHASE_LABELS;
  return labels[phaseId] ?? phaseId.replace(/_/g, " ");
}

export function getPhaseNameShort(
  phaseId: string,
  discipline: Discipline = "lead",
): string {
  const labels =
    discipline === "boulder" || discipline === "all_round"
      ? BOULDER_PHASE_SHORT
      : LEAD_PHASE_SHORT;
  return labels[phaseId] ?? phaseId.replace(/_/g, " ");
}
