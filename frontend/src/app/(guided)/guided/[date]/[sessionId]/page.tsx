"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { ArrowLeft, CloudOff } from "lucide-react";
import { SoundToggle } from "@/components/guided/sound-toggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { SessionTimer } from "@/components/guided/session-timer";
import { GuidedProgressBar } from "@/components/guided/guided-progress-bar";
import { GuidedExerciseStep } from "@/components/guided/guided-exercise-step";
import { GuidedSummary } from "@/components/guided/guided-summary";
import { postFeedback, getState } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { writeWeekCache } from "@/lib/week-cache";
import { bodyweightFromState, loadGuidedSession } from "@/lib/guided-session-utils";
import {
  announcePendingSync,
  buildGuidedFeedbackBody,
  syncPendingGuidedFeedback,
  type PendingGuidedState,
} from "@/lib/guided-pending-feedback";
import { applyStepUndo, closeStep, isWithinAdvanceGuard, type StepUndo } from "@/lib/guided-step-undo";
import { unlockAudio, getAudioContext, setPlaybackAudioSession } from "@/lib/audio-unlock";
import { isSoundMuted, SOUND_MUTED_EVENT } from "@/lib/sound-pref";
import { useSubscription } from "@/lib/hooks/use-subscription";
import { useSubmitLock } from "@/lib/hooks/use-submit-lock";
import { useWakeLock } from "@/lib/hooks/use-wake-lock";
import { useUserState } from "@/lib/hooks/use-state";
import { hrMaxFromState } from "@/lib/hr-zones";
import type { GuidedSessionState, GuidedExercise, LimitProblem, SessionPain, WeekPlan } from "@/lib/types";
import type { MeasureValues } from "@/lib/measured-feedback";

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

// B290 (closes F54): the local key builder that used to live here produced
// `guided_session_clerk_...` — the literal string, not the user id — while the
// readers in guided-session-utils had already moved to the real id. Writers and
// readers stopped agreeing, so resume and the offline feedback retry both went
// blind. There is now exactly one key builder (guided-session-utils).
//
// B397 G1: the page no longer rebuilds the key on each write. It reads the
// session once through loadGuidedSession(), PINS the key it came from, and
// writes only there — so a session read while Clerk was still booting can
// never be copied under whichever user Clerk names afterwards.

/** Returns false when the write failed (quota, private mode). */
function writeGuided(key: string, state: GuidedSessionState): boolean {
  if (typeof window === "undefined") return false;
  try {
    localStorage.setItem(key, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

function removeGuided(key: string) {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(key);
  } catch {
    /* storage unavailable — nothing to remove */
  }
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const WARMUP_CATEGORIES = ["warmup_general", "warmup_specific", "mobility"];

/**
 * B397 G1 — how long a reload waits for Clerk when nothing was found under the
 * remembered user (a device that never identified one). Offline it does not
 * wait at all: Clerk.js comes from the network and would never answer.
 */
const CLERK_WAIT_MS = 4000;

/** B397 G5 — how long the "Undo" of a Done/Skip stays on screen. */
const UNDO_TOAST_MS = 5000;

function exerciseLabel(ex: GuidedExercise): string {
  return ex.name || ex.exerciseId.replace(/_/g, " ");
}

/**
 * B128: a finished lp_max_test_5s re-bases the lp_duration_test suggestion on
 * 60% (intensityPct) of the new max, per hand.
 */
function rebaseDurationTest(
  exercises: GuidedExercise[],
  fromIdx: number,
  perHand: { right?: number; left?: number },
): GuidedExercise[] {
  const roundHalf = (v: number) => Math.round(v * 2) / 2;
  const out = [...exercises];
  for (let i = fromIdx + 1; i < out.length; i++) {
    const next = out[i];
    if (next.exerciseId === "lp_duration_test" && next.prescription.intensityPct) {
      const pct = next.prescription.intensityPct;
      out[i] = {
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
  return out;
}

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
  // B397 G1 — Clerk's answer, to confirm (or contradict) the user the session
  // was read for while Clerk was still booting.
  const { isLoaded: authLoaded, userId: authUserId } = useAuth();
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
  const [error, setError] = useState<string | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [resumed, setResumed] = useState(false);
  // B397 G6 — "Finish session early" asks first (inline, not window.confirm).
  const [confirmFinish, setConfirmFinish] = useState(false);
  // B397 G3 — the pending view's "Send now" result.
  const [syncError, setSyncError] = useState<string | null>(null);
  // B397 G2 — the session has been handed over (sent, or queued for the
  // replay): the submit button stays disabled until the page goes away.
  const [handedOver, setHandedOver] = useState(false);

  /** B397 G1 — the key the session was read from, and who owns it. */
  const scopeRef = useRef<{ key: string; owner: string | null } | null>(null);
  /**
   * B397 G2 — latched when the session is handed over. Synchronous, unlike
   * `handedOver`: a tap landing between the end of the request and the route
   * change must not send the feedback a second time, and nothing may write the
   * session back to storage after it was removed.
   */
  const finishedRef = useRef(false);

  const isPending = state?.submitStatus === "feedback_pending";

  // B332: keep the screen awake for the whole session, like the session-builder
  // player already did (play/page.tsx). Without it the screen sleeps on its own
  // during a 5-minute boulder rest, which suspends the timer — the condition the
  // set counter used to get wrong.
  useWakeLock(state !== null && !showSummary && !isPending);
  // A316: HRmax for the bpm bands — fetched only when a cardio row has one.
  const { state: userState } = useUserState(!!state?.exercises.some((ex) => ex.hrTarget));
  const hrMax = hrMaxFromState(userState);

  // Ref to always have latest state for the beforeunload handler
  const stateRef = useRef(state);
  useEffect(() => { stateRef.current = state; }, [state]);

  // Load state from localStorage on mount
  useEffect(() => {
    // B397 G1 — a session is already on screen. It may have been read for the
    // user remembered on this device while Clerk was still booting: once Clerk
    // answers, it must be the same user. Otherwise drop it from the screen
    // (its data stays where it is, under its owner) and leave.
    if (scopeRef.current) {
      if (authLoaded && scopeRef.current.owner !== (authUserId ?? null)) {
        scopeRef.current = null;
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setState(null);
        router.replace(`/today?date=${date}`);
      }
      return;
    }

    const loaded = loadGuidedSession(date, sessionId);
    if (loaded) {
      scopeRef.current = { key: loaded.key, owner: loaded.owner };
      let saved = loaded.state;
      // B397 G7 — body weight for the test sessions' total-load maths comes
      // from the ['state'] cache (persisted, so it works offline); the GET is
      // only the fallback when the cache does not have it.
      if (saved.isTestSession && !saved.bodyweightKg) {
        const cachedBw = bodyweightFromState(qc.getQueryData(queryKeys.state));
        if (cachedBw) {
          saved = { ...saved, bodyweightKg: cachedBw };
        } else {
          getState().then((stateData) => {
            const bw = bodyweightFromState(stateData);
            if (bw) {
              setState((prev) => prev ? { ...prev, bodyweightKg: bw } : prev);
            }
          }).catch((err) => { console.error("Failed to prefetch bodyweight:", err); });
        }
      }
      // B355 — idratazione post-mount da localStorage: leggerla in render
      // romperebbe l'SSR (hydration mismatch). L'effect è la sede corretta.
      setState(saved);
      setSessionStarted(true);
      // B397 G3: a session waiting for its feedback replay shows the pending
      // view — no resume banner, and above all no second "Submit".
      if (saved.submitStatus === "feedback_pending") return;
      // Show resume banner if there's actual progress (not a fresh session)
      const hasProgress =
        saved.exercises.some((ex) => ex.status !== "pending") ||
        saved.currentIndex > 0;
      if (hasProgress) setResumed(true);
      // If all exercises are done/skipped, show summary
      const allDone = saved.exercises.every((ex) => ex.status !== "pending");
      if (allDone) setShowSummary(true);
      return;
    }

    // B397 G1 — nothing under the provisional scope. While Clerk is still
    // booting (and online, so it can answer) wait for it: this effect runs
    // again when it does, under the confirmed user. Bounded, so a Clerk that
    // never loads cannot leave the spinner up forever.
    if (!authLoaded && (typeof navigator === "undefined" || navigator.onLine !== false)) {
      const timer = setTimeout(() => router.replace(`/today?date=${date}`), CLERK_WAIT_MS);
      return () => clearTimeout(timer);
    }
    // No saved state — redirect back to today
    router.replace(`/today?date=${date}`);
  }, [date, sessionId, router, authLoaded, authUserId, qc]);

  // Auto-dismiss resume banner after 4 seconds
  useEffect(() => {
    if (!resumed) return;
    const timer = setTimeout(() => setResumed(false), 4000);
    return () => clearTimeout(timer);
  }, [resumed]);

  // Persist state to localStorage on every change — under the pinned key only,
  // and never after the session was handed over (B397 G1/G2).
  useEffect(() => {
    if (state && scopeRef.current && !finishedRef.current) {
      writeGuided(scopeRef.current.key, state);
    }
  }, [state]);

  // B397 G4 — let the cues through the iPhone silent switch while the session
  // is open and its sound is on; back to the default when muted or closed.
  useEffect(() => {
    const apply = () => setPlaybackAudioSession(!isSoundMuted());
    apply();
    window.addEventListener(SOUND_MUTED_EVENT, apply);
    return () => {
      window.removeEventListener(SOUND_MUTED_EVENT, apply);
      setPlaybackAudioSession(false);
    };
  }, []);

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

  // ---------------------------------------------------------------------------
  // B397 G5 — Done / Skip are reversible, and a double tap closes ONE exercise
  // ---------------------------------------------------------------------------

  /** When the last Done/Skip (or Undo) moved the player. */
  const lastAdvanceRef = useRef(0);
  const undoToastRef = useRef<string | number | null>(null);

  const dismissUndo = useCallback(() => {
    if (undoToastRef.current != null) {
      toast.dismiss(undoToastRef.current);
      undoToastRef.current = null;
    }
  }, []);
  // An "Undo" must not outlive the player it would rewrite.
  useEffect(() => dismissUndo, [dismissUndo]);

  const handleUndo = useCallback((undo: StepUndo) => {
    undoToastRef.current = null;
    if (finishedRef.current) return;
    // The restored card mounts under the finger too.
    lastAdvanceRef.current = Date.now();
    setState((prev) => (prev ? applyStepUndo(prev, undo) : prev));
    setShowSummary(false);
    setConfirmFinish(false);
  }, []);

  const offerUndo = useCallback(
    (message: string, undo: StepUndo) => {
      dismissUndo();
      undoToastRef.current = toast(message, {
        duration: UNDO_TOAST_MS,
        action: { label: "Undo", onClick: () => handleUndo(undo) },
        // A thumb-sized target: sonner's default action button is ~24 px tall.
        actionButtonStyle: { minHeight: 40, paddingInline: 16, fontSize: 14 },
      });
    },
    [dismissUndo, handleUndo],
  );

  /**
   * The next card mounts with its own Done/Skip exactly where the last ones
   * were, so the second half of a double tap would close an exercise nobody
   * looked at. Swallow it.
   */
  const advanceBlocked = useCallback((): boolean => {
    const now = Date.now();
    if (isWithinAdvanceGuard(lastAdvanceRef.current, now)) return true;
    lastAdvanceRef.current = now;
    return false;
  }, []);

  /** Close the current exercise, move on, and offer the way back. */
  const advance = useCallback(
    (
      current: GuidedSessionState,
      updates: Partial<GuidedExercise>,
      message: string,
      extra?: (exercises: GuidedExercise[]) => GuidedExercise[],
    ) => {
      const idx = current.currentIndex;
      const { openedSummary, undo } = closeStep(current, idx, updates, extra);
      setState((prev) => (prev ? closeStep(prev, idx, updates, extra).next : prev));
      if (openedSummary) setShowSummary(true);
      setConfirmFinish(false);
      offerUndo(message, undo);
    },
    [offerUndo],
  );

  const handleDone = useCallback(
    (feedbackLabel: string | null, usedLoad?: number, usedGrade?: string, usedTotalLoad?: number, testMeasurement?: number, perHand?: { right?: number; left?: number; right_reps?: number; left_reps?: number }, measures?: MeasureValues, problems?: LimitProblem[], surface?: string) => {
      if (!state || finishedRef.current) return;
      if (advanceBlocked()) return;
      const exercise = state.exercises[state.currentIndex];

      // B128: detect unilateral test measurement (e.g. lp_duration_test — seconds per hand)
      const isUnilateralMeasurement = exercise.unilateral && !!exercise.testField && !!exercise.testUnit && perHand;

      const updates: Partial<GuidedExercise> = isUnilateralMeasurement
        ? {
            status: "done",
            feedbackLabel,
            testMeasurementRight: perHand?.right,
            testMeasurementLeft: perHand?.left,
          }
        : {
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
            // A295: optional measures (undefined = not measured)
            lastSetReps: measures?.lastSetReps,
            hangMargin: measures?.hangMargin,
            hangHeldS: measures?.hangHeldS,
            // A296: limit problem log (undefined = not logged)
            problems: problems && problems.length > 0 ? problems : undefined,
            // A299: the wall picked in the logger (custom/adhoc limit rows).
            chosenSurface: surface,
          };

      // B128: recalc suggestion for next exercise if user just completed a max test
      // When lp_max_test_5s is done, update lp_duration_test suggestion with 60% of new max
      const idx = state.currentIndex;
      const extra =
        exercise.exerciseId === "lp_max_test_5s" && perHand
          ? (exercises: GuidedExercise[]) => rebaseDurationTest(exercises, idx, perHand)
          : undefined;

      // Advance to next exercise or show summary
      advance(state, updates, `Done: ${exerciseLabel(exercise)}`, extra);
    },
    [state, advance, advanceBlocked]
  );

  const handleSkip = useCallback(() => {
    if (!state || finishedRef.current) return;
    if (advanceBlocked()) return;
    const exercise = state.exercises[state.currentIndex];
    // A295: a skipped exercise is not rated (it used to ship as "ok").
    advance(state, { status: "skipped", feedbackLabel: null }, `Skipped: ${exerciseLabel(exercise)}`);
  }, [state, advance, advanceBlocked]);

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
      if (!state || finishedRef.current) return;
      setShowSummary(false);
      setConfirmFinish(false);
      setState((prev) => prev ? { ...prev, currentIndex: index } : prev);
    },
    [state]
  );

  /** B397 G6 — from the summary back to the player, on the first exercise left. */
  const handleBackToExercises = useCallback(() => {
    if (!state) return;
    const firstPending = state.exercises.findIndex((ex) => ex.status === "pending");
    handleNavigate(firstPending >= 0 ? firstPending : state.currentIndex);
  }, [state, handleNavigate]);

  const handleFinishEarly = useCallback(() => {
    setConfirmFinish(false);
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
        // A295: "done" but NOT rated — marking the rest as done must not sign
        // an "ok" on exercises nobody looked at.
        return { ...ex, status: "done" as const, feedbackLabel: null, usedLoadKg };
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

  const submitSession = useCallback(async () => {
    // B397 G2 — one submit per session: the lock below stops the double tap,
    // this latch stops a tap that lands after the request but before the
    // route change.
    const scope = scopeRef.current;
    if (!state || !scope || finishedRef.current) return;
    setError(null);
    dismissUndo();

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

      const durationSeconds = Math.max(0, Math.floor((Date.now() - new Date(state.startedAt).getTime()) / 1000));

      // B288 / B397 G3: ONE builder for the first POST and for the replay, and
      // the replay sends this very body — duration included.
      const body = buildGuidedFeedbackBody(state, finalExercises, durationSeconds);

      try {
        const response = await postFeedback(body);
        finishedRef.current = true;
        setHandedOver(true);

        // Success — clean up localStorage
        removeGuided(scope.key);

        // A194: the backend returned the updated week_plan inline. Write it
        // directly into the ['week', 0] cache so /today renders fresh on first
        // paint — no refetch round-trip needed. State cache is invalidated so
        // progression working_loads get picked up on next read.
        if (response.week_plan) {
          // B371: mirrored onto the week(N) alias too (the revision moved).
          if (qc.getQueryData(queryKeys.week(0))) {
            writeWeekCache(qc, 0, response.week_plan as WeekPlan);
          }
        } else {
          // Fallback: force a refetch if the backend could not return a plan
          await qc.refetchQueries({ queryKey: queryKeys.weekAll });
        }
        qc.invalidateQueries({ queryKey: queryKeys.state });
        // A245 G-3 (F36): loads just changed — drop cached resolutions.
        qc.invalidateQueries({ queryKey: queryKeys.sessionResolveAll });
      } catch {
        // Feedback POST failed — save for retry, with the exact body (B397 G3).
        const pending: PendingGuidedState = {
          ...state,
          exercises: finalExercises,
          submitStatus: "feedback_pending",
          pendingFeedback: body,
        };
        if (!writeGuided(scope.key, pending)) {
          // Could not even keep it on the device: stay here, say so, let the
          // athlete try again instead of pretending it is safe.
          setError("Could not save your session on this device. Check your connection and try again.");
          return;
        }
        finishedRef.current = true;
        setHandedOver(true);
        toast("Session saved on this device — it will sync when you're back online.", {
          duration: 6000,
        });
      }

      // Redirect to today regardless
      router.replace(`/today?date=${state.date}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to submit. Your progress is saved locally.");
    }
  }, [state, router, qc, dismissUndo]);

  // B397 G2 — B330's lock: a double tap on "Submit & finish" sends ONE POST
  // (the server runs apply_feedback on every POST it receives).
  const { run: runSubmit, busy: submitting } = useSubmitLock(submitSession);
  const handleSubmit = useCallback(() => {
    void runSubmit();
  }, [runSubmit]);

  /**
   * B397 G3 — "Send now" in the pending view: the same single-flight replay
   * /today runs, so it can never race it into a second POST.
   */
  const sendPendingNow = useCallback(async () => {
    setSyncError(null);
    try {
      const result = await syncPendingGuidedFeedback(qc);
      announcePendingSync(result);
    } catch (err) {
      console.error("[guided] pending feedback sync failed:", err);
    }
    const scope = scopeRef.current;
    const stillQueued = (() => {
      if (!scope) return false;
      try {
        return localStorage.getItem(scope.key) !== null;
      } catch {
        return true;
      }
    })();
    if (!stillQueued) {
      finishedRef.current = true;
      router.replace(`/today?date=${date}`);
      return;
    }
    setSyncError("Not sent yet — it stays saved on this device and will go out when the connection is back.");
  }, [qc, router, date]);
  const { run: runSendPending, busy: sendingPending } = useSubmitLock(sendPendingNow);

  // A295: session pain (0-3, zone from 2) — saved with the state, so the
  // offline retry from /today replays it.
  const handlePainChange = useCallback((pain: SessionPain | null) => {
    setState((prev) => (prev ? { ...prev, pain: pain ?? undefined } : prev));
  }, []);

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

  // B397 G3 — Start reopened a session whose feedback is still queued. It used
  // to land on the summary with a live "Submit & finish": a second POST of the
  // same session. Now it only says where the feedback is.
  if (isPending) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b px-4 pt-[calc(0.75rem+env(safe-area-inset-top))] pb-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => router.replace(`/today?date=${date}`)}
              className="-ml-2 flex min-h-[44px] min-w-[44px] shrink-0 items-center gap-1 px-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowLeft className="size-4" />
              Back
            </button>
            <p className="flex-1 truncate text-center text-sm font-semibold">{sessionName}</p>
            <div className="min-w-[44px]" />
          </div>
        </div>
        <main className="p-4">
          <Card className="gap-0 py-0">
            <CardContent className="space-y-4 py-5">
              <div className="flex items-start gap-3">
                <CloudOff className="mt-0.5 size-5 shrink-0 text-warning" />
                <div className="space-y-1">
                  <p className="font-medium">Session saved on this device</p>
                  <p className="text-sm text-muted-foreground">
                    Your feedback hasn&apos;t reached the server yet. It is sent automatically
                    when you&apos;re back online — no need to submit it again.
                  </p>
                </div>
              </div>
              {syncError && <p className="text-sm text-warning">{syncError}</p>}
              <div className="space-y-2">
                <Button
                  className="min-h-[44px] w-full"
                  onClick={() => { void runSendPending(); }}
                  disabled={sendingPending || !authLoaded}
                >
                  {sendingPending ? "Sending..." : "Send now"}
                </Button>
                <Button
                  variant="outline"
                  className="min-h-[44px] w-full"
                  onClick={() => router.replace(`/today?date=${date}`)}
                >
                  Back to Today
                </Button>
              </div>
            </CardContent>
          </Card>
        </main>
      </div>
    );
  }

  const remainingCount = state.exercises.filter((ex) => ex.status === "pending").length;

  return (
    <div className="mx-auto max-w-2xl">
      {/* Sticky header */}
      <div ref={headerRef} className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b px-4 pt-[calc(0.75rem+env(safe-area-inset-top))] pb-3 space-y-3">
        {/* A307: one row — back | session name | timer + sound */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleBack}
            className={`-ml-2 flex min-h-[44px] min-w-[44px] shrink-0 items-center gap-1 px-2 text-sm transition-colors ${
              confirmLeave ? "text-warning font-medium" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <ArrowLeft className="size-4" />
            {confirmLeave ? "Tap again to leave" : "Back"}
          </button>
          <p className="flex-1 truncate text-center text-sm font-semibold">{sessionName}</p>
          <div className="flex shrink-0 items-center gap-2">
            {/* A307: the summary shows a frozen duration instead. */}
            {!showSummary && <SessionTimer startedAt={state.startedAt} />}
            <SoundToggle />
          </div>
        </div>

        {/* Progress bar */}
        {!showSummary && (
          <GuidedProgressBar
            exercises={state.exercises}
            currentIndex={state.currentIndex}
            onNavigate={handleNavigate}
          />
        )}

        {/* A307: past the first step the focus shrinks to one line */}
        {state.processCue && !showSummary && state.currentIndex > 0 && (
          <p className="truncate text-xs text-warning">Focus: {state.processCue.text}</p>
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

        {/* A141: Process cue banner — A307: full card on the first step only */}
        {state.processCue && !showSummary && state.currentIndex === 0 && (
          <div className="rounded-xl bg-warning-muted border border-warning/30 p-4">
            <div className="flex items-start gap-3">
              <svg className="h-5 w-5 text-warning mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
              </svg>
              <div>
                <p className="text-xs font-medium text-warning mb-1">Today&apos;s focus</p>
                <p className="text-sm text-foreground leading-relaxed">{state.processCue.text}</p>
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
              pain={state.pain ?? null}
              onPainChange={handlePainChange}
              onSubmit={handleSubmit}
              submitting={submitting || handedOver}
              onBackToExercises={handleBackToExercises}
              onEditExercise={handleNavigate}
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
                hrMax={hrMax}
                onDone={handleDone}
                onSkip={handleSkip}
                onSetChange={handleSetChange}
                onNotesChange={handleNotesChange}
                nextExerciseName={(() => {
                  const next = state.exercises[state.currentIndex + 1];
                  return next ? next.name || next.exerciseId.replace(/_/g, " ") : undefined;
                })()}
              />
            </div>

            {/* Finish early — B397 G6: 44 px, set apart from Skip/Done by a
                divider, and it asks first. The question text takes the
                button's place, so a double tap lands on text, not on "Finish". */}
            <div className="border-t border-border/50 pt-4">
              {confirmFinish ? (
                <div className="space-y-3 rounded-lg border border-warning/30 bg-warning-muted p-3">
                  <p className="text-sm">
                    End the session now?
                    {remainingCount > 0 && (
                      <>
                        {" "}
                        {remainingCount} exercise{remainingCount === 1 ? "" : "s"} still to do — you
                        can mark or skip {remainingCount === 1 ? "it" : "them"} on the next screen.
                      </>
                    )}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      className="min-h-[44px] flex-1"
                      onClick={() => setConfirmFinish(false)}
                    >
                      Keep going
                    </Button>
                    <Button
                      variant="secondary"
                      className="min-h-[44px] flex-1"
                      onClick={handleFinishEarly}
                    >
                      Finish now
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  variant="ghost"
                  className="min-h-[44px] w-full text-muted-foreground text-sm"
                  onClick={() => setConfirmFinish(true)}
                >
                  Finish session early
                </Button>
              )}
            </div>
          </>
        ) : null}
      </main>
    </div>
  );
}
