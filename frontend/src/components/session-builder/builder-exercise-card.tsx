"use client";

import { Button } from "@/components/ui/button";
import type { CustomSessionExercise } from "@/lib/types";
import { isAutoLoadRow } from "@/lib/anchored-load";
import { ChevronUp, ChevronDown } from "lucide-react";

function formatPrescription(ex: CustomSessionExercise, loadModel?: string): string {
  const parts: string[] = [];
  const perSide = ex.alt_sides ? " per side" : "";   // B324
  if (ex.reps != null) parts.push(`${ex.sets}×${ex.reps}${perSide}`);
  else if (ex.work_seconds != null) parts.push(`${ex.sets}×${ex.work_seconds}s${perSide}`);
  else parts.push(`${ex.sets} sets${perSide}`);

  // B364 / A304: a row in "Auto" gets its kg on the day it is played.
  if (isAutoLoadRow(ex, loadModel)) parts.push("Auto load");
  if (ex.progress_mode === "ladder") parts.push("Follows level");
  else if (ex.load_kg > 0) parts.push(`${ex.load_kg}kg`);
  if (ex.rest_between_sets_seconds != null) parts.push(`Rest ${ex.rest_between_sets_seconds}s`);
  return parts.join(" · ");
}

interface BuilderExerciseCardProps {
  exercise: CustomSessionExercise;
  name: string;
  /** 1-based position in the session (playback order). */
  position: number;
  /** A304: catalog load model, to tell an "Auto load" row. */
  loadModel?: string;
  /** A309: reorder stays inside the row's Warmup / Main / Cooldown group. */
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
  /** Tap on the row: opens the params drawer (Remove lives there). */
  onEdit: () => void;
}

export function BuilderExerciseCard({
  exercise,
  name,
  position,
  loadModel,
  canMoveUp,
  canMoveDown,
  onMoveUp,
  onMoveDown,
  onEdit,
}: BuilderExerciseCardProps) {
  return (
    <div className="flex items-stretch rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={onEdit}
        aria-label={`Edit ${name}`}
        className="flex min-h-[56px] min-w-0 flex-1 items-start gap-2 rounded-lg p-3 text-left transition-colors hover:bg-accent active:scale-[0.99]"
      >
        <span className="w-5 shrink-0 pt-0.5 text-xs tabular-nums text-muted-foreground">{position}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium line-clamp-2">{name}</span>
          <span className="mt-0.5 block text-xs text-muted-foreground">
            {formatPrescription(exercise, loadModel)}
          </span>
        </span>
      </button>
      <div className="flex shrink-0 flex-col">
        <Button
          variant="ghost"
          size="icon"
          className="h-11 w-9"
          disabled={!canMoveUp}
          onClick={onMoveUp}
          aria-label={`Move ${name} up`}
        >
          <ChevronUp className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-11 w-9"
          disabled={!canMoveDown}
          onClick={onMoveDown}
          aria-label={`Move ${name} down`}
        >
          <ChevronDown className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
