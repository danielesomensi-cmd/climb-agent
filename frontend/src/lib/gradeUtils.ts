// ── Grade display conversion (A-B2) ─────────────────────────────────────

const FONT_TO_V: Record<string, string> = {
  "4A": "V0", "4B": "V0", "4C": "V1",
  "5A": "V2", "5B": "V2", "5C": "V3",
  "6A": "V4", "6A+": "V4", "6B": "V4", "6B+": "V5", "6C": "V5", "6C+": "V6",
  "7A": "V6", "7A+": "V7", "7B": "V8", "7B+": "V8", "7C": "V9", "7C+": "V10",
  "8A": "V11", "8A+": "V12", "8B": "V13", "8B+": "V14", "8C": "V15", "8C+": "V16",
};

export type BoulderGradeSystem = "font" | "v_scale";

/**
 * Convert a Fontainebleau boulder grade to the user's preferred display system.
 * Engine always stores Font grades — this is render-only.
 */
export function displayBoulderGrade(
  fontGrade: string,
  preference: BoulderGradeSystem,
): string {
  if (preference === "font") return fontGrade;
  return FONT_TO_V[fontGrade.toUpperCase()] ?? fontGrade;
}

/** Ordered boulder grade options in Fontainebleau */
export const BOULDER_GRADE_OPTIONS = [
  "4A", "4B", "4C",
  "5A", "5A+", "5B", "5B+", "5C", "5C+",
  "6A", "6A+", "6B", "6B+", "6C", "6C+",
  "7A", "7A+", "7B", "7B+", "7C", "7C+",
  "8A", "8A+", "8B", "8B+", "8C", "8C+",
];

// ── Discipline-aware radar labels (A-B4) ─────────────────────────────────

export type Discipline = "lead" | "boulder" | "all_round";

const LEAD_LABELS: Record<string, string> = {
  finger_strength: "Finger Strength",
  pulling_strength: "Pulling Strength",
  power_endurance: "Power Endurance",
  technique: "Technique & Tactics",
  endurance: "Endurance",
};

const BOULDER_LABELS: Record<string, string> = {
  finger_strength: "Finger Strength",
  pulling_strength: "Contact Strength",
  power_endurance: "Work Capacity",
  technique: "Movement & Reading",
  endurance: "Recovery",
};

export function getRadarLabels(
  discipline: Discipline = "lead",
): Record<string, string> {
  return discipline === "boulder" ? BOULDER_LABELS : LEAD_LABELS;
}

export function getDiscipline(
  goalType?: string,
): Discipline {
  if (goalType === "boulder_grade") return "boulder";
  if (goalType === "all_round") return "all_round";
  return "lead";
}
