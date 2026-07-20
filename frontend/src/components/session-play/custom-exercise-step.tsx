"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { unlockAudio } from "@/lib/audio-unlock";
import { countdownTick, longBeep, transitionBeep } from "@/lib/beep";
import type { CustomSessionExercise } from "@/lib/types";

export type ExerciseCategory = "time_based" | "reps_based" | "timed_sets";

export function detectCategory(ex: CustomSessionExercise): ExerciseCategory {
  const hasWork = (ex.work_seconds ?? 0) > 0;
  const hasReps = (ex.reps ?? 0) > 0;
  const sets = ex.sets ?? 1;
  if (hasWork && sets > 1) return "timed_sets";
  if (hasWork && sets === 1) return "time_based";
  if (hasReps) return "reps_based";
  return "reps_based";
}



function vibrate(pattern: number[]) {
  try {
    (navigator as Navigator & { vibrate?: (p: number[]) => boolean }).vibrate?.(pattern);
  } catch {
    /* noop */
  }
}

interface CustomExerciseStepProps {
  exercise: CustomSessionExercise;
  exerciseName: string;
  currentSet: number; // 1-based
  onSetDone: () => void;
}

export function CustomExerciseStep({
  exercise,
  exerciseName,
  currentSet,
  onSetDone,
}: CustomExerciseStepProps) {
  const category = detectCategory(exercise);
  const totalSets = exercise.sets ?? 1;
  const workSec = exercise.work_seconds ?? 0;
  const loadKg = exercise.load_kg;
  const reps = exercise.reps ?? 0;

  const [timerRunning, setTimerRunning] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(workSec);
  const endRef = useRef<number>(0);
  const lastTickRef = useRef<number>(-1);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onSetDoneRef = useRef(onSetDone);
  useEffect(() => {
    onSetDoneRef.current = onSetDone;
  }, [onSetDone]);

  // Reset timer when exercise OR set changes (remount via key in parent clears
  // this naturally, but we also guard here for safety).
  useEffect(() => {
    setTimerRunning(false);
    setSecondsLeft(workSec);
    lastTickRef.current = -1;
    if (intervalRef.current) clearInterval(intervalRef.current);
  }, [exercise.exercise_id, currentSet, workSec]);

  // Wall-clock based countdown (iOS background safe).
  useEffect(() => {
    if (!timerRunning) return;
    endRef.current = Date.now() + secondsLeft * 1000;

    intervalRef.current = setInterval(() => {
      const remainingMs = endRef.current - Date.now();
      const remainingS = Math.max(0, Math.ceil(remainingMs / 1000));

      if (remainingS !== lastTickRef.current) {
        lastTickRef.current = remainingS;
        if (remainingS === 10 || remainingS === 3 || remainingS === 2 || remainingS === 1) {
          countdownTick();
        }
        if (remainingS === 0) {
          longBeep();
          vibrate([300, 100, 300]);
          setTimerRunning(false);
          setSecondsLeft(0);
          onSetDoneRef.current();
          return;
        }
      }

      setSecondsLeft(remainingS);
    }, 200);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
    // secondsLeft is intentionally not in deps — the endRef pins wall-clock
    // target at start; re-running on every tick would reset it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timerRunning]);

  // iOS visibility resync — recalc from wall clock when returning to foreground.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState !== "visible" || !timerRunning) return;
      const remainingMs = endRef.current - Date.now();
      setSecondsLeft(Math.max(0, Math.ceil(remainingMs / 1000)));
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [timerRunning]);

  const handleStartTimer = useCallback(async () => {
    await unlockAudio();
    lastTickRef.current = -1;
    setSecondsLeft(workSec);
    endRef.current = Date.now() + workSec * 1000;
    setTimerRunning(true);
    transitionBeep();
  }, [workSec]);

  const handleRepsDone = useCallback(async () => {
    await unlockAudio();
    transitionBeep();
    onSetDoneRef.current();
  }, []);

  // B281: never trap the user inside a countdown — long timed exercises (5-15
  // min drills) need a way out. Finishing early counts the set as done.
  const handleFinishEarly = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setTimerRunning(false);
    setSecondsLeft(0);
    onSetDoneRef.current();
  }, []);

  const isCountdown = timerRunning && secondsLeft <= 3 && secondsLeft > 0;

  return (
    <div className="space-y-6 py-6">
      <div className="text-center space-y-2">
        <Badge
          variant="outline"
          className="border-primary/40 bg-primary/10 text-primary text-[10px] uppercase tracking-wider"
        >
          Custom
        </Badge>
        <h2 className="text-2xl font-semibold">{exerciseName}</h2>
        <div className="text-sm text-muted-foreground">
          <span>
            Set {currentSet} of {totalSets}
          </span>
          {loadKg > 0 && <span> · @ {loadKg} kg</span>}
          {category === "reps_based" && reps > 0 && <span> · {reps} reps</span>}
          {(category === "time_based" || category === "timed_sets") && workSec > 0 && (
            <span> · {workSec}s</span>
          )}
        </div>
        {exercise.notes && (
          <p className="text-xs text-muted-foreground italic max-w-md mx-auto">{exercise.notes}</p>
        )}
      </div>

      {(category === "time_based" || category === "timed_sets") && (
        <div className="flex flex-col items-center gap-5">
          <div
            className={cn(
              "flex items-center justify-center w-60 h-60 rounded-full border-2",
              timerRunning
                ? "bg-orange-500/10 border-orange-500/40"
                : "bg-muted/30 border-muted",
            )}
          >
            <span
              className={cn(
                "text-7xl font-bold tabular-nums",
                isCountdown && "animate-pulse text-orange-500",
              )}
            >
              {secondsLeft}s
            </span>
          </div>

          {!timerRunning && (
            <Button size="lg" onClick={handleStartTimer} className="gap-2 min-w-[200px]">
              <Play className="size-5" />
              Start set
            </Button>
          )}
          {timerRunning && (
            <button
              type="button"
              onClick={handleFinishEarly}
              className="text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
            >
              Finish set early
            </button>
          )}
        </div>
      )}

      {category === "reps_based" && (
        <div className="flex flex-col items-center gap-5 py-4">
          <p className="text-sm text-muted-foreground">Do the reps at your pace, then tap Done.</p>
          <Button
            size="lg"
            onClick={handleRepsDone}
            className="gap-2 bg-green-600 hover:bg-green-700 text-white min-w-[200px]"
          >
            <CheckCircle2 className="size-5" />
            Done set
          </Button>
        </div>
      )}
    </div>
  );
}
