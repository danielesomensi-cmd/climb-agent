/**
 * A295 (R4) — measured feedback, feedback_contract 2.
 *
 * Before A295 every path that POSTs /api/feedback pre-selected "ok": closing a
 * session without touching anything signed "ok" on every exercise, and the
 * engine could not tell a real "ok" from no answer at all. Now:
 *
 *  - nothing is pre-selected; an untouched exercise ships WITHOUT
 *    `feedback_label` and the server treats it as "not rated" (load held at
 *    what was used, left out of difficulty, report and coach);
 *  - three optional measures, one tap each, only on the exercises the server
 *    flags with `measure`: reps on the last set (pull-ups, double-progression
 *    accessories), seconds left on the last hang, and the timed overhold of
 *    the guided player;
 *  - one "Any pain?" row per session (0-3, zone from 2).
 *
 * Every log entry built under this contract carries `feedback_contract: 2`.
 */

import type { FeedbackMeasure, HangMargin, PainSite, SessionPain } from "@/lib/types";

export const FEEDBACK_CONTRACT = 2;

export const HANG_MARGIN_OPTIONS: ReadonlyArray<{ value: HangMargin; label: string }> = [
  { value: "failed", label: "Failed" },
  { value: "0-2", label: "0–2 s" },
  { value: "3-5", label: "3–5 s" },
  { value: ">5", label: ">5 s" },
];

export const PAIN_OPTIONS: ReadonlyArray<{ value: SessionPain["score"]; label: string }> = [
  { value: 0, label: "None" },
  { value: 1, label: "Niggle" },
  { value: 2, label: "Pain" },
  { value: 3, label: "Had to stop" },
];

export const PAIN_SITE_OPTIONS: ReadonlyArray<{ value: PainSite; label: string }> = [
  { value: "fingers", label: "Fingers" },
  { value: "elbow", label: "Elbow" },
  { value: "shoulder", label: "Shoulder" },
  { value: "other", label: "Other" },
];

/** Timed overhold: the guided timer runs at most this far past the target. */
export const OVERHOLD_CAP_S = 6;
/**
 * A295 review — ENGINEERING CONSTANT: seconds between letting go of the hold
 * and the tap on the phone. Subtracted from a tapped overhold so the reaction
 * time never inflates the measure that can trigger an early retest.
 */
export const OVERHOLD_TAP_LATENCY_S = 1;

const MEASURES: ReadonlySet<string> = new Set(["last_set_reps", "hang_margin", "dp_reps"]);

export function asMeasure(value: unknown): FeedbackMeasure | undefined {
  return typeof value === "string" && MEASURES.has(value) ? (value as FeedbackMeasure) : undefined;
}

/**
 * Upper bound of the "reps on your last set" stepper. For a pull-up it must
 * reach the rep count at which the measured e1RM passes the official max (7
 * at +30 for Daniele), so max(P + 4, 8).
 */
export function lastSetStepperMax(prescribedReps: number | undefined, targetReps?: number): number {
  const p = Math.max(prescribedReps ?? 0, targetReps ?? 0);
  return Math.min(20, Math.max(p + 4, 8));
}

export interface MeasureValues {
  lastSetReps?: number;
  hangMargin?: HangMargin;
  hangHeldS?: number;
  targetReps?: number;
}

/**
 * Measure fields for one feedback item. Only the fields the server asked for
 * (`measure`) are sent; `target_reps` travels only with a measured
 * double-progression set, because it is what that set is compared with.
 */
export function measureFields(
  measure: FeedbackMeasure | undefined,
  values: MeasureValues,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (!measure) return out;
  if ((measure === "last_set_reps" || measure === "dp_reps") && values.lastSetReps != null) {
    out.last_set_reps = values.lastSetReps;
    if (measure === "dp_reps" && values.targetReps != null) out.target_reps = values.targetReps;
  }
  if (measure === "hang_margin") {
    if (values.hangMargin) out.hang_margin = values.hangMargin;
    if (values.hangHeldS != null && values.hangHeldS > 0) out.hang_held_s = values.hangHeldS;
  }
  return out;
}

/** Copy `log_entry` with the contract marker and the session pain, if given. */
export function withFeedbackContract<T extends Record<string, unknown>>(
  logEntry: T,
  pain?: SessionPain | null,
): T & { feedback_contract: number; pain?: SessionPain } {
  const out: T & { feedback_contract: number; pain?: SessionPain } = {
    ...logEntry,
    feedback_contract: FEEDBACK_CONTRACT,
  };
  if (pain) {
    out.pain = { score: pain.score, site: pain.score >= 2 ? pain.site : null };
  }
  return out;
}
