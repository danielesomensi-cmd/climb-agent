"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { TopBar } from "@/components/layout/top-bar";
import { cn } from "@/lib/utils";
import { getAudioContext, unlockAudio } from "@/lib/audio-unlock";
import { speakPhaseTransition } from "@/lib/voice-cues";

// ===========================================================================
// Types & config
// ===========================================================================

interface ParamConfig {
  key: string;
  label: string;
  icon: React.ReactNode;
  default: number;
  min: number;
  max: number;
  step: number;
  unit: "s" | "x";
}

const PARAMS: ParamConfig[] = [
  {
    key: "prepare",
    label: "Prepare",
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 3v4M3 5h4M6 17v4M4 19h4M13 3l2 4 4 2-4 2-2 4-2-4-4-2 4-2 2-4z" />
      </svg>
    ),
    default: 10,
    min: 0,
    max: 60,
    step: 1,
    unit: "s",
  },
  {
    key: "work",
    label: "Work",
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
      </svg>
    ),
    default: 40,
    min: 5,
    max: 300,
    step: 5,
    unit: "s",
  },
  {
    key: "rest",
    label: "Rest",
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 4h20M2 4v8a10 10 0 0020 0V4M6 4v4M10 4v2" />
      </svg>
    ),
    default: 10,
    min: 0,
    max: 120,
    step: 5,
    unit: "s",
  },
  {
    key: "cycles",
    label: "Cycles",
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 1l4 4-4 4" />
        <path d="M3 11V9a4 4 0 014-4h14" />
        <path d="M7 23l-4-4 4-4" />
        <path d="M21 13v2a4 4 0 01-4 4H3" />
      </svg>
    ),
    default: 8,
    min: 1,
    max: 50,
    step: 1,
    unit: "x",
  },
  {
    key: "sets",
    label: "Sets",
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
    default: 1,
    min: 1,
    max: 10,
    step: 1,
    unit: "x",
  },
  {
    key: "rest_between_sets",
    label: "Set rest",
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
    default: 60,
    min: 0,
    max: 300,
    step: 5,
    unit: "s",
  },
  {
    key: "cool_down",
    label: "Cool down",
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2v20M2 12h20M12 2a5 5 0 015 5M12 2a5 5 0 00-5 5M12 22a5 5 0 005-5M12 22a5 5 0 01-5-5M2 12a5 5 0 015-5M2 12a5 5 0 005 5M22 12a5 5 0 00-5-5M22 12a5 5 0 01-5 5" />
      </svg>
    ),
    default: 0,
    min: 0,
    max: 120,
    step: 5,
    unit: "s",
  },
];

// ===========================================================================
// Phase types & colors
// ===========================================================================

type TabataPhase =
  | "idle"
  | "prepare"
  | "work"
  | "rest"
  | "rest_between_sets"
  | "cool_down"
  | "done";

const PHASE_LABEL: Record<TabataPhase, string> = {
  idle: "",
  prepare: "PREPARE",
  work: "WORK",
  rest: "REST",
  rest_between_sets: "SET REST",
  cool_down: "COOL DOWN",
  done: "DONE",
};

// Colors: work = teal/green energico, rest = blue calmo, prepare/cooldown = grey neutro
const PHASE_BG: Record<TabataPhase, string> = {
  idle: "bg-card",
  prepare: "bg-zinc-800/80",
  work: "bg-teal-900/80",
  rest: "bg-blue-900/60",
  rest_between_sets: "bg-blue-900/60",
  cool_down: "bg-zinc-800/80",
  done: "bg-card",
};

const PHASE_RING_COLOR: Record<TabataPhase, string> = {
  idle: "stroke-muted",
  prepare: "stroke-zinc-400",
  work: "stroke-teal-400",
  rest: "stroke-blue-400",
  rest_between_sets: "stroke-blue-400",
  cool_down: "stroke-zinc-400",
  done: "stroke-green-500",
};

const PHASE_TEXT_COLOR: Record<TabataPhase, string> = {
  idle: "text-muted-foreground",
  prepare: "text-zinc-300",
  work: "text-teal-400",
  rest: "text-blue-400",
  rest_between_sets: "text-blue-400",
  cool_down: "text-zinc-300",
  done: "text-green-500",
};

// ===========================================================================
// Audio (reuse pattern from exercise-timer.tsx)
// ===========================================================================

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

// ===========================================================================
// Helpers
// ===========================================================================

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatValue(value: number, unit: "s" | "x"): string {
  if (unit === "s") {
    if (value >= 60) {
      const m = Math.floor(value / 60);
      const s = value % 60;
      return s > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${m}:00`;
    }
    return `${value}s`;
  }
  return `${value}`;
}

// Progress ring constants
const RING_RADIUS = 120;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

// ===========================================================================
// ParamRow
// ===========================================================================

function ParamRow({
  config,
  value,
  onChange,
}: {
  config: ParamConfig;
  value: number;
  onChange: (v: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const speedRef = useRef(0);

  const clamp = useCallback(
    (v: number) => Math.max(config.min, Math.min(config.max, v)),
    [config.min, config.max]
  );

  const startHold = useCallback(
    (direction: 1 | -1) => {
      speedRef.current = 0;
      timeoutRef.current = setTimeout(() => {
        intervalRef.current = setInterval(() => {
          speedRef.current++;
          const step =
            speedRef.current > 20
              ? config.step * 5
              : speedRef.current > 10
              ? config.step * 2
              : config.step;
          onChange(clamp(value + direction * step));
        }, 80);
      }, 400);
    },
    [value, onChange, clamp, config.step]
  );

  const stopHold = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (intervalRef.current) clearInterval(intervalRef.current);
    timeoutRef.current = null;
    intervalRef.current = null;
  }, []);

  useEffect(() => () => stopHold(), [stopHold]);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const handleStartEdit = () => {
    setEditValue(String(value));
    setEditing(true);
  };

  const commitEdit = () => {
    const parsed = parseInt(editValue, 10);
    if (!isNaN(parsed)) onChange(clamp(parsed));
    setEditing(false);
  };

  return (
    <div className="flex items-center gap-3 py-2.5">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        {config.icon}
      </div>
      <span className="min-w-[72px] text-sm font-medium text-foreground">
        {config.label}
      </span>
      <div className="ml-auto flex items-center gap-1">
        <button
          onClick={() => onChange(clamp(value - config.step))}
          onPointerDown={() => startHold(-1)}
          onPointerUp={stopHold}
          onPointerLeave={stopHold}
          onPointerCancel={stopHold}
          disabled={value <= config.min}
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-foreground transition-colors active:bg-muted/70 disabled:opacity-30"
          aria-label={`Decrease ${config.label}`}
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
            <path d="M5 12h14" />
          </svg>
        </button>

        {editing ? (
          <input
            ref={inputRef}
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value.replace(/[^0-9]/g, ""))}
            onBlur={commitEdit}
            onKeyDown={(e) => { if (e.key === "Enter") commitEdit(); }}
            className="h-10 w-16 rounded-lg bg-primary/10 text-center text-base font-bold text-primary outline-none ring-2 ring-primary/30"
          />
        ) : (
          <button
            onClick={handleStartEdit}
            className="flex h-10 min-w-[64px] items-center justify-center rounded-lg bg-card px-2 text-base font-bold tabular-nums text-foreground transition-colors hover:bg-primary/10 hover:text-primary"
          >
            {formatValue(value, config.unit)}
          </button>
        )}

        <button
          onClick={() => onChange(clamp(value + config.step))}
          onPointerDown={() => startHold(1)}
          onPointerUp={stopHold}
          onPointerLeave={stopHold}
          onPointerCancel={stopHold}
          disabled={value >= config.max}
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-foreground transition-colors active:bg-muted/70 disabled:opacity-30"
          aria-label={`Increase ${config.label}`}
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
      </div>
    </div>
  );
}

// ===========================================================================
// Main page
// ===========================================================================

type ParamValues = Record<string, number>;

function getDefaults(): ParamValues {
  const v: ParamValues = {};
  for (const p of PARAMS) v[p.key] = p.default;
  return v;
}

export default function TabataPage() {
  const [values, setValues] = useState<ParamValues>(getDefaults);
  const [mode, setMode] = useState<"setup" | "running" | "done">("setup");

  const update = useCallback((key: string, val: number) => {
    setValues((prev) => ({ ...prev, [key]: val }));
  }, []);

  // Computed totals
  const { prepare, work, rest, cycles, sets, rest_between_sets, cool_down } = values;
  const totalSeconds =
    prepare +
    (work + rest) * cycles * sets +
    rest_between_sets * (sets - 1) +
    cool_down;
  const totalIntervals = cycles * sets * 2;

  // -------------------------------------------------------------------------
  // Timer state
  // -------------------------------------------------------------------------
  const [phase, setPhase] = useState<TabataPhase>("idle");
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [paused, setPaused] = useState(false);
  const [currentCycle, setCurrentCycle] = useState(1);
  const [currentSet, setCurrentSet] = useState(1);
  const [elapsed, setElapsed] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [transitionId, setTransitionId] = useState(0);

  // Refs for wall-clock timer
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const phaseEndTimeRef = useRef(0);
  const secondsLeftRef = useRef(0);
  const startTimeRef = useRef(0);
  const elapsedAtPauseRef = useRef(0);
  const phaseRef = useRef<TabataPhase>("idle");
  const pausedRef = useRef(false);
  const pendingVoiceCueRef = useRef<string | null>(null);
  // Track completed cycles/sets for summary
  const completedCyclesRef = useRef(0);
  const completedSetsRef = useRef(0);

  useEffect(() => { secondsLeftRef.current = secondsLeft; }, [secondsLeft]);
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  useEffect(() => { pausedRef.current = paused; }, [paused]);

  // -------------------------------------------------------------------------
  // Timer helpers
  // -------------------------------------------------------------------------

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

  // Duration of current phase
  const totalForPhase = useCallback((p: TabataPhase) => {
    switch (p) {
      case "prepare": return prepare;
      case "work": return work;
      case "rest": return rest;
      case "rest_between_sets": return rest_between_sets;
      case "cool_down": return cool_down;
      default: return 0;
    }
  }, [prepare, work, rest, rest_between_sets, cool_down]);

  // -------------------------------------------------------------------------
  // Phase transitions
  // -------------------------------------------------------------------------

  // Determine next phase based on current phase + cycle/set counters
  const advancePhase = useCallback(
    (
      curPhase: TabataPhase,
      curCycle: number,
      curSet: number,
    ): { phase: TabataPhase; cycle: number; set: number; duration: number } => {
      if (curPhase === "prepare") {
        return { phase: "work", cycle: curCycle, set: curSet, duration: work };
      }

      if (curPhase === "work") {
        // After work → rest (if rest > 0) or next cycle directly
        if (rest > 0) {
          return { phase: "rest", cycle: curCycle, set: curSet, duration: rest };
        }
        // No rest: check cycle/set progression
        if (curCycle < cycles) {
          return { phase: "work", cycle: curCycle + 1, set: curSet, duration: work };
        }
        // End of cycles for this set
        if (curSet < sets && rest_between_sets > 0) {
          return { phase: "rest_between_sets", cycle: curCycle, set: curSet, duration: rest_between_sets };
        }
        if (curSet < sets) {
          return { phase: "work", cycle: 1, set: curSet + 1, duration: work };
        }
        // All sets done
        if (cool_down > 0) {
          return { phase: "cool_down", cycle: curCycle, set: curSet, duration: cool_down };
        }
        return { phase: "done", cycle: curCycle, set: curSet, duration: 0 };
      }

      if (curPhase === "rest") {
        // After rest → next cycle or end of set
        if (curCycle < cycles) {
          return { phase: "work", cycle: curCycle + 1, set: curSet, duration: work };
        }
        // End of cycles for this set
        if (curSet < sets && rest_between_sets > 0) {
          return { phase: "rest_between_sets", cycle: curCycle, set: curSet, duration: rest_between_sets };
        }
        if (curSet < sets) {
          return { phase: "work", cycle: 1, set: curSet + 1, duration: work };
        }
        if (cool_down > 0) {
          return { phase: "cool_down", cycle: curCycle, set: curSet, duration: cool_down };
        }
        return { phase: "done", cycle: curCycle, set: curSet, duration: 0 };
      }

      if (curPhase === "rest_between_sets") {
        return { phase: "work", cycle: 1, set: curSet + 1, duration: work };
      }

      if (curPhase === "cool_down") {
        return { phase: "done", cycle: curCycle, set: curSet, duration: 0 };
      }

      return { phase: "done", cycle: curCycle, set: curSet, duration: 0 };
    },
    [work, rest, cycles, sets, rest_between_sets, cool_down]
  );

  // -------------------------------------------------------------------------
  // Audio effects
  // -------------------------------------------------------------------------

  // Transition beep + voice
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
      const p = phaseRef.current;
      if (!pausedRef.current && p !== "idle" && p !== "done") {
        countdownTick();
      }
    }
  }, [secondsLeft]);

  // Half-time tick — subtle beep at the halfway point of work/rest phases
  const halfTimeRef = useRef(false);
  useEffect(() => {
    const dur = totalForPhase(phaseRef.current);
    if (dur >= 10 && !pausedRef.current && phaseRef.current !== "idle" && phaseRef.current !== "done") {
      const halfPoint = Math.ceil(dur / 2);
      if (secondsLeft === halfPoint && !halfTimeRef.current) {
        halfTimeRef.current = true;
        beep(550, 0.06, 0.15); // soft, low tick
      } else if (secondsLeft !== halfPoint) {
        halfTimeRef.current = false;
      }
    }
  }, [secondsLeft, totalForPhase]);

  // -------------------------------------------------------------------------
  // Main tick loop (wall-clock)
  // -------------------------------------------------------------------------

  useEffect(() => {
    clearTimer();

    if (phase === "idle" || phase === "done" || paused) return;

    // Recompute end time from remaining
    phaseEndTimeRef.current = Date.now() + secondsLeftRef.current * 1000;

    intervalRef.current = setInterval(() => {
      // Update elapsed
      if (!pausedRef.current && startTimeRef.current > 0) {
        setElapsed(elapsedAtPauseRef.current + Math.floor((Date.now() - startTimeRef.current) / 1000));
      }

      const remainingMs = phaseEndTimeRef.current - Date.now();

      if (remainingMs <= 0) {
        // Phase transition
        const curCycle = currentCycle;
        const curSet = currentSet;

        // Track completions
        if (phaseRef.current === "work") {
          completedCyclesRef.current++;
        }
        if (
          phaseRef.current === "rest_between_sets" ||
          (phaseRef.current === "rest" && curCycle >= cycles) ||
          (phaseRef.current === "work" && rest === 0 && curCycle >= cycles)
        ) {
          completedSetsRef.current++;
        }

        const next = advancePhase(phaseRef.current, curCycle, curSet);

        if (next.phase === "done") {
          // Final set completion
          completedSetsRef.current = sets;
          completedCyclesRef.current = cycles * sets;
          setPhase("done");
          setSecondsLeft(0);
          setMode("done");
          pendingVoiceCueRef.current = "complete";
          setTransitionId((id) => id + 1);
          // Freeze elapsed
          if (startTimeRef.current > 0) {
            elapsedAtPauseRef.current =
              elapsedAtPauseRef.current + Math.floor((Date.now() - startTimeRef.current) / 1000);
          }
          return;
        }

        setPhase(next.phase);
        setCurrentCycle(next.cycle);
        setCurrentSet(next.set);
        startCountdown(next.duration);

        // Voice cue
        if (next.phase === "work") {
          pendingVoiceCueRef.current = "work";
        } else if (next.phase === "rest" || next.phase === "rest_between_sets") {
          pendingVoiceCueRef.current = null; // just beep, no voice for rest
        } else if (next.phase === "cool_down") {
          pendingVoiceCueRef.current = null;
        }
        setTransitionId((id) => id + 1);
        return;
      }

      setSecondsLeft(Math.max(0, Math.ceil(remainingMs / 1000)));
    }, 200);

    return clearTimer;
  }, [phase, paused, currentCycle, currentSet, cycles, sets, rest, advancePhase, clearTimer, startCountdown]);

  // iOS visibility change handler
  useEffect(() => {
    function onVisible() {
      if (document.visibilityState !== "visible") return;
      if (phaseRef.current === "idle" || phaseRef.current === "done") return;
      if (pausedRef.current) return;
      const remainingMs = phaseEndTimeRef.current - Date.now();
      setSecondsLeft(Math.max(0, Math.ceil(remainingMs / 1000)));
      // Update elapsed
      if (startTimeRef.current > 0) {
        setElapsed(elapsedAtPauseRef.current + Math.floor((Date.now() - startTimeRef.current) / 1000));
      }
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  async function handleStart() {
    await unlockAudio();
    completedCyclesRef.current = 0;
    completedSetsRef.current = 0;
    setCurrentCycle(1);
    setCurrentSet(1);
    setElapsed(0);
    elapsedAtPauseRef.current = 0;
    startTimeRef.current = Date.now();
    setPaused(false);
    setMode("running");

    if (prepare > 0) {
      setPhase("prepare");
      startCountdown(prepare);
      pendingVoiceCueRef.current = "get_ready";
    } else {
      setPhase("work");
      startCountdown(work);
      pendingVoiceCueRef.current = "work";
    }
    setTransitionId((id) => id + 1);
  }

  function handlePauseToggle() {
    if (phase === "idle" || phase === "done") return;
    if (paused) {
      // Resume
      startTimeRef.current = Date.now();
      phaseEndTimeRef.current = Date.now() + secondsLeftRef.current * 1000;
      setPaused(false);
    } else {
      // Pause — freeze elapsed
      elapsedAtPauseRef.current =
        elapsedAtPauseRef.current + Math.floor((Date.now() - startTimeRef.current) / 1000);
      startTimeRef.current = 0;
      setPaused(true);
    }
  }

  function handleStop() {
    clearTimer();
    // Freeze elapsed
    if (startTimeRef.current > 0) {
      elapsedAtPauseRef.current =
        elapsedAtPauseRef.current + Math.floor((Date.now() - startTimeRef.current) / 1000);
    }
    setElapsed(elapsedAtPauseRef.current);
    setPhase("done");
    setMode("done");
    setSecondsLeft(0);
    setPaused(false);
    setExpanded(false);
  }

  function handleRestart() {
    handleStart();
  }

  function handleBackToSetup() {
    clearTimer();
    setPhase("idle");
    setMode("setup");
    setSecondsLeft(0);
    setPaused(false);
    setElapsed(0);
    setExpanded(false);
    elapsedAtPauseRef.current = 0;
    startTimeRef.current = 0;
    completedCyclesRef.current = 0;
    completedSetsRef.current = 0;
  }

  // -------------------------------------------------------------------------
  // Progress ring
  // -------------------------------------------------------------------------

  const phaseDuration = totalForPhase(phase);

  // ---- Smooth progress ring via requestAnimationFrame ----
  const [smoothProgress, setSmoothProgress] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    // When idle/done or paused, snap to discrete progress
    if (phase === "idle" || phase === "done" || paused) {
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

  // Remaining total
  const totalRemaining = (() => {
    if (phase === "done") return 0;
    // Approximate: current phase remaining + remaining phases
    let rem = secondsLeft;
    // Remaining cycles in current set (after current cycle)
    const cyclesLeftInSet = cycles - currentCycle;
    if (phase === "work") {
      // Still have rest for this cycle (if rest > 0)
      if (rest > 0) rem += rest;
      rem += cyclesLeftInSet * (work + rest);
    } else if (phase === "rest") {
      rem += cyclesLeftInSet * (work + rest);
    } else if (phase === "prepare") {
      rem += cycles * (work + rest) * sets + rest_between_sets * (sets - 1) + cool_down;
      return rem;
    }
    // Remaining sets after current
    const setsLeft = sets - currentSet;
    if (setsLeft > 0) {
      rem += rest_between_sets; // rest before next set
      rem += (setsLeft - 1) * rest_between_sets;
      rem += setsLeft * cycles * (work + rest);
    }
    rem += cool_down;
    return Math.max(0, rem);
  })();

  // -------------------------------------------------------------------------
  // Expand mode
  // -------------------------------------------------------------------------

  const touchStartY = useRef<number | null>(null);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  // --- DONE screen ---
  if (mode === "done") {
    return (
      <>
        <TopBar title="Tabata" />
        <main className="mx-auto flex max-w-2xl flex-col items-center justify-center px-4 py-12 pb-24">
          <div className="flex flex-col items-center gap-6 text-center">
            {/* Checkmark circle */}
            <div className="flex h-24 w-24 items-center justify-center rounded-full bg-green-500/20">
              <svg className="h-12 w-12 text-green-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </div>

            <h2 className="text-3xl font-bold">Done!</h2>

            <div className="grid grid-cols-2 gap-4 w-full max-w-xs">
              <div className="rounded-xl bg-card border border-border p-4 text-center">
                <div className="text-2xl font-bold tabular-nums">{formatTime(elapsed)}</div>
                <div className="text-xs text-muted-foreground mt-1">Total time</div>
              </div>
              <div className="rounded-xl bg-card border border-border p-4 text-center">
                <div className="text-2xl font-bold tabular-nums">{completedCyclesRef.current}/{cycles * sets}</div>
                <div className="text-xs text-muted-foreground mt-1">Cycles</div>
              </div>
              <div className="rounded-xl bg-card border border-border p-4 text-center">
                <div className="text-2xl font-bold tabular-nums">{completedSetsRef.current}/{sets}</div>
                <div className="text-xs text-muted-foreground mt-1">Sets</div>
              </div>
              <div className="rounded-xl bg-card border border-border p-4 text-center">
                <div className="text-2xl font-bold tabular-nums">{totalIntervals}</div>
                <div className="text-xs text-muted-foreground mt-1">Intervals</div>
              </div>
            </div>

            <div className="flex gap-3 mt-4 w-full max-w-xs">
              <button
                onClick={handleRestart}
                className="flex-1 flex h-12 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-bold text-primary-foreground transition-all active:scale-[0.98]"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 4v6h6" />
                  <path d="M3.51 15a9 9 0 102.13-9.36L1 10" />
                </svg>
                Restart
              </button>
              <button
                onClick={handleBackToSetup}
                className="flex-1 flex h-12 items-center justify-center gap-2 rounded-xl border border-border bg-card text-sm font-bold text-foreground transition-all active:scale-[0.98]"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                Setup
              </button>
            </div>
          </div>
        </main>
      </>
    );
  }

  // --- RUNNING screen ---
  if (mode === "running") {
    const isActive = phase !== "idle" && phase !== "done";

    return (
      <>
        {/* Expanded overlay */}
        {expanded && (
          <div
            className="fixed inset-0 z-50 flex flex-col items-center justify-center select-none bg-[#0a0a0a]"
            onTouchStart={(e) => { touchStartY.current = e.touches[0].clientY; }}
            onTouchEnd={(e) => {
              if (touchStartY.current !== null) {
                if (e.changedTouches[0].clientY - touchStartY.current > 80) setExpanded(false);
                touchStartY.current = null;
              }
            }}
          >
            {/* Close */}
            <button
              onClick={() => setExpanded(false)}
              className="absolute top-4 right-4 flex h-12 w-12 items-center justify-center rounded-lg border border-muted-foreground/40 text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Exit expanded timer"
            >
              <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>

            {/* Tap area */}
            <div
              className="flex flex-1 w-full flex-col items-center justify-center gap-4 cursor-pointer"
              onClick={handlePauseToggle}
            >
              {/* Phase label */}
              <span className={cn("text-lg font-bold uppercase tracking-[0.2em]", PHASE_TEXT_COLOR[phase])}>
                {PHASE_LABEL[phase]}
              </span>

              {/* Big countdown */}
              <span className={cn(
                "text-[120px] leading-none font-bold tabular-nums transition-transform duration-150",
                secondsLeft <= 3 && secondsLeft > 0 && "scale-110"
              )}>
                {formatTime(secondsLeft)}
              </span>

              {/* Cycle/set — large in expand too */}
              <div className="flex items-center gap-6 tabular-nums mt-2">
                <div className="flex flex-col items-center">
                  <div className="leading-none">
                    <span className="text-4xl font-bold">{currentCycle}</span>
                    <span className="text-2xl font-bold text-muted-foreground/50">/{cycles}</span>
                  </div>
                  <span className="text-xs uppercase tracking-[0.15em] text-muted-foreground mt-1">Cycle</span>
                </div>
                {sets > 1 && (
                  <div className="flex flex-col items-center">
                    <div className="leading-none">
                      <span className="text-4xl font-bold">{currentSet}</span>
                      <span className="text-2xl font-bold text-muted-foreground/50">/{sets}</span>
                    </div>
                    <span className="text-xs uppercase tracking-[0.15em] text-muted-foreground mt-1">Set</span>
                  </div>
                )}
              </div>

              {paused && (
                <div className="mt-2 rounded-lg bg-white/10 px-6 py-2 text-lg font-bold text-white/70">
                  PAUSED
                </div>
              )}
            </div>

            {/* Bottom controls */}
            <div className="flex items-center gap-4 pb-8">
              <button
                onClick={(e) => { e.stopPropagation(); handlePauseToggle(); }}
                className="flex h-14 w-14 items-center justify-center rounded-full border border-muted-foreground/30 text-muted-foreground hover:text-foreground transition-colors"
              >
                {paused ? (
                  <svg className="h-7 w-7" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
                ) : (
                  <svg className="h-7 w-7" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1" /><rect x="14" y="4" width="4" height="16" rx="1" /></svg>
                )}
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); handleStop(); }}
                className="flex h-14 w-14 items-center justify-center rounded-full border border-red-500/50 text-red-400 hover:text-red-300 hover:border-red-400 transition-colors"
              >
                <svg className="h-7 w-7" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2" /></svg>
              </button>
            </div>
          </div>
        )}

        <div className={cn(
          "fixed inset-0 flex flex-col transition-colors duration-500",
          PHASE_BG[phase]
        )}>
          {/* Top bar — phase label left, compact counter right */}
          <div className="flex items-center justify-between px-4 pt-4 pb-1">
            <span className={cn("text-sm font-bold uppercase tracking-[0.2em]", PHASE_TEXT_COLOR[phase])}>
              {PHASE_LABEL[phase]}
            </span>
            <span className="text-sm text-muted-foreground tabular-nums">
              Cycle {currentCycle}/{cycles}{sets > 1 && <> &middot; Set {currentSet}/{sets}</>}
            </span>
          </div>

          {/* Center: progress ring + countdown */}
          <div
            className="flex flex-1 flex-col items-center justify-center cursor-pointer"
            onClick={handlePauseToggle}
          >
            <div className="relative w-72 h-72">
              {/* SVG ring */}
              <svg viewBox="0 0 260 260" className="w-full h-full -rotate-90">
                {/* Track */}
                <circle
                  cx="130" cy="130" r={RING_RADIUS}
                  fill="none"
                  strokeWidth={10}
                  className="stroke-white/10"
                />
                {/* Half-time marker — small tick at 50% */}
                <line
                  x1="130" y1={130 - RING_RADIUS + 14}
                  x2="130" y2={130 - RING_RADIUS - 2}
                  className="stroke-white/20"
                  strokeWidth={2}
                  strokeLinecap="round"
                />
                {/* Progress — no CSS transition, driven by rAF */}
                <circle
                  cx="130" cy="130" r={RING_RADIUS}
                  fill="none"
                  strokeWidth={10}
                  strokeLinecap="round"
                  strokeDasharray={RING_CIRCUMFERENCE}
                  strokeDashoffset={dashOffset}
                  className={PHASE_RING_COLOR[phase]}
                />
              </svg>

              {/* Center content */}
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={cn(
                  "text-7xl font-bold tabular-nums leading-none transition-transform duration-150",
                  secondsLeft <= 3 && secondsLeft > 0 && "scale-110"
                )}>
                  {formatTime(secondsLeft)}
                </span>
              </div>
            </div>

            {/* Cycle / Set counter — extra large, below ring */}
            <div className="mt-5 flex items-center gap-8 tabular-nums">
              <div className="flex flex-col items-center">
                <div className="leading-none">
                  <span className="text-5xl font-bold">{currentCycle}</span>
                  <span className="text-3xl font-bold text-muted-foreground/50">/{cycles}</span>
                </div>
                <span className="text-xs uppercase tracking-[0.15em] text-muted-foreground mt-1">Cycle</span>
              </div>
              {sets > 1 && (
                <div className="flex flex-col items-center">
                  <div className="leading-none">
                    <span className="text-5xl font-bold">{currentSet}</span>
                    <span className="text-3xl font-bold text-muted-foreground/50">/{sets}</span>
                  </div>
                  <span className="text-xs uppercase tracking-[0.15em] text-muted-foreground mt-1">Set</span>
                </div>
              )}
            </div>

            {/* Pause overlay */}
            {paused && (
              <div className="mt-4 rounded-xl bg-white/10 px-8 py-3 backdrop-blur-sm">
                <span className="text-xl font-bold text-white/80 tracking-wider">PAUSED</span>
              </div>
            )}
          </div>

          {/* Bottom: elapsed/remaining + next up + controls */}
          <div className="pb-28 px-4">
            {/* Elapsed / Remaining + Next up */}
            <div className="flex flex-col items-center gap-2 mb-5">
              <div className="flex justify-center gap-8 text-sm text-muted-foreground tabular-nums">
                <div className="flex flex-col items-center">
                  <span className="text-xs uppercase tracking-wider mb-0.5">Elapsed</span>
                  <span className="font-semibold text-foreground">{formatTime(elapsed)}</span>
                </div>
                <div className="flex flex-col items-center">
                  <span className="text-xs uppercase tracking-wider mb-0.5">Remaining</span>
                  <span className="font-semibold text-foreground">{formatTime(totalRemaining)}</span>
                </div>
              </div>
              {/* Next up preview */}
              {phase !== "done" && (() => {
                const next = advancePhase(phase, currentCycle, currentSet);
                if (next.phase === "done") return <span className="text-xs text-muted-foreground/60">Last interval</span>;
                return (
                  <span className="text-xs text-muted-foreground/60 tabular-nums">
                    Next: {PHASE_LABEL[next.phase]} {next.duration > 0 && formatTime(next.duration)}
                  </span>
                );
              })()}
            </div>

            {/* Controls */}
            <div className="flex items-center justify-center gap-4">
              {/* Pause */}
              <button
                onClick={handlePauseToggle}
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

              {/* Expand */}
              <button
                onClick={() => setExpanded(true)}
                className="flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-card/50 text-muted-foreground hover:text-foreground transition-colors"
                aria-label="Expand timer"
              >
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
                </svg>
              </button>

              {/* Stop */}
              <button
                onClick={handleStop}
                className="flex h-14 w-14 items-center justify-center rounded-2xl border border-red-500/30 bg-red-500/10 text-red-400 hover:text-red-300 transition-colors"
                aria-label="Stop timer"
              >
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2" /></svg>
              </button>
            </div>
          </div>
        </div>
      </>
    );
  }

  // --- SETUP screen ---
  return (
    <>
      <TopBar title="Tabata" />
      <main className="mx-auto max-w-2xl px-4 pb-8 pt-2">
        {/* Summary header */}
        <div className="mb-4 flex flex-col items-center gap-1 py-4">
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold tabular-nums tracking-tight text-foreground">
              {formatTime(totalSeconds)}
            </span>
          </div>
          <span className="text-sm text-muted-foreground">
            {totalIntervals} intervals
          </span>
        </div>

        {/* Parameter list */}
        <div className="rounded-2xl border border-border bg-card/50 px-3">
          {PARAMS.map((p, i) => (
            <div key={p.key}>
              {i > 0 && <div className="border-t border-border/50" />}
              <ParamRow
                config={p}
                value={values[p.key]}
                onChange={(v) => update(p.key, v)}
              />
            </div>
          ))}
        </div>

        {/* Start button */}
        <button
          onClick={handleStart}
          className="mt-6 flex h-14 w-full items-center justify-center gap-3 rounded-2xl bg-primary text-lg font-bold text-primary-foreground shadow-lg shadow-primary/25 transition-all active:scale-[0.98]"
        >
          <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z" />
          </svg>
          START
        </button>
      </main>
    </>
  );
}
