"use client";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";

interface ExerciseCardProps {
  exercise: {
    exercise_id: string;
    name: string;
    sets?: number;
    reps?: string;
    load_kg?: number;
    rest_s?: number;
    tempo?: string;
    notes?: string;
  };
}

/** Format rest as mm:ss (e.g. 120 → "2:00", 90 → "1:30") */
function formatRestMMSS(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

export function ExerciseCard({ exercise }: ExerciseCardProps) {
  // Build prescription: "4 × 8 @ 25kg — Rest 2:00"
  const mainParts: string[] = [];

  if (exercise.sets != null && exercise.reps != null) {
    mainParts.push(`${exercise.sets} \u00D7 ${exercise.reps}`);
  } else if (exercise.sets != null) {
    mainParts.push(`${exercise.sets} sets`);
  } else if (exercise.reps != null) {
    mainParts.push(exercise.reps);
  }

  if (exercise.load_kg != null) {
    mainParts.push(
      exercise.load_kg > 0 ? `@ ${exercise.load_kg}kg` : "@ bodyweight"
    );
  }

  let prescriptionLine = mainParts.join(" ");
  if (exercise.rest_s != null) {
    prescriptionLine += ` \u2014 Rest ${formatRestMMSS(exercise.rest_s)}`;
  }

  return (
    <Card className="gap-0 py-0">
      <CardHeader className="py-2.5">
        <div className="min-w-0">
          <CardTitle className="text-sm truncate">{exercise.name}</CardTitle>
          {prescriptionLine && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {prescriptionLine}
            </p>
          )}
          {exercise.tempo && (
            <p className="text-[11px] text-muted-foreground/70 mt-0.5">
              Tempo: {exercise.tempo}
            </p>
          )}
          {exercise.notes && (
            <p className="text-[11px] text-muted-foreground/70 mt-0.5">
              {exercise.notes}
            </p>
          )}
        </div>
      </CardHeader>
    </Card>
  );
}
