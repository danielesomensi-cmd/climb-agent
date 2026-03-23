"use client";

import { useState } from "react";
import { Flame } from "lucide-react";
import { Button } from "@/components/ui/button";

interface CircuitCompletionProps {
  completedExercises: number;
  targetExercises: number;
  workSeconds: number;
  restSeconds: number;
  durationSeconds: number;
  onSave: (feel?: string, notes?: string) => void;
  onRestart: () => void;
  onBack: () => void;
}

export function CircuitCompletion({
  completedExercises,
  targetExercises,
  workSeconds,
  restSeconds,
  durationSeconds,
  onSave,
  onRestart,
  onBack,
}: CircuitCompletionProps) {
  const [feel, setFeel] = useState<string | undefined>();
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const durationMin = Math.floor(durationSeconds / 60);
  const durationSec = durationSeconds % 60;

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(feel, notes || undefined);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 px-4 pb-8">
      {/* Header */}
      <div className="flex flex-col items-center gap-3 pt-4">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-green-500/20">
          <Flame className="size-10 text-green-500" />
        </div>
        <h2 className="text-2xl font-bold">Circuit Complete!</h2>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border bg-card p-4 text-center">
          <div className="text-2xl font-bold tabular-nums">
            {durationMin}:{String(durationSec).padStart(2, "0")}
          </div>
          <div className="text-xs text-muted-foreground mt-1">Duration</div>
        </div>
        <div className="rounded-xl border bg-card p-4 text-center">
          <div className="text-2xl font-bold tabular-nums">
            {completedExercises}/{targetExercises}
          </div>
          <div className="text-xs text-muted-foreground mt-1">Exercises</div>
        </div>
        <div className="rounded-xl border bg-card p-4 text-center">
          <div className="text-2xl font-bold tabular-nums">{workSeconds}s</div>
          <div className="text-xs text-muted-foreground mt-1">Work</div>
        </div>
        <div className="rounded-xl border bg-card p-4 text-center">
          <div className="text-2xl font-bold tabular-nums">{restSeconds}s</div>
          <div className="text-xs text-muted-foreground mt-1">Rest</div>
        </div>
      </div>

      {/* Feel selector */}
      <div>
        <h3 className="mb-2 text-center text-sm font-medium text-muted-foreground">How did it feel?</h3>
        <div className="flex gap-2">
          {([
            { key: "easy", label: "Easy", emoji: "\ud83d\ude34" },
            { key: "good", label: "Good", emoji: "\ud83d\udc4d" },
            { key: "hard", label: "Hard", emoji: "\ud83d\udcaa" },
          ] as const).map((f) => (
            <button
              key={f.key}
              onClick={() => setFeel(feel === f.key ? undefined : f.key)}
              className={`flex flex-1 flex-col items-center gap-1 rounded-xl border py-3 transition-all ${
                feel === f.key
                  ? "border-primary/50 bg-primary/10"
                  : "border-border hover:border-foreground/20"
              }`}
            >
              <span className="text-2xl">{f.emoji}</span>
              <span className="text-xs font-medium">{f.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Notes */}
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="How was the circuit? Any notes..."
        rows={2}
        className="w-full rounded-xl border bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/50"
      />

      {/* Actions */}
      <Button onClick={handleSave} disabled={saving} size="lg" className="w-full text-base font-semibold">
        {saving ? "Saving..." : "Save"}
      </Button>

      <button
        onClick={onRestart}
        className="flex h-12 w-full items-center justify-center gap-2 rounded-xl border border-border bg-card text-sm font-bold text-foreground transition-all active:scale-[0.98]"
      >
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <path d="M1 4v6h6" />
          <path d="M3.51 15a9 9 0 102.13-9.36L1 10" />
        </svg>
        Do Another
      </button>

      <button
        onClick={onBack}
        className="text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        Back to Free Session
      </button>
    </div>
  );
}
