"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Check, SkipForward, Lightbulb, Film } from "lucide-react";
import type { GuidedExercise } from "@/lib/types";
import { ExerciseTimer } from "@/components/guided/exercise-timer";

interface GuidedExerciseStepProps {
  exercise: GuidedExercise;
  isTestSession?: boolean;
  bodyweightKg?: number;
  onDone: (feedbackLabel: string, usedLoad?: number, usedGrade?: string, usedTotalLoad?: number, testMeasurement?: number) => void;
  onSkip: () => void;
  onSetChange?: (completedSets: number) => void;
}

const FEEDBACK_OPTIONS = [
  { value: "very_easy", label: "Very easy", color: "bg-green-600" },
  { value: "easy", label: "Easy", color: "bg-green-500" },
  { value: "ok", label: "OK", color: "bg-yellow-500" },
  { value: "hard", label: "Hard", color: "bg-orange-500" },
  { value: "very_hard", label: "Very hard", color: "bg-red-500" },
];

function formatRest(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? (s > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${m}:00`) : `${s}s`;
}

function formatPrescription(ex: GuidedExercise): string[] {
  const lines: string[] = [];
  const p = ex.prescription;

  // Main scheme
  if (p.sets && p.reps && p.workSeconds) {
    // Timed reps: "3 × 3 × 30s"
    const work = p.workSeconds >= 60 ? `${Math.round(p.workSeconds / 60)} min` : `${p.workSeconds}s`;
    lines.push(`${p.sets} \u00d7 ${p.reps} \u00d7 ${work}`);
  } else if (p.sets && p.reps) {
    lines.push(`${p.sets} \u00d7 ${p.reps}`);
  } else if (p.sets && p.workSeconds) {
    if (p.workSeconds >= 60) {
      lines.push(`${p.sets} \u00d7 ${Math.round(p.workSeconds / 60)} min`);
    } else {
      lines.push(`${p.sets} \u00d7 ${p.workSeconds}s`);
    }
  } else if (p.workSeconds) {
    if (p.workSeconds >= 60) {
      lines.push(`${Math.round(p.workSeconds / 60)} min`);
    } else {
      lines.push(`${p.workSeconds}s`);
    }
  }

  // Rest info
  if (p.restBetweenRepsSeconds) {
    lines.push(`Hold between reps: ${formatRest(p.restBetweenRepsSeconds)}`);
  }
  if (p.restSeconds) {
    const label = p.restBetweenRepsSeconds ? "Set rest" : "Rest";
    lines.push(`${label}: ${formatRest(p.restSeconds)}`);
  }

  if (p.loadKg) {
    lines.push(`Load: ${p.loadKg} kg`);
  }

  if (p.tempo) {
    lines.push(`Tempo: ${p.tempo}`);
  }

  return lines;
}

export function GuidedExerciseStep({
  exercise,
  isTestSession,
  bodyweightKg,
  onDone,
  onSkip,
  onSetChange,
}: GuidedExerciseStepProps) {
  const [feedback, setFeedback] = useState(exercise.feedbackLabel || "ok");
  const [loadInput, setLoadInput] = useState("");
  const [gradeInput, setGradeInput] = useState("");
  const [measurementInput, setMeasurementInput] = useState("");

  // Test measurement exercises: just a number input, no feedback
  const isTestMeasurement = exercise.category === "test_measurement" && !!exercise.testField;

  // Test session total_load exercises get two mandatory fields
  const isTestLoadExercise = !isTestMeasurement && isTestSession && exercise.loadModel === "total_load";

  // Determine which kind of editable field to show
  const hasLoadField =
    !isTestLoadExercise &&
    !isTestMeasurement &&
    exercise.loadModel !== "bodyweight_only" &&
    (exercise.suggested.externalLoadKg != null || exercise.suggested.totalLoadKg != null);
  const hasGradeField = !isTestMeasurement && exercise.suggested.grade != null;

  // Pre-populate from suggested values or previous user input
  useEffect(() => {
    if (exercise.usedLoadKg != null) {
      setLoadInput(String(exercise.usedLoadKg));
    } else if (exercise.suggested.externalLoadKg != null) {
      setLoadInput(String(exercise.suggested.externalLoadKg));
    }
    if (exercise.usedGrade != null) {
      setGradeInput(exercise.usedGrade);
    } else if (exercise.suggested.grade) {
      setGradeInput(exercise.suggested.grade);
    }
    if (exercise.testMeasurement != null) {
      setMeasurementInput(String(exercise.testMeasurement));
    }
    setFeedback(exercise.feedbackLabel || "ok");
  }, [exercise]);

  const prescriptionLines = formatPrescription(exercise);
  const isAlreadyDone = exercise.status === "done";
  const isAlreadySkipped = exercise.status === "skipped";

  function handleDone() {
    if (isTestMeasurement) {
      const val = measurementInput ? parseFloat(measurementInput) : undefined;
      onDone("ok", undefined, undefined, undefined, val);
      return;
    }
    if (isTestLoadExercise) {
      const usedExternal = loadInput ? parseFloat(loadInput) : undefined;
      const usedTotal = usedExternal != null && bodyweightKg != null
        ? bodyweightKg + usedExternal
        : undefined;
      onDone(feedback, usedExternal, undefined, usedTotal);
      return;
    }
    const usedLoad = hasLoadField && loadInput ? parseFloat(loadInput) : undefined;
    const usedGrade = hasGradeField && gradeInput ? gradeInput : undefined;
    onDone(feedback, usedLoad, usedGrade);
  }

  return (
    <Card className="gap-0 py-0">
      <CardHeader className="py-4">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">{exercise.name || exercise.exerciseId.replace(/_/g, " ")}</CardTitle>
          {isAlreadyDone && (
            <Badge className="bg-green-600 text-white text-[10px]">Done</Badge>
          )}
          {isAlreadySkipped && (
            <Badge className="bg-red-400 text-white text-[10px]">Skipped</Badge>
          )}
        </div>
        {exercise.category && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {exercise.category.replace(/_/g, " ")}
          </p>
        )}
      </CardHeader>

      <CardContent className="pb-4 space-y-4">
        {/* Prescription */}
        {prescriptionLines.length > 0 && (
          <div className="space-y-1">
            {prescriptionLines.map((line, i) => (
              <p key={i} className="text-sm">{line}</p>
            ))}
          </div>
        )}

        {exercise.prescription.notes && (
          <p className="text-xs text-muted-foreground italic">
            {exercise.prescription.notes}
          </p>
        )}

        {/* Cues */}
        {exercise.cues && exercise.cues.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Cues:</p>
            <ul className="space-y-0.5">
              {exercise.cues.map((cue, i) => (
                <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                  <span className="mt-1.5 block h-1 w-1 shrink-0 rounded-full bg-muted-foreground/50" />
                  {cue}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Video link */}
        {exercise.videoUrl && (
          <a
            href={exercise.videoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
          >
            <Film className="size-3.5" />
            Watch video
          </a>
        )}

        {/* Test measurement: single value input, no feedback/timer */}
        {isTestMeasurement ? (
          <div className="space-y-3 rounded-md border border-primary/30 bg-primary/5 p-3">
            <p className="text-xs font-medium text-primary">Record your result</p>
            <div className="space-y-1.5">
              <Label htmlFor="measurement-input" className="text-xs text-muted-foreground">
                Result ({exercise.testUnit ?? "value"}) *
              </Label>
              <Input
                id="measurement-input"
                type="number"
                step={exercise.testUnit === "cm" ? "1" : "0.5"}
                min="0"
                value={measurementInput}
                onChange={(e) => setMeasurementInput(e.target.value)}
                className="w-40 h-9"
                placeholder={exercise.testUnit === "seconds" ? "e.g. 65" : exercise.testUnit === "cm" ? "e.g. 120" : ""}
                required
              />
            </div>
          </div>
        ) : (
          <>
            {/* Suggested load/grade */}
            {(exercise.suggested.externalLoadKg != null ||
              exercise.suggested.totalLoadKg != null ||
              exercise.suggested.grade != null) && (
              <div className="flex items-start gap-2 rounded-md bg-primary/5 border border-primary/20 p-3">
                <Lightbulb className="size-4 text-primary mt-0.5 shrink-0" />
                <div className="text-sm space-y-0.5 w-full">
                  {exercise.suggested.externalLoadKg != null && (
                    <p>
                      Suggested: <span className="font-semibold">+{exercise.suggested.externalLoadKg} kg</span>
                      {exercise.suggested.totalLoadKg != null && (
                        <span className="text-muted-foreground"> (total: {exercise.suggested.totalLoadKg} kg)</span>
                      )}
                      {exercise.suggested.loadSource === "estimated" && (
                        <span className="text-xs text-muted-foreground ml-1">(estimated)</span>
                      )}
                    </p>
                  )}
                  {exercise.suggested.grade && (
                    <p>
                      Target: <span className="font-semibold">{exercise.suggested.grade}</span>
                      {exercise.suggested.surface && (
                        <span className="text-muted-foreground"> on {exercise.suggested.surface}</span>
                      )}
                    </p>
                  )}
                  {exercise.suggested.loadWarning && (
                    <p className="text-xs text-orange-500 mt-1">
                      ⚠ Baseline outdated — run a max hang test for accurate suggestions.
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Exercise timer — shown for timed exercises AND multi-set rep-based exercises */}
            {(((exercise.prescription.workSeconds ?? 0) > 0) ||
              ((exercise.prescription.sets ?? 1) > 1 && (exercise.prescription.restSeconds ?? 0) > 0)) && (
              <ExerciseTimer
                workSeconds={exercise.prescription.workSeconds ?? 0}
                restBetweenRepsSeconds={exercise.prescription.restBetweenRepsSeconds ?? 0}
                restBetweenSetsSeconds={exercise.prescription.restSeconds ?? 0}
                sets={exercise.prescription.sets ?? 1}
                reps={typeof exercise.prescription.reps === "number" ? exercise.prescription.reps : 1}
                initialSet={
                  exercise.completedSets != null &&
                  exercise.completedSets < (exercise.prescription.sets ?? 1)
                    ? exercise.completedSets + 1
                    : 1
                }
                onSetChange={onSetChange}
              />
            )}

            {/* Feedback selector */}
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">How did it feel?</Label>
              <div className="flex flex-wrap gap-1.5">
                {FEEDBACK_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setFeedback(opt.value)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition-all ${
                      feedback === opt.value
                        ? `${opt.color} text-white ring-2 ring-offset-1 ring-offset-background ring-${opt.color.replace("bg-", "")}`
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Test session: external load input with auto-computed total */}
            {isTestLoadExercise && (
              <div className="space-y-3 rounded-md border border-primary/30 bg-primary/5 p-3">
                <p className="text-xs font-medium text-primary">Record your test result</p>
                <div className="space-y-1.5">
                  <Label htmlFor="external-load-input" className="text-xs text-muted-foreground">
                    External load added (kg) *
                  </Label>
                  <Input
                    id="external-load-input"
                    type="number"
                    step="0.5"
                    min="0"
                    value={loadInput}
                    onChange={(e) => setLoadInput(e.target.value)}
                    className="w-40 h-9"
                    placeholder="e.g. 15"
                    required
                  />
                </div>
                {bodyweightKg != null && loadInput && !isNaN(parseFloat(loadInput)) && (
                  <p className="text-sm text-muted-foreground">
                    Total load:{" "}
                    <span className="font-semibold text-foreground">
                      {(bodyweightKg + parseFloat(loadInput)).toFixed(1)} kg
                    </span>
                    <span className="text-xs ml-1">
                      (your weight {bodyweightKg} kg + {loadInput} kg added)
                    </span>
                  </p>
                )}
              </div>
            )}

            {/* Editable load field (non-test sessions) */}
            {hasLoadField && (
              <div className="space-y-1.5">
                <Label htmlFor="load-input" className="text-xs text-muted-foreground">
                  Actual load used (kg)
                </Label>
                <Input
                  id="load-input"
                  type="number"
                  step="0.5"
                  value={loadInput}
                  onChange={(e) => setLoadInput(e.target.value)}
                  className="w-32 h-9"
                  placeholder="kg"
                />
              </div>
            )}

            {/* Editable grade field */}
            {hasGradeField && (
              <div className="space-y-1.5">
                <Label htmlFor="grade-input" className="text-xs text-muted-foreground">
                  Actual grade used
                </Label>
                <Input
                  id="grade-input"
                  type="text"
                  value={gradeInput}
                  onChange={(e) => setGradeInput(e.target.value)}
                  className="w-32 h-9"
                  placeholder="e.g. 7A"
                />
              </div>
            )}
          </>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2 pt-2">
          <Button
            size="sm"
            variant="outline"
            className="text-muted-foreground"
            onClick={onSkip}
          >
            <SkipForward className="size-4 mr-1" />
            Skip
          </Button>
          <Button
            size="sm"
            className="bg-green-600 hover:bg-green-700 text-white flex-1"
            onClick={handleDone}
          >
            <Check className="size-4 mr-1" />
            {isAlreadyDone ? "Update" : "Done"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
