/**
 * B288 — single source of truth for building `exercise_feedback_v1` items.
 *
 * Why this module exists: the load the user actually lifted is the ONLY fuel
 * for the engine's load memory (`working_loads` → `progression_v1.apply_feedback`).
 * Before B288 three of the five paths that POST /api/feedback built their items
 * inline and each dropped a different subset of fields, so a session completed
 * from /today or /week never updated the memory at all — the engine kept
 * proposing the cold-start fallback forever (reverse_wrist_curl pinned at 2.0kg
 * from 2026-03-30 to 2026-07-20).
 *
 * Rule of thumb for anything added here: an item that carries no `used_*` value
 * is silently discarded server-side. Dropping a field is never neutral.
 */

import type { FeedbackMeasure, GuidedExercise, LimitProblemDraft } from "@/lib/types";
import { asMeasure, measureFields, type MeasureValues } from "@/lib/measured-feedback";
import { displayPrescribedGrade } from "@/lib/gradeUtils";
import { limitFeedbackFields } from "@/lib/limit-problems";

/** An exercise as the post-session FeedbackDialog needs to know it. */
export interface FeedbackDialogExercise {
  exercise_id: string;
  name: string;
  loadModel?: string;
  unilateral?: boolean;
  suggestedExternalLoadKg?: number;
  suggestedTotalLoadKg?: number;
  allowLoadLogging?: boolean;
  /** A295: measure the server asks for (suggested.measure), and its context. */
  measure?: FeedbackMeasure;
  targetReps?: number;
  prescribedReps?: number;
  /** A298: the dose came from the resolver's ladder stage. */
  ladderSource?: "engine";
  /**
   * A299: grade-relative exercises — the prescribed grade (same source as the
   * guided player: suggested_grade, else the boulder target) and its scale.
   */
  grade?: string;
  gradeLow?: string;
  gradeScale?: string;
  /** A299: limit family — logged problem by problem, as in the guided player. */
  logProblems?: boolean;
  /** A299: the surface the target is for (sent back as surface_selected). */
  surface?: string;
  /** Test exercises carry their own measurement field: no grade input. */
  testField?: string;
}

/**
 * A299: does this exercise take an "Actual grade used" field? Mirrors
 * `hasGradeField` in guided-exercise-step.tsx (a prescribed grade, not a test).
 */
export function hasGradeInput(ex: FeedbackDialogExercise): boolean {
  return ex.grade != null && ex.grade !== "" && !ex.testField;
}

/** A299: the limit family shows the problem logger instead of the grade field. */
export function hasProblemLog(ex: FeedbackDialogExercise): boolean {
  return hasGradeInput(ex) && ex.logProblems === true;
}

/** A299: the grade field's pre-fill — the target, on its own scale (as the guided player). */
export function prefilledGrade(ex: FeedbackDialogExercise): string {
  return ex.grade ? displayPrescribedGrade(ex.grade, ex.gradeScale) : "";
}

/**
 * Does this exercise take a load the engine will consume?
 *
 * Mirrors `hasLoadField` in components/guided/guided-exercise-step.tsx — the
 * two must agree, otherwise the same session records a load in the guided
 * player and loses it in the dialog. Unilateral exercises are excluded on
 * purpose: they need a per-hand split (`hand` field) that a compact dialog row
 * cannot collect, and sending a single value would write one wrong entry
 * instead of two right ones.
 */
export function hasLoadInput(ex: FeedbackDialogExercise): boolean {
  if (ex.unilateral) return false;
  // B298: mirror guided-exercise-step's hasLoadField — a kg-loadable exercise
  // (external_load / total_load) always takes a load, even before any is
  // suggested, so a never-logged loadable exercise is loggable (and the two
  // surfaces stay in agreement). bodyweight/band stay opt-in via allowLoadLogging.
  const isKgLoadable =
    ex.loadModel === "external_load" || ex.loadModel === "total_load";
  return isKgLoadable || !!ex.allowLoadLogging;
}

/**
 * Pull the dialog's exercise list out of a resolved session slot, carrying the
 * load metadata the dialog needs to render (and send) a weight.
 */
export function extractFeedbackExercises(
  session: { resolved?: unknown } | null | undefined,
): FeedbackDialogExercise[] {
  const resolved = session?.resolved as Record<string, unknown> | undefined;
  if (!resolved) return [];
  const resolvedSession = resolved.resolved_session as Record<string, unknown> | undefined;
  const instances = (resolvedSession?.exercise_instances ?? []) as Array<Record<string, unknown>>;

  return instances.map((ex) => {
    const suggested = (ex.suggested ?? {}) as Record<string, unknown>;
    const attributes = (ex.attributes ?? {}) as Record<string, unknown>;
    const prescription = (ex.prescription ?? {}) as Record<string, unknown>;
    const exerciseId = (ex.exercise_id as string) ?? "";
    const reps = typeof prescription.reps === "number" ? prescription.reps : undefined;
    const boulderTarget = (suggested.suggested_boulder_target ?? {}) as Record<string, unknown>;
    // A299: same grade source as session-card's buildGuidedExercise.
    const grade =
      (suggested.suggested_grade as string | undefined) ?? (boulderTarget.target_grade as string | undefined);
    return {
      exercise_id: exerciseId,
      name: (ex.name as string) ?? exerciseId.replace(/_/g, " "),
      loadModel: ex.load_model as string | undefined,
      unilateral: !!(ex.unilateral ?? suggested.right_hand),
      suggestedExternalLoadKg: suggested.suggested_external_load_kg as number | undefined,
      suggestedTotalLoadKg: suggested.suggested_total_load_kg as number | undefined,
      allowLoadLogging: !!attributes.allow_load_logging,
      measure: asMeasure(suggested.measure),
      targetReps: typeof suggested.target_reps === "number" ? suggested.target_reps : undefined,
      prescribedReps: reps,
      ladderSource: prescription.source === "bw_ladder" ? "engine" : undefined,
      grade: grade ?? undefined,
      gradeLow: boulderTarget.target_grade_low as string | undefined,
      gradeScale: suggested.grade_scale as string | undefined,
      logProblems: boulderTarget.log_problems === true,
      surface: boulderTarget.surface_selected as string | undefined,
      testField: attributes.test_field as string | undefined,
    };
  });
}

/**
 * Build feedback items from the post-session dialog.
 *
 * `loads` is keyed by exercise_id and holds what the user left in the kg field
 * (pre-filled with the suggested value, exactly like the guided player — a user
 * who just taps Submit is confirming the proposed load, which is also what
 * keeps the memory from going stale).
 *
 * A295: `feedback_label` is sent ONLY when the user picked one — an untouched
 * exercise is "not rated" (never a silent "ok", never null). `measures` holds
 * the optional last-set reps / hang margin per exercise.
 *
 * A299: `grades` holds what the user left in the "Actual grade used" field
 * (pre-filled with the target, exactly like the guided player — untouched,
 * the target travels and the server holds it); `problems` the limit problem
 * rows, turned into the payload by the SAME `limitFeedbackFields` the guided
 * player uses (rows without an outcome are dropped).
 */
export function buildDialogFeedbackItems(
  exercises: FeedbackDialogExercise[],
  labels: Record<string, string>,
  loads: Record<string, number>,
  measures: Record<string, MeasureValues> = {},
  grades: Record<string, string> = {},
  problems: Record<string, LimitProblemDraft[]> = {},
): Array<Record<string, unknown>> {
  return exercises.map((ex) => {
    const item: Record<string, unknown> = {
      exercise_id: ex.exercise_id,
      completed: true,
    };
    const label = labels[ex.exercise_id];
    if (label) item.feedback_label = label;
    if (ex.ladderSource) item.bw_ladder = ex.ladderSource;
    Object.assign(
      item,
      measureFields(ex.measure, { targetReps: ex.targetReps, ...(measures[ex.exercise_id] ?? {}) }),
    );
    const load = loads[ex.exercise_id];
    if (hasLoadInput(ex) && load != null && !Number.isNaN(load)) {
      item.used_external_load_kg = load;
      // total_load exercises (hangboard): derive the total the same way the
      // guided player does, from the bodyweight implied by the suggestion.
      if (ex.suggestedTotalLoadKg != null && ex.suggestedExternalLoadKg != null) {
        const bodyweight = ex.suggestedTotalLoadKg - ex.suggestedExternalLoadKg;
        item.used_total_load_kg = bodyweight + load;
      }
    }
    if (hasGradeInput(ex)) {
      const typed = (grades[ex.exercise_id] ?? prefilledGrade(ex)).trim();
      if (hasProblemLog(ex)) {
        Object.assign(item, limitFeedbackFields(problems[ex.exercise_id], typed || undefined));
      } else if (typed) {
        item.used_grade = typed;
      }
      if (ex.surface) item.surface_selected = ex.surface;
    }
    return item;
  });
}

/**
 * Build feedback items from a guided-player state.
 *
 * Extracted verbatim from the guided page's handleSubmit so the localStorage
 * retry path in /today replays the SAME payload instead of a narrowed copy of
 * it (pre-B288 the retry dropped used_total_load_kg, the per-hand `hand` split,
 * completed_sets/reps, surface_selected, notes and test measurements — a failed
 * POST silently degraded into a lossy one, then deleted the richer local copy).
 */
export function buildGuidedFeedbackItems(
  exercises: GuidedExercise[],
): Array<Record<string, unknown>> {
  const items: Array<Record<string, unknown>> = [];

  for (const ex of exercises) {
    if (ex.isInstructionOnly) continue;

    // B128: unilateral test measurement (e.g. lp_duration_test — seconds per hand)
    if (ex.unilateral && ex.testField && (ex.testMeasurementRight != null || ex.testMeasurementLeft != null)) {
      for (const hand of ["right", "left"] as const) {
        const measurement = hand === "right" ? ex.testMeasurementRight : ex.testMeasurementLeft;
        const suggestedLoad = hand === "right"
          ? ex.suggested.rightHand?.externalLoadKg
          : ex.suggested.leftHand?.externalLoadKg;
        items.push({
          exercise_id: ex.exerciseId,
          ...labelField(ex),
          completed: ex.status === "done",
          hand,
          [ex.testField]: measurement,
          used_external_load_kg: suggestedLoad,
        });
      }
      continue;
    }

    // Unilateral exercises: split into per-hand feedback entries
    if (ex.unilateral && (ex.usedLoadKgRight != null || ex.usedLoadKgLeft != null)) {
      for (const hand of ["right", "left"] as const) {
        const load = hand === "right" ? ex.usedLoadKgRight : ex.usedLoadKgLeft;
        const reps = hand === "right" ? ex.completedRepsRight : ex.completedRepsLeft;
        const entry: Record<string, unknown> = {
          exercise_id: ex.exerciseId,
          ...labelField(ex),
          completed: ex.status === "done",
          hand,
          used_external_load_kg: load,
        };
        if (reps != null) entry.completed_reps = reps;
        Object.assign(entry, guidedMeasureFields(ex));
        items.push(entry);
      }
      continue;
    }

    const item: Record<string, unknown> = {
      exercise_id: ex.exerciseId,
      ...labelField(ex),
      completed: ex.status === "done",
    };
    // A298: tell the server the dose came from the bodyweight ladder.
    if (ex.suggested.ladderSource) item.bw_ladder = ex.suggested.ladderSource;
    if (ex.usedTotalLoadKg != null) {
      item.used_total_load_kg = ex.usedTotalLoadKg;
    }
    if (ex.usedLoadKg != null) {
      item.used_external_load_kg = ex.usedLoadKg;
      // Auto-compute total from external + body weight if not manually set
      if (ex.usedTotalLoadKg == null && ex.suggested.totalLoadKg != null && ex.suggested.externalLoadKg != null) {
        const bodyWeight = ex.suggested.totalLoadKg - ex.suggested.externalLoadKg;
        item.used_total_load_kg = bodyWeight + ex.usedLoadKg;
      }
    }
    if (ex.usedGrade) {
      item.used_grade = ex.usedGrade;
    }
    // A296: limit problem log — only for an exercise actually done.
    if (ex.status === "done" && ex.problems && ex.problems.length > 0) {
      item.problems = ex.problems;
    }
    // A299: the wall the athlete said he was on (custom/adhoc limit rows)
    // wins over the server's guess.
    const surface = ex.chosenSurface ?? ex.suggested.surface;
    if (surface) {
      item.surface_selected = surface;
    }
    if (ex.completedSets != null) {
      item.completed_sets = ex.completedSets;
      // B133: the repeater test reads completed_reps (reps to failure). A295:
      // ONLY there — elsewhere it was a copy of completed_sets that the
      // engine could mistake for real reps.
      if (REPEATER_TEST_IDS.has(ex.exerciseId)) item.completed_reps = ex.completedSets;
    }
    Object.assign(item, guidedMeasureFields(ex));
    // Test measurement exercises: send the value as the field name directly
    if (ex.testField && ex.testMeasurement != null) {
      item[ex.testField] = ex.testMeasurement;
    }
    if (ex.notes) {
      item.notes = ex.notes;
    }
    items.push(item);
  }

  return items;
}

/** B133: tests whose completed_reps is the number of reps to failure. */
const REPEATER_TEST_IDS: ReadonlySet<string> = new Set([
  "repeater_hang_7_3",
  "test_repeater_7_3_to_failure",
]);

/** A295: the label only when the athlete picked one (never null, never "ok" by default). */
function labelField(ex: GuidedExercise): { feedback_label?: string } {
  return ex.feedbackLabel ? { feedback_label: ex.feedbackLabel } : {};
}

/** A295: measure fields of a guided exercise (only the ones the server asked for). */
function guidedMeasureFields(ex: GuidedExercise): Record<string, unknown> {
  // A skipped exercise carries no measure: nothing was done.
  if (ex.status !== "done") return {};
  return measureFields(ex.suggested.measure, {
    lastSetReps: ex.lastSetReps,
    hangMargin: ex.hangMargin,
    hangHeldS: ex.hangHeldS,
    targetReps: ex.suggested.targetReps,
  });
}
