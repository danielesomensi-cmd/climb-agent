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
  pulling_strength: "Contact",
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
      low: "Your fingers are the bottleneck. You're falling off holds your body could otherwise use.",
    },
    boulder: {
      label: "Finger Strength",
      description: "How hard you can grip a hold at maximum effort. Measured by your max hang on a 20mm edge for 7 seconds — the #1 predictor of bouldering grade across all ability levels.",
      low: "Your fingers are the bottleneck. You're falling off holds your body could otherwise use.",
    },
  },
  pulling_strength: {
    lead: {
      label: "Pulling Strength",
      description: "How much force your arms and back can generate to pull through powerful moves and lock off on steep terrain. Measured by your best weighted pull-up.",
      low: "You struggle on steep or powerful sections even when your fingers can hold on. You might pump out early on overhangs or fail to make dynamic moves.",
    },
    boulder: {
      label: "Contact",
      description: "How explosively you can latch holds and pull through big moves. Measured by your best weighted pull-up — a proxy for the raw upper-body power that bouldering demands.",
      low: "You struggle on steep or powerful sections even when your fingers can hold on. You fail to make dynamic moves that are within your finger strength.",
    },
  },
  power_endurance: {
    lead: {
      label: "Power Endurance",
      description: "How long you can sustain hard moves before the pump shuts you down. Your ability to keep climbing through sustained crux sections without your forearms giving out.",
      low: "You can do the moves individually but can't link them. You pump off above the crux.",
    },
    boulder: {
      label: "Work Capacity",
      description: "How well you handle multiple hard moves in a row — the difference between sticking the first move and linking the whole problem. Your ability to produce force repeatedly across a sequence.",
      low: "You can do the moves individually but can't link them. You fall on move 5 of a problem whose moves you can all do separately.",
    },
  },
  technique: {
    lead: {
      label: "Technique & Tactics",
      description: "How efficiently you climb and how well you read routes. A big gap between your onsight and redpoint grades suggests there's free performance hiding in better movement and route-reading skills.",
      low: "You're stronger than your grades suggest. You have the fitness to climb harder, but you're burning energy on poor footwork or missed sequences. Often the fastest axis to improve.",
    },
    boulder: {
      label: "Movement & Reading",
      description: "How efficiently you move on the wall and how quickly you figure out the right beta. Good movement skills mean less energy wasted and faster sends.",
      low: "You're stronger than your grades suggest. You have the fitness to climb harder, but you're burning energy on poor body positioning or missed sequences. Often the fastest axis to improve.",
    },
  },
  endurance: {
    lead: {
      label: "Endurance",
      description: "Your ability to sustain moderate effort over a full route without accumulating pump. This is about capillary density and aerobic fitness — can you cruise the easy sections and arrive at the crux fresh?",
      low: "You run out of gas before the chains. You get pumped on sections well below your max.",
    },
    boulder: {
      label: "Recovery",
      description: "How fast you bounce back between attempts. Good recovery means you can try your project again in 3-5 minutes feeling fresh, instead of waiting 15 minutes and still feeling the last attempt.",
      low: "Your session falls apart after a few hard attempts because you can't recover between burns.",
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
