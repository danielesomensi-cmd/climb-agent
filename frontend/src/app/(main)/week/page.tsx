"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { TopBar } from "@/components/layout/top-bar";
import { WeekGrid } from "@/components/training/week-grid";
import { DayCard } from "@/components/training/day-card";
import { QuickAddDialog } from "@/components/training/quick-add-dialog";
import { ReplanDialog } from "@/components/training/replan-dialog";
import { MoveSessionDialog } from "@/components/training/move-session-dialog";
import { GymPickerDialog } from "@/components/training/gym-picker-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, BarChart3 } from "lucide-react";
import { FeedbackDialog } from "@/components/training/feedback-dialog";
import { getWeek, getState, applyOverride, quickAddSession, applyEvents, postFeedback, getOutdoorSpots, getOutdoorSessions } from "@/lib/api";
import OutdoorLogForm from "@/components/training/OutdoorLogForm";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { WeekPlan, DayPlan, Macrocycle, OutdoorSpot, OutdoorRoute } from "@/lib/types";

/** English labels for phase names */
const PHASE_LABELS: Record<string, string> = {
  base: "Base",
  strength_power: "Strength & Power",
  power_endurance: "Power Endurance",
  performance: "Performance",
  deload: "Deload",
};

/** Returns today's date in YYYY-MM-DD format */
function todayISO(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function WeekPage() {
  const [weekPlan, setWeekPlan] = useState<WeekPlan | null>(null);
  const [phaseId, setPhaseId] = useState<string | null>(null);
  const [weekNum, setWeekNum] = useState(0); // 0 = current week
  const [displayWeekNum, setDisplayWeekNum] = useState(1);
  const [macrocycle, setMacrocycle] = useState<Macrocycle | null>(null);
  const [gyms, setGyms] = useState<
    Array<{ name: string; equipment: string[] }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
  const [outdoorSpots, setOutdoorSpots] = useState<OutdoorSpot[]>([]);
  const [currentGrade, setCurrentGrade] = useState<string | null>(null);
  const [outdoorRoutesMap, setOutdoorRoutesMap] = useState<Record<string, OutdoorRoute[]>>({});
  const dayRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const handleDayClick = useCallback((date: string) => {
    dayRefs.current[date]?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }, []);

  const fetchWeek = useCallback(async (wn: number) => {
    setLoading(true);
    setError(null);
    try {
      const weekData = await getWeek(wn);
      setWeekPlan(weekData.week_plan);
      setPhaseId(weekData.phase_id);
      setDisplayWeekNum(weekData.week_num);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchInitial = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [weekData, stateData] = await Promise.all([
        getWeek(0),
        getState(),
      ]);
      setWeekPlan(weekData.week_plan);
      setPhaseId(weekData.phase_id);
      setDisplayWeekNum(weekData.week_num);
      setMacrocycle(stateData.macrocycle ?? null);
      const goal = stateData.goal as { current_grade?: string } | undefined;
      if (goal?.current_grade) setCurrentGrade(goal.current_grade);
      const eq = stateData.equipment as Record<string, unknown> | undefined;
      setGyms(
        (eq?.gyms as Array<{ name: string; equipment: string[] }>) ?? []
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInitial();
  }, [fetchInitial]);

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
        for (const s of sessions) {
          if (doneDates.includes(s.date)) {
            map[s.date] = [...(map[s.date] || []), ...s.routes];
          }
        }
        setOutdoorRoutesMap(map);
      })
      .catch(() => {});
  }, [weekPlan]);

  const totalWeeks = macrocycle?.total_weeks ?? 0;

  const handlePrevWeek = () => {
    if (displayWeekNum <= 1) return;
    const newWn = displayWeekNum - 1;
    setWeekNum(newWn);
    fetchWeek(newWn);
  };

  const handleNextWeek = () => {
    if (totalWeeks > 0 && displayWeekNum >= totalWeeks) return;
    const newWn = displayWeekNum + 1;
    setWeekNum(newWn);
    fetchWeek(newWn);
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

  /** Complete other activity with feedback */
  async function handleCompleteOtherActivity(date: string, feedback: string) {
    if (!weekPlan) return;
    setError(null);
    try {
      const result = await applyEvents({
        events: [{ event_type: "complete_other_activity", date, feedback }],
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to complete activity");
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
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to undo");
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
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
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
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove session");
    }
  }

  /** Submit session feedback */
  async function handleFeedbackSubmit(feedback: Record<string, string>) {
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
          actual: { exercise_feedback_v1: feedbackItems },
        },
        status: "done",
      });
      // Re-fetch week plan so feedback_summary badges appear
      const weekData = await getWeek(displayWeekNum);
      setWeekPlan(weekData.week_plan);
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
      setWeekPlan(result.week_plan);
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

  /** Open outdoor log form */
  function handleLogOutdoor(date: string) {
    setOutdoorLogDate(date);
    getOutdoorSpots().then((data) => setOutdoorSpots(data.spots)).catch(() => {});
  }

  /** After outdoor log, mark complete */
  async function handleOutdoorLogSuccess() {
    if (!weekPlan || !outdoorLogDate) return;
    try {
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

  /** Remove outdoor session */
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

  const today = todayISO();
  const days: DayPlan[] = weekPlan?.weeks.flatMap((w) => w.days) ?? [];
  const phaseLabel = phaseId
    ? PHASE_LABELS[phaseId] ?? phaseId.replace(/_/g, " ")
    : null;

  // Extract exercises for the feedback dialog
  const feedbackExercises: Array<{ exercise_id: string; name: string }> =
    (() => {
      if (!feedbackSessionId || !feedbackDate) return [];
      const day = days.find((d) => d.date === feedbackDate);
      if (!day) return [];
      const session = day.sessions.find(
        (s) => s.session_id === feedbackSessionId
      );
      if (!session?.resolved) return [];
      const resolved = session.resolved as Record<string, unknown>;
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
              <span className="text-sm font-medium">
                Week {displayWeekNum}{totalWeeks > 0 ? ` / ${totalWeeks}` : ""}
              </span>
              {phaseLabel && (
                <Badge variant="secondary">{phaseLabel}</Badge>
              )}
              {weekPlan?.weekly_load_summary?.total_load != null && (
                <Badge variant="outline">
                  Load: {weekPlan.weekly_load_summary.total_load}
                  {" · Done: "}
                  {days.reduce((sum, d) =>
                    sum
                    + d.sessions
                        .filter((s) => s.status === "done")
                        .reduce((acc, s) => acc + (s.estimated_load_score ?? 0), 0)
                    + (d.other_activity_load ?? 0),
                    0,
                  )}
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
        {error && !loading && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center">
            <p className="text-sm text-destructive">{error}</p>
            <button
              onClick={fetchInitial}
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
              <a href={`/reports/weekly?week_start=${firstDay}`}>
                <Button variant="outline" size="sm" className="gap-2">
                  <BarChart3 className="size-4" />
                  Weekly Report
                </Button>
              </a>
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
                  outdoorRoutes={outdoorRoutesMap[day.date]}
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
                  onLogOutdoor={handleLogOutdoor}
                  onUndoOutdoor={handleUndoOutdoor}
                  onRemoveOutdoor={handleRemoveOutdoor}
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
    </>
  );
}
