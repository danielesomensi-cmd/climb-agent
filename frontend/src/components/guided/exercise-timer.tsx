"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Play, Pause, RotateCcw, CheckCircle2, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { getAudioContext, unlockAudio } from "@/lib/audio-unlock";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ExerciseTimerProps {
  workSeconds: number;              // 0 for manual/rep-based exercises
  restBetweenRepsSeconds: number;   // rest between reps within a set (0 = no rep rest)
  restBetweenSetsSeconds: number;   // rest between sets
  sets: number;
  reps: number;                     // reps per set (timer loops reps only when workSeconds > 0)
  initialSet?: number;
  onSetChange?: (completedSets: number) => void;
}

type Phase = "idle" | "get_ready" | "work" | "rep_rest" | "set_rest" | "complete";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GET_READY_SECONDS = 5;
const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

// ---------------------------------------------------------------------------
// Audio — uses shared AudioContext from audio-unlock.ts.
// unlockAudio() is called once on the guided-session page (touchstart +
// Start button), so the context is already running by the time beep() fires.
// ---------------------------------------------------------------------------

async function beep(freq: number, duration: number, volume: number) {
  try {
    const ctx = getAudioContext();
    if (ctx.state !== "running") {
      await ctx.resume();
    }
    if (ctx.state !== "running") return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  } catch { /* silent */ }
}

/** Short high-pitched tick for countdown 3-2-1 */
function countdownTick() { beep(660, 0.08, 0.25); }

/** Longer beep on phase transition */
function transitionBeep() { beep(880, 0.2, 0.4); }

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatSeconds(s: number): string {
  if (s >= 60) {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${String(sec).padStart(2, "0")}`;
  }
  return String(s);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ExerciseTimer({
  workSeconds,
  restBetweenRepsSeconds,
  restBetweenSetsSeconds,
  sets,
  reps,
  initialSet = 1,
  onSetChange,
}: ExerciseTimerProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [currentSet, setCurrentSet] = useState(initialSet);
  const [currentRep, setCurrentRep] = useState(1);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [paused, setPaused] = useState(false);
  const [transitionId, setTransitionId] = useState(0);
  const [flash, setFlash] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onSetChangeRef = useRef(onSetChange);
  useEffect(() => { onSetChangeRef.current = onSetChange; }, [onSetChange]);

  // Refs for countdown beep effect (avoid re-triggering on phase/paused change)
  const phaseRef = useRef(phase);
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  const pausedRef = useRef(paused);
  useEffect(() => { pausedRef.current = paused; }, [paused]);

  const isManual = workSeconds === 0;
  const hasRepLoop = !isManual && reps > 1;

  // Total duration for current phase (progress arc denominator)
  const totalForPhase = (() => {
    switch (phase) {
      case "get_ready": return GET_READY_SECONDS;
      case "work": return workSeconds;
      case "rep_rest": return restBetweenRepsSeconds;
      case "set_rest": return restBetweenSetsSeconds;
      default: return 0;
    }
  })();

  // --- Audio effects ---

  // Transition beep + visual flash
  useEffect(() => {
    if (transitionId > 0) {
      transitionBeep();
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 300);
      return () => clearTimeout(t);
    }
  }, [transitionId]);

  // Countdown ticks at 3 / 2 / 1 seconds
  useEffect(() => {
    if (secondsLeft >= 1 && secondsLeft <= 3) {
      const p = phaseRef.current;
      if (!pausedRef.current && p !== "idle" && p !== "complete") {
        // No countdown ticks during manual work (no timer running)
        if (!(p === "work" && isManual)) {
          countdownTick();
        }
      }
    }
  }, [secondsLeft, isManual]);

  // --- Timer management ---

  const clearTimer = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => clearTimer, [clearTimer]);

  // Main tick — recreated when relevant state changes
  useEffect(() => {
    clearTimer();

    if (phase === "idle" || phase === "complete" || paused) return;
    if (phase === "work" && isManual) return; // manual work has no countdown

    intervalRef.current = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          // --- Phase transition ---

          if (phase === "get_ready") {
            setPhase("work");
            setTransitionId((id) => id + 1);
            if (isManual) return 0;
            return workSeconds;
          }

          if (phase === "work") {
            // More reps in this set?
            if (hasRepLoop && currentRep < reps) {
              if (restBetweenRepsSeconds > 0) {
                setPhase("rep_rest");
                setTransitionId((id) => id + 1);
                return restBetweenRepsSeconds;
              }
              // No rep rest — next rep immediately
              setCurrentRep((r) => r + 1);
              setTransitionId((id) => id + 1);
              return workSeconds;
            }
            // End of set
            onSetChangeRef.current?.(currentSet);
            if (currentSet >= sets) {
              setPhase("complete");
              setTransitionId((id) => id + 1);
              return 0;
            }
            // More sets — go to set rest
            if (restBetweenSetsSeconds > 0) {
              setPhase("set_rest");
              setTransitionId((id) => id + 1);
              return restBetweenSetsSeconds;
            }
            // No set rest — next set with get_ready
            setCurrentSet((s) => s + 1);
            setCurrentRep(1);
            setPhase("get_ready");
            setTransitionId((id) => id + 1);
            return GET_READY_SECONDS;
          }

          if (phase === "rep_rest") {
            setCurrentRep((r) => r + 1);
            setPhase("work");
            setTransitionId((id) => id + 1);
            return workSeconds;
          }

          if (phase === "set_rest") {
            setCurrentSet((s) => s + 1);
            setCurrentRep(1);
            if (!isManual) {
              setPhase("get_ready");
              setTransitionId((id) => id + 1);
              return GET_READY_SECONDS;
            }
            setPhase("work");
            setTransitionId((id) => id + 1);
            return 0;
          }

          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return clearTimer;
  }, [phase, paused, currentSet, currentRep, sets, reps, workSeconds, restBetweenRepsSeconds, restBetweenSetsSeconds, isManual, hasRepLoop, clearTimer]);

  // --- Handlers ---

  async function handleStart() {
    await unlockAudio(); // Unlock audio on iOS (must be inside user gesture)
    if (isManual) {
      setPhase("work");
      setSecondsLeft(0);
    } else {
      setPhase("get_ready");
      setSecondsLeft(GET_READY_SECONDS);
    }
    setPaused(false);
    setTransitionId((id) => id + 1);
  }

  async function handleDoneSet() {
    await unlockAudio(); // Resume audio if suspended
    onSetChangeRef.current?.(currentSet);
    if (currentSet >= sets) {
      setPhase("complete");
    } else if (restBetweenSetsSeconds > 0) {
      setPhase("set_rest");
      setSecondsLeft(restBetweenSetsSeconds);
    } else {
      setCurrentSet((s) => s + 1);
      // Phase stays "work" (manual), no countdown
    }
    setTransitionId((id) => id + 1);
  }

  function handleReset() {
    clearTimer();
    setPhase("idle");
    setCurrentSet(1);
    setCurrentRep(1);
    setSecondsLeft(0);
    setPaused(false);
  }

  function handleCircleTap() {
    if (phase === "work" && isManual) {
      handleDoneSet();
      return;
    }
    if (phase !== "idle" && phase !== "complete") {
      setPaused((p) => !p);
    }
  }

  /** Skip to the next phase in the timer sequence. */
  function handlePhaseForward() {
    if (phase === "idle" || phase === "complete") return;
    const wasRunning = !paused;

    if (phase === "get_ready") {
      setPhase("work");
      setSecondsLeft(isManual ? 0 : workSeconds);
    } else if (phase === "work") {
      if (hasRepLoop && currentRep < reps) {
        if (restBetweenRepsSeconds > 0) {
          setPhase("rep_rest");
          setSecondsLeft(restBetweenRepsSeconds);
        } else {
          setCurrentRep((r) => r + 1);
          setSecondsLeft(workSeconds);
        }
      } else {
        // End of set
        onSetChangeRef.current?.(currentSet);
        if (currentSet >= sets) {
          setPhase("complete");
          setSecondsLeft(0);
        } else if (restBetweenSetsSeconds > 0) {
          setPhase("set_rest");
          setSecondsLeft(restBetweenSetsSeconds);
        } else {
          setCurrentSet((s) => s + 1);
          setCurrentRep(1);
          setPhase(isManual ? "work" : "get_ready");
          setSecondsLeft(isManual ? 0 : GET_READY_SECONDS);
        }
      }
    } else if (phase === "rep_rest") {
      setCurrentRep((r) => r + 1);
      setPhase("work");
      setSecondsLeft(isManual ? 0 : workSeconds);
    } else if (phase === "set_rest") {
      setCurrentSet((s) => s + 1);
      setCurrentRep(1);
      setPhase(isManual ? "work" : "get_ready");
      setSecondsLeft(isManual ? 0 : GET_READY_SECONDS);
    }

    setTransitionId((id) => id + 1);
    if (!wasRunning) setPaused(true);
  }

  /** Go back: restart current phase if >2s elapsed, else go to previous phase. */
  function handlePhaseBack() {
    if (phase === "idle" || phase === "complete") return;
    const wasRunning = !paused;
    const elapsed = totalForPhase - secondsLeft;

    if (elapsed > 2) {
      // Restart current phase from beginning
      setSecondsLeft(totalForPhase);
      if (!wasRunning) setPaused(true);
      return;
    }

    // Go to previous phase
    if (phase === "get_ready") {
      // Can't go further back — just restart
      setSecondsLeft(GET_READY_SECONDS);
    } else if (phase === "work") {
      if (currentRep > 1 && restBetweenRepsSeconds > 0) {
        setCurrentRep((r) => r - 1);
        setPhase("rep_rest");
        setSecondsLeft(restBetweenRepsSeconds);
      } else {
        setPhase(isManual ? "work" : "get_ready");
        setSecondsLeft(isManual ? 0 : GET_READY_SECONDS);
      }
    } else if (phase === "rep_rest") {
      setPhase("work");
      setSecondsLeft(isManual ? 0 : workSeconds);
    } else if (phase === "set_rest") {
      // Go back to work phase (last rep of current set)
      setPhase("work");
      setSecondsLeft(isManual ? 0 : workSeconds);
    }

    setTransitionId((id) => id + 1);
    if (!wasRunning) setPaused(true);
  }

  // --- SVG progress ---

  const progress =
    phase === "idle" || phase === "complete" || totalForPhase === 0
      ? 0
      : 1 - secondsLeft / totalForPhase;
  const dashOffset = progress * CIRCUMFERENCE;

  const strokeColor = (() => {
    switch (phase) {
      case "get_ready": return "stroke-sky-500";
      case "work": return "stroke-orange-500";
      case "rep_rest": return "stroke-teal-400";
      case "set_rest": return "stroke-emerald-500";
      default: return "stroke-orange-500";
    }
  })();

  const isCountdown =
    secondsLeft <= 3 && secondsLeft > 0 &&
    phase !== "idle" && phase !== "complete" &&
    !(phase === "work" && isManual);

  const isActive = phase !== "idle" && phase !== "complete";

  // --- Render ---

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Timer row: ‹ arrow | circle | › arrow */}
      <div className="flex items-center gap-2">
        {/* ‹ Back phase arrow — always visible when active */}
        <button
          onClick={handlePhaseBack}
          className={cn(
            "flex items-center justify-center w-12 h-12 rounded-full border transition-colors",
            isActive
              ? "border-muted-foreground/30 text-muted-foreground hover:text-foreground hover:border-foreground/50 active:scale-95"
              : "border-transparent text-transparent cursor-default"
          )}
          disabled={!isActive}
          aria-label="Previous phase"
        >
          <ChevronLeft className="size-6" />
        </button>

        {/* SVG circle */}
        <div
          className={cn(
            "relative w-40 h-40 cursor-pointer select-none transition-transform",
            isActive && "active:scale-95",
            flash && "ring-2 ring-primary/50 rounded-full"
          )}
          onClick={handleCircleTap}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === " " || e.key === "Enter") handleCircleTap();
          }}
          aria-label={
            phase === "work" && isManual
              ? "Complete set"
              : paused ? "Resume timer" : "Pause timer"
          }
        >
          <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
            {/* Background track */}
            <circle
              cx="60" cy="60" r={RADIUS}
              fill="none" strokeWidth={8}
              className="stroke-muted"
            />
            {/* Progress arc (hidden during manual work and idle/complete) */}
            {isActive && !(phase === "work" && isManual) && (
              <circle
                cx="60" cy="60" r={RADIUS}
                fill="none" strokeWidth={8}
                strokeLinecap="round"
                strokeDasharray={CIRCUMFERENCE}
                strokeDashoffset={dashOffset}
                className={cn(
                  strokeColor,
                  "transition-[stroke-dashoffset] duration-1000 ease-linear"
                )}
              />
            )}
          </svg>

          {/* Center text */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {phase === "idle" && (
              <button
                onClick={(e) => { e.stopPropagation(); handleStart(); }}
                className="flex flex-col items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
              >
                <Play className="size-8" />
                <span className="text-xs font-medium">Start</span>
              </button>
            )}

            {phase === "get_ready" && (
              <>
                <span className={cn("text-3xl font-bold tabular-nums", isCountdown && "animate-pulse")}>
                  {secondsLeft}
                </span>
                <span className="text-xs font-semibold uppercase tracking-wider mt-0.5 text-sky-500">
                  Get Ready
                </span>
              </>
            )}

            {phase === "work" && !isManual && (
              <>
                <span className={cn("text-3xl font-bold tabular-nums", isCountdown && "animate-pulse")}>
                  {formatSeconds(secondsLeft)}
                </span>
                <span className="text-xs font-semibold uppercase tracking-wider mt-0.5 text-orange-500">
                  Work
                </span>
                {paused && <Pause className="size-5 text-muted-foreground mt-1" />}
              </>
            )}

            {phase === "work" && isManual && (
              <>
                <span className="text-2xl font-bold">Set {currentSet}</span>
                <span className="text-xs text-muted-foreground mt-1">
                  {reps > 1 ? `Do ${reps} reps` : "Do your set"}
                </span>
                <span className="text-[10px] text-muted-foreground/60 mt-0.5">
                  Tap when done
                </span>
              </>
            )}

            {phase === "rep_rest" && (
              <>
                <span className={cn("text-3xl font-bold tabular-nums", isCountdown && "animate-pulse")}>
                  {formatSeconds(secondsLeft)}
                </span>
                <span className="text-xs font-semibold uppercase tracking-wider mt-0.5 text-teal-400">
                  Rep Rest
                </span>
                {paused && <Pause className="size-5 text-muted-foreground mt-1" />}
              </>
            )}

            {phase === "set_rest" && (
              <>
                <span className={cn("text-3xl font-bold tabular-nums", isCountdown && "animate-pulse")}>
                  {formatSeconds(secondsLeft)}
                </span>
                <span className="text-xs font-semibold uppercase tracking-wider mt-0.5 text-emerald-500">
                  Rest
                </span>
                {paused && <Pause className="size-5 text-muted-foreground mt-1" />}
              </>
            )}

            {phase === "complete" && (
              <div className="flex flex-col items-center gap-1 text-green-600">
                <span className="text-sm font-semibold">Done!</span>
              </div>
            )}
          </div>
        </div>

        {/* › Forward phase arrow — always visible when active */}
        <button
          onClick={handlePhaseForward}
          className={cn(
            "flex items-center justify-center w-12 h-12 rounded-full border transition-colors",
            isActive
              ? "border-muted-foreground/30 text-muted-foreground hover:text-foreground hover:border-foreground/50 active:scale-95"
              : "border-transparent text-transparent cursor-default"
          )}
          disabled={!isActive}
          aria-label="Next phase"
        >
          <ChevronRight className="size-6" />
        </button>
      </div>

      {/* Set/rep counter + controls */}
      <div className="flex flex-col items-center gap-2">
        {isActive && (
          <span className="text-xs text-muted-foreground tabular-nums">
            Set {currentSet} / {sets}
            {hasRepLoop && (
              <> &mdash; Rep {currentRep} / {reps}</>
            )}
          </span>
        )}
        <div className="flex items-center gap-3">
          {phase === "work" && isManual && (
            <button
              onClick={(e) => { e.stopPropagation(); handleDoneSet(); }}
              className="inline-flex items-center gap-1.5 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors"
            >
              <CheckCircle2 className="size-4" />
              Done set
            </button>
          )}
          {phase !== "idle" && (
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-1.5 rounded-md border border-muted-foreground/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:border-foreground/50 transition-colors"
              aria-label="Reset timer"
            >
              <RotateCcw className="size-4" />
              Reset
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
