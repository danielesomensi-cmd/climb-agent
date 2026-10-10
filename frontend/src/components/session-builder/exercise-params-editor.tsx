"use client";

import { useId, useState } from "react";
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerFooter } from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { CustomSessionExercise } from "@/lib/types";
import { followsTrainingLoad, isAnchoredExercise } from "@/lib/anchored-load";
import { useBuilderExercises } from "@/lib/hooks/queries";
import { Info, Minus, Plus, Trash2 } from "lucide-react";
import { parseStepperInput, stepValue, type StepperBounds } from "./stepper-value";

interface StepperProps {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  min?: number;
  max?: number;
  step?: number;
  /** Decimal places a typed value keeps (0 = integers). */
  decimals?: number;
  suffix?: string;
  nullable?: boolean;
  /** A309: small line under the label (e.g. when a kg is only a fallback). */
  hint?: string;
}

/**
 * A309 — 44px −/+ and a typeable value ("32.5" without twenty taps). The
 * buttons keep their old semantics; a typed value is clamped to the same
 * min/max on blur / Enter.
 */
function Stepper({ label, value, onChange, min = 0, max = 999, step = 1, decimals = 0, suffix, nullable, hint }: StepperProps) {
  const id = useId();
  const bounds: StepperBounds = { min, max, step, nullable, decimals };
  // null = not editing: the field shows the committed value.
  const [text, setText] = useState<string | null>(null);
  const commit = () => {
    if (text !== null) onChange(parseStepperInput(text, value, bounds));
    setText(null);
  };
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="min-w-0">
        <Label htmlFor={id} className="text-sm">{label}</Label>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Button
          variant="outline"
          size="icon"
          className="h-11 w-11"
          aria-label={`Decrease ${label}`}
          onClick={() => onChange(stepValue(value, -1, bounds))}
        >
          <Minus className="h-4 w-4" />
        </Button>
        <div className="relative">
          <input
            id={id}
            type="text"
            inputMode={decimals > 0 ? "decimal" : "numeric"}
            value={text ?? (value === null ? "" : String(value))}
            placeholder="—"
            onFocus={(e) => { setText(value === null ? "" : String(value)); e.currentTarget.select(); }}
            onChange={(e) => setText(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
            className={`h-11 w-20 rounded-md border border-transparent bg-transparent text-center text-base font-medium tabular-nums outline-none focus:border-input ${suffix ? "pr-5" : ""}`}
          />
          {suffix && (
            <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
              {suffix}
            </span>
          )}
        </div>
        <Button
          variant="outline"
          size="icon"
          className="h-11 w-11"
          aria-label={`Increase ${label}`}
          onClick={() => onChange(stepValue(value, 1, bounds))}
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

/** A309: one-line mode explanation, with the long version behind an Info tap. */
function ModeHelp({ short, long }: { short: string; long: string }) {
  return (
    <div className="flex items-center gap-1">
      <p className="flex-1 text-xs text-muted-foreground">{short}</p>
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="icon" className="size-11 shrink-0 text-muted-foreground" aria-label="More about this setting">
            <Info className="h-4 w-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="text-xs text-muted-foreground">{long}</PopoverContent>
      </Popover>
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
  /** A309: "Remove from session" (moved here from the row's trash icon). */
  onRemove?: () => void;
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
  onRemove,
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

        <div className="max-h-[60vh] overflow-y-auto overscroll-contain px-4 space-y-5 pb-2">
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
              <ModeHelp
                short={progressing ? "Sets/reps come from your ladder level on the day." : "Always uses the values below."}
                long={
                  progressing
                    ? "With a recent test, the app sets sets and reps from your level on this ladder on the day you play it, and proposes the next level when you are ready. The values below are used only without one."
                    : "The sets and reps below are used every time you play this session."
                }
              />
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
              <Label className="text-sm">Load mode</Label>
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
              <ModeHelp
                short={fixed ? "Always uses this kg." : "kg set on the day from your max/training load."}
                long={
                  fixed
                    ? "The kg below is used every time you play this session."
                    : anchored
                      ? "With a recent test, the app sets the kg on the day you play it (from your max and training load). The kg below is used only without a recent test."
                      : "The app uses your training load for this exercise on the day you play it, so it moves with your feedback. The kg below is used until you have logged it once."
                }
              />
            </div>
          )}

          <Stepper
            label="Load"
            hint={
              anchored && !fixed
                ? "used only without a recent test"
                : follows && !fixed
                  ? "used only until you have logged it once"
                  : undefined
            }
            value={draft.load_kg}
            onChange={(v) => update({ load_kg: v ?? 0 })}
            min={0}
            max={200}
            step={0.5}
            decimals={2}
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

        <DrawerFooter className="grid grid-cols-2 gap-2">
          <Button variant="outline" className="h-11" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button className="h-11" onClick={() => { onConfirm(draft); onOpenChange(false); }}>
            Confirm
          </Button>
          {onRemove && (
            <Button
              variant="ghost"
              className="col-span-2 h-11 text-destructive hover:text-destructive"
              onClick={() => { onOpenChange(false); onRemove(); }}
            >
              <Trash2 className="h-4 w-4" />
              Remove from session
            </Button>
          )}
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
