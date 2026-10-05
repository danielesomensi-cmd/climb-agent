"use client";

import dynamic from "next/dynamic";

import { Suspense, useEffect, useState, useCallback, useMemo } from "react";
import { StartNewMacrocycleDialog } from "@/components/settings/start-new-macrocycle-dialog";
import { useCanStartNewCycle } from "@/lib/hooks/use-can-start-new-cycle";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { TopBar } from "@/components/layout/top-bar";
import { DayCard } from "@/components/training/day-card";
import { WeekAlertsCard } from "@/components/training/week-alerts-card";
import { KeySessionsCard } from "@/components/training/key-sessions-card";
import { KeyConflictDialog } from "@/components/training/key-conflict-dialog";
import { useKeyConflictGate } from "@/lib/hooks/use-key-conflict-gate";
import { DailyCueBanner } from "@/components/training/daily-cue-banner";
import { DailyTipCard } from "@/components/training/daily-tip-card";
import { FounderNoteCard, type FounderNote } from "@/components/training/founder-note-card";
import { PhaseCelebration } from "@/components/training/phase-celebration";
import { MilestoneToast } from "@/components/training/milestone-toast";
import { WeatherCard } from "@/components/training/weather-card";
import { CoachCard } from "@/components/training/coach-card";
const FeedbackDialog = dynamic(() => import("@/components/training/feedback-dialog").then((m) => m.FeedbackDialog), { ssr: false });
const QuickAddDialog = dynamic(() => import("@/components/training/quick-add-dialog").then((m) => m.QuickAddDialog), { ssr: false });
const ReplanDialog = dynamic(() => import("@/components/training/replan-dialog").then((m) => m.ReplanDialog), { ssr: false });
const MoveSessionDialog = dynamic(() => import("@/components/training/move-session-dialog").then((m) => m.MoveSessionDialog), { ssr: false });
const GymPickerDialog = dynamic(() => import("@/components/training/gym-picker-dialog").then((m) => m.GymPickerDialog), { ssr: false });
import { WeeklyCheckinCard } from "@/components/training/weekly-checkin-card";
import { TestReminderCard } from "@/components/training/test-reminder-card";
import { WeekProgressBar } from "@/components/training/week-progress-bar";
import { TodaySkeleton } from "@/components/training/today-skeleton";
import { ApiError, apiErrorDetail, applyEvents, checkKeyConflicts, postFeedback, applyOverride, quickAddSession,
  getOutdoorSpots, getOutdoorLogByDate, deleteFreeSession, getPitchLadder, setOutdoorPlan } from "@/lib/api";
import { STALE_PLAN_MESSAGE } from "@/lib/plan-revision";
import { useSubscription } from "@/lib/hooks/use-subscription";
import { useUserState, useWeekPlan, useDailyQuote, useOutdoorDoneDays } from "@/lib/hooks/queries";
import { useFreeSessionHistory, useFreeSessionsForDates } from "@/lib/hooks/queries/use-free-session";
import { useWeekEvents } from "@/lib/hooks/use-week-events";
import { queueOrWarn } from "@/lib/outbox-feedback";
import { flush as flushOutbox } from "@/lib/outbox";
import { queryKeys } from "@/lib/query-keys";
import { siblingsOf, writeWeekCache, type WeekSiblings } from "@/lib/week-cache";
import { alertMessagesFor, describeActionAlerts } from "@/lib/week-alerts";
import {
  buildDialogFeedbackItems,
  buildGuidedFeedbackItems,
  extractFeedbackExercises,
} from "@/lib/feedback-items";
import { resolveOutdoorLogTarget } from "@/lib/outdoor-log-target";
import { toast } from "sonner";
const OutdoorLogForm = dynamic(() => import("@/components/training/OutdoorLogForm"), { ssr: false });
import { TodayHeroCTA, type NextSessionInfo } from "@/components/training/today-hero-cta";
import { PausedBanner } from "@/components/training/paused-banner";
import { confirmFeedback } from "@/lib/haptics";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getInProgressSession, clearSavedSession, getKeyPrefix, type InProgressSession } from "@/lib/guided-session-utils";
import { getBoulderPhaseTip } from "@/lib/boulder-phase-tips";
import type { WeekPlan, DayPlan, OutdoorSpot, OutdoorSession, GuidedExercise, OutdoorDayType, OutdoorPitchLadder, KeyStatus, KeyProposal, SessionPain, LimitProblemDraft } from "@/lib/types";
import { boulderGradeSystemOf } from "@/lib/gradeUtils";
import { withFeedbackContract, type MeasureValues } from "@/lib/measured-feedback";
import { hasOtherActivity } from "@/lib/other-activity";
import { completeOtherActivityEvent, removeOtherActivityEvent, removeOutdoorEvent, undoOtherActivityEvent, undoOutdoorEvent } from "@/lib/week-events";

/** Full weekday names */
const WEEKDAY_FULL: Record<number, string> = {
  0: "Sunday",
  1: "Monday",
  2: "Tuesday",
  3: "Wednesday",
  4: "Thursday",
  5: "Friday",
  6: "Saturday",
};

/** Full month names */
const MONTH_EN: Record<number, string> = {
  0: "January",
  1: "February",
  2: "March",
  3: "April",
  4: "May",
  5: "June",
  6: "July",
  7: "August",
  8: "September",
  9: "October",
  10: "November",
  11: "December",
};

/** Returns today's date in YYYY-MM-DD format */
function todayISO(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Formats a date string as "Monday 15 February" */
function formatDateSubtitle(dateStr: string): string {
  const parts = dateStr.split("-");
  if (parts.length !== 3) return dateStr;
  const d = new Date(
    parseInt(parts[0]),
    parseInt(parts[1]) - 1,
    parseInt(parts[2])
  );
  const dayName = WEEKDAY_FULL[d.getDay()] ?? "";
  const dayNum = d.getDate();
  const monthName = MONTH_EN[d.getMonth()] ?? "";
  return `${dayName} ${dayNum} ${monthName}`;
}

function TodayContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isLoaded: authReady } = useAuth();
  const { canInteract } = useSubscription();
  const dateParam = searchParams.get("date");
  const targetDate = dateParam || todayISO();
  const isViewingToday = targetDate === todayISO();
  const checkoutSuccess = searchParams.get("checkout") === "success";

  // A187 — React Query hooks for cached reads
  const qc = useQueryClient();
  // B292b — `authReady` gates the NETWORK, not the display. Clerk.js is fetched
  // from the network, so offline it never initialises and `authReady` stays
  // false forever. Keeping the queries disabled is right (a request without a
  // token would only 401), but React Query still serves the persisted cache
  // through a disabled query — which is exactly what makes /today usable in
  // falesia. Nothing below may gate rendering on `authReady`.
  const stateQuery = useUserState(authReady);
  const weekQuery = useWeekPlan(0, authReady);
  /** True when Clerk answered. False offline — "we could not ask", not "no one". */
  const identityKnown = authReady;

  const weekPlan: WeekPlan | null = weekQuery.data?.week_plan ?? null;
  const phaseId: string | null = weekQuery.data?.phase_id ?? null;
  // B257: distinguish a genuine new user (no macrocycle → onboarding) from an
  // existing user whose current week resolves to a past Monday (e.g. the
  // macrocycle has ended), which now fails closed with week_plan: null rather
  // than regenerating an immutable past week.
  const hasMacrocycle = !!(stateQuery.data?.macrocycle);
  // A246 (F52): the reminder rides on the week payload.
  const testReminder = weekQuery.data?.test_reminder ?? null;
  const keyStatus: KeyStatus | null = weekQuery.data?.key_status ?? null;
  /** A301 — the week's guard alerts (sibling of week_plan, never persisted). */
  const guardWarnings = weekQuery.data?.guard_warnings ?? null;
  const pastWeekUnavailable = weekQuery.data?.past_week_unavailable ?? false;

  // B293 — first-load interruption queue: phase modal first, milestone toasts
  // only after it settled (won't show) or was dismissed. One overlay at a time.
  const [phaseGateOpen, setPhaseGateOpen] = useState(false);
  const handlePhaseSettled = useCallback((willShow: boolean) => {
    if (!willShow) setPhaseGateOpen(true);
  }, []);
  const handlePhaseClosed = useCallback(() => setPhaseGateOpen(true), []);

  // Derived from /api/state — memoised to avoid re-renders
  const gyms = useMemo<Array<{ gym_id?: string; name: string; equipment: string[] }>>(() => {
    const eq = stateQuery.data?.equipment as Record<string, unknown> | undefined;
    return (eq?.gyms as Array<{ gym_id?: string; name: string; equipment: string[] }>) ?? [];
  }, [stateQuery.data]);

  const homeEquipment = useMemo<string[]>(() => {
    const eq = stateQuery.data?.equipment as Record<string, unknown> | undefined;
    return (eq?.home as string[]) ?? [];
  }, [stateQuery.data]);

  const currentGrade = useMemo<string | null>(() => {
    const goal = stateQuery.data?.goal as { current_grade?: string } | undefined;
    return goal?.current_grade ?? null;
  }, [stateQuery.data]);

  // C203: boulder phase tip — shown only when goal discipline is "boulder"
  const discipline = useMemo<string | null>(() => {
    const goal = stateQuery.data?.goal as { discipline?: string } | undefined;
    return goal?.discipline ?? null;
  }, [stateQuery.data]);

  // A-NEW-MACRO: end-of-cycle CTA visibility
  const cycleStatus = useCanStartNewCycle(stateQuery.data ?? null);

  const boulderPhaseTip = useMemo<string | null>(() => {
    if (discipline !== "boulder") return null;
    return getBoulderPhaseTip(phaseId);
  }, [discipline, phaseId]);

  const loading = stateQuery.isLoading || weekQuery.isLoading;
  const queryError = stateQuery.error || weekQuery.error;

  /**
   * B292c — the onboarding prompt may ONLY appear when the server positively
   * told us this account has no plan.
   *
   * The old condition was `!loading && !error && ...`, where `error` is the
   * LOCAL mutation-error state — it never reflects a failed `getState()`. So a
   * failed state fetch rendered the red "Load failed" box AND "Welcome to
   * climb-agent! Complete your onboarding" at the same time, to a user with
   * months of training behind them.
   *
   * `isSuccess && !isFetching` covers every way we might not know yet: in
   * flight, errored, or disabled with nothing cached.
   */
  const stateLoadedOk = stateQuery.isSuccess && !stateQuery.isFetching;

  /** Helper: write a fresh week_plan into the React Query cache (instant UI update) */
  const updateWeekCache = useCallback((newWeekPlan: WeekPlan, siblings?: WeekSiblings) => {
    // A245 G-2 (F34): keeps week(0) and week(<server num>) in step.
    // A294 / A301: and the key status + guard alerts the response carried
    // (undefined = keep).
    writeWeekCache(qc, 0, newWeekPlan, siblings);
  }, [qc]);

  /** F6 — done/skip/undo passano da qui: coda FIFO + snapshot fresco. */
  const runWeekEvents = useWeekEvents(0);
  /** A294 — confirm before a custom session takes a key session's place. */
  const keyGate = useKeyConflictGate();

  /** Helper: refetch state + week (used by retry button and weekly check-in callback) */
  const refetchAll = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.weekAll });
    qc.invalidateQueries({ queryKey: queryKeys.state });
    // A245 G-3 (F36): progression rewrites working_loads, so any resolved
    // session in cache is now showing pre-feedback numbers.
    qc.invalidateQueries({ queryKey: queryKeys.sessionResolveAll });
  }, [qc]);

  const [error, setErrorState] = useState<string | null>(null);
  // B371: a stale-plan 409 is not a page error — the watcher refetches the
  // week and toasts; hiding the plan behind an error box would be wrong.
  const setError = useCallback(
    (msg: string | null) => setErrorState(msg === STALE_PLAN_MESSAGE ? null : msg),
    [],
  );
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackSessionId, setFeedbackSessionId] = useState<string | null>(
    null
  );
  const [replanDate, setReplanDate] = useState<string | null>(null);
  const [replanSessionIndex, setReplanSessionIndex] = useState<number | undefined>(undefined);
  const [quickAddDate, setQuickAddDate] = useState<string | null>(null);
  const [moveSession, setMoveSession] = useState<{
    date: string;
    slot: string;
    sessionId: string;
  } | null>(null);
  const [changeGymDate, setChangeGymDate] = useState<string | null>(null);
  const [outdoorLogDate, setOutdoorLogDate] = useState<string | null>(null);
  const [outdoorEditDate, setOutdoorEditDate] = useState<string | null>(null);
  // A265 — date of the outdoor day whose ladder is being generated/saved.
  const [outdoorPlanBusy, setOutdoorPlanBusy] = useState<string | null>(null);
  const [outdoorEditData, setOutdoorEditData] = useState<OutdoorSession | null>(null);
  const [outdoorSpots, setOutdoorSpots] = useState<OutdoorSpot[]>([]);
  // A286 E4 — routes/durate/load outdoor arrivano dalla cache di React Query
  // (vedi useOutdoorDoneDays più sotto): erano quattro useState riempiti da un
  // effetto keyato su weekPlan, che con structuralSharing disattivato ripartiva
  // a ogni azione dell'utente.
  const [resumeSession, setResumeSession] = useState<InProgressSession | null>(null);
  // A-NEW-MACRO: end-of-cycle banner + dialog
  const [newCycleDialogOpen, setNewCycleDialogOpen] = useState(false);

  // A202: feedback education banner — shown after ≥1 done session, dismissible.
  const [feedbackEduDismissed, setFeedbackEduDismissed] = useState(true);
  // C203: boulder phase tip banner — dismissed per-phase so it reappears on
  // phase transitions. Initialized to true and hydrated from localStorage.
  const [phaseTipDismissed, setPhaseTipDismissed] = useState(true);

  // Check for in-progress session on mount
  useEffect(() => {
    setResumeSession(getInProgressSession());
    if (typeof window !== "undefined") {
      setFeedbackEduDismissed(
        window.localStorage.getItem("feedback_education_dismissed") === "1",
      );
    }
  }, []);

  // Hydrate phase-tip dismissal when the phase id becomes known or changes.
  useEffect(() => {
    if (typeof window === "undefined" || !phaseId) return;
    const key = `boulder_phase_tip_dismissed_${phaseId}`;
    setPhaseTipDismissed(window.localStorage.getItem(key) === "1");
  }, [phaseId]);

  const hasDoneSession = useMemo<boolean>(() => {
    if (!weekPlan) return false;
    for (const w of weekPlan.weeks) {
      for (const d of w.days) {
        for (const s of d.sessions) {
          if (s.status === "done") return true;
        }
      }
    }
    return false;
  }, [weekPlan]);

  const dismissFeedbackEdu = useCallback(() => {
    setFeedbackEduDismissed(true);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("feedback_education_dismissed", "1");
    }
  }, []);

  const dismissPhaseTip = useCallback(() => {
    setPhaseTipDismissed(true);
    if (typeof window !== "undefined" && phaseId) {
      window.localStorage.setItem(`boulder_phase_tip_dismissed_${phaseId}`, "1");
    }
  }, [phaseId]);

  // B127/B128: retry pending guided-session feedback from localStorage on mount.
  // Stays outside React Query — this is recovery of pending writes, not a fetch.
  useEffect(() => {
    if (!authReady || typeof window === "undefined") return;
    // A245 B-2: was rebuilding the prefix inline with the literal "clerk"
    // instead of the real user id — same bug as guided-session-utils, and a
    // second copy of the same expression. Single source of truth now.
    const prefix = getKeyPrefix();
    const now = Date.now();
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key || !key.startsWith(prefix)) continue;
      try {
        const raw = localStorage.getItem(key);
        if (!raw) continue;
        const saved = JSON.parse(raw) as { startedAt?: string; submitStatus?: string; date?: string; sessionId?: string; exercises?: Array<Record<string, unknown>>; pain?: SessionPain; isTestSession?: boolean };

        // Cleanup sessions older than 24h that are completed
        if (saved.startedAt) {
          const age = now - new Date(saved.startedAt).getTime();
          if (age > 24 * 60 * 60 * 1000 && saved.submitStatus !== "feedback_pending") {
            localStorage.removeItem(key);
            continue;
          }
        }

        // Retry pending feedback
        if (saved.submitStatus === "feedback_pending" && saved.exercises) {
          // B288: this replay used to rebuild items by hand and kept only
          // usedLoadKg + usedGrade — a failed POST silently degraded into a
          // lossy one (total load, per-hand `hand` split, sets/reps, surface,
          // notes and test measurements all dropped) and then deleted the
          // richer local copy. Same builder as the guided player now.
          const feedbackItems = buildGuidedFeedbackItems(
            saved.exercises as unknown as GuidedExercise[],
          );
          // A295: the retry carries the contract and the session pain too —
          // a replay must never be poorer than the original POST.
          const retryEntry: Record<string, unknown> = {
            date: saved.date ?? "",
            session_id: saved.sessionId ?? "",
            ...(saved.startedAt ? { started_at: saved.startedAt } : {}),
            actual: { exercise_feedback_v1: feedbackItems },
          };
          if (saved.isTestSession) {
            retryEntry.planned = [{ session_id: saved.sessionId ?? "", tags: { test: true }, exercise_instances: [] }];
          }
          postFeedback({
            log_entry: withFeedbackContract(retryEntry, saved.pain ?? null),
            status: "done",
          }).then(() => {
            localStorage.removeItem(key);
            // refresh week plan so feedback badges appear
            qc.invalidateQueries({ queryKey: queryKeys.weekAll });
          }).catch((err) => {
            console.error("Failed to retry pending feedback submission:", err);
            // Leave in localStorage for next retry
          });
        }
      } catch {
        // Ignore malformed localStorage entries
      }
    }
  }, [authReady, qc]);

  // A245 B-4 (F4, F5) — drain the offline outbox on mount and whenever the
  // browser reports the connection is back. /today is the natural place: it is
  // the first screen after a session and the app's default landing route.
  useEffect(() => {
    if (!authReady || typeof window === "undefined") return;

    const drain = () => {
      flushOutbox()
        .then(({ sent }) => {
          if (sent > 0) {
            qc.invalidateQueries({ queryKey: queryKeys.weekAll });
            qc.invalidateQueries({ queryKey: queryKeys.state });
            // A245 G-3 (F36): a flushed feedback moved the loads too.
            qc.invalidateQueries({ queryKey: queryKeys.sessionResolveAll });
          }
        })
        .catch((err) => console.error("[outbox] flush failed:", err));
    };

    drain();
    window.addEventListener("online", drain);
    return () => window.removeEventListener("online", drain);
  }, [authReady, qc]);

  // Daily quote — context derived from current week plan
  const quoteContext = useMemo(() => {
    if (!weekPlan) return "";
    const phase = (weekPlan.profile_snapshot as Record<string, unknown> | undefined)?.phase_id as string | undefined;
    const day = weekPlan.weeks.flatMap((w) => w.days).find((d) => d.date === targetDate);
    const sessionIds = day?.sessions.map((s) => s.session_id) ?? [];
    if (phase === "deload") return "deload";
    if (sessionIds.some((id) => ["strength_long", "power_contact", "finger_strength"].some((kw) => id.includes(kw)))) {
      return "hard_day";
    }
    return "general";
  }, [weekPlan, targetDate]);
  const { data: quote } = useDailyQuote(quoteContext);

  // A286 E4 — le giornate outdoor "done" passano dalla cache di React Query.
  // B278: weekOutdoorLoad resta il totale di settimana usato dalla progress bar.
  const outdoorDoneDates = useMemo(
    () =>
      weekPlan?.weeks
        .flatMap((w) => w.days)
        .filter((d) => d.outdoor_session_status === "done")
        .map((d) => d.date) ?? [],
    [weekPlan],
  );
  const {
    routesMap: outdoorRoutesMap,
    durationMap: outdoorDurationMap,
    loadMap: outdoorLoadMap,
    totalLoad: weekOutdoorLoad,
  } = useOutdoorDoneDays(outdoorDoneDates, !!weekPlan);

  // A245 F-5 (F15): free sessions now come from the React Query cache instead
  // of two hand-rolled effects keyed on [weekPlan]. With structuralSharing
  // disabled every mutation produced a new weekPlan reference, so those effects
  // refired on every user action — 8 uncached requests each time.
  const weekDates = useMemo(
    () => weekPlan?.weeks.flatMap((w) => w.days).map((d) => d.date) ?? [],
    [weekPlan],
  );
  const freeSessionsQuery = useFreeSessionHistory(targetDate, !!targetDate);
  const freeSessions = useMemo(
    () => freeSessionsQuery.data?.sessions ?? [],
    [freeSessionsQuery.data],
  );
  const { sessions: weekFreeSessions, isSettled: weekFreeSessionsLoaded } =
    useFreeSessionsForDates(weekDates, !!weekPlan);

  /** Find target day in the weekly plan */
  const dayPlan: DayPlan | undefined = weekPlan?.weeks
    .flatMap((w) => w.days)
    .find((d) => d.date === targetDate);

  /** First day after target with sessions */
  const nextTrainingDay: DayPlan | undefined = weekPlan?.weeks
    .flatMap((w) => w.days)
    .find((d) => d.date > targetDate && d.sessions.length > 0);

  /** A-ACTIVATION-TIMING Day 3: hero empty-state decision.
   *
   * pre_start   : today < macrocycle.start_date (fallback fired, plan is future)
   * offday      : dayPlan exists but has 0 sessions AND there IS a next training day
   * empty_week  : dayPlan empty (or missing) AND no next training day this week
   * session     : dayPlan has sessions → DayCard renders, no hero
   *
   * pre_start supersedes offday/empty_week when today is before start_date.
   */
  const macrocycleStart: string | undefined =
    (stateQuery.data?.macrocycle as { start_date?: string } | null | undefined)?.start_date;

  const isPreStart = !!(
    isViewingToday && macrocycleStart && targetDate < macrocycleStart
  );

  // A223: while the plan is paused, today serves no session — a paused card
  // replaces the day view / hero. Resume lives in Settings.
  const pausedSince: string | null =
    (stateQuery.data?.macrocycle?.pause?.active_since) ?? null;
  const isPaused = !!(isViewingToday && pausedSince);

  /** First session across the entire week_plan (used for pre_start preview) */
  const firstSessionDay: DayPlan | undefined = weekPlan?.weeks
    .flatMap((w) => w.days)
    .find((d) => d.sessions.length > 0);

  /** Derive NextSessionInfo for offday / pre_start hero preview */
  const nextSessionInfo: NextSessionInfo | undefined = (() => {
    const source = isPreStart ? firstSessionDay : nextTrainingDay;
    if (!source || source.sessions.length === 0) return undefined;
    const s = source.sessions[0];
    const resolved = s.resolved as Record<string, unknown> | undefined;
    const sessionMeta = resolved?.session as Record<string, unknown> | undefined;
    const sessionName =
      (sessionMeta?.session_name as string | undefined) ??
      s.session_id
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
    return {
      date: source.date,
      weekday: source.weekday,
      session_name: sessionName,
      slot: s.slot,
      location: s.location,
    };
  })();

  /** A217: dayPlan has non-engine content (yoga, outdoor logged, free session)
   * — when true, prefer DayCard over hero so the user can interact with that
   * content. Hero only fires on truly empty rest-like days.
   */
  const hasNonEngineContent: boolean = !!(
    dayPlan && (
      hasOtherActivity(dayPlan) ||
      dayPlan.outdoor_spot_name ||
      dayPlan.outdoor_slot ||
      freeSessions.length > 0
    )
  );

  const heroState: "pre_start" | "offday" | "empty_week" | null = (() => {
    if (!isViewingToday || !weekPlan) return null;
    if (isPreStart) return "pre_start";
    const dayEmpty = !dayPlan || dayPlan.sessions.length === 0;
    if (!dayEmpty) return null; // DayCard handles it
    if (hasNonEngineContent) return null; // A217: defer to DayCard for non-engine days
    return nextTrainingDay ? "offday" : "empty_week";
  })();

  /** Mark a session as completed */
  async function handleMarkDone(sessionId: string) {
    if (!canInteract) { router.push("/subscribe"); return; }
    if (!weekPlan) return;
    try {
      // F6 — serializzata + snapshot riletto dalla cache (vedi useWeekEvents).
      await runWeekEvents([
        { event_type: "mark_done", date: targetDate, session_ref: sessionId },
      ]);
      // A286 — micro-ricompensa: la conferma si sente. La card fa la sua
      // transizione a "Completed" (session-card, con prefers-reduced-motion).
      confirmFeedback();

      // A207: custom sessions don't feed closed-loop/progression — skip feedback dialog.
      const markedSession = dayPlan?.sessions.find((s) => s.session_id === sessionId);
      if (markedSession?.is_custom) return;

      // Open feedback dialog
      setFeedbackSessionId(sessionId);
      setFeedbackOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  }

  /** Mark a session as skipped */
  async function handleMarkSkipped(sessionId: string) {
    if (!canInteract) { router.push("/subscribe"); return; }
    if (!weekPlan) return;
    try {
      await runWeekEvents([
        { event_type: "mark_skipped", date: targetDate, session_ref: sessionId },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  }

  /** Undo a session's done/skipped status */
  async function handleUndo(sessionId: string) {
    if (!weekPlan) return;
    try {
      await runWeekEvents([
        { event_type: "mark_planned", date: targetDate, session_ref: sessionId },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo");
    }
  }

  /** Complete an other-activity (complementary sport) with feedback + optional duration */
  async function handleCompleteOtherActivity(date: string, slot: string | undefined, feedback: string, durationMinutes?: number) {
    if (!weekPlan) return;
    // A245 G-5 (F19): /week clears a stale error before retrying and /today
    // did not — one of the real divergences the duplication had already produced.
    setError(null);
    try {
      const ev = completeOtherActivityEvent(date, slot, feedback, durationMinutes);
      const result = await applyEvents({
        events: [ev],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to complete activity");
    }
  }

  /** Edit a completed other-activity (B127/B276) */
  async function handleEditOtherActivity(date: string, slot: string | undefined, fields: { activity_name?: string; feedback?: string; duration_minutes?: number }) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [{ event_type: "edit_other_activity", date, ...(slot ? { slot } : {}), ...fields }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to edit activity");
    }
  }

  /** Undo other-activity completion (B276: per-slot) */
  async function handleUndoOtherActivity(date: string, slot?: string) {
    if (!weekPlan) return;
    // A245 G-5 (F19): /week clears a stale error before retrying and /today
    // did not — one of the real divergences the duplication had already produced.
    setError(null);
    try {
      const result = await applyEvents({
        events: [undoOtherActivityEvent(date, slot)],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo");
    }
  }

  /** Remove other activity from a day (B276: per-slot) */
  async function handleRemoveOtherActivity(date: string, slot?: string) {
    if (!weekPlan) return;
    // A245 G-5 (F19): /week clears a stale error before retrying and /today
    // did not — one of the real divergences the duplication had already produced.
    setError(null);
    try {
      const result = await applyEvents({
        events: [removeOtherActivityEvent(date, slot)],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove activity");
    }
  }

  /** Remove a session from the day plan */
  async function handleRemoveSession(sessionId: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [
          {
            event_type: "remove_session",
            date: targetDate,
            session_ref: sessionId,
          },
        ],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove session");
    }
  }

  /** Handle replan: call override API and update week plan */
  async function handleReplanApply(rdata: {
    intent: string;
    location: string;
    gym_id?: string;
    session_index?: number;
    // B360 — la falesia scelta nel dialog
    spot_id?: string;
    spot_name?: string;
    whole_day?: boolean;
  }) {
    if (!weekPlan || !replanDate) return;
    setError(null);
    try {
      const result = await applyOverride({
        intent: rdata.intent,
        location: rdata.location,
        reference_date: replanDate,
        target_date: replanDate,
        gym_id: rdata.gym_id,
        phase_id: phaseId ?? undefined,
        week_plan: weekPlan,
        session_index: rdata.session_index,
        spot_id: rdata.spot_id,
        spot_name: rdata.spot_name,
        whole_day: rdata.whole_day,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
      // A301: the override replaced its slot and nothing else. Its notes and
      // the alerts that involve it are a heads-up, never an error (an error
      // here used to hide the whole plan behind a red box).
      const alert = describeActionAlerts(result.warnings, "Changed");
      if (alert) toast(alert.title, { description: alert.description, duration: 10000 });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update plan");
    } finally {
      setReplanDate(null);
      setReplanSessionIndex(undefined);
    }
  }

  /** Handle quick-add: call quick-add API and update week plan */
  async function handleQuickAddApply(rdata: {
    session_id: string;
    slot: string;
    location: string;
    gym_id?: string;
  }) {
    if (!weekPlan || !quickAddDate) return;
    setError(null);
    try {
      // A301: the session goes in exactly as picked — nothing is eased and
      // there is nothing to force. What the recovery guards object to comes
      // back as alerts: a toast now, badges on the cards and the week's list.
      const result = await quickAddSession({
        session_id: rdata.session_id,
        target_date: quickAddDate,
        slot: rdata.slot,
        location: rdata.location,
        gym_id: rdata.gym_id,
        phase_id: phaseId ?? undefined,
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
      const alert = describeActionAlerts(result.warnings);
      if (alert) toast(alert.title, { description: alert.description, duration: 10000 });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to add session";
      if (msg.includes("already occupied")) {
        setError("That time slot is already taken. Try a different slot or day.");
      } else {
        setError(msg);
      }
    } finally {
      setQuickAddDate(null);
    }
  }

  /** A207: quick-add a user-built custom session via apply_events. */
  async function handleQuickAddCustomApply(rdata: {
    custom_session_id: string;
    slot: string;
    location: string;
    gym_id?: string;
  }) {
    if (!weekPlan || !quickAddDate) return;
    setError(null);
    const plan = weekPlan;
    const event = {
      event_type: "add_custom_session",
      custom_session_id: rdata.custom_session_id,
      target_date: quickAddDate,
      slot: rdata.slot,
      location: rdata.location,
      gym_id: rdata.gym_id,
    };
    setQuickAddDate(null);
    // A294: dry run first — confirm when the custom takes a key session's place.
    await keyGate.gate(
      () => checkKeyConflicts({ events: [event], week_plan: plan }),
      async () => {
        try {
          const result = await applyEvents({ events: [event], week_plan: plan });
          updateWeekCache(result.week_plan, siblingsOf(result));
          // A301: the custom goes in as built; what it trips is an alert.
          const alert = describeActionAlerts(alertMessagesFor(result.guard_warnings, event.target_date, event.slot));
          if (alert) toast(alert.title, { description: alert.description, duration: 10000 });
        } catch (e) {
          const msg = e instanceof Error ? e.message : "Failed to add custom session";
          if (msg.includes("already occupied")) {
            setError("That time slot is already taken. Try a different slot or day.");
          } else {
            setError(msg);
          }
        }
      },
    );
  }

  /** A294: one-tap re-schedule of a missed key session (validated server-side). */
  async function handleApplyKeyProposal(p: KeyProposal) {
    setError(null);
    try {
      await runWeekEvents([p.apply.event]);
      toast("Key session re-scheduled", {
        description: `${p.session_name} on ${p.date}`,
        duration: 6000,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to re-schedule the key session");
    }
  }

  /** Handle move session: call events API with move_session event */
  async function handleMoveApply(data: { to_date: string; to_slot: string }) {
    if (!weekPlan || !moveSession) return;
    setError(null);
    try {
      const result = await applyEvents({
        events: [
          {
            event_type: "move_session",
            from_date: moveSession.date,
            from_slot: moveSession.slot,
            to_date: data.to_date,
            to_slot: data.to_slot,
          },
        ],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
      // A301: the move is applied as asked; what it trips is an alert.
      const alert = describeActionAlerts(alertMessagesFor(result.guard_warnings, data.to_date, data.to_slot), "Moved");
      if (alert) toast(alert.title, { description: alert.description, duration: 10000 });
    } catch (e) {
      // A301: a refused move (422 — e.g. onto a done or skipped slot) is a
      // toast; the page keeps showing the week instead of an error screen.
      if (e instanceof ApiError && e.status === 422) {
        toast.error("Session not moved", { description: apiErrorDetail(e, "That slot cannot take this session.") });
      } else {
        setError(e instanceof Error ? e.message : "Failed to move session");
      }
    } finally {
      setMoveSession(null);
    }
  }

  /** Handle gym/location change for a day */
  async function handleChangeGymApply(data: {
    gym_id?: string;
    location: string;
  }) {
    if (!weekPlan || !changeGymDate) return;
    setError(null);
    try {
      const result = await applyEvents({
        events: [
          {
            event_type: "change_gym",
            date: changeGymDate,
            gym_id: data.gym_id,
            location: data.location,
          },
        ],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
      // A301: nothing compensates a lost finger session any more — say so.
      if (result.warnings && result.warnings.length > 0) {
        toast("Location changed", { description: result.warnings.join(" "), duration: 10000 });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to change location");
    } finally {
      setChangeGymDate(null);
    }
  }

  /** Handle outdoor quick-add: add outdoor session to day */
  async function handleApplyOutdoor(data: {
    spot_name: string;
    discipline: string;
    spot_id?: string;
  }) {
    if (!weekPlan || !quickAddDate) return;
    setError(null);
    try {
      const result = await applyEvents({
        events: [
          {
            event_type: "add_outdoor",
            date: quickAddDate,
            spot_name: data.spot_name,
            discipline: data.discipline,
            spot_id: data.spot_id,
          },
        ],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add outdoor session");
    } finally {
      setQuickAddDate(null);
    }
  }

  async function handleApplyOtherSport(data: { activity_name: string; slot: string }) {
    if (!weekPlan || !quickAddDate) return;
    setError(null);
    try {
      const result = await applyEvents({
        events: [
          {
            event_type: "add_other_activity",
            date: quickAddDate,
            activity_name: data.activity_name,
            slot: data.slot,
          },
        ],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add activity");
    } finally {
      setQuickAddDate(null);
    }
  }

  /** Open outdoor log form — check for existing session first (B186) */
  async function handleLogOutdoor(date: string) {
    // A245 C-5 (F37): only a real 404 means "no log yet" — see
    // lib/outdoor-log-target.ts for why the old bare catch was wrong.
    const target = await resolveOutdoorLogTarget(date);
    if (target.kind === "unavailable") {
      toast.error(target.message, { duration: 8000 });
      return;
    }
    setOutdoorSpots(target.spots);
    if (target.kind === "edit") {
      setOutdoorEditData(target.session);
      setOutdoorEditDate(date);
      return;
    }
    if (target.spotsFailed) {
      toast("Couldn't load your spots — you can still log the session.", { duration: 6000 });
    }
    setOutdoorLogDate(date);
  }

  /** After outdoor routes are logged, verify data persisted, then mark complete (D134) */
  async function handleOutdoorLogSuccess(info?: { planSynced?: boolean }) {
    if (!weekPlan || !outdoorLogDate) return;
    try {
      // B371: the log already marked the day done server side (B273) and
      // moved the week's revision — sending complete_outdoor on the copy held
      // here would be a false stale-plan 409. Just reload.
      if (info?.planSynced) {
        await qc.invalidateQueries({ queryKey: queryKeys.weekAll });
        return;
      }
      // D134: read-after-write — verify outdoor log was persisted before marking complete
      try {
        await getOutdoorLogByDate(outdoorLogDate);
      } catch {
        setError("Outdoor session data was not saved. Please try again.");
        return;
      }
      // B371: not synced (paused / no plan day / queued offline) — the log
      // may still have touched the week, so edit the fresh copy.
      const fresh = (await weekQuery.refetch()).data?.week_plan ?? weekPlan;
      const result = await applyEvents({
        events: [{ event_type: "complete_outdoor", date: outdoorLogDate }],
        week_plan: fresh,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to mark outdoor as done");
    } finally {
      setOutdoorLogDate(null);
    }
  }

  /** Undo outdoor completion */
  async function handleUndoOutdoor(date: string) {
    if (!weekPlan) return;
    // A245 G-5 (F19): /week clears a stale error before retrying and /today
    // did not — one of the real divergences the duplication had already produced.
    setError(null);
    try {
      const result = await applyEvents({
        events: [undoOutdoorEvent(date)],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo outdoor");
    }
  }

  /** Remove an outdoor session from a day */
  async function handleRemoveOutdoor(date: string) {
    if (!weekPlan) return;
    // A245 G-5 (F19): /week clears a stale error before retrying and /today
    // did not — one of the real divergences the duplication had already produced.
    setError(null);
    try {
      const result = await applyEvents({
        events: [removeOutdoorEvent(date)],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove outdoor session");
    }
  }

  /** A265 — generate the day's pitch ladder and persist it in one go. */
  async function handleGenerateOutdoorPlan(date: string, dayType: OutdoorDayType) {
    if (!weekPlan) return;
    setError(null);
    setOutdoorPlanBusy(date);
    try {
      const ladder = await getPitchLadder({ day_type: dayType });
      const result = await setOutdoorPlan({ date, plan: ladder, week_plan: weekPlan });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate the plan");
    } finally {
      setOutdoorPlanBusy(null);
    }
  }

  /** A265 — persist a hand-edited ladder (null clears it). */
  async function handleSetOutdoorPlan(date: string, plan: OutdoorPitchLadder | null) {
    if (!weekPlan) return;
    setError(null);
    setOutdoorPlanBusy(date);
    try {
      const result = await setOutdoorPlan({ date, plan, week_plan: weekPlan });
      updateWeekCache(result.week_plan, siblingsOf(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save the plan");
    } finally {
      setOutdoorPlanBusy(null);
    }
  }

  /** Edit outdoor session — fetch entry, open form in edit mode */
  async function handleEditOutdoor(date: string) {
    try {
      const data = await getOutdoorLogByDate(date);
      setOutdoorEditData(data.session);
      setOutdoorEditDate(date);
      getOutdoorSpots().then((d) => setOutdoorSpots(d.spots)).catch((err) => { console.error("Failed to load outdoor spots:", err); });
    } catch {
      setError("No outdoor session found for this date");
    }
  }

  async function handleEditOutdoorSuccess() {
    setOutdoorEditDate(null);
    setOutdoorEditData(null);
    refetchAll();
  }

  /** Submit session feedback (B127: always includes duration) */
  async function handleFeedbackSubmit(
    feedback: Record<string, string>,
    durationMinutes: number,
    loads: Record<string, number>,
    measures: Record<string, MeasureValues> = {},
    pain: SessionPain | null = null,
    grades: Record<string, string> = {},
    problems: Record<string, LimitProblemDraft[]> = {},
  ) {
    if (!feedbackSessionId) return;
    try {
      // B288: was {exercise_id, feedback_label, completed} only — the used
      // load never reached the engine, so working_loads stayed frozen and the
      // suggestion decayed back to the cold-start fallback forever.
      const feedbackItems = buildDialogFeedbackItems(
        feedbackExercises,
        feedback,
        loads,
        measures,
        grades,
        problems,
      );
      const body = {
        // A295: feedback_contract 2 — an omitted label means "not rated".
        log_entry: withFeedbackContract({
          date: targetDate,
          session_id: feedbackSessionId,
          session_duration_seconds: durationMinutes * 60,
          actual: {
            exercise_feedback_v1: feedbackItems,
          },
        }, pain),
        status: "done",
      };
      try {
        await postFeedback(body);
        // Re-fetch week plan so feedback_summary badges appear immediately
        refetchAll();
      } catch {
        // A245 B-4 (F4) — this used to be `catch { /* Non-critical */ }`.
        // Feedback IS the closed loop's fuel: losing it silently desynchronises
        // progression with no signal to anyone.
        queueOrWarn(body);
      }
    } finally {
      setFeedbackOpen(false);
      setFeedbackSessionId(null);
    }
  }

  // Extract exercises + slot from the resolved session for the feedback dialog
  const feedbackSession = feedbackSessionId && dayPlan
    ? dayPlan.sessions.find((s) => s.session_id === feedbackSessionId)
    : null;

  const feedbackSlot = feedbackSession?.slot ?? "";

  const feedbackExercises = extractFeedbackExercises(
    feedbackSession,
  );

  const title = isViewingToday ? "Today" : formatDateSubtitle(targetDate);
  const subtitle = isViewingToday
    ? formatDateSubtitle(targetDate)
    : undefined;

  return (
    <>
      <TopBar title={title} subtitle={subtitle} />

      <main className="relative z-10 mx-auto max-w-2xl space-y-4 p-4">
        {/* A264: hand-written note from the founder to this specific athlete.
            Renders only when user_state.founder_note exists and is undismissed,
            and only on the live "today" view — a note about your training is
            noise when you are looking back at last Tuesday. */}
        <FounderNoteCard
          note={stateQuery.data?.founder_note as FounderNote | undefined}
          isViewingToday={isViewingToday}
        />

        {/* Checkout success banner */}
        {checkoutSuccess && (
          <div className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
            Your subscription is active. Welcome to climb-agent Pro!
          </div>
        )}

        {/* A-NEW-MACRO: end-of-cycle CTA — only on the live "today" view */}
        {isViewingToday && cycleStatus.canShow && (
          <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-2">
            <p className="text-sm font-medium">
              {cycleStatus.isPastEndDate
                ? "Your macrocycle is complete."
                : "Final week — ready to plan your next cycle?"}
            </p>
            <button
              type="button"
              className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              onClick={() => setNewCycleDialogOpen(true)}
            >
              {cycleStatus.isPastEndDate
                ? "Plan your next cycle →"
                : "Start new macrocycle →"}
            </button>
          </div>
        )}

        {/* Resume in-progress session banner */}
        {resumeSession && (
          <div className="rounded-lg border border-warning/30 bg-warning/10 p-3 space-y-2">
            <p className="text-sm font-medium text-warning">
              You have a session in progress — exercise {resumeSession.completedCount} of {resumeSession.totalCount}
            </p>
            <p className="text-xs text-warning/70">
              {resumeSession.state.sessionName}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded-md bg-warning px-3 py-1.5 text-xs font-medium text-surface-base hover:bg-warning/90 transition-colors"
                onClick={() => router.push(`/guided/${resumeSession.date}/${resumeSession.sessionId}`)}
              >
                Resume
              </button>
              <button
                type="button"
                className="rounded-md border border-warning/30 px-3 py-1.5 text-xs text-warning hover:bg-warning/10 transition-colors"
                onClick={() => {
                  clearSavedSession(resumeSession.date, resumeSession.sessionId);
                  setResumeSession(null);
                }}
              >
                Discard
              </button>
            </div>
          </div>
        )}

        {/* Loading state */}
        {/* A245 F-6 (F14): a skeleton that reserves the real height, not a
            centred spinner that lets the page snap from empty to full. */}
        {(loading || (stateQuery.isFetching && !hasMacrocycle)) && <TodaySkeleton />}

        {/* Error state */}
        {(error || queryError) && !loading && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{error ?? (queryError instanceof Error ? queryError.message : "Failed to load data")}</p>
            <button
              onClick={refetchAll}
              className="mt-2 text-sm font-medium text-primary underline"
            >
              Retry
            </button>
          </div>
        )}


        {/* B292b — offline, with nothing cached for this device yet.
         *
         * Clerk cannot initialise without the network, so we genuinely do not
         * know who this is and there is no cached plan to fall back on. Say so.
         * Before this, the page sat blank (or, worse, invited an established
         * user to redo their onboarding). */}
        {!loading && !identityKnown && !weekPlan && !hasMacrocycle && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-lg font-medium">You&apos;re offline</p>
            <p className="mt-2 text-sm text-muted-foreground">
              We can&apos;t verify your session without a connection, and this
              device hasn&apos;t saved your plan yet. Connect once and it will be
              available offline from then on.
            </p>
          </div>
        )}

        {/* No macrocycle — prompt to start onboarding (true new user only).
         *
         * B292 — `loading` is `isLoading`, which is FALSE as soon as any cached
         * value exists, including a restored-but-empty one (A245 B-2 added
         * cache persistence). An established user could therefore be told
         * "Welcome to climb-agent! Complete your onboarding" while the real
         * state was still in flight — the worst possible message for someone
         * who has been training for months.
         *
         * Never claim the user has no plan while we are still asking. */}
        {stateLoadedOk && identityKnown && !weekPlan && !hasMacrocycle && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-lg font-medium">Welcome to climb-agent!</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Complete your onboarding to get your first training plan.
            </p>
            <Link
              href="/onboarding/welcome"
              className="mt-4 inline-block rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            >
              Start Onboarding
            </Link>
          </div>
        )}

        {/* B257: macrocycle exists but the current week resolves to a past,
            immutable week (cycle ended) — explain instead of showing onboarding.
            The "Plan your next cycle" CTA above provides the action. */}
        {!loading && !error && !weekPlan && hasMacrocycle && pastWeekUnavailable && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="font-medium">Nothing scheduled for today</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Your training plan has ended. Past weeks stay exactly as you
              trained them and aren&apos;t regenerated — start your next cycle to
              keep training.
            </p>
          </div>
        )}

        {/* A246 (F52) — periodic retest reminder. The backend has emitted this
            every ~6 weeks since it was built; until now nothing rendered it, so
            the recalibration it triggers never happened for anyone. Placed
            above the check-in because it decides what NEXT week contains. */}
        {!loading && !error && isViewingToday && testReminder && (
          <TestReminderCard reminder={testReminder} onResponded={refetchAll} />
        )}

        {/* Weekly check-in card (Sunday / Monday morning grace) */}
        {!loading && !error && isViewingToday && (
          <WeeklyCheckinCard weekPlan={weekPlan} onPlanUpdated={refetchAll} />
        )}

        {/* A220: standalone "Focus di oggi" cue section above the day's cards */}
        {!loading && !error && dayPlan && !heroState && dayPlan.sessions.length > 0 && (
          <DailyCueBanner
            sessions={dayPlan.sessions}
            date={dayPlan.date}
            isToday={isViewingToday}
          />
        )}

        {/* A294 — only when a key session of this week is owed or at risk. */}
        {!loading && !error && isViewingToday && !isPaused && (
          <KeySessionsCard status={keyStatus} compact onApplyProposal={handleApplyKeyProposal} />
        )}

        {/* A301 — the alerts of the day shown (recovery guards + lunch rules):
            a heads-up, the sessions stay as planned. */}
        {!loading && !error && !isPaused && dayPlan && (
          <WeekAlertsCard guardWarnings={guardWarnings} weekPlan={weekPlan} date={dayPlan.date} compact />
        )}

        {/* A223: plan paused — replaces today's sessions until resumed.
            A286: stesso componente di /week (era una card scritta a mano qui). */}
        {!loading && !error && isPaused && (
          <PausedBanner since={pausedSince} variant="prominent" />
        )}

        {/* Day plan — suppressed when hero is active (A217 rest-day dedup) */}
        {!loading && !error && !isPaused && dayPlan && !heroState && (
          <DayCard
            day={dayPlan}
            keyStatus={keyStatus}
            guardWarnings={guardWarnings}
            gyms={gyms}
            homeEquipment={homeEquipment}
            outdoorRoutes={outdoorRoutesMap[dayPlan.date]}
            outdoorDurationMinutes={outdoorDurationMap[dayPlan.date]}
            outdoorLoadScore={outdoorLoadMap[dayPlan.date]}
            weekPlan={weekPlan}
            onSessionUpdated={(updatedPlan) => {
              // B153d: use response data when available to avoid 422 reload race
              if (updatedPlan) { updateWeekCache(updatedPlan); } else { refetchAll(); }
            }}
            onMarkDone={handleMarkDone}
            onMarkSkipped={handleMarkSkipped}
            onUndo={handleUndo}
            onRemoveSession={handleRemoveSession}
            onReplan={(date, sessionIndex) => { setReplanDate(date); setReplanSessionIndex(sessionIndex); }}
            onQuickAdd={(date) => { if (!canInteract) { router.push("/subscribe"); return; } setQuickAddDate(date); }}
            onMoveSession={(date, slot, sessionId) =>
              setMoveSession({ date, slot, sessionId })
            }
            onChangeGym={(date) => setChangeGymDate(date)}
            onCompleteOtherActivity={handleCompleteOtherActivity}
            onUndoOtherActivity={handleUndoOtherActivity}
            onEditOtherActivity={handleEditOtherActivity}
            onRemoveOtherActivity={handleRemoveOtherActivity}
            onLogOutdoor={handleLogOutdoor}
            onGenerateOutdoorPlan={handleGenerateOutdoorPlan}
            onSetOutdoorPlan={handleSetOutdoorPlan}
            outdoorPlanGenerating={outdoorPlanBusy === dayPlan.date}
            outdoorPlanSaving={outdoorPlanBusy === dayPlan.date}
            onEditOutdoor={handleEditOutdoor}
            onUndoOutdoor={handleUndoOutdoor}
            onRemoveOutdoor={handleRemoveOutdoor}
            freeSessions={freeSessions as never}
            onDeleteFreeSession={async (sessionId: string) => {
              try {
                await deleteFreeSession(sessionId);
                // A245 F-5: the list is cache-owned now, so drop the cached
                // day instead of filtering a local copy that no longer exists.
                qc.invalidateQueries({ queryKey: queryKeys.freeSessionHistoryAll });
              } catch { /* ignore */ }
            }}
          />
        )}

        {/* A-ACTIVATION-TIMING Day 3: empty-state hero (today-viewing only) */}
        {!loading && !error && !isPaused && heroState && (
          <TodayHeroCTA
            state={heroState}
            nextSession={nextSessionInfo}
            startDate={macrocycleStart}
            onPreviewNextSession={
              nextSessionInfo
                ? () => router.push(`/today?date=${nextSessionInfo.date}`)
                : undefined
            }
            onPreviewFirstSession={
              nextSessionInfo
                ? () => router.push(`/week?date=${nextSessionInfo.date}`)
                : undefined
            }
            onChangeStartDate={() => router.push("/onboarding/start-week")}
          />
        )}

        {/* Non-today navigation with empty/missing day → minimal fallback */}
        {!loading && !error && !heroState && weekPlan && !isViewingToday &&
          (!dayPlan || dayPlan.sessions.length === 0) && (
            <div className="rounded-lg border border-dashed p-8 text-center">
              <p className="text-muted-foreground">No sessions on this day</p>
              {dayPlan && (
                <p className="mt-1 text-sm text-muted-foreground">
                  Enjoy the rest and recover for the next session.
                </p>
              )}
            </div>
          )}

        {/* A286 — tutto quello che segue stava SOPRA la sessione del giorno:
            per arrivare all'allenamento di oggi bisognava scorrere progress bar,
            meteo, coach e due banner educativi. La sessione ora è il primo
            blocco sotto l'header; questi restano, ma dopo. */}

        {/* Week progress bar */}
        {!loading && !error && weekPlan && (
          <WeekProgressBar weekPlan={weekPlan} freeSessions={weekFreeSessions} freeSessionsLoaded={weekFreeSessionsLoaded} outdoorLoad={weekOutdoorLoad} />
        )}

        {/* A224: live weather card — current location, today view only */}
        {!loading && !error && isViewingToday && <WeatherCard />}

        {/* A-COACH-V1a: AI coach entry point (bottom nav is full) */}
        {!loading && !error && isViewingToday && <CoachCard />}

        {/* C203: boulder phase tip — discipline-gated, dismissible per-phase */}
        {!loading && !error && dayPlan && boulderPhaseTip && !phaseTipDismissed && (
          <div className="relative rounded-lg border border-info/30 bg-info/5 p-3 pr-12 text-sm">
            <p className="font-medium text-info capitalize">
              {phaseId?.replace(/_/g, " ")} phase
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {boulderPhaseTip}
            </p>
            <button
              type="button"
              onClick={dismissPhaseTip}
              aria-label="Dismiss"
              className="absolute right-1 top-1 flex h-11 w-11 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              ×
            </button>
          </div>
        )}

        {/* A202: feedback loop education banner */}
        {!loading && !error && dayPlan && hasDoneSession && !feedbackEduDismissed && (
          <div className="relative rounded-lg border border-primary/30 bg-primary/5 p-3 pr-12 text-sm">
            <p className="font-medium text-primary">
              Your feedback adapts your training
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              After each exercise, your rating (easy/ok/hard) automatically adjusts weight and volume in future sessions. The more feedback you give, the more precise your plan becomes.
            </p>
            <button
              type="button"
              onClick={dismissFeedbackEdu}
              aria-label="Dismiss"
              className="absolute right-1 top-1 flex h-11 w-11 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              ×
            </button>
          </div>
        )}

        {/* A217: daily motivational quote inside hero card */}
        {quote && !loading && (
          <div className="relative mt-6 overflow-hidden rounded-xl border border-border-subtle shadow-md">
            <div className="relative aspect-[4/5] w-full">
              <Image
                src="/hero/today_hero.webp"
                alt="Climber chalking up before an indoor route"
                fill
                sizes="(max-width: 768px) 100vw, 768px"
                className="object-cover"
              />
              <div
                className="pointer-events-none absolute inset-0"
                style={{
                  background:
                    "linear-gradient(to bottom, transparent 40%, hsl(var(--surface-base) / 0.95) 100%)",
                }}
                aria-hidden="true"
              />
              <div className="absolute inset-x-0 bottom-0 p-5">
                <p className="text-base italic leading-relaxed text-fg">
                  &ldquo;{quote.text}&rdquo;
                </p>
                <p className="mt-2 text-right text-sm text-fg-secondary">
                  — {quote.author}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* A234: daily feature-discovery tip below the quote */}
        {isViewingToday && !loading && !error && (
          <DailyTipCard date={targetDate} />
        )}
      </main>

      {/* A235: one-time phase-transition celebration.
          B293: first in the interruption queue — the milestone toast below
          waits for this to settle (no-show) or be dismissed. */}
      {isViewingToday && !loading && (
        <PhaseCelebration
          state={stateQuery.data}
          onSettled={handlePhaseSettled}
          onClosed={handlePhaseClosed}
        />
      )}

      {/* A239: milestone unlock toasts (B293: gated behind the phase modal;
          if user state failed to load the modal can never settle — let the
          toast through rather than suppressing it forever) */}
      {isViewingToday && !loading && (
        <MilestoneToast enabled={phaseGateOpen || stateQuery.isError} />
      )}

      {/* Post-session feedback dialog */}
      <FeedbackDialog
        open={feedbackOpen}
        onClose={() => {
          setFeedbackOpen(false);
          setFeedbackSessionId(null);
        }}
        onSubmit={handleFeedbackSubmit}
        exercises={feedbackExercises}
        slot={feedbackSlot}
        gradeSystem={boulderGradeSystemOf(stateQuery.data)}
      />

      {/* Replan dialog */}
      <ReplanDialog
        open={replanDate !== null}
        date={replanDate ?? ""}
        gyms={gyms}
        sessionIndex={replanSessionIndex}
        onClose={() => { setReplanDate(null); setReplanSessionIndex(undefined); }}
        onApply={handleReplanApply}
      />

      {/* Quick-add dialog */}
      <QuickAddDialog
        open={quickAddDate !== null}
        date={quickAddDate ?? ""}
        gyms={gyms}
        onClose={() => setQuickAddDate(null)}
        onApply={handleQuickAddApply}
        onApplyOutdoor={handleApplyOutdoor}
        onApplyOtherSport={handleApplyOtherSport}
        onApplyFreeClimbing={() => {
          setQuickAddDate(null);
          router.push(`/free-session?context=standalone&date=${quickAddDate || targetDate}`);
        }}
        onApplyCustom={handleQuickAddCustomApply}
      />

      {/* A294 — a custom session that takes a key session's place */}
      <KeyConflictDialog {...keyGate.dialogProps} />

      {/* Move session dialog */}
      {weekPlan && (
        <MoveSessionDialog
          open={moveSession !== null}
          sessionId={moveSession?.sessionId ?? ""}
          fromDate={moveSession?.date ?? ""}
          fromSlot={moveSession?.slot ?? ""}
          weekPlan={weekPlan}
          onClose={() => setMoveSession(null)}
          onApply={handleMoveApply}
        />
      )}

      {/* Gym/location picker dialog */}
      <GymPickerDialog
        open={changeGymDate !== null}
        date={changeGymDate ?? ""}
        gyms={gyms}
        onClose={() => setChangeGymDate(null)}
        onApply={handleChangeGymApply}
      />

      {/* Outdoor log dialog */}
      <Dialog open={outdoorLogDate !== null} onOpenChange={(v) => !v && setOutdoorLogDate(null)}>
        <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Log Outdoor Session</DialogTitle>
          </DialogHeader>
          <OutdoorLogForm
            spots={outdoorSpots}
            defaultDate={outdoorLogDate ?? undefined}
            defaultSpotName={dayPlan?.outdoor_spot_name}
            defaultDiscipline={dayPlan?.outdoor_discipline}
            defaultGrade={currentGrade ?? undefined}
            onSuccess={handleOutdoorLogSuccess}
          />
        </DialogContent>
      </Dialog>

      {/* A-NEW-MACRO: shared Start New Macrocycle dialog */}
      <StartNewMacrocycleDialog
        open={newCycleDialogOpen}
        onOpenChange={setNewCycleDialogOpen}
        state={stateQuery.data ?? null}
        onSuccess={() => {
          qc.invalidateQueries({ queryKey: ["state"] });
          qc.invalidateQueries({ queryKey: ["week"] });
        }}
      />

      {/* Outdoor edit dialog */}
      <Dialog open={outdoorEditDate !== null} onOpenChange={(v) => { if (!v) { setOutdoorEditDate(null); setOutdoorEditData(null); } }}>
        <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Outdoor Session</DialogTitle>
          </DialogHeader>
          {outdoorEditData && (
            <OutdoorLogForm
              spots={outdoorSpots}
              initialData={outdoorEditData}
              onSuccess={handleEditOutdoorSuccess}
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function TodayPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      }
    >
      <TodayContent />
    </Suspense>
  );
}
