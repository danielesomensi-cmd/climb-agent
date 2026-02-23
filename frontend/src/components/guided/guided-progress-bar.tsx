"use client";

import { cn } from "@/lib/utils";
import type { GuidedExercise } from "@/lib/types";

interface GuidedProgressBarProps {
  exercises: GuidedExercise[];
  currentIndex: number;
  onNavigate: (index: number) => void;
}

export function GuidedProgressBar({
  exercises,
  currentIndex,
  onNavigate,
}: GuidedProgressBarProps) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1.5 flex-1 flex-wrap">
        {exercises.map((ex, i) => (
          <button
            key={i}
            type="button"
            onClick={() => onNavigate(i)}
            className={cn(
              "size-3 rounded-full transition-colors",
              ex.status === "done" && "bg-green-500",
              ex.status === "skipped" && "bg-red-400",
              ex.status === "pending" && i === currentIndex && "bg-primary ring-2 ring-primary/40",
              ex.status === "pending" && i !== currentIndex && "bg-muted-foreground/30",
            )}
            aria-label={`Exercise ${i + 1}: ${ex.name} (${ex.status})`}
          />
        ))}
      </div>
      <span className="text-xs text-muted-foreground tabular-nums whitespace-nowrap">
        {currentIndex + 1} / {exercises.length}
      </span>
    </div>
  );
}
