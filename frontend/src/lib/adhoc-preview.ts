/**
 * A299 — what a coach ad-hoc preview card may show of a limit target.
 *
 * The composer/builder attach to limit-family rows the limit target of the
 * day they composed for (`resolved_for_date`), using the same read the player
 * uses (progression_v1.limit_grade_target). The target is never stored: the
 * saved row drops it and the guided player recomputes it for the day played
 * (GET /api/week, GET custom ?date=). So the card shows it only when the
 * preview was computed for the athlete's own today — the day "Add to today &
 * run" plays it, hence the same number the player will show. An older card in
 * the chat history would show a stale value: it shows none.
 */
import { displayBoulderGrade, type BoulderGradeSystem } from "@/lib/gradeUtils";
import { surfaceLabel } from "@/lib/limit-problems";
import type { AdhocSessionExercisePreview } from "@/lib/api";

export function previewLimitTarget(
  ex: Pick<AdhocSessionExercisePreview, "target_grade" | "target_grade_low" | "surface_selected">,
  resolvedFor: string | undefined,
  today: string,
  gradeSystem: BoulderGradeSystem = "font",
): string | null {
  if (!ex.target_grade || !resolvedFor || resolvedFor !== today) return null;
  const hi = displayBoulderGrade(ex.target_grade, gradeSystem);
  const lo =
    ex.target_grade_low && ex.target_grade_low !== ex.target_grade
      ? displayBoulderGrade(ex.target_grade_low, gradeSystem)
      : null;
  const where = ex.surface_selected ? ` · ${surfaceLabel(ex.surface_selected)}` : "";
  return `limit ${lo ? `${lo}–${hi}` : hi}${where}`;
}
