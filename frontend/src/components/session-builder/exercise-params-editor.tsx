"use client";

import { useState } from "react";
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerFooter } from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { CustomSessionExercise } from "@/lib/types";
import { Minus, Plus } from "lucide-react";

interface StepperProps {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
  nullable?: boolean;
}

function Stepper({ label, value, onChange, min = 0, max = 999, step = 1, suffix, nullable }: StepperProps) {
  const display = value ?? 0;
  return (
    <div className="flex items-center justify-between">
      <Label className="text-sm">{label}</Label>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => {
            const next = display - step;
            if (nullable && next < min) onChange(null);
            else onChange(Math.max(min, next));
          }}
        >
          <Minus className="h-3 w-3" />
        </Button>
        <span className="w-16 text-center text-sm tabular-nums font-medium">
          {value === null ? "—" : `${value}${suffix ?? ""}`}
        </span>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => onChange(Math.min(max, display + step))}
        >
          <Plus className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

interface ExerciseParamsEditorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  exercise: CustomSessionExercise;
  exerciseName: string;
  /** Whether to show reps vs work_seconds fields */
  hasReps: boolean;
  hasWork: boolean;
  hasRestBetweenReps: boolean;
  onConfirm: (updated: CustomSessionExercise) => void;
}

export function ExerciseParamsEditor({
  open,
  onOpenChange,
  exercise,
  exerciseName,
  hasReps,
  hasWork,
  hasRestBetweenReps,
  onConfirm,
}: ExerciseParamsEditorProps) {
  const [draft, setDraft] = useState<CustomSessionExercise>(exercise);

  // Reset draft when exercise changes
  const exerciseId = exercise.exercise_id;
  const [prevId, setPrevId] = useState(exerciseId);
  if (exerciseId !== prevId) {
    setDraft(exercise);
    setPrevId(exerciseId);
  }

  const update = (patch: Partial<CustomSessionExercise>) =>
    setDraft((d) => ({ ...d, ...patch }));

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle className="text-base">{exerciseName}</DrawerTitle>
        </DrawerHeader>

        <div className="px-4 space-y-5 pb-2">
          <Stepper
            label="Sets"
            value={draft.sets}
            onChange={(v) => update({ sets: v ?? 1 })}
            min={1}
            max={20}
          />

          {hasReps && (
            <Stepper
              label="Reps"
              value={draft.reps}
              onChange={(v) => update({ reps: v })}
              min={1}
              max={100}
              nullable
            />
          )}

          {hasWork && (
            <Stepper
              label="Work"
              value={draft.work_seconds}
              onChange={(v) => update({ work_seconds: v })}
              min={1}
              max={600}
              step={5}
              suffix="s"
              nullable
            />
          )}

          <Stepper
            label="Load"
            value={draft.load_kg}
            onChange={(v) => update({ load_kg: v ?? 0 })}
            min={0}
            max={200}
            step={1}
            suffix="kg"
          />

          <Stepper
            label="Rest between sets"
            value={draft.rest_between_sets_seconds}
            onChange={(v) => update({ rest_between_sets_seconds: v })}
            min={0}
            max={600}
            step={15}
            suffix="s"
            nullable
          />

          {hasRestBetweenReps && (
            <Stepper
              label="Rest between reps"
              value={draft.rest_between_reps_seconds}
              onChange={(v) => update({ rest_between_reps_seconds: v })}
              min={0}
              max={300}
              step={5}
              suffix="s"
              nullable
            />
          )}

          <div className="space-y-1.5">
            <Label className="text-sm">Notes</Label>
            <Input
              value={draft.notes}
              onChange={(e) => update({ notes: e.target.value })}
              placeholder="Optional notes..."
              maxLength={200}
            />
          </div>
        </div>

        <DrawerFooter>
          <Button onClick={() => { onConfirm(draft); onOpenChange(false); }}>
            Confirm
          </Button>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
