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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";

interface FeedbackDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (feedback: Record<string, string>) => void;
  exercises: Array<{ exercise_id: string; name: string }>;
}

/** Difficulty levels with mapping to backend values */
const DIFFICULTY_LEVELS = [
  { value: "very_easy", label: "Very easy" },
  { value: "easy", label: "Easy" },
  { value: "ok", label: "Ok" },
  { value: "hard", label: "Hard" },
  { value: "very_hard", label: "Very hard" },
] as const;

export function FeedbackDialog({
  open,
  onClose,
  onSubmit,
  exercises,
}: FeedbackDialogProps) {
  const [feedback, setFeedback] = useState<Record<string, string>>({});

  function handleValueChange(exerciseId: string, value: string) {
    setFeedback((prev) => ({ ...prev, [exerciseId]: value }));
  }

  function handleSubmit() {
    // Default unrated exercises to "ok"
    const complete: Record<string, string> = {};
    for (const ex of exercises) {
      complete[ex.exercise_id] = feedback[ex.exercise_id] ?? "ok";
    }
    onSubmit(complete);
    setFeedback({});
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      onClose();
      setFeedback({});
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
                      className="text-[10px] text-center leading-tight cursor-pointer text-muted-foreground"
                    >
                      {level.label}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </div>
          ))}
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
