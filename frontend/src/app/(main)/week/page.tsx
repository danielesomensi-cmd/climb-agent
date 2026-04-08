"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { TopBar } from "@/components/layout/top-bar";
import { WeekGrid } from "@/components/training/week-grid";
import { DayCard } from "@/components/training/day-card";
import { QuickAddDialog } from "@/components/training/quick-add-dialog";
import { ReplanDialog } from "@/components/training/replan-dialog";
import { MoveSessionDialog } from "@/components/training/move-session-dialog";
import { GymPickerDialog } from "@/components/training/gym-picker-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { ChevronLeft, ChevronRight, ChevronDown, BarChart3, Check } from "lucide-react";
import { FeedbackDialog } from "@/components/training/feedback-dialog";
import { useRouter } from "next/navigation";
import { applyOverride, quickAddSession, applyEvents, postFeedback, getOutdoorSpots, getOutdoorSessions, getOutdoorLogByDate, getFreeSessionHistory, deleteFreeSession } from "@/lib/api";
import { useUserState } from "@/lib/hooks/queries/use-user-state";
import { useWeekPlan } from "@/lib/hooks/queries/use-week-plan";
import { queryKeys } from "@/lib/query-keys";
import OutdoorLogForm from "@/components/training/OutdoorLogForm";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { WeekPlan, DayPlan, Macrocycle, OutdoorSpot, OutdoorRoute, OutdoorSession, Phase } from "@/lib/types";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";

import { getPhaseName } from "@/lib/phase-labels";

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
      qc.setQueryData(queryKeys.week(weekNum), (old: { week_num: number; phase_id?: string | null; week_plan: WeekPlan } | undefined) =>
        old ? { ...old, week_plan: newWeekPlan } : { week_num: weekNum, week_plan: newWeekPlan },
      );
    },
    [qc, weekNum],
  );

  /** Force refetch of state + current week. */
  const refetchAll = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.state });
    qc.invalidateQueries({ queryKey: queryKeys.week(weekNum) });
  }, [qc, weekNum]);
  const [replanDate, setReplanDate] = useState<string | null>(null);
  const [replanSessionIndex, setReplanSessionIndex] = useState<number | undefined>(undefined);
  const [quickAddDate, setQuickAddDate] = useState<string | null>(null);
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
  const [freeSessionsByDate, setFreeSessionsByDate] = useState<Record<string, Array<Record<string, unknown>>>>({});
  const [freeSessionsLoaded, setFreeSessionsLoaded] = useState(false);
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

  // Fetch free sessions for all days in the week (A138)
  useEffect(() => {
    if (!weekPlan) return;
    setFreeSessionsLoaded(false);
    const allDays = weekPlan.weeks.flatMap(w => w.days);
    const dates = allDays.map(d => d.date);
    if (dates.length === 0) { setFreeSessionsLoaded(true); return; }
    Promise.all(dates.map(d => getFreeSessionHistory(d).then(r => ({ date: d, sessions: r.sessions })).catch(() => ({ date: d, sessions: [] }))))
      .then((results) => {
        const map: Record<string, Array<Record<string, unknown>>> = {};
        for (const r of results) {
          if (r.sessions.length > 0) map[r.date] = r.sessions;
        }
        setFreeSessionsByDate(map);
        setFreeSessionsLoaded(true);
      });
  }, [weekPlan]);

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

  /** Complete other activity with feedback + optional duration (B127) */
  async function handleCompleteOtherActivity(date: string, feedback: string, durationMinutes?: number) {
    if (!weekPlan) return;
    setError(null);
    try {
      const ev: Record<string, unknown> = { event_type: "complete_other_activity", date, feedback };
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

  /** Edit a completed other-activity (B127) */
  async function handleEditOtherActivity(date: string, fields: { activity_name?: string; feedback?: string; duration_minutes?: number }) {
    if (!weekPlan) return;
    setError(null);
    try {
      const result = await applyEvents({
        events: [{ event_type: "edit_other_activity", date, ...fields }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to edit activity");
    }
  }

  /** Undo other activity completion */
  async function handleUndoOtherActivity(date: string) {
    if (!weekPlan) return;
    setError(null);
    try {
      const result = await applyEvents({
        events: [{ event_type: "undo_other_activity", date }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo");
    }
  }

  /** Remove other activity from a day */
  async function handleRemoveOtherActivity(date: string) {
    if (!weekPlan) return;
    setError(null);
    try {
      const result = await applyEvents({
        events: [{ event_type: "remove_other_activity", date }],
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
      const result = await applyEvents({
        events: [{ event_type: "mark_done", date, session_ref: sessionId }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
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
      const result = await applyEvents({
        events: [{ event_type: "mark_skipped", date, session_ref: sessionId }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  }

  /** Undo a session's done/skipped status */
  async function handleUndoSession(sessionId: string, date: string) {
    if (!weekPlan) return;
    setError(null);
    try {
      const result = await applyEvents({
        events: [{ event_type: "mark_planned", date, session_ref: sessionId }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
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
  async function handleFeedbackSubmit(feedback: Record<string, string>, durationMinutes: number, durationSource: "user_reported" | "estimated") {
    if (!feedbackSessionId || !feedbackDate) return;
    try {
      const feedbackItems = Object.entries(feedback).map(
        ([exercise_id, feedback_label]) => ({
          exercise_id,
          feedback_label,
          completed: true,
        })
      );
      await postFeedback({
        log_entry: {
          date: feedbackDate,
          session_id: feedbackSessionId,
          session_duration_seconds: durationMinutes * 60,
          duration_source: durationSource,
          actual: { exercise_feedback_v1: feedbackItems },
        },
        status: "done",
      });
      // Re-fetch week plan so feedback_summary badges appear (cascade from progression)
      qc.invalidateQueries({ queryKey: queryKeys.weekAll });
    } catch {
      // Non-critical
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
    const spotsData = await getOutdoorSpots().catch(() => ({ spots: [] }));
    setOutdoorSpots(spotsData.spots);
    try {
      const existing = await getOutdoorLogByDate(date);
      // Session already exists for this date → open edit dialog
      setOutdoorEditData(existing.session);
      setOutdoorEditDate(date);
    } catch {
      // No session yet → open new log dialog
      setOutdoorLogDate(date);
    }
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
        events: [{ event_type: "undo_outdoor", date }],
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
        events: [{ event_type: "remove_outdoor", date }],
        week_plan: weekPlan,
      });
      updateWeekCache(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove outdoor session");
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

  const feedbackExercises: Array<{ exercise_id: string; name: string }> =
    (() => {
      if (!feedbackSessionObj?.resolved) return [];
      const resolved = feedbackSessionObj.resolved as Record<string, unknown>;
      const resolvedSession = resolved.resolved_session as
        | Record<string, unknown>
        | undefined;
      const instances = (resolvedSession?.exercise_instances ?? []) as Array<
        Record<string, unknown>
      >;
      return instances.map((ex) => ({
        exercise_id: (ex.exercise_id as string) ?? "",
        name:
          (ex.name as string) ??
          (ex.exercise_id as string)?.replace(/_/g, " ") ??
          "",
      }));
    })();

  return (
    <>
      <TopBar title="Week" />

      <main className="mx-auto max-w-2xl space-y-6 p-4">
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
                        + (d.other_activity_load ?? 0)
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
                  onEditOutdoor={handleEditOutdoor}
                  onUndoOutdoor={handleUndoOutdoor}
                  onRemoveOutdoor={handleRemoveOutdoor}
                  freeSessions={freeSessionsByDate[day.date] as never}
                  onDeleteFreeSession={async (sessionId: string) => {
                    try {
                      await deleteFreeSession(sessionId);
                      setFreeSessionsByDate((prev) => {
                        const copy = { ...prev };
                        for (const d in copy) {
                          copy[d] = copy[d].filter((s) => s.id !== sessionId);
                          if (copy[d].length === 0) delete copy[d];
                        }
                        return copy;
                      });
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
            <p className="text-muted-foreground">
              No weekly plan available.
            </p>
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
