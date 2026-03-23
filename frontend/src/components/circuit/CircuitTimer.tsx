"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";
import { getAudioContext, unlockAudio } from "@/lib/audio-unlock";
import { speakPhaseTransition } from "@/lib/voice-cues";
import {
  type CircuitExercise,
  CORE_EXERCISES,
  generateCircuitSequence,
} from "./circuit-exercises";

// ── Types ──────────────────────────────────────────────────────────────

type CircuitPhase = "prepare" | "work" | "rest" | "done";

const PHASE_BG: Record<CircuitPhase, string> = {
  prepare: "bg-zinc-800/80",
  work: "bg-teal-900/80",
  rest: "bg-blue-900/80",
  done: "bg-card",
};

const PHASE_TEXT: Record<CircuitPhase, string> = {
  prepare: "text-zinc-300",
  work: "text-teal-400",
  rest: "text-blue-400",
  done: "text-green-500",
};

const PHASE_LABEL: Record<CircuitPhase, string> = {
  prepare: "GET READY",
  work: "WORK",
  rest: "REST",
  done: "DONE",
};

const PHASE_RING: Record<CircuitPhase, string> = {
  prepare: "stroke-zinc-400",
  work: "stroke-teal-400",
  rest: "stroke-blue-400",
  done: "stroke-green-500",
};

// ── Audio ──────────────────────────────────────────────────────────────

async function beep(freq: number, duration: number, volume: number) {
  try {
    const ctx = getAudioContext();
    if (ctx.state !== "running") await ctx.resume();
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

function countdownTick() { beep(660, 0.08, 0.25); }
function transitionBeep() { beep(880, 0.2, 0.4); }

// ── Helpers ────────────────────────────────────────────────────────────

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

const RING_RADIUS = 100;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;
const PREPARE_SECONDS = 5;

// ── Component ──────────────────────────────────────────────────────────

export interface CircuitResult {
  completedExercises: number;
  targetExercises: number;
  exercisesPerformed: string[];
  workSeconds: number;
  restSeconds: number;
  durationSeconds: number;
}

interface CircuitTimerProps {
  workSeconds: number;
  restSeconds: number;
  totalExercises: number;
  onComplete: (result: CircuitResult) => void;
  onStop: (result: CircuitResult) => void;
}

export function CircuitTimer({
  workSeconds,
  restSeconds,
  totalExercises,
  onComplete,
  onStop,
}: CircuitTimerProps) {
  // Generate exercise sequence once on mount
  const [sequence] = useState<CircuitExercise[]>(() =>
    generateCircuitSequence(CORE_EXERCISES, totalExercises)
  );

  const [phase, setPhase] = useState<CircuitPhase>("prepare");
  const [secondsLeft, setSecondsLeft] = useState(PREPARE_SECONDS);
  const [paused, setPaused] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [transitionId, setTransitionId] = useState(0);
  const completedRef = useRef(0);
  const performedRef = useRef<string[]>([]);
  const skippedRef = useRef<Set<number>>(new Set()); // indices of skipped exercises

  // Wall-clock refs
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const phaseEndTimeRef = useRef(0);
  const secondsLeftRef = useRef(PREPARE_SECONDS);
  const startTimeRef = useRef(Date.now());
  const elapsedAtPauseRef = useRef(0);
  const phaseRef = useRef<CircuitPhase>("prepare");
  const pausedRef = useRef(false);
  const pendingVoiceCueRef = useRef<string | null>("get_ready");

  const currentIndexRef = useRef(0);

  useEffect(() => { secondsLeftRef.current = secondsLeft; }, [secondsLeft]);
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  useEffect(() => { pausedRef.current = paused; }, [paused]);
  useEffect(() => { currentIndexRef.current = currentIndex; }, [currentIndex]);

  // ── Timer management ─────────────────────────────────────────────

  const clearTimer = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => clearTimer, [clearTimer]);

  const startCountdown = useCallback((seconds: number) => {
    phaseEndTimeRef.current = Date.now() + seconds * 1000;
    setSecondsLeft(seconds);
  }, []);

  // Init: start prepare countdown
  useEffect(() => {
    unlockAudio();
    phaseEndTimeRef.current = Date.now() + PREPARE_SECONDS * 1000;
    pendingVoiceCueRef.current = "get_ready";
    setTransitionId(1);
  }, []);

  // ── Build result helper ──────────────────────────────────────────

  const buildResult = useCallback((): CircuitResult => {
    const dur = elapsedAtPauseRef.current +
      (startTimeRef.current > 0 ? Math.floor((Date.now() - startTimeRef.current) / 1000) : 0);
    // Completed = naturally finished exercises (not skipped)
    const completed = completedRef.current - skippedRef.current.size;
    return {
      completedExercises: Math.max(0, completed),
      targetExercises: totalExercises,
      exercisesPerformed: [...performedRef.current],
      workSeconds,
      restSeconds,
      durationSeconds: dur,
    };
  }, [totalExercises, workSeconds, restSeconds]);

  // ── Audio effects ────────────────────────────────────────────────

  useEffect(() => {
    if (transitionId > 0) {
      transitionBeep();
      if (pendingVoiceCueRef.current) {
        speakPhaseTransition(pendingVoiceCueRef.current);
        pendingVoiceCueRef.current = null;
      }
    }
  }, [transitionId]);

  // Countdown ticks at 3-2-1
  useEffect(() => {
    if (secondsLeft >= 1 && secondsLeft <= 3) {
      if (!pausedRef.current && phaseRef.current !== "done") {
        countdownTick();
      }
    }
  }, [secondsLeft]);

  // ── Main tick loop (wall-clock) ──────────────────────────────────

  useEffect(() => {
    clearTimer();
    if (phase === "done" || paused) return;

    phaseEndTimeRef.current = Date.now() + secondsLeftRef.current * 1000;

    intervalRef.current = setInterval(() => {
      // Update elapsed
      if (!pausedRef.current && startTimeRef.current > 0) {
        setElapsed(elapsedAtPauseRef.current + Math.floor((Date.now() - startTimeRef.current) / 1000));
      }

      const remainingMs = phaseEndTimeRef.current - Date.now();

      if (remainingMs <= 0) {
        const curPhase = phaseRef.current;

        if (curPhase === "prepare") {
          // Start first exercise work
          performedRef.current.push(sequence[0].id);
          setPhase("work");
          startCountdown(workSeconds);
          pendingVoiceCueRef.current = "work";
          setTransitionId((id) => id + 1);
          return;
        }

        if (curPhase === "work") {
          // Work done — mark exercise completed (not skipped)
          completedRef.current++;
          const curIdx = currentIndexRef.current;
          const nextIdx = curIdx + 1;

          if (nextIdx >= totalExercises) {
            // All done
            setPhase("done");
            setSecondsLeft(0);
            pendingVoiceCueRef.current = "complete";
            setTransitionId((id) => id + 1);
            // Freeze elapsed
            if (startTimeRef.current > 0) {
              elapsedAtPauseRef.current += Math.floor((Date.now() - startTimeRef.current) / 1000);
              startTimeRef.current = 0;
            }
            return;
          }

          // Go to rest (show next exercise)
          setCurrentIndex(nextIdx);
          setPhase("rest");
          startCountdown(restSeconds);
          setTransitionId((id) => id + 1);
          return;
        }

        if (curPhase === "rest") {
          // Rest done — start next exercise work
          const idx = currentIndexRef.current;
          if (idx < sequence.length) {
            performedRef.current.push(sequence[idx].id);
          }
          setPhase("work");
          startCountdown(workSeconds);
          pendingVoiceCueRef.current = "work";
          setTransitionId((id) => id + 1);
          return;
        }
      }

      setSecondsLeft(Math.max(0, Math.ceil(remainingMs / 1000)));
    }, 200);

    return clearTimer;
  }, [phase, paused, workSeconds, restSeconds, totalExercises, sequence, clearTimer, startCountdown]);

  // iOS visibility handler
  useEffect(() => {
    function onVisible() {
      if (document.visibilityState !== "visible") return;
      if (phaseRef.current === "done" || pausedRef.current) return;
      const remainingMs = phaseEndTimeRef.current - Date.now();
      setSecondsLeft(Math.max(0, Math.ceil(remainingMs / 1000)));
      if (startTimeRef.current > 0) {
        setElapsed(elapsedAtPauseRef.current + Math.floor((Date.now() - startTimeRef.current) / 1000));
      }
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);

  // ── Handlers ─────────────────────────────────────────────────────

  function handlePauseToggle() {
    if (phase === "done") return;
    if (paused) {
      startTimeRef.current = Date.now();
      phaseEndTimeRef.current = Date.now() + secondsLeftRef.current * 1000;
      setPaused(false);
    } else {
      elapsedAtPauseRef.current += Math.floor((Date.now() - startTimeRef.current) / 1000);
      startTimeRef.current = 0;
      setPaused(true);
    }
  }

  function handleStop() {
    clearTimer();
    if (startTimeRef.current > 0) {
      elapsedAtPauseRef.current += Math.floor((Date.now() - startTimeRef.current) / 1000);
      startTimeRef.current = 0;
    }
    setElapsed(elapsedAtPauseRef.current);
    onStop(buildResult());
  }

  function handleNext() {
    if (phase === "done" || phase === "prepare") return;

    // Mark current exercise as skipped (doesn't count as completed)
    const curIdx = currentIndex;
    skippedRef.current.add(curIdx);

    const nextIdx = curIdx + 1;
    if (nextIdx >= totalExercises) {
      // Last exercise — go to completion
      setPhase("done");
      setSecondsLeft(0);
      pendingVoiceCueRef.current = "complete";
      setTransitionId((id) => id + 1);
      if (startTimeRef.current > 0) {
        elapsedAtPauseRef.current += Math.floor((Date.now() - startTimeRef.current) / 1000);
        startTimeRef.current = 0;
      }
      return;
    }

    // Advance to next exercise, start work
    setCurrentIndex(nextIdx);
    performedRef.current.push(sequence[nextIdx].id);
    setPhase("work");
    startCountdown(workSeconds);
    pendingVoiceCueRef.current = "work";
    setTransitionId((id) => id + 1);
  }

  function handleBack() {
    if (phase === "done" || phase === "prepare") return;
    if (currentIndex <= 0) return; // first exercise — no-op

    const prevIdx = currentIndex - 1;
    // Un-skip previous if it was skipped
    skippedRef.current.delete(prevIdx);

    setCurrentIndex(prevIdx);
    // Remove last entry from performed if it was the current exercise
    // and re-add the previous one
    performedRef.current.push(sequence[prevIdx].id);
    setPhase("work");
    startCountdown(workSeconds);
    pendingVoiceCueRef.current = "work";
    setTransitionId((id) => id + 1);
  }

  // Auto-call onComplete when done
  useEffect(() => {
    if (phase === "done") {
      onComplete(buildResult());
    }
  }, [phase, onComplete, buildResult]);

  // ── Progress ring ────────────────────────────────────────────────

  const phaseDuration =
    phase === "prepare" ? PREPARE_SECONDS :
    phase === "work" ? workSeconds :
    phase === "rest" ? restSeconds : 0;

  const [smoothProgress, setSmoothProgress] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (phase === "done" || paused) {
      cancelAnimationFrame(rafRef.current);
      const p = phaseDuration > 0 ? 1 - secondsLeft / phaseDuration : 0;
      setSmoothProgress(p);
      return;
    }
    function tick() {
      const remainingMs = phaseEndTimeRef.current - Date.now();
      const dur = phaseDuration * 1000;
      const p = dur > 0 ? 1 - Math.max(0, remainingMs) / dur : 0;
      setSmoothProgress(Math.min(1, Math.max(0, p)));
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [phase, paused, phaseDuration, secondsLeft]);

  const dashOffset = RING_CIRCUMFERENCE - smoothProgress * RING_CIRCUMFERENCE;

  // ── Current & next exercise ──────────────────────────────────────

  const currentExercise = sequence[currentIndex] || sequence[0];
  const nextExercise = currentIndex + 1 < sequence.length ? sequence[currentIndex + 1] : null;

  // During REST, show the NEXT exercise as the main one (brief §5.4)
  const displayExercise = phase === "rest" ? (nextExercise || currentExercise) : currentExercise;
  const previewExercise = phase === "work" ? nextExercise : null;

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div
      className={cn(
        "fixed inset-0 flex flex-col transition-colors duration-500",
        PHASE_BG[phase]
      )}
    >
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 pt-4 pb-1">
        <span className={cn("text-sm font-bold uppercase tracking-[0.2em]", PHASE_TEXT[phase])}>
          {PHASE_LABEL[phase]}
        </span>
        <span className="text-sm text-muted-foreground tabular-nums">
          {completedRef.current + (phase === "work" ? 1 : 0)}/{totalExercises}
        </span>
      </div>

      {/* Main content area — tap to pause */}
      <div
        className="flex flex-1 flex-col items-center justify-center px-4 cursor-pointer"
        onClick={handlePauseToggle}
      >
        {/* Progress ring + countdown */}
        <div className="relative w-56 h-56 mb-4">
          <svg viewBox="0 0 220 220" className="w-full h-full -rotate-90">
            <circle
              cx="110" cy="110" r={RING_RADIUS}
              fill="none" strokeWidth={8}
              className="stroke-white/10"
            />
            <circle
              cx="110" cy="110" r={RING_RADIUS}
              fill="none" strokeWidth={8}
              strokeLinecap="round"
              strokeDasharray={RING_CIRCUMFERENCE}
              strokeDashoffset={dashOffset}
              className={PHASE_RING[phase]}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={cn(
              "text-6xl font-bold tabular-nums leading-none transition-transform duration-150",
              secondsLeft <= 3 && secondsLeft > 0 && "scale-110"
            )}>
              {formatTime(secondsLeft)}
            </span>
          </div>
        </div>

        {/* Exercise card with back/next arrows */}
        {phase !== "prepare" && (
          <div className="w-full max-w-sm flex items-center gap-2">
            {/* Back arrow */}
            <button
              onClick={(e) => { e.stopPropagation(); handleBack(); }}
              disabled={currentIndex <= 0 || phase === "rest"}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-black/20 text-white/50 transition-colors hover:text-white/80 disabled:opacity-20 disabled:cursor-default"
              aria-label="Previous exercise"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 18l-6-6 6-6" />
              </svg>
            </button>

            {/* Exercise info */}
            <div className="flex-1 rounded-2xl border border-white/10 bg-black/20 p-5 backdrop-blur-sm">
              {displayExercise.image && (
                <img
                  src={`/exercises/core/${displayExercise.image}`}
                  alt={displayExercise.name}
                  className="mx-auto mb-3 max-w-[300px] w-full rounded-xl"
                />
              )}
              <h3 className="text-2xl font-bold text-center mb-2">
                {displayExercise.name}
              </h3>
              <p className="text-sm text-center text-white/70 leading-relaxed">
                {displayExercise.description}
              </p>
            </div>

            {/* Next arrow */}
            <button
              onClick={(e) => { e.stopPropagation(); handleNext(); }}
              disabled={phase === "rest"}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-black/20 text-white/50 transition-colors hover:text-white/80 disabled:opacity-20 disabled:cursor-default"
              aria-label="Skip exercise"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </button>
          </div>
        )}

        {/* Prepare: show first exercise preview */}
        {phase === "prepare" && (
          <div className="w-full max-w-sm rounded-2xl border border-white/10 bg-black/20 p-5 backdrop-blur-sm">
            <p className="text-xs text-center text-white/50 uppercase tracking-wider mb-2">First up</p>
            {sequence[0].image && (
              <img
                src={`/exercises/core/${sequence[0].image}`}
                alt={sequence[0].name}
                className="mx-auto mb-3 max-w-[300px] w-full rounded-xl"
              />
            )}
            <h3 className="text-2xl font-bold text-center mb-2">
              {sequence[0].name}
            </h3>
            <p className="text-sm text-center text-white/70 leading-relaxed">
              {sequence[0].description}
            </p>
          </div>
        )}

        {/* Next exercise preview (during work) */}
        {previewExercise && phase === "work" && (
          <div className="w-full max-w-sm mt-3 rounded-xl border border-white/5 bg-black/10 px-4 py-2.5">
            <span className="text-xs text-white/40">Next: </span>
            <span className="text-sm font-medium text-white/60">{previewExercise.name}</span>
          </div>
        )}

        {/* REST: pulsing GET READY */}
        {phase === "rest" && (
          <div className="mt-4 animate-pulse">
            <span className="text-lg font-bold text-blue-300 uppercase tracking-wider">Get Ready</span>
          </div>
        )}

        {/* Paused overlay */}
        {paused && (
          <div className="mt-4 rounded-xl bg-white/10 px-8 py-3 backdrop-blur-sm">
            <span className="text-xl font-bold text-white/80 tracking-wider">PAUSED</span>
          </div>
        )}
      </div>

      {/* Bottom: elapsed + controls */}
      <div className="pb-28 px-4">
        <div className="flex justify-center gap-8 text-sm text-muted-foreground tabular-nums mb-5">
          <div className="flex flex-col items-center">
            <span className="text-xs uppercase tracking-wider mb-0.5">Elapsed</span>
            <span className="font-semibold text-foreground">{formatTime(elapsed)}</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-xs uppercase tracking-wider mb-0.5">Exercise</span>
            <span className="font-semibold text-foreground">
              {completedRef.current + (phase === "work" ? 1 : 0)}/{totalExercises}
            </span>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={(e) => { e.stopPropagation(); handlePauseToggle(); }}
            className="flex h-14 flex-1 max-w-[160px] items-center justify-center gap-2 rounded-2xl border border-border bg-card/50 text-sm font-bold text-foreground transition-all active:scale-[0.98]"
          >
            {paused ? (
              <>
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
                RESUME
              </>
            ) : (
              <>
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1" /><rect x="14" y="4" width="4" height="16" rx="1" /></svg>
                PAUSE
              </>
            )}
          </button>

          <button
            onClick={(e) => { e.stopPropagation(); handleStop(); }}
            className="flex h-14 w-14 items-center justify-center rounded-2xl border border-red-500/30 bg-red-500/10 text-red-400 hover:text-red-300 transition-colors"
            aria-label="Stop circuit"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2" /></svg>
          </button>
        </div>
      </div>
    </div>
  );
}
