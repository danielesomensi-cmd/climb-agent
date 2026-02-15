"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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

/** Formatta il tempo di recupero in modo leggibile */
function formatRest(seconds: number): string {
  if (seconds >= 60) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  }
  return `${seconds}s`;
}

export function ExerciseCard({ exercise }: ExerciseCardProps) {
  const [expanded, setExpanded] = useState(false);

  const hasDetails = exercise.tempo || exercise.notes;

  // Riga prescrizione compatta: "3 x 8 @ 10 kg — rec 90s"
  const parts: string[] = [];
  if (exercise.sets != null && exercise.reps != null) {
    parts.push(`${exercise.sets} x ${exercise.reps}`);
  } else if (exercise.sets != null) {
    parts.push(`${exercise.sets} serie`);
  } else if (exercise.reps != null) {
    parts.push(exercise.reps);
  }
  if (exercise.load_kg != null) {
    parts.push(`${exercise.load_kg} kg`);
  }
  if (exercise.rest_s != null) {
    parts.push(`rec ${formatRest(exercise.rest_s)}`);
  }
  const prescriptionLine = parts.join(" \u00B7 "); // middle dot separator

  return (
    <Card className="gap-0 py-0">
      <CardHeader
        className={`py-2.5 ${hasDetails ? "cursor-pointer select-none" : ""}`}
        onClick={() => hasDetails && setExpanded((prev) => !prev)}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="text-sm truncate">{exercise.name}</CardTitle>
            {prescriptionLine && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {prescriptionLine}
              </p>
            )}
          </div>
          {hasDetails &&
            (expanded ? (
              <ChevronUp className="size-3.5 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
            ))}
        </div>
      </CardHeader>

      {expanded && hasDetails && (
        <CardContent className="pt-0 pb-2.5 space-y-1">
          {exercise.tempo && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium">Tempo:</span> {exercise.tempo}
            </p>
          )}
          {exercise.notes && (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium">Note:</span> {exercise.notes}
            </p>
          )}
        </CardContent>
      )}
    </Card>
  );
}
