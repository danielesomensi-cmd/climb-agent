"use client";

import { useState } from "react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ChevronRight } from "lucide-react";
import type { ActualExercise } from "@/lib/types";
import { ExerciseDetailSheet } from "@/components/training/exercise-detail-sheet";

const FEEDBACK_COLORS: Record<string, string> = {
  very_easy: "bg-emerald-500",
  easy: "bg-green-500",
  ok: "bg-yellow-400",
  hard: "bg-orange-500",
  very_hard: "bg-red-500",
};

const FEEDBACK_TEXT_COLORS: Record<string, string> = {
  very_easy: "text-emerald-400",
  easy: "text-green-400",
  ok: "text-yellow-400",
  hard: "text-orange-400",
  very_hard: "text-red-400",
};

const FEEDBACK_LABELS: Record<string, string> = {
  very_easy: "Very Easy",
  easy: "Easy",
  ok: "OK",
  hard: "Hard",
  very_hard: "Very Hard",
};

/** Visual treatment based on module role */
const MODULE_ROLE_STYLES: Record<string, { opacity: string; border: string }> = {
  general_warmup: { opacity: "opacity-55", border: "border-l-2 border-l-slate-500/50" },
  cooldown:       { opacity: "opacity-55", border: "border-l-2 border-l-slate-500/50" },
  secondary:      { opacity: "opacity-85", border: "border-l-2 border-l-teal-500/60" },
  primary:        { opacity: "",           border: "border-l-2 border-l-amber-500/80" },
};

/** Fallback: derive visual treatment from exercise role array */
function roleToModuleStyle(roles: string[]): string {
  if (roles.some(r => r === "warmup" || r === "activation")) return "general_warmup";
  if (roles.includes("cooldown")) return "cooldown";
  if (roles.includes("recovery")) return "cooldown";
  if (roles.includes("prehab") && !roles.includes("main")) return "secondary";
  return "primary";
}

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
    suggested_external_load_kg?: number;
    suggested_total_load_kg?: number;
    load_source?: string;
    category?: string;
    testField?: string;
  };
  feedbackLevel?: string;
  actual?: ActualExercise;
  /** Raw resolved exercise instance — opens detail sheet on tap when provided */
  rawExercise?: Record<string, unknown>;
  /** Module role from parent block (general_warmup, primary, secondary, cooldown) */
  moduleRole?: string;
}

/** Format rest as mm:ss (e.g. 120 → "2:00", 90 → "1:30") */
function formatRestMMSS(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

/** Format load with sign: +26 kg or -5 kg */
function formatLoad(kg: number): string {
  return kg >= 0 ? `+${kg} kg` : `${kg} kg`;
}

export function ExerciseCard({ exercise, feedbackLevel, actual, rawExercise, moduleRole }: ExerciseCardProps) {
  const [sheetOpen, setSheetOpen] = useState(false);

  // Phase coloring: resolve visual style from moduleRole or exercise role fallback
  const effectiveRole = moduleRole
    ?? roleToModuleStyle(
      rawExercise
        ? (Array.isArray((rawExercise as Record<string, unknown>).role) ? (rawExercise as Record<string, unknown>).role as string[] : [(rawExercise as Record<string, unknown>).role as string ?? "main"])
        : ["main"]
    );
  const phaseStyle = MODULE_ROLE_STYLES[effectiveRole] ?? MODULE_ROLE_STYLES.primary;

  // Use actual feedback label if available, fall back to exercise_feedback dot
  const effectiveFeedback = actual?.feedback_label ?? feedbackLevel;

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

  // A139: Load delta (only when actual data with load exists)
  const prescribedExternal = exercise.suggested_external_load_kg;
  const usedExternal = actual?.used_external_load_kg;
  const usedTotal = actual?.used_total_load_kg;
  const hasLoadDelta = actual && usedExternal != null && prescribedExternal != null;
  const loadDiff = hasLoadDelta ? usedExternal - prescribedExternal : 0;
  const loadDeltaColor = loadDiff > 0 ? "text-green-400" : loadDiff < 0 ? "text-orange-400" : "text-muted-foreground";

  // A139: Test result detection
  const isTest = exercise.category === "test" || exercise.category === "test_measurement";
  const testField = exercise.testField;
  const testValue = testField && actual ? (actual[testField] as number | undefined) : undefined;
  // Fallback: for max hang tests, used_total_load_kg IS the result
  const testLoadResult = isTest && actual?.used_total_load_kg != null ? actual.used_total_load_kg : undefined;
  const testRepsResult = isTest && actual?.completed_reps != null ? actual.completed_reps : undefined;

  return (
    <>
    <Card
      className={`gap-0 py-0 ${phaseStyle.border} ${phaseStyle.opacity}${rawExercise ? " cursor-pointer active:bg-muted/50 transition-colors" : ""}`}
      onClick={rawExercise ? (e) => { e.stopPropagation(); setSheetOpen(true); } : undefined}
    >
      <CardHeader className="py-2.5">
        <div className="min-w-0">
          {/* Exercise name + feedback badge */}
          <div className="flex items-center gap-1.5">
            <CardTitle className="text-sm flex-1">{exercise.name}</CardTitle>
            {rawExercise && (
              <ChevronRight className="size-3.5 shrink-0 text-muted-foreground/50" />
            )}
            {effectiveFeedback && FEEDBACK_COLORS[effectiveFeedback] ? (
              actual ? (
                <span
                  className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[9px] font-medium leading-none ${FEEDBACK_COLORS[effectiveFeedback]} text-white`}
                >
                  {FEEDBACK_LABELS[effectiveFeedback] ?? effectiveFeedback}
                </span>
              ) : (
                <span
                  className={`inline-block size-2 shrink-0 rounded-full ${FEEDBACK_COLORS[effectiveFeedback]}`}
                  title={effectiveFeedback.replace(/_/g, " ")}
                />
              )
            ) : null}
          </div>

          {/* Prescription line */}
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

          {/* Suggested load (when no actual data) */}
          {!actual && exercise.suggested_external_load_kg != null && (
            <p className="text-[11px] text-muted-foreground/70 mt-0.5">
              Load: +{exercise.suggested_external_load_kg} kg
              {exercise.suggested_total_load_kg != null && (
                <span> (total: {exercise.suggested_total_load_kg} kg)</span>
              )}
              {exercise.load_source === "estimated" && (
                <span className="ml-1 opacity-60">(est.)</span>
              )}
            </p>
          )}

          {/* A139: Load delta — prescribed vs used */}
          {hasLoadDelta && (
            <p className="text-[11px] mt-0.5">
              <span className="text-muted-foreground/70">
                Prescribed: {formatLoad(prescribedExternal)}
              </span>
              <span className="text-muted-foreground/50 mx-1">{"\u2192"}</span>
              <span className={loadDeltaColor}>
                Used: {formatLoad(usedExternal)}
              </span>
              {usedTotal != null && (
                <span className="text-muted-foreground/50 ml-1">
                  ({usedTotal} kg tot)
                </span>
              )}
            </p>
          )}

          {/* A139: Used load without prescribed (no delta, just show what was used) */}
          {actual && usedExternal != null && prescribedExternal == null && (
            <p className="text-[11px] text-muted-foreground/70 mt-0.5">
              Used: {formatLoad(usedExternal)}
              {usedTotal != null && <span> ({usedTotal} kg tot)</span>}
            </p>
          )}

          {/* A139: Used grade (climbing exercises) */}
          {actual?.used_grade && (
            <p className="text-[11px] text-muted-foreground/70 mt-0.5">
              Grade: {actual.used_grade}
            </p>
          )}

          {/* A139: Test results — prominent display */}
          {testValue != null && (
            <p className="text-[11px] font-medium text-amber-400 mt-0.5">
              {"⭐"} Result: {testValue}
              {exercise.testField?.includes("seconds") ? "s" : ""}
            </p>
          )}
          {testLoadResult != null && !testValue && (
            <p className="text-[11px] font-medium text-amber-400 mt-0.5">
              {"⭐"} Max: {testLoadResult} kg total
            </p>
          )}
          {testRepsResult != null && !testValue && (
            <p className="text-[11px] font-medium text-amber-400 mt-0.5">
              {"⭐"} Reps: {testRepsResult}
            </p>
          )}

          {/* Completed sets delta */}
          {actual?.completed_sets != null && exercise.sets != null && !isTest && (
            <p className={`text-[11px] mt-0.5 ${actual.completed_sets >= exercise.sets ? "text-green-400" : "text-orange-400"}`}>
              Sets: {actual.completed_sets}/{exercise.sets}
              {actual.completed_sets >= exercise.sets ? " \u2713" : ""}
            </p>
          )}

          {/* Prescription notes */}
          {exercise.notes && (
            <p className="text-[11px] text-muted-foreground/70 mt-0.5">
              {exercise.notes}
            </p>
          )}

          {/* A139: User notes from feedback */}
          {actual?.notes && (
            <p className="text-[11px] italic text-muted-foreground mt-1">
              {actual.notes}
            </p>
          )}
        </div>
      </CardHeader>
    </Card>
    {rawExercise && (
      <ExerciseDetailSheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        exercise={rawExercise}
      />
    )}
    </>
  );
}
