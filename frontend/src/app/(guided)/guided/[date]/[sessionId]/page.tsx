"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SessionTimer } from "@/components/guided/session-timer";
import { GuidedProgressBar } from "@/components/guided/guided-progress-bar";
import { GuidedExerciseStep } from "@/components/guided/guided-exercise-step";
import { GuidedSummary } from "@/components/guided/guided-summary";
import { applyEvents, postFeedback, getWeek, getState } from "@/lib/api";
import { unlockAudio, getAudioContext } from "@/lib/audio-unlock";
import type { GuidedSessionState, GuidedExercise, WeekPlan } from "@/lib/types";

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

function getStorageKey(date: string, sessionId: string): string {
  let userId = "";
  if (typeof window !== "undefined") {
    userId = localStorage.getItem("climb_user_id") ?? "";
  }
  return `guided_session_${userId}_${date}_${sessionId}`;
}

function loadState(date: string, sessionId: string): GuidedSessionState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(getStorageKey(date, sessionId));
    return raw ? (JSON.parse(raw) as GuidedSessionState) : null;
  } catch {
    return null;
  }
}

function saveState(state: GuidedSessionState) {
  if (typeof window === "undefined") return;
  const key = getStorageKey(state.date, state.sessionId);
  localStorage.setItem(key, JSON.stringify(state));
}

function removeState(date: string, sessionId: string) {
  if (typeof window === "undefined") return;
  localStorage.removeItem(getStorageKey(date, sessionId));
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const WARMUP_CATEGORIES = ["warmup_general", "warmup_specific"];

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

export default function GuidedSessionPage() {
  const params = useParams();
  const router = useRouter();
  const date = params.date as string;
  const sessionId = params.sessionId as string;

  const [state, setState] = useState<GuidedSessionState | null>(null);
  const [showSummary, setShowSummary] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [resumed, setResumed] = useState(false);

  // Ref to always have latest state for the beforeunload handler
  const stateRef = useRef(state);
  useEffect(() => { stateRef.current = state; }, [state]);

  // Load state from localStorage on mount
  useEffect(() => {
    const saved = loadState(date, sessionId);
    if (saved) {
      setState(saved);
      // Show resume banner if there's actual progress (not a fresh session)
      const hasProgress =
        saved.exercises.some((ex) => ex.status !== "pending") ||
        saved.currentIndex > 0;
      if (hasProgress) setResumed(true);
      // If all exercises are done/skipped, show summary
      const allDone = saved.exercises.every((ex) => ex.status !== "pending");
      if (allDone) setShowSummary(true);
      // Fetch bodyweight for test sessions (needed for total load auto-computation)
      if (saved.isTestSession && !saved.bodyweightKg) {
        getState().then((stateData) => {
          const body = (stateData.assessment as Record<string, unknown> | undefined)?.body as Record<string, number> | undefined;
          const bw = body?.weight_kg;
          if (bw) {
            setState((prev) => prev ? { ...prev, bodyweightKg: bw } : prev);
          }
        }).catch(() => {});
      }
    } else {
      // No saved state — redirect back to today
      router.replace(`/today?date=${date}`);
    }
  }, [date, sessionId, router]);

  // Auto-dismiss resume banner after 4 seconds
  useEffect(() => {
    if (!resumed) return;
    const timer = setTimeout(() => setResumed(false), 4000);
    return () => clearTimeout(timer);
  }, [resumed]);

  // Persist state to localStorage on every change
  useEffect(() => {
    if (state) saveState(state);
  }, [state]);

  // Warn on navigation away (beforeunload)
  useEffect(() => {
    function onBeforeUnload(e: BeforeUnloadEvent) {
      if (stateRef.current && !stateRef.current.submitStatus) {
        e.preventDefault();
      }
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  // Unlock audio on first touch — iOS Safari requires user gesture to start AudioContext
  useEffect(() => {
    function onFirstTouch() {
      unlockAudio();
      window.removeEventListener("touchstart", onFirstTouch);
    }
    window.addEventListener("touchstart", onFirstTouch, { once: true });
    return () => window.removeEventListener("touchstart", onFirstTouch);
  }, []);

  // Resume AudioContext when PWA returns to foreground (iOS suspends on background)
  useEffect(() => {
    async function onVisibilityChange() {
      if (document.visibilityState === "visible") {
        try {
          const ctx = getAudioContext();
          if (ctx.state === "suspended") await ctx.resume();
          // Re-play silent buffer to re-unlock iOS audio gate after background
          const buffer = ctx.createBuffer(1, 1, 22050);
          const source = ctx.createBufferSource();
          source.buffer = buffer;
          source.connect(ctx.destination);
          source.start(0);
        } catch { /* silent */ }
      }
    }
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, []);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const updateExercise = useCallback(
    (index: number, updates: Partial<GuidedExercise>) => {
      setState((prev) => {
        if (!prev) return prev;
        const exercises = [...prev.exercises];
        exercises[index] = { ...exercises[index], ...updates };
        return { ...prev, exercises };
      });
    },
    []
  );

  const handleDone = useCallback(
    (feedbackLabel: string, usedLoad?: number, usedGrade?: string, usedTotalLoad?: number, testMeasurement?: number) => {
      if (!state) return;
      const idx = state.currentIndex;

      updateExercise(idx, {
        status: "done",
        feedbackLabel,
        usedLoadKg: usedLoad,
        usedTotalLoadKg: usedTotalLoad,
        usedGrade,
        testMeasurement,
      });

      // Advance to next exercise or show summary
      const nextIdx = idx + 1;
      if (nextIdx >= state.exercises.length) {
        setState((prev) => prev ? { ...prev, currentIndex: idx } : prev);
        setShowSummary(true);
      } else {
        setState((prev) => prev ? { ...prev, currentIndex: nextIdx } : prev);
      }
    },
    [state, updateExercise]
  );

  const handleSkip = useCallback(() => {
    if (!state) return;
    const idx = state.currentIndex;

    updateExercise(idx, { status: "skipped", feedbackLabel: "ok" });

    const nextIdx = idx + 1;
    if (nextIdx >= state.exercises.length) {
      setState((prev) => prev ? { ...prev, currentIndex: idx } : prev);
      setShowSummary(true);
    } else {
      setState((prev) => prev ? { ...prev, currentIndex: nextIdx } : prev);
    }
  }, [state, updateExercise]);

  const handleNavigate = useCallback(
    (index: number) => {
      if (!state) return;
      setShowSummary(false);
      setState((prev) => prev ? { ...prev, currentIndex: index } : prev);
    },
    [state]
  );

  const handleFinishEarly = useCallback(() => {
    setShowSummary(true);
  }, []);

  const handleMarkRemainingOk = useCallback(() => {
    setState((prev) => {
      if (!prev) return prev;
      const exercises = prev.exercises.map((ex) =>
        ex.status === "pending" ? { ...ex, status: "done" as const, feedbackLabel: "ok" } : ex
      );
      return { ...prev, exercises };
    });
  }, []);

  const handleSkipRemaining = useCallback(() => {
    setState((prev) => {
      if (!prev) return prev;
      const exercises = prev.exercises.map((ex) => {
        if (ex.status !== "pending") return ex;
        // Auto-skip warmups silently
        if (WARMUP_CATEGORIES.includes(ex.category)) {
          return { ...ex, status: "skipped" as const };
        }
        return { ...ex, status: "skipped" as const };
      });
      return { ...prev, exercises };
    });
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!state) return;
    setSubmitting(true);
    setError(null);

    try {
      // Auto-skip remaining warmups
      const finalExercises = state.exercises.map((ex) => {
        if (ex.status === "pending" && WARMUP_CATEGORIES.includes(ex.category)) {
          return { ...ex, status: "skipped" as const };
        }
        return ex;
      });

      // 1. Fetch fresh week plan and mark session done
      const weekData = await getWeek(0);
      const weekPlan: WeekPlan = weekData.week_plan;

      await applyEvents({
        events: [
          {
            event_type: "mark_done",
            date: state.date,
            session_ref: state.sessionId,
          },
        ],
        week_plan: weekPlan,
      });

      // 2. Build and send feedback
      const exerciseFeedback = finalExercises.map((ex) => {
        const item: Record<string, unknown> = {
          exercise_id: ex.exerciseId,
          feedback_label: ex.feedbackLabel,
          completed: ex.status === "done",
        };
        if (ex.usedTotalLoadKg != null) {
          item.used_total_load_kg = ex.usedTotalLoadKg;
        }
        if (ex.usedLoadKg != null) {
          item.used_external_load_kg = ex.usedLoadKg;
          // Auto-compute total from external + body weight if not manually set
          if (ex.usedTotalLoadKg == null && ex.suggested.totalLoadKg != null && ex.suggested.externalLoadKg != null) {
            const bodyWeight = ex.suggested.totalLoadKg - ex.suggested.externalLoadKg;
            item.used_total_load_kg = bodyWeight + ex.usedLoadKg;
          }
        }
        if (ex.usedGrade) {
          item.used_grade = ex.usedGrade;
        }
        if (ex.suggested.surface) {
          item.surface_selected = ex.suggested.surface;
        }
        if (ex.completedSets != null) {
          item.completed_sets = ex.completedSets;
        }
        // Test measurement exercises: send the value as the field name directly
        if (ex.testField && ex.testMeasurement != null) {
          item[ex.testField] = ex.testMeasurement;
        }
        return item;
      });

      const durationSeconds = Math.max(0, Math.floor((Date.now() - new Date(state.startedAt).getTime()) / 1000));

      try {
        const logEntry: Record<string, unknown> = {
          date: state.date,
          session_id: state.sessionId,
          session_duration_seconds: durationSeconds,
          actual: {
            exercise_feedback_v1: exerciseFeedback,
          },
        };
        if (state.isTestSession) {
          logEntry.planned = [{
            session_id: state.sessionId,
            tags: { test: true },
            exercise_instances: [],
          }];
        }
        await postFeedback({
          log_entry: logEntry,
          status: "done",
        });

        // Success — clean up localStorage
        removeState(state.date, state.sessionId);
      } catch {
        // Feedback POST failed — save for retry
        setState((prev) => prev ? { ...prev, submitStatus: "feedback_pending" } : prev);
        saveState({ ...state, exercises: finalExercises, submitStatus: "feedback_pending" });
      }

      // Redirect to today regardless
      router.replace(`/today?date=${state.date}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to submit. Your progress is saved locally.");
      setSubmitting(false);
    }
  }, [state, router]);

  const handleSetChange = useCallback(
    (completedSets: number) => {
      if (!state) return;
      updateExercise(state.currentIndex, { completedSets });
    },
    [state, updateExercise]
  );

  const handleBack = useCallback(() => {
    if (!state || state.exercises.every((ex) => ex.status === "pending")) {
      router.replace(`/today?date=${date}`);
      return;
    }
    if (confirmLeave) {
      router.replace(`/today?date=${date}`);
    } else {
      setConfirmLeave(true);
      setTimeout(() => setConfirmLeave(false), 3000);
    }
  }, [state, confirmLeave, date, router]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!state) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const currentExercise = state.exercises[state.currentIndex];
  const sessionName =
    state.sessionName || state.sessionId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="mx-auto max-w-2xl">
      {/* Sticky header */}
      <div className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b px-4 py-3 space-y-3">
        {/* Top row: back + timer + session name */}
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={handleBack}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-4" />
            {confirmLeave ? "Tap again to leave" : "Back"}
          </button>
          <SessionTimer startedAt={state.startedAt} />
        </div>
        <p className="text-sm font-medium">{sessionName}</p>

        {/* Progress bar */}
        {!showSummary && (
          <GuidedProgressBar
            exercises={state.exercises}
            currentIndex={state.currentIndex}
            onNavigate={handleNavigate}
          />
        )}
      </div>

      {/* Main content */}
      <main className="p-4 space-y-4">
        {resumed && (
          <div className="rounded-lg border border-primary/30 bg-primary/10 p-3 flex items-center justify-between text-sm">
            <span className="text-primary font-medium">Session resumed — continuing from where you left off</span>
            <button
              type="button"
              onClick={() => setResumed(false)}
              className="text-muted-foreground hover:text-foreground ml-3 transition-colors"
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-center text-sm text-destructive">
            {error}
          </div>
        )}

        {showSummary ? (
          <GuidedSummary
            exercises={state.exercises}
            sessionName={sessionName}
            startedAt={state.startedAt}
            onMarkRemainingOk={handleMarkRemainingOk}
            onSkipRemaining={handleSkipRemaining}
            onSubmit={handleSubmit}
            submitting={submitting}
          />
        ) : currentExercise ? (
          <>
            <GuidedExerciseStep
              key={`${state.currentIndex}-${currentExercise.exerciseId}`}
              exercise={currentExercise}
              isTestSession={state.isTestSession}
              bodyweightKg={state.bodyweightKg}
              onDone={handleDone}
              onSkip={handleSkip}
              onSetChange={handleSetChange}
            />

            {/* Finish early button */}
            <Button
              variant="ghost"
              className="w-full text-muted-foreground text-sm"
              onClick={handleFinishEarly}
            >
              Finish session early
            </Button>
          </>
        ) : null}
      </main>
    </div>
  );
}
