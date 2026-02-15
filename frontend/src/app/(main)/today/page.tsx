"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { TopBar } from "@/components/layout/top-bar";
import { DayCard } from "@/components/training/day-card";
import { FeedbackDialog } from "@/components/training/feedback-dialog";
import { getWeek, applyEvents, postFeedback } from "@/lib/api";
import type { WeekPlan, DayPlan } from "@/lib/types";

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

/** Formats today's date as "Monday 15 February" */
function formatTodaySubtitle(): string {
  const d = new Date();
  const dayName = WEEKDAY_FULL[d.getDay()] ?? "";
  const dayNum = d.getDate();
  const monthName = MONTH_EN[d.getMonth()] ?? "";
  return `${dayName} ${dayNum} ${monthName}`;
}

export default function TodayPage() {
  const [weekPlan, setWeekPlan] = useState<WeekPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackSessionId, setFeedbackSessionId] = useState<string | null>(null);

  const fetchWeek = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWeek(0);
      setWeekPlan(data.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWeek();
  }, [fetchWeek]);

  /** Find today's entry in the weekly plan */
  const today = todayISO();
  const todayPlan: DayPlan | undefined = weekPlan?.weeks
    .flatMap((w) => w.days)
    .find((d) => d.date === today);

  /** First day after today with sessions */
  const nextTrainingDay: DayPlan | undefined = weekPlan?.weeks
    .flatMap((w) => w.days)
    .find((d) => d.date > today && d.sessions.length > 0);

  /** Mark a session as completed */
  async function handleMarkDone(sessionId: string) {
    if (!weekPlan) return;
    try {
      const result = await applyEvents({
        events: [
          {
            type: "session_done",
            date: today,
            session_id: sessionId,
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
            type: "session_skipped",
            date: today,
            session_id: sessionId,
          },
        ],
        week_plan: weekPlan,
      });
      setWeekPlan(result.week_plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  }

  /** Submit session feedback */
  async function handleFeedbackSubmit(feedback: Record<string, string>) {
    if (!feedbackSessionId) return;
    try {
      await postFeedback({
        log_entry: {
          date: today,
          session_id: feedbackSessionId,
          exercise_feedback: feedback,
        },
        status: "done",
      });
    } catch {
      // Non-critical feedback, don't block the UX
    } finally {
      setFeedbackOpen(false);
      setFeedbackSessionId(null);
    }
  }

  // Exercises for the feedback dialog (simplified: using session_id as placeholder)
  const feedbackExercises = feedbackSessionId
    ? [{ exercise_id: feedbackSessionId, name: feedbackSessionId.replace(/_/g, " ") }]
    : [];

  return (
    <>
      <TopBar title="Today" subtitle={formatTodaySubtitle()} />

      <main className="mx-auto max-w-2xl space-y-4 p-4">
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
              onClick={fetchWeek}
              className="mt-2 text-sm font-medium text-primary underline"
            >
              Retry
            </button>
          </div>
        )}

        {/* Today's plan */}
        {!loading && !error && todayPlan && (
          <DayCard
            day={todayPlan}
            onMarkDone={handleMarkDone}
            onMarkSkipped={handleMarkSkipped}
          />
        )}

        {/* No sessions today (rest day) */}
        {!loading && !error && todayPlan && todayPlan.sessions.length === 0 && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-muted-foreground">
              No sessions today
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Enjoy the rest and recover for the next session.
            </p>
            {nextTrainingDay && (
              <Link href="/week" className="mt-3 inline-block text-sm font-medium text-primary underline">
                Preview next training day ({nextTrainingDay.weekday})
              </Link>
            )}
          </div>
        )}

        {/* Weekly plan not found for today */}
        {!loading && !error && !todayPlan && weekPlan && (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <p className="text-muted-foreground">
              No sessions today
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              No plan found for today.
            </p>
            {nextTrainingDay && (
              <Link href="/week" className="mt-3 inline-block text-sm font-medium text-primary underline">
                Preview next training day ({nextTrainingDay.weekday})
              </Link>
            )}
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
      />
    </>
  );
}
