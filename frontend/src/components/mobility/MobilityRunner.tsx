"use client";

// A230 — Mobility & Stretching runner.
// timed_hold: countdown with editable duration, L/R sequencing for unilateral
// entries (10s transition), per-step progress. ux_flow entries reuse the same
// countdown with breath-paced "slow flow" copy.
// untimed_release: guided coaching text + optional open stopwatch, no forced
// countdown — the user taps Done when the release feels complete.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { getAudioContext, unlockAudio } from "@/lib/audio-unlock";
import type { MobilityEntry } from "@/lib/api";

export interface MobilityResult {
  id: string;
  name: string;
  hold_seconds?: number;
}

interface MobilityRunnerProps {
  entry: MobilityEntry;
  onComplete: (result: MobilityResult) => void;
  onExit: () => void;
}

type Phase = "ready" | "prepare" | "hold" | "transition" | "release" | "done";

interface HoldStep {
  side: "left" | "right" | null;
  set: number; // 1-based
}

const PREPARE_SECONDS = 5;

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
  } catch {
    /* silent */
  }
}

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function MobilityRunner({ entry, onComplete, onExit }: MobilityRunnerProps) {
  const pd = entry.prescription_defaults;
  const isRelease = entry.mode === "untimed_release";
  const sets = pd.sets || 1;
  const transitionSeconds = pd.rest_between_reps_seconds ?? 10;

  // Build the hold sequence: per set, L then R for unilateral entries.
  const holdSteps = useMemo<HoldStep[]>(() => {
    const steps: HoldStep[] = [];
    for (let s = 1; s <= sets; s++) {
      if (entry.unilateral) {
        steps.push({ side: "left", set: s });
        steps.push({ side: "right", set: s });
      } else {
        steps.push({ side: null, set: s });
      }
    }
    return steps;
  }, [entry.unilateral, sets]);

  const [phase, setPhase] = useState<Phase>("ready");
  const [holdSeconds, setHoldSeconds] = useState<number>(pd.work_seconds ?? 45);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [elapsed, setElapsed] = useState(0); // release stopwatch
  const [stepIndex, setStepIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pausedRef = useRef(paused);
  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  const clearTimer = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);
  useEffect(() => clearTimer, [clearTimer]);

  const finish = useCallback(() => {
    clearTimer();
    setPhase("done");
    beep(880, 0.3, 0.4);
    onComplete({
      id: entry.id,
      name: entry.name,
      ...(isRelease ? {} : { hold_seconds: holdSeconds }),
    });
  }, [clearTimer, onComplete, entry.id, entry.name, isRelease, holdSeconds]);

  // Countdown driver for prepare/hold/transition phases.
  const runCountdown = useCallback(
    (seconds: number, current: Phase, onDone: () => void) => {
      clearTimer();
      setPhase(current);
      setSecondsLeft(seconds);
      intervalRef.current = setInterval(() => {
        if (pausedRef.current) return;
        setSecondsLeft((prev) => {
          if (prev <= 1) {
            clearTimer();
            onDone();
            return 0;
          }
          if (prev <= 4) beep(660, 0.08, 0.25);
          return prev - 1;
        });
      }, 1000);
    },
    [clearTimer]
  );

  function startStep(index: number) {
    if (index >= holdSteps.length) {
      finish();
      return;
    }
    setStepIndex(index);
    runCountdown(holdSeconds, "hold", () => {
      beep(880, 0.2, 0.4);
      if (index + 1 >= holdSteps.length) {
        finish();
      } else {
        runCountdown(transitionSeconds, "transition", () => startStep(index + 1));
      }
    });
  }

  function handleStart() {
    unlockAudio();
    if (isRelease) {
      clearTimer();
      setPhase("release");
      setElapsed(0);
      intervalRef.current = setInterval(() => {
        if (pausedRef.current) return;
        setElapsed((prev) => prev + 1);
      }, 1000);
      return;
    }
    runCountdown(PREPARE_SECONDS, "prepare", () => startStep(0));
  }

  const currentStep = holdSteps[stepIndex];
  const sideLabel =
    currentStep?.side === "left" ? "Left side" : currentStep?.side === "right" ? "Right side" : null;

  const phaseLabel =
    phase === "prepare"
      ? "Get ready"
      : phase === "transition"
        ? "Switch sides"
        : entry.ux_flow
          ? "Slow flow — keep moving with your breath"
          : sideLabel
            ? sideLabel
            : "Hold";

  const totalSteps = holdSteps.length;
  const stepProgress = `${Math.min(stepIndex + 1, totalSteps)}/${totalSteps}`;

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold">{entry.name}</h2>
        <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
          {isRelease ? (
            <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-sky-400">
              Release
            </span>
          ) : entry.ux_flow ? (
            <span className="rounded-full border border-teal-500/30 bg-teal-500/10 px-2 py-0.5 text-teal-400">
              Slow flow
            </span>
          ) : (
            <span className="rounded-full border border-teal-500/30 bg-teal-500/10 px-2 py-0.5 text-teal-400">
              {holdSeconds}s hold
            </span>
          )}
          {entry.unilateral && <span className="rounded-full border px-2 py-0.5">Per side</span>}
          {sets > 1 && <span className="rounded-full border px-2 py-0.5">{sets} sets</span>}
        </div>
      </div>

      {/* Image / placeholder */}
      {entry.image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`/exercises/mobility/${entry.image}`}
          alt={entry.name}
          className="w-full rounded-xl border object-cover"
        />
      ) : (
        <div className="flex h-36 items-center justify-center rounded-xl border border-dashed bg-card/50 text-4xl">
          🧘
        </div>
      )}

      {/* GATE-2 warning */}
      {entry.warning && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-400">
          ⚠️ {entry.warning}
        </div>
      )}

      {/* READY: description + duration editor */}
      {phase === "ready" && (
        <>
          <p className="text-sm text-muted-foreground leading-relaxed">{entry.description}</p>
          {pd.notes && (
            <div className="rounded-lg border bg-card p-3 text-sm text-muted-foreground">
              {pd.notes}
            </div>
          )}

          {!isRelease && entry.hold_seconds_editable && (
            <div className="flex items-center justify-between rounded-xl border bg-card p-3">
              <span className="text-sm font-medium">Hold duration</span>
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setHoldSeconds((s) => Math.max(10, s - 5))}
                >
                  −5s
                </Button>
                <span className="w-12 text-center font-mono font-semibold">{holdSeconds}s</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setHoldSeconds((s) => Math.min(300, s + 5))}
                >
                  +5s
                </Button>
              </div>
            </div>
          )}

          <Button onClick={handleStart} className="w-full" size="lg">
            {isRelease ? "Start release" : "Start"}
          </Button>
          <Button variant="ghost" onClick={onExit} className="w-full">
            Back
          </Button>
        </>
      )}

      {/* TIMED phases */}
      {(phase === "prepare" || phase === "hold" || phase === "transition") && (
        <div className="flex flex-col items-center gap-4 py-4">
          <div
            className={`text-sm font-semibold uppercase tracking-wider ${
              phase === "transition" ? "text-blue-400" : "text-teal-400"
            }`}
          >
            {phaseLabel}
          </div>
          <div className="font-mono text-7xl font-bold tabular-nums">
            {formatTime(secondsLeft)}
          </div>
          {totalSteps > 1 && phase !== "prepare" && (
            <div className="text-sm text-muted-foreground">
              {entry.unilateral && currentStep
                ? `Set ${currentStep.set}/${sets} · ${stepProgress}`
                : `Set ${stepProgress}`}
            </div>
          )}
          <div className="flex w-full gap-2">
            <Button variant="outline" onClick={() => setPaused((p) => !p)} className="flex-1">
              {paused ? "Resume" : "Pause"}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                clearTimer();
                onExit();
              }}
              className="flex-1"
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* RELEASE: open stopwatch + guided text */}
      {phase === "release" && (
        <div className="flex flex-col items-center gap-4 py-4">
          <div className="text-sm font-semibold uppercase tracking-wider text-sky-400">
            Release — take your time
          </div>
          <div className="font-mono text-6xl font-bold tabular-nums text-muted-foreground">
            {formatTime(elapsed)}
          </div>
          <p className="text-center text-sm text-muted-foreground leading-relaxed">{pd.notes}</p>
          <Button onClick={finish} className="w-full" size="lg">
            Done
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              clearTimer();
              onExit();
            }}
            className="w-full"
          >
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}
