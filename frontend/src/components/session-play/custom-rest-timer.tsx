"use client";

import { useEffect, useRef, useState } from "react";
import { SkipForward, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { unlockAudio } from "@/lib/audio-unlock";
import { countdownTick, transitionBeep } from "@/lib/beep";




function formatMMSS(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

/**
 * B350 — how far past the target a tick may land and still count as "observed
 * live". The tick runs every 250 ms, so in the foreground the target is crossed
 * within a second. Anything past this margin means the interval was suspended
 * (screen off / PWA backgrounded) and the rest ended with nobody watching, so
 * the athlete taps instead — same contract as the guided timer's RESUME_GAP_MS.
 */
const AUTO_ADVANCE_GRACE_S = 2;

export type RestColor = "green" | "yellow" | "red";

export function colorForRatio(ratio: number): RestColor {
  if (ratio <= 1.0) return "green";
  if (ratio <= 1.2) return "yellow";
  return "red";
}

interface CustomRestTimerProps {
  targetSeconds: number;
  nextLabel: string;
  onComplete: () => void;
  onSkip: () => void;
  /**
   * B350: true when the next bout is TIMED work (a plank, a hang). Then the
   * rest starts it on its own the moment it ends, because the clock is the
   * exercise and a tap per set defeats the timer. Rep-based work leaves this
   * false: only the athlete knows when that set is done.
   */
  autoAdvance?: boolean;
}

export function CustomRestTimer({
  targetSeconds,
  nextLabel,
  onComplete,
  onSkip,
  autoAdvance = false,
}: CustomRestTimerProps) {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number>(0);
  const reachedTargetRef = useRef(false);
  const lastBeepSecRef = useRef<number>(-1);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // The tick effect is keyed on targetSeconds alone, so it must read these
  // through refs rather than closing over the render that started it.
  const onCompleteRef = useRef(onComplete);
  const autoAdvanceRef = useRef(autoAdvance);
  useEffect(() => { onCompleteRef.current = onComplete; }, [onComplete]);
  useEffect(() => { autoAdvanceRef.current = autoAdvance; }, [autoAdvance]);

  useEffect(() => {
    // Best-effort unlock in case the user hadn't interacted yet since mount.
    unlockAudio();
    startRef.current = Date.now();
    reachedTargetRef.current = false;
    lastBeepSecRef.current = -1;

    intervalRef.current = setInterval(() => {
      const e = Math.floor((Date.now() - startRef.current) / 1000);
      setElapsed(e);

      // Countdown ticks at 3 / 2 / 1 seconds before target
      const remaining = targetSeconds - e;
      if (
        (remaining === 3 || remaining === 2 || remaining === 1) &&
        lastBeepSecRef.current !== remaining
      ) {
        lastBeepSecRef.current = remaining;
        countdownTick();
      }

      if (!reachedTargetRef.current && e >= targetSeconds) {
        reachedTargetRef.current = true;
        transitionBeep();
        try {
          (navigator as Navigator & { vibrate?: (p: number[]) => boolean }).vibrate?.([200, 100, 200]);
        } catch {
          /* noop */
        }
        // B350: hands-free only when the rest ended under our eyes.
        if (
          autoAdvanceRef.current &&
          e - targetSeconds <= AUTO_ADVANCE_GRACE_S &&
          document.visibilityState === "visible"
        ) {
          onCompleteRef.current();
        }
      }
    }, 250);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [targetSeconds]);

  // iOS visibility resync
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);

  const ratio = targetSeconds > 0 ? elapsed / targetSeconds : 0;
  const color = colorForRatio(ratio);
  const colorClass =
    color === "green"
      ? "text-emerald-500"
      : color === "yellow"
        ? "text-yellow-400"
        : "text-red-500";
  const ringClass =
    color === "green"
      ? "bg-emerald-500/10 border-emerald-500/40"
      : color === "yellow"
        ? "bg-yellow-500/10 border-yellow-400/40"
        : "bg-red-500/10 border-red-500/40";

  const remaining = Math.max(0, targetSeconds - elapsed);
  const display =
    elapsed < targetSeconds ? formatMMSS(remaining) : `+${formatMMSS(elapsed - targetSeconds)}`;

  const atOrPastTarget = elapsed >= targetSeconds;

  return (
    <div className="flex flex-col items-center gap-6 py-8">
      <p className="text-sm uppercase tracking-wider text-muted-foreground">Rest</p>

      <div
        className={cn(
          "flex items-center justify-center w-60 h-60 rounded-full border-2 transition-colors",
          ringClass,
        )}
      >
        <span className={cn("text-6xl font-bold tabular-nums", colorClass)}>{display}</span>
      </div>

      <p className="text-sm text-muted-foreground text-center max-w-xs">
        Next: <span className="font-medium text-foreground">{nextLabel}</span>
      </p>

      <div className="flex gap-3">
        {atOrPastTarget ? (
          <Button
            size="lg"
            onClick={onComplete}
            className="gap-1.5 bg-primary hover:bg-primary/90"
          >
            <ArrowRight className="size-4" />
            Start next
          </Button>
        ) : (
          <Button size="lg" variant="outline" onClick={onSkip} className="gap-1.5">
            <SkipForward className="size-4" />
            Skip rest
          </Button>
        )}
      </div>
    </div>
  );
}
