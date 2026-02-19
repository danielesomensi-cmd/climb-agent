"use client";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";

const FEEDBACK_COLORS: Record<string, string> = {
  very_easy: "bg-green-500",
  easy: "bg-green-400",
  ok: "bg-yellow-400",
  hard: "bg-orange-500",
  very_hard: "bg-red-500",
};

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
  feedbackLevel?: string;
}

/** Format rest as mm:ss (e.g. 120 → "2:00", 90 → "1:30") */
function formatRestMMSS(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

export function ExerciseCard({ exercise, feedbackLevel }: ExerciseCardProps) {
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
          <div className="flex items-center gap-1.5">
            <CardTitle className="text-sm truncate">{exercise.name}</CardTitle>
            {feedbackLevel && FEEDBACK_COLORS[feedbackLevel] && (
              <span
                className={`inline-block size-2 shrink-0 rounded-full ${FEEDBACK_COLORS[feedbackLevel]}`}
                title={feedbackLevel.replace(/_/g, " ")}
              />
            )}
          </div>
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
