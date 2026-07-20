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
import { hasLoadInput, type FeedbackDialogExercise } from "@/lib/feedback-items";

interface FeedbackDialogProps {
  open: boolean;
  onClose: () => void;
  /**
   * B288: `loads` (kg per exercise_id) is the third argument. Without it the
   * engine's load memory never updates for sessions completed from here — see
   * lib/feedback-items.ts.
   */
  onSubmit: (
    feedback: Record<string, string>,
    durationMinutes: number,
    loads: Record<string, number>,
  ) => void;
  exercises: FeedbackDialogExercise[];
  /** Session slot — used to pre-fill duration estimate */
  slot?: string;
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
}: FeedbackDialogProps) {
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const estimatedMin = slot ? SLOT_ESTIMATES[slot] ?? 60 : 60;
  const [durationStr, setDurationStr] = useState(String(estimatedMin));
  // B288: kg per exercise, pre-filled with the suggested load. Same contract as
  // the guided player — submitting untouched confirms the proposed load, which
  // is what keeps the load memory alive instead of decaying to the fallback.
  const [loadStr, setLoadStr] = useState<Record<string, string>>({});

  function loadValue(ex: FeedbackDialogExercise): string {
    const typed = loadStr[ex.exercise_id];
    if (typed != null) return typed;
    return ex.suggestedExternalLoadKg != null ? String(ex.suggestedExternalLoadKg) : "";
  }

  function handleValueChange(exerciseId: string, value: string) {
    setFeedback((prev) => ({ ...prev, [exerciseId]: value }));
  }

  function handleSubmit() {
    // Default unrated exercises to "ok"
    const complete: Record<string, string> = {};
    for (const ex of exercises) {
      complete[ex.exercise_id] = feedback[ex.exercise_id] ?? "ok";
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
    onSubmit(complete, dur, loads);
    setFeedback({});
    setLoadStr({});
    setDurationStr(String(estimatedMin));
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      onClose();
      setFeedback({});
      setLoadStr({});
      setDurationStr(String(estimatedMin));
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Session feedback</DialogTitle>
          <DialogDescription>
            Rate the perceived difficulty for each exercise. Unrated exercises default to &quot;Ok&quot;.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-2">
          {exercises.map((exercise) => (
            <div key={exercise.exercise_id} className="space-y-2">
              <p className="text-sm font-medium">{exercise.name}</p>
              <RadioGroup
                value={feedback[exercise.exercise_id] ?? ""}
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
