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
import { DailyCueBanner } from "@/components/training/daily-cue-banner";
import { DailyTipCard } from "@/components/training/daily-tip-card";
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
import { WeekProgressBar } from "@/components/training/week-progress-bar";
import { TodaySkeleton } from "@/components/training/today-skeleton";
import { applyEvents, postFeedback, applyOverride, quickAddSession, getOutdoorSpots, getOutdoorSessions, getOutdoorLogByDate, deleteFreeSession } from "@/lib/api";
import { useSubscription } from "@/lib/hooks/use-subscription";
import { useUserState, useWeekPlan, useDailyQuote } from "@/lib/hooks/queries";
import { useFreeSessionHistory, useFreeSessionsForDates } from "@/lib/hooks/queries/use-free-session";
import { useWeekEvents } from "@/lib/hooks/use-week-events";
import { queueOrWarn } from "@/lib/outbox-feedback";
import { flush as flushOutbox } from "@/lib/outbox";
import { queryKeys } from "@/lib/query-keys";
import { writeWeekCache } from "@/lib/week-cache";
import {
  buildDialogFeedbackItems,
  buildGuidedFeedbackItems,
  extractFeedbackExercises,
} from "@/lib/feedback-items";
import { resolveOutdoorLogTarget } from "@/lib/outdoor-log-target";
import { toast } from "sonner";
const OutdoorLogForm = dynamic(() => import("@/components/training/OutdoorLogForm"), { ssr: false });
import { TodayHeroCTA, type NextSessionInfo } from "@/components/training/today-hero-cta";
import { formatPauseDate } from "@/lib/hooks/use-plan-pause";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getInProgressSession, clearSavedSession, getKeyPrefix, type InProgressSession } from "@/lib/guided-session-utils";
import { getBoulderPhaseTip } from "@/lib/boulder-phase-tips";
import type { WeekPlan, DayPlan, OutdoorSpot, OutdoorRoute, OutdoorSession, GuidedExercise } from "@/lib/types";
import { hasOtherActivity } from "@/lib/other-activity";

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
  const pastWeekUnavailable = weekQuery.data?.past_week_unavailable ?? false;

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
  const updateWeekCache = useCallback((newWeekPlan: WeekPlan) => {
    // A245 G-2 (F34): keeps week(0) and week(<server num>) in step.
    writeWeekCache(qc, 0, newWeekPlan);
  }, [qc]);

  /** F6 — done/skip/undo passano da qui: coda FIFO + snapshot fresco. */
  const runWeekEvents = useWeekEvents(0);

  /** Helper: refetch state + week (used by retry button and weekly check-in callback) */
  const refetchAll = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.weekAll });
    qc.invalidateQueries({ queryKey: queryKeys.state });
    // A245 G-3 (F36): progression rewrites working_loads, so any resolved
    // session in cache is now showing pre-feedback numbers.
    qc.invalidateQueries({ queryKey: queryKeys.sessionResolveAll });
  }, [qc]);

  const [error, setError] = useState<string | null>(null);
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
  const [outdoorEditData, setOutdoorEditData] = useState<OutdoorSession | null>(null);
  const [outdoorSpots, setOutdoorSpots] = useState<OutdoorSpot[]>([]);
  const [outdoorRoutesMap, setOutdoorRoutesMap] = useState<Record<string, OutdoorRoute[]>>({});
  const [outdoorDurationMap, setOutdoorDurationMap] = useState<Record<string, number>>({});
  const [weekOutdoorLoad, setWeekOutdoorLoad] = useState(0); // B278: outdoor load for the week
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
        const saved = JSON.parse(raw) as { startedAt?: string; submitStatus?: string; date?: string; sessionId?: string; exercises?: Array<Record<string, unknown>> };

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
          postFeedback({
            log_entry: {
              date: saved.date ?? "",
              session_id: saved.sessionId ?? "",
              actual: { exercise_feedback_v1: feedbackItems },
            },
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

  // Fetch outdoor session routes for days marked "done"
  useEffect(() => {
    if (!weekPlan) return;
    const days = weekPlan.weeks.flatMap(w => w.days);
    const doneDates = days
      .filter(d => d.outdoor_session_status === "done")
      .map(d => d.date);
    if (doneDates.length === 0) {
      setOutdoorRoutesMap({});
      setWeekOutdoorLoad(0);
      return;
    }
    const minDate = doneDates.sort()[0];
    getOutdoorSessions(minDate)
      .then(({ sessions }) => {
        const map: Record<string, OutdoorRoute[]> = {};
        const durMap: Record<string, number> = {};
        let outdoorLoadTotal = 0; // B278: keep Today's load coherent with Week header + report
        for (const s of sessions) {
          if (doneDates.includes(s.date)) {
            map[s.date] = [...(map[s.date] || []), ...s.routes];
            if (s.duration_minutes) durMap[s.date] = (durMap[s.date] ?? 0) + s.duration_minutes;
            if (s.load_score) outdoorLoadTotal += s.load_score;
          }
        }
        setOutdoorRoutesMap(map);
        setOutdoorDurationMap(durMap);
        setWeekOutdoorLoad(outdoorLoadTotal);
      })
      .catch((err) => { console.error("Failed to load outdoor sessions:", err); });
  }, [weekPlan]);

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
    try {
      const ev: Record<string, unknown> = {
        event_type: "complete_other_activity",
        date,
        feedback,
      };
      if (slot) ev.slot = slot;
      if (durationMinutes != null) ev.duration_minutes = durationMinutes;
      const result = await applyEvents({
        events: [ev],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
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
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to edit activity");
    }
  }

  /** Undo other-activity completion (B276: per-slot) */
  async function handleUndoOtherActivity(date: string, slot?: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [
          {
            event_type: "undo_other_activity",
            date,
            ...(slot ? { slot } : {}),
          },
        ],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo");
    }
  }

  /** Remove other activity from a day (B276: per-slot) */
  async function handleRemoveOtherActivity(date: string, slot?: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [{ event_type: "remove_other_activity", date, ...(slot ? { slot } : {}) }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
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
      updateWeekCache(result.week_plan);
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
      });
      updateWeekCache(result.week_plan);
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
      const result = await quickAddSession({
        session_id: rdata.session_id,
        target_date: quickAddDate,
        slot: rdata.slot,
        location: rdata.location,
        gym_id: rdata.gym_id,
        phase_id: phaseId ?? undefined,
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
      if (result.warnings?.length > 0) {
        setError(result.warnings.join("; "));
      }
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
    try {
      const result = await applyEvents({
        events: [
          {
            event_type: "add_custom_session",
            custom_session_id: rdata.custom_session_id,
            target_date: quickAddDate,
            slot: rdata.slot,
            location: rdata.location,
            gym_id: rdata.gym_id,
          },
        ],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to add custom session";
      if (msg.includes("already occupied")) {
        setError("That time slot is already taken. Try a different slot or day.");
      } else {
        setError(msg);
      }
    } finally {
      setQuickAddDate(null);
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
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to move session");
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
      updateWeekCache(result.week_plan);
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
      updateWeekCache(result.week_plan);
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
      updateWeekCache(result.week_plan);
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
  async function handleOutdoorLogSuccess() {
    if (!weekPlan || !outdoorLogDate) return;
    try {
      // D134: read-after-write — verify outdoor log was persisted before marking complete
      try {
        await getOutdoorLogByDate(outdoorLogDate);
      } catch {
        setError("Outdoor session data was not saved. Please try again.");
        return;
      }
      const result = await applyEvents({
        events: [{ event_type: "complete_outdoor", date: outdoorLogDate }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to mark outdoor as done");
    } finally {
      setOutdoorLogDate(null);
    }
  }

  /** Undo outdoor completion */
  async function handleUndoOutdoor(date: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [{ event_type: "undo_outdoor", date }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo outdoor");
    }
  }

  /** Remove an outdoor session from a day */
  async function handleRemoveOutdoor(date: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [{ event_type: "remove_outdoor", date }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove outdoor session");
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
      );
      const body = {
        log_entry: {
          date: targetDate,
          session_id: feedbackSessionId,
          session_duration_seconds: durationMinutes * 60,
          actual: {
            exercise_feedback_v1: feedbackItems,
          },
        },
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

        {/* Week progress bar */}
        {!loading && !error && weekPlan && (
          <WeekProgressBar weekPlan={weekPlan} freeSessions={weekFreeSessions} freeSessionsLoaded={weekFreeSessionsLoaded} outdoorLoad={weekOutdoorLoad} />
        )}

        {/* Weekly check-in card (Sunday / Monday morning grace) */}
        {!loading && !error && isViewingToday && (
          <WeeklyCheckinCard weekPlan={weekPlan} onPlanUpdated={refetchAll} />
        )}

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

        {/* A224: live weather card — current location, today view only */}
        {!loading && !error && isViewingToday && <WeatherCard />}

        {/* A-COACH-V1a: AI coach entry point (bottom nav is full) */}
        {!loading && !error && isViewingToday && <CoachCard />}

        {/* A220: standalone "Focus di oggi" cue section above the day's cards */}
        {!loading && !error && dayPlan && !heroState && dayPlan.sessions.length > 0 && (
          <DailyCueBanner
            sessions={dayPlan.sessions}
            date={dayPlan.date}
            isToday={isViewingToday}
          />
        )}

        {/* A223: plan paused — replaces today's sessions until resumed */}
        {!loading && !error && isPaused && (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-6 text-center space-y-3">
            <p className="text-lg font-semibold text-amber-200">Plan paused</p>
            <p className="text-sm text-muted-foreground">
              Paused since {formatPauseDate(pausedSince)}. Your training is frozen
              right where you left off — no sessions are scheduled while paused.
            </p>
            <button
              type="button"
              onClick={() => router.push("/settings")}
              className="inline-flex h-11 w-full items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Resume plan
            </button>
          </div>
        )}

        {/* Day plan — suppressed when hero is active (A217 rest-day dedup) */}
        {!loading && !error && !isPaused && dayPlan && !heroState && (
          <DayCard
            day={dayPlan}
            gyms={gyms}
            homeEquipment={homeEquipment}
            outdoorRoutes={outdoorRoutesMap[dayPlan.date]}
            outdoorDurationMinutes={outdoorDurationMap[dayPlan.date]}
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

      {/* A235: one-time phase-transition celebration */}
      {isViewingToday && !loading && (
        <PhaseCelebration state={stateQuery.data} />
      )}

      {/* A239: milestone unlock toasts */}
      {isViewingToday && !loading && <MilestoneToast />}

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
