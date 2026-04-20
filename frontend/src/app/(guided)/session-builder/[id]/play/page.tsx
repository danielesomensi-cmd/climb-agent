"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trophy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCustomSession, useBuilderExercises } from "@/lib/hooks/queries";
import { useWakeLock } from "@/lib/hooks/use-wake-lock";
import { useSubscription } from "@/lib/hooks/use-subscription";
import { queryKeys } from "@/lib/query-keys";
import { applyEvents } from "@/lib/api";
import type { WeekPlan, CustomSessionExercise } from "@/lib/types";
import { CustomExerciseStep } from "@/components/session-play/custom-exercise-step";
import { CustomRestTimer } from "@/components/session-play/custom-rest-timer";
import { unlockAudio } from "@/lib/audio-unlock";

type Stage = "idle" | "exercise_active" | "resting" | "completed";

type CachedWeek = { week_num: number; phase_id?: string | null; week_plan: WeekPlan };

function formatExerciseName(id: string, catalogMap: Map<string, string>): string {
  return (
    catalogMap.get(id) ??
    id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

function exercisePrescriptionSummary(ex: CustomSessionExercise): string {
  const parts: string[] = [];
  const sets = ex.sets ?? 1;
  if (ex.reps != null && ex.reps > 0) parts.push(`${sets}\u00d7${ex.reps}`);
  else if (ex.work_seconds != null && ex.work_seconds > 0) parts.push(`${sets}\u00d7${ex.work_seconds}s`);
  else parts.push(`${sets} sets`);
  if (ex.load_kg > 0) parts.push(`${ex.load_kg}kg`);
  if (ex.rest_between_sets_seconds != null && ex.rest_between_sets_seconds > 0) {
    parts.push(`rest ${ex.rest_between_sets_seconds}s`);
  }
  return parts.join(" \u00b7 ");
}

/**
 * Scan cached weeks for the one containing this custom session on the given
 * date. We don't thread `weekNum` through session-card — the cache already has
 * whatever week the user was looking at when they tapped Start.
 */
function findWeekForCustomSession(
  qc: ReturnType<typeof useQueryClient>,
  customSessionId: string,
  date: string,
): { weekNum: number; weekPlan: WeekPlan } | null {
  const sessionRef = `custom_${customSessionId}`;
  for (let w = 0; w < 14; w++) {
    const cached = qc.getQueryData<CachedWeek>(queryKeys.week(w));
    const weekPlan = cached?.week_plan;
    if (!weekPlan) continue;
    for (const weekObj of weekPlan.weeks ?? []) {
      for (const day of weekObj.days ?? []) {
        if (day.date !== date) continue;
        for (const s of day.sessions ?? []) {
          if (s.session_id === sessionRef || s.custom_session_id === customSessionId) {
            return { weekNum: w, weekPlan };
          }
        }
      }
    }
  }
  return null;
}

export default function SessionPlayPage() {
  const params = useParams();
  const router = useRouter();
  const search = useSearchParams();
  const qc = useQueryClient();
  const id = params.id as string;
  const date = search.get("date") ?? "";

  const { canInteract, loading: subLoading } = useSubscription();
  useEffect(() => {
    if (!subLoading && !canInteract) router.replace("/subscribe");
  }, [canInteract, subLoading, router]);

  const { data: session, isLoading, error: fetchError } = useCustomSession(id);
  const { data: catalogData } = useBuilderExercises("", "");

  const catalogNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const ex of catalogData?.exercises ?? []) {
      map.set(ex.id, ex.name);
    }
    return map;
  }, [catalogData]);

  const [stage, setStage] = useState<Stage>("idle");
  const [currentExerciseIndex, setCurrentExerciseIndex] = useState(0);
  const [currentSet, setCurrentSet] = useState(1);
  const startedAtRef = useRef<number>(0);
  const [durationSec, setDurationSec] = useState(0);
  const [setsCompleted, setSetsCompleted] = useState(0);
  useEffect(() => {
    if (startedAtRef.current === 0) startedAtRef.current = Date.now();
  }, []);

  const completeSession = useCallback(() => {
    if (startedAtRef.current > 0) {
      setDurationSec(Math.floor((Date.now() - startedAtRef.current) / 1000));
    }
    setStage("completed");
  }, []);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmBack, setConfirmBack] = useState(false);

  // Keep screen awake during active playback (not idle, not completed).
  useWakeLock(stage === "exercise_active" || stage === "resting");

  // Audio unlock on first touch anywhere on page (iOS gesture gate).
  useEffect(() => {
    const onTouch = () => {
      unlockAudio();
      window.removeEventListener("touchstart", onTouch);
    };
    window.addEventListener("touchstart", onTouch, { once: true });
    return () => window.removeEventListener("touchstart", onTouch);
  }, []);

  const exercises = session?.exercises ?? [];
  const currentExercise: CustomSessionExercise | undefined = exercises[currentExerciseIndex];
  const nextExercise: CustomSessionExercise | undefined = exercises[currentExerciseIndex + 1];

  const backDestination = date ? `/today?date=${date}` : "/today";

  const handleBack = useCallback(() => {
    if (stage === "idle" || stage === "completed") {
      router.push(backDestination);
      return;
    }
    if (confirmBack) {
      router.push(backDestination);
    } else {
      setConfirmBack(true);
      setTimeout(() => setConfirmBack(false), 3000);
    }
  }, [router, stage, confirmBack, backDestination]);

  const handleBeginSession = useCallback(async () => {
    await unlockAudio();
    setStage("exercise_active");
  }, []);

  /** Called when the current set finishes (timer hit zero OR user tapped Done for reps). */
  const handleSetDone = useCallback(() => {
    if (!currentExercise) return;
    setSetsCompleted((n) => n + 1);

    const totalSets = currentExercise.sets ?? 1;
    const restSec = currentExercise.rest_between_sets_seconds ?? 0;
    const hasMoreSetsInExercise = currentSet < totalSets;
    const hasNextExercise = currentExerciseIndex < exercises.length - 1;

    if (hasMoreSetsInExercise) {
      if (restSec > 0) {
        setStage("resting");
      } else {
        setCurrentSet((s) => s + 1);
        // Stay in exercise_active — next set starts fresh via key prop
      }
      return;
    }

    // End of exercise
    if (hasNextExercise) {
      if (restSec > 0) {
        setStage("resting");
      } else {
        setCurrentExerciseIndex((i) => i + 1);
        setCurrentSet(1);
      }
      return;
    }

    // End of session
    completeSession();
  }, [currentExercise, currentSet, currentExerciseIndex, exercises.length, completeSession]);

  /** Called when rest timer reaches target + user taps Start next, or skips early. */
  const handleRestDone = useCallback(() => {
    if (!currentExercise) return;
    const totalSets = currentExercise.sets ?? 1;
    if (currentSet < totalSets) {
      setCurrentSet((s) => s + 1);
      setStage("exercise_active");
      return;
    }
    if (currentExerciseIndex < exercises.length - 1) {
      setCurrentExerciseIndex((i) => i + 1);
      setCurrentSet(1);
      setStage("exercise_active");
      return;
    }
    completeSession();
  }, [currentExercise, currentSet, currentExerciseIndex, exercises.length, completeSession]);

  const handleFinish = useCallback(async () => {
    if (!session) return;
    if (!date) {
      setError("Session date is missing — return to Today and retry.");
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      const found = findWeekForCustomSession(qc, id, date);
      if (!found) {
        setError("Could not locate this session in the cached week plan. Return to Today and try again.");
        setSubmitting(false);
        return;
      }

      const result = await applyEvents({
        events: [
          {
            event_type: "mark_done",
            date,
            session_ref: `custom_${id}`,
          },
        ],
        week_plan: found.weekPlan,
      });

      qc.setQueryData<CachedWeek>(queryKeys.week(found.weekNum), (old) =>
        old ? { ...old, week_plan: result.week_plan } : { week_num: found.weekNum, week_plan: result.week_plan },
      );
      qc.invalidateQueries({ queryKey: queryKeys.state });

      router.push(backDestination);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to mark the session done.");
      setSubmitting(false);
    }
  }, [session, date, id, qc, router, backDestination]);

  // --- Render ---

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!session || fetchError) {
    return (
      <div className="mx-auto max-w-2xl p-4 space-y-3">
        <p className="text-sm text-muted-foreground">Session not found.</p>
        <Button variant="outline" onClick={() => router.push(backDestination)}>
          Back to Today
        </Button>
      </div>
    );
  }

  if (exercises.length === 0) {
    return (
      <div className="mx-auto max-w-2xl p-4 space-y-3">
        <p className="text-sm text-muted-foreground">This session has no exercises.</p>
        <Button variant="outline" onClick={() => router.push(backDestination)}>
          Back to Today
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b px-4 py-3 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={handleBack}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-4" />
            {confirmBack ? "Tap again to leave" : "Back"}
          </button>
          <span className="text-[10px] font-medium px-2 py-0.5 rounded border border-primary/40 bg-primary/10 text-primary uppercase tracking-wider">
            Custom
          </span>
        </div>
        <p className="text-base font-semibold truncate">{session.name}</p>
        {stage !== "completed" && currentExercise && (
          <p className="text-xs text-muted-foreground">
            Exercise {currentExerciseIndex + 1} of {exercises.length}
            {stage === "exercise_active" && (
              <>
                {" "}
                · Set {currentSet} of {currentExercise.sets ?? 1}
              </>
            )}
            {stage === "resting" && <> · Resting</>}
          </p>
        )}
      </header>

      <main className="flex-1 px-4 pb-8">
        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-center text-sm text-destructive mt-3">
            {error}
          </div>
        )}

        {stage === "idle" && currentExercise && (
          <div className="py-12 text-center space-y-6">
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">
                First exercise
              </p>
              <h2 className="text-2xl font-semibold">
                {formatExerciseName(currentExercise.exercise_id, catalogNameMap)}
              </h2>
              <p className="text-sm text-muted-foreground">
                {exercisePrescriptionSummary(currentExercise)}
              </p>
              {currentExercise.notes && (
                <p className="text-xs text-muted-foreground italic max-w-md mx-auto pt-1">
                  {currentExercise.notes}
                </p>
              )}
            </div>
            <Button size="lg" onClick={handleBeginSession} className="min-w-[200px]">
              Start first exercise
            </Button>
            <p className="text-[11px] text-muted-foreground">
              {exercises.length} exercises · ~{session.estimated_duration_minutes} min
            </p>
          </div>
        )}

        {stage === "exercise_active" && currentExercise && (
          <CustomExerciseStep
            key={`${currentExerciseIndex}-${currentSet}`}
            exercise={currentExercise}
            exerciseName={formatExerciseName(currentExercise.exercise_id, catalogNameMap)}
            currentSet={currentSet}
            onSetDone={handleSetDone}
          />
        )}

        {stage === "resting" &&
          currentExercise &&
          (() => {
            const totalSets = currentExercise.sets ?? 1;
            const hasMoreSetsInExercise = currentSet < totalSets;
            const nextLabel = hasMoreSetsInExercise
              ? `Set ${currentSet + 1} of ${totalSets} · ${formatExerciseName(currentExercise.exercise_id, catalogNameMap)}`
              : nextExercise
                ? formatExerciseName(nextExercise.exercise_id, catalogNameMap)
                : "Finish";
            return (
              <CustomRestTimer
                targetSeconds={currentExercise.rest_between_sets_seconds ?? 0}
                nextLabel={nextLabel}
                onComplete={handleRestDone}
                onSkip={handleRestDone}
              />
            );
          })()}

        {stage === "completed" && (
          <div className="py-12 text-center space-y-6">
            <div className="flex items-center justify-center">
              <div className="flex items-center justify-center w-20 h-20 rounded-full bg-green-500/15 border border-green-500/30">
                <Trophy className="size-10 text-green-500" />
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-xs uppercase tracking-wider text-emerald-500">Session complete</p>
              <h2 className="text-2xl font-semibold">{session.name}</h2>
            </div>
            <div className="rounded-lg border bg-muted/30 p-4 space-y-2 max-w-sm mx-auto text-left">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Duration</span>
                <span className="font-medium tabular-nums">
                  {Math.floor(durationSec / 60)}m {durationSec % 60}s
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Sets completed</span>
                <span className="font-medium tabular-nums">{setsCompleted}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Load score</span>
                <span className="font-medium tabular-nums">{session.estimated_load_score}</span>
              </div>
            </div>
            <div className="flex gap-3 justify-center pt-2">
              <Button variant="outline" onClick={handleBack} disabled={submitting}>
                Back
              </Button>
              <Button
                onClick={handleFinish}
                disabled={submitting}
                className="bg-green-600 hover:bg-green-700 text-white min-w-[140px]"
              >
                {submitting ? "Saving\u2026" : "Done"}
              </Button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
