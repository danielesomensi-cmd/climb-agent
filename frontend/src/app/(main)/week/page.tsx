"use client";

import dynamic from "next/dynamic";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { TopBar } from "@/components/layout/top-bar";
import { WeekGrid } from "@/components/training/week-grid";
import { PausedBanner } from "@/components/training/paused-banner";
import { DayCard } from "@/components/training/day-card";
import { SkippedTestsCard } from "@/components/training/skipped-tests-card";
const QuickAddDialog = dynamic(() => import("@/components/training/quick-add-dialog").then((m) => m.QuickAddDialog), { ssr: false });
const ReplanDialog = dynamic(() => import("@/components/training/replan-dialog").then((m) => m.ReplanDialog), { ssr: false });
const MoveSessionDialog = dynamic(() => import("@/components/training/move-session-dialog").then((m) => m.MoveSessionDialog), { ssr: false });
const GymPickerDialog = dynamic(() => import("@/components/training/gym-picker-dialog").then((m) => m.GymPickerDialog), { ssr: false });
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { ChevronLeft, ChevronRight, ChevronDown, BarChart3, Check } from "lucide-react";
const FeedbackDialog = dynamic(() => import("@/components/training/feedback-dialog").then((m) => m.FeedbackDialog), { ssr: false });
import { useRouter } from "next/navigation";
import { applyOverride, quickAddSession, describeQuickAddAdjustments, quickAddHasFingerRisk, applyEvents, postFeedback, getOutdoorSpots, getOutdoorSessions, getOutdoorLogByDate, deleteFreeSession, getPitchLadder, setOutdoorPlan } from "@/lib/api";
import { ForceHardDialog } from "@/components/training/force-hard-dialog";
import { useUserState } from "@/lib/hooks/queries/use-user-state";
import { useWeekPlan } from "@/lib/hooks/queries/use-week-plan";
import { useFreeSessionsForDates } from "@/lib/hooks/queries/use-free-session";
import { useWeekEvents } from "@/lib/hooks/use-week-events";
import { queueOrWarn } from "@/lib/outbox-feedback";
import { queryKeys } from "@/lib/query-keys";
import { writeWeekCache } from "@/lib/week-cache";
import { buildDialogFeedbackItems, extractFeedbackExercises } from "@/lib/feedback-items";
import { resolveOutdoorLogTarget } from "@/lib/outdoor-log-target";
import { toast } from "sonner";
const OutdoorLogForm = dynamic(() => import("@/components/training/OutdoorLogForm"), { ssr: false });
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { WeekPlan, DayPlan, Macrocycle, OutdoorSpot, OutdoorRoute, OutdoorSession, Phase, OutdoorDayType, OutdoorPitchLadder } from "@/lib/types";
import { normalizeOtherActivities } from "@/lib/other-activity";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";

import { getPhaseName } from "@/lib/phase-labels";
import { completeOtherActivityEvent, removeOtherActivityEvent, removeOutdoorEvent, undoOtherActivityEvent, undoOutdoorEvent } from "@/lib/week-events";

/** Returns today's date in YYYY-MM-DD format */
function todayISO(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function WeekPage() {
  const { isLoaded: authReady } = useAuth();
  const qc = useQueryClient();
  const [weekNum, setWeekNum] = useState(0); // 0 = current week (also the cache key)
  const stateQuery = useUserState(authReady);
  const weekQuery = useWeekPlan(weekNum, authReady);
  const weekPlan = weekQuery.data?.week_plan ?? null;
  // B257: a past week with no saved plan fails closed (immutable, never
  // regenerated) — show an explicit message instead of a generic empty state.
  const pastWeekUnavailable = weekQuery.data?.past_week_unavailable ?? false;
  const phaseId = weekQuery.data?.phase_id ?? null;
  const displayWeekNum = weekQuery.data?.week_num ?? 1;
  const macrocycle = (stateQuery.data?.macrocycle as Macrocycle | undefined) ?? null;
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
  const loading = (stateQuery.isLoading || weekQuery.isLoading) && authReady;
  const queryError = stateQuery.error || weekQuery.error;
  const [error, setError] = useState<string | null>(null);

  /** Update the cached week plan after a mutation. */
  const updateWeekCache = useCallback(
    (newWeekPlan: WeekPlan) => {
      // A245 G-2 (F34): keeps week(0) and week(<server num>) in step.
      writeWeekCache(qc, weekNum, newWeekPlan);
    },
    [qc, weekNum],
  );

  /** F6 — done/skip/undo passano da qui: coda FIFO + snapshot fresco. */
  const runWeekEvents = useWeekEvents(weekNum);

  /** Force refetch of state + current week. */
  const refetchAll = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.state });
    qc.invalidateQueries({ queryKey: queryKeys.week(weekNum) });
    // A245 G-3 (F36): progression rewrites working_loads, so any resolved
    // session in cache is now showing pre-feedback numbers.
    qc.invalidateQueries({ queryKey: queryKeys.sessionResolveAll });
  }, [qc, weekNum]);
  const [replanDate, setReplanDate] = useState<string | null>(null);
  const [replanSessionIndex, setReplanSessionIndex] = useState<number | undefined>(undefined);
  const [quickAddDate, setQuickAddDate] = useState<string | null>(null);
  // A254: when a forced hard finger session needs explicit confirmation, this
  // holds the retry to run on confirm (dialog open = non-null).
  const [forceRetry, setForceRetry] = useState<(() => void) | null>(null);
  const [moveSession, setMoveSession] = useState<{
    date: string;
    slot: string;
    sessionId: string;
  } | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackSessionId, setFeedbackSessionId] = useState<string | null>(null);
  const [feedbackDate, setFeedbackDate] = useState<string | null>(null);
  const [changeGymDate, setChangeGymDate] = useState<string | null>(null);
  const [outdoorLogDate, setOutdoorLogDate] = useState<string | null>(null);
  const [outdoorEditDate, setOutdoorEditDate] = useState<string | null>(null);
  const [outdoorSpots, setOutdoorSpots] = useState<OutdoorSpot[]>([]);
  const [outdoorRoutesMap, setOutdoorRoutesMap] = useState<Record<string, OutdoorRoute[]>>({});
  const [outdoorDurationMap, setOutdoorDurationMap] = useState<Record<string, number>>({});
  const [outdoorLoadMap, setOutdoorLoadMap] = useState<Record<string, number>>({});
  const weekRouter = useRouter();
  const dayRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const handleDayClick = useCallback((date: string) => {
    dayRefs.current[date]?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }, []);

  // React Query handles fetching via useUserState + useWeekPlan(weekNum).
  // Changing weekNum swaps the cache key; RQ shows cached data instantly and refetches in background.

  // Fetch outdoor session routes for days marked "done"
  useEffect(() => {
    if (!weekPlan) return;
    const allDays = weekPlan.weeks.flatMap(w => w.days);
    const doneDates = allDays
      .filter(d => d.outdoor_session_status === "done")
      .map(d => d.date);
    if (doneDates.length === 0) {
      setOutdoorRoutesMap({});
      return;
    }
    const minDate = doneDates.sort()[0];
    getOutdoorSessions(minDate)
      .then(({ sessions }) => {
        const map: Record<string, OutdoorRoute[]> = {};
        const durMap: Record<string, number> = {};
        const loadMap: Record<string, number> = {};
        for (const s of sessions) {
          if (doneDates.includes(s.date)) {
            map[s.date] = [...(map[s.date] || []), ...s.routes];
            if (s.duration_minutes) durMap[s.date] = (durMap[s.date] ?? 0) + s.duration_minutes;
            if (s.load_score) loadMap[s.date] = (loadMap[s.date] ?? 0) + s.load_score;
          }
        }
        setOutdoorRoutesMap(map);
        setOutdoorDurationMap(durMap);
        setOutdoorLoadMap(loadMap);
      })
      .catch((err) => { console.error("Failed to load outdoor sessions:", err); });
  }, [weekPlan]);

  // A245 F-5 (F15): was a hand-rolled Promise.all over 7 days in an effect
  // keyed on [weekPlan]. structuralSharing is off, so every mutation produced a
  // fresh reference and refired all 7 requests, uncached, on every action —
  // and again on every today→week→today navigation. Now cache-backed, sharing
  // the same per-date keys as /today.
  const weekDates = useMemo(
    () => weekPlan?.weeks.flatMap((w) => w.days).map((d) => d.date) ?? [],
    [weekPlan],
  );
  const { sessions: allFreeSessions, isSettled: freeSessionsLoaded } =
    useFreeSessionsForDates(weekDates, !!weekPlan);
  const freeSessionsByDate = useMemo(() => {
    const map: Record<string, Array<Record<string, unknown>>> = {};
    for (const fs of allFreeSessions as Array<Record<string, unknown>>) {
      const d = fs.date as string | undefined;
      if (d) (map[d] ??= []).push(fs);
    }
    return map;
  }, [allFreeSessions]);

  const totalWeeks = macrocycle?.total_weeks ?? 0;

  /** Build array mapping week number (1-based) to phase info */
  const weekPhaseMap: Array<{ weekNum: number; phase: Phase }> = (() => {
    if (!macrocycle) return [];
    const result: Array<{ weekNum: number; phase: Phase }> = [];
    let w = 1;
    for (const phase of macrocycle.phases) {
      for (let i = 0; i < phase.duration_weeks; i++) {
        result.push({ weekNum: w, phase });
        w++;
      }
    }
    return result;
  })();

  /** Navigate directly to a specific week (React Query handles the fetch via cache key swap). */
  const handleGoToWeek = (wn: number) => {
    setWeekPickerOpen(false);
    if (wn === displayWeekNum) return;
    setWeekNum(wn);
  };

  const handlePrevWeek = () => {
    if (displayWeekNum <= 1) return;
    setWeekNum(displayWeekNum - 1);
  };

  const handleNextWeek = () => {
    if (totalWeeks > 0 && displayWeekNum >= totalWeeks) return;
    setWeekNum(displayWeekNum + 1);
  };

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
    // A254: capture the pre-add plan + args so a force retry re-runs from the
    // ORIGINAL plan (the cache now holds the eased session in that slot).
    const preAddPlan = weekPlan;
    const baseArgs = {
      session_id: rdata.session_id,
      target_date: quickAddDate,
      slot: rdata.slot,
      location: rdata.location,
      gym_id: rdata.gym_id,
      phase_id: phaseId ?? undefined,
    };
    try {
      const result = await quickAddSession({ ...baseArgs, week_plan: preAddPlan });
      updateWeekCache(result.week_plan);
      if (result.warnings?.length > 0) {
        setError(result.warnings.join("; "));
      }
      const note = describeQuickAddAdjustments(result.adjustments);
      if (note && result.adjustments?.length) {
        const doForce = async () => {
          try {
            const forced = await quickAddSession({ ...baseArgs, week_plan: preAddPlan, force: true });
            updateWeekCache(forced.week_plan);
            toast("Hard session added", { description: "Train smart — listen to your body.", duration: 6000 });
          } catch (err) {
            setError(err instanceof Error ? err.message : "Couldn't add the hard session.");
          }
        };
        // Finger downshift is injury protection → the action opens an explicit
        // confirm. A cap-only downshift is just volume → force straight away.
        const onForce = quickAddHasFingerRisk(result.adjustments)
          ? () => setForceRetry(() => doForce)
          : doForce;
        toast("Session adjusted", { description: note, duration: 10000, action: { label: "Add hard anyway", onClick: onForce } });
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

  /** Complete other activity with feedback + optional duration (B127/B276) */
  async function handleCompleteOtherActivity(date: string, slot: string | undefined, feedback: string, durationMinutes?: number) {
    if (!weekPlan) return;
    setError(null);
    try {
      const ev = completeOtherActivityEvent(date, slot, feedback, durationMinutes);
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
    setError(null);
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

  /** Undo other activity completion (B276: per-slot) */
  async function handleUndoOtherActivity(date: string, slot?: string) {
    if (!weekPlan) return;
    setError(null);
    try {
      const result = await applyEvents({
        events: [undoOtherActivityEvent(date, slot)],
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
    setError(null);
    try {
      const result = await applyEvents({
        events: [removeOtherActivityEvent(date, slot)],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove activity");
    }
  }

  /** Mark a session as completed + open feedback dialog */
  async function handleMarkDone(sessionId: string, date: string) {
    if (!weekPlan) return;
    setError(null);
    try {
      // F6 — serializzata + snapshot riletto dalla cache (vedi useWeekEvents).
      await runWeekEvents([{ event_type: "mark_done", date, session_ref: sessionId }]);

      // A207: custom sessions don't feed closed-loop/progression — skip feedback dialog.
      const day = weekPlan.weeks?.[0]?.days?.find((d) => d.date === date);
      const markedSession = day?.sessions.find((s) => s.session_id === sessionId);
      if (markedSession?.is_custom) return;

      setFeedbackSessionId(sessionId);
      setFeedbackDate(date);
      setFeedbackOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  }

  /** Mark a session as skipped */
  async function handleMarkSkipped(sessionId: string, date: string) {
    if (!weekPlan) return;
    setError(null);
    try {
      await runWeekEvents([{ event_type: "mark_skipped", date, session_ref: sessionId }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  }

  /** Undo a session's done/skipped status */
  async function handleUndoSession(sessionId: string, date: string) {
    if (!weekPlan) return;
    setError(null);
    try {
      await runWeekEvents([{ event_type: "mark_planned", date, session_ref: sessionId }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo");
    }
  }

  /** Remove a session from the day plan */
  async function handleRemoveSession(sessionId: string, date: string) {
    if (!weekPlan) return;
    setError(null);
    try {
      const result = await applyEvents({
        events: [{ event_type: "remove_session", date, session_ref: sessionId }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove session");
    }
  }

  /** Submit session feedback (B127: always includes duration) */
  async function handleFeedbackSubmit(
    feedback: Record<string, string>,
    durationMinutes: number,
    loads: Record<string, number>,
  ) {
    if (!feedbackSessionId || !feedbackDate) return;
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
          date: feedbackDate,
          session_id: feedbackSessionId,
          session_duration_seconds: durationMinutes * 60,
          actual: { exercise_feedback_v1: feedbackItems },
        },
        status: "done",
      };
      try {
        await postFeedback(body);
        // Re-fetch week plan so feedback_summary badges appear (cascade from progression)
        qc.invalidateQueries({ queryKey: queryKeys.weekAll });
      } catch {
        // A245 B-4 (F4) — see today/page.tsx: silently dropping feedback
        // desynchronises progression with no signal.
        queueOrWarn(body);
      }
    } finally {
      setFeedbackOpen(false);
      setFeedbackSessionId(null);
      setFeedbackDate(null);
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

  /** Handle outdoor quick-add from week view */
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

  /** After outdoor log, verify data persisted, then mark complete (D134) */
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
        events: [undoOutdoorEvent(date)],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo outdoor");
    }
  }

  /** Remove outdoor session */
  async function handleRemoveOutdoor(date: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [removeOutdoorEvent(date)],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove outdoor session");
    }
  }

  // A265 — pitch ladder: generate from the athlete's grades, or persist an edit.
  const [outdoorPlanBusy, setOutdoorPlanBusy] = useState<string | null>(null);

  async function handleGenerateOutdoorPlan(date: string, dayType: OutdoorDayType) {
    if (!weekPlan) return;
    setError(null);
    setOutdoorPlanBusy(date);
    try {
      const ladder = await getPitchLadder({ day_type: dayType });
      const result = await setOutdoorPlan({ date, plan: ladder, week_plan: weekPlan });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate the plan");
    } finally {
      setOutdoorPlanBusy(null);
    }
  }

  async function handleSetOutdoorPlan(date: string, plan: OutdoorPitchLadder | null) {
    if (!weekPlan) return;
    setError(null);
    setOutdoorPlanBusy(date);
    try {
      const result = await setOutdoorPlan({ date, plan, week_plan: weekPlan });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save the plan");
    } finally {
      setOutdoorPlanBusy(null);
    }
  }

  /** Edit outdoor session — fetch entry, open form in edit mode */
  const [weekPickerOpen, setWeekPickerOpen] = useState(false);
  const [outdoorEditData, setOutdoorEditData] = useState<OutdoorSession | null>(null);
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
    // Refresh outdoor routes map
    refetchAll();
  }

  const today = todayISO();
  const days: DayPlan[] = weekPlan?.weeks.flatMap((w) => w.days) ?? [];
  const discipline = (weekPlan?.profile_snapshot?.discipline as string) ?? "lead";
  const phaseLabel = phaseId
    ? getPhaseName(phaseId, discipline as "lead" | "boulder" | "all_round")
    : null;

  // Extract exercises + slot for the feedback dialog
  const feedbackDay = feedbackDate ? days.find((d) => d.date === feedbackDate) : null;
  const feedbackSessionObj = feedbackDay?.sessions.find((s) => s.session_id === feedbackSessionId);
  const feedbackSlot = feedbackSessionObj?.slot ?? "";

  const feedbackExercises = extractFeedbackExercises(
    feedbackSessionObj,
  );

  return (
    <>
      <TopBar title="Week" />

      <main className="mx-auto max-w-2xl space-y-6 p-4">
        <PausedBanner since={macrocycle?.pause?.active_since} />

        {/* Week navigation */}
        {!loading && weekPlan && (
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              onClick={handlePrevWeek}
              disabled={displayWeekNum <= 1}
            >
              <ChevronLeft className="size-4 mr-1" />
              Previous
            </Button>
            <div className="flex items-center gap-2 flex-wrap justify-center">
              <button
                type="button"
                onClick={() => totalWeeks > 0 && setWeekPickerOpen(true)}
                className="flex items-center gap-1 text-sm font-medium hover:text-primary transition-colors rounded-md px-2 py-1 -mx-2 -my-1 active:bg-muted"
              >
                Week {displayWeekNum}{totalWeeks > 0 ? ` / ${totalWeeks}` : ""}
                {totalWeeks > 0 && <ChevronDown className="size-3.5 opacity-60" />}
              </button>
              {phaseLabel && (
                <Badge variant="secondary">{phaseLabel}</Badge>
              )}
              {(weekPlan?.weekly_load_summary?.planned_load ?? weekPlan?.weekly_load_summary?.total_load) != null && (
                <Badge variant="outline">
                  Load: {weekPlan!.weekly_load_summary!.planned_load ?? weekPlan!.weekly_load_summary!.total_load}
                  {" · Done: "}
                  {freeSessionsLoaded
                    ? days.reduce((sum, d) =>
                        sum
                        + d.sessions
                            .filter((s) => s.status === "done")
                            .reduce((acc, s) => acc + (s.session_load_score ?? s.estimated_load_score ?? 0), 0)
                        + normalizeOtherActivities(d).reduce((a, oa) => a + (oa.load ?? 0), 0)
                        + ((freeSessionsByDate[d.date] ?? []).reduce((a, fs) => a + ((fs.load_score as number) ?? 0), 0))
                        + (outdoorLoadMap[d.date] ?? 0),
                        0,
                      )
                    : "—"}
                </Badge>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleNextWeek}
              disabled={totalWeeks > 0 && displayWeekNum >= totalWeeks}
            >
              Next
              <ChevronRight className="size-4 ml-1" />
            </Button>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

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

        {/* Weekly grid */}
        {!loading && !error && weekPlan && (
          <WeekGrid
            weekPlan={weekPlan}
            currentDate={today}
            onDayClick={handleDayClick}
          />
        )}

        {/* B297 (D211-F9): tests the planner couldn't fit this week */}
        {!loading && !error && weekPlan?.skipped_tests?.length ? (
          <SkippedTestsCard
            skipped={weekPlan.skipped_tests}
            weekKey={weekPlan.weeks[0]?.days[0]?.date ?? String(weekNum)}
          />
        ) : null}

        {/* Weekly report link */}
        {!loading && !error && weekPlan && (() => {
          const firstDay = weekPlan.weeks[0]?.days[0]?.date;
          return firstDay ? (
            <div className="flex justify-center">
              <Link href={`/reports/weekly?week_start=${firstDay}`}>
                <Button variant="outline" size="sm" className="gap-2">
                  <BarChart3 className="size-4" />
                  Weekly Report
                </Button>
              </Link>
            </div>
          ) : null;
        })()}

        {/* Detailed day list */}
        {!loading && !error && days.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Daily detail
            </h2>
            {days.map((day) => (
              <div
                key={day.date}
                ref={(el) => {
                  dayRefs.current[day.date] = el;
                }}
              >
                <DayCard
                  day={day}
                  gyms={gyms}
                  homeEquipment={homeEquipment}
                  outdoorRoutes={outdoorRoutesMap[day.date]}
                  outdoorDurationMinutes={outdoorDurationMap[day.date]}
                  outdoorLoadScore={outdoorLoadMap[day.date]}
                  weekPlan={weekPlan}
                  onSessionUpdated={(updatedPlan) => {
                    if (updatedPlan) { updateWeekCache(updatedPlan); } else { refetchAll(); }
                  }}
                  showActions
                  onMarkDone={(sessionId) => handleMarkDone(sessionId, day.date)}
                  onMarkSkipped={(sessionId) => handleMarkSkipped(sessionId, day.date)}
                  onUndo={(sessionId) => handleUndoSession(sessionId, day.date)}
                  onRemoveSession={(sessionId) => handleRemoveSession(sessionId, day.date)}
                  onReplan={(date, sessionIndex) => { setReplanDate(date); setReplanSessionIndex(sessionIndex); }}
                  onQuickAdd={(date) => setQuickAddDate(date)}
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
                  outdoorPlanGenerating={outdoorPlanBusy === day.date}
                  outdoorPlanSaving={outdoorPlanBusy === day.date}
                  onEditOutdoor={handleEditOutdoor}
                  onUndoOutdoor={handleUndoOutdoor}
                  onRemoveOutdoor={handleRemoveOutdoor}
                  freeSessions={freeSessionsByDate[day.date] as never}
                  onDeleteFreeSession={async (sessionId: string) => {
                    try {
                      await deleteFreeSession(sessionId);
                      // A245 F-5: cache-owned now — invalidate instead of
                      // hand-editing a local map that no longer exists.
                      qc.invalidateQueries({ queryKey: queryKeys.freeSessionHistoryAll });
                    } catch { /* ignore */ }
                  }}
                />
              </div>
            ))}
          </div>
        )}

        {/* No plan */}
        {!loading && !error && !weekPlan && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            {pastWeekUnavailable ? (
              <>
                <p className="font-medium">This week is in the past</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Past weeks are locked and never regenerated. There&apos;s no
                  saved plan for this week, so there&apos;s nothing to show here.
                </p>
              </>
            ) : (
              <p className="text-muted-foreground">
                No weekly plan available.
              </p>
            )}
          </div>
        )}
      </main>

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
          const date = quickAddDate || "";
          setQuickAddDate(null);
          weekRouter.push(`/free-session?context=standalone&date=${date}`);
        }}
        onApplyCustom={handleQuickAddCustomApply}
      />

      {/* A254: explicit confirm before forcing a hard finger session past the 48h gap */}
      <ForceHardDialog
        open={forceRetry !== null}
        onOpenChange={(v) => { if (!v) setForceRetry(null); }}
        onConfirm={() => { forceRetry?.(); setForceRetry(null); }}
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

      {/* Post-session feedback dialog */}
      <FeedbackDialog
        open={feedbackOpen}
        onClose={() => {
          setFeedbackOpen(false);
          setFeedbackSessionId(null);
          setFeedbackDate(null);
        }}
        onSubmit={handleFeedbackSubmit}
        exercises={feedbackExercises}
        slot={feedbackSlot}
      />

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
          {outdoorLogDate && (() => {
            const logDay = days.find((d) => d.date === outdoorLogDate);
            return (
              <OutdoorLogForm
                spots={outdoorSpots}
                defaultDate={outdoorLogDate}
                defaultSpotName={logDay?.outdoor_spot_name}
                defaultDiscipline={logDay?.outdoor_discipline}
                defaultGrade={currentGrade ?? undefined}
                onSuccess={handleOutdoorLogSuccess}
              />
            );
          })()}
        </DialogContent>
      </Dialog>

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

      {/* Week picker drawer (B139) */}
      <Drawer open={weekPickerOpen} onOpenChange={setWeekPickerOpen}>
        <DrawerContent>
          <DrawerHeader>
            <DrawerTitle>Go to week</DrawerTitle>
          </DrawerHeader>
          <div className="px-4 pb-6 max-h-[60vh] overflow-y-auto">
            <div className="space-y-1">
              {weekPhaseMap.map(({ weekNum: wn, phase }) => {
                const isCurrent = wn === displayWeekNum;
                const isPast = wn < displayWeekNum;
                const label = getPhaseName(phase.phase_id, discipline as "lead" | "boulder" | "all_round");
                return (
                  <button
                    key={wn}
                    type="button"
                    onClick={() => handleGoToWeek(wn)}
                    className={`w-full flex items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors ${
                      isCurrent
                        ? "bg-primary/15 text-primary font-medium"
                        : "hover:bg-muted active:bg-muted"
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      <span className={isPast && !isCurrent ? "text-muted-foreground" : ""}>
                        Week {wn}
                      </span>
                      <span className="text-muted-foreground">&mdash;</span>
                      <span className={isPast && !isCurrent ? "text-muted-foreground" : ""}>
                        {label}
                      </span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      {isPast && !isCurrent && (
                        <Check className="size-3.5 text-muted-foreground" />
                      )}
                      {isCurrent && (
                        <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                          current
                        </Badge>
                      )}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </DrawerContent>
      </Drawer>
    </>
  );
}
