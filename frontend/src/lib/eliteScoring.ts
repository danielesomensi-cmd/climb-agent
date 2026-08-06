// A267 — elite-relative axis scoring. Pure, render-time only.
//
// ── The one non-negotiable ────────────────────────────────────────────────
// Nothing in this file writes. `computeEliteScores` is a pure function called
// during render; its output lives in React state for the lifetime of the open
// component and is never persisted, never sent to the API, and never read by
// the engine. The engine's axis scores (`assessment.profile`, target-relative)
// remain the only scores that exist anywhere outside this render pass — they
// are what `macrocycle_v1` weights, what the replanner sees, and what the coach
// is given. Changing the anchor table cannot move a single training plan.
//
// The inputs below are read from data already in the `/api/state` payload, so
// the elite mode adds no request, no endpoint and no storage path.

import {
  ELITE_ANCHORS_V1,
  type AxisKey,
  type EliteAxisAnchor,
} from "@/lib/eliteAnchors";

/**
 * One-arm loading-pin lift → two-hand max-hang total. Mirrors
 * `LP_ONE_ARM_TO_TWO_HAND` in `backend/engine/assessment_v1.py` (A266) so a
 * climber who trains on a pin is not greyed out on the finger axis.
 */
const LP_ONE_ARM_TO_TWO_HAND = 1.85;
/** Above this ratio a "one-hand lift" is a data-entry error (A266). */
const LP_MAX_PLAUSIBLE_BW_RATIO = 1.5;

export interface EliteRawInputs {
  bodyweightKg?: number | null;
  /** Two-arm max-hang TOTAL load in kg (includes bodyweight). */
  maxHangTotalKg?: number | null;
  /** Weighted pull-up 1RM TOTAL load in kg (includes bodyweight). */
  weightedPullupTotalKg?: number | null;
  /** D261 — body-mass-normalized intermittent impulse, kg·s·kg⁻¹. Not collected yet. */
  enduranceImpulse?: number | null;
}

/** Elite-relative score per axis. `null` = greyed (no anchor, or no input). */
export type EliteScores = Record<AxisKey, number | null>;

function toPositiveNumber(value: unknown): number | null {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n) || n <= 0) return null;
  return n;
}

/** Brzycki 1RM estimate — mirrors `brzycki_1rm` in `assessment_v1.py` (D38). */
function brzycki1rm(weight: number, reps: number): number {
  if (reps <= 0) return 0;
  if (reps === 1) return weight;
  if (reps >= 37) return weight;
  return weight * (36 / (37 - reps));
}

/**
 * Normalize one raw value against one anchor. Linear between floor and elite,
 * clamped to [0, 100]. Returns null when the axis has no anchor or no input —
 * a greyed axis, never a fabricated 0.
 */
export function normalizeAgainstAnchor(
  raw: number | null | undefined,
  anchor: EliteAxisAnchor,
): number | null {
  if (anchor.elite === null || anchor.floor === null) return null;
  if (raw === null || raw === undefined || !Number.isFinite(raw)) return null;
  const span = anchor.elite - anchor.floor;
  if (span <= 0) return null;
  const pct = ((raw - anchor.floor) / span) * 100;
  return Math.round(Math.max(0, Math.min(100, pct)));
}

/**
 * Elite-relative scores for all five axes.
 *
 * Pure: `(raw_inputs, anchor_set) → scores`. Same inputs, same output, no I/O.
 */
export function computeEliteScores(
  raw: EliteRawInputs,
  anchors: Record<AxisKey, EliteAxisAnchor> = ELITE_ANCHORS_V1,
): EliteScores {
  const bw = toPositiveNumber(raw.bodyweightKg);
  const hang = toPositiveNumber(raw.maxHangTotalKg);
  const pull = toPositiveNumber(raw.weightedPullupTotalKg);
  const impulse = toPositiveNumber(raw.enduranceImpulse);

  // Both strength axes are expressed as a percentage of bodyweight, so without
  // a bodyweight there is no measurement — grey, not a default of 70 kg. That
  // silent default is exactly what A262/A263 removed from the public endpoint.
  const hangPctBw = bw && hang ? (hang / bw) * 100 : null;
  const pullPctBw = bw && pull ? (pull / bw) * 100 : null;

  return {
    finger_strength: normalizeAgainstAnchor(hangPctBw, anchors.finger_strength),
    pulling_strength: normalizeAgainstAnchor(pullPctBw, anchors.pulling_strength),
    power_endurance: normalizeAgainstAnchor(null, anchors.power_endurance),
    technique: normalizeAgainstAnchor(null, anchors.technique),
    endurance: normalizeAgainstAnchor(impulse, anchors.endurance),
  };
}

/** True when at least one axis can be scored — i.e. the toggle is worth showing. */
export function hasAnyEliteScore(scores: EliteScores): boolean {
  return Object.values(scores).some((v) => v !== null);
}

/**
 * A268 — build the raw inputs from **added** loads rather than totals.
 *
 * The public `/assessment` page (A263) asks for the weight *added* to the bar,
 * which can be negative when the pull-up is assisted; the engine and the elite
 * anchors both speak in totals. This mirrors exactly what
 * `routers/public_assessment.py` does before calling the engine
 * (`tests["max_hang_20mm_7s_total_kg"] = bw + added`), so the same answers score
 * the same way on both scales.
 *
 * Without a bodyweight there is nothing to convert and nothing to normalise —
 * both axes come back null rather than being scored against a stand-in, the
 * same refusal the endpoint makes with a 422.
 */
export function eliteInputsFromAddedLoads(input: {
  bodyweight_kg?: number | null;
  max_hang_added_kg?: number | null;
  weighted_pullup_added_kg?: number | null;
}): EliteRawInputs {
  const bw = toPositiveNumber(input.bodyweight_kg);
  const total = (added: number | null | undefined): number | null => {
    if (bw === null || added === null || added === undefined) return null;
    const n = Number(added);
    if (!Number.isFinite(n)) return null;
    return toPositiveNumber(bw + n);
  };
  return {
    bodyweightKg: bw,
    maxHangTotalKg: total(input.max_hang_added_kg),
    weightedPullupTotalKg: total(input.weighted_pullup_added_kg),
    enduranceImpulse: null,
  };
}

// ---------------------------------------------------------------------------
// Extraction from the existing /api/state payload (no new endpoint)
// ---------------------------------------------------------------------------

type Dict = Record<string, unknown>;

/**
 * Pull the raw inputs out of a user_state assessment block, following the same
 * precedence `assessment_v1.py` uses: a measured hangboard total wins, a
 * loading-pin lift is converted as a fallback (A266), and a pull-up 1RM falls
 * back to a Brzycki estimate from submaximal reps (D38).
 */
export function extractEliteInputs(state: unknown): EliteRawInputs {
  const s = (state ?? {}) as Dict;
  const assessment = (s.assessment ?? {}) as Dict;
  const tests = (assessment.tests ?? {}) as Dict;
  const assessmentBody = (assessment.body ?? {}) as Dict;
  const topBody = (s.body ?? {}) as Dict;

  const bw =
    toPositiveNumber(assessmentBody.weight_kg) ??
    toPositiveNumber(topBody.weight_kg) ??
    toPositiveNumber(s.bodyweight_kg);

  let maxHang =
    toPositiveNumber(tests.max_hang_20mm_7s_total_kg) ??
    toPositiveNumber(tests.max_hang_20mm_5s_total_kg);

  if (maxHang === null && bw !== null) {
    const lifts: number[] = [];
    for (const key of ["lp_max_lift_5s_left_kg", "lp_max_lift_5s_right_kg"]) {
      const v = toPositiveNumber(tests[key]);
      // Same implausibility guard as the engine: past 1.5x bodyweight on one
      // hand the number is a typo, not a climber.
      if (v !== null && v / bw <= LP_MAX_PLAUSIBLE_BW_RATIO) lifts.push(v);
    }
    if (lifts.length > 0) {
      const mean = lifts.reduce((a, b) => a + b, 0) / lifts.length;
      maxHang = mean * LP_ONE_ARM_TO_TWO_HAND;
    }
  }

  let pullup = toPositiveNumber(tests.weighted_pullup_1rm_total_kg);
  if (pullup === null && bw !== null) {
    const reps = toPositiveNumber(tests.pullup_submaximal_reps);
    const load = toPositiveNumber(tests.pullup_submaximal_load_kg);
    if (reps !== null && load !== null) {
      pullup = brzycki1rm(bw + load, Math.round(reps));
    }
  }

  return {
    bodyweightKg: bw,
    maxHangTotalKg: maxHang,
    weightedPullupTotalKg: pullup,
    // D261 has not shipped — nothing writes an impulse yet. Wired so the axis
    // wakes up on data alone once it does.
    enduranceImpulse: toPositiveNumber(tests.endurance_intermittent_impulse),
  };
}
