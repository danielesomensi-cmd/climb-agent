"use client";

import { useState, useSyncExternalStore } from "react";
import dynamic from "next/dynamic";
import { Calendar, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { getTargetMonday } from "@/lib/weekly-checkin-dates";
import type { WeekPlan } from "@/lib/types";
import { normalizeOtherActivities } from "@/lib/other-activity";
import {
  readCheckinDismissed,
  subscribeCheckinDismissed,
  writeCheckinDismissed,
} from "@/lib/checkin-dismiss";

// B396 — opens only on tap (and only on Sunday/Monday): not part of the
// /today first load any more. Mounted on the first tap, see below.
const WeeklyCheckinSheet = dynamic(
  () => import("./weekly-checkin-sheet").then((m) => m.WeeklyCheckinSheet),
  { ssr: false },
);

/**
 * Returns true if any session in the given week plan is already completed.
 * Counts indoor sessions (status=done), outdoor (outdoor_session_status=done),
 * and other-activity entries (status=completed). Once anything
 * in the week is logged, replanning the whole week is blocked (B245).
 */
function hasCompletedActivity(weekPlan: WeekPlan | null): boolean {
  if (!weekPlan) return false;
  const days = weekPlan.weeks?.[0]?.days ?? [];
  for (const day of days) {
    if (day.outdoor_session_status === "done") return true;
    if (normalizeOtherActivities(day).some((oa) => oa.status === "completed")) return true;
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
  // B396 — the sheet's chunk is fetched on the first tap, then stays mounted
  // (so closing still animates).
  const [sheetMounted, setSheetMounted] = useState(false);

  const targetMonday = getTargetMonday();

  // A286 — il dismiss veniva scritto in sessionStorage e mai riletto.
  // B396 — e sessionStorage iOS lo azzera quando chiude la PWA: la card
  // tornava a ogni riapertura. Ora sta in localStorage (lib/checkin-dismiss)
  // ed è letto con useSyncExternalStore: nel render client è già noto (la card
  // non compare un frame dopo spingendo giù Start); nel render server è
  // `null` e non renderizziamo, come prima.
  const dismissedFor = useSyncExternalStore<string | null>(
    subscribeCheckinDismissed,
    readCheckinDismissed,
    () => null,
  );
  const dismissed = dismissedFor === null ? null : dismissedFor === targetMonday;

  // Tue–Sat: banner hidden entirely.
  if (!targetMonday) return null;
  if (dismissed === null) return null;

  // Monday: block when the current week already has completed activity.
  // Sunday: target is next week (freshly generated, no completed activity by definition).
  const isMonday = new Date().getDay() === 1;
  if (isMonday && hasCompletedActivity(weekPlan)) return null;

  if (dismissed) return null;

  function handleDismiss() {
    if (targetMonday) writeCheckinDismissed(targetMonday);
  }

  return (
    <>
      <Card
        className="border-primary/30 bg-primary/5 cursor-pointer hover:bg-primary/10 transition-colors"
        onClick={() => {
          setSheetMounted(true);
          setSheetOpen(true);
        }}
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

      {sheetMounted && (
        <WeeklyCheckinSheet
          open={sheetOpen}
          nextWeekStart={targetMonday}
          onClose={() => {
            setSheetOpen(false);
            handleDismiss();
          }}
          onPlanUpdated={onPlanUpdated}
        />
      )}
    </>
  );
}
