"use client";

import { useState } from "react";
import { Calendar, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { WeeklyCheckinSheet } from "./weekly-checkin-sheet";
import { getTargetMonday } from "@/lib/weekly-checkin-dates";
import type { WeekPlan } from "@/lib/types";

/**
 * Returns true if any session in the given week plan is already completed.
 * Counts indoor sessions (status=done), outdoor (outdoor_session_status=done),
 * and other-activity entries (other_activity_status=completed). Once anything
 * in the week is logged, replanning the whole week is blocked (B245).
 */
function hasCompletedActivity(weekPlan: WeekPlan | null): boolean {
  if (!weekPlan) return false;
  const days = weekPlan.weeks?.[0]?.days ?? [];
  for (const day of days) {
    if (day.outdoor_session_status === "done") return true;
    if (day.other_activity_status === "completed") return true;
    for (const s of day.sessions ?? []) {
      if (s.status === "done") return true;
    }
  }
  return false;
}

interface Props {
  weekPlan: WeekPlan | null;
  onPlanUpdated: () => void;
}

export function WeeklyCheckinCard({ weekPlan, onPlanUpdated }: Props) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const targetMonday = getTargetMonday();

  // Tue–Sat: banner hidden entirely.
  if (!targetMonday) return null;

  // Monday: block when the current week already has completed activity.
  // Sunday: target is next week (freshly generated, no completed activity by definition).
  const isMonday = new Date().getDay() === 1;
  if (isMonday && hasCompletedActivity(weekPlan)) return null;

  const dismissKey = `checkin_dismissed_${targetMonday}`;
  if (dismissed) return null;

  function handleDismiss() {
    setDismissed(true);
    if (typeof window !== "undefined") {
      sessionStorage.setItem(dismissKey, "1");
    }
  }

  return (
    <>
      <Card
        className="border-primary/30 bg-primary/5 cursor-pointer hover:bg-primary/10 transition-colors"
        onClick={() => setSheetOpen(true)}
      >
        <CardContent className="flex items-center gap-3 py-4 px-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
            <Calendar className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold">Plan your week</p>
          </div>
          <ChevronRight className="h-5 w-5 text-muted-foreground" />
        </CardContent>
      </Card>

      <WeeklyCheckinSheet
        open={sheetOpen}
        nextWeekStart={targetMonday}
        onClose={() => {
          setSheetOpen(false);
          handleDismiss();
        }}
        onPlanUpdated={onPlanUpdated}
      />
    </>
  );
}
