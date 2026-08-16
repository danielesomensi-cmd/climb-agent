"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SessionTimer } from "@/components/guided/session-timer";
import { GuidedProgressBar } from "@/components/guided/guided-progress-bar";
import { GuidedExerciseStep } from "@/components/guided/guided-exercise-step";
import { GuidedSummary } from "@/components/guided/guided-summary";
import { postFeedback, getState } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { buildGuidedFeedbackItems } from "@/lib/feedback-items";
import { guidedStorageKey } from "@/lib/guided-session-utils";
import { unlockAudio, getAudioContext } from "@/lib/audio-unlock";
import { useSubscription } from "@/lib/hooks/use-subscription";
import { useWakeLock } from "@/lib/hooks/use-wake-lock";
import type { GuidedSessionState, GuidedExercise, WeekPlan } from "@/lib/types";

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

// B290 (closes F54): the local key builder that used to live here produced
// `guided_session_clerk_...` — the literal string, not the user id — while the
// readers in guided-session-utils had already moved to the real id. Writers and
// readers stopped agreeing, so resume and the offline feedback retry both went
// blind. There is now exactly one key builder: guidedStorageKey().

function loadState(date: string, sessionId: string): GuidedSessionState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(guidedStorageKey(date, sessionId));
    return raw ? (JSON.parse(raw) as GuidedSessionState) : null;
  } catch {
    return null;
  }
}

function saveState(state: GuidedSessionState) {
  if (typeof window === "undefined") return;
  const key = guidedStorageKey(state.date, state.sessionId);
  localStorage.setItem(key, JSON.stringify(state));
}

function removeState(date: string, sessionId: string) {
  if (typeof window === "undefined") return;
  localStorage.removeItem(guidedStorageKey(date, sessionId));
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const WARMUP_CATEGORIES = ["warmup_general", "warmup_specific", "mobility"];

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

export default function GuidedSessionPage() {
  const params = useParams();
  const router = useRouter();
  const date = params.date as string;
  const sessionId = params.sessionId as string;
  const qc = useQueryClient();
  const { canInteract, loading: subLoading } = useSubscription();
  // A245 C-1 (F8) — true once saved state has been loaded, i.e. this really is
  // a session in progress and not a cold hit on the URL.
  const [sessionStarted, setSessionStarted] = useState(false);

  // Gate: redirect expired users to subscribe page.
  //
  // A245 C-1 (F8) — but NEVER once a session is under way. The gate belongs at
  // the entry point (/today's "Start session"); yanking someone to /subscribe
  // mid-workout because the gym wifi flapped loses the session they are in the
  // middle of. `sessionStarted` is set as soon as saved state is loaded.
  useEffect(() => {
    if (!subLoading && !canInteract && !sessionStarted) {
      router.replace("/subscribe");
    }
  }, [canInteract, subLoading, sessionStarted, router]);

  const [state, setState] = useState<GuidedSessionState | null>(null);
  const [showSummary, setShowSummary] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [resumed, setResumed] = useState(false);

  // B332: keep the screen awake for the whole session, like the session-builder
  // player already did (play/page.tsx). Without it the screen sleeps on its own
  // during a 5-minute boulder rest, which suspends the timer — the condition the
  // set counter used to get wrong.
  useWakeLock(state !== null && !showSummary);

  // Ref to always have latest state for the beforeunload handler
  const stateRef = useRef(state);
  useEffect(() => { stateRef.current = state; }, [state]);

  // Load state from localStorage on mount
  useEffect(() => {
    const saved = loadState(date, sessionId);
    if (saved) {
      setState(saved);
      setSessionStarted(true);
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
        }).catch((err) => { console.error("Failed to prefetch bodyweight:", err); });
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
    (feedbackLabel: string, usedLoad?: number, usedGrade?: string, usedTotalLoad?: number, testMeasurement?: number, perHand?: { right?: number; left?: number; right_reps?: number; left_reps?: number }) => {
      if (!state) return;
      const idx = state.currentIndex;
      const exercise = state.exercises[idx];

      // B128: detect unilateral test measurement (e.g. lp_duration_test — seconds per hand)
      const isUnilateralMeasurement = exercise.unilateral && !!exercise.testField && !!exercise.testUnit && perHand;

      if (isUnilateralMeasurement) {
        updateExercise(idx, {
          status: "done",
          feedbackLabel,
          testMeasurementRight: perHand?.right,
          testMeasurementLeft: perHand?.left,
        });
      } else {
        updateExercise(idx, {
          status: "done",
          feedbackLabel,
          usedLoadKg: usedLoad,
          usedTotalLoadKg: usedTotalLoad,
          usedGrade,
          testMeasurement,
          usedLoadKgRight: perHand?.right,
          usedLoadKgLeft: perHand?.left,
          completedRepsRight: perHand?.right_reps,
          completedRepsLeft: perHand?.left_reps,
        });
      }

      // B128: recalc suggestion for next exercise if user just completed a max test
      // When lp_max_test_5s is done, update lp_duration_test suggestion with 60% of new max
      if (exercise.exerciseId === "lp_max_test_5s" && perHand) {
        const roundHalf = (v: number) => Math.round(v * 2) / 2;
        setState((prev) => {
          if (!prev) return prev;
          const exercises = [...prev.exercises];
          for (let i = idx + 1; i < exercises.length; i++) {
            const next = exercises[i];
            if (next.exerciseId === "lp_duration_test" && next.prescription.intensityPct) {
              const pct = next.prescription.intensityPct;
              exercises[i] = {
                ...next,
                suggested: {
                  ...next.suggested,
                  leftHand: perHand.left != null
                    ? { externalLoadKg: roundHalf(perHand.left * pct) }
                    : next.suggested.leftHand,
                  rightHand: perHand.right != null
                    ? { externalLoadKg: roundHalf(perHand.right * pct) }
                    : next.suggested.rightHand,
                },
              };
              break;
            }
          }
          return { ...prev, exercises };
        });
      }

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

  // A247 — anchors for the scroll-on-advance effect below.
  const headerRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);

  /**
   * A247 — bring the new exercise's TITLE into view.
   *
   * Tapping Done at the BOTTOM of a long card advanced `currentIndex`, the card
   * re-rendered with the next exercise... and the scroll position stayed put.
   * You were left staring at the bottom of a different exercise, usually at
   * another Done button, with no way to tell whether your tap had registered.
   *
   * First fix scrolled to page top — not enough: on an iPhone the sticky
   * header plus the "Today's focus" banner pushed the exercise title below the
   * fold, so you still could not see WHAT you had to do next. Now we scroll
   * the exercise card itself to sit right under the sticky header; whatever
   * lives above it (process cue banner, resume banner) may go off-screen —
   * intended, the title is the anchor.
   *
   * Smooth, guarded on `prefers-reduced-motion` → instant jump. Also fires on
   * the last-exercise → summary transition so the summary heading is visible.
   */
  useEffect(() => {
    if (typeof window === "undefined") return;
    // Wait one frame so the new card has rendered and layout is final —
    // scrolling before that targets a stale position.
    const raf = requestAnimationFrame(() => {
      const content = contentRef.current;
      if (!content) return;
      const headerHeight = headerRef.current?.offsetHeight ?? 0;
      const top =
        content.getBoundingClientRect().top + window.scrollY - headerHeight - 8;
      const reduceMotion = window.matchMedia?.(
        "(prefers-reduced-motion: reduce)"
      )?.matches;
      window.scrollTo({
        top: Math.max(0, top),
        behavior: reduceMotion ? "auto" : "smooth",
      });
    });
    return () => cancelAnimationFrame(raf);
  }, [state?.currentIndex, showSummary]);

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
      const exercises = prev.exercises.map((ex) => {
        if (ex.status !== "pending") return ex;
        // B288: an exercise closed from here was never visited, so usedLoadKg
        // is null and the item would ship without a load — the engine then
        // discards it and the load memory never moves. The suggested load is
        // what the user saw and (implicitly) confirmed by marking it OK, which
        // is exactly what the guided step does when you tap Done without
        // touching the field.
        const usedLoadKg =
          ex.usedLoadKg ??
          (ex.loadModel !== "bodyweight_only" ? ex.suggested.externalLoadKg : undefined);
        return { ...ex, status: "done" as const, feedbackLabel: "ok", usedLoadKg };
      });
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
      // Auto-skip remaining warmups and instruction-only blocks
      const finalExercises = state.exercises.map((ex) => {
        if (ex.status === "pending" && (WARMUP_CATEGORIES.includes(ex.category) || ex.isInstructionOnly)) {
          return { ...ex, status: "skipped" as const };
        }
        return ex;
      });

      // A194: the backend now handles mark_done inline as part of POST
      // /api/feedback and returns the updated week_plan. No prelude
      // getState/getWeek/applyEvents round-trips needed.

      // B288: item construction lives in lib/feedback-items so the /today
      // retry path replays the identical payload instead of a narrowed copy.
      const exerciseFeedback = buildGuidedFeedbackItems(finalExercises);

      const durationSeconds = Math.max(0, Math.floor((Date.now() - new Date(state.startedAt).getTime()) / 1000));

      try {
        const logEntry: Record<string, unknown> = {
          date: state.date,
          session_id: state.sessionId,
          // Real wall-clock start the timer already runs on (health-vault export).
          started_at: state.startedAt,
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
        const response = await postFeedback({
          log_entry: logEntry,
          status: "done",
        });

        // Success — clean up localStorage
        removeState(state.date, state.sessionId);

        // A194: the backend returned the updated week_plan inline. Write it
        // directly into the ['week', 0] cache so /today renders fresh on first
        // paint — no refetch round-trip needed. State cache is invalidated so
        // progression working_loads get picked up on next read.
        if (response.week_plan) {
          qc.setQueryData<{
            week_num: number;
            phase_id: string;
            week_plan: WeekPlan;
          }>(queryKeys.week(0), (old) =>
            old ? { ...old, week_plan: response.week_plan as WeekPlan } : old,
          );
        } else {
          // Fallback: force a refetch if the backend could not return a plan
          await qc.refetchQueries({ queryKey: queryKeys.weekAll });
        }
        qc.invalidateQueries({ queryKey: queryKeys.state });
        // A245 G-3 (F36): loads just changed — drop cached resolutions.
        qc.invalidateQueries({ queryKey: queryKeys.sessionResolveAll });
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
  }, [state, router, qc]);

  const handleSetChange = useCallback(
    (completedSets: number) => {
      if (!state) return;
      updateExercise(state.currentIndex, { completedSets });
    },
    [state, updateExercise]
  );

  // B156: per-exercise notes
  const handleNotesChange = useCallback(
    (notes: string) => {
      if (!state) return;
      updateExercise(state.currentIndex, { notes: notes || undefined });
    },
    [state, updateExercise]
  );

  const isNavigatingRef = useRef(false);

  const handleBack = useCallback(() => {
    if (isNavigatingRef.current) return;
    if (!state || state.exercises.every((ex) => ex.status === "pending")) {
      isNavigatingRef.current = true;
      router.replace(`/today?date=${date}`);
      return;
    }
    if (confirmLeave) {
      isNavigatingRef.current = true;
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
      <div ref={headerRef} className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b px-4 pt-[calc(0.75rem+env(safe-area-inset-top))] pb-3 space-y-3">
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

        {/* A141: Process cue banner */}
        {state.processCue && !showSummary && (
          <div className="rounded-xl bg-gradient-to-r from-amber-900/30 to-amber-800/20 border border-amber-700/30 p-4">
            <div className="flex items-start gap-3">
              <svg className="h-5 w-5 text-amber-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
              </svg>
              <div>
                <p className="text-xs font-medium text-amber-400 mb-1">Today&apos;s focus</p>
                <p className="text-sm text-zinc-200 leading-relaxed">{state.processCue.text}</p>
              </div>
            </div>
          </div>
        )}

        {showSummary ? (
          <div ref={contentRef}>
            <GuidedSummary
              exercises={state.exercises}
              sessionName={sessionName}
              startedAt={state.startedAt}
              onMarkRemainingOk={handleMarkRemainingOk}
              onSkipRemaining={handleSkipRemaining}
              onSubmit={handleSubmit}
              submitting={submitting}
            />
          </div>
        ) : currentExercise ? (
          <>
            {/* A247: contentRef marks the scroll anchor — the card starts with
                the exercise title, so "card under the header" == "title visible". */}
            <div ref={contentRef}>
              <GuidedExerciseStep
                key={`${state.currentIndex}-${currentExercise.exerciseId}`}
                exercise={currentExercise}
                isTestSession={state.isTestSession}
                bodyweightKg={state.bodyweightKg}
                onDone={handleDone}
                onSkip={handleSkip}
                onSetChange={handleSetChange}
                onNotesChange={handleNotesChange}
              />
            </div>

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
