"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Pause, Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { unlockAudio } from "@/lib/audio-unlock";
import { countdownTick, longBeep, transitionBeep } from "@/lib/beep";
import { completeFeedback, tapFeedback } from "@/lib/haptics";
import { displaySetNumber, sideForSet } from "@/lib/alt-sides";
import type { CustomSessionExercise } from "@/lib/types";
import { PHASE_TEXT } from "./player-phase-colors";

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



// A286 — l'haptic passa da `navigator.vibrate` (che su iOS non fa nulla) agli
// helper di src/lib/haptics, che hanno il fallback switch-toggle per Safari.

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
  // B324: alt_sides exercises are run once per side — the parent counts doubled
  // internal sets, we show the prescribed number plus the side badge.
  const altSides = exercise.alt_sides === true;
  const totalSets = exercise.sets ?? 1;
  const currentSide = sideForSet(currentSet, altSides);
  const displaySet = displaySetNumber(currentSet, altSides);
  const workSec = exercise.work_seconds ?? 0;
  const loadKg = exercise.load_kg;
  const reps = exercise.reps ?? 0;

  const [timerRunning, setTimerRunning] = useState(false);
  // A286 — B10: un set cronometrato si può mettere in pausa, come negli altri
  // player. `timerRunning` resta "il set è in corso", `paused` ne ferma il tick.
  const [paused, setPaused] = useState(false);
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
    setPaused(false);
    setSecondsLeft(workSec);
    lastTickRef.current = -1;
    if (intervalRef.current) clearInterval(intervalRef.current);
  }, [exercise.exercise_id, currentSet, workSec]);

  // Wall-clock based countdown (iOS background safe).
  useEffect(() => {
    if (!timerRunning || paused) return;
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
          completeFeedback();
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
    // target at start; re-running on every tick would reset it. A286: `paused`
    // invece sì, ed è proprio quello che ricalcola endRef alla ripresa.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timerRunning, paused]);

  // iOS visibility resync — recalc from wall clock when returning to foreground.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState !== "visible" || !timerRunning || paused) return;
      const remainingMs = endRef.current - Date.now();
      setSecondsLeft(Math.max(0, Math.ceil(remainingMs / 1000)));
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [timerRunning, paused]);

  const handleStartTimer = useCallback(async () => {
    await unlockAudio();
    lastTickRef.current = -1;
    setSecondsLeft(workSec);
    endRef.current = Date.now() + workSec * 1000;
    setPaused(false);
    setTimerRunning(true);
    transitionBeep();
  }, [workSec]);

  const handlePauseToggle = useCallback(() => {
    tapFeedback();
    setPaused((p) => !p);
  }, []);

  const handleRepsDone = useCallback(async () => {
    await unlockAudio();
    transitionBeep();
    completeFeedback();
    onSetDoneRef.current();
  }, []);

  // B281: never trap the user inside a countdown — long timed exercises (5-15
  // min drills) need a way out. Finishing early counts the set as done.
  const handleFinishEarly = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setTimerRunning(false);
    setPaused(false);
    setSecondsLeft(0);
    onSetDoneRef.current();
  }, []);

  const isCountdown = timerRunning && !paused && secondsLeft <= 3 && secondsLeft > 0;

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
        {currentSide && (
          <div className="flex justify-center pt-1">
            <div
              className={cn(
                "flex items-center justify-center rounded-lg px-5 py-1.5 text-lg font-bold tracking-widest",
                currentSide === "RIGHT"
                  ? "bg-orange-500/15 text-orange-400 border border-orange-500/30"
                  : "bg-sky-500/15 text-sky-400 border border-sky-500/30",
              )}
            >
              {currentSide}
            </div>
          </div>
        )}
        <div className="text-sm text-muted-foreground">
          <span>
            Set {displaySet} of {totalSets}
            {currentSide && " per side"}
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
              "flex flex-col items-center justify-center w-60 h-60 rounded-full border-2",
              timerRunning
                ? "bg-warning/10 border-warning/40"
                : "bg-muted/30 border-muted",
            )}
          >
            <span
              className={cn(
                "text-7xl font-bold tabular-nums",
                isCountdown && cn("animate-pulse", PHASE_TEXT.work),
              )}
            >
              {secondsLeft}s
            </span>
            {paused && (
              <span className="mt-1 text-sm font-bold uppercase tracking-widest text-muted-foreground">
                Paused
              </span>
            )}
          </div>

          {!timerRunning && (
            <Button size="lg" onClick={handleStartTimer} className="gap-2 min-w-[200px]">
              <Play className="size-5" />
              Start set
            </Button>
          )}
          {timerRunning && (
            <div className="flex flex-col items-center gap-3">
              {/* A286 — B10: pausa/ripresa, coerente con gli altri player */}
              <Button
                size="lg"
                variant="outline"
                onClick={handlePauseToggle}
                className="gap-2 min-w-[200px]"
              >
                {paused ? <Play className="size-5" /> : <Pause className="size-5" />}
                {paused ? "Resume" : "Pause"}
              </Button>
              <button
                type="button"
                onClick={handleFinishEarly}
                className="min-h-[44px] text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
              >
                Finish set early
              </button>
            </div>
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
