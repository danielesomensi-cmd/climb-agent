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
  onExit: () => void;
}

export function CircuitTimer({
  workSeconds,
  restSeconds,
  totalExercises,
  onComplete,
  onStop,
  onExit,
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

  // Countdown ticks at 3-2-1 (skip if phase duration ≤ 3s)
  useEffect(() => {
    if (secondsLeft >= 1 && secondsLeft <= 3) {
      if (!pausedRef.current && phaseRef.current !== "done") {
        const dur = phaseRef.current === "work" ? workSeconds
          : phaseRef.current === "rest" ? restSeconds
          : PREPARE_SECONDS;
        if (dur > 3) countdownTick();
      }
    }
  }, [secondsLeft, workSeconds, restSeconds]);

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

          // Go to rest — do NOT increment index yet (REST display reads currentIndex+1)
          setPhase("rest");
          startCountdown(restSeconds);
          pendingVoiceCueRef.current = "rest";
          setTransitionId((id) => id + 1);
          return;
        }

        if (curPhase === "rest") {
          // Rest done — advance to next exercise and start work
          const nextIdx = currentIndexRef.current + 1;
          setCurrentIndex(nextIdx);
          if (nextIdx < sequence.length) {
            performedRef.current.push(sequence[nextIdx].id);
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

    if (phase === "work") {
      // Skip remaining work → go to REST (same as natural timer expiry)
      completedRef.current++;
      const curIdx = currentIndexRef.current;
      const nextIdx = curIdx + 1;

      if (nextIdx >= totalExercises) {
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

      setPhase("rest");
      startCountdown(restSeconds);
      pendingVoiceCueRef.current = "rest";
      setTransitionId((id) => id + 1);
      return;
    }

    if (phase === "rest") {
      // Skip remaining rest → go to WORK for next exercise
      const nextIdx = currentIndexRef.current + 1;
      setCurrentIndex(nextIdx);
      if (nextIdx < sequence.length) {
        performedRef.current.push(sequence[nextIdx].id);
      }
      setPhase("work");
      startCountdown(workSeconds);
      pendingVoiceCueRef.current = "work";
      setTransitionId((id) => id + 1);
    }
  }

  function handleBack() {
    if (phase === "done" || phase === "prepare") return;

    if (phase === "rest") {
      // During REST → go back to current exercise's WORK (redo it)
      setPhase("work");
      startCountdown(workSeconds);
      completedRef.current = Math.max(0, completedRef.current - 1);
      pendingVoiceCueRef.current = "work";
      setTransitionId((id) => id + 1);
      return;
    }

    if (phase === "work") {
      // During WORK → go back to previous exercise's WORK
      if (currentIndex <= 0) return;
      const prevIdx = currentIndex - 1;
      setCurrentIndex(prevIdx);
      performedRef.current.push(sequence[prevIdx].id);
      setPhase("work");
      startCountdown(workSeconds);
      pendingVoiceCueRef.current = "work";
      setTransitionId((id) => id + 1);
    }
  }

  function handleExit() {
    clearTimer();
    onExit();
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
      {/* Header — thin */}
      <div className="flex shrink-0 items-center justify-between px-4 pt-2 pb-1">
        <span className={cn("text-sm font-bold uppercase tracking-[0.2em]", PHASE_TEXT[phase])}>
          {PHASE_LABEL[phase]}
        </span>
        <button
          onClick={(e) => { e.stopPropagation(); handleExit(); }}
          className="flex items-center gap-1 text-xs text-white/30 hover:text-white/60 transition-colors"
          aria-label="Exit circuit"
        >
          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
          Exit
        </button>
      </div>

      {/* Timer ring + controls — side by side, shrink-0 */}
      <div className="flex shrink-0 items-center gap-3 px-4 mt-4">
        {/* Ring — left */}
        <div
          className="relative w-36 h-36 shrink-0 cursor-pointer"
          onClick={handlePauseToggle}
        >
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
              "text-4xl font-bold tabular-nums leading-none transition-transform duration-150",
              secondsLeft <= 3 && secondsLeft > 0 && "scale-110"
            )}>
              {formatTime(secondsLeft)}
            </span>
          </div>
        </div>

        {/* Stats + controls — right */}
        <div className="flex flex-col gap-2 min-w-0">
          {/* Counters */}
          <div className="flex gap-4 text-sm tabular-nums">
            <div className="flex flex-col">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Elapsed</span>
              <span className="font-semibold text-foreground">{formatTime(elapsed)}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Exercise</span>
              <span className="font-semibold text-foreground">
                {completedRef.current + (phase === "work" ? 1 : 0)}/{totalExercises}
              </span>
            </div>
          </div>

          {/* Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={(e) => { e.stopPropagation(); handlePauseToggle(); }}
              className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-xl border border-border bg-card/50 text-sm font-bold text-foreground transition-all active:scale-[0.98]"
            >
              {paused ? (
                <>
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
                  RESUME
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1" /><rect x="14" y="4" width="4" height="16" rx="1" /></svg>
                  PAUSE
                </>
              )}
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); handleStop(); }}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 hover:text-red-300 transition-colors"
              aria-label="Stop circuit"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2" /></svg>
            </button>
          </div>

          {/* Paused label */}
          {paused && (
            <span className="text-sm font-bold text-white/60 tracking-wider">PAUSED</span>
          )}
        </div>
      </div>

      {/* Exercise card area — flex-1, tap to pause */}
      <div
        className="flex flex-1 min-h-0 flex-col items-center px-4 pt-2 overflow-y-auto cursor-pointer"
        onClick={handlePauseToggle}
      >
        {/* Exercise card with back/next arrows */}
        {phase !== "prepare" && (
          <div className="w-full max-w-sm flex items-center gap-2">
            {/* Back arrow */}
            <button
              onClick={(e) => { e.stopPropagation(); handleBack(); }}
              disabled={currentIndex <= 0 && phase === "work"}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-black/20 text-white/50 transition-colors hover:text-white/80 disabled:opacity-20 disabled:cursor-default self-center"
              aria-label="Previous"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 18l-6-6 6-6" />
              </svg>
            </button>

            {/* Exercise info */}
            <div className="flex-1 rounded-2xl border border-white/10 bg-black/20 p-3 backdrop-blur-sm">
              {displayExercise.image && (
                <img
                  src={`/exercises/core/${displayExercise.image}`}
                  alt={displayExercise.name}
                  className="mx-auto mb-2 max-h-[140px] w-full object-contain rounded-xl"
                />
              )}
              <h3 className="text-lg font-bold text-center mb-1">
                {displayExercise.name}
              </h3>
              <p className="text-sm text-center text-white/70 leading-relaxed">
                {displayExercise.description}
              </p>
            </div>

            {/* Next arrow */}
            <button
              onClick={(e) => { e.stopPropagation(); handleNext(); }}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-black/20 text-white/50 transition-colors hover:text-white/80 self-center"
              aria-label="Next"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </button>
          </div>
        )}

        {/* Prepare: show first exercise preview */}
        {phase === "prepare" && (
          <div className="w-full max-w-sm rounded-2xl border border-white/10 bg-black/20 p-3 backdrop-blur-sm">
            <p className="text-xs text-center text-white/50 uppercase tracking-wider mb-2">First up</p>
            {sequence[0].image && (
              <img
                src={`/exercises/core/${sequence[0].image}`}
                alt={sequence[0].name}
                className="mx-auto mb-2 max-h-[140px] w-full object-contain rounded-xl"
              />
            )}
            <h3 className="text-lg font-bold text-center mb-1">
              {sequence[0].name}
            </h3>
            <p className="text-sm text-center text-white/70 leading-relaxed">
              {sequence[0].description}
            </p>
          </div>
        )}

        {/* Next exercise preview (during work) */}
        {previewExercise && phase === "work" && (
          <div className="w-full max-w-sm mt-2 rounded-xl border border-white/5 bg-black/10 px-4 py-2">
            <span className="text-xs text-white/40">Next: </span>
            <span className="text-sm font-medium text-white/60">{previewExercise.name}</span>
          </div>
        )}

        {/* REST: pulsing GET READY */}
        {phase === "rest" && (
          <div className="mt-2 animate-pulse">
            <span className="text-lg font-bold text-blue-300 uppercase tracking-wider">Get Ready</span>
          </div>
        )}
      </div>

      {/* Safe area bottom spacer for nav bar */}
      <div className="shrink-0 h-[env(safe-area-inset-bottom)]" />
    </div>
  );
}
