import { displaySetNumber, sideForSet, totalSetsWithSides } from "@/lib/alt-sides";

/**
 * A307 — what comes after the rest the athlete is sitting in, for the planned
 * guided player. Same wording as the custom player's rest screen
 * (play/page.tsx → CustomRestTimer): "Set 2 of 3 · LEFT" for another bout of
 * this exercise, the next exercise's name once its sets are used up, "Finish"
 * at the end of the session. The timer prefixes it with "Next · ".
 *
 * `completedSets` counts INTERNAL sets (doubled for alt_sides), exactly what
 * ExerciseTimer reports through onSetChange at the end of each set.
 */
export function guidedNextLabel({
  completedSets,
  sets,
  altSides,
  nextExerciseName,
}: {
  completedSets: number | null | undefined;
  sets: number | null | undefined;
  altSides: boolean;
  nextExerciseName?: string | null;
}): string {
  const total = totalSetsWithSides(sets, altSides);
  const done = Math.max(0, completedSets ?? 0);
  if (done < total) {
    const next = done + 1;
    const side = sideForSet(next, altSides);
    return `Set ${displaySetNumber(next, altSides)} of ${Math.max(1, sets ?? 1)}${side ? ` · ${side}` : ""}`;
  }
  return nextExerciseName ? nextExerciseName : "Finish";
}
