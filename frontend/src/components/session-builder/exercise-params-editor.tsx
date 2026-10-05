"use client";

import { useState } from "react";
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerFooter } from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { CustomSessionExercise } from "@/lib/types";
import { followsTrainingLoad, isAnchoredExercise } from "@/lib/anchored-load";
import { useBuilderExercises } from "@/lib/hooks/queries";
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

  // B364: missing load_mode on an anchored exercise means "anchored" (backend default).
  const anchored = isAnchoredExercise(draft.exercise_id);
  // A298: a level of a bodyweight ladder — Progress (follow my level) / Fixed.
  const { data: catalogData } = useBuilderExercises("", "");
  const catalogEntry = (catalogData?.exercises ?? []).find((e) => e.id === draft.exercise_id);
  const ladderable = draft.progress_mode != null || !!catalogEntry?.ladder;
  const progressing = draft.progress_mode === "ladder";
  // A304: any other weighted row follows the training load unless fixed.
  const follows = followsTrainingLoad(draft, catalogEntry?.load_model);
  const fixed = (anchored || follows) && draft.load_mode === "fixed";

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle className="text-base">{exerciseName}</DrawerTitle>
        </DrawerHeader>

        <div className="px-4 space-y-5 pb-2">
          {ladderable && (
            <div className="space-y-1.5">
              <Label className="text-sm">Dose</Label>
              <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Progress mode">
                <Button
                  type="button"
                  role="radio"
                  aria-checked={progressing}
                  variant={progressing ? "default" : "outline"}
                  size="sm"
                  onClick={() => update({ progress_mode: "ladder" })}
                >
                  Progress
                </Button>
                <Button
                  type="button"
                  role="radio"
                  aria-checked={!progressing}
                  variant={progressing ? "outline" : "default"}
                  size="sm"
                  onClick={() => update({ progress_mode: "fixed" })}
                >
                  Fixed
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                {progressing
                  ? "With a recent test, the app sets sets and reps from your level on this ladder on the day you play it, and proposes the next level when you are ready. The values below are used only without one."
                  : "The sets and reps below are used every time you play this session."}
              </p>
            </div>
          )}

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

          {(anchored || follows) && (
            <div className="space-y-1.5">
              <Label className="text-sm">Load</Label>
              {/* B364: anchored exercises follow your tested max unless you fix the kg.
                  A304: other weighted rows follow your training load unless you fix it. */}
              <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Load mode">
                <Button
                  type="button"
                  role="radio"
                  aria-checked={!fixed}
                  variant={fixed ? "outline" : "default"}
                  size="sm"
                  onClick={() => update({ load_mode: "anchored" })}
                >
                  Auto
                </Button>
                <Button
                  type="button"
                  role="radio"
                  aria-checked={fixed}
                  variant={fixed ? "default" : "outline"}
                  size="sm"
                  onClick={() => update({ load_mode: "fixed" })}
                >
                  Fixed kg
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                {fixed
                  ? "The kg below is used every time you play this session."
                  : anchored
                    ? "With a recent test, the app sets the kg on the day you play it (from your max and training load). The kg below is used only without a recent test."
                    : "The app uses your training load for this exercise on the day you play it, so it moves with your feedback. The kg below is used until you have logged it once."}
              </p>
            </div>
          )}

          <Stepper
            label={
              anchored && !fixed ? "Kg without a recent test" : follows && !fixed ? "Kg until first logged" : "Load"
            }
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
