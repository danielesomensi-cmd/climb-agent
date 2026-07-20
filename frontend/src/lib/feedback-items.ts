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

import type { GuidedExercise } from "@/lib/types";

/** An exercise as the post-session FeedbackDialog needs to know it. */
export interface FeedbackDialogExercise {
  exercise_id: string;
  name: string;
  loadModel?: string;
  unilateral?: boolean;
  suggestedExternalLoadKg?: number;
  suggestedTotalLoadKg?: number;
  allowLoadLogging?: boolean;
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
  if (ex.loadModel === "bodyweight_only") return !!ex.allowLoadLogging;
  return (
    ex.suggestedExternalLoadKg != null ||
    ex.suggestedTotalLoadKg != null ||
    !!ex.allowLoadLogging
  );
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
    const exerciseId = (ex.exercise_id as string) ?? "";
    return {
      exercise_id: exerciseId,
      name: (ex.name as string) ?? exerciseId.replace(/_/g, " "),
      loadModel: ex.load_model as string | undefined,
      unilateral: !!(ex.unilateral ?? suggested.right_hand),
      suggestedExternalLoadKg: suggested.suggested_external_load_kg as number | undefined,
      suggestedTotalLoadKg: suggested.suggested_total_load_kg as number | undefined,
      allowLoadLogging: !!attributes.allow_load_logging,
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
 */
export function buildDialogFeedbackItems(
  exercises: FeedbackDialogExercise[],
  labels: Record<string, string>,
  loads: Record<string, number>,
): Array<Record<string, unknown>> {
  return exercises.map((ex) => {
    const item: Record<string, unknown> = {
      exercise_id: ex.exercise_id,
      feedback_label: labels[ex.exercise_id] ?? "ok",
      completed: true,
    };
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
          feedback_label: ex.feedbackLabel,
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
          feedback_label: ex.feedbackLabel,
          completed: ex.status === "done",
          hand,
          used_external_load_kg: load,
        };
        if (reps != null) entry.completed_reps = reps;
        items.push(entry);
      }
      continue;
    }

    const item: Record<string, unknown> = {
      exercise_id: ex.exerciseId,
      feedback_label: ex.feedbackLabel,
      completed: ex.status === "done",
    };
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
    if (ex.suggested.surface) {
      item.surface_selected = ex.suggested.surface;
    }
    if (ex.completedSets != null) {
      item.completed_sets = ex.completedSets;
      // B133: new repeater test expects completed_reps
      item.completed_reps = ex.completedSets;
    }
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
