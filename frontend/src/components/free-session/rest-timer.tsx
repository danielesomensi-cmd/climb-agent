"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { SkipForward, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { speakPhaseTransition, isVoiceCuesEnabled } from "@/lib/voice-cues";
import { unlockAudio } from "@/lib/audio-unlock";
import { countdownTick, transitionBeep } from "@/lib/beep";
import { completeFeedback } from "@/lib/haptics";
import { useWakeLock } from "@/lib/hooks/use-wake-lock";

interface RestTimerProps {
  initialSeconds: number;
  autoStart?: boolean;
  onComplete?: () => void;
}

export function RestTimer({ initialSeconds, autoStart = false, onComplete }: RestTimerProps) {
  const [seconds, setSeconds] = useState(initialSeconds);
  const [isRunning, setIsRunning] = useState(autoStart);
  const [isVisible, setIsVisible] = useState(autoStart);
  const endTimeRef = useRef<number | null>(null);
  // A286 — dedup del tick 3-2-1: l'intervallo gira a 250 ms, senza questo
  // ogni secondo suonerebbe quattro volte.
  const lastTickedSecRef = useRef<number>(-1);

  // A286 — lo schermo non si spegne mentre il riposo scorre.
  useWakeLock(isRunning);

  // Wall-clock based timer (iOS PWA safe)
  useEffect(() => {
    if (!isRunning) return;

    if (endTimeRef.current === null) {
      endTimeRef.current = Date.now() + seconds * 1000;
    }

    const tick = () => {
      const remaining = Math.max(0, Math.ceil((endTimeRef.current! - Date.now()) / 1000));
      setSeconds(remaining);

      // A286 — chi si riposa non guarda lo schermo: stesso countdown sonoro
      // degli altri quattro timer (beep.ts) più un haptic a fine riposo.
      if (remaining >= 1 && remaining <= 3 && lastTickedSecRef.current !== remaining) {
        lastTickedSecRef.current = remaining;
        countdownTick();
      }

      if (remaining <= 0) {
        setIsRunning(false);
        endTimeRef.current = null;
        lastTickedSecRef.current = -1;
        transitionBeep();
        completeFeedback();
        if (isVoiceCuesEnabled()) speakPhaseTransition("work");
        onComplete?.();
      }
    };

    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, [isRunning, onComplete, seconds]);

  const start = useCallback(() => {
    // Deve stare dentro il gesto utente, altrimenti su iOS l'AudioContext
    // resta sospeso e il beep di fine riposo non esce.
    void unlockAudio();
    setSeconds(initialSeconds);
    endTimeRef.current = Date.now() + initialSeconds * 1000;
    lastTickedSecRef.current = -1;
    setIsRunning(true);
    setIsVisible(true);
  }, [initialSeconds]);

  const skip = useCallback(() => {
    setIsRunning(false);
    setSeconds(0);
    endTimeRef.current = null;
    lastTickedSecRef.current = -1;
    setIsVisible(false);
    onComplete?.();
  }, [onComplete]);

  const addMinute = useCallback(() => {
    setSeconds((s) => s + 60);
    if (endTimeRef.current) endTimeRef.current += 60000;
  }, []);

  // Reset when a new timer starts via autoStart
  useEffect(() => {
    if (autoStart) {
      void unlockAudio();
      setSeconds(initialSeconds);
      endTimeRef.current = Date.now() + initialSeconds * 1000;
      lastTickedSecRef.current = -1;
      setIsRunning(true);
      setIsVisible(true);
    }
  }, [autoStart, initialSeconds]);

  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const progress = initialSeconds > 0 ? ((initialSeconds - seconds) / initialSeconds) * 100 : 0;

  if (!isVisible && !autoStart) {
    return (
      <Button variant="outline" onClick={start} className="w-full">
        Start rest timer ({Math.floor(initialSeconds / 60)}:{String(initialSeconds % 60).padStart(2, "0")})
      </Button>
    );
  }

  if (!isVisible) return null;

  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">REST</span>
        <span className="text-2xl font-bold tabular-nums">
          {minutes}:{String(secs).padStart(2, "0")}
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-3 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-info transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="flex gap-2">
        <Button variant="ghost" size="sm" onClick={skip} className="flex-1 gap-1">
          <SkipForward className="size-4" />
          Skip
        </Button>
        <Button variant="ghost" size="sm" onClick={addMinute} className="flex-1 gap-1">
          <Plus className="size-4" />
          1 min
        </Button>
      </div>
    </div>
  );
}
