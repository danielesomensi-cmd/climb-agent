"use client";

import { useParams, useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/top-bar";
import { Button } from "@/components/ui/button";
import { BuilderSkeleton } from "@/components/session-builder/builder-skeleton";
import { useStartCustomSession } from "@/components/session-builder/start-custom-session";
import { KeyConflictDialog } from "@/components/training/key-conflict-dialog";
import { useCustomSession, useBuilderExercises } from "@/lib/hooks/queries";
import { ApiError } from "@/lib/api";
import { useMemo } from "react";
import { Loader2, Pencil, Play } from "lucide-react";
import { toISODateLocal } from "@/lib/dates";

function formatPrescription(ex: { sets: number; reps: number | null; work_seconds: number | null; load_kg: number; rest_between_sets_seconds: number | null; alt_sides?: boolean }): string {
  const parts: string[] = [];
  const perSide = ex.alt_sides ? " per side" : "";   // B324
  if (ex.reps != null) parts.push(`${ex.sets}×${ex.reps}${perSide}`);
  else if (ex.work_seconds != null) parts.push(`${ex.sets}×${ex.work_seconds}s${perSide}`);
  else parts.push(`${ex.sets} sets${perSide}`);
  if (ex.load_kg > 0) parts.push(`${ex.load_kg}kg`);
  if (ex.rest_between_sets_seconds != null) parts.push(`Rest ${ex.rest_between_sets_seconds}s`);
  return parts.join(" · ");
}

/** A309: a missing session and a failed request are different problems. */
function describeLoadError(error: unknown): { title: string; retry: boolean } {
  if (error instanceof ApiError && error.status === 404) return { title: "Session not found", retry: false };
  const offline = typeof navigator !== "undefined" && navigator.onLine === false;
  if (offline || error instanceof TypeError) return { title: "You're offline — try again", retry: true };
  return { title: "Couldn't load this session", retry: true };
}

/**
 * A309 — read-only preview of a saved custom session. It used to be a
 * tap-to-check list with no timer and nothing logged; "Start session" now opens
 * the real player (wake lock, rest timer, feedback into working_loads).
 */
export default function SessionViewPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  // B364: the loads of today, like the player (anchored exercises follow the
  // official max + training load) — the stored kg would disagree with play.
  const today = useMemo(() => toISODateLocal(new Date()), []);
  const { data: session, isLoading, error, refetch } = useCustomSession(id, today);
  const { data: catalogData } = useBuilderExercises("", "");
  const { start, startingId, keyDialogProps } = useStartCustomSession();

  const catalogNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const ex of catalogData?.exercises ?? []) {
      map.set(ex.id, ex.name);
    }
    return map;
  }, [catalogData]);

  if (isLoading) {
    return (
      <>
        <TopBar title="Session" backHref="/free-session" />
        <main className="px-4 py-4">
          <BuilderSkeleton withInput={false} />
        </main>
      </>
    );
  }

  if (!session) {
    const { title, retry } = describeLoadError(error);
    return (
      <>
        <TopBar title="Session" backHref="/free-session" />
        <main className="px-4 py-8 text-center space-y-3">
          <p className="text-sm text-muted-foreground">{title}</p>
          {retry && (
            <Button variant="outline" className="h-11" onClick={() => void refetch()}>
              Retry
            </Button>
          )}
        </main>
      </>
    );
  }

  const total = session.exercises.length;

  return (
    <>
      <TopBar title={session.name} backHref="/free-session" />
      <main className="px-4 pt-4 space-y-4">
        {/* Summary */}
        <p className="text-sm text-muted-foreground tabular-nums">
          {total} exercise{total !== 1 ? "s" : ""} · Load {session.estimated_load_score} · ~{session.estimated_duration_minutes} min
        </p>

        {/* Exercise list (read-only) */}
        <ol className="space-y-2">
          {session.exercises.map((ex, i) => (
            <li
              key={`${ex.exercise_id}-${i}`}
              className="flex items-start gap-3 rounded-lg border border-border bg-card p-3"
            >
              <span className="w-5 shrink-0 pt-0.5 text-xs tabular-nums text-muted-foreground">{i + 1}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">
                  {catalogNameMap.get(ex.exercise_id) ?? ex.exercise_id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatPrescription(ex)}
                </p>
                {ex.notes && (
                  <p className="text-xs text-muted-foreground mt-0.5 italic">{ex.notes}</p>
                )}
              </div>
            </li>
          ))}
        </ol>

        {/* Sticky actions, above the bottom nav */}
        <div className="sticky bottom-[var(--nav-h)] -mx-4 flex gap-2 border-t border-border bg-background/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80">
          <Button
            variant="outline"
            className="h-12"
            onClick={() => router.push(`/session-builder/${id}`)}
          >
            <Pencil />
            Edit
          </Button>
          <Button
            className="h-12 flex-1"
            disabled={startingId !== null || total === 0}
            onClick={() => void start(id)}
          >
            {startingId ? <Loader2 className="animate-spin" /> : <Play />}
            Start session
          </Button>
        </div>
      </main>
      <KeyConflictDialog {...keyDialogProps} />
    </>
  );
}
