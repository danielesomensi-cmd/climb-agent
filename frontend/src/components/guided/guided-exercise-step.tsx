"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Check, SkipForward, Lightbulb, Film } from "lucide-react";
import type { GuidedExercise } from "@/lib/types";

interface GuidedExerciseStepProps {
  exercise: GuidedExercise;
  onDone: (feedbackLabel: string, usedLoad?: number, usedGrade?: string) => void;
  onSkip: () => void;
}

const FEEDBACK_OPTIONS = [
  { value: "very_easy", label: "Very easy", color: "bg-green-600" },
  { value: "easy", label: "Easy", color: "bg-green-500" },
  { value: "ok", label: "OK", color: "bg-yellow-500" },
  { value: "hard", label: "Hard", color: "bg-orange-500" },
  { value: "very_hard", label: "Very hard", color: "bg-red-500" },
];

function formatPrescription(ex: GuidedExercise): string[] {
  const lines: string[] = [];
  const p = ex.prescription;

  if (p.sets && p.reps) {
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

  if (p.restSeconds) {
    const m = Math.floor(p.restSeconds / 60);
    const s = p.restSeconds % 60;
    const rest = m > 0 ? (s > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${m}:00`) : `${s}s`;
    lines.push(`Rest: ${rest}`);
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
  onDone,
  onSkip,
}: GuidedExerciseStepProps) {
  const [feedback, setFeedback] = useState(exercise.feedbackLabel || "ok");
  const [loadInput, setLoadInput] = useState("");
  const [gradeInput, setGradeInput] = useState("");

  // Determine which kind of editable field to show
  const hasLoadField =
    exercise.loadModel !== "bodyweight_only" &&
    (exercise.suggested.externalLoadKg != null || exercise.suggested.totalLoadKg != null);
  const hasGradeField = exercise.suggested.grade != null;

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
    setFeedback(exercise.feedbackLabel || "ok");
  }, [exercise]);

  const prescriptionLines = formatPrescription(exercise);
  const isAlreadyDone = exercise.status === "done";
  const isAlreadySkipped = exercise.status === "skipped";

  function handleDone() {
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

        {/* Suggested load/grade */}
        {(exercise.suggested.externalLoadKg != null ||
          exercise.suggested.totalLoadKg != null ||
          exercise.suggested.grade != null) && (
          <div className="flex items-start gap-2 rounded-md bg-primary/5 border border-primary/20 p-3">
            <Lightbulb className="size-4 text-primary mt-0.5 shrink-0" />
            <div className="text-sm space-y-0.5">
              {exercise.suggested.externalLoadKg != null && (
                <p>
                  Suggested: <span className="font-semibold">+{exercise.suggested.externalLoadKg} kg</span>
                  {exercise.suggested.totalLoadKg != null && (
                    <span className="text-muted-foreground"> (total: {exercise.suggested.totalLoadKg} kg)</span>
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
            </div>
          </div>
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

        {/* Editable load field */}
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
