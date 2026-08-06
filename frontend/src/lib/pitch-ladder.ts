/**
 * A265 — normalisation of a hand-edited pitch ladder.
 *
 * Kept out of the component so the rules that matter (drop empty rows, never
 * emit attempts < 1, re-index, recompute the summary, flag the ladder as no
 * longer generated) are testable without rendering anything.
 */

import type { OutdoorPitchLadder, PitchLadderRow } from "./types";

/** Minutes of climbing + rigging assumed per attempt — mirrors the backend. */
const MIN_PER_ATTEMPT = 12;

export function summarisePitches(pitches: PitchLadderRow[]) {
  const totalAttempts = pitches.reduce((n, r) => n + r.attempts, 0);
  const totalRest = pitches.reduce((n, r) => n + r.rest_after_min, 0);
  return {
    pitch_count: pitches.length,
    total_attempts: totalAttempts,
    estimated_hours:
      Math.round(((totalAttempts * MIN_PER_ATTEMPT + totalRest) / 60) * 10) / 10,
  };
}

/**
 * Turn edited rows into a ladder ready to persist.
 *
 * Returns `null` when nothing usable is left — the caller sends that as-is,
 * which clears the day's plan rather than storing an empty one.
 */
export function normaliseLadder(
  rows: PitchLadderRow[],
  base?: OutdoorPitchLadder,
): OutdoorPitchLadder | null {
  const cleaned = rows
    .filter((r) => String(r.grade ?? "").trim() !== "")
    .map((r, idx) => ({
      ...r,
      index: idx + 1,
      grade: String(r.grade).trim(),
      attempts: Math.max(1, Number(r.attempts) || 1),
      rest_after_min: Math.max(0, Number(r.rest_after_min) || 0),
    }));

  if (!cleaned.length) return null;

  return {
    ...base,
    pitches: cleaned,
    // Hand-edited: the regenerate button must warn before overwriting it.
    generated: false,
    summary: summarisePitches(cleaned),
  };
}
