"use client";

import { useParams, useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { useCustomSession } from "@/lib/hooks/queries";
import { useState } from "react";
import { Pencil } from "lucide-react";

function formatPrescription(ex: { sets: number; reps: number | null; work_seconds: number | null; load_kg: number; rest_between_sets_seconds: number | null }): string {
  const parts: string[] = [];
  if (ex.reps != null) parts.push(`${ex.sets}\u00d7${ex.reps}`);
  else if (ex.work_seconds != null) parts.push(`${ex.sets}\u00d7${ex.work_seconds}s`);
  else parts.push(`${ex.sets} sets`);
  if (ex.load_kg > 0) parts.push(`${ex.load_kg}kg`);
  if (ex.rest_between_sets_seconds != null) parts.push(`Rest ${ex.rest_between_sets_seconds}s`);
  return parts.join(" \u00b7 ");
}

export default function SessionViewPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const { data: session, isLoading } = useCustomSession(id);
  const [checked, setChecked] = useState<Set<number>>(new Set());

  const toggleCheck = (index: number) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  if (isLoading) {
    return (
      <>
        <TopBar title="Session" backHref="/free-session" />
        <main className="px-4 py-8 text-center">
          <p className="text-sm text-muted-foreground">Loading...</p>
        </main>
      </>
    );
  }

  if (!session) {
    return (
      <>
        <TopBar title="Session" backHref="/free-session" />
        <main className="px-4 py-8 text-center">
          <p className="text-sm text-muted-foreground">Session not found</p>
        </main>
      </>
    );
  }

  const completedCount = checked.size;
  const totalCount = session.exercises.length;

  return (
    <>
      <TopBar title={session.name} backHref="/free-session" />
      <main className="px-4 py-4 space-y-4">
        {/* Progress */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {completedCount}/{totalCount} exercises
          </span>
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">
              Load {session.estimated_load_score} · ~{session.estimated_duration_minutes} min
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-300"
            style={{ width: `${totalCount > 0 ? (completedCount / totalCount) * 100 : 0}%` }}
          />
        </div>

        {/* Exercise checklist */}
        <div className="space-y-2">
          {session.exercises.map((ex, i) => {
            const isDone = checked.has(i);
            return (
              <button
                key={`${ex.exercise_id}-${i}`}
                type="button"
                className={`w-full flex items-start gap-3 rounded-lg border p-3 text-left transition-colors ${
                  isDone ? "bg-muted/50 border-muted" : ""
                }`}
                onClick={() => toggleCheck(i)}
              >
                <Checkbox checked={isDone} className="mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${isDone ? "line-through text-muted-foreground" : ""}`}>
                    {ex.exercise_id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {formatPrescription(ex)}
                  </p>
                  {ex.notes && (
                    <p className="text-xs text-muted-foreground mt-0.5 italic">{ex.notes}</p>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* Edit button */}
        <Button
          variant="outline"
          className="w-full"
          onClick={() => router.push(`/session-builder/${id}`)}
        >
          <Pencil className="h-4 w-4 mr-2" />
          Edit Session
        </Button>
      </main>
    </>
  );
}
