"use client";

import { cn } from "@/lib/utils";
import { tapFeedback } from "@/lib/haptics";
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
      {/* -my-2.5 compensa l'hit-area verticale da 44px: i pallini restano
          visivamente identici ma diventano toccabili con le mani magnesiate.
          B397 G5 — anche in larghezza: erano ~20 px (12 di pallino + 8 di
          padding), ora ogni bersaglio è almeno 32 px, contigui, e la riga va
          a capo solo oltre ~9 esercizi su un iPhone. */}
      <div className="flex items-center flex-1 flex-wrap -my-2.5">
        {exercises.map((ex, i) => (
          <button
            key={i}
            type="button"
            onClick={() => onNavigate(i)}
            onPointerDown={tapFeedback}
            className="group flex min-h-[44px] min-w-[32px] items-center justify-center"
            aria-label={`Exercise ${i + 1}: ${ex.name} (${ex.status})`}
          >
            <span
              className={cn(
                "block size-3 rounded-full transition-all group-active:scale-125 motion-reduce:group-active:scale-100",
                ex.status === "done" && "bg-success",
                ex.status === "skipped" && "bg-muted-foreground",
                ex.status === "pending" && i === currentIndex && "bg-primary ring-2 ring-primary/40",
                ex.status === "pending" && i !== currentIndex && "bg-muted-foreground/30",
              )}
            />
          </button>
        ))}
      </div>
      <span className="text-xs text-muted-foreground tabular-nums whitespace-nowrap">
        {currentIndex + 1} / {exercises.length}
      </span>
    </div>
  );
}
