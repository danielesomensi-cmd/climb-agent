"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { CustomSessionExercise } from "@/lib/types";
import { ChevronUp, ChevronDown, Pencil, Trash2 } from "lucide-react";

function formatPrescription(ex: CustomSessionExercise): string {
  const parts: string[] = [];
  const perSide = ex.alt_sides ? " per side" : "";   // B324
  if (ex.reps != null) parts.push(`${ex.sets}\u00d7${ex.reps}${perSide}`);
  else if (ex.work_seconds != null) parts.push(`${ex.sets}\u00d7${ex.work_seconds}s${perSide}`);
  else parts.push(`${ex.sets} sets${perSide}`);

  if (ex.load_kg > 0) parts.push(`${ex.load_kg}kg`);
  if (ex.rest_between_sets_seconds != null) parts.push(`Rest ${ex.rest_between_sets_seconds}s`);
  return parts.join(" \u00b7 ");
}

interface BuilderExerciseCardProps {
  exercise: CustomSessionExercise;
  name: string;
  index: number;
  total: number;
  tag?: "warmup" | "cooldown";
  onMoveUp: () => void;
  onMoveDown: () => void;
  onEdit: () => void;
  onRemove: () => void;
}

export function BuilderExerciseCard({
  exercise,
  name,
  index,
  total,
  tag,
  onMoveUp,
  onMoveDown,
  onEdit,
  onRemove,
}: BuilderExerciseCardProps) {
  return (
    <div className="flex items-start gap-2 rounded-lg border p-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <p className="text-sm font-medium truncate">{name}</p>
          {tag && (
            <Badge
              variant="outline"
              className={`text-[10px] px-1.5 py-0 shrink-0 ${
                tag === "warmup" ? "text-orange-500 border-orange-500/30" : "text-blue-500 border-blue-500/30"
              }`}
            >
              {tag === "warmup" ? "Warmup" : "Cooldown"}
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">
          {formatPrescription(exercise)}
        </p>
      </div>
      <div className="flex items-center gap-0.5 shrink-0">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          disabled={index === 0}
          onClick={onMoveUp}
        >
          <ChevronUp className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          disabled={index === total - 1}
          onClick={onMoveDown}
        >
          <ChevronDown className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onEdit}>
          <Pencil className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={onRemove}>
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
