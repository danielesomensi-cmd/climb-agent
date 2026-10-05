"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  hasGradeInput,
  hasLoadInput,
  hasProblemLog,
  prefilledGrade,
  type FeedbackDialogExercise,
} from "@/lib/feedback-items";
import type { MeasureValues } from "@/lib/measured-feedback";
import type { BoulderGradeSystem } from "@/lib/gradeUtils";
import type { LimitProblemDraft, SessionPain } from "@/lib/types";
import { MeasureInput, PainPicker } from "@/components/training/measured-feedback-inputs";
import { LimitProblemLogger } from "@/components/training/limit-problem-logger";

interface FeedbackDialogProps {
  open: boolean;
  onClose: () => void;
  /**
   * B288: `loads` (kg per exercise_id) is the third argument. Without it the
   * engine's load memory never updates for sessions completed from here — see
   * lib/feedback-items.ts.
   */
  /**
   * A295: `feedback` holds ONLY the exercises the user rated (untouched = not
   * rated, never a silent "ok"); `measures` the optional last-set reps / hang
   * margin; `pain` the session's "Any pain?" answer (null = not answered).
   * A299: `grades` (grade typed per exercise; untouched = the pre-filled
   * target) and `problems` (limit problem rows) — the same two inputs the
   * guided player collects, fed to the same payload builder.
   */
  onSubmit: (
    feedback: Record<string, string>,
    durationMinutes: number,
    loads: Record<string, number>,
    measures: Record<string, MeasureValues>,
    pain: SessionPain | null,
    grades: Record<string, string>,
    problems: Record<string, LimitProblemDraft[]>,
  ) => void;
  exercises: FeedbackDialogExercise[];
  /** Session slot — used to pre-fill duration estimate */
  slot?: string;
  /** A299: boulder display preference for the problem logger (render-only). */
  gradeSystem?: BoulderGradeSystem;
}

/** Difficulty levels with mapping to backend values */
const DIFFICULTY_LEVELS = [
  { value: "very_easy", label: "Very easy" },
  { value: "easy", label: "Easy" },
  { value: "ok", label: "Ok" },
  { value: "hard", label: "Hard" },
  { value: "very_hard", label: "Very hard" },
] as const;

/** Slot-based duration estimates (minutes) */
const SLOT_ESTIMATES: Record<string, number> = {
  lunch: 35,
  morning: 60,
  afternoon: 60,
  evening: 90,
};

export function FeedbackDialog({
  open,
  onClose,
  onSubmit,
  exercises,
  slot,
  gradeSystem = "font",
}: FeedbackDialogProps) {
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const estimatedMin = slot ? SLOT_ESTIMATES[slot] ?? 60 : 60;
  const [durationStr, setDurationStr] = useState(String(estimatedMin));
  // B288: kg per exercise, pre-filled with the suggested load. Same contract as
  // the guided player — submitting untouched confirms the proposed load, which
  // is what keeps the load memory alive instead of decaying to the fallback.
  const [loadStr, setLoadStr] = useState<Record<string, string>>({});
  // A295: optional measures + session pain — nothing pre-selected.
  const [measures, setMeasures] = useState<Record<string, MeasureValues>>({});
  const [pain, setPain] = useState<SessionPain | null>(null);
  // A299: grade typed per exercise (absent = the pre-filled target) and the
  // limit problem rows — no row exists until the athlete adds one.
  const [grades, setGrades] = useState<Record<string, string>>({});
  const [problems, setProblems] = useState<Record<string, LimitProblemDraft[]>>({});

  function setMeasure(exerciseId: string, patch: MeasureValues) {
    setMeasures((prev) => ({ ...prev, [exerciseId]: { ...(prev[exerciseId] ?? {}), ...patch } }));
  }

  function resetAll() {
    setFeedback({});
    setLoadStr({});
    setMeasures({});
    setPain(null);
    setGrades({});
    setProblems({});
    setDurationStr(String(estimatedMin));
  }

  function loadValue(ex: FeedbackDialogExercise): string {
    const typed = loadStr[ex.exercise_id];
    if (typed != null) return typed;
    return ex.suggestedExternalLoadKg != null ? String(ex.suggestedExternalLoadKg) : "";
  }

  function handleValueChange(exerciseId: string, value: string) {
    setFeedback((prev) => ({ ...prev, [exerciseId]: value }));
  }

  function handleSubmit() {
    // A295: only what was rated. An untouched exercise is "not rated" — the
    // engine holds its load and the report/coach do not invent an "ok".
    const rated: Record<string, string> = {};
    for (const ex of exercises) {
      if (feedback[ex.exercise_id]) rated[ex.exercise_id] = feedback[ex.exercise_id];
    }
    const loads: Record<string, number> = {};
    for (const ex of exercises) {
      if (!hasLoadInput(ex)) continue;
      const raw = loadValue(ex);
      if (raw === "") continue;
      const parsedLoad = parseFloat(raw);
      if (!isNaN(parsedLoad) && parsedLoad >= 0) loads[ex.exercise_id] = parsedLoad;
    }
    const parsed = parseInt(durationStr, 10);
    const userEntered = !isNaN(parsed) && parsed > 0;
    const dur = userEntered ? parsed : estimatedMin;
    // B217: duration_source dropped — was a Potemkin field (never persisted
    // server-side, read only with hard-coded default).
    onSubmit(rated, dur, loads, measures, pain, grades, problems);
    resetAll();
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      onClose();
      resetAll();
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Session feedback</DialogTitle>
          <DialogDescription>
            Rate the exercises you want to. Untouched exercises are saved as not rated and don&apos;t change your loads.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-2">
          {exercises.map((exercise) => (
            <div key={exercise.exercise_id} className="space-y-2">
              <p className="text-sm font-medium">{exercise.name}</p>
              <RadioGroup
                value={feedback[exercise.exercise_id] ?? ""}
                aria-label={`${exercise.name} difficulty`}
                onValueChange={(v) =>
                  handleValueChange(exercise.exercise_id, v)
                }
                className="grid grid-cols-5 gap-1"
              >
                {DIFFICULTY_LEVELS.map((level) => (
                  <div
                    key={level.value}
                    className="flex flex-col items-center gap-1"
                  >
                    <RadioGroupItem
                      value={level.value}
                      id={`${exercise.exercise_id}-${level.value}`}
                    />
                    <Label
                      htmlFor={`${exercise.exercise_id}-${level.value}`}
                      className="text-xs text-center leading-tight cursor-pointer text-muted-foreground"
                    >
                      {level.label}
                    </Label>
                  </div>
                ))}
              </RadioGroup>

              {/* A295: optional measure (last-set reps / hang margin) */}
              {exercise.measure && (
                <MeasureInput
                  id={`${exercise.exercise_id}-measure`}
                  measure={exercise.measure}
                  prescribedReps={exercise.prescribedReps}
                  targetReps={exercise.targetReps}
                  lastSetReps={measures[exercise.exercise_id]?.lastSetReps}
                  hangMargin={measures[exercise.exercise_id]?.hangMargin}
                  onLastSetReps={(v) => setMeasure(exercise.exercise_id, { lastSetReps: v })}
                  onHangMargin={(v) => setMeasure(exercise.exercise_id, { hangMargin: v })}
                />
              )}

              {/* A299: limit family — the guided player's problem logger */}
              {hasProblemLog(exercise) && (
                <LimitProblemLogger
                  idPrefix={exercise.exercise_id}
                  target={exercise.grade}
                  targetLow={exercise.gradeLow}
                  problems={problems[exercise.exercise_id] ?? []}
                  onChange={(rows) =>
                    setProblems((prev) => ({ ...prev, [exercise.exercise_id]: rows }))
                  }
                  gradeSystem={gradeSystem}
                />
              )}

              {/* A299: grade actually climbed (pre-filled with the target, as in the guided player) */}
              {hasGradeInput(exercise) && !hasProblemLog(exercise) && (
                <div className="flex items-center gap-2 pt-1">
                  <Label
                    htmlFor={`${exercise.exercise_id}-grade`}
                    className="text-xs text-muted-foreground"
                  >
                    Actual grade used
                  </Label>
                  <Input
                    id={`${exercise.exercise_id}-grade`}
                    type="text"
                    value={grades[exercise.exercise_id] ?? prefilledGrade(exercise)}
                    onChange={(e) =>
                      setGrades((prev) => ({ ...prev, [exercise.exercise_id]: e.target.value }))
                    }
                    className="w-24 h-8"
                    placeholder="e.g. 7A"
                  />
                </div>
              )}

              {/* B288: load actually used — the engine's only progression input */}
              {hasLoadInput(exercise) && (
                <div className="flex items-center gap-2 pt-1">
                  <Label
                    htmlFor={`${exercise.exercise_id}-load`}
                    className="text-xs text-muted-foreground"
                  >
                    Load used
                  </Label>
                  <Input
                    id={`${exercise.exercise_id}-load`}
                    type="number"
                    inputMode="decimal"
                    step="0.5"
                    min={0}
                    value={loadValue(exercise)}
                    onChange={(e) =>
                      setLoadStr((prev) => ({
                        ...prev,
                        [exercise.exercise_id]: e.target.value,
                      }))
                    }
                    className="w-24 h-8"
                    placeholder="kg"
                  />
                  <span className="text-xs text-muted-foreground">kg</span>
                </div>
              )}
            </div>
          ))}

          {/* A295: session pain, one tap */}
          <div className="border-t pt-4">
            <PainPicker value={pain} onChange={setPain} />
          </div>

          {/* B127: Duration input */}
          <div className="space-y-2 border-t pt-4">
            <Label htmlFor="session-duration" className="text-sm font-medium">
              Session duration (minutes)
            </Label>
            <div className="flex items-center gap-2">
              <Input
                id="session-duration"
                type="number"
                inputMode="numeric"
                min={1}
                max={600}
                step={5}
                value={durationStr}
                onChange={(e) => setDurationStr(e.target.value)}
                className="w-24"
              />
              <span className="text-xs text-muted-foreground">min</span>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Pre-filled with estimate. Leave empty to skip.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit}>
            Submit feedback
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
