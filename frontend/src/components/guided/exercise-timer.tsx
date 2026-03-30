"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Play, Pause, RotateCcw, CheckCircle2, ChevronLeft, ChevronRight, Maximize2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { getAudioContext, unlockAudio } from "@/lib/audio-unlock";
import { speakPhaseTransition } from "@/lib/voice-cues";

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
  unilateral?: boolean;             // alternate RIGHT/LEFT each set; internally doubles set count
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
  unilateral = false,
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
  const phaseEndTimeRef = useRef<number>(0);
  const secondsLeftRef = useRef(0);
  useEffect(() => { secondsLeftRef.current = secondsLeft; }, [secondsLeft]);
  const onSetChangeRef = useRef(onSetChange);
  useEffect(() => { onSetChangeRef.current = onSetChange; }, [onSetChange]);

  // Voice cue: store the phase at transition time so the transitionId effect can speak it
  const pendingVoiceCueRef = useRef<Phase | null>(null);

  // Refs for countdown beep effect (avoid re-triggering on phase/paused change)
  const phaseRef = useRef(phase);
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  const pausedRef = useRef(paused);
  useEffect(() => { pausedRef.current = paused; }, [paused]);

  const isManual = workSeconds === 0;
  const hasRepLoop = !isManual && reps > 1;
  // B124: manual work + timed rest between reps (technique drills, limit bouldering)
  const hasManualRepLoop = isManual && reps > 1 && restBetweenRepsSeconds > 0;

  // B169-F3b: unilateral — internally double the set count, alternate sides
  const totalSets = unilateral ? sets * 2 : sets;
  const currentSide: "RIGHT" | "LEFT" | null = unilateral
    ? currentSet % 2 === 1 ? "RIGHT" : "LEFT"
    : null;
  const displaySet = unilateral ? Math.ceil(currentSet / 2) : currentSet;

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

  // Transition beep + voice cue + visual flash
  useEffect(() => {
    if (transitionId > 0) {
      transitionBeep();
      if (pendingVoiceCueRef.current) {
        speakPhaseTransition(pendingVoiceCueRef.current);
        pendingVoiceCueRef.current = null;
      }
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

  /** Set wall-clock end time + display value. Use for all non-tick timer updates. */
  const startCountdown = useCallback((seconds: number) => {
    phaseEndTimeRef.current = Date.now() + seconds * 1000;
    setSecondsLeft(seconds);
  }, []);

  // Main tick — wall-clock based so iOS background suspension doesn't freeze countdown.
  // Instead of decrementing a counter, each tick computes remaining = endTime - Date.now().
  useEffect(() => {
    clearTimer();

    if (phase === "idle" || phase === "complete" || paused) return;
    if (phase === "work" && isManual) return; // manual work has no countdown (rep_rest/set_rest still run)

    // (Re)compute end time from current remaining seconds.
    // Handles both: (a) resuming from pause, (b) effect re-run after phase transition.
    phaseEndTimeRef.current = Date.now() + secondsLeftRef.current * 1000;

    intervalRef.current = setInterval(() => {
      const remainingMs = phaseEndTimeRef.current - Date.now();

      if (remainingMs <= 0) {
        // --- Phase transition ---

        if (phase === "get_ready") {
          setPhase("work");
          pendingVoiceCueRef.current = "work";
          setTransitionId((id) => id + 1);
          if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
          return;
        }

        if (phase === "work") {
          // More reps in this set?
          if (hasRepLoop && currentRep < reps) {
            if (restBetweenRepsSeconds > 0) {
              setPhase("rep_rest");
              pendingVoiceCueRef.current = "rep_rest";
              setTransitionId((id) => id + 1);
              startCountdown(restBetweenRepsSeconds);
              return;
            }
            // No rep rest — next rep immediately
            setCurrentRep((r) => r + 1);
            pendingVoiceCueRef.current = "work";
            setTransitionId((id) => id + 1);
            startCountdown(workSeconds);
            return;
          }
          // End of set
          onSetChangeRef.current?.(currentSet);
          if (currentSet >= totalSets) {
            setPhase("complete");
            pendingVoiceCueRef.current = "complete";
            setTransitionId((id) => id + 1);
            setSecondsLeft(0);
            return;
          }
          // More sets — go to set rest
          if (restBetweenSetsSeconds > 0) {
            setPhase("set_rest");
            pendingVoiceCueRef.current = "set_rest";
            setTransitionId((id) => id + 1);
            startCountdown(restBetweenSetsSeconds);
            return;
          }
          // No set rest — next set directly (no get_ready between sets)
          setCurrentSet((s) => s + 1);
          setCurrentRep(1);
          setPhase("work");
          pendingVoiceCueRef.current = "work";
          setTransitionId((id) => id + 1);
          if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
          return;
        }

        if (phase === "rep_rest") {
          setCurrentRep((r) => r + 1);
          setPhase("work");
          pendingVoiceCueRef.current = "work";
          setTransitionId((id) => id + 1);
          if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
          return;
        }

        if (phase === "set_rest") {
          setCurrentSet((s) => s + 1);
          setCurrentRep(1);
          setPhase("work");
          pendingVoiceCueRef.current = "work";
          setTransitionId((id) => id + 1);
          if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
          return;
        }

        setSecondsLeft(0);
        return;
      }

      // Normal tick — update display from wall clock
      setSecondsLeft(Math.max(0, Math.ceil(remainingMs / 1000)));
    }, 1000);

    return clearTimer;
  }, [phase, paused, currentSet, currentRep, sets, reps, totalSets, workSeconds, restBetweenRepsSeconds, restBetweenSetsSeconds, isManual, hasRepLoop, hasManualRepLoop, clearTimer, startCountdown]);

  // Immediate recalc when PWA returns to foreground (iOS suspends setInterval in background).
  useEffect(() => {
    function onVisible() {
      if (document.visibilityState !== "visible") return;
      if (phaseRef.current === "idle" || phaseRef.current === "complete") return;
      if (pausedRef.current) return;
      if (phaseRef.current === "work" && isManual) return;
      // Force display update — the next interval tick will handle phase transition if expired
      const remainingMs = phaseEndTimeRef.current - Date.now();
      setSecondsLeft(Math.max(0, Math.ceil(remainingMs / 1000)));
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [isManual]);

  // --- Handlers ---

  async function handleStart() {
    await unlockAudio(); // Unlock audio on iOS (must be inside user gesture)
    if (isManual) {
      setPhase("work");
      setSecondsLeft(0);
      pendingVoiceCueRef.current = "work";
    } else {
      setPhase("get_ready");
      startCountdown(GET_READY_SECONDS);
      pendingVoiceCueRef.current = "get_ready";
    }
    setPaused(false);
    setTransitionId((id) => id + 1);
  }

  /** Handle tap during manual work phase. Routes to rep_rest or set_rest as appropriate. */
  async function handleDoneManual() {
    await unlockAudio(); // Resume audio if suspended

    // B124: manual rep loop — more reps in this set → go to rep_rest
    if (hasManualRepLoop && currentRep < reps) {
      setPhase("rep_rest");
      pendingVoiceCueRef.current = "rep_rest";
      startCountdown(restBetweenRepsSeconds);
      setTransitionId((id) => id + 1);
      return;
    }

    // End of set (all reps done, or no rep loop)
    onSetChangeRef.current?.(currentSet);
    if (currentSet >= totalSets) {
      setPhase("complete");
      pendingVoiceCueRef.current = "complete";
    } else if (restBetweenSetsSeconds > 0) {
      setPhase("set_rest");
      startCountdown(restBetweenSetsSeconds);
      pendingVoiceCueRef.current = "set_rest";
    } else {
      setCurrentSet((s) => s + 1);
      setCurrentRep(1);
      pendingVoiceCueRef.current = "work";
      // Phase stays "work" (manual), no countdown
    }
    setTransitionId((id) => id + 1);
  }

  function handleReset() {
    clearTimer();
    phaseEndTimeRef.current = 0;
    setPhase("idle");
    setCurrentSet(1);
    setCurrentRep(1);
    setSecondsLeft(0);
    setPaused(false);
  }

  function handleCircleTap() {
    if (phase === "work" && isManual) {
      handleDoneManual();
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
      pendingVoiceCueRef.current = "work";
      if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
    } else if (phase === "work") {
      if ((hasRepLoop || hasManualRepLoop) && currentRep < reps) {
        if (restBetweenRepsSeconds > 0) {
          setPhase("rep_rest");
          pendingVoiceCueRef.current = "rep_rest";
          startCountdown(restBetweenRepsSeconds);
        } else {
          setCurrentRep((r) => r + 1);
          pendingVoiceCueRef.current = "work";
          if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
        }
      } else {
        // End of set
        onSetChangeRef.current?.(currentSet);
        if (currentSet >= totalSets) {
          setPhase("complete");
          pendingVoiceCueRef.current = "complete";
          setSecondsLeft(0);
        } else if (restBetweenSetsSeconds > 0) {
          setPhase("set_rest");
          pendingVoiceCueRef.current = "set_rest";
          startCountdown(restBetweenSetsSeconds);
        } else {
          setCurrentSet((s) => s + 1);
          setCurrentRep(1);
          setPhase("work");
          pendingVoiceCueRef.current = "work";
          if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
        }
      }
    } else if (phase === "rep_rest") {
      setCurrentRep((r) => r + 1);
      setPhase("work");
      pendingVoiceCueRef.current = "work";
      if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
    } else if (phase === "set_rest") {
      setCurrentSet((s) => s + 1);
      setCurrentRep(1);
      setPhase("work");
      pendingVoiceCueRef.current = "work";
      if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
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
      startCountdown(totalForPhase);
      if (!wasRunning) setPaused(true);
      return;
    }

    // Go to previous phase
    if (phase === "get_ready") {
      // Can't go further back — just restart
      startCountdown(GET_READY_SECONDS);
    } else if (phase === "work") {
      if (currentRep > 1 && restBetweenRepsSeconds > 0 && (hasRepLoop || hasManualRepLoop)) {
        setCurrentRep((r) => r - 1);
        setPhase("rep_rest");
        startCountdown(restBetweenRepsSeconds);
      } else if (currentSet > 1 && restBetweenSetsSeconds > 0) {
        // Go back to the set rest before this set
        setPhase("set_rest");
        startCountdown(restBetweenSetsSeconds);
      } else if (currentSet === 1 && !isManual) {
        // Go back to initial get_ready
        setPhase("get_ready");
        startCountdown(GET_READY_SECONDS);
      } else {
        // Manual set 1, or set > 1 with no rest — restart current phase
        if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
      }
    } else if (phase === "rep_rest") {
      setPhase("work");
      if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
    } else if (phase === "set_rest") {
      // Go back to work phase (last rep of current set)
      setPhase("work");
      if (isManual) { setSecondsLeft(0); } else { startCountdown(workSeconds); }
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

  // --- Enlarged mode ---
  const [enlarged, setEnlarged] = useState(false);

  // Close enlarged mode on swipe down
  const touchStartY = useRef<number | null>(null);

  function handleEnlargedTouchStart(e: React.TouchEvent) {
    touchStartY.current = e.touches[0].clientY;
  }

  function handleEnlargedTouchEnd(e: React.TouchEvent) {
    if (touchStartY.current === null) return;
    const deltaY = e.changedTouches[0].clientY - touchStartY.current;
    if (deltaY > 80) setEnlarged(false); // swipe down > 80px = close
    touchStartY.current = null;
  }

  // Phase label + color for enlarged mode
  const phaseLabel = (() => {
    switch (phase) {
      case "get_ready": return "GET READY";
      case "work": return isManual ? (hasManualRepLoop ? "DO REP" : "DO SET") : "WORK";
      case "rep_rest": return "HOLD";
      case "set_rest": return "REST";
      case "complete": return "DONE";
      default: return "";
    }
  })();

  const phaseColor = (() => {
    switch (phase) {
      case "get_ready": return "text-sky-500";
      case "work": return "text-orange-500";
      case "rep_rest": return "text-teal-400";
      case "set_rest": return "text-emerald-500";
      case "complete": return "text-green-600";
      default: return "text-muted-foreground";
    }
  })();

  // --- Render ---

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Enlarged overlay */}
      {enlarged && (
        <div
          className="fixed inset-0 z-50 bg-[#0a0a0a] flex flex-col items-center justify-center select-none"
          onTouchStart={handleEnlargedTouchStart}
          onTouchEnd={handleEnlargedTouchEnd}
        >
          {/* Close button */}
          <button
            onClick={() => setEnlarged(false)}
            className="absolute top-4 right-4 flex items-center justify-center w-12 h-12 rounded-lg border border-muted-foreground/40 text-muted-foreground hover:text-foreground hover:border-foreground/50 transition-colors"
            aria-label="Exit enlarged timer"
          >
            <X className="size-6" />
          </button>

          {/* Main tap area for play/pause */}
          <div
            className="flex flex-col items-center justify-center gap-4 w-full flex-1 cursor-pointer"
            onClick={handleCircleTap}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === " " || e.key === "Enter") handleCircleTap();
            }}
            aria-label={paused ? "Resume timer" : "Pause timer"}
          >
            {/* Phase label */}
            <span className={cn("text-lg font-bold uppercase tracking-[0.2em]", phaseColor)}>
              {phaseLabel}
            </span>

            {/* Unilateral side badge — enlarged mode */}
            {unilateral && isActive && currentSide && (
              <div className={cn(
                "flex items-center justify-center rounded-xl px-8 py-2 text-3xl font-black tracking-widest",
                currentSide === "RIGHT"
                  ? "bg-orange-500/15 text-orange-400 border border-orange-500/30"
                  : "bg-sky-500/15 text-sky-400 border border-sky-500/30"
              )}>
                {currentSide}
              </div>
            )}

            {/* Big time display */}
            {phase === "work" && isManual ? (
              <div className="flex flex-col items-center gap-2">
                {hasManualRepLoop ? (
                  <span className="text-[120px] leading-none font-bold tabular-nums">
                    {currentRep}<span className="text-muted-foreground/40">/{reps}</span>
                  </span>
                ) : (
                  <span className="text-[120px] leading-none font-bold tabular-nums">
                    {displaySet}<span className="text-muted-foreground/40">/{sets}</span>
                  </span>
                )}
              </div>
            ) : phase === "complete" ? (
              <CheckCircle2 className="size-32 text-green-600" />
            ) : (
              <span className={cn(
                "text-[120px] leading-none font-bold tabular-nums",
                isCountdown && "animate-pulse"
              )}>
                {formatSeconds(secondsLeft)}
              </span>
            )}

            {/* Set/rep counter */}
            {isActive && (
              <span className="text-lg text-muted-foreground tabular-nums">
                Set {displaySet}/{sets}
                {(hasRepLoop || hasManualRepLoop) && (
                  <> &mdash; Rep {currentRep}/{reps}</>
                )}
              </span>
            )}

            {/* Pause indicator */}
            {paused && isActive && (
              <Pause className="size-10 text-muted-foreground/60 mt-2" />
            )}
          </div>

          {/* Bottom controls */}
          <div className="flex items-center gap-6 pb-8">
            {/* ‹ Back */}
            <button
              onClick={(e) => { e.stopPropagation(); handlePhaseBack(); }}
              className={cn(
                "flex items-center justify-center w-14 h-14 rounded-full border transition-colors",
                isActive
                  ? "border-muted-foreground/30 text-muted-foreground hover:text-foreground hover:border-foreground/50 active:scale-95"
                  : "border-transparent text-transparent cursor-default"
              )}
              disabled={!isActive}
              aria-label="Previous phase"
            >
              <ChevronLeft className="size-8" />
            </button>

            {/* Manual done button */}
            {phase === "work" && isManual && (
              <button
                onClick={(e) => { e.stopPropagation(); handleDoneManual(); }}
                className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-6 py-3 text-base font-medium text-white hover:bg-green-700 transition-colors"
              >
                <CheckCircle2 className="size-5" />
                {hasManualRepLoop ? "Done rep" : "Done set"}
              </button>
            )}

            {/* Reset */}
            {phase !== "idle" && (
              <button
                onClick={(e) => { e.stopPropagation(); handleReset(); setEnlarged(false); }}
                className="inline-flex items-center gap-2 rounded-lg border border-muted-foreground/30 px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:border-foreground/50 transition-colors"
                aria-label="Reset timer"
              >
                <RotateCcw className="size-5" />
                Reset
              </button>
            )}

            {/* › Forward */}
            <button
              onClick={(e) => { e.stopPropagation(); handlePhaseForward(); }}
              className={cn(
                "flex items-center justify-center w-14 h-14 rounded-full border transition-colors",
                isActive
                  ? "border-muted-foreground/30 text-muted-foreground hover:text-foreground hover:border-foreground/50 active:scale-95"
                  : "border-transparent text-transparent cursor-default"
              )}
              disabled={!isActive}
              aria-label="Next phase"
            >
              <ChevronRight className="size-8" />
            </button>
          </div>
        </div>
      )}
      {/* Unilateral side badge */}
      {unilateral && isActive && currentSide && (
        <div className={cn(
          "flex items-center justify-center rounded-lg px-5 py-1.5 text-lg font-bold tracking-widest",
          currentSide === "RIGHT"
            ? "bg-orange-500/15 text-orange-400 border border-orange-500/30"
            : "bg-sky-500/15 text-sky-400 border border-sky-500/30"
        )}>
          {currentSide}
        </div>
      )}

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
              ? (hasManualRepLoop ? "Complete rep" : "Complete set")
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
                {hasManualRepLoop ? (
                  <>
                    <span className="text-2xl font-bold">Rep {currentRep}/{reps}</span>
                    <span className="text-xs text-muted-foreground mt-1">Set {currentSet}/{sets}</span>
                    <span className="text-[10px] text-muted-foreground/60 mt-0.5">
                      Tap when done
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-2xl font-bold">Set {displaySet}</span>
                    <span className="text-xs text-muted-foreground mt-1">
                      {reps > 1 ? `Do ${reps} reps` : "Do your set"}
                    </span>
                    <span className="text-[10px] text-muted-foreground/60 mt-0.5">
                      Tap when done
                    </span>
                  </>
                )}
              </>
            )}

            {phase === "rep_rest" && (
              <>
                <span className={cn("text-3xl font-bold tabular-nums", isCountdown && "animate-pulse")}>
                  {formatSeconds(secondsLeft)}
                </span>
                <span className="text-xs font-semibold uppercase tracking-wider mt-0.5 text-teal-400">
                  Rest
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

      {/* Expand button — visible when timer is active */}
      {isActive && (
        <button
          onClick={() => setEnlarged(true)}
          className="inline-flex items-center gap-1.5 rounded-lg border-2 border-muted-foreground/40 px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:border-foreground/60 transition-colors min-h-[44px] min-w-[44px]"
          aria-label="Expand timer"
        >
          <Maximize2 className="size-5" />
          <span>Expand</span>
        </button>
      )}

      {/* Set/rep counter + controls */}
      <div className="flex flex-col items-center gap-2">
        {isActive && (
          <span className="text-xs text-muted-foreground tabular-nums">
            Set {displaySet} / {sets}
            {(hasRepLoop || hasManualRepLoop) && (
              <> &mdash; Rep {currentRep} / {reps}</>
            )}
          </span>
        )}
        <div className="flex items-center gap-3">
          {phase === "work" && isManual && (
            <button
              onClick={(e) => { e.stopPropagation(); handleDoneManual(); }}
              className="inline-flex items-center gap-1.5 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors"
            >
              <CheckCircle2 className="size-4" />
              {hasManualRepLoop ? "Done rep" : "Done set"}
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
