"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { TopBar } from "@/components/layout/top-bar";
import { DayCard } from "@/components/training/day-card";
import { FeedbackDialog } from "@/components/training/feedback-dialog";
import { QuickAddDialog } from "@/components/training/quick-add-dialog";
import { ReplanDialog } from "@/components/training/replan-dialog";
import { MoveSessionDialog } from "@/components/training/move-session-dialog";
import { GymPickerDialog } from "@/components/training/gym-picker-dialog";
import { WeeklyCheckinCard } from "@/components/training/weekly-checkin-card";
import { WeekProgressBar } from "@/components/training/week-progress-bar";
import { getWeek, getState, applyEvents, postFeedback, getDailyQuote, applyOverride, quickAddSession, getOutdoorSpots, getOutdoorSessions, getOutdoorLogByDate, getFreeSessionHistory, deleteFreeSession } from "@/lib/api";
import OutdoorLogForm from "@/components/training/OutdoorLogForm";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { WeekPlan, DayPlan, Quote, OutdoorSpot, OutdoorRoute, OutdoorSession } from "@/lib/types";

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
  const dateParam = searchParams.get("date");
  const targetDate = dateParam || todayISO();
  const isViewingToday = targetDate === todayISO();

  const [weekPlan, setWeekPlan] = useState<WeekPlan | null>(null);
  const [gyms, setGyms] = useState<
    Array<{ name: string; equipment: string[] }>
  >([]);
  const [homeEquipment, setHomeEquipment] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackSessionId, setFeedbackSessionId] = useState<string | null>(
    null
  );
  const [quote, setQuote] = useState<Quote | null>(null);
  const [phaseId, setPhaseId] = useState<string | null>(null);
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
  const [currentGrade, setCurrentGrade] = useState<string | null>(null);
  const [outdoorRoutesMap, setOutdoorRoutesMap] = useState<Record<string, OutdoorRoute[]>>({});
  const [outdoorDurationMap, setOutdoorDurationMap] = useState<Record<string, number>>({});
  const [freeSessions, setFreeSessions] = useState<Array<Record<string, unknown>>>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [weekData, stateData] = await Promise.all([
        getWeek(0),
        getState(),
      ]);
      setWeekPlan(weekData.week_plan);
      setPhaseId(weekData.phase_id ?? null);
      const goal = stateData.goal as { current_grade?: string } | undefined;
      if (goal?.current_grade) setCurrentGrade(goal.current_grade);
      const eq = stateData.equipment as Record<string, unknown> | undefined;
      setGyms(
        (eq?.gyms as Array<{ name: string; equipment: string[] }>) ?? []
      );
      setHomeEquipment((eq?.home as string[]) ?? []);

      // Retry pending guided session feedback + cleanup old sessions
      if (typeof window !== "undefined") {
        const userId = window.Clerk?.session ? "clerk" : "";
        const prefix = `guided_session_${userId}_`;
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
              const feedbackItems = saved.exercises.map((ex: Record<string, unknown>) => {
                const item: Record<string, unknown> = {
                  exercise_id: ex.exerciseId,
                  feedback_label: ex.feedbackLabel,
                  completed: ex.status === "done",
                };
                if (ex.usedLoadKg != null) item.used_external_load_kg = ex.usedLoadKg;
                if (ex.usedGrade) item.used_grade = ex.usedGrade;
                return item;
              });
              await postFeedback({
                log_entry: {
                  date: saved.date ?? "",
                  session_id: saved.sessionId ?? "",
                  actual: { exercise_feedback_v1: feedbackItems },
                },
                status: "done",
              }).then(() => {
                localStorage.removeItem(key);
              }).catch(() => {
                // Leave in localStorage for next retry
              });
            }
          } catch {
            // Ignore malformed localStorage entries
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  // B155: gate on Clerk readiness to avoid 422 race on first load
  useEffect(() => {
    if (!authReady) return;
    fetchData();
  }, [fetchData, authReady]);

  // Fetch daily quote once the week plan is loaded
  useEffect(() => {
    if (!weekPlan) return;
    const phaseId = (weekPlan.profile_snapshot as Record<string, unknown> | undefined)?.phase_id as string | undefined;
    const sessionIds = dayPlan?.sessions.map((s) => s.session_id) ?? [];

    let context = "general";
    if (phaseId === "deload") {
      context = "deload";
    } else if (
      sessionIds.some((id) =>
        ["strength_long", "power_contact", "finger_strength"].some((kw) => id.includes(kw))
      )
    ) {
      context = "hard_day";
    }

    getDailyQuote(context).then(setQuote).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weekPlan]);

  // Fetch outdoor session routes for days marked "done"
  useEffect(() => {
    if (!weekPlan) return;
    const days = weekPlan.weeks.flatMap(w => w.days);
    const doneDates = days
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
        for (const s of sessions) {
          if (doneDates.includes(s.date)) {
            map[s.date] = [...(map[s.date] || []), ...s.routes];
            if (s.duration_minutes) durMap[s.date] = (durMap[s.date] ?? 0) + s.duration_minutes;
          }
        }
        setOutdoorRoutesMap(map);
        setOutdoorDurationMap(durMap);
      })
      .catch(() => {});
  }, [weekPlan]);

  // Fetch free sessions for target date (A138)
  useEffect(() => {
    if (!targetDate) return;
    getFreeSessionHistory(targetDate)
      .then((data) => setFreeSessions(data.sessions))
      .catch(() => setFreeSessions([]));
  }, [targetDate, weekPlan]); // re-fetch when weekPlan changes (after save)

  /** Find target day in the weekly plan */
  const dayPlan: DayPlan | undefined = weekPlan?.weeks
    .flatMap((w) => w.days)
    .find((d) => d.date === targetDate);

  /** First day after target with sessions */
  const nextTrainingDay: DayPlan | undefined = weekPlan?.weeks
    .flatMap((w) => w.days)
    .find((d) => d.date > targetDate && d.sessions.length > 0);

  /** Mark a session as completed */
  async function handleMarkDone(sessionId: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [
          {
            event_type: "mark_done",
            date: targetDate,
            session_ref: sessionId,
          },
        ],
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);

      // Open feedback dialog
      setFeedbackSessionId(sessionId);
      setFeedbackOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  }

  /** Mark a session as skipped */
  async function handleMarkSkipped(sessionId: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [
          {
            event_type: "mark_skipped",
            date: targetDate,
            session_ref: sessionId,
          },
        ],
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  }

  /** Undo a session's done/skipped status */
  async function handleUndo(sessionId: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [
          {
            event_type: "mark_planned",
            date: targetDate,
            session_ref: sessionId,
          },
        ],
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo");
    }
  }

  /** Complete an other-activity (complementary sport) with feedback + optional duration */
  async function handleCompleteOtherActivity(date: string, feedback: string, durationMinutes?: number) {
    if (!weekPlan) return;
    try {
      const ev: Record<string, unknown> = {
        event_type: "complete_other_activity",
        date,
        feedback,
      };
      if (durationMinutes != null) ev.duration_minutes = durationMinutes;
      const result = await applyEvents({
        events: [ev],
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to complete activity");
    }
  }

  /** Edit a completed other-activity (B127) */
  async function handleEditOtherActivity(date: string, fields: { activity_name?: string; feedback?: string; duration_minutes?: number }) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [{ event_type: "edit_other_activity", date, ...fields }],
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to edit activity");
    }
  }

  /** Undo other-activity completion */
  async function handleUndoOtherActivity(date: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [
          {
            event_type: "undo_other_activity",
            date,
          },
        ],
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo");
    }
  }

  /** Remove other activity from a day */
  async function handleRemoveOtherActivity(date: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [{ event_type: "remove_other_activity", date }],
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add activity");
    } finally {
      setQuickAddDate(null);
    }
  }

  /** Open the outdoor log form for a day */
  function handleLogOutdoor(date: string) {
    setOutdoorLogDate(date);
    getOutdoorSpots().then((data) => setOutdoorSpots(data.spots)).catch(() => {});
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
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
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
      getOutdoorSpots().then((d) => setOutdoorSpots(d.spots)).catch(() => {});
    } catch {
      setError("No outdoor session found for this date");
    }
  }

  async function handleEditOutdoorSuccess() {
    setOutdoorEditDate(null);
    setOutdoorEditData(null);
    await fetchData();
  }

  /** Submit session feedback (B127: always includes duration) */
  async function handleFeedbackSubmit(feedback: Record<string, string>, durationMinutes: number, durationSource: "user_reported" | "estimated") {
    if (!feedbackSessionId) return;
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
          date: targetDate,
          session_id: feedbackSessionId,
          session_duration_seconds: durationMinutes * 60,
          duration_source: durationSource,
          actual: {
            exercise_feedback_v1: feedbackItems,
          },
        },
        status: "done",
      });
      // Re-fetch week plan so feedback_summary badges appear immediately
      await fetchData();
    } catch {
      // Non-critical feedback, don't block the UX
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

  const feedbackExercises: Array<{ exercise_id: string; name: string }> =
    (() => {
      if (!feedbackSession?.resolved) return [];
      const resolved = feedbackSession.resolved as Record<string, unknown>;
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

  const title = isViewingToday ? "Today" : formatDateSubtitle(targetDate);
  const subtitle = isViewingToday
    ? formatDateSubtitle(targetDate)
    : undefined;

  return (
    <>
      <TopBar title={title} subtitle={subtitle} />

      {/* Decorative climber illustration — fixed to bottom of viewport */}
      <div
        className="pointer-events-none fixed inset-x-0 bottom-0 z-0"
        style={{ height: "55vh" }}
        aria-hidden="true"
      >
        {/* Gradient fade: transparent at bottom → background color at top */}
        <div
          className="absolute inset-0 z-10"
          style={{
            background:
              "linear-gradient(to bottom, var(--background) 0%, transparent 40%)",
          }}
        />
        {/* Image: object-position crops out the "CLIMB AGENT" text at top */}
        <img
          src="/daniclimb.jpg"
          alt=""
          className="h-full w-full object-cover opacity-20 dark:opacity-15"
          style={{ objectPosition: "center 25%" }}
        />
      </div>

      <main className="relative z-10 mx-auto max-w-2xl space-y-4 p-4">
        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{error}</p>
            <button
              onClick={fetchData}
              className="mt-2 text-sm font-medium text-primary underline"
            >
              Retry
            </button>
          </div>
        )}


        {/* No macrocycle — prompt to start onboarding */}
        {!loading && !error && !weekPlan && (
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

        {/* Week progress bar */}
        {!loading && !error && weekPlan && (
          <WeekProgressBar weekPlan={weekPlan} />
        )}

        {/* Weekly check-in card (Sunday / Monday morning grace) */}
        {!loading && !error && isViewingToday && (
          <WeeklyCheckinCard onPlanUpdated={fetchData} />
        )}

        {/* Day plan */}
        {!loading && !error && dayPlan && (
          <DayCard
            day={dayPlan}
            gyms={gyms}
            homeEquipment={homeEquipment}
            outdoorRoutes={outdoorRoutesMap[dayPlan.date]}
            outdoorDurationMinutes={outdoorDurationMap[dayPlan.date]}
            weekPlan={weekPlan}
            onSessionUpdated={(updatedPlan) => {
              // B153d: use response data when available to avoid 422 reload race
              if (updatedPlan) { setWeekPlan(updatedPlan); } else { fetchData(); }
            }}
            onMarkDone={handleMarkDone}
            onMarkSkipped={handleMarkSkipped}
            onUndo={handleUndo}
            onRemoveSession={handleRemoveSession}
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
            freeSessions={freeSessions as never}
            onDeleteFreeSession={async (sessionId: string) => {
              try {
                await deleteFreeSession(sessionId);
                setFreeSessions((prev) => prev.filter((s) => s.id !== sessionId));
              } catch { /* ignore */ }
            }}
          />
        )}

        {/* No sessions (rest day) */}
        {!loading && !error && dayPlan && dayPlan.sessions.length === 0 && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-muted-foreground">
              No sessions {isViewingToday ? "today" : "on this day"}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Enjoy the rest and recover for the next session.
            </p>
            {nextTrainingDay && (
              <Link
                href={`/today?date=${nextTrainingDay.date}`}
                className="mt-3 inline-block text-sm font-medium text-primary underline"
              >
                Preview next training day ({nextTrainingDay.weekday})
              </Link>
            )}
          </div>
        )}

        {/* Weekly plan not found for this date */}
        {!loading && !error && !dayPlan && weekPlan && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-muted-foreground">
              No sessions {isViewingToday ? "today" : "on this day"}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              No plan found for this date.
            </p>
            {nextTrainingDay && (
              <Link
                href={`/today?date=${nextTrainingDay.date}`}
                className="mt-3 inline-block text-sm font-medium text-primary underline"
              >
                Preview next training day ({nextTrainingDay.weekday})
              </Link>
            )}
          </div>
        )}

        {/* Daily motivational quote */}
        {quote && !loading && (
          <div className="pt-4 pb-2">
            <p className="text-sm italic text-muted-foreground">
              &ldquo;{quote.text}&rdquo;
            </p>
            <p className="text-xs text-muted-foreground text-right mt-1">
              — {quote.author}
            </p>
          </div>
        )}
      </main>

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
