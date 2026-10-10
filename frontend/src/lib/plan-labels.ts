/**
 * A311 — human labels for the /plan page.
 *
 * The phase cards used to print engine enums as-is: `intensity_cap` ("max"),
 * `session_pool` ids with underscores swapped for spaces, and domain weights as
 * a mono percentage grid. Pure helpers here so the wording is unit-tested and
 * the page only renders.
 */

import type { Macrocycle } from "@/lib/types";
import { formatSessionName } from "@/lib/format";
import { getPhaseName } from "@/lib/phase-labels";
import { getPhaseAtWeek } from "@/lib/phase-progress";

type Discipline = "lead" | "boulder" | "all_round";

/** Engine `PHASE_INTENSITY_CAP` values (macrocycle_v1.py) → display label. */
const INTENSITY_CAP_LABELS: Record<string, string> = {
  low: "Low intensity",
  medium: "Moderate intensity",
  high: "High intensity",
  max: "Max intensity",
};

export function getIntensityCapLabel(cap: string | null | undefined): string {
  if (!cap) return "";
  return INTENSITY_CAP_LABELS[cap] ?? formatSessionName(cap);
}

const DOMAIN_LABELS: Record<string, string> = {
  finger_strength: "Finger strength",
  pulling_strength: "Pulling strength",
  power_endurance: "Power endurance",
  technique: "Technique",
  endurance: "Endurance",
  power: "Power",
  strength: "Strength",
  conditioning: "Conditioning",
  flexibility: "Flexibility",
  prehab: "Prehab",
};

export function getDomainLabel(domain: string): string {
  return DOMAIN_LABELS[domain] ?? formatSessionName(domain);
}

export interface DomainWeightRow {
  domain: string;
  label: string;
  /** 0–100, rounded. */
  pct: number;
}

/**
 * Domain weights (fractions, 0–1) → rows sorted heaviest first, ties by label
 * so the order is stable. Non-numeric or negative weights read as 0; anything
 * above 1 is clamped so a bar never overflows its track.
 */
export function domainWeightRows(weights: Record<string, number>): DomainWeightRow[] {
  return Object.entries(weights)
    .map(([domain, w]) => {
      const n = typeof w === "number" && Number.isFinite(w) ? w : 0;
      const pct = Math.round(Math.min(Math.max(n, 0), 1) * 100);
      return { domain, label: getDomainLabel(domain), pct };
    })
    .sort((a, b) => b.pct - a.pct || a.label.localeCompare(b.label));
}

/** Catalog session name when the catalog has one, else the prettified id. */
export function getSessionLabel(
  sessionId: string,
  names: ReadonlyMap<string, string> | null | undefined,
): string {
  const name = names?.get(sessionId)?.trim();
  return name ? name : formatSessionName(sessionId);
}

export interface CyclePosition {
  week: number;
  totalWeeks: number;
  phaseId: string | null;
  phaseLabel: string | null;
  /** Weeks left in the current phase, this one included (≥1), or null. */
  weeksLeftInPhase: number | null;
}

/**
 * Where the athlete is in the cycle. `week` must come from
 * `computeCurrentWeek` — the same pause-aware number /week uses — so the two
 * pages never disagree.
 */
export function getCyclePosition(
  macrocycle: Macrocycle,
  week: number,
  discipline: Discipline = "lead",
): CyclePosition {
  const at = getPhaseAtWeek(macrocycle, week);
  return {
    week,
    totalWeeks: macrocycle.total_weeks,
    phaseId: at?.phase.phase_id ?? null,
    phaseLabel: at ? getPhaseName(at.phase.phase_id, discipline) : null,
    weeksLeftInPhase: at ? at.phase.duration_weeks - at.phaseWeek + 1 : null,
  };
}

export function formatWeeksLeftInPhase(weeksLeft: number): string {
  if (weeksLeft <= 1) return "last week of phase";
  return `${weeksLeft} weeks left in phase`;
}

/** "Week 6 of 12 · Strength & Power · 2 weeks left in phase" */
export function formatCycleHeadline(pos: CyclePosition): string {
  const parts = [`Week ${pos.week} of ${pos.totalWeeks}`];
  if (pos.phaseLabel) parts.push(pos.phaseLabel);
  if (pos.weeksLeftInPhase != null) parts.push(formatWeeksLeftInPhase(pos.weeksLeftInPhase));
  return parts.join(" · ");
}
