"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Play, Pause, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";

interface ExerciseTimerProps {
  workSeconds: number;
  restSeconds: number;
  sets: number;
}

type Phase = "idle" | "work" | "rest" | "complete";

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function formatSeconds(s: number): string {
  if (s >= 60) {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${String(sec).padStart(2, "0")}`;
  }
  return String(s);
}

function playBeep() {
  try {
    const Ctx =
      typeof window !== "undefined"
        ? window.AudioContext ??
          (window as unknown as { webkitAudioContext?: typeof AudioContext })
            .webkitAudioContext
        : undefined;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 440;
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.15);
    // Clean up after playback
    osc.onended = () => ctx.close();
  } catch {
    // Silent fail
  }
}

function vibrate() {
  try {
    navigator?.vibrate?.(200);
  } catch {
    // Silent fail
  }
}

export function ExerciseTimer({
  workSeconds,
  restSeconds,
  sets,
}: ExerciseTimerProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [currentSet, setCurrentSet] = useState(1);
  const [secondsLeft, setSecondsLeft] = useState(workSeconds);
  const [paused, setPaused] = useState(false);
  const [transitionId, setTransitionId] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const totalForPhase = phase === "work" ? workSeconds : restSeconds;

  // Beep + vibrate on phase transitions (not on initial mount)
  useEffect(() => {
    if (transitionId > 0) {
      playBeep();
      vibrate();
    }
  }, [transitionId]);

  const clearTimer = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return clearTimer;
  }, [clearTimer]);

  // Main timer tick
  useEffect(() => {
    clearTimer();

    if (phase === "idle" || phase === "complete" || paused) return;

    intervalRef.current = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          // Transition happens here
          if (phase === "work") {
            if (currentSet >= sets) {
              // Last set done
              setPhase("complete");
              setTransitionId((id) => id + 1);
              return 0;
            }
            if (restSeconds > 0) {
              setPhase("rest");
              setSecondsLeft(restSeconds);
              setTransitionId((id) => id + 1);
              return restSeconds;
            }
            // No rest — go straight to next work
            setCurrentSet((s) => s + 1);
            setSecondsLeft(workSeconds);
            setTransitionId((id) => id + 1);
            return workSeconds;
          }
          if (phase === "rest") {
            setCurrentSet((s) => s + 1);
            setPhase("work");
            setSecondsLeft(workSeconds);
            setTransitionId((id) => id + 1);
            return workSeconds;
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return clearTimer;
  }, [phase, paused, currentSet, sets, workSeconds, restSeconds, clearTimer]);

  function handleStart() {
    setPhase("work");
    setCurrentSet(1);
    setSecondsLeft(workSeconds);
    setPaused(false);
    setTransitionId((id) => id + 1);
  }

  function handleReset() {
    clearTimer();
    setPhase("idle");
    setCurrentSet(1);
    setSecondsLeft(workSeconds);
    setPaused(false);
  }

  function handleCircleTap() {
    if (phase === "work" || phase === "rest") {
      setPaused((p) => !p);
    }
  }

  // SVG progress
  const progress =
    phase === "idle" || phase === "complete" || totalForPhase === 0
      ? 0
      : 1 - secondsLeft / totalForPhase;
  const dashOffset = progress * CIRCUMFERENCE;

  const strokeColor =
    phase === "rest" ? "stroke-emerald-500" : "stroke-orange-500";
  const isLastThree =
    (phase === "work" || phase === "rest") && secondsLeft <= 3;

  return (
    <div className="flex flex-col items-center gap-3">
      {/* SVG circle */}
      <div
        className={cn(
          "relative w-40 h-40 cursor-pointer select-none",
          (phase === "work" || phase === "rest") && "active:scale-95 transition-transform"
        )}
        onClick={handleCircleTap}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === " " || e.key === "Enter") handleCircleTap();
        }}
        aria-label={paused ? "Resume timer" : "Pause timer"}
      >
        <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
          {/* Background track */}
          <circle
            cx="60"
            cy="60"
            r={RADIUS}
            fill="none"
            strokeWidth={8}
            className="stroke-muted"
          />
          {/* Progress arc */}
          {phase !== "idle" && phase !== "complete" && (
            <circle
              cx="60"
              cy="60"
              r={RADIUS}
              fill="none"
              strokeWidth={8}
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
        <div className="absolute inset-0 flex flex-col items-center justify-center rotate-0">
          {phase === "idle" && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleStart();
              }}
              className="flex flex-col items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
            >
              <Play className="size-8" />
              <span className="text-xs font-medium">Start</span>
            </button>
          )}

          {(phase === "work" || phase === "rest") && (
            <>
              <span
                className={cn(
                  "text-3xl font-bold tabular-nums",
                  isLastThree && "animate-pulse"
                )}
              >
                {formatSeconds(secondsLeft)}
              </span>
              <span
                className={cn(
                  "text-xs font-semibold uppercase tracking-wider mt-0.5",
                  phase === "work"
                    ? "text-orange-500"
                    : "text-emerald-500"
                )}
              >
                {phase === "work" ? "Work" : "Rest"}
              </span>
              {paused && (
                <Pause className="size-5 text-muted-foreground mt-1" />
              )}
            </>
          )}

          {phase === "complete" && (
            <div className="flex flex-col items-center gap-1 text-green-600">
              <span className="text-sm font-semibold">Done!</span>
            </div>
          )}
        </div>
      </div>

      {/* Set counter + controls */}
      <div className="flex items-center gap-3">
        {phase !== "idle" && (
          <span className="text-xs text-muted-foreground tabular-nums">
            Set {currentSet} / {sets}
          </span>
        )}
        {(phase === "work" || phase === "rest" || phase === "complete") && (
          <button
            onClick={handleReset}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Reset timer"
          >
            <RotateCcw className="size-4" />
          </button>
        )}
      </div>
    </div>
  );
}
