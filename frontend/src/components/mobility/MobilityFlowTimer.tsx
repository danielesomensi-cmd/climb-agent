"use client";

// A231 — Auto-advancing guided stretch flow, same engine as CircuitTimer:
// wall-clock phases (prepare → hold → rest → …), beeps + voice cues, smooth
// progress ring, back/next/pause/stop. The difference: each step carries its
// own duration (holds vary per stretch) and a side (left/right sequencing).

import { useState, useRef, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";
import { unlockAudio } from "@/lib/audio-unlock";
import { countdownTick, transitionBeep } from "@/lib/beep";
import { speakPhaseTransition } from "@/lib/voice-cues";
import type { MobilityFlowStep } from "@/lib/api";
import { RegionFigure } from "./RegionFigure";

// ── Types ──────────────────────────────────────────────────────────────

type FlowPhase = "prepare" | "work" | "rest" | "done";

const PHASE_BG: Record<FlowPhase, string> = {
  prepare: "bg-zinc-800/80",
  work: "bg-violet-950/90",
  rest: "bg-blue-900/80",
  done: "bg-card",
};

const PHASE_TEXT: Record<FlowPhase, string> = {
  prepare: "text-zinc-300",
  work: "text-violet-400",
  rest: "text-blue-400",
  done: "text-green-500",
};

const PHASE_RING: Record<FlowPhase, string> = {
  prepare: "stroke-zinc-400",
  work: "stroke-violet-400",
  rest: "stroke-blue-400",
  done: "stroke-green-500",
};

// ── Audio (same tones as Core Circuit) ─────────────────────────────────



function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

const RING_RADIUS = 100;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;
const PREPARE_SECONDS = 5;

// ── Component ──────────────────────────────────────────────────────────

export interface MobilityFlowResult {
  completedSteps: number;
  totalSteps: number;
  entriesPerformed: Array<{ id: string; name: string }>;
  durationSeconds: number;
}

interface MobilityFlowTimerProps {
  steps: MobilityFlowStep[];
  restSeconds: number;
  onComplete: (result: MobilityFlowResult) => void;
  onStop: (result: MobilityFlowResult) => void;
  onExit: () => void;
}

function stepLabel(step: MobilityFlowStep): string {
  const bits: string[] = [];
  if (step.side) bits.push(step.side === "left" ? "Left side" : "Right side");
  if (step.set_count > 1) bits.push(`Set ${step.set}/${step.set_count}`);
  return bits.join(" · ");
}

export function MobilityFlowTimer({
  steps,
  restSeconds,
  onComplete,
  onStop,
  onExit,
}: MobilityFlowTimerProps) {
  const totalSteps = steps.length;

  const [phase, setPhase] = useState<FlowPhase>("prepare");
  const [secondsLeft, setSecondsLeft] = useState(PREPARE_SECONDS);
  const [paused, setPaused] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [transitionId, setTransitionId] = useState(0);
  const [completedSteps, setCompletedSteps] = useState(0);
  const completedRef = useRef(0);
  const performedRef = useRef<Map<string, string>>(new Map()); // id → name

  // Wall-clock refs
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const phaseEndTimeRef = useRef(0);
  const secondsLeftRef = useRef(PREPARE_SECONDS);
  const startTimeRef = useRef(0);
  const elapsedAtPauseRef = useRef(0);
  const phaseRef = useRef<FlowPhase>("prepare");
  const pausedRef = useRef(false);
  const pendingVoiceCueRef = useRef<string | null>("get_ready");
  const currentIndexRef = useRef(0);
  const phaseDurationRef = useRef(PREPARE_SECONDS);

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
    phaseDurationRef.current = seconds;
    setSecondsLeft(seconds);
  }, []);

  // Init: start prepare countdown
  useEffect(() => {
    unlockAudio();
    startTimeRef.current = Date.now();
    phaseEndTimeRef.current = Date.now() + PREPARE_SECONDS * 1000;
    phaseDurationRef.current = PREPARE_SECONDS;
    transitionBeep();
    speakPhaseTransition("get_ready");
  }, []);

  // ── Build result helper ──────────────────────────────────────────

  const buildResult = useCallback((): MobilityFlowResult => {
    const dur = elapsedAtPauseRef.current +
      (startTimeRef.current > 0 ? Math.floor((Date.now() - startTimeRef.current) / 1000) : 0);
    return {
      completedSteps: completedRef.current,
      totalSteps,
      entriesPerformed: Array.from(performedRef.current, ([id, name]) => ({ id, name })),
      durationSeconds: dur,
    };
  }, [totalSteps]);

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
      if (!pausedRef.current && phaseRef.current !== "done" && phaseDurationRef.current > 3) {
        countdownTick();
      }
    }
  }, [secondsLeft]);

  // ── Phase transitions ────────────────────────────────────────────

  const markPerformed = useCallback((idx: number) => {
    const s = steps[idx];
    if (s) performedRef.current.set(s.entry_id, s.name);
  }, [steps]);

  const freezeElapsed = useCallback(() => {
    if (startTimeRef.current > 0) {
      elapsedAtPauseRef.current += Math.floor((Date.now() - startTimeRef.current) / 1000);
      startTimeRef.current = 0;
    }
  }, []);

  const advanceFromWork = useCallback(() => {
    completedRef.current++;
    setCompletedSteps(completedRef.current);
    const nextIdx = currentIndexRef.current + 1;
    if (nextIdx >= totalSteps) {
      setPhase("done");
      setSecondsLeft(0);
      pendingVoiceCueRef.current = "complete";
      setTransitionId((id) => id + 1);
      freezeElapsed();
      return;
    }
    setPhase("rest");
    startCountdown(restSeconds);
    pendingVoiceCueRef.current = "rest";
    setTransitionId((id) => id + 1);
  }, [totalSteps, restSeconds, startCountdown, freezeElapsed]);

  const advanceFromRest = useCallback(() => {
    const nextIdx = currentIndexRef.current + 1;
    setCurrentIndex(nextIdx);
    markPerformed(nextIdx);
    setPhase("work");
    startCountdown(steps[nextIdx]?.seconds ?? 30);
    pendingVoiceCueRef.current = "rep_rest"; // "Hold"
    setTransitionId((id) => id + 1);
  }, [steps, startCountdown, markPerformed]);

  // ── Main tick loop (wall-clock) ──────────────────────────────────

  useEffect(() => {
    clearTimer();
    if (phase === "done" || paused) return;

    phaseEndTimeRef.current = Date.now() + secondsLeftRef.current * 1000;

    intervalRef.current = setInterval(() => {
      if (!pausedRef.current && startTimeRef.current > 0) {
        setElapsed(elapsedAtPauseRef.current + Math.floor((Date.now() - startTimeRef.current) / 1000));
      }

      const remainingMs = phaseEndTimeRef.current - Date.now();

      if (remainingMs <= 0) {
        const curPhase = phaseRef.current;

        if (curPhase === "prepare") {
          markPerformed(0);
          setPhase("work");
          startCountdown(steps[0]?.seconds ?? 30);
          pendingVoiceCueRef.current = "rep_rest";
          setTransitionId((id) => id + 1);
          return;
        }

        if (curPhase === "work") {
          advanceFromWork();
          return;
        }

        if (curPhase === "rest") {
          advanceFromRest();
          return;
        }
      }

      setSecondsLeft(Math.max(0, Math.ceil(remainingMs / 1000)));
    }, 200);

    return clearTimer;
  }, [phase, paused, steps, clearTimer, startCountdown, advanceFromWork, advanceFromRest, markPerformed]);

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
    freezeElapsed();
    setElapsed(elapsedAtPauseRef.current);
    onStop(buildResult());
  }

  function handleNext() {
    if (phase === "done" || phase === "prepare") return;
    if (phase === "work") {
      advanceFromWork();
      return;
    }
    if (phase === "rest") {
      advanceFromRest();
    }
  }

  function handleBack() {
    if (phase === "done" || phase === "prepare") return;

    if (phase === "rest") {
      // Redo current step
      completedRef.current = Math.max(0, completedRef.current - 1);
      setCompletedSteps(completedRef.current);
      setPhase("work");
      startCountdown(steps[currentIndexRef.current]?.seconds ?? 30);
      pendingVoiceCueRef.current = "rep_rest";
      setTransitionId((id) => id + 1);
      return;
    }

    if (phase === "work") {
      if (currentIndex <= 0) return;
      const prevIdx = currentIndex - 1;
      setCurrentIndex(prevIdx);
      setPhase("work");
      startCountdown(steps[prevIdx]?.seconds ?? 30);
      pendingVoiceCueRef.current = "rep_rest";
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
    phase === "rest" ? restSeconds :
    phase === "work" ? (steps[currentIndex]?.seconds ?? 0) : 0;
  const [smoothProgress, setSmoothProgress] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (phase === "done" || paused) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        const p = phaseDuration > 0 ? 1 - secondsLeft / phaseDuration : 0;
        setSmoothProgress(p);
      });
      return () => cancelAnimationFrame(rafRef.current);
    }
    function tick() {
      const remainingMs = phaseEndTimeRef.current - Date.now();
      const dur = phaseDurationRef.current * 1000;
      const p = dur > 0 ? 1 - Math.max(0, remainingMs) / dur : 0;
      setSmoothProgress(Math.min(1, Math.max(0, p)));
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [phase, paused, phaseDuration, secondsLeft]);

  const dashOffset = RING_CIRCUMFERENCE - smoothProgress * RING_CIRCUMFERENCE;

  // ── Current & next step ──────────────────────────────────────────

  const currentStep = steps[currentIndex] || steps[0];
  const nextStep = currentIndex + 1 < steps.length ? steps[currentIndex + 1] : null;

  // During REST, show the NEXT step as the main one
  const displayStep = phase === "rest" ? (nextStep || currentStep) : currentStep;
  const previewStep = phase === "work" ? nextStep : null;

  const phaseLabel =
    phase === "prepare" ? "GET READY"
    : phase === "rest" ? "SWITCH"
    : phase === "done" ? "DONE"
    : displayStep.kind === "release" ? "RELEASE"
    : displayStep.kind === "flow" ? "SLOW FLOW"
    : "HOLD";

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div
      className={cn(
        "fixed inset-0 z-[60] flex flex-col transition-colors duration-500",
        PHASE_BG[phase]
      )}
    >
      {/* Header — minimal */}
      <div className="flex shrink-0 items-center justify-between px-4 pt-[calc(0.25rem+env(safe-area-inset-top))] pb-0.5">
        <span className={cn("text-sm font-bold uppercase tracking-[0.2em]", PHASE_TEXT[phase])}>
          {phaseLabel}
        </span>
        <button
          onClick={(e) => { e.stopPropagation(); handleExit(); }}
          className="-mr-2 flex min-h-[44px] items-center gap-1.5 px-2 text-sm text-white/60 transition-colors hover:text-white/90"
          aria-label="Exit flow"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
          Exit
        </button>
      </div>

      {/* Timer ring + controls */}
      <div className="mt-4 flex shrink-0 items-center gap-3 px-4">
        <div className="relative h-36 w-36 shrink-0 cursor-pointer" onClick={handlePauseToggle}>
          <svg viewBox="0 0 220 220" className="h-full w-full -rotate-90">
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
              "text-4xl font-bold leading-none tabular-nums transition-transform duration-150",
              secondsLeft <= 3 && secondsLeft > 0 && "scale-110"
            )}>
              {formatTime(secondsLeft)}
            </span>
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-2">
          <div className="flex gap-4 text-sm tabular-nums">
            <div className="flex flex-col">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Elapsed</span>
              <span className="font-semibold text-foreground">{formatTime(elapsed)}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Step</span>
              <span className="font-semibold text-foreground">
                {Math.min(completedSteps + (phase === "work" ? 1 : 0), totalSteps)}/{totalSteps}
              </span>
            </div>
          </div>

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
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 transition-colors hover:text-red-300"
              aria-label="Stop flow"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2" /></svg>
            </button>
          </div>

          {paused && (
            <span className="text-sm font-bold tracking-wider text-white/60">PAUSED</span>
          )}
        </div>
      </div>

      {/* Step card area */}
      <div
        className="flex min-h-0 flex-1 cursor-pointer flex-col items-center overflow-y-auto px-4 pt-2"
        onClick={handlePauseToggle}
      >
        {phase !== "prepare" && (
          <div className="flex w-full max-w-sm items-center gap-2">
            <button
              onClick={(e) => { e.stopPropagation(); handleBack(); }}
              disabled={currentIndex <= 0 && phase === "work"}
              className="flex h-10 w-10 shrink-0 items-center justify-center self-center rounded-xl border border-white/10 bg-black/20 text-white/50 transition-colors hover:text-white/80 disabled:cursor-default disabled:opacity-20"
              aria-label="Previous"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 18l-6-6 6-6" />
              </svg>
            </button>

            <div className="flex-1 rounded-2xl border border-white/10 bg-black/20 p-3 backdrop-blur-sm">
              <div className="mx-auto mb-2 h-[110px]">
                <RegionFigure region={displayStep.body_region} className="mx-auto" />
              </div>
              <h3 className="mb-1 text-center text-lg font-bold">{displayStep.name}</h3>
              {stepLabel(displayStep) && (
                <div className="mb-1 text-center">
                  <span className="rounded-full border border-violet-400/40 bg-violet-500/15 px-3 py-0.5 text-sm font-bold uppercase tracking-wider text-violet-300">
                    {stepLabel(displayStep)}
                  </span>
                </div>
              )}
              <p className="text-center text-sm leading-relaxed text-white/70">
                {displayStep.cue}
              </p>
            </div>

            <button
              onClick={(e) => { e.stopPropagation(); handleNext(); }}
              className="flex h-10 w-10 shrink-0 items-center justify-center self-center rounded-xl border border-white/10 bg-black/20 text-white/50 transition-colors hover:text-white/80"
              aria-label="Next"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </button>
          </div>
        )}

        {phase === "prepare" && steps[0] && (
          <div className="w-full max-w-sm rounded-2xl border border-white/10 bg-black/20 p-3 backdrop-blur-sm">
            <p className="mb-2 text-center text-xs uppercase tracking-wider text-white/50">First up</p>
            <div className="mx-auto mb-2 h-[110px]">
              <RegionFigure region={steps[0].body_region} className="mx-auto" />
            </div>
            <h3 className="mb-1 text-center text-lg font-bold">{steps[0].name}</h3>
            {stepLabel(steps[0]) && (
              <p className="mb-1 text-center text-sm font-semibold text-violet-300">{stepLabel(steps[0])}</p>
            )}
            <p className="text-center text-sm leading-relaxed text-white/70">{steps[0].cue}</p>
          </div>
        )}

        {previewStep && phase === "work" && (
          <div className="mt-2 w-full max-w-sm rounded-xl border border-white/5 bg-black/10 px-4 py-2">
            <span className="text-xs text-white/40">Next: </span>
            <span className="text-sm font-medium text-white/60">
              {previewStep.name}
              {previewStep.side ? ` — ${previewStep.side === "left" ? "left" : "right"}` : ""}
            </span>
          </div>
        )}

        {phase === "rest" && (
          <div className="mt-2 animate-pulse">
            <span className="text-lg font-bold uppercase tracking-wider text-blue-300">Get Ready</span>
          </div>
        )}
      </div>

      <div className="h-[env(safe-area-inset-bottom)] shrink-0" />
    </div>
  );
}
