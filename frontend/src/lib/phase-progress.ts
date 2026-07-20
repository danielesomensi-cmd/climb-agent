/**
 * A235 (A-GAMIFY-01) — macrocycle progress helpers.
 *
 * Shared, pause-aware week math: A223 pause shifts future weeks forward by
 * `pause.offset_days` without moving `start_date`, so any week computed from
 * start_date alone over-counts after a resume. Every consumer (plan timeline,
 * phase celebration) goes through computeCurrentWeek so they stay coherent.
 */

import type { Macrocycle, Phase } from "@/lib/types";
import { parseISODateLocal } from "@/lib/dates";

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

/** 1-based current macrocycle week, clamped to [1, total_weeks]. */
export function computeCurrentWeek(macrocycle: Macrocycle): number {
  const start = parseISODateLocal(macrocycle.start_date);
  const offsetDays = macrocycle.pause?.offset_days ?? 0;
  const diffMs = Date.now() - start.getTime() - offsetDays * 24 * 60 * 60 * 1000;
  const week = Math.floor(diffMs / WEEK_MS) + 1;
  return Math.min(Math.max(1, week), macrocycle.total_weeks);
}

/** True once the macrocycle end_date (or start + total_weeks) is behind us. */
export function isCycleEnded(macrocycle: Macrocycle): boolean {
  const offsetDays = macrocycle.pause?.offset_days ?? 0;
  const end = macrocycle.end_date
    ? parseISODateLocal(macrocycle.end_date)
    : new Date(
        parseISODateLocal(macrocycle.start_date).getTime() +
          macrocycle.total_weeks * WEEK_MS +
          offsetDays * 24 * 60 * 60 * 1000,
      );
  return Date.now() > end.getTime() + 24 * 60 * 60 * 1000;
}

export interface PhaseProgress {
  phase: Phase;
  /** 0-based index into macrocycle.phases */
  index: number;
  /** 1-based week within the phase */
  phaseWeek: number;
  /** 1-based macrocycle week the phase starts at */
  startWeek: number;
}

/** The phase containing the given 1-based macrocycle week (null if none). */
export function getPhaseAtWeek(
  macrocycle: Macrocycle,
  week: number,
): PhaseProgress | null {
  let cursor = 1;
  for (let i = 0; i < macrocycle.phases.length; i++) {
    const phase = macrocycle.phases[i];
    if (week < cursor + phase.duration_weeks) {
      return { phase, index: i, phaseWeek: week - cursor + 1, startWeek: cursor };
    }
    cursor += phase.duration_weeks;
  }
  return null;
}

/** Key marking one phase-entry celebration as seen, scoped to this cycle. */
export function celebrationKey(macrocycle: Macrocycle, phaseId: string): string {
  return `${macrocycle.start_date}:${phaseId}`;
}
