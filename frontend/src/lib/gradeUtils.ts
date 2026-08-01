// ── Grade display conversion (A-B2; B248 corrected against intl. standard) ─

/**
 * Fontainebleau → V-scale conversion.
 *
 * Source: Wikipedia "Grade (climbing)" comparison table + Mountain Project
 * boulder-grade conversion (international consensus). Pre-B248, this table
 * was inflated by +1 grade across 5A..7A (e.g. 7A → V7 instead of V6); fixed
 * 2026-05-05 to align with the standard. 7A+..8C+ were already correct.
 *
 * Engine always stores Fontainebleau; this is render-only.
 */
const FONT_TO_V: Record<string, string> = {
  "4A": "V0", "4B": "V0", "4C": "V1",
  "5A": "V1", "5A+": "V1", "5B": "V2", "5B+": "V2", "5C": "V2", "5C+": "V3",
  "6A": "V3", "6A+": "V3", "6B": "V4", "6B+": "V4", "6C": "V5", "6C+": "V5",
  "7A": "V6", "7A+": "V7", "7B": "V8", "7B+": "V8", "7C": "V9", "7C+": "V10",
  "8A": "V11", "8A+": "V12", "8B": "V13", "8B+": "V14", "8C": "V15", "8C+": "V16",
};

/**
 * V-scale → canonical Fontainebleau storage value.
 *
 * Convention: pick the *lowest* Font that maps to a given V (so a user picking
 * V5 stores 6C, not 6C+ — onboarding never inflates the stored grade).
 * Round-trip via FONT_TO_V is preserved for every V0..V16.
 */
const V_TO_FONT: Record<string, string> = {
  "V0": "4A", "V1": "5A", "V2": "5B", "V3": "5C+", "V4": "6B",
  "V5": "6C", "V6": "7A", "V7": "7A+", "V8": "7B", "V9": "7C",
  "V10": "7C+", "V11": "8A", "V12": "8A+", "V13": "8B", "V14": "8B+",
  "V15": "8C", "V16": "8C+",
};

export const V_SCALE_GRADES = [
  "V0", "V1", "V2", "V3", "V4", "V5", "V6", "V7",
  "V8", "V9", "V10", "V11", "V12", "V13", "V14", "V15",
];

/** Convert a V-scale grade to its canonical Fontainebleau storage value */
export function vScaleToFont(vGrade: string): string {
  return V_TO_FONT[vGrade] ?? vGrade;
}

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

/**
 * Ordered French lead grade options.
 *
 * A262: exported for the public assessment page. Must stay identical to the
 * backend's `GRADE_ORDER` (assessment_v1.py) — offering a grade the engine does
 * not know is the B302 failure mode: `grade_index` misses, the profile is
 * computed against index 0 and the user gets a confidently wrong answer.
 */
export const LEAD_GRADE_OPTIONS = [
  "5a", "5a+", "5b", "5b+", "5c", "5c+",
  "6a", "6a+", "6b", "6b+", "6c", "6c+",
  "7a", "7a+", "7b", "7b+", "7c", "7c+",
  "8a", "8a+", "8b", "8b+", "8c", "8c+",
  "9a", "9a+",
];

/** Ordered boulder grade options in Fontainebleau */
export const BOULDER_GRADE_OPTIONS = [
  "4A", "4B", "4C",
  "5A", "5A+", "5B", "5B+", "5C", "5C+",
  "6A", "6A+", "6B", "6B+", "6C", "6C+",
  "7A", "7A+", "7B", "7B+", "7C", "7C+",
  "8A", "8A+", "8B", "8B+", "8C", "8C+",
];

// ── Canonical Fontainebleau/French grade ordering (A227 / B2) ────────────
//
// One ordered scale covering BOTH Font boulder (4, 4+, 5+, 6a…8c+) and French
// sport (4a…9c) tokens, lowest → hardest. Never V-scale. Use for sorting and
// "hardest" comparisons instead of lexicographic `.sort()`, which mis-ranks
// across number/letter/+ boundaries. Within each discipline the order is exact;
// the bare-number Font tokens (4, 4+) sort just below the lettered French ones
// of the same number — a deterministic, harmless cross-scale placement.
const GRADE_ORDER_CANONICAL: string[] = [
  "3",
  "4", "4+", "4a", "4b", "4c",
  "5", "5+", "5a", "5a+", "5b", "5b+", "5c", "5c+",
  "6a", "6a+", "6b", "6b+", "6c", "6c+",
  "7a", "7a+", "7b", "7b+", "7c", "7c+",
  "8a", "8a+", "8b", "8b+", "8c", "8c+",
  "9a", "9a+", "9b", "9b+", "9c",
];

const _GRADE_RANK: Record<string, number> = Object.fromEntries(
  GRADE_ORDER_CANONICAL.map((g, i) => [g, i]),
);

/** Ordinal rank of a grade in the canonical Font/French scale. Unknown/empty
 *  grades rank -1 (sort below everything). Case-insensitive. */
export function gradeRank(grade: string): number {
  if (!grade) return -1;
  const r = _GRADE_RANK[grade.toLowerCase()];
  return r === undefined ? -1 : r;
}

/** Compare two grades by canonical difficulty: negative if a < b. */
export function compareGrades(a: string, b: string): number {
  return gradeRank(a) - gradeRank(b);
}

/** Hardest grade in a list (canonical), or null if none rank. */
export function hardestGrade(grades: string[]): string | null {
  let best: string | null = null;
  let bestRank = -1;
  for (const g of grades) {
    const r = gradeRank(g);
    if (r > bestRank) {
      bestRank = r;
      best = g;
    }
  }
  return best;
}

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
  pulling_strength: "Pulling Power",
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

// ── Axis descriptions for tooltips (A-B4b) ──────────────────────────────

interface AxisInfo {
  label: string;
  description: string;
  low: string;
}

export const AXIS_DESCRIPTIONS: Record<string, { lead: AxisInfo; boulder: AxisInfo }> = {
  finger_strength: {
    lead: {
      label: "Finger Strength",
      description: "How hard you can grip a hold with maximum effort. Measured by how much weight you can hang on a standard 20mm edge for 7 seconds — the single strongest predictor of climbing grade.",
      low: "A lower score means your fingers are the limiter right now — the axis where focused hangboard work buys the most progress toward {target}.",
    },
    boulder: {
      label: "Finger Strength",
      description: "How hard you can grip a hold at maximum effort. Measured by your max hang on a 20mm edge for 7 seconds — the #1 predictor of bouldering grade across all ability levels.",
      low: "A lower score means your fingers are the limiter — focused hangboard work is where you'll gain the most toward {target}.",
    },
  },
  pulling_strength: {
    lead: {
      label: "Pulling Strength",
      description: "How much force your arms and back can generate to pull through powerful moves and lock off on steep terrain. Measured by your best weighted pull-up.",
      low: "A lower score means pulling power holds you back on steep, powerful moves — general strength work is where you'll gain most toward {target}.",
    },
    boulder: {
      label: "Pulling Power",
      description: "How much explosive pulling force your arms and back can generate for powerful moves on steep terrain. Measured by your best weighted pull-up.",
      low: "A lower score means pulling power limits you on steep, powerful moves — max strength work is your biggest lever toward {target}.",
    },
  },
  power_endurance: {
    lead: {
      label: "Power Endurance",
      description: "How long you can sustain hard moves before the pump shuts you down. Your ability to keep climbing through sustained crux sections without your forearms giving out.",
      low: "A lower score means linking sustained cruxes is your ceiling — power-endurance intervals are where training pays off most toward {target}.",
    },
    boulder: {
      label: "Work Capacity",
      description: "How well you handle multiple hard moves in a row — the difference between sticking the first move and linking the whole problem. Your ability to produce force repeatedly across a sequence.",
      low: "A lower score means linking sequences is your ceiling — volume and work-capacity training is where you'll gain most toward {target}.",
    },
  },
  technique: {
    lead: {
      label: "Technique & Tactics",
      description: "How efficiently you climb and how well you read routes. A big gap between your onsight and redpoint grades suggests there's free performance hiding in better movement and route-reading skills.",
      low: "A lower score means there's free performance in better movement and route-reading — often the fastest axis to improve on the way to {target}.",
    },
    boulder: {
      label: "Movement & Reading",
      description: "How efficiently you move on the wall and how quickly you figure out the right beta. Good movement skills mean less energy wasted and faster sends.",
      low: "A lower score means better movement and beta-reading unlock grades you're already strong enough for — often the fastest gains toward {target}.",
    },
  },
  endurance: {
    lead: {
      label: "Endurance",
      description: "Your ability to sustain moderate effort over a full route without accumulating pump. This is about capillary density and aerobic fitness — can you cruise the easy sections and arrive at the crux fresh?",
      low: "A lower score means aerobic base is your gap — easy mileage and capillarity work is where steady progress toward {target} comes from.",
    },
    boulder: {
      label: "Recovery",
      description: "How fast you bounce back between attempts. Good recovery means you can try your project again in 3-5 minutes feeling fresh, instead of waiting 15 minutes and still feeling the last attempt.",
      low: "A lower score means recovery between attempts limits your sessions — aerobic and rest-management work is your lever toward {target}.",
    },
  },
};

export function getAxisDescription(
  axis: string,
  discipline: Discipline = "lead",
): AxisInfo | undefined {
  const entry = AXIS_DESCRIPTIONS[axis];
  if (!entry) return undefined;
  return discipline === "boulder" ? entry.boulder : entry.lead;
}
